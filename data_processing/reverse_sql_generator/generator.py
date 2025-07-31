"""
反向SQL生成器核心逻辑
"""
import json
import asyncio
import random
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from utils.format_validators import validate_synthetic_data_response

from utils.llm_client import LLMClient
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from .sql_generator import SQLGenerator
from .orm_mapper import ORMMapper
from .caller_generator import CallerGenerator
from .control_flow_processor import ControlFlowProcessor
from .case_integrator import CaseIntegrator


class ReverseSQLGenerator:
    """反向SQL生成器 - 从SQL开始生成ORM和Caller代码"""
    
    def __init__(self, config: ReverseSQLConfig):
        """初始化反向生成器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.llm_client = LLMClient(config.llm_server)
        self._session = None
        
        # 初始化各个组件
        self.sql_generator = SQLGenerator(config, self.llm_client)
        self.orm_mapper = ORMMapper(config, self.llm_client)
        self.caller_generator = CallerGenerator(config, self.llm_client)
        self.control_flow_processor = ControlFlowProcessor(config, self.llm_client)
        self.case_integrator = CaseIntegrator(config)
        
        # 失败案例记录
        self.failed_cases = []
    
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
    
    @property
    def session(self):
        """获取aiohttp session（懒加载）"""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _exponential_backoff_delay(self, attempt: int, base_delay: float = 1.0, max_delay: float = 60.0):
        """指数退避延迟
        
        Args:
            attempt: 当前尝试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
        """
        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
        print(f"⏳ 等待 {delay:.1f} 秒后重试...")
        await asyncio.sleep(delay)
    
    async def _retry_with_backoff(self, operation, operation_name: str, max_retries: int = 10):
        """带指数退避的重试机制
        
        Args:
            operation: 要执行的操作（异步函数）
            operation_name: 操作名称（用于日志）
            max_retries: 最大重试次数
            
        Returns:
            操作结果
        """
        for attempt in range(max_retries):
            try:
                print(f"🔄 {operation_name} 尝试 {attempt + 1}/{max_retries}")
                result = await operation()
                
                # 检查结果是否为空或无效
                if result is None or (isinstance(result, str) and not result.strip()):
                    print(f"⚠️ {operation_name} 返回空响应，将重试")
                    if attempt < max_retries - 1:
                        await self._exponential_backoff_delay(attempt)
                        continue
                    else:
                        raise ValueError(f"{operation_name} 返回空响应，已重试 {max_retries} 次")
                
                print(f"✅ {operation_name} 成功")
                return result
            except Exception as e:
                error_msg = str(e)
                print(f"❌ {operation_name} 尝试 {attempt + 1} 失败: {error_msg}")
                
                # 根据错误类型决定是否重试
                if "超时" in error_msg or "timeout" in error_msg.lower():
                    print(f"  - 检测到超时错误，将重试")
                elif "Expecting value" in error_msg or "JSON" in error_msg:
                    print(f"  - 检测到JSON解析错误，将重试")
                elif "连接" in error_msg or "connection" in error_msg.lower():
                    print(f"  - 检测到连接错误，将重试")
                elif "空响应" in error_msg:
                    print(f"  - 检测到空响应错误，将重试")
                else:
                    print(f"  - 未知错误类型，将重试")
                
                if attempt < max_retries - 1:
                    await self._exponential_backoff_delay(attempt)
                else:
                    print(f"❌ {operation_name} 最终失败: 已重试 {max_retries} 次")
                    raise
    
    async def generate_complete_case(self, scenario: str, complexity: str = "simple") -> Dict:
        """生成完整的反向案例
        
        Args:
            scenario: 场景类型
            complexity: 复杂度级别
            
        Returns:
            完整的案例数据
        """
        print(f"开始生成反向案例: {scenario} ({complexity})")
        
        max_retries = self.config.max_retries  # 从配置获取最大重试次数
        
        for attempt in range(max_retries):
            try:
                print(f"🔄 尝试 {attempt + 1}/{max_retries}")
                
                # 步骤1: 生成完整SQL查询
                print("步骤1: 生成完整SQL查询...")
                base_sql = await self._retry_with_backoff(
                    lambda: self.sql_generator.generate_complete_sql(scenario, complexity),
                    "SQL生成"
                )
                print(f"✅ SQL生成成功: {base_sql.get('query', '')[:50]}...")
                
                # 步骤2: 生成ORM代码
                print("步骤2: 生成ORM代码...")
                if scenario == "multi_branch_transaction":
                    # 使用专门的ORM生成方法
                    orm_code = await self._retry_with_backoff(
                        lambda: self.orm_mapper.sql_to_orm_for_multi_branch_transaction(base_sql),
                        "多分支事务处理ORM生成"
                    )
                else:
                    # 使用通用的ORM生成方法
                    orm_code = await self._retry_with_backoff(
                        lambda: self.orm_mapper.sql_to_orm(base_sql),
                        "ORM映射"
                    )
                print(f"✅ ORM生成成功: {orm_code.get('method_name', '')}")
                
                # 步骤3: 生成Caller代码
                print("步骤3: 生成Caller代码...")
                caller_code = await self._retry_with_backoff(
                    lambda: self.caller_generator.generate_caller(orm_code, scenario),
                    "Caller生成"
                )
                print(f"✅ Caller生成成功: {caller_code.get('method_name', '')}")
                
                # 步骤4: 生成控制流SQL变体
                print("步骤4: 生成控制流SQL变体...")
                control_flow_sqls = []
                
                # 根据场景类型生成不同的控制流
                if scenario == "if-else+caller":
                    # if-else+caller: 在Caller中添加if-else逻辑
                    print("  - 生成if-else变体...")
                    if_else_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_if_else_sqls(base_sql, orm_code, scenario),
                        "if-else SQL变体生成"
                    )
                    control_flow_sqls.extend(if_else_sqls)
                    print(f"  ✅ 生成 {len(if_else_sqls)} 个if-else变体")
                    
                    # 生成if-else Caller
                    print("  - 生成if-else Caller...")
                    if_else_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_if_else_caller(orm_code, if_else_sqls, scenario),
                        "if-else Caller生成"
                    )
                    caller_code = if_else_caller
                    print(f"  ✅ if-else Caller生成成功: {if_else_caller.get('method_name', '')}")
                
                elif scenario == "if-else+orm":
                    print("  - 生成if-else+orm变体...")
                    # if-else+orm: 在ORM方法内部包含if-else逻辑
                    if_else_orm_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_if_else_orm_sqls(base_sql, orm_code, scenario),
                        "if-else+orm SQL变体生成"
                    )
                    control_flow_sqls.extend(if_else_orm_sqls)
                    print(f"  ✅ 生成 {len(if_else_orm_sqls)} 个if-else+orm变体")
                    
                    # 生成if-else+orm Caller
                    print("  - 生成if-else+orm Caller...")
                    if_else_orm_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_if_else_orm_caller(orm_code, if_else_orm_sqls, scenario),
                        "if-else+orm Caller生成"
                    )
                    caller_code = if_else_orm_caller
                    print(f"  ✅ if-else+orm Caller生成成功: {if_else_orm_caller.get('method_name', '')}")
                
                elif scenario == "switch":
                    print("  - 生成switch变体...")
                    switch_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_switch_sqls(base_sql, orm_code, scenario),
                        "switch SQL变体生成"
                    )
                    control_flow_sqls.extend(switch_sqls)
                    print(f"  ✅ 生成 {len(switch_sqls)} 个switch变体")
                    
                    # 生成switch Caller
                    print("  - 生成switch Caller...")
                    switch_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_switch_caller(orm_code, switch_sqls, scenario),
                        "switch Caller生成"
                    )
                    caller_code = switch_caller
                    print(f"  ✅ switch Caller生成成功: {switch_caller.get('method_name', '')}")
                
                elif scenario == "dynamic_query":
                    print("  - 生成动态查询变体...")
                    dynamic_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_dynamic_sqls(base_sql, orm_code, scenario),
                        "dynamic SQL变体生成"
                    )
                    control_flow_sqls.extend(dynamic_sqls)
                    print(f"  ✅ 生成 {len(dynamic_sqls)} 个动态查询变体")
                    
                    # 生成动态Caller
                    print("  - 生成动态Caller...")
                    dynamic_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_dynamic_caller(orm_code, dynamic_sqls, scenario),
                        "dynamic Caller生成"
                    )
                    caller_code = dynamic_caller
                    print(f"  ✅ 动态Caller生成成功: {dynamic_caller.get('method_name', '')}")
                
                elif scenario == "complex_control":
                    print("  - 生成复杂控制流变体...")
                    # 生成多层嵌套的控制流
                    complex_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_complex_control_sqls(base_sql, orm_code, scenario),
                        "复杂控制流SQL变体生成"
                    )
                    control_flow_sqls.extend(complex_sqls)
                    print(f"  ✅ 生成 {len(complex_sqls)} 个复杂控制流变体")
                    
                    # 生成复杂控制流Caller
                    print("  - 生成复杂控制流Caller...")
                    complex_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_complex_control_caller(orm_code, complex_sqls, scenario),
                        "复杂控制流Caller生成"
                    )
                    caller_code = complex_caller
                    print(f"  ✅ 复杂控制流Caller生成成功: {complex_caller.get('method_name', '')}")
                
                elif scenario == "if-else+switch_mixed":
                    print("  - 生成if-else+switch混合变体...")
                    # 生成if-else和switch混合的控制流
                    mixed_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_if_else_switch_mixed_sqls(base_sql, orm_code, scenario),
                        "if-else+switch混合SQL变体生成"
                    )
                    control_flow_sqls.extend(mixed_sqls)
                    print(f"  ✅ 生成 {len(mixed_sqls)} 个if-else+switch混合变体")
                    
                    # 生成if-else+switch混合Caller
                    print("  - 生成if-else+switch混合Caller...")
                    mixed_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_if_else_switch_mixed_caller(orm_code, mixed_sqls, scenario),
                        "if-else+switch混合Caller生成"
                    )
                    caller_code = mixed_caller
                    print(f"  ✅ if-else+switch混合Caller生成成功: {mixed_caller.get('method_name', '')}")
                
                elif scenario == "conditional_chain":
                    print("  - 生成条件链式查询变体...")
                    # 生成条件链式查询变体
                    chain_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_conditional_chain_sqls(base_sql, orm_code, scenario),
                        "条件链式查询SQL变体生成"
                    )
                    control_flow_sqls.extend(chain_sqls)
                    print(f"  ✅ 生成 {len(chain_sqls)} 个条件链式查询变体")
                    
                    # 生成条件链式Caller
                    print("  - 生成条件链式Caller...")
                    chain_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_conditional_chain_caller(orm_code, chain_sqls, scenario),
                        "条件链式Caller生成"
                    )
                    caller_code = chain_caller
                    print(f"  ✅ 条件链式Caller生成成功: {chain_caller.get('method_name', '')}")
                
                elif scenario == "multi_branch_transaction":
                    print("  - 生成多分支事务处理变体...")
                    # 生成多分支事务处理变体
                    transaction_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_multi_branch_transaction_sqls(base_sql, orm_code, scenario),
                        "多分支事务处理SQL变体生成"
                    )
                    control_flow_sqls.extend(transaction_sqls)
                    print(f"  ✅ 生成 {len(transaction_sqls)} 个多分支事务处理变体")
                    
                    # 生成多分支事务处理Caller
                    print("  - 生成多分支事务处理Caller...")
                    transaction_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_multi_branch_transaction_caller(orm_code, transaction_sqls, scenario),
                        "多分支事务处理Caller生成"
                    )
                    caller_code = transaction_caller
                    print(f"  ✅ 多分支事务处理Caller生成成功: {transaction_caller.get('method_name', '')}")
                
                elif scenario == "state_machine_branch":
                    print("  - 生成状态机式分支变体...")
                    # 生成状态机式分支变体
                    state_machine_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_state_machine_branch_sqls(base_sql, orm_code, scenario),
                        "状态机式分支SQL变体生成"
                    )
                    control_flow_sqls.extend(state_machine_sqls)
                    print(f"  ✅ 生成 {len(state_machine_sqls)} 个状态机式分支变体")
                    
                    # 生成状态机式分支Caller
                    print("  - 生成状态机式分支Caller...")
                    state_machine_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_state_machine_branch_caller(orm_code, state_machine_sqls, scenario),
                        "状态机式分支Caller生成"
                    )
                    caller_code = state_machine_caller
                    print(f"  ✅ 状态机式分支Caller生成成功: {state_machine_caller.get('method_name', '')}")
                
                elif scenario == "conditional_meta":
                    print("  - 生成条件分支+meta变体...")
                    # 生成条件分支+meta变体
                    meta_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_conditional_meta_sqls(base_sql, orm_code, scenario),
                        "条件分支+meta SQL变体生成"
                    )
                    control_flow_sqls.extend(meta_sqls)
                    print(f"  ✅ 生成 {len(meta_sqls)} 个条件分支+meta变体")
                    
                    # 生成条件分支+meta Caller
                    print("  - 生成条件分支+meta Caller...")
                    meta_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_conditional_meta_caller(orm_code, meta_sqls, scenario),
                        "条件分支+meta Caller生成"
                    )
                    caller_code = meta_caller
                    print(f"  ✅ 条件分支+meta Caller生成成功: {meta_caller.get('method_name', '')}")
                
                elif scenario == "fixed_params":
                    print("  - 生成固定参数变体...")
                    # fixed_params: 生成包含固定参数和动态参数的不同变体
                    fixed_sqls = await self._retry_with_backoff(
                        lambda: self.control_flow_processor.generate_fixed_params_sqls(base_sql, orm_code, scenario),
                        "固定参数SQL变体生成"
                    )
                    control_flow_sqls.extend(fixed_sqls)
                    print(f"  ✅ 生成 {len(fixed_sqls)} 个固定参数变体")
                    
                    # 生成固定参数Caller
                    print("  - 生成固定参数Caller...")
                    fixed_caller = await self._retry_with_backoff(
                        lambda: self.caller_generator.generate_fixed_params_caller(orm_code, fixed_sqls, scenario),
                        "固定参数Caller生成"
                    )
                    caller_code = fixed_caller
                    print(f"  ✅ 固定参数Caller生成成功: {fixed_caller.get('method_name', '')}")
                
                else:
                    print(f"  - 未识别的场景类型: {scenario}")
                    print("  - 无控制流变体")
                
                # 构建完整案例
                case_key = f"{scenario}_{complexity}"
                
                # 构建sql_statement_list
                sql_statement_list = []
                
                # 根据场景类型构建不同的SQL语句列表
                variants = []
                
                if control_flow_sqls:
                    # 使用控制流生成的变体
                    for i, sql_variant in enumerate(control_flow_sqls):
                        variant = {
                            "scenario": sql_variant.get("description", f"分支{i+1}"),
                            "sql": sql_variant.get("query", "")
                        }
                        variants.append(variant)
                else:
                    # 其他场景：基于基础SQL生成不同的参数组合变体
                    base_query = base_sql.get("query", "")
                    if base_query:
                        # 生成几个不同的参数组合变体
                        variants = [
                            {
                                "scenario": "包含所有参数",
                                "sql": base_query
                            },
                            {
                                "scenario": "部分参数组合",
                                "sql": base_query  # 可以根据需要修改
                            },
                            {
                                "scenario": "简化参数",
                                "sql": base_query  # 可以根据需要修改
                            }
                        ]
                
                sql_statement_list.append({
                    "type": "param_dependent",
                    "variants": variants
                })
                
                # 确定SQL类型
                sql_types = []
                # 所有场景都对应param_dependent类型，因为都有动态参数
                sql_types.append("PARAM_DEPENDENT")
                
                # 通过LLM生成code_meta_data（参考正向生成器的方式）
                print("步骤4: 生成code_meta_data...")
                
                # 准备示例元数据
                example_meta = "无样例数据"
                
                # 构建meta提示词
                from config.data_processing.synthetic_data_generator.prompts import PROMPT_META
                
                # 获取随机变量名
                var_names = self.config.get_random_names()
                
                meta_prompt = PROMPT_META.format(
                    orm_block=json.dumps(orm_code, ensure_ascii=False),
                    caller_block=json.dumps(caller_code, ensure_ascii=False),
                    example_meta=example_meta,
                    **var_names
                )
                
                # 调用LLM生成元数据
                meta_response = await self._retry_with_backoff(
                    lambda: self.llm_client.call_async_with_format_validation(
                        self.session,
                        meta_prompt,
                        validator=lambda x: validate_synthetic_data_response(x, 'meta'),
                        max_tokens=self.config.max_tokens,
                        temperature=self.config.temperature,
                        module="reverse_sql_generator"
                    ),
                    "Meta生成"
                )
                
                # 处理响应结果
                if isinstance(meta_response, dict) and 'valid' in meta_response:
                    if meta_response['valid']:
                        meta_json = meta_response.get('content', '')
                    else:
                        raise ValueError(f"Meta格式验证失败: {meta_response.get('error', '未知错误')}")
                else:
                    meta_json = self._clean_json_response(str(meta_response))
                
                try:
                    code_meta_data = json.loads(meta_json)
                except json.JSONDecodeError as e:
                    print(f"解析Meta JSON失败: {e}")
                    print(f"原始响应: {meta_response}")
                    print(f"清理后: {meta_json}")
                    raise
                
                print(f"✅ Meta生成成功: {len(code_meta_data)} 个元数据项")
                
                # 从orm_code和caller中移除package、import和结构体定义，只保留函数定义
                orm_code_clean = orm_code.get("code", "")
                caller_code_clean = caller_code.get("code", "")
                
                # 简单的清理逻辑：移除package、import和结构体定义
                def clean_code(code):
                    if not code:
                        return code
                    
                    lines = code.split('\n')
                    cleaned_lines = []
                    in_struct = False
                    skip_next = False
                    in_import_block = False
                    
                    for line in lines:
                        original_line = line
                        line = line.strip()
                        
                        # 跳过package声明
                        if line.startswith('package '):
                            continue
                            
                        # 处理import块
                        if line.startswith('import '):
                            if '(' in line:
                                in_import_block = True
                            continue
                        elif in_import_block:
                            if line == ')':
                                in_import_block = False
                            continue
                            
                        # 跳过结构体定义
                        if line.startswith('type ') and 'struct' in line:
                            in_struct = True
                            continue
                        elif in_struct and line.startswith('}'):
                            in_struct = False
                            continue
                        elif in_struct:
                            continue
                            
                        # 跳过TableName方法
                        if 'func (' in line and 'TableName()' in line:
                            skip_next = True
                            continue
                        elif skip_next and line.startswith('}'):
                            skip_next = False
                            continue
                        elif skip_next:
                            continue
                            
                        # 跳过import字符串行（如 "gorm.io/gorm"）
                        if line.startswith('"') and line.endswith('"') and ('/' in line or '.' in line):
                            continue
                            
                        # 跳过import结束的右括号
                        if line == ')':
                            continue
                            
                        # 保留其他行（包括空行，但移除前导空格）
                        if not in_struct and not skip_next and not in_import_block:
                            if original_line.strip():  # 非空行
                                cleaned_lines.append(original_line)
                            else:  # 空行
                                cleaned_lines.append('')
                    
                    # 移除开头和结尾的空行
                    while cleaned_lines and not cleaned_lines[0].strip():
                        cleaned_lines.pop(0)
                    while cleaned_lines and not cleaned_lines[-1].strip():
                        cleaned_lines.pop()
                    
                    return '\n'.join(cleaned_lines)
                
                orm_code_clean = clean_code(orm_code_clean)
                caller_code_clean = clean_code(caller_code_clean)
                
                # 构建最终输出格式（和正向生成器一致）
                case_data = {
                    "function_name": orm_code.get("method_name", "GeneratedFunction"),
                    "orm_code": orm_code_clean,
                    "caller": caller_code_clean,
                    "sql_statement_list": sql_statement_list,
                    "sql_types": sql_types,
                    "sql_length_match": True,
                    "code_meta_data": code_meta_data
                }
                
                print(f"✅ 反向案例生成完成: {case_key}")
                return {case_key: case_data}
                
            except Exception as e:
                print(f"❌ 尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    await self._exponential_backoff_delay(attempt)
                else:
                    print(f"❌ 生成案例失败 {scenario} ({complexity}): 已重试 {max_retries} 次")
                    # 记录失败案例
                    self.failed_cases.append({
                        "scenario": scenario,
                        "complexity": complexity,
                        "error": str(e)
                    })
                    import traceback
                    traceback.print_exc()
                    raise
    
    async def retry_failed_cases(self) -> Dict:
        """重新尝试生成失败的案例
        
        Returns:
            重新生成的案例数据
        """
        if not self.failed_cases:
            print("✅ 没有失败的案例需要重试")
            return {}
        
        print(f"🔄 开始重试 {len(self.failed_cases)} 个失败的案例...")
        
        retry_results = {}
        for failed_case in self.failed_cases:
            try:
                print(f"🔄 重试失败案例: {failed_case['scenario']} ({failed_case['complexity']})")
                result = await self.generate_complete_case(
                    failed_case['scenario'], 
                    failed_case['complexity']
                )
                retry_results.update(result)
                print(f"✅ 重试成功: {failed_case['scenario']} ({failed_case['complexity']})")
            except Exception as e:
                print(f"❌ 重试失败: {failed_case['scenario']} ({failed_case['complexity']}): {e}")
        
        # 清空失败案例列表
        self.failed_cases.clear()
        
        return retry_results
    
    async def generate_multiple_cases(self, scenarios_and_complexities: List[Tuple[str, str]], 
                                    parallel: bool = False, max_workers: int = 1) -> Dict:  # 默认改为串行模式
        """批量生成多个案例
        
        Args:
            scenarios_and_complexities: [(场景, 复杂度), ...]
            parallel: 是否启用并行模式
            max_workers: 并行worker数量
            
        Returns:
            所有案例的集合
        """
        print(f"开始批量生成 {len(scenarios_and_complexities)} 个反向案例...")
        print(f"模式: {'并行' if parallel else '串行'}, Worker数量: {max_workers}")
        
        if parallel and len(scenarios_and_complexities) > 1:
            # 并行处理
            import asyncio
            import aiohttp
            from tqdm import tqdm
            
            async def generate_single_case_with_semaphore(semaphore, scenario, complexity):
                """使用信号量控制并发的单个案例生成"""
                async with semaphore:
                    try:
                        # 设置单个案例的超时时间（5分钟）
                        case = await asyncio.wait_for(
                            self.generate_complete_case(scenario, complexity),
                            timeout=300.0
                        )
                        return case
                    except asyncio.TimeoutError:
                        print(f"⏰ 生成案例超时 {scenario} ({complexity})")
                        return None
                    except Exception as e:
                        print(f"❌ 生成案例失败 {scenario} ({complexity}): {e}")
                        # 在并行模式下，如果单个案例失败，返回None而不是抛出异常
                        return None
            
            # 创建信号量控制并发数
            semaphore = asyncio.Semaphore(max_workers)
            
            # 创建所有任务
            tasks = []
            for scenario, complexity in scenarios_and_complexities:
                task = generate_single_case_with_semaphore(semaphore, scenario, complexity)
                tasks.append(task)
            
            # 使用进度条显示并行执行
            cases = {}
            completed_count = 0
            failed_count = 0
            with tqdm(total=len(tasks), desc="生成反向案例") as pbar:
                for completed_task in asyncio.as_completed(tasks):
                    try:
                        result = await completed_task
                        completed_count += 1
                        # 检查result是否为有效结果（非None且非空字典）
                        if result and isinstance(result, dict) and len(result) > 0:
                            cases.update(result)
                            print(f"✅ 完成案例 {completed_count}/{len(tasks)}")
                        else:
                            failed_count += 1
                            print(f"❌ 失败案例 {completed_count}/{len(tasks)} (空结果)")
                    except Exception as e:
                        completed_count += 1
                        failed_count += 1
                        print(f"❌ 异常案例 {completed_count}/{len(tasks)}: {e}")
                    
                    pbar.update(1)
                    pbar.set_postfix({
                        "已完成": len(cases),
                        "失败": failed_count,
                        "成功率": f"{len(cases)/completed_count*100:.1f}%" if completed_count > 0 else "0%"
                    })
        else:
            # 串行处理
            cases = {}
            for i, (scenario, complexity) in enumerate(scenarios_and_complexities, 1):
                try:
                    print(f"🔄 处理案例 {i}/{len(scenarios_and_complexities)}: {scenario} ({complexity})")
                    case = await self.generate_complete_case(scenario, complexity)
                    cases.update(case)
                    print(f"✅ 完成: {scenario}_{complexity}")
                except Exception as e:
                    print(f"❌ 生成案例失败 {scenario} ({complexity}): {e}")
                    continue
        
        print(f"✅ 批量生成完成: {len(cases)} 个案例")
        return cases
    
    async def generate_if_else_case(self, scenario: str) -> Dict:
        """生成if-else结构的案例
        
        Args:
            scenario: 场景类型
            
        Returns:
            if-else案例数据
        """
        print(f"生成if-else案例: {scenario}")
        
        # 1. 生成基础SQL
        base_sql = await self.sql_generator.generate_complete_sql(scenario, "simple")
        
        # 2. 生成ORM代码
        orm_code = await self.orm_mapper.sql_to_orm(base_sql)
        
        # 3. 生成if-else控制流SQL
        if_else_sqls = await self.control_flow_processor.generate_if_else_sqls(
            base_sql, orm_code, scenario
        )
        
        # 4. 生成Caller代码
        caller_code = await self.caller_generator.generate_if_else_caller(
            orm_code, if_else_sqls, scenario
        )
        
        # 5. 整合案例
        case = self.case_integrator.integrate_if_else_case(
            scenario, base_sql, orm_code, caller_code, if_else_sqls
        )
        
        return case
    
    async def generate_switch_case(self, scenario: str) -> Dict:
        """生成switch结构的案例
        
        Args:
            scenario: 场景类型
            
        Returns:
            switch案例数据
        """
        print(f"生成switch案例: {scenario}")
        
        # 1. 生成基础SQL
        base_sql = await self.sql_generator.generate_complete_sql(scenario, "simple")
        
        # 2. 生成ORM代码
        orm_code = await self.orm_mapper.sql_to_orm(base_sql)
        
        # 3. 生成switch控制流SQL
        switch_sqls = await self.control_flow_processor.generate_switch_sqls(
            base_sql, orm_code, scenario
        )
        
        # 4. 生成Caller代码
        caller_code = await self.caller_generator.generate_switch_caller(
            orm_code, switch_sqls, scenario
        )
        
        # 5. 整合案例
        case = self.case_integrator.integrate_switch_case(
            scenario, base_sql, orm_code, caller_code, switch_sqls
        )
        
        return case
    
    async def generate_dynamic_case(self, scenario: str) -> Dict:
        """生成动态条件查询案例
        
        Args:
            scenario: 场景类型
            
        Returns:
            动态查询案例数据
        """
        print(f"生成动态查询案例: {scenario}")
        
        # 1. 生成基础SQL
        base_sql = await self.sql_generator.generate_complete_sql(scenario, "simple")
        
        # 2. 生成ORM代码
        orm_code = await self.orm_mapper.sql_to_orm(base_sql)
        
        # 3. 生成动态条件SQL变体
        dynamic_sqls = await self.control_flow_processor.generate_dynamic_sqls(
            base_sql, orm_code, scenario
        )
        
        # 4. 生成Caller代码
        caller_code = await self.caller_generator.generate_dynamic_caller(
            orm_code, dynamic_sqls, scenario
        )
        
        # 5. 整合案例
        case = self.case_integrator.integrate_dynamic_case(
            scenario, base_sql, orm_code, caller_code, dynamic_sqls
        )
        
        return case
    
    def validate_case(self, case: Dict) -> bool:
        """验证生成的案例
        
        Args:
            case: 案例数据
            
        Returns:
            验证结果
        """
        required_fields = ['scenario', 'base_sql', 'orm_code', 'caller_code']
        
        for field in required_fields:
            if field not in case:
                print(f"❌ 缺少必需字段: {field}")
                return False
        
        # 验证SQL格式
        if not self._validate_sql_format(case['base_sql']):
            print("❌ SQL格式验证失败")
            return False
        
        # 验证ORM代码格式
        if not self._validate_orm_format(case['orm_code']):
            print("❌ ORM代码格式验证失败")
            return False
        
        print("✅ 案例验证通过")
        return True
    
    def _validate_sql_format(self, sql_data: Dict) -> bool:
        """验证SQL格式"""
        required_sql_fields = ['query', 'table', 'fields', 'conditions']
        return all(field in sql_data for field in required_sql_fields)
    
    def _validate_orm_format(self, orm_data: Dict) -> bool:
        """验证ORM数据格式
        
        Args:
            orm_data: ORM数据
            
        Returns:
            格式是否正确
        """
        required_fields = ['method_name', 'entity_name', 'table_name', 'fields', 'conditions']
        return all(field in orm_data for field in required_fields)
    
    async def close(self):
        """关闭所有会话和连接"""
        if self._session:
            await self._session.close()
            self._session = None
            print("  - 已关闭主会话")
        
        # 关闭各个组件的会话
        if hasattr(self.sql_generator, 'close'):
            await self.sql_generator.close()
        if hasattr(self.orm_mapper, 'close'):
            await self.orm_mapper.close()
        if hasattr(self.caller_generator, 'close'):
            await self.caller_generator.close()
        if hasattr(self.control_flow_processor, 'close'):
            await self.control_flow_processor.close() 