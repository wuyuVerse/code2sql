"""
控制流验证器

用于检测包含switch、if等控制流语句的ORM代码，验证生成的SQL变体数量是否合理
"""

import json
import logging
import asyncio
import aiohttp
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from tqdm.asyncio import tqdm_asyncio

logger = logging.getLogger(__name__)


class ControlFlowValidator:
    """控制流验证器
    
    用于检测包含switch、if等控制流语句的ORM代码，验证生成的SQL变体数量是否合理
    """
    
    def __init__(self, output_dir: str, llm_server: str = "v3"):
        """
        初始化控制流验证器
        
        Args:
            output_dir: 输出目录
            llm_server: LLM服务器名称
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm_server = llm_server
        
        # 控制流关键词
        self.control_flow_keywords = [
            'switch', 'if', 'else if', 'else', 'case', 'default'
        ]
        
        logger.info(f"控制流验证器初始化完成，输出目录: {self.output_dir}")
    
    def detect_control_flow_records(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        检测包含控制流语句的记录
        
        Args:
            data: 数据记录列表
            
        Returns:
            包含控制流语句的记录列表
        """
        control_flow_records = []
        
        for record in data:
            orm_code = record.get('orm_code', '')
            if self._contains_control_flow(orm_code):
                control_flow_records.append(record)
        
        logger.info(f"检测到 {len(control_flow_records)} 条包含控制流语句的记录")
        return control_flow_records
    
    def _contains_control_flow(self, orm_code: str) -> bool:
        """
        检查ORM代码是否包含控制流语句
        
        Args:
            orm_code: ORM代码
            
        Returns:
            是否包含控制流语句
        """
        if not orm_code:
            return False
        
        # 转换为小写进行匹配
        code_lower = orm_code.lower()
        
        # 检查是否包含控制流关键词
        for keyword in self.control_flow_keywords:
            if keyword in code_lower:
                return True
        
        return False
    
    def _format_code_meta_data(self, code_meta_data: List[Dict[str, Any]]) -> str:
        """
        格式化代码元数据
        
        Args:
            code_meta_data: 代码元数据列表
            
        Returns:
            格式化后的代码元数据字符串
        """
        if not code_meta_data:
            return "无代码元数据"
        
        formatted_parts = []
        for i, meta in enumerate(code_meta_data, 1):
            if isinstance(meta, dict):
                parts = []
                if 'code_file' in meta:
                    parts.append(f"文件: {meta['code_file']}")
                if 'code_start_line' in meta and 'code_end_line' in meta:
                    parts.append(f"行号: {meta['code_start_line']}-{meta['code_end_line']}")
                if 'code_key' in meta:
                    parts.append(f"键: {meta['code_key']}")
                if 'code_value' in meta:
                    parts.append(f"值: {meta['code_value']}")
                if 'code_label' in meta and meta['code_label']:
                    parts.append(f"标签: {meta['code_label']}")
                if 'code_type' in meta:
                    parts.append(f"类型: {meta['code_type']}")
                
                formatted_parts.append(f"{i}. {' | '.join(parts)}")
            else:
                formatted_parts.append(f"{i}. {str(meta)}")
        
        return "\n".join(formatted_parts)
    
    def _extract_sql_variants(self, record: Dict[str, Any]) -> str:
        """
        提取记录中的SQL变体信息
        
        Args:
            record: 数据记录
            
        Returns:
            SQL变体的字符串表示
        """
        sql_list = record.get('sql_statement_list', [])
        
        if isinstance(sql_list, str):
            return sql_list
        
        elif isinstance(sql_list, list):
            variants_info = []
            for i, variant in enumerate(sql_list):
                if isinstance(variant, dict):
                    if variant.get('type') == 'param_dependent':
                        variants = variant.get('variants', [])
                        for j, v in enumerate(variants):
                            scenario = v.get('scenario', f'变体{j+1}')
                            sql = v.get('sql', '')
                            variants_info.append(f"  {j+1}. {scenario}: {sql}")
                    else:
                        variants_info.append(f"  {i+1}. {variant}")
                else:
                    variants_info.append(f"  {i+1}. {variant}")
            
            return "\n".join(variants_info) if variants_info else str(sql_list)
        
        else:
            return str(sql_list)
    
    async def validate_control_flow_records(self, records: List[Dict[str, Any]], 
                                          max_concurrent: int = 50) -> Dict[str, Any]:
        """
        验证包含控制流语句的记录
        
        Args:
            records: 包含控制流语句的记录列表
            max_concurrent: 最大并发数
            
        Returns:
            验证结果
        """
        if not records:
            logger.info("没有需要验证的控制流记录")
            return {
                'total_records': 0,
                'validated_records': 0,
                'correct_records': 0,
                'incorrect_records': 0,
                'error_records': 0,
                'validation_details': []
            }
        
        logger.info(f"开始验证 {len(records)} 条控制流记录")
        
        # 动态导入LLM客户端
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
        
        try:
            from utils.llm_client import LLMClient
            from config.data_clean.control_flow_validation_prompt import get_control_flow_validation_prompt
            llm_client = LLMClient(self.llm_server)
        except ImportError as e:
            logger.error(f"无法导入LLM相关模块: {e}")
            raise ValueError("LLM模块不可用，无法执行控制流验证")
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def validate_single_record(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
            """验证单条记录的控制流"""
            async with semaphore:
                try:
                    orm_code = record.get('orm_code', '')
                    caller = record.get('caller', '')
                    code_meta_data = record.get('code_meta_data', [])
                    sql_variants = self._extract_sql_variants(record)
                    
                    # 格式化代码元数据
                    formatted_meta_data = self._format_code_meta_data(code_meta_data)
                    
                    # 生成提示词
                    prompt = get_control_flow_validation_prompt(orm_code, caller, formatted_meta_data, sql_variants)
                    
                    # 调用LLM
                    response = await llm_client.call_async(
                        session, 
                        prompt, 
                        max_tokens=1000, 
                        temperature=0.0,
                        max_retries=5
                    )
                    
                    # 解析响应
                    validation_result = self._parse_llm_response(response, record)
                    
                    return {
                        'record': record,
                        'validation_result': validation_result,
                        'llm_response': response,
                        'status': 'success'
                    }
                    
                except Exception as e:
                    logger.warning(f"验证记录失败: {e}")
                    return {
                        'record': record,
                        'validation_result': {
                            'is_correct': True,  # 默认认为正确，避免误判
                            'reason': f'验证失败: {str(e)}',
                            'error': True
                        },
                        'llm_response': '',
                        'status': 'error',
                        'error': str(e)
                    }
        
        # 执行并发验证
        validated_records = []
        with tqdm_asyncio(total=len(records), desc="验证控制流记录") as pbar:
            async with aiohttp.ClientSession() as session:
                tasks = []
                for record in records:
                    task = asyncio.ensure_future(validate_single_record(session, record))
                    
                    def update_progress(fut, pbar=pbar):
                        pbar.update(1)
                    
                    task.add_done_callback(update_progress)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        correct_count = 0
        incorrect_count = 0
        error_count = 0
        regenerated_count = 0
        
        # 收集需要重新生成的记录
        records_to_regenerate = []
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
                logger.warning(f"验证过程异常: {result}")
                continue
            
            validated_records.append(result)
            validation_result = result.get('validation_result', {})
            
            if validation_result.get('error'):
                error_count += 1
            elif validation_result.get('is_correct', True):
                correct_count += 1
            else:
                incorrect_count += 1
                # 收集需要重新生成的记录
                records_to_regenerate.append((result, validation_result))
        
        # 重新生成SQL（带进度条）
        if records_to_regenerate:
            logger.info(f"开始重新生成 {len(records_to_regenerate)} 条记录的SQL...")
            with tqdm_asyncio(total=len(records_to_regenerate), desc="重新生成SQL") as pbar:
                async with aiohttp.ClientSession() as regen_session:
                    for result, validation_result in records_to_regenerate:
                        regenerated_record = await self._regenerate_sql_for_incorrect_record(
                            regen_session, result['record'], validation_result
                        )
                        if regenerated_record:
                            result['regenerated_sql'] = regenerated_record
                            regenerated_count += 1
                        pbar.update(1)
        
        # 保存验证结果
        validation_file = self.output_dir / "control_flow_validation_results.json"
        with open(validation_file, 'w', encoding='utf-8') as f:
            json.dump({
                'validation_timestamp': datetime.now().isoformat(),
                'total_records': len(records),
                'validated_records': len(validated_records),
                'correct_records': correct_count,
                'incorrect_records': incorrect_count,
                'error_records': error_count,
                'validation_details': validated_records
            }, f, ensure_ascii=False, indent=2)
        
        # 生成问题记录报告
        problematic_records = []
        for result in validated_records:
            validation_result = result.get('validation_result', {})
            if not validation_result.get('is_correct', True) and not validation_result.get('error'):
                problematic_records.append(result)
        
        if problematic_records:
            problematic_file = self.output_dir / "problematic_control_flow_records.json"
            with open(problematic_file, 'w', encoding='utf-8') as f:
                json.dump(problematic_records, f, ensure_ascii=False, indent=2)
            logger.info(f"发现 {len(problematic_records)} 条有问题的控制流记录，已保存到: {problematic_file}")
        
        result = {
            'total_records': len(records),
            'validated_records': len(validated_records),
            'correct_records': correct_count,
            'incorrect_records': incorrect_count,
            'error_records': error_count,
            'regenerated_records': regenerated_count,
            'validation_details': validated_records,
            'problematic_records': problematic_records,
            'validation_file': str(validation_file),
            'problematic_file': str(problematic_file) if problematic_records else None
        }
        
        logger.info(f"控制流验证完成 - 正确: {correct_count}, 错误: {incorrect_count}, 异常: {error_count}, 重新生成: {regenerated_count}")
        return result
    
    async def _regenerate_sql_for_incorrect_record(self, session: aiohttp.ClientSession, 
                                                  record: Dict[str, Any], 
                                                  validation_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        为验证失败的记录重新生成SQL
        
        Args:
            session: aiohttp会话
            record: 原始记录
            validation_result: 验证结果
            
        Returns:
            重新生成的SQL记录，如果失败则返回None
        """
        try:
            # 动态导入SQL重新生成提示词
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
            
            try:
                from config.data_clean.control_flow_validation_prompt import get_control_flow_sql_regeneration_prompt
                from utils.llm_client import LLMClient
            except ImportError as e:
                logger.warning(f"无法导入SQL重新生成提示词: {e}")
                return None
            
            # 准备重新生成所需的信息
            orm_code = record.get('orm_code', '')
            caller = record.get('caller', '')
            code_meta_data = record.get('code_meta_data', [])
            formatted_meta_data = self._format_code_meta_data(code_meta_data)
            
            # 格式化验证结果
            validation_summary = self._format_validation_result(validation_result)
            
            # 生成重新生成提示词
            prompt = get_control_flow_sql_regeneration_prompt(
                orm_code=orm_code,
                caller=caller,
                code_meta_data=formatted_meta_data,
                validation_result=validation_summary
            )
            
            # 调用LLM重新生成SQL
            llm_client = LLMClient(self.llm_server)
            response = await llm_client.call_async(
                session,
                prompt,
                max_tokens=1500,
                temperature=0.0,
                max_retries=3
            )
            
            if response:
                # 解析重新生成的SQL
                regenerated_sql = self._parse_regenerated_sql(response)
                if regenerated_sql:
                    return {
                        'original_sql': record.get('sql_statement_list'),
                        'regenerated_sql': regenerated_sql,
                        'regeneration_reason': validation_result.get('reason', ''),
                        'regeneration_timestamp': datetime.now().isoformat()
                    }
            
            return None
            
        except Exception as e:
            logger.warning(f"重新生成SQL失败: {e}")
            return None
    
    def _format_validation_result(self, validation_result: Dict[str, Any]) -> str:
        """
        格式化验证结果用于重新生成提示词
        
        Args:
            validation_result: 验证结果
            
        Returns:
            格式化后的验证结果字符串
        """
        parts = []
        
        # 添加最终判断
        is_correct = validation_result.get('is_correct', True)
        reason = validation_result.get('reason', '')
        parts.append(f"验证结果: {'正确' if is_correct else '错误'}")
        if reason:
            parts.append(f"原因: {reason}")
        
        # 添加期望和实际数量
        expected_count = validation_result.get('expected_count')
        actual_count = validation_result.get('actual_count')
        if expected_count is not None and actual_count is not None:
            parts.append(f"期望SQL变体数量: {expected_count}")
            parts.append(f"实际SQL变体数量: {actual_count}")
        
        # 添加问题和建议
        issues = validation_result.get('issues', [])
        if issues:
            parts.append("发现的问题:")
            for issue in issues:
                parts.append(f"  - {issue}")
        
        recommendations = validation_result.get('recommendations', [])
        if recommendations:
            parts.append("改进建议:")
            for rec in recommendations:
                parts.append(f"  - {rec}")
        
        # 添加控制流分析
        control_flow_analysis = validation_result.get('control_flow_analysis', {})
        if control_flow_analysis:
            parts.append("控制流分析:")
            
            switch_statements = control_flow_analysis.get('switch_statements', [])
            if switch_statements:
                parts.append("  Switch语句:")
                for switch in switch_statements:
                    parts.append(f"    变量: {switch.get('variable', 'N/A')}")
                    parts.append(f"    行号: {switch.get('line_range', 'N/A')}")
                    branches = switch.get('branches', [])
                    for branch in branches:
                        condition = branch.get('condition', 'N/A')
                        logic = branch.get('logic', 'N/A')
                        should_have_sql = branch.get('should_have_sql', True)
                        parts.append(f"      分支: {condition} -> {logic} (应有SQL: {should_have_sql})")
            
            if_statements = control_flow_analysis.get('if_statements', [])
            if if_statements:
                parts.append("  If语句:")
                for if_stmt in if_statements:
                    condition = if_stmt.get('condition', 'N/A')
                    logic = if_stmt.get('logic', 'N/A')
                    should_have_sql = if_stmt.get('should_have_sql', True)
                    parts.append(f"    条件: {condition} -> {logic} (应有SQL: {should_have_sql})")
        
        return "\n".join(parts)
    
    def _parse_regenerated_sql(self, response: str) -> Optional[Any]:
        """
        解析重新生成的SQL响应
        
        Args:
            response: LLM响应
            
        Returns:
            解析后的SQL，如果失败则返回None
        """
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'```json\s*(\[.*?\])\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response
            
            # 解析JSON
            result = json.loads(json_str)
            return result
            
        except Exception as e:
            logger.warning(f"解析重新生成的SQL失败: {e}")
            return None
    
    def _parse_llm_response(self, response: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析LLM响应
        
        Args:
            response: LLM响应内容
            record: 原始记录
            
        Returns:
            解析后的验证结果
        """
        if not response:
            return {
                'is_correct': True,
                'reason': 'LLM无响应，默认认为正确',
                'error': True
            }
        
        try:
            # 尝试提取JSON
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response
            
            # 解析JSON
            result = json.loads(json_str)
            
            # 提取关键信息
            final_judgment = result.get('final_judgment', {})
            sql_analysis = result.get('sql_variants_analysis', {})
            
            return {
                'is_correct': final_judgment.get('is_correct', True),
                'reason': final_judgment.get('reason', ''),
                'expected_count': sql_analysis.get('expected_count'),
                'actual_count': sql_analysis.get('actual_count'),
                'issues': sql_analysis.get('issues', []),
                'recommendations': sql_analysis.get('recommendations', []),
                'control_flow_analysis': result.get('control_flow_analysis', {}),
                'raw_response': response
            }
            
        except Exception as e:
            logger.warning(f"解析LLM响应失败: {e}")
            return {
                'is_correct': True,
                'reason': f'解析失败: {str(e)}',
                'error': True,
                'raw_response': response
            }
    
    async def validate_dataset(self, data: List[Dict[str, Any]], 
                             max_concurrent: int = 50) -> Dict[str, Any]:
        """
        验证整个数据集的控制流
        
        Args:
            data: 数据集
            max_concurrent: 最大并发数
            
        Returns:
            验证结果
        """
        logger.info(f"开始验证数据集的控制流，共 {len(data)} 条记录")
        
        # 检测包含控制流的记录
        control_flow_records = self.detect_control_flow_records(data)
        
        if not control_flow_records:
            logger.info("数据集中没有发现包含控制流语句的记录")
            return {
                'total_records': len(data),
                'control_flow_records': 0,
                'validation_result': None
            }
        
        # 验证控制流记录
        validation_result = await self.validate_control_flow_records(
            control_flow_records, 
            max_concurrent
        )
        
        # 添加总体统计
        validation_result['total_records'] = len(data)
        validation_result['control_flow_records'] = len(control_flow_records)
        validation_result['control_flow_rate'] = len(control_flow_records) / len(data) * 100 if data else 0
        
        logger.info(f"数据集控制流验证完成:")
        logger.info(f"  - 总记录数: {len(data)}")
        logger.info(f"  - 控制流记录: {len(control_flow_records)} ({validation_result['control_flow_rate']:.2f}%)")
        logger.info(f"  - 验证正确: {validation_result['correct_records']}")
        logger.info(f"  - 验证错误: {validation_result['incorrect_records']}")
        logger.info(f"  - 验证异常: {validation_result['error_records']}")
        
        return validation_result 