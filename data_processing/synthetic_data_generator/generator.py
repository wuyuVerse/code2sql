"""
合成数据生成器核心逻辑
"""
import json
import time
import uuid
import random
import threading
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.llm_client import LLMClient
from config.data_processing.synthetic_data_generator.config import SyntheticDataConfig
from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM, PROMPT_CALLER, PROMPT_META
from utils.format_validators import validate_json_format

# 线程锁用于保护共享资源
_print_lock = threading.Lock()
_stats_lock = threading.Lock()

# 全局统计
_generation_stats = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "total_tokens": 0
}


class SyntheticDataGenerator:
    """合成数据生成器"""
    
    def __init__(self, config: SyntheticDataConfig):
        """初始化生成器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.llm_client = LLMClient(config.llm_server)
        self.full_scenarios = self._load_full_scenarios()
        self._session = None
    
    @property
    def session(self):
        """获取aiohttp session（懒加载）"""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session
    
    def _load_full_scenarios(self) -> Dict:
        """加载full_scenario.json文件"""
        try:
            with open(self.config.full_scenario_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 无法加载 {self.config.full_scenario_path}: {e}")
            return {}
    
    def _get_scenario_example(self, scenario: str) -> Optional[Dict]:
        """根据场景标签获取第一个匹配的样例"""
        for key, value in self.full_scenarios.items():
            if value.get('scenario') == scenario:
                return {key: value}
        return None
    
    def _format_example_for_prompt(self, example: Dict, remove_fields: Optional[List[str]] = None) -> str:
        """格式化样例用于提示词显示"""
        if not example:
            return "无样例数据"
        
        if remove_fields is None:
            remove_fields = ["code_file", "code_version", "code_label", "code_type", 
                            "code_start_line", "code_end_line", "code_start_column"]
        
        # 深拷贝以避免修改原始数据
        example_copy = json.loads(json.dumps(example))
        
        # 递归移除不需要的字段
        def remove_unwanted_fields(obj):
            if isinstance(obj, dict):
                for field in remove_fields:
                    obj.pop(field, None)
                for value in obj.values():
                    remove_unwanted_fields(value)
            elif isinstance(obj, list):
                for item in obj:
                    remove_unwanted_fields(item)
        
        remove_unwanted_fields(example_copy)
        
        return json.dumps(example_copy, indent=2, ensure_ascii=False)
    
    def _clean_json_response(self, response: str) -> str:
        """清理LLM响应，提取JSON部分"""
        # 移除可能的markdown代码块标记
        response = response.replace("```json", "").replace("```", "")
        response = response.strip()
        
        # 查找JSON开始和结束位置
        start_idx = -1
        end_idx = -1
        
        # 查找第一个 { 或 [
        for i, char in enumerate(response):
            if char in ['{', '[']:
                start_idx = i
                break
        
        if start_idx == -1:
            return response
        
        # 查找匹配的结束符
        bracket_count = 0
        start_char = response[start_idx]
        end_char = '}' if start_char == '{' else ']'
        
        for i in range(start_idx, len(response)):
            if response[i] == start_char:
                bracket_count += 1
            elif response[i] == end_char:
                bracket_count -= 1
                if bracket_count == 0:
                    end_idx = i
                    break
        
        if end_idx == -1:
            return response[start_idx:]
        
        return response[start_idx:end_idx + 1]
    
    def _thread_safe_print(self, *args, **kwargs):
        """线程安全的打印函数"""
        with _print_lock:
            print(*args, **kwargs)
    
    def _update_stats(self, success: bool, tokens: int = 0):
        """更新全局统计信息"""
        with _stats_lock:
            _generation_stats["total_requests"] += 1
            if success:
                _generation_stats["successful_requests"] += 1
            else:
                _generation_stats["failed_requests"] += 1
            _generation_stats["total_tokens"] += tokens
    
    async def _call_llm(self, prompt: str, request_type: str = "unknown") -> str:
        """调用大语言模型（异步）"""
        try:
            thread_id = threading.current_thread().name
            self._thread_safe_print(f"[{thread_id}] 开始 {request_type} 请求...")
            
            # 根据请求类型选择验证器
            from utils.format_validators import validate_synthetic_data_response
            if request_type.lower() in ['caller', 'meta']:
                validator = lambda x: validate_synthetic_data_response(x, request_type.lower())
            else:
                validator = validate_json_format
            
            # 使用格式验证调用LLM
            response = await self.llm_client.call_async_with_format_validation(
                self.session,
                prompt,
                validator=validator,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                module="synthetic_data_generator"
            )
            # 处理响应结果
            if isinstance(response, dict) and 'valid' in response:
                if response['valid']:
                    content = response.get('content', '')
                else:
                    raise ValueError(f"格式验证失败: {response.get('error', '未知错误')}")
            else:
                content = str(response) if response else ""
            content = content.strip()
            tokens = len(content.split())  # 简单估算token数
            self._update_stats(True, tokens)
            self._thread_safe_print(f"[{thread_id}] {request_type} 请求完成 (tokens: {tokens})")
            return content
        except Exception as e:
            self._update_stats(False)
            self._thread_safe_print(f"[{threading.current_thread().name}] 调用LLM时出错 ({request_type}): {e}")
            raise
    
    async def _call_llm_parallel(self, prompts_and_types: List[Tuple[str, str]]) -> List[str]:
        """并行调用多个LLM请求（异步版本）"""
        # 创建异步任务
        tasks = []
        for prompt, request_type in prompts_and_types:
            task = self._call_llm(prompt, request_type)
            tasks.append(task)
        
        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._thread_safe_print(f"并行请求失败 (index {i}): {result}")
                raise result
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def generate_pack(self, scenario: str) -> Dict:
        """为给定场景标签生成*一个*合成包（串行版本，异步）"""
        
        # 特殊处理with_first场景
        if scenario == "with_first":
            return await self._generate_with_first_pack()
            
        # 特殊处理with_take场景
        if scenario == "with_take":
            return await self._generate_with_take_pack()
            
        # 特殊处理with_last场景
        if scenario == "with_last":
            return await self._generate_with_last_pack()
            
        # 特殊处理with_find_no_limit场景
        if scenario == "with_find_no_limit":
            return await self._generate_with_find_no_limit_pack()
            
        # 特殊处理with_count场景
        if scenario == "with_count":
            return await self._generate_with_count_pack()
            
        self._thread_safe_print(f"正在生成场景: {scenario}")
        var_names = self.config.get_random_names()
        scenario_desc = self.config.get_scenario_description(scenario)
        example = self._get_scenario_example(scenario)
        example_str = self._format_example_for_prompt(example) if example else "无对应场景样例"
        if example:
            self._thread_safe_print(f"  - 找到场景样例: {list(example.keys())[0]}")
        else:
            self._thread_safe_print(f"  - 未找到场景样例，将使用通用模板")
        # 1) ORM代码块
        self._thread_safe_print("  - 生成ORM代码块...")
        from utils.format_validators import validate_synthetic_data_response
        
        # 根据场景选择不同的ORM提示词模板
        if scenario == "if-else+caller":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_IF_ELSE_CALLER
            orm_prompt = PROMPT_ORM_IF_ELSE_CALLER.format(
                example=example_str,
                **var_names
            )
        elif scenario == "switch":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_SWITCH
            orm_prompt = PROMPT_ORM_SWITCH.format(
                example=example_str,
                **var_names
            )
        elif scenario == "if-else+orm":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_IF_ELSE_ORM
            orm_prompt = PROMPT_ORM_IF_ELSE_ORM.format(
                example=example_str,
                **var_names
            )
        elif scenario == "mutual_exclusive_conditions":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_MUTUAL_EXCLUSIVE
            orm_prompt = PROMPT_ORM_MUTUAL_EXCLUSIVE.format(
                example=example_str,
                **var_names
            )
        elif scenario == "table_name_from_caller":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_TABLE_NAME_FROM_CALLER
            orm_prompt = PROMPT_ORM_TABLE_NAME_FROM_CALLER.format(
                scenario=scenario,
                scenario_desc=scenario_desc,
                example=example_str,
                **var_names
            )
        elif scenario == "no-where":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_NO_WHERE
            orm_prompt = PROMPT_ORM_NO_WHERE.format(
                example=example_str,
                **var_names
            )
        elif scenario == "table_mapping_incomplete":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_TABLE_MAPPING_INCOMPLETE
            orm_prompt = PROMPT_ORM_TABLE_MAPPING_INCOMPLETE.format(
                example=example_str,
                **var_names
            )
        elif scenario == "condition_field_mapping":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_CONDITION_FIELD_MAPPING
            orm_prompt = PROMPT_ORM_CONDITION_FIELD_MAPPING.format(
                example=example_str,
                **var_names
            )
        elif scenario == "where_condition_with_fixed_values":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_WHERE_FIXED_VALUES
            orm_prompt = PROMPT_ORM_WHERE_FIXED_VALUES.format(
                example=example_str,
                **var_names
            )
        elif scenario == "raw_sql_in_code":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_RAW_SQL_IN_CODE
            orm_prompt = PROMPT_ORM_RAW_SQL_IN_CODE.format(
                example=example_str,
                **var_names
            )
        else:
            orm_prompt = PROMPT_ORM.format(
                scenario=scenario,
                scenario_desc=scenario_desc,
                example=example_str,
                **var_names
            )
        
        orm_response = await self.llm_client.call_async_with_format_validation(
            self.session,
            orm_prompt,
            validator=lambda x: validate_synthetic_data_response(x, 'orm'),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="synthetic_data_generator"
        )
        if isinstance(orm_response, dict) and 'valid' in orm_response:
            if orm_response['valid']:
                orm_json = orm_response.get('content', '')
            else:
                raise ValueError(f"ORM格式验证失败: {orm_response.get('error', '未知错误')}")
        else:
            orm_json = self._clean_json_response(str(orm_response))
        try:
            orm_block = json.loads(orm_json)
        except json.JSONDecodeError as e:
            self._thread_safe_print(f"解析ORM JSON失败: {e}")
            self._thread_safe_print(f"原始响应: {orm_response}")
            self._thread_safe_print(f"清理后: {orm_json}")
            raise
        if 'callers' not in orm_block:
            orm_block['callers'] = []
        # 2) 调用者代码块
        if scenario == "no-where":
            # no-where场景不需要生成caller，直接使用空数组
            self._thread_safe_print("  - no-where场景跳过caller生成...")
            caller_blocks = []
        elif scenario == "table_name_from_caller":
            # table_name_from_caller场景必须生成caller，因为表名信息依赖于caller
            self._thread_safe_print("  - table_name_from_caller场景必须生成caller...")
            example_caller = "无样例数据"
            if example:
                example_data = list(example.values())[0]
                if 'callers' in example_data and example_data['callers']:
                    caller_data = example_data['callers'][0]
                    caller_clean = {k: v for k, v in caller_data.items() 
                                  if k not in ["code_file", "code_version", "code_label", "code_type", 
                                             "code_start_line", "code_end_line", "code_start_column"]}
                    example_caller = json.dumps(caller_clean, indent=2, ensure_ascii=False)
            
            # 使用table_name_from_caller专用的Caller提示词
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_TABLE_NAME_FROM_CALLER
            caller_prompt = PROMPT_CALLER_TABLE_NAME_FROM_CALLER.format(
                orm_block=json.dumps(orm_block, ensure_ascii=False),
                example_caller=example_caller,
                **var_names
            )
            
            caller_response = await self._call_llm(caller_prompt, "Caller")
            caller_json = self._clean_json_response(caller_response)
            try:
                caller_data = json.loads(caller_json)
                
                # 处理 caller 数据：如果是数组，转换为多个 callers；如果是单个对象，包装成数组
                if isinstance(caller_data, list):
                    # LLM 返回了数组格式，直接使用
                    caller_blocks = caller_data
                    self._thread_safe_print(f"  - 检测到多个 callers: {len(caller_blocks)} 个")
                elif isinstance(caller_data, dict):
                    # LLM 返回了单个对象，包装成数组
                    caller_blocks = [caller_data]
                    self._thread_safe_print(f"  - 检测到单个 caller")
                else:
                    raise ValueError(f"Caller 数据格式不正确: {type(caller_data)}")
                    
                # 确保callers不为空
                if not caller_blocks:
                    raise ValueError("table_name_from_caller场景必须生成caller，但生成的callers为空")
                    
            except json.JSONDecodeError as e:
                self._thread_safe_print(f"解析调用者JSON失败: {e}")
                self._thread_safe_print(f"原始响应: {caller_response}")
                self._thread_safe_print(f"清理后: {caller_json}")
                raise
        elif scenario == "mutual_exclusive_conditions":
            # mutual_exclusive_conditions场景必须生成caller，因为filter条件信息依赖于caller
            self._thread_safe_print("  - mutual_exclusive_conditions场景必须生成caller...")
            example_caller = "无样例数据"
            if example:
                example_data = list(example.values())[0]
                if 'callers' in example_data and example_data['callers']:
                    caller_data = example_data['callers'][0]
                    caller_clean = {k: v for k, v in caller_data.items() 
                                  if k not in ["code_file", "code_version", "code_label", "code_type", 
                                             "code_start_line", "code_end_line", "code_start_column"]}
                    example_caller = json.dumps(caller_clean, indent=2, ensure_ascii=False)
            
            # 使用mutual_exclusive_conditions专用的Caller提示词
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_MUTUAL_EXCLUSIVE
            caller_prompt = PROMPT_CALLER_MUTUAL_EXCLUSIVE.format(
                orm_block=json.dumps(orm_block, ensure_ascii=False),
                example_caller=example_caller,
                **var_names
            )
            
            caller_response = await self._call_llm(caller_prompt, "Caller")
            caller_json = self._clean_json_response(caller_response)
            try:
                caller_data = json.loads(caller_json)
                
                # 处理 caller 数据：如果是数组，转换为多个 callers；如果是单个对象，包装成数组
                if isinstance(caller_data, list):
                    # LLM 返回了数组格式，直接使用
                    caller_blocks = caller_data
                    self._thread_safe_print(f"  - 检测到多个 callers: {len(caller_blocks)} 个")
                elif isinstance(caller_data, dict):
                    # LLM 返回了单个对象，包装成数组
                    caller_blocks = [caller_data]
                    self._thread_safe_print(f"  - 检测到单个 caller")
                else:
                    raise ValueError(f"Caller 数据格式不正确: {type(caller_data)}")
                    
                # 确保callers不为空
                if not caller_blocks:
                    raise ValueError("mutual_exclusive_conditions场景必须生成caller，但生成的callers为空")
                    
            except json.JSONDecodeError as e:
                self._thread_safe_print(f"解析调用者JSON失败: {e}")
                self._thread_safe_print(f"原始响应: {caller_response}")
                self._thread_safe_print(f"清理后: {caller_json}")
                raise
        else:
            self._thread_safe_print("  - 生成调用者代码块...")
            example_caller = "无样例数据"
            if example:
                example_data = list(example.values())[0]
                if 'callers' in example_data and example_data['callers']:
                    caller_data = example_data['callers'][0]
                    caller_clean = {k: v for k, v in caller_data.items() 
                                  if k not in ["code_file", "code_version", "code_label", "code_type", 
                                             "code_start_line", "code_end_line", "code_start_column"]}
                    example_caller = json.dumps(caller_clean, indent=2, ensure_ascii=False)
            
            # 根据场景选择不同的Caller提示词模板
            if scenario == "if-else+caller":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_IF_ELSE
                caller_prompt = PROMPT_CALLER_IF_ELSE.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "switch":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_SWITCH
                caller_prompt = PROMPT_CALLER_SWITCH.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "if-else+orm":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_IF_ELSE_ORM
                caller_prompt = PROMPT_CALLER_IF_ELSE_ORM.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "table_mapping_incomplete":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_TABLE_MAPPING_INCOMPLETE
                caller_prompt = PROMPT_CALLER_TABLE_MAPPING_INCOMPLETE.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "condition_field_mapping":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_CONDITION_FIELD_MAPPING
                caller_prompt = PROMPT_CALLER_CONDITION_FIELD_MAPPING.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "where_condition_with_fixed_values":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_WHERE_FIXED_VALUES
                caller_prompt = PROMPT_CALLER_WHERE_FIXED_VALUES.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )

            else:
                caller_prompt = PROMPT_CALLER.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            caller_response = await self._call_llm(caller_prompt, "Caller")
            caller_json = self._clean_json_response(caller_response)
            try:
                caller_data = json.loads(caller_json)
                
                # 处理 caller 数据：如果是数组，转换为多个 callers；如果是单个对象，包装成数组
                if isinstance(caller_data, list):
                    # LLM 返回了数组格式，直接使用
                    caller_blocks = caller_data
                    self._thread_safe_print(f"  - 检测到多个 callers: {len(caller_blocks)} 个")
                elif isinstance(caller_data, dict):
                    # LLM 返回了单个对象，包装成数组
                    caller_blocks = [caller_data]
                    self._thread_safe_print(f"  - 检测到单个 caller")
                else:
                    raise ValueError(f"Caller 数据格式不正确: {type(caller_data)}")
                    
            except json.JSONDecodeError as e:
                self._thread_safe_print(f"解析调用者JSON失败: {e}")
                self._thread_safe_print(f"原始响应: {caller_response}")
                self._thread_safe_print(f"清理后: {caller_json}")
                raise
        # 3) 元数据
        self._thread_safe_print("  - 生成元数据...")
        example_meta = "无样例数据"
        if example:
            example_data = list(example.values())[0]
            if 'code_meta_data' in example_data:
                meta_data = example_data['code_meta_data']
                meta_clean = []
                for item in meta_data:
                    item_clean = {k: v for k, v in item.items() 
                                if k not in ["code_file", "code_version", "code_label", "code_type", 
                                           "code_start_line", "code_end_line", "code_start_column"]}
                    meta_clean.append(item_clean)
                example_meta = json.dumps(meta_clean, indent=2, ensure_ascii=False)
        # 使用第一个 caller 作为 meta 提示的参考
        first_caller = caller_blocks[0] if caller_blocks else {}
        
        # 根据场景选择不同的元数据提示词模板
        if scenario == "table_mapping_incomplete":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_META_TABLE_MAPPING_INCOMPLETE
            meta_prompt = PROMPT_META_TABLE_MAPPING_INCOMPLETE.format(
                orm_block=json.dumps(orm_block, ensure_ascii=False),
                caller_block=json.dumps(first_caller, ensure_ascii=False),
                example_meta=example_meta,
                **var_names
            )
        else:
            meta_prompt = PROMPT_META.format(
                orm_block=json.dumps(orm_block, ensure_ascii=False),
                caller_block=json.dumps(first_caller, ensure_ascii=False),
                example_meta=example_meta,
                **var_names
            )
        meta_response = await self._call_llm(meta_prompt, "Meta")
        meta_json = self._clean_json_response(meta_response)
        try:
            meta_block = json.loads(meta_json)
        except json.JSONDecodeError as e:
            self._thread_safe_print(f"解析元数据JSON失败: {e}")
            self._thread_safe_print(f"原始响应: {meta_response}")
            self._thread_safe_print(f"清理后: {meta_json}")
            raise
        pack_key = f"synthetic_{scenario.replace('+', '_').replace(' ', '_').replace('(', '').replace(')', '')}_{orm_block['code_key']}"
        pack = {
            pack_key: {
                **orm_block,
                "code_meta_data": meta_block,
                "callers": caller_blocks,
            }
        }
        self._thread_safe_print(f"  - 成功生成包: {pack_key}")
        return pack
    
    async def generate_pack_parallel(self, scenario: str) -> Dict:
        """为给定场景标签生成*一个*合成包（并行版本）"""
        # 特殊处理 with_* 场景，将其重定向到专用的生成方法
        if scenario.startswith("with_"):
            # _generate_with_method_pack 是所有 with_* 场景的统一处理器，
            # 它会内部处理“选择基础场景 -> 修改代码”的逻辑。
            method_type = scenario.replace("with_", "")
            self._thread_safe_print(f"[并行] 检测到`with_*`场景，重定向到增强方法: {method_type}")
            return await self._generate_with_method_pack(method_type)

        self._thread_safe_print(f"[并行] 正在生成场景: {scenario}")
        
        # 获取随机变量名
        var_names = self.config.get_random_names()
        scenario_desc = self.config.get_scenario_description(scenario)
        
        # 获取场景样例
        example = self._get_scenario_example(scenario)
        example_str = self._format_example_for_prompt(example) if example else "无对应场景样例"
        
        if example:
            self._thread_safe_print(f"  - 找到场景样例: {list(example.keys())[0]}")
        else:
            self._thread_safe_print(f"  - 未找到场景样例，将使用通用模板")
        
        # 提取样例信息（为后续请求准备）
        example_caller = "无样例数据"
        example_meta = "无样例数据"
        
        if example:
            example_data = list(example.values())[0]
            
            # 准备caller样例
            if 'callers' in example_data and example_data['callers']:
                caller_data = example_data['callers'][0]
                caller_clean = {k: v for k, v in caller_data.items() 
                              if k not in ["code_file", "code_version", "code_label", "code_type", 
                                         "code_start_line", "code_end_line", "code_start_column"]}
                example_caller = json.dumps(caller_clean, indent=2, ensure_ascii=False)
            
            # 准备meta样例
            if 'code_meta_data' in example_data:
                meta_data = example_data['code_meta_data']
                meta_clean = []
                for item in meta_data:
                    item_clean = {k: v for k, v in item.items() 
                                if k not in ["code_file", "code_version", "code_label", "code_type", 
                                           "code_start_line", "code_end_line", "code_start_column"]}
                    meta_clean.append(item_clean)
                example_meta = json.dumps(meta_clean, indent=2, ensure_ascii=False)
        
        # 第一阶段：生成ORM代码块
        self._thread_safe_print("  - [阶段1] 生成ORM代码块...")
        
        # 根据场景选择不同的ORM提示词模板
        if scenario == "if-else+caller":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_IF_ELSE_CALLER
            orm_prompt = PROMPT_ORM_IF_ELSE_CALLER.format(
                example=example_str,
                **var_names
            )
        elif scenario == "switch":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_SWITCH
            orm_prompt = PROMPT_ORM_SWITCH.format(
                example=example_str,
                **var_names
            )
        elif scenario == "if-else+orm":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_IF_ELSE_ORM
            orm_prompt = PROMPT_ORM_IF_ELSE_ORM.format(
                example=example_str,
                **var_names
            )
        elif scenario == "mutual_exclusive_conditions":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_MUTUAL_EXCLUSIVE
            orm_prompt = PROMPT_ORM_MUTUAL_EXCLUSIVE.format(
                example=example_str,
                **var_names
            )
        elif scenario == "table_name_from_caller":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_TABLE_NAME_FROM_CALLER
            orm_prompt = PROMPT_ORM_TABLE_NAME_FROM_CALLER.format(
                example=example_str,
                **var_names
            )
        elif scenario == "no-where":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_NO_WHERE
            orm_prompt = PROMPT_ORM_NO_WHERE.format(
                example=example_str,
                **var_names
            )
        elif scenario == "table_mapping_incomplete":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_TABLE_MAPPING_INCOMPLETE
            orm_prompt = PROMPT_ORM_TABLE_MAPPING_INCOMPLETE.format(
                example=example_str,
                **var_names
            )
        elif scenario == "condition_field_mapping":
            from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_CONDITION_FIELD_MAPPING
            orm_prompt = PROMPT_ORM_CONDITION_FIELD_MAPPING.format(
                example=example_str,
                **var_names
            )
        else:
            orm_prompt = PROMPT_ORM.format(
                scenario=scenario,
                scenario_desc=scenario_desc,
                example=example_str,
                **var_names
            )
        
        orm_response = await self._call_llm(orm_prompt, "ORM")
        orm_json = self._clean_json_response(orm_response)
        
        try:
            orm_block = json.loads(orm_json)
        except json.JSONDecodeError as e:
            self._thread_safe_print(f"解析ORM JSON失败: {e}")
            raise
        
        # 确保必要的字段存在
        if 'callers' not in orm_block:
            orm_block['callers'] = []
        
        # 第二阶段：并行生成Caller和Meta
        if scenario == "no-where":
            # no-where场景不需要生成caller，直接使用空数组
            self._thread_safe_print("  - [阶段2] no-where场景跳过caller生成，只生成Meta...")
            caller_blocks = []
            
            # 只生成Meta
            meta_prompt = PROMPT_META.format(
                orm_block=json.dumps(orm_block, ensure_ascii=False),
                caller_block="",  # 这里暂时为空，因为我们没有caller
                example_meta=example_meta,
                **var_names
            )
            
            meta_response = await self._call_llm(meta_prompt, "Meta")
            meta_json = self._clean_json_response(meta_response)
            
            try:
                meta_block = json.loads(meta_json)
            except json.JSONDecodeError as e:
                self._thread_safe_print(f"解析Meta JSON失败: {e}")
                raise
        else:
            self._thread_safe_print("  - [阶段2] 并行生成Caller和Meta...")
            
            # 准备并行请求
            # 根据场景选择不同的Caller提示词模板
            if scenario == "if-else+caller":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_IF_ELSE
                caller_prompt = PROMPT_CALLER_IF_ELSE.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "switch":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_SWITCH
                caller_prompt = PROMPT_CALLER_SWITCH.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "if-else+orm":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_IF_ELSE_ORM
                caller_prompt = PROMPT_CALLER_IF_ELSE_ORM.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "mutual_exclusive_conditions":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_MUTUAL_EXCLUSIVE
                caller_prompt = PROMPT_CALLER_MUTUAL_EXCLUSIVE.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "table_name_from_caller":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_TABLE_NAME_FROM_CALLER
                caller_prompt = PROMPT_CALLER_TABLE_NAME_FROM_CALLER.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "table_mapping_incomplete":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_TABLE_MAPPING_INCOMPLETE
                caller_prompt = PROMPT_CALLER_TABLE_MAPPING_INCOMPLETE.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            elif scenario == "condition_field_mapping":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_CALLER_CONDITION_FIELD_MAPPING
                caller_prompt = PROMPT_CALLER_CONDITION_FIELD_MAPPING.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            else:
                caller_prompt = PROMPT_CALLER.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    example_caller=example_caller,
                    **var_names
                )
            
            # 先获取caller，然后再生成meta
            caller_response = await self._call_llm(caller_prompt, "Caller")
            caller_json = self._clean_json_response(caller_response)
            try:
                caller_data = json.loads(caller_json)
                
                # 处理 caller 数据：如果是数组，转换为多个 callers；如果是单个对象，包装成数组
                if isinstance(caller_data, list):
                    # LLM 返回了数组格式，直接使用
                    caller_blocks = caller_data
                    self._thread_safe_print(f"  - 检测到多个 callers: {len(caller_blocks)} 个")
                elif isinstance(caller_data, dict):
                    # LLM 返回了单个对象，包装成数组
                    caller_blocks = [caller_data]
                    self._thread_safe_print(f"  - 检测到单个 caller")
                else:
                    raise ValueError(f"Caller 数据格式不正确: {type(caller_data)}")
                    
            except json.JSONDecodeError as e:
                self._thread_safe_print(f"解析Caller JSON失败: {e}")
                raise
            
            # 使用第一个caller作为meta生成的参考
            caller_block_for_meta = json.dumps(caller_blocks[0], ensure_ascii=False) if caller_blocks else ""
            
            # 根据场景选择不同的元数据提示词模板
            if scenario == "table_mapping_incomplete":
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_META_TABLE_MAPPING_INCOMPLETE
                meta_prompt = PROMPT_META_TABLE_MAPPING_INCOMPLETE.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    caller_block=caller_block_for_meta,
                    example_meta=example_meta,
                    **var_names
                )
            else:
                meta_prompt = PROMPT_META.format(
                    orm_block=json.dumps(orm_block, ensure_ascii=False),
                    caller_block=caller_block_for_meta,
                    example_meta=example_meta,
                    **var_names
                )
            
            # 生成meta
            meta_response = await self._call_llm(meta_prompt, "Meta")
            meta_json = self._clean_json_response(meta_response)
            
            try:
                meta_block = json.loads(meta_json)
            except json.JSONDecodeError as e:
                self._thread_safe_print(f"解析Meta JSON失败: {e}")
                raise
        
        # 组装最终字典
        pack_key = f"synthetic_{scenario.replace('+', '_').replace(' ', '_').replace('(', '').replace(')', '')}_{orm_block['code_key']}"
        pack = {
            pack_key: {
                **orm_block,
                "code_meta_data": meta_block,
                "callers": caller_blocks,
            }
        }
        
        self._thread_safe_print(f"  - [并行] 成功生成包: {pack_key}")
        return pack
    
    async def generate_multiple_packs_parallel(self, scenarios_and_counts: List[Tuple[str, int]]) -> Dict:
        """并行生成多个场景的数据包（异步版本）"""
        all_packs = {}
        
        # 创建所有任务
        tasks = []
        for scenario, count in scenarios_and_counts:
            for i in range(count):
                tasks.append((scenario, i + 1, count))
        
        self._thread_safe_print(f"开始并行生成 {len(tasks)} 个数据包...")
        
        async def generate_single_task(args):
            scenario, index, total = args
            thread_id = threading.current_thread().name
            self._thread_safe_print(f"[{thread_id}] 开始生成 {scenario} ({index}/{total})")
            
            try:
                pack = await self.generate_pack_parallel(scenario)
                self._thread_safe_print(f"[{thread_id}] 完成 {scenario} ({index}/{total})")
                return pack
            except Exception as e:
                self._thread_safe_print(f"[{thread_id}] 生成失败 {scenario} ({index}/{total}): {e}")
                return None
        
        # 并发执行所有任务
        results = await asyncio.gather(*[generate_single_task(task) for task in tasks], return_exceptions=True)
            
        # 处理结果
        completed = 0
        for i, result in enumerate(results):
            completed += 1
            if isinstance(result, Exception):
                self._thread_safe_print(f"任务执行失败: {result}")
            elif result and isinstance(result, dict):
                all_packs.update(result)
                self._thread_safe_print(f"进度: {completed}/{len(tasks)} 完成")
        
        return all_packs
    
    def validate_pack(self, pack: Dict) -> bool:
        """验证生成的包是否符合预期格式"""
        for key, value in pack.items():
            required_fields = ['scenario', 'code_key', 'code_value', 
                              'sql_pattern_cnt', 'callers', 'code_meta_data']
            
            for field in required_fields:
                if field not in value:
                    print(f"警告: 包 {key} 缺少必需字段: {field}")
                    return False
            
            # 验证callers结构
            if not isinstance(value['callers'], list) or len(value['callers']) == 0:
                print(f"警告: 包 {key} 的callers字段格式不正确")
                return False
            
            caller = value['callers'][0]
            caller_required = ['code_key', 'code_value']
            for field in caller_required:
                if field not in caller:
                    print(f"警告: 包 {key} 的caller缺少字段: {field}")
                    return False
                    
            # 验证code_meta_data结构
            if not isinstance(value['code_meta_data'], list):
                print(f"警告: 包 {key} 的code_meta_data不是数组")
                return False
        
        return True
    
    def print_generation_stats(self):
        """打印生成统计信息"""
        with _stats_lock:
            stats = _generation_stats.copy()
        
        self._thread_safe_print(f"\n📊 生成统计:")
        self._thread_safe_print(f"  - 总请求数: {stats['total_requests']}")
        self._thread_safe_print(f"  - 成功请求: {stats['successful_requests']}")
        self._thread_safe_print(f"  - 失败请求: {stats['failed_requests']}")
        self._thread_safe_print(f"  - 成功率: {stats['successful_requests']/max(stats['total_requests'], 1)*100:.1f}%")
        self._thread_safe_print(f"  - 总Token数: {stats['total_tokens']}")
        if stats['successful_requests'] > 0:
            self._thread_safe_print(f"  - 平均Token/请求: {stats['total_tokens']/stats['successful_requests']:.0f}") 

    def _get_base_scenarios_for_with_methods(self) -> List[str]:
        """获取用于with_first、with_take、with_last、with_find_no_limit、with_count场景的基础场景列表
        
        Returns:
            排除了所有with_*场景的基础场景列表
        """
        all_scenarios = self.config.list_scenarios()
        # 排除所有with_*场景
        excluded_scenarios = {"with_first", "with_take", "with_last", "with_find_no_limit", "with_count"}
        base_scenarios = [s for s in all_scenarios if s not in excluded_scenarios]
        return base_scenarios

    async def _generate_with_method_pack(self, method_type: str) -> Dict:
        """生成with_*场景的通用方法
        
        Args:
            method_type: 方法类型，支持 "first", "take", "last"
            
        Returns:
            生成的数据包
        """
        scenario_name = f"with_{method_type}"
        self._thread_safe_print(f"开始生成{scenario_name}场景数据包...")
        
                # 获取对应的提示词模板
        method_templates = {
            "first": {
                "judge": "PROMPT_WITH_FIRST_JUDGE",
                "generate": "PROMPT_WITH_FIRST_GENERATE",
                "can_add_field": "can_add_first"
            },
            "take": {
                "judge": "PROMPT_WITH_TAKE_JUDGE", 
                "generate": "PROMPT_WITH_TAKE_GENERATE",
                "can_add_field": "can_add_take"
            },
            "last": {
                "judge": "PROMPT_WITH_LAST_JUDGE",
                "generate": "PROMPT_WITH_LAST_GENERATE", 
                "can_add_field": "can_add_last"
            },
            "find_no_limit": {
                "judge": "PROMPT_WITH_FIND_NO_LIMIT_JUDGE",
                "generate": "PROMPT_WITH_FIND_NO_LIMIT_GENERATE",
                "can_add_field": "can_use_find_no_limit"
            },
            "count": {
                "judge": "PROMPT_WITH_COUNT_JUDGE",
                "generate": "PROMPT_WITH_COUNT_GENERATE",
                "can_add_field": "can_use_count"
            }
        }
        
        if method_type not in method_templates:
            raise ValueError(f"不支持的方法类型: {method_type}")
            
        templates = method_templates[method_type]
        
        # 第一步：生成基础场景数据包
        self._thread_safe_print("  - 第一步：生成基础场景数据包...")
        base_scenarios = self._get_base_scenarios_for_with_methods()
        
        import random
        base_scenario = random.choice(base_scenarios)
        self._thread_safe_print(f"  - 选择基础场景: {base_scenario}")
        
        # 生成基础数据包
        base_pack = await self.generate_pack(base_scenario)
        if not base_pack:
            self._thread_safe_print("  - 基础数据包生成失败")
            return {}
        
        # 获取基础数据包中的ORM代码和caller代码
        pack_key = list(base_pack.keys())[0]
        orm_code = base_pack[pack_key].get('code_value', '')
        original_scenario = base_pack[pack_key].get('scenario', '')
        original_code_meta_data = base_pack[pack_key].get('code_meta_data', [])
        caller_code = ''
        
        if 'callers' in base_pack[pack_key] and base_pack[pack_key]['callers']:
            caller_data = base_pack[pack_key]['callers'][0]
            caller_code = caller_data.get('code_value', '')
        
        # 第二步：判断是否可以添加对应方法
        self._thread_safe_print(f"  - 第二步：判断是否可以添加{method_type.title()}()方法...")
        
        # 获取随机变量名（如果需要的话）
        var_names = self.config.get_random_names()
        
        # 动态导入判断提示词
        from config.data_processing.synthetic_data_generator import prompts
        judge_prompt_template = getattr(prompts, templates["judge"])
        
        # 尝试格式化，如果模板需要更多参数就提供
        try:
            judge_prompt = judge_prompt_template.format(orm_code=orm_code)
        except Exception as e:
            # 如果需要更多参数，提供完整的参数集
            try:
                judge_prompt = judge_prompt_template.format(
                    orm_code=orm_code,
                    **var_names
                )
            except Exception as e2:
                raise
        
        judge_response = await self.llm_client.call_async_with_format_validation(
            self.session,
            judge_prompt,
            validator=lambda x: True,  # 简单的JSON验证
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="synthetic_data_generator"
        )
        
        if isinstance(judge_response, dict) and 'valid' in judge_response:
            if judge_response['valid']:
                judge_json = judge_response.get('content', '')
            else:
                raise ValueError(f"判断格式验证失败: {judge_response.get('error', '未知错误')}")
        else:
            judge_json = self._clean_json_response(str(judge_response))
        
        try:
            judge_data = json.loads(judge_json)
        except json.JSONDecodeError as e:
            self._thread_safe_print(f"解析判断JSON失败: {e}")
            raise
        
        # 检查是否可以添加对应方法
        if not judge_data.get(templates["can_add_field"], False):
            reason = judge_data.get('reason', '未知原因')
            self._thread_safe_print(f"  - 无法添加{method_type.title()}()方法，原因: {reason}")
            return {}  # 返回空字典表示丢弃
        
        # 第三步：生成添加方法后的完整数据
        self._thread_safe_print(f"  - 第三步：生成添加{method_type.title()}()后的完整数据...")
        
        # 动态导入生成提示词
        generate_prompt_template = getattr(prompts, templates["generate"])
        
        # 准备原始code_meta_data作为参考
        original_code_meta_data_str = ""
        if original_code_meta_data:
            for meta in original_code_meta_data:
                meta_key = meta.get('code_key', '')
                meta_value = meta.get('code_value', '')
                if meta_key and meta_value:
                    original_code_meta_data_str += f"// {meta_key}\n{meta_value}\n\n"
        
        # 尝试格式化，如果模板需要更多参数就提供
        try:
            generate_prompt = generate_prompt_template.format(
                orm_code=orm_code,
                original_scenario=original_scenario,
                caller_code=caller_code,
                original_code_meta_data=original_code_meta_data_str
            )
        except (KeyError, ValueError) as e:
            # 如果需要更多参数，提供完整的参数集
            generate_prompt = generate_prompt_template.format(
                orm_code=orm_code,
                original_scenario=original_scenario,
                caller_code=caller_code,
                original_code_meta_data=original_code_meta_data_str,
                **var_names
            )
        
        generate_response = await self.llm_client.call_async_with_format_validation(
            self.session,
            generate_prompt,
            validator=lambda x: True,  # 简单的JSON验证
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            module="synthetic_data_generator"
        )
        
        if isinstance(generate_response, dict) and 'valid' in generate_response:
            if generate_response['valid']:
                generate_json = generate_response.get('content', '')
            else:
                raise ValueError(f"生成格式验证失败: {generate_response.get('error', '未知错误')}")
        else:
            generate_json = self._clean_json_response(str(generate_response))
        
        try:
            generate_data = json.loads(generate_json)
        except json.JSONDecodeError as e:
            self._thread_safe_print(f"解析生成JSON失败: {e}")
            raise
        
        # 验证生成的数据格式
        required_fields = ['scenario', 'code_key', 'code_value', 'sql_pattern_cnt', 'callers', 'callees', 'code_meta_data']
        for field in required_fields:
            if field not in generate_data:
                self._thread_safe_print(f"  - 生成的数据缺少必需字段: {field}")
                return {}
        
        # 验证scenario字段
        if generate_data['scenario'] != scenario_name:
            self._thread_safe_print(f"  - 生成的scenario字段不正确: {generate_data['scenario']}")
            return {}
        
        # 验证callers和callees是数组
        if not isinstance(generate_data['callers'], list) or not isinstance(generate_data['callees'], list):
            self._thread_safe_print("  - 生成的callers或callees字段不是数组")
            return {}
        
        # 验证code_meta_data是数组
        if not isinstance(generate_data['code_meta_data'], list):
            self._thread_safe_print("  - 生成的code_meta_data字段不是数组")
            return {}
        
        # 构建最终的数据包
        new_pack_key = f"synthetic_{scenario_name}_{generate_data['code_key']}"
        
        # 如果LLM没有生成code_meta_data或生成了空数组，则使用原始数据作为基础
        if not generate_data.get('code_meta_data') or len(generate_data.get('code_meta_data', [])) == 0:
            self._thread_safe_print(f"  - 警告：LLM未生成code_meta_data，使用原始数据作为基础")
            generate_data['code_meta_data'] = original_code_meta_data
        
        new_pack = {new_pack_key: generate_data}
        
        self._thread_safe_print(f"  - 成功生成{scenario_name}数据包: {new_pack_key}")
        return new_pack

    async def _generate_with_first_pack(self) -> Dict:
        """生成with_first场景的数据包"""
        return await self._generate_with_method_pack("first") 

    async def _generate_with_take_pack(self) -> Dict:
        """生成with_take场景的数据包"""
        return await self._generate_with_method_pack("take") 

    async def _generate_with_last_pack(self) -> Dict:
        """生成with_last场景的数据包"""
        return await self._generate_with_method_pack("last")

    async def _generate_with_find_no_limit_pack(self) -> Dict:
        """生成with_find_no_limit场景的数据包"""
        return await self._generate_with_method_pack("find_no_limit")

    async def _generate_with_count_pack(self) -> Dict:
        """生成with_count场景的数据包"""
        return await self._generate_with_method_pack("count") 