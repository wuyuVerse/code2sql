"""
Workflow管理器

管理数据处理的整个工作流，包括数据读取、清洗、验证等步骤
"""

import json
import logging
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from tqdm.asyncio import tqdm_asyncio
import re
import traceback
import random
import tempfile
import shutil

# 尝试相对导入，如果失败则直接导入
try:
    from ..data_reader import DataReader
    from ..cleaning.sql_cleaner import SQLCleaner
except ImportError:
    from data_reader import DataReader
    from cleaning.sql_cleaner import SQLCleaner

logger = logging.getLogger(__name__)

try:
    from config.data_clean.keyword_processing_prompt import KEYWORD_PROCESSING_PROMPT
except ImportError:
    # Fallback if the new prompt file is not found, to maintain compatibility
    KEYWORD_PROCESSING_PROMPT = "Legacy or default prompt here, if any."
    logger.warning("Could not import KEYWORD_PROCESSING_PROMPT, using fallback.")


class WorkflowManager:
    """工作流管理器
    
    负责协调数据处理的各个步骤，记录处理过程和结果
    """
    
    def __init__(self, base_output_dir: str = "workflow_output"):
        """
        初始化工作流管理器
        
        Args:
            base_output_dir: 工作流输出基目录
        """
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(exist_ok=True)
        
        # 创建当前workflow实例的目录
        self.workflow_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.workflow_dir = self.base_output_dir / f"workflow_{self.workflow_timestamp}"
        self.workflow_dir.mkdir(exist_ok=True)
        
        # 工作流步骤记录
        self.workflow_steps = []
        self.current_data = None
        self.extracted_data = None  # 提取的关键词数据
        
        logger.info(f"工作流管理器初始化完成，输出目录: {self.workflow_dir}")

    def load_raw_dataset(self, data_dir: str) -> Dict[str, Any]:
        """
        从原始数据集加载所有数据
        
        Args:
            data_dir: 原始数据目录
            
        Returns:
            加载结果信息
        """
        logger.info(f"开始从原始数据集加载所有数据: {data_dir}")
        
        # 创建数据读取器并读取所有数据
        reader = DataReader(data_dir)
        reader.read_all_files()
        
        # 转换为dict格式的数据
        self.current_data = []
        for record in reader.records:
            record_dict = {
                'function_name': record.function_name,
                'orm_code': record.orm_code,
                'caller': record.caller,
                'sql_statement_list': record.sql_statement_list,
                'sql_types': record.sql_types,
                'code_meta_data': [
                    {
                        'code_file': meta.code_file,
                        'code_start_line': meta.code_start_line,
                        'code_end_line': meta.code_end_line,
                        'code_key': meta.code_key,
                        'code_value': meta.code_value,
                        'code_label': meta.code_label,
                        'code_type': meta.code_type,
                        'code_version': meta.code_version
                    } for meta in record.code_meta_data
                ],
                'sql_pattern_cnt': record.sql_pattern_cnt,
                'source_file': record.source_file
            }
            self.current_data.append(record_dict)
        
        step_info = {
            'step_name': 'load_raw_dataset',
            'step_type': 'data_loading',
            'timestamp': datetime.now().isoformat(),
            'input_source': str(data_dir),
            'total_records_loaded': len(self.current_data),
            'data_size_mb': sum(len(str(record)) for record in self.current_data) / (1024 * 1024)
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"原始数据集加载完成，共 {len(self.current_data):,} 条记录")
        return step_info
    
    def run_sql_cleaning(self, step_name: str = "sql_cleaning_step1") -> Dict[str, Any]:
        """
        运行SQL清洗步骤（清洗全体数据）
        
        Args:
            step_name: 步骤名称
            
        Returns:
            清洗结果信息
        """
        if self.current_data is None:
            raise ValueError("请先加载数据")
        
        logger.info(f"开始对全体数据集进行SQL清洗: {step_name}")
        
        # 创建SQL清洗器
        cleaner_output_dir = self.workflow_dir / "cleaning_steps"
        sql_cleaner = SQLCleaner(str(cleaner_output_dir))
        
        # 执行清洗
        cleaning_result = sql_cleaner.clean_dataset(self.current_data, step_name)
        
        # 优先加载带有冗余标记的数据（如果ORM分析成功）
        marked_data_file = Path(cleaning_result['output_directory']) / "cleaned_records_with_redundant_marks.json"
        cleaned_data_file = Path(cleaning_result['output_directory']) / "cleaned_records.json"
        
        if marked_data_file.exists():
            logger.info("检测到ORM指纹分析结果，加载带冗余标记的数据...")
            with open(marked_data_file, 'r', encoding='utf-8') as f:
                self.current_data = json.load(f)
            preferred_data_file = str(marked_data_file)
        else:
            logger.info("未检测到ORM指纹分析结果，加载清洗后的数据...")
            with open(cleaned_data_file, 'r', encoding='utf-8') as f:
                self.current_data = json.load(f)
            preferred_data_file = str(cleaned_data_file)
        
        # 记录工作流步骤，包含ORM分析信息
        input_count = cleaning_result['input_records_count']
        modified_count = cleaning_result['records_modified']
        step_info = {
            'step_name': step_name,
            'step_type': 'sql_cleaning',
            'timestamp': datetime.now().isoformat(),
            'input_records': input_count,
            'output_records': cleaning_result['output_records_count'],
            'records_modified': modified_count,
            'modification_rate': (modified_count / input_count * 100) if input_count > 0 else 0.0,
            'invalid_sql_removed': cleaning_result['invalid_sql_removed'],
            'valid_sql_retained': cleaning_result['valid_sql_retained'],
            'param_dependent_sql_retained': cleaning_result['param_dependent_sql_retained'],
            'empty_sql_lists_found': cleaning_result.get('empty_sql_lists_found', 0),
            'lists_emptied_after_cleaning': cleaning_result.get('lists_emptied_after_cleaning', 0),
            'output_directory': cleaning_result['output_directory'],
            'preferred_data_file': preferred_data_file
        }
        
        # 添加ORM分析结果信息（如果可用）
        if 'orm_analysis_summary' in cleaning_result and cleaning_result['orm_analysis_summary']:
            orm_summary = cleaning_result['orm_analysis_summary']
            detailed_analysis = orm_summary.get('detailed_analysis', {})
            
            step_info.update({
                'orm_analysis_available': True,
                'total_orm_codes': orm_summary.get('total_orm_codes', 0),
                'orm_with_redundant_candidates': detailed_analysis.get('orm_with_redundant_candidates', 0),
                'orm_with_missing_candidates': detailed_analysis.get('orm_with_missing_candidates', 0),
                'orm_with_new_fp_candidates': detailed_analysis.get('orm_with_new_fp_candidates', 0),
                'total_sql_records': orm_summary.get('total_sql_records', 0),
                'orm_analysis_reports': cleaning_result.get('orm_analysis_reports')
            })
            logger.info(f"ORM指纹分析已完成:")
            logger.info(f"  - 分析了 {orm_summary.get('total_orm_codes', 0)} 个ORM代码")
            logger.info(f"  - 发现 {detailed_analysis.get('orm_with_redundant_candidates', 0)} 个ORM代码有冗余候选项")
            logger.info(f"  - 发现 {detailed_analysis.get('orm_with_missing_candidates', 0)} 个ORM代码有缺漏候选项")
            logger.info(f"  - 发现 {detailed_analysis.get('orm_with_new_fp_candidates', 0)} 个ORM代码有新增指纹候选项")
        else:
            step_info['orm_analysis_available'] = False
            logger.info("ORM指纹分析未执行或执行失败")
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"全体数据集SQL清洗完成 - 移除了 {cleaning_result['invalid_sql_removed']:,} 个无效SQL，修改了 {cleaning_result['records_modified']:,} 条记录")
        return cleaning_result
    
    async def tag_lack_information_data(self, step_name: str = "sql_completeness_check_step") -> Dict[str, Any]:
        """
        使用LLM检查数据的SQL完整性并标记缺少信息的数据
        
        Args:
            step_name: 步骤名称
            
        Returns:
            标记结果信息
        """
        if self.current_data is None:
            raise ValueError("请先加载并清洗数据")
        
        logger.info(f"开始使用LLM检查SQL完整性并标记数据: {step_name}")
        
        # 筛选出需要处理的记录和直接跳过的记录
        records_to_process = []
        excluded_records = []
        if self.current_data:
            for record in self.current_data:
                sql_list = record.get('sql_statement_list', [])
                # 检查是否为 <NO SQL GENERATE>（可能是字符串或包含该字符串的列表）
                is_no_sql = False
                if isinstance(sql_list, str):
                    is_no_sql = sql_list == '<NO SQL GENERATE>'
                elif isinstance(sql_list, list):
                    is_no_sql = len(sql_list) == 1 and sql_list[0] == '<NO SQL GENERATE>'
                
                if is_no_sql:
                    excluded_records.append(record)
                else:
                    records_to_process.append(record)
        
        logger.info(f"从 {len(self.current_data):,} 条记录中筛选出 {len(records_to_process):,} 条记录进行完整性检查，排除了 {len(excluded_records):,} 条 '<NO SQL GENERATE>' 记录。")

        # 如果没有需要处理的记录，则直接跳过
        if not records_to_process:
            logger.info("没有需要处理的记录，跳过LLM完整性检查步骤。")
            step_info = {
                'step_name': step_name,
                'step_type': 'sql_completeness_check',
                'timestamp': datetime.now().isoformat(),
                'input_records': len(self.current_data),
                'records_to_check': 0,
                'excluded_no_sql_records': len(excluded_records),
                'lack_info_records': 0,
                'complete_records': 0,
                'error_records': 0,
                'lack_info_rate': 0.0,
                'concurrent_requests': 0,
                'output_file': None
            }
            self.workflow_steps.append(step_info)
            return step_info
        
        # 动态导入LLM相关模块
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
        
        try:
            from utils.llm_client import LLMClient
            from config.data_clean.sql_completeness_check_prompt import get_sql_completeness_check_prompt  # type: ignore
        except ImportError as e:
            logger.error(f"无法导入LLM相关模块: {e}")
            raise ValueError("LLM模块不可用，无法执行SQL完整性检查")
        
        # 创建LLM客户端
        llm_client = LLMClient("v3")
        
        # 并发处理的函数
        async def check_single_record(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
            """检查单条记录的SQL完整性"""
            try:
                # 准备检查材料
                caller_raw = record.get('caller')
                caller = str(caller_raw).strip() if caller_raw else '<EMPTY>'
                orm_code = record.get('orm_code', '')
                sql_statements = str(record.get('sql_statement_list', []))
                
                # 处理元数据
                code_meta_data = record.get('code_meta_data', [])
                if isinstance(code_meta_data, list) and code_meta_data:
                    code_meta = str(code_meta_data[0])
                else:
                    code_meta = '<EMPTY>' if (isinstance(code_meta_data, list) and not code_meta_data) else str(code_meta_data)
                
                # 生成提示词
                prompt = get_sql_completeness_check_prompt(
                    caller=caller,
                    code_meta=code_meta,
                    orm_code=orm_code,
                    sql_statements=sql_statements
                )
                
                # 调用LLM
                response = await llm_client.call_async(session, prompt, max_tokens=100, temperature=0.0, max_retries=1000)
                
                # 处理响应
                is_complete = True
                reason = ""
                
                if response:
                    response_lower = response.strip().lower()
                    if response_lower.startswith('否'):
                        is_complete = False
                        # 提取原因
                        if '，' in response:
                            reason = response.split('，', 1)[1].strip()
                        elif ',' in response:
                            reason = response.split(',', 1)[1].strip()
                        else:
                            reason = response.replace('否', '').strip()
                
                # 创建新记录
                new_record = record.copy()
                
                # 添加检查结果
                if not is_complete:
                    new_record['completeness_check'] = {
                        'is_complete': False,
                        'reason': reason,
                        'tag': '<LACK INFORMATION>',
                        'checked_at': datetime.now().isoformat()
                    }
                    new_record['sql_statement_list'] = "<LACK INFORMATION>"
                else:
                    new_record['completeness_check'] = {
                        'is_complete': True,
                        'reason': '',
                        'tag': '',
                        'checked_at': datetime.now().isoformat()
                    }
                
                return new_record
                
            except Exception as e:
                logger.warning(f"检查记录失败: {e}")
                # 出错时保留原记录并标记为未检查
                error_record = record.copy()
                error_record['completeness_check'] = {
                    'is_complete': True,  # 默认认为完整，避免错误标记
                    'reason': f'检查失败: {str(e)}',
                    'tag': '',
                    'checked_at': datetime.now().isoformat(),
                    'check_error': True
                }
                return error_record
        
        # 动态获取并发数
        from config.data_clean.workflow_config import get_workflow_config
        workflow_config = get_workflow_config()
        concurrency = workflow_config.get_concurrency('sql_completeness_check')
        semaphore = asyncio.Semaphore(concurrency)
        
        async def process_with_semaphore(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await check_single_record(session, record)
        
        # 执行并发处理
        logger.info(f"使用 {semaphore._value} 并发请求处理 {len(records_to_process)} 条记录...")
        
        processed_records = []
        with tqdm_asyncio(total=len(records_to_process), desc=f"检查SQL完整性 ({step_name})") as pbar:
            async with aiohttp.ClientSession() as session:
                tasks = []
                for record in records_to_process:
                    task = asyncio.ensure_future(process_with_semaphore(session, record))
                    
                    def update_progress(fut, pbar=pbar):
                        pbar.update(1)
                    
                    task.add_done_callback(update_progress)
                    tasks.append(task)
                
                processed_records = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        tagged_data = []
        error_count = 0
        lack_info_count = 0
        
        for i, result in enumerate(processed_records):
            if isinstance(result, Exception):
                logger.warning(f"处理第{i+1}条记录时出错: {result}")
                error_record = records_to_process[i].copy()
                error_record['completeness_check'] = {
                    'is_complete': True,
                    'reason': f'处理异常: {str(result)}',
                    'tag': '',
                    'checked_at': datetime.now().isoformat(),
                    'process_error': True
                }
                tagged_data.append(error_record)
                error_count += 1
            else:
                tagged_data.append(result)
                # 检查completeness_check字段，确保result是字典类型
                if isinstance(result, dict) and not result.get('completeness_check', {}).get('is_complete', True):
                    lack_info_count += 1
        
        # 更新当前数据
        self.current_data = excluded_records + tagged_data
        
        # 保存标记后的数据
        tagging_output_dir = self.workflow_dir / "sql_completeness_check"
        tagging_output_dir.mkdir(exist_ok=True)
        
        tagged_data_file = tagging_output_dir / f"{step_name}.json"
        with open(tagged_data_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_data, f, ensure_ascii=False, indent=2)
        
        # 记录工作流步骤
        step_info = {
            'step_name': step_name,
            'step_type': 'sql_completeness_check',
            'timestamp': datetime.now().isoformat(),
            'input_records': len(self.current_data),
            'records_to_check': len(records_to_process),
            'excluded_no_sql_records': len(excluded_records),
            'lack_info_records': lack_info_count,
            'complete_records': len(records_to_process) - lack_info_count - error_count,
            'error_records': error_count,
            'lack_info_rate': lack_info_count / len(records_to_process) * 100 if records_to_process else 0.0,
            'concurrent_requests': concurrency,
            'output_file': str(tagged_data_file)
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"SQL完整性检查完成 - 在 {len(records_to_process):,} 条待查记录中，标记了 {lack_info_count:,} 条缺少信息的记录，{error_count:,} 条处理错误。")
        return step_info

    async def check_sql_correctness(self, step_name: str = "sql_correctness_check_step") -> Dict[str, Any]:
        """
        使用LLM检查数据的SQL正确性并进行标记
        
        Args:
            step_name: 步骤名称
            
        Returns:
            标记结果信息
        """
        if self.current_data is None:
            raise ValueError("请先加载并处理数据")

        logger.info(f"开始使用LLM检查SQL正确性并标记数据: {step_name}")

        # 筛选出需要进行正确性检查的记录
        records_to_process = []
        excluded_records = []
        for record in self.current_data:
            sql_list = record.get('sql_statement_list', [])
            # 检查是否为 <NO SQL GENERATE>（可能是字符串或包含该字符串的列表）
            is_no_sql = False
            if isinstance(sql_list, str):
                is_no_sql = sql_list == '<NO SQL GENERATE>'
            elif isinstance(sql_list, list):
                is_no_sql = len(sql_list) == 1 and sql_list[0] == '<NO SQL GENERATE>'
            
            has_lack_info_tag = record.get('completeness_check', {}).get('tag') == '<LACK INFORMATION>'
            
            if is_no_sql or has_lack_info_tag:
                excluded_records.append(record)
            else:
                records_to_process.append(record)

        logger.info(f"从 {len(self.current_data):,} 条记录中筛选出 {len(records_to_process):,} 条记录进行正确性检查，排除了 {len(excluded_records):,} 条不适用记录。")

        if not records_to_process:
            logger.info("没有需要进行正确性检查的记录，跳过此步骤。")
            step_info = {
                'step_name': step_name,
                'step_type': 'sql_correctness_check',
                'timestamp': datetime.now().isoformat(),
                'input_records': len(self.current_data),
                'records_to_check': 0,
                'excluded_records': len(excluded_records),
                'correct_records': 0,
                'incorrect_records': 0,
                'error_records': 0,
                'incorrect_rate': 0.0,
                'output_file': None
            }
            self.workflow_steps.append(step_info)
            return step_info

        # 动态导入LLM相关模块
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
        
        try:
            from utils.llm_client import LLMClient
            from config.data_clean.sql_completeness_check_prompt import get_sql_correctness_check_prompt, get_sql_correctness_check_prompt
        except ImportError as e:
            logger.error(f"无法导入LLM相关模块: {e}")
            raise ValueError("LLM模块不可用，无法执行SQL正确性检查")
        
        llm_client = LLMClient("v3")

        async def check_single_record(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
            """检查单条记录的SQL正确性"""
            try:
                # 安全地处理元数据
                code_meta_data = record.get('code_meta_data', [])
                if isinstance(code_meta_data, list) and code_meta_data:
                    code_meta = str(code_meta_data[0])
                else:
                    # 如果是空列表，传递空字符串；否则，转换整个对象
                    code_meta = '' if isinstance(code_meta_data, list) else str(code_meta_data)

                caller_raw = record.get('caller')
                caller = str(caller_raw).strip() if caller_raw else '<EMPTY>'
                prompt = get_sql_correctness_check_prompt(
                    caller=caller,
                    code_meta=code_meta,
                    orm_code=record.get('orm_code', ''),
                    sql_statements=str(record.get('sql_statement_list', []))
                )
                
                response = await llm_client.call_async(session, prompt, max_tokens=100, temperature=0.0, max_retries=1000)
                
                is_correct = True
                reason = ""
                correction_override = None
                
                if response and response.strip().lower().startswith('否'):
                    is_correct = False
                    reason = response.replace('否', '').strip(' ，,')

                    # 新增逻辑：如果理由涉及特定关键词，则覆盖为正确
                    if re.search(r'事务|表名', reason):
                        is_correct = True
                        correction_override = f"Keyword match: {reason}"
                
                new_record = record.copy()
                new_record['correctness_check'] = {
                    'is_correct': is_correct,
                    'reason': reason,
                    'tag': '' if is_correct else '<INCORRECT SQL>',
                    'checked_at': datetime.now().isoformat(),
                    'correction_override': correction_override
                }
                return new_record

            except Exception as e:
                logger.warning(f"检查记录正确性失败: {e}")
                error_record = record.copy()
                error_record['correctness_check'] = {
                    'is_correct': True,  # 默认正确
                    'reason': f'检查失败: {str(e)}',
                    'tag': '',
                    'checked_at': datetime.now().isoformat(),
                    'check_error': True
                }
                return error_record

        # 动态获取并发数
        from config.data_clean.workflow_config import get_workflow_config  # type: ignore
        workflow_config = get_workflow_config()
        concurrency = workflow_config.get_concurrency('sql_correctness_check')
        semaphore = asyncio.Semaphore(concurrency)
        async def process_with_semaphore(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await check_single_record(session, record)

        processed_records = []
        with tqdm_asyncio(total=len(records_to_process), desc=f"检查SQL正确性 ({step_name})") as pbar:
            async with aiohttp.ClientSession() as session:
                tasks = [asyncio.ensure_future(process_with_semaphore(session, r)) for r in records_to_process]
                for task in tasks:
                    task.add_done_callback(lambda p: pbar.update(1))
                processed_records = await asyncio.gather(*tasks, return_exceptions=True)

        final_data = []
        error_count = 0
        incorrect_count = 0
        override_count = 0
        accepted_fix_count = 0  # LLM 审核通过
        rejected_fix_count = 0  # LLM 审核拒绝
        for i, result in enumerate(processed_records):
            if isinstance(result, Exception):
                error_count += 1
                error_record = records_to_process[i].copy()
                error_record['correctness_check'] = {
                    'is_correct': True,  # 默认正确
                    'reason': f'处理异常: {str(result)}',
                    'tag': '',
                    'checked_at': datetime.now().isoformat(),
                    'process_error': True
                }
                final_data.append(error_record)
            elif isinstance(result, dict):
                final_data.append(result)
                correctness_info = result.get('correctness_check', {})
                if not correctness_info.get('is_correct', True):
                    incorrect_count += 1
                if correctness_info.get('correction_override'):
                    override_count += 1
                if correctness_info.get('is_correct', True):
                    accepted_fix_count += 1
            else:
                # 处理其他意外情况
                error_count += 1
                error_record = records_to_process[i].copy()
                error_record['correctness_check'] = {
                    'is_correct': True,
                    'reason': f'未知处理结果类型: {type(result)}',
                    'tag': '',
                    'checked_at': datetime.now().isoformat(),
                    'process_error': True
                }
                final_data.append(error_record)

        self.current_data = excluded_records + final_data
        
        output_dir = self.workflow_dir / "sql_correctness_check"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{step_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_data, f, ensure_ascii=False, indent=2)
            
        step_info = {
            'step_name': step_name,
            'step_type': 'sql_correctness_check',
            'timestamp': datetime.now().isoformat(),
            'input_records': len(self.current_data),
            'records_to_check': len(records_to_process),
            'excluded_records': len(excluded_records),
            'correct_records': len(records_to_process) - incorrect_count - error_count,
            'incorrect_records': incorrect_count,
            'error_records': error_count,
            'overridden_as_correct': override_count,
            'incorrect_rate': incorrect_count / len(records_to_process) * 100 if records_to_process else 0.0,
            'output_file': str(output_file)
        }
        
        self.workflow_steps.append(step_info)
        logger.info(f"SQL正确性检查完成 - 在 {len(records_to_process):,} 条记录中，发现 {incorrect_count:,} 条不正确，{override_count:,} 条因关键词被覆盖为正确，{error_count:,} 条处理错误。")
        return step_info

    async def run_redundant_sql_validation(self, apply_fix: bool = False, step_name: str = "redundant_sql_validation_step") -> Dict[str, Any]:
        """
        运行冗余SQL验证步骤（新版接口）
        
        流程：
        1. 从上一清洗步骤的orm_analysis_reports中读取llm_validation_candidates.json
        2. 调用 RedundantSQLValidator.validate_llm_candidates 进行分步骤验证
        3. 根据 fix_recommendations 对当前数据集应用修复（可选）
        """
        if self.current_data is None:
            raise ValueError("请先加载并处理数据")
        
        logger.info(f"开始冗余SQL验证(新版接口): {step_name}")
        
        analysis_reports: Optional[Dict[str, Any]] = None  # 若需临时生成指纹分析报告
        candidates_file: Optional[str] = None

        # 1️⃣ 尝试从历史步骤中寻找最新的可用候选项文件
        for step in reversed(self.workflow_steps):
            if step.get('step_type') == 'sql_cleaning':
                reports = step.get('orm_analysis_reports') or {}
                path_from_step = reports.get('candidates_file') if isinstance(reports, dict) else None
                if path_from_step and Path(path_from_step).exists():
                    logger.info(f"从历史步骤 '{step['step_name']}' 中找到可用的候选项文件: {path_from_step}")
                    candidates_file = path_from_step
                    break  # 找到即退出
        
        # 2️⃣ 如果未找到候选项文件，则动态生成
        if not candidates_file:
            logger.info("未找到可用的候选项文件，将执行 ORM SQL 指纹分析以动态生成。")
            try:
                from data_processing.cleaning.orm_sql_fingerprint_analyzer import ORM_SQLFingerprintAnalyzer

                analyzer = ORM_SQLFingerprintAnalyzer()
                for record in self.current_data:
                    analyzer.add_record(record)

                analysis_output_dir = self.workflow_dir / "redundant_sql_validation" / "fingerprint_analysis"
                analysis_reports = analyzer.generate_reports(output_dir=str(analysis_output_dir))
                candidates_file = analysis_reports.get('candidates_file') if isinstance(analysis_reports, dict) else None
            except Exception as e:
                logger.error(f"动态进行ORM SQL指纹分析失败: {e}")
                return {
                    'step_skipped': True,
                    'reason': 'fingerprint_analysis_failed_dynamically',
                    'error': str(e)
                }

        # 3️⃣ 最后检查文件是否存在
        if not candidates_file or not Path(candidates_file).exists():
            logger.error("冗余SQL验证失败：无法找到或生成有效的候选项文件。")
            return {
                'step_skipped': True,
                'reason': 'no_candidates_file_found_or_generated'
            }
        
        # 读取候选项
        import json
        with open(candidates_file, 'r', encoding='utf-8') as f:
            llm_candidates = json.load(f)
        
        logger.info(f"读取到 {len(llm_candidates)} 个LLM验证候选项")
        
        # 2️⃣ 调用新版验证器
        from data_processing.cleaning.redundant_sql_validator import RedundantSQLValidator
        validation_output_dir = self.workflow_dir / "redundant_sql_validation"
        validator = RedundantSQLValidator(output_dir=str(validation_output_dir), llm_server="v3")
        # 动态获取并发数
        from config.data_clean.workflow_config import get_workflow_config  # type: ignore
        workflow_config = get_workflow_config()
        concurrency = workflow_config.get_concurrency('redundant_sql_validation')
        validation_result = await validator.validate_llm_candidates(llm_candidates, max_concurrent=concurrency)
        
        # 3️⃣ 可选：应用修复
        if apply_fix:
            await self._apply_fix_recommendations_async(validation_result.get('fix_recommendations', {}))
            logger.info("已根据fix_recommendations应用修复到当前数据集")
        
        # 4️⃣ 记录workflow步骤
        fr = validation_result['fix_recommendations']
        step_info = {
            'step_name': step_name,
            'step_type': 'redundant_sql_validation',
            'timestamp': datetime.now().isoformat(),
            'total_candidates': validation_result['total_candidates'],
            'validation_stats': validation_result['validation_stats'],
            'output_files': validation_result['report_files'],
            'fix_recommendations_summary': fr.get('summary', {}),
            'apply_fix': apply_fix,
            'orm_analysis_reports': analysis_reports
        }
        self.workflow_steps.append(step_info)
        
        logger.info("冗余SQL验证(新版接口)完成")
        return step_info

    # ------------------------------------------------------------------
    # 新增: 根据验证结果中的 fix_recommendations 修改 self.current_data
    # ------------------------------------------------------------------
    async def _apply_fix_recommendations_async(self, fix_recommendations: Dict[str, Any]):
        """
        根据fix_recommendations修改当前数据集（异步版本）
        
        处理三种类型的修复：
        1. remove_redundant: 删除确认冗余的SQL
        2. remove_wrong_new: 删除错误的新增SQL  
        3. add_missing: 添加必要的缺失SQL
        
        支持的SQL结构：
        - 单个字符串
        - SQL列表
        - param_dependent对象
        - 嵌套结构
        
        修复逻辑：
        - 冗余SQL直接删除，不置为<NO SQL GENERATE>
        - 如果删除后SQL列表为空，删除整条记录
        """
        if not fix_recommendations or not self.current_data:
            logger.info("没有修复建议或当前数据为空，跳过修复应用")
            return
        
        # 构建删除映射: (orm_code, caller) -> set(sql_text)
        remove_redundant_map: Dict[Tuple[str, str], set] = {}
        remove_wrong_new_map: Dict[Tuple[str, str], set] = {}
        add_missing_map: Dict[Tuple[str, str], List[Any]] = {}
        
        # 处理冗余删除
        for item in fix_recommendations.get('remove_redundant', []):
            orm_code = item.get('orm_code', '')
            caller = item.get('caller', '')
            key = (orm_code, caller)
            if key not in remove_redundant_map:
                remove_redundant_map[key] = set()
            for sql_rec in item.get('candidate_info', {}).get('redundant_sqls', []):
                sql_text = sql_rec.get('sql_text', '').replace(' <REDUNDANT SQL>', '').strip()
                if not sql_text:
                    continue

                # LLM 审核删除操作（异步）
                review = await self._llm_review_fix_async(orm_code, caller, 'remove', sql_text)
                if review.get('accepted', True):
                    remove_redundant_map[key].add(sql_text)
                else:
                    replacement = review.get('replacement', '')
                    if replacement:
                        if key not in add_missing_map:
                            add_missing_map[key] = []
                        add_missing_map[key].append(replacement)
        
        # 处理错误新增删除
        for item in fix_recommendations.get('remove_wrong_new', []):
            orm_code = item.get('orm_code', '')
            caller = item.get('caller', '')
            key = (orm_code, caller)
            if key not in remove_wrong_new_map:
                remove_wrong_new_map[key] = set()
            for sql_rec in item.get('candidate_info', {}).get('new_sqls', []):
                sql_text = sql_rec.get('sql_text', '').strip()
                if not sql_text:
                    continue

                review = await self._llm_review_fix_async(orm_code, caller, 'remove', sql_text)
                if review.get('accepted', True):
                    remove_wrong_new_map[key].add(sql_text)
                else:
                    replacement = review.get('replacement', '')
                    if replacement:
                        if key not in add_missing_map:
                            add_missing_map[key] = []
                        add_missing_map[key].append(replacement)
        
        # 处理缺失添加
        for item in fix_recommendations.get('add_missing', []):
            orm_code = item.get('orm_code', '')
            caller = item.get('caller', '')
            key = (orm_code, caller)
            if key not in add_missing_map:
                add_missing_map[key] = []
            
            # 支持添加字符串SQL和param_dependent结构
            missing_items = item.get('candidate_info', {}).get('missing_sql_examples', [])
            for missing_item in missing_items:
                if isinstance(missing_item, dict) and 'sql_text' in missing_item:
                    # 简单SQL文本
                    sql_text = missing_item.get('sql_text', '').strip()
                    if sql_text:
                        review = await self._llm_review_fix_async(orm_code, caller, 'add', sql_text)
                        if review.get('accepted', True):
                            add_missing_map[key].append(sql_text)
                        else:
                            replacement = review.get('replacement', '')
                            if replacement:
                                add_missing_map[key].append(replacement)
                elif isinstance(missing_item, dict) and missing_item.get('type') == 'param_dependent':
                    # param_dependent结构
                    # 将整个结构转为字符串示例进行审核
                    review = await self._llm_review_fix_async(orm_code, caller, 'add', str(missing_item))
                    if review.get('accepted', True):
                        add_missing_map[key].append(missing_item)
                    else:
                        replacement = review.get('replacement', '')
                        if replacement:
                            add_missing_map[key].append(replacement)
                elif isinstance(missing_item, str):
                    # 直接的SQL字符串
                    sql_text = missing_item.strip()
                    if sql_text:
                        review = await self._llm_review_fix_async(orm_code, caller, 'add', sql_text)
                        if review.get('accepted', True):
                            add_missing_map[key].append(sql_text)
                        else:
                            replacement = review.get('replacement', '')
                            if replacement:
                                add_missing_map[key].append(replacement)
        
        # 合并所有删除映射
        all_remove_map: Dict[Tuple[str, str], set] = {}
        for key in set(remove_redundant_map.keys()) | set(remove_wrong_new_map.keys()):
            all_remove_map[key] = remove_redundant_map.get(key, set()) | remove_wrong_new_map.get(key, set())
        
        def _process_sql_list(sql_list, key):
            """处理SQL列表：删除指定SQL，添加缺失SQL
            
            Returns:
                - None: 表示SQL列表为空，应该删除整条记录
                - 其他值: 处理后的SQL列表
            """
            try:
                remove_set = all_remove_map.get(key, set())
                add_list = add_missing_map.get(key, [])
                
                if isinstance(sql_list, str):
                    return self._process_string_sql(sql_list, remove_set, add_list)
                elif isinstance(sql_list, list):
                    return self._process_list_sql(sql_list, remove_set, add_list)
                elif isinstance(sql_list, dict):
                    return self._process_dict_sql(sql_list, remove_set, add_list)
                else:
                    # 未知类型，记录警告但保留原值
                    logger.warning(f"遇到未知SQL类型: {type(sql_list)}, 保留原值")
                    return sql_list
            except Exception as e:
                logger.error(f"处理SQL列表时出错: {e}, 保留原值")
                return sql_list
        
        # 应用修复 - 需要在迭代时安全地删除记录
        original_count = len(self.current_data)
        filtered_records = []
        modifications_count = 0
        deleted_records_count = 0
        error_count = 0
        
        for record in self.current_data:
            try:
                key = (record.get('orm_code', ''), record.get('caller', ''))
                
                # 检查是否需要处理此记录
                if key in all_remove_map or key in add_missing_map:
                    original_sql_list = record.get('sql_statement_list')
                    processed_sql_list = _process_sql_list(original_sql_list, key)
                    
                    # 如果处理结果为None，表示应该删除整条记录
                    if processed_sql_list is None:
                        deleted_records_count += 1
                        logger.debug(f"删除记录: orm_code={record.get('orm_code', 'unknown')[:50]}..., caller={record.get('caller', 'unknown')}")
                        continue  # 不添加到filtered_records中
                    
                    # 如果有变化，更新记录
                    if processed_sql_list != original_sql_list:
                        record['sql_statement_list'] = processed_sql_list
                        modifications_count += 1
                    
                    # 保留这条记录
                    filtered_records.append(record)
                else:
                    # 不需要处理的记录，直接保留
                    filtered_records.append(record)
            except Exception as e:
                logger.error(f"处理记录时出错 (orm_code={record.get('orm_code', 'unknown')}, caller={record.get('caller', 'unknown')}): {e}")
                error_count += 1
                # 出错时仍然保留原记录
                filtered_records.append(record)
        
        # 更新当前数据为过滤后的记录
        self.current_data = filtered_records
        
        # 记录修复统计
        logger.info(f"修复应用完成:")
        logger.info(f"  - 删除冗余SQL: {sum(len(sqls) for sqls in remove_redundant_map.values())} 个")
        logger.info(f"  - 删除错误新增SQL: {sum(len(sqls) for sqls in remove_wrong_new_map.values())} 个")
        logger.info(f"  - 添加缺失SQL: {sum(len(items) for items in add_missing_map.values())} 个")
        logger.info(f"  - 修改记录数: {modifications_count}")
        logger.info(f"  - 删除记录数: {deleted_records_count}")
        logger.info(f"  - 记录总数变化: {original_count} -> {len(filtered_records)}")
        if error_count > 0:
            logger.warning(f"  - 处理错误数: {error_count}")
    
    def _process_string_sql(self, sql_string: str, remove_set: set, add_list: List) -> Any:
        """处理单个SQL字符串
        
        Returns:
            - None: 表示SQL为空，应该删除整条记录
            - 其他值: 处理后的SQL内容
        """
        if sql_string == '<NO SQL GENERATE>':
            # 如果原本就是空，只添加缺失的SQL
            if add_list:
                return add_list if len(add_list) > 1 else add_list[0]
            else:
                return None  # 返回None表示应该删除记录
        
        # 检查是否需要删除
        clean_sql = sql_string.replace(' <REDUNDANT SQL>', '').strip()
        if clean_sql in remove_set:
            # 删除后，如果有缺失SQL需要添加，则添加；否则返回None表示删除记录
            if add_list:
                return add_list if len(add_list) > 1 else add_list[0]
            else:
                return None  # 返回None表示应该删除记录
        else:
            # 保留原SQL，并添加缺失SQL
            if add_list:
                result = [clean_sql] if clean_sql else []
                result.extend(add_list)
                return result if len(result) > 1 else (result[0] if result else None)
            else:
                return clean_sql if clean_sql else None
    
    def _process_list_sql(self, sql_list: List, remove_set: set, add_list: List) -> Any:
        """处理SQL列表
        
        Returns:
            - None: 表示SQL列表为空，应该删除整条记录
            - 其他值: 处理后的SQL列表
        """
        cleaned = []
        
        for item in sql_list:
            if isinstance(item, str):
                clean_sql = item.replace(' <REDUNDANT SQL>', '').strip()
                if clean_sql and clean_sql not in remove_set:
                    cleaned.append(clean_sql)
            elif isinstance(item, dict):
                processed_item = self._process_dict_sql(item, remove_set, [])
                if processed_item is not None:
                    cleaned.append(processed_item)
            elif isinstance(item, list):
                # 处理嵌套列表
                processed_nested = self._process_list_sql(item, remove_set, [])
                if processed_nested is not None:
                    cleaned.append(processed_nested)
            else:
                # 其他类型，保留
                cleaned.append(item)
        
        # 添加缺失的SQL
        cleaned.extend(add_list)
        
        # 如果清洗后没有内容，返回None表示删除记录
        if not cleaned:
            return None
        else:
            return cleaned
    
    def _process_dict_sql(self, sql_dict: Dict, remove_set: set, add_list: List) -> Optional[Dict]:
        """处理字典类型的SQL（如param_dependent）"""
        if sql_dict.get("type") == "param_dependent":
            return self._process_param_dependent_sql(sql_dict, remove_set, add_list)
        else:
            # 其他类型的字典，检查是否包含SQL字段
            if 'sql' in sql_dict:
                sql_content = sql_dict['sql']
                processed_dict = sql_dict.copy()
                
                if isinstance(sql_content, str):
                    clean_sql = sql_content.replace(' <REDUNDANT SQL>', '').strip()
                    if clean_sql not in remove_set:
                        processed_dict['sql'] = clean_sql
                        return processed_dict
                elif isinstance(sql_content, list):
                    processed_sql_list = self._process_list_sql(sql_content, remove_set, [])
                    if processed_sql_list is not None:
                        processed_dict['sql'] = processed_sql_list
                        return processed_dict
            
            # 如果没有SQL字段或者SQL被删除了，检查是否有其他重要字段
            important_fields = ['scenario', 'description', 'condition', 'when']
            if any(field in sql_dict for field in important_fields):
                return sql_dict  # 保留元数据信息
            
            return None  # 没有重要内容，删除
    
    def _process_param_dependent_sql(self, param_dependent_item: Dict, remove_set: set, add_list: Optional[List] = None) -> Optional[Dict]:
        """
        处理param_dependent类型的SQL项，删除其中的冗余/错误SQL，添加缺失SQL
        
        Args:
            param_dependent_item: param_dependent SQL项
            remove_set: 需要删除的SQL文本集合
            add_list: 需要添加的SQL项列表
            
        Returns:
            处理后的param_dependent项，如果所有变体都被删除则返回None
        """
        if not isinstance(param_dependent_item, dict) or param_dependent_item.get("type") != "param_dependent":
            return param_dependent_item
        
        cleaned_item = param_dependent_item.copy()
        cleaned_variants = []
        
        # 处理现有变体
        variants = param_dependent_item.get("variants", [])
        for variant in variants:
            if isinstance(variant, dict) and "sql" in variant:
                variant_sql = variant["sql"]
                cleaned_variant = variant.copy()
                
                if isinstance(variant_sql, str):
                    clean_sql = variant_sql.replace(' <REDUNDANT SQL>', '').strip()
                    if clean_sql not in remove_set:
                        cleaned_variant["sql"] = clean_sql
                        cleaned_variants.append(cleaned_variant)
                elif isinstance(variant_sql, list):
                    # 处理SQL列表
                    cleaned_sql_list = []
                    for sql in variant_sql:
                        if isinstance(sql, str):
                            clean_sql = sql.replace(' <REDUNDANT SQL>', '').strip()
                            if clean_sql and clean_sql not in remove_set:
                                cleaned_sql_list.append(clean_sql)
                    
                    if cleaned_sql_list:
                        cleaned_variant["sql"] = cleaned_sql_list
                        cleaned_variants.append(cleaned_variant)
                else:
                    # 其他类型，保留
                    cleaned_variants.append(cleaned_variant)
            else:
                # 非SQL变体或没有SQL字段，保留
                cleaned_variants.append(variant)
        
        # 添加缺失的SQL变体
        if add_list:
            for add_item in add_list:
                if isinstance(add_item, str):
                    # 添加简单SQL变体
                    new_variant = {
                        "scenario": "补充的必要SQL",
                        "sql": add_item
                    }
                    cleaned_variants.append(new_variant)
                elif isinstance(add_item, dict) and add_item.get("type") == "param_dependent":
                    # 如果要添加的也是param_dependent，合并其变体
                    for variant in add_item.get("variants", []):
                        cleaned_variants.append(variant)
                elif isinstance(add_item, dict) and "sql" in add_item:
                    # 添加结构化变体
                    cleaned_variants.append(add_item)
        
        if cleaned_variants:
            cleaned_item["variants"] = cleaned_variants
            return cleaned_item
        else:
            # 所有变体都被删除，返回None
            return None

    async def extract_keyword_data(self, keywords: Optional[List[str]] = None, step_name: str = "keyword_extraction_step2", use_llm: bool = False) -> Dict[str, Any]:
        """
        从清洗后的数据中提取关键词数据
        
        Args:
            keywords: 关键词列表，如果为None则使用GORM关键词
            step_name: 步骤名称
            use_llm: 是否使用LLM进行关键词判断而不是正则匹配
            
        Returns:
            提取结果信息
        """
        if self.current_data is None:
            raise ValueError("请先加载并清洗数据")
        
        logger.info(f"开始从清洗后的数据中提取关键词: {step_name} (use_llm={use_llm})")
        
        # 如果使用LLM模式，则调用LLM关键词提取逻辑
        if use_llm:
            return await self._extract_keyword_data_with_llm(step_name)
        
        # 创建临时的DataReader来使用其提取功能
        try:
            from ..data_reader import FunctionRecord, CodeMetaData
        except ImportError:
            from data_reader import FunctionRecord, CodeMetaData
        
        # 转换回FunctionRecord格式
        temp_records = []
        for record_dict in self.current_data:
            code_meta_data = [
                CodeMetaData(
                    code_file=meta['code_file'],
                    code_start_line=meta['code_start_line'],
                    code_end_line=meta['code_end_line'],
                    code_key=meta['code_key'],
                    code_value=meta['code_value'],
                    code_label=meta['code_label'],
                    code_type=meta['code_type'],
                    code_version=meta['code_version']
                ) for meta in record_dict['code_meta_data']
            ]
            
            record = FunctionRecord(
                function_name=record_dict['function_name'],
                orm_code=record_dict['orm_code'],
                caller=record_dict['caller'],
                sql_statement_list=record_dict['sql_statement_list'],
                sql_types=record_dict['sql_types'],
                code_meta_data=code_meta_data,
                sql_pattern_cnt=record_dict['sql_pattern_cnt'],
                source_file=record_dict['source_file']
            )
            temp_records.append(record)
        
        # 创建临时目录
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建临时DataReader并设置数据（不依赖实际文件）
            temp_reader = DataReader(temp_dir)
            temp_reader.records = temp_records
            
            # 执行关键词提取
            extraction_output_dir = self.workflow_dir / "keyword_extraction"
            if keywords is None:
                extract_result = temp_reader.extract_gorm_keywords(str(extraction_output_dir))
            else:
                extract_result = temp_reader.extract_by_keywords(
                    keywords=keywords,
                    output_dir=str(extraction_output_dir),
                    step_name=step_name
                )
        
        # 加载提取的数据
        extracted_data_file = Path(extract_result['output_directory']) / "keyword_matched_records.json"
        with open(extracted_data_file, 'r', encoding='utf-8') as f:
            self.extracted_data = json.load(f)
        
        step_info = {
            'step_name': step_name,
            'step_type': 'keyword_extraction',
            'timestamp': datetime.now().isoformat(),
            'input_records': len(self.current_data),
            'extracted_records': len(self.extracted_data),
            'extraction_rate': len(self.extracted_data) / len(self.current_data) * 100,
            'keywords_used': keywords or "GORM预定义关键词",
            'output_directory': extract_result['output_directory']
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"关键词提取完成 - 从 {len(self.current_data):,} 条记录中提取了 {len(self.extracted_data):,} 条匹配记录")
        return step_info

    async def _llm_review_fix_async(self, orm_code: str, caller: str, action: str, target_sql: str) -> Dict[str, Any]:
        """使用LLM对单条修复操作进行审核（异步版本）。

        Args:
            orm_code: ORM 代码全文或片段
            caller: 调用者名称
            action: 'remove' or 'add'
            target_sql: 目标 SQL 文本

        Returns:
            dict: {"accepted": bool, "replacement": str}
        """
        try:
            # 延迟导入避免循环依赖
            from utils.llm_client import LLMClient
            from config.data_clean.fix_review_prompts import REMOVAL_REVIEW_PROMPT, ADDITION_REVIEW_PROMPT  # type: ignore
            import aiohttp
            import json
            import re
            
            prompt_tpl = REMOVAL_REVIEW_PROMPT if action == 'remove' else ADDITION_REVIEW_PROMPT
            # 使用安全的字符串替换
            prompt = prompt_tpl.replace('{orm_code}', str(orm_code))
            prompt = prompt.replace('{caller}', str(caller))
            prompt = prompt.replace('{target_sql}', str(target_sql))
            
            client = LLMClient("v3")
            
            # 使用异步调用
            async with aiohttp.ClientSession() as session:
                response = await client.call_async(
                    session, 
                    prompt, 
                    max_tokens=300, 
                    temperature=0.0,
                    max_retries=5
                )
                
                if response:
                    # 提取 JSON
                    match = re.search(r"\{[\s\S]*\}", response)
                    if match:
                        resp_json = json.loads(match.group(0))
                        accepted = bool(resp_json.get("accepted", True))
                        replacement = resp_json.get("replacement", "")
                        return {"accepted": accepted, "replacement": replacement}
        except Exception as e:
            # 记录错误但不中断流程
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"LLM审查调用失败: {e}")
            pass  # 出错时默认接受
        return {"accepted": True, "replacement": ""}

    async def _extract_keyword_data_with_llm(self, step_name: str) -> Dict[str, Any]:
        """使用LLM进行关键词提取"""
        if self.current_data is None:
            raise ValueError("请先加载数据")

        def parse_llm_keyword_response(response_text: str) -> List[str]:
            """
            解析LLM的关键词响应，处理多种格式
            
            Args:
                response_text: LLM返回的原始文本
                
            Returns:
                解析出的有效关键词列表
            """
            if not response_text:
                return []
            
            response_lower = response_text.strip().lower()
            
            # 检查是否为否定回答
            if response_lower == "no" or response_lower.endswith("no"):
                return []
            
            # 延迟导入关键词列表
            try:
                from config.data_clean.special_keyword_prompt import SPECIAL_KEYWORDS
            except ImportError:
                # 如果导入失败，使用默认关键词列表
                SPECIAL_KEYWORDS = [
                    "Preload", "Transaction", "Scopes", "Locking", "Migration", 
                    "CreateOrUpdate", "save", "ForeignKey", "References"
                ]
            
            matched_keywords = []
            
            # 1. 尝试找到JSON数组格式 ["keyword1", "keyword2"]
            import re
            json_pattern = r'\["([^"]+)"(?:,\s*"([^"]+)")*\]'
            json_matches = re.findall(r'\[([^\]]+)\]', response_text)
            
            for match in json_matches:
                # 清理引号和分割
                items = [item.strip().strip('"').strip("'") for item in match.split(',')]
                for item in items:
                    if item in SPECIAL_KEYWORDS:
                        matched_keywords.append(item)
            
            # 2. 如果没找到JSON格式，尝试查找关键词本身
            if not matched_keywords:
                for keyword in SPECIAL_KEYWORDS:
                    # 检查关键词是否在文本中出现（忽略大小写）
                    if keyword.lower() in response_lower:
                        matched_keywords.append(keyword)
            
            # 3. 额外处理：查找被双引号包围的关键词
            quoted_keywords = re.findall(r'"([^"]+)"', response_text)
            for quoted in quoted_keywords:
                if quoted in SPECIAL_KEYWORDS and quoted not in matched_keywords:
                    matched_keywords.append(quoted)
            
            # 去重并保持顺序
            seen = set()
            unique_keywords = []
            for kw in matched_keywords:
                if kw not in seen:
                    seen.add(kw)
                    unique_keywords.append(kw)
            
            return unique_keywords

        # 设置并发控制
        concurrency = 50  # 降低并发数以避免服务器过载
        semaphore = asyncio.Semaphore(concurrency)

        # 延迟导入避免循环依赖
        from utils.llm_client import LLMClient
        from config.data_clean.special_keyword_prompt import SPECIAL_KEYWORD_PROMPT, SPECIAL_KEYWORDS

        llm_client = LLMClient("v3")

        async with aiohttp.ClientSession() as session:
            async def process_single_record(record: Dict[str, Any]) -> Dict[str, Any]:
                """处理单条记录，确保总是返回记录而不是None"""
                async with semaphore:
                    try:                        # 构造提示
                        # 使用安全的字符串替换而不是format
                        prompt = SPECIAL_KEYWORD_PROMPT.replace('{caller}', str(record.get('caller', '')))
                        prompt = prompt.replace('{code_meta}', json.dumps(record.get('code_meta_data', []), ensure_ascii=False, indent=2))
                        prompt = prompt.replace('{orm_code}', str(record.get('orm_code', '')))
                        prompt = prompt.replace('{sql_statements}', json.dumps(record.get('sql_statement_list', []), ensure_ascii=False, indent=2))

                        
                        # 调用LLM
                        response = await llm_client.call_async(
                            session, 
                            prompt, 
                            max_tokens=200, 
                            temperature=0.0,
                            max_retries=1000
                        )
                        
                        if response:
                            result_text = response.strip()
                            logger.debug(f"LLM响应 for {record.get('function_name', 'unknown')}: {result_text}")
                            
                            # 使用新的解析函数
                            matched_keywords = parse_llm_keyword_response(result_text)
                            
                            # 复制记录并添加分析信息
                            processed_record = record.copy()
                            processed_record['llm_keyword_analysis'] = {
                                'matched_keywords': matched_keywords,
                                'llm_response': result_text,
                                'analysis_timestamp': datetime.now().isoformat(),
                                'has_special_keywords': bool(matched_keywords)
                            }
                            return processed_record
                        else:
                            logger.error(f"LLM调用失败 for {record.get('function_name', 'unknown')}: 无响应")
                            # LLM调用失败，返回原记录并标记
                            failed_record = record.copy()
                            failed_record['llm_keyword_analysis'] = {
                                'matched_keywords': [],
                                'llm_response': '',
                                'analysis_timestamp': datetime.now().isoformat(),
                                'has_special_keywords': False,
                                'llm_call_failed': True,
                                'error': 'LLM调用无响应'
                            }
                            return failed_record
                            
                    except Exception as e:
                        logger.error(f"处理记录时发生错误 {record.get('function_name', 'unknown')}: {e}")
                        # 异常情况，返回原记录并标记错误
                        error_record = record.copy()
                        error_record['llm_keyword_analysis'] = {
                            'matched_keywords': [],
                            'llm_response': '',
                            'analysis_timestamp': datetime.now().isoformat(),
                            'has_special_keywords': False,
                            'processing_error': True,
                            'error': str(e)
                        }
                        return error_record
            
            # 使用进度条并发处理所有记录
            tasks = [process_single_record(record) for record in self.current_data]
            
            logger.info("开始并发调用LLM进行关键词分析...")
            results = await tqdm_asyncio.gather(*tasks, desc="LLM关键词分析")
            
            # 所有记录都已经被处理并标记，更新当前数据
            self.current_data = results
            
            # 分离匹配和未匹配的记录
            matched_records = [record for record in self.current_data 
                             if record.get('llm_keyword_analysis', {}).get('has_special_keywords', False)]
            unmatched_records = [record for record in self.current_data 
                               if not record.get('llm_keyword_analysis', {}).get('has_special_keywords', False)]
            
            # 数据完整性检查
            # if len(matched_records) + len(unmatched_records) != len(self.current_data):
            #     logger.error(f"❌ 数据处理后总数不匹配！原始: {len(self.current_data)}, 处理后: {len(matched_records) + len(unmatched_records)}")
            #     logger.error(f"匹配记录: {len(matched_records)}, 未匹配记录: {len(unmatched_records)}")
            #     raise ValueError("数据完整性检查失败：处理前后记录数不一致")
            
            # 保存提取的数据
            extraction_output_dir = self.workflow_dir / "keyword_extraction_llm"
            extraction_output_dir.mkdir(exist_ok=True)
            
            # 保存匹配的记录（用于后续处理）
            self.extracted_data = matched_records  # 只保留匹配的记录用于后续处理
            extracted_data_file = extraction_output_dir / "llm_keyword_matched_records.json"
            with open(extracted_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.extracted_data, f, ensure_ascii=False, indent=2)
            
            # 保存未匹配的记录
            unmatched_data_file = extraction_output_dir / "llm_keyword_unmatched_records.json"
            with open(unmatched_data_file, 'w', encoding='utf-8') as f:
                json.dump(unmatched_records, f, ensure_ascii=False, indent=2)
        
                # 统计关键词匹配情况
        keyword_stats = {}
        for record in self.extracted_data:
            for keyword in record.get('llm_keyword_analysis', {}).get('matched_keywords', []):
                keyword_stats[keyword] = keyword_stats.get(keyword, 0) + 1
        
        # 保存统计信息
        stats_file = extraction_output_dir / "llm_keyword_statistics.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_records_analyzed': len(self.current_data),
                'matched_records': len(self.extracted_data),
                'unmatched_records': len(unmatched_records),
                'keyword_statistics': keyword_stats,
                'special_keywords_used': SPECIAL_KEYWORDS,
                'extraction_timestamp': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        
        step_info = {
            'step_name': step_name,
            'step_type': 'llm_keyword_extraction',
            'timestamp': datetime.now().isoformat(),
            'input_records': len(self.current_data),
            'extracted_records': len(self.extracted_data),
            'unmatched_records': len(unmatched_records),
            'extraction_rate': len(self.extracted_data) / len(self.current_data) * 100,
            'keyword_statistics': keyword_stats,
            'special_keywords_count': len(SPECIAL_KEYWORDS),
            'output_directory': str(extraction_output_dir),
            'extracted_data_file': str(extracted_data_file),
            'unmatched_data_file': str(unmatched_data_file),
            'stats_file': str(stats_file)
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"LLM关键词提取完成 - 从 {len(self.current_data):,} 条记录中提取了 {len(self.extracted_data):,} 条匹配记录")
        logger.info(f"匹配关键词统计: {keyword_stats}")
        
        return step_info
    
    def process_extracted_data(self, step_name: str = "special_processing_step3") -> Dict[str, Any]:
        """
        对提取的数据进行特殊处理
        
        Args:
            step_name: 步骤名称
            
        Returns:
            处理结果信息
        """
        if self.extracted_data is None:
            raise ValueError("请先提取关键词数据")
        
        logger.info(f"开始对提取的数据进行特殊处理: {step_name}")
        
        # TODO: 这里预留特殊处理逻辑的接口
        # 当前只是简单复制，后续可以添加数据增强、标注等处理
        processed_data = []
        for record in self.extracted_data:
            # 复制原记录
            processed_record = record.copy()
            
            # TODO: 在这里添加特殊处理逻辑
            # 例如：
            # - 数据增强
            # - 自动标注
            # - 格式转换
            # - 质量评估
            
            # 添加处理标记
            processed_record['processing_metadata'] = {
                'processed_at': datetime.now().isoformat(),
                'processing_step': step_name,
                'processing_applied': []  # 后续可以记录应用的处理方法
            }
            
            processed_data.append(processed_record)
        
        self.extracted_data = processed_data
        
        # 保存处理后的数据
        processing_output_dir = self.workflow_dir / "special_processing"
        processing_output_dir.mkdir(exist_ok=True)
        
        processed_data_file = processing_output_dir / f"{step_name}.json"
        with open(processed_data_file, 'w', encoding='utf-8') as f:
            json.dump(self.extracted_data, f, ensure_ascii=False, indent=2)
        
        step_info = {
            'step_name': step_name,
            'step_type': 'special_processing',
            'timestamp': datetime.now().isoformat(),
            'input_records': len(self.extracted_data),
            'output_records': len(self.extracted_data),
            'processing_applied': [],  # 目前为空，后续可以记录具体处理
            'output_file': str(processed_data_file)
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"特殊处理完成 - 处理了 {len(self.extracted_data):,} 条提取的记录")
        return step_info
    
    def merge_processed_data_back(self, step_name: str = "merge_back_step4") -> Dict[str, Any]:
        """
        将处理后的数据合并回原数据集
        
        Args:
            step_name: 步骤名称
            
        Returns:
            合并结果信息
        """
        if self.extracted_data is None or self.current_data is None:
            raise ValueError("请先完成数据提取和特殊处理")
        
        logger.info(f"开始将处理后的数据合并回原数据集: {step_name}")
        
        # 创建function_name到记录的映射，用于快速查找
        extracted_data_map = {record['function_name']: record for record in self.extracted_data}
        
        # 合并数据
        merged_data = []
        updated_count = 0
        
        for original_record in self.current_data:
            function_name = original_record['function_name']
            
            if function_name in extracted_data_map:
                # 如果在提取数据中找到对应记录，使用处理后的版本
                processed_record = extracted_data_map[function_name].copy()
                
                # 保留原始记录中可能不在提取数据中的字段
                for key, value in original_record.items():
                    if key not in processed_record:
                        processed_record[key] = value
                
                # 添加合并标记
                if 'processing_metadata' not in processed_record:
                    processed_record['processing_metadata'] = {}
                processed_record['processing_metadata']['merged_back'] = True
                processed_record['processing_metadata']['merge_timestamp'] = datetime.now().isoformat()
                
                merged_data.append(processed_record)
                updated_count += 1
            else:
                # 如果不在提取数据中，保留原始记录并确保有llm_keyword_analysis字段
                if 'llm_keyword_analysis' not in original_record:
                    original_record['llm_keyword_analysis'] = {
                        'matched_keywords': [],
                        'llm_response': '"No"',
                        'analysis_timestamp': datetime.now().isoformat(),
                        'has_special_keywords': False
                    }
                merged_data.append(original_record)
        
        self.current_data = merged_data
        
        # 保存合并后的数据
        merge_output_dir = self.workflow_dir / "merged_data"
        merge_output_dir.mkdir(exist_ok=True)
        
        merged_data_file = merge_output_dir / f"{step_name}.json"
        with open(merged_data_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_data, f, ensure_ascii=False, indent=2)
        
        step_info = {
            'step_name': step_name,
            'step_type': 'data_merging',
            'timestamp': datetime.now().isoformat(),
            'total_records': len(self.current_data),
            'updated_records': updated_count,
            'unchanged_records': len(self.current_data) - updated_count,
            'update_rate': updated_count / len(self.current_data) * 100,
            'output_file': str(merged_data_file)
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"数据合并完成 - 更新了 {updated_count:,} 条记录，保持了 {len(self.current_data) - updated_count:,} 条原始记录")
        return step_info
    
    def save_workflow_summary(self) -> str:
        """
        保存工作流摘要
        
        Returns:
            摘要文件路径
        """
        summary = {
            'workflow_id': f"workflow_{self.workflow_timestamp}",
            'start_time': self.workflow_steps[0]['timestamp'] if self.workflow_steps else None,
            'end_time': datetime.now().isoformat(),
            'total_steps': len(self.workflow_steps),
            'steps': self.workflow_steps,
            'final_data_count': len(self.current_data) if self.current_data else 0,
            'extracted_data_count': len(self.extracted_data) if self.extracted_data else 0,
            'workflow_directory': str(self.workflow_dir)
        }
        
        summary_file = self.workflow_dir / "workflow_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"工作流摘要已保存: {summary_file}")
        return str(summary_file)
    
    def export_final_data(self, output_file: str = "final_processed_data.json") -> str:
        """
        导出最终处理后的数据
        
        Args:
            output_file: 输出文件名
            
        Returns:
            输出文件路径
        """
        if not self.current_data:
            raise ValueError("没有数据可导出")
        
        export_path = self.workflow_dir / output_file
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(self.current_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"最终数据已导出: {export_path}")
        return str(export_path)

        return str(export_path)    
        
    def print_workflow_summary(self):
        """打印工作流摘要（美化输出）"""
        print(f"\n{'='*80}")
        print(f"📋 工作流执行摘要")
        print(f"{'='*80}")
        print(f"🆔 工作流ID: workflow_{self.workflow_timestamp}")
        print(f"📁 输出目录: {self.workflow_dir}")
        print(f"⏱️  总步骤数: {len(self.workflow_steps)}")
        print(f"📊 最终数据量: {len(self.current_data):,} 条记录" if self.current_data else "📊 最终数据量: 0 条记录")
        
        if self.extracted_data:
            print(f"🎯 提取数据量: {len(self.extracted_data):,} 条记录")
        
        print(f"\n📝 执行步骤:")
        for i, step in enumerate(self.workflow_steps, 1):
            print(f"\n  {i}. {step['step_name']} ({step['step_type']})")
            print(f"     ⏰ 时间: {step['timestamp']}")
            
            if step['step_type'] == 'data_loading':
                print(f"     📊 加载记录: {step['total_records_loaded']:,}")
                print(f"     💾 数据大小: {step['data_size_mb']:.2f} MB")
                
            elif step['step_type'] == 'sql_cleaning':
                print(f"     📊 输入记录: {step['input_records']:,}")
                print(f"     📊 输出记录: {step['output_records']:,}")
                print(f"     🗑️  无效SQL删除: {step['invalid_sql_removed']:,}")
                print(f"     ✏️  记录修改: {step['records_modified']:,}")
                print(f"     📈 修改率: {step['modification_rate']:.2f}%")
                
            elif step['step_type'] == 'sql_completeness_check':
                print(f"     📊 检查记录: {step['input_records']:,}")
                print(f"     ✅ 完整记录: {step['complete_records']:,}")
                print(f"     ❌ 不完整记录: {step['incomplete_records']:,}")
                print(f"     📈 完整率: {step['completeness_rate']:.2f}%")
                
            elif step['step_type'] == 'sql_correctness_check':
                print(f"     📊 检查记录: {step['input_records']:,}")
                print(f"     ✅ 正确记录: {step['correct_records']:,}")
                print(f"     ❌ 错误记录: {step['incorrect_records']:,}")
                print(f"     🔥 处理异常: {step['error_records']:,}")
                print(f"     📈 错误率: {step['incorrect_rate']:.2f}%")
                
            elif step['step_type'] == 'keyword_extraction':
                print(f"     📊 输入记录: {step['input_records']:,}")
                print(f"     🎯 提取记录: {step['extracted_records']:,}")
                print(f"     📈 提取率: {step['extraction_rate']:.2f}%")
                
            elif step['step_type'] == 'special_processing':
                print(f"     🔧 处理记录: {step['input_records']:,}")
                print(f"     📤 输出记录: {step['output_records']:,}")
                
            elif step['step_type'] == 'data_merging':
                print(f"     📊 总记录数: {step['total_records']:,}")
                print(f"     🔄 更新记录: {step['updated_records']:,}")
                print(f"     📈 更新率: {step['update_rate']:.2f}%")
        
            elif step['step_type'] == 'control_flow_validation':
                print(f"     📊 总记录数: {step['total_records']:,}")
                print(f"     🔍 控制流记录: {step['control_flow_records']:,}")
                print(f"     📈 控制流比例: {step['control_flow_rate']:.2f}%")
                print(f"     ✅ 验证正确: {step['correct_records']:,}")
                print(f"     ❌ 验证错误: {step['incorrect_records']:,}")
                print(f"     🔥 验证异常: {step['error_records']:,}")
                print(f"     🔄 重新生成: {step.get('regenerated_records', 0):,}")
        
        print(f"\n💾 输出文件:")
        for step in self.workflow_steps:
            if 'output_directory' in step and step['output_directory']:
                print(f"   📁 {step['step_name']}: {step['output_directory']}")
            elif 'output_file' in step and step['output_file']:
                print(f"   📄 {step['step_name']}: {step['output_file']}")

    def load_from_existing_workflow(self, workflow_dir: str) -> bool:
        """
        从已有的工作流目录加载状态
        
        Args:
            workflow_dir: 工作流目录路径
            
        Returns:
            是否成功加载
        """
        workflow_path = Path(workflow_dir)
        if not workflow_path.exists():
            logger.error(f"工作流目录不存在: {workflow_dir}")
            return False
        
        # 从目录名推断工作流时间戳
        workflow_dir_name = workflow_path.name
        if workflow_dir_name.startswith('workflow_'):
            self.workflow_timestamp = workflow_dir_name.replace('workflow_', '')
        else:
            self.workflow_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 设置工作流目录
        self.workflow_dir = workflow_path
        
        # 尝试加载工作流摘要（如果存在）
        summary_file = workflow_path / "workflow_summary.json"
        if summary_file.exists():
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                self.workflow_steps = summary.get('steps', [])
                logger.info("📋 成功加载工作流摘要文件")
            except Exception as e:
                logger.warning(f"加载工作流摘要失败，将使用空步骤列表: {e}")
                self.workflow_steps = []
        else:
            logger.info("📋 工作流摘要文件不存在，将使用空步骤列表")
            self.workflow_steps = []
        
        # 查找最新的数据文件并加载
        data_loaded = self._load_latest_data()
        
        if data_loaded:
            logger.info(f"✅ 成功从工作流目录加载状态: {workflow_dir}")
            data_count = len(self.current_data) if self.current_data else 0
            logger.info(f"📊 当前数据量: {data_count:,} 条记录")
            logger.info(f"📝 已完成步骤: {len(self.workflow_steps)}")
            return True
        else:
            logger.error("❌ 无法加载数据文件")
            return False
    
    def _load_latest_data(self) -> bool:
        """
        加载最新的数据文件
        
        Returns:
            是否成功加载数据
        """
        logger.info(f"🔍 开始在目录 {self.workflow_dir} 中查找数据文件")
        
        # 按优先级查找数据文件，明确指定数据文件名
        data_file_candidates = [
            # 最高优先级：remove_no_sql_records步骤的输出
            "remove_no_sql_records/*_step.json",
            "remove_no_sql_records/remove_no_sql_records_step.json",
            
            # 其次：清洗步骤的输出
            "cleaning_steps/*/cleaned_records.json",
            "cleaning_steps/*/cleaned_records_with_redundant_marks.json",
            
            # 关键词提取的数据文件
            "keyword_extraction*/llm_keyword_matched_records.json",
            "keyword_extraction*/keyword_matched_records.json",
            
            # 合并数据
            "merged_data/*.json",
            
            # 最终数据
            "final_processed_dataset.json"
        ]
        
        # 排除的统计文件和日志文件
        exclude_patterns = [
            "*statistics*",
            "*log*", 
            "*summary*",
            "*unmatched*"
        ]
        
        for pattern in data_file_candidates:
            logger.debug(f"🔍 尝试模式: {pattern}")
            data_files = list(self.workflow_dir.glob(pattern))
            
            # 过滤掉统计文件
            filtered_files = []
            for file in data_files:
                exclude = False
                for exclude_pattern in exclude_patterns:
                    if file.match(exclude_pattern):
                        exclude = True
                        break
                if not exclude:
                    filtered_files.append(file)
            
            logger.debug(f"🔍 找到 {len(filtered_files)} 个数据文件: {[str(f) for f in filtered_files]}")
            
            if filtered_files:
                # 选择最新的文件
                latest_file = max(filtered_files, key=lambda f: f.stat().st_mtime)
                logger.info(f"📁 尝试加载数据文件: {latest_file}")
                
                if self._try_load_file(latest_file):
                    return True
        
        # 如果上面的特定模式都没找到，尝试所有JSON文件
        logger.info("🔍 尝试加载所有JSON文件...")
        all_json_files = list(self.workflow_dir.rglob("*.json"))
        
        # 过滤掉统计文件和日志文件
        data_files = []
        for file in all_json_files:
            exclude = False
            for exclude_pattern in exclude_patterns:
                if file.match(exclude_pattern):
                    exclude = True
                    break
            if not exclude:
                data_files.append(file)
        
        logger.info(f"🔍 找到 {len(data_files)} 个候选数据文件")
        
        # 按文件大小排序，优先尝试大文件（通常是数据文件）
        data_files.sort(key=lambda f: f.stat().st_size, reverse=True)
        
        for file in data_files:
            logger.info(f"📁 尝试加载数据文件: {file} (大小: {file.stat().st_size/1024/1024:.1f} MB)")
            if self._try_load_file(file):
                return True
        
        logger.error("❌ 未找到可用的数据文件")
        return False
    
    def _try_load_file(self, file_path: Path) -> bool:
        """
        尝试加载单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否成功加载
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 根据文件内容确定数据类型
            if isinstance(data, list) and len(data) > 0:
                # 检查是否是记录列表
                if isinstance(data[0], dict) and 'function_name' in data[0]:
                    self.current_data = data
                    logger.info(f"✅ 成功加载列表格式数据，包含 {len(data)} 条记录")
                    return True
                else:
                    logger.debug(f"❌ 列表格式但不是记录数据: {file_path}")
                    
            elif isinstance(data, dict):
                # 尝试多个可能的数据字段
                data_keys = ['records', 'data', 'items', 'results']
                for key in data_keys:
                    if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                        if isinstance(data[key][0], dict) and 'function_name' in data[key][0]:
                            self.current_data = data[key]
                            logger.info(f"✅ 成功加载字典格式数据（字段: {key}），包含 {len(data[key])} 条记录")
                            return True
                
                logger.debug(f"❌ 字典格式但没有找到有效的数据字段: {file_path}")
            else:
                logger.debug(f"❌ 数据格式不符合预期: {file_path}")
                
        except Exception as e:
            logger.warning(f"❌ 加载文件失败 {file_path}: {e}")
            
        return False
    
    def resume_from_step(self, step_name: str, **kwargs) -> Dict[str, Any]:
        """
        从指定步骤开始继续执行工作流
        
        Args:
            step_name: 要开始执行的步骤名称
            **kwargs: 步骤执行所需的额外参数
            
        Returns:
            执行结果
        """
        logger.info(f"🔄 从步骤 '{step_name}' 开始继续执行工作流")
        
        # 检查步骤是否已经执行过
        completed_steps = [step['step_name'] for step in self.workflow_steps]
        if step_name in completed_steps:
            logger.warning(f"⚠️ 步骤 '{step_name}' 已经执行过，将重新执行")
        
        # 步骤映射和执行
        step_mapping = {
            'remove_no_sql_records': self._execute_remove_no_sql_records,
            'redundant_sql_validation': self._execute_redundant_sql_validation,
            'sql_cleaning': self._execute_sql_cleaning,
            'keyword_extraction': self._execute_keyword_extraction,
            'export_final_data': self._execute_export_final_data
        }
        
        if step_name not in step_mapping:
            available_steps = list(step_mapping.keys())
            raise ValueError(f"不支持的步骤名称: {step_name}。支持的步骤: {available_steps}")
        
        try:
            result = step_mapping[step_name](**kwargs)
            logger.info(f"✅ 步骤 '{step_name}' 执行完成")
            return result
        except Exception as e:
            logger.error(f"❌ 步骤 '{step_name}' 执行失败: {e}")
            raise
    
    def _execute_remove_no_sql_records(self, reanalyze_no_sql: bool = True, **kwargs) -> Dict[str, Any]:
        """执行删除NO SQL记录步骤"""
        return asyncio.run(self.remove_no_sql_records(
            step_name="remove_no_sql_records_step", 
            reanalyze_no_sql=reanalyze_no_sql
        ))
    
    def _execute_redundant_sql_validation(self, apply_fix: bool = True, **kwargs) -> Dict[str, Any]:
        """执行冗余SQL验证步骤"""
        return asyncio.run(self.run_redundant_sql_validation(
            apply_fix=apply_fix,
            step_name="redundant_sql_validation_with_fix"
        ))
    
    def _execute_sql_cleaning(self, step_name: str = "sql_cleaning_resume", **kwargs) -> Dict[str, Any]:
        """执行SQL清洗步骤"""
        return self.run_sql_cleaning(step_name)
    
    def _execute_keyword_extraction(self, keywords: Optional[List[str]] = None, use_llm: bool = True, **kwargs) -> Dict[str, Any]:
        """执行关键词提取步骤"""
        return asyncio.run(self.extract_keyword_data(
            keywords=keywords, 
            step_name="keyword_extraction_resume", 
            use_llm=use_llm
        ))
    
    def _execute_export_final_data(self, output_file: str = "final_processed_dataset.json", **kwargs) -> Dict[str, Any]:
        """执行导出最终数据步骤"""
        final_data_path = self.export_final_data(output_file)
        summary_path = self.save_workflow_summary()
        self.print_workflow_summary()
        
        return {
            'final_data_path': final_data_path,
            'summary_path': summary_path,
            'workflow_directory': str(self.workflow_dir)
        }

    async def remove_no_sql_records(self, step_name: str = "remove_no_sql_records_step", 
                             reanalyze_no_sql: bool = False,
                             validator_config_path: str = "config/validation/rerun_config.yaml") -> Dict[str, Any]:
        """
        删除所有包含 <NO SQL GENERATE> 的记录
        
        Args:
            step_name: 步骤名称
            reanalyze_no_sql: 是否对<NO SQL GENERATE>记录进行重新分析
            validator_config_path: validator配置文件路径
            
        Returns:
            删除结果信息（包含重新分析统计）
        """
        if self.current_data is None:
            raise ValueError("请先加载并处理数据")
        
        if reanalyze_no_sql:
            logger.info(f"开始重新分析包含 <NO SQL GENERATE> 的记录: {step_name}")
        else:
            logger.info(f"开始删除所有包含 <NO SQL GENERATE> 的记录: {step_name}")
        
        # 初始化 validator（仅在需要时）
        validator = None
        if reanalyze_no_sql:
            try:
                from data_processing.validation.validator import RerunValidator
                # 创建步骤专用的输出目录
                validator_output_dir = self.workflow_dir / step_name / "reanalysis_details"
                validator_output_dir.mkdir(parents=True, exist_ok=True)
                # 传递自定义输出目录给validator
                validator = RerunValidator(config_path=validator_config_path, custom_output_dir=validator_output_dir)
                logger.info("✅ 成功初始化 RerunValidator")
                logger.info(f"📁 详细分析结果将保存到: {validator_output_dir}")
            except Exception as e:
                logger.error(f"❌ 初始化 RerunValidator 失败: {e}")
                logger.info("⚠️ 降级为删除模式")
                reanalyze_no_sql = False
        
        original_count = len(self.current_data)
        
        # 筛选出需要处理的记录
        no_sql_records = []
        non_no_sql_records = []
        
        for record in self.current_data:
            sql_list = record.get('sql_statement_list', [])
            # 检查是否为 NO SQL GENERATE 格式（支持多种格式）
            is_no_sql = False
            
            # 检查简单字符串格式
            if isinstance(sql_list, str):
                is_no_sql = sql_list == '<NO SQL GENERATE>'
            elif isinstance(sql_list, list):
                # 检查列表中的简单字符串格式
                if len(sql_list) == 1 and sql_list[0] == '<NO SQL GENERATE>':
                    is_no_sql = True
                else:
                    # 检查复杂格式：列表中包含 {"type": "NO_SQL_GENERATE", ...} 的对象
                    for item in sql_list:
                        if isinstance(item, dict) and item.get('type') == 'NO_SQL_GENERATE':
                            is_no_sql = True
                            break
            
            if is_no_sql:
                no_sql_records.append(record)
            else:
                non_no_sql_records.append(record)
        
        # 初始化结果列表
        filtered_records = non_no_sql_records.copy()  # 非<NO SQL GENERATE>记录直接保留
        removed_records = []
        reanalyzed_success = []
        reanalyzed_failed = []
        concurrency = 0  # 初始化并发数变量
        
        # 如果需要重新分析且有validator，则并发处理
        if reanalyze_no_sql and validator and no_sql_records:
            logger.info(f"开始并发重新分析 {len(no_sql_records):,} 条 '<NO SQL GENERATE>' 记录，并发数: 20")
            
            # 并发重新分析的函数
            async def reanalyze_single_record(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
                """重新分析单条记录"""
                try:
                    analysis_result = await validator.run_three_stage_analysis(record)
                    
                    if analysis_result['success'] and analysis_result['parsed_json']:
                        # 分析成功，更新 sql_statement_list
                        updated_record = record.copy()
                        updated_record['sql_statement_list'] = analysis_result['parsed_json']
                        return {
                            'status': 'success',
                            'record': updated_record,
                            'function_name': record.get('function_name', 'Unknown'),
                            'error': None
                        }
                    else:
                        # 分析失败
                        return {
                            'status': 'failed',
                            'record': record,
                            'function_name': record.get('function_name', 'Unknown'),
                            'error': analysis_result.get('error', '未知错误')
                        }
                except Exception as e:
                    # 分析异常
                    return {
                        'status': 'exception',
                        'record': record,
                        'function_name': record.get('function_name', 'Unknown'),
                        'error': str(e)
                    }
            
            # 设置并发控制
            concurrency = 20  # 降低并发数以避免服务器过载
            semaphore = asyncio.Semaphore(concurrency)
            
            async def process_with_semaphore(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    # 添加小延迟避免请求过快
                    await asyncio.sleep(0.1)
                    return await reanalyze_single_record(session, record)
            
            # 执行并发重新分析
            try:
                from tqdm.asyncio import tqdm as tqdm_asyncio
                
                processed_results = []
                with tqdm_asyncio(
                    total=len(no_sql_records), 
                    desc=f"🔄 重新分析 <NO SQL GENERATE> 记录 (并发数: {concurrency})",
                    unit="条记录",
                    colour="green",
                    dynamic_ncols=True
                ) as pbar:
                    async with aiohttp.ClientSession() as session:
                        tasks = []
                        for record in no_sql_records:
                            task = asyncio.ensure_future(process_with_semaphore(session, record))
                            
                            def update_progress(fut, pbar=pbar):
                                pbar.update(1)
                            
                            task.add_done_callback(update_progress)
                            tasks.append(task)
                        
                        processed_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理并发结果
                for result in processed_results:
                    if isinstance(result, Exception):
                        logger.warning(f"处理记录时发生异常: {result}")
                        continue
                    
                    # 类型安全检查
                    if not isinstance(result, dict):
                        logger.warning(f"结果格式异常，跳过: {type(result)}")
                        continue
                    
                    if result.get('status') == 'success':
                        filtered_records.append(result['record'])
                        reanalyzed_success.append(result['record'])
                    else:
                        # 重点修改：即使重分析失败，也保留原始记录
                        filtered_records.append(result['record'])
                        reanalyzed_failed.append(result['record'])
                        if result.get('status') == 'failed':
                            logger.debug(f"❌ 重新分析失败（已保留）: {result.get('function_name', 'Unknown')} - {result.get('error', '未知错误')}")
                        else:  # exception
                            logger.warning(f"❌ 重新分析异常（已保留）: {result.get('function_name', 'Unknown')} - {result.get('error', '未知错误')}")
                
                # 保存所有详细分析结果到单个JSON文件
                if validator and hasattr(validator, 'save_all_detailed_results'):
                    try:
                        detailed_results_path = await validator.save_all_detailed_results()
                        if detailed_results_path:
                            logger.info(f"✅ 详细分析结果已保存: {detailed_results_path}")
                    except Exception as e:
                        logger.warning(f"保存详细分析结果失败: {e}")
                
            except Exception as e:
                logger.error(f"并发重新分析过程发生异常: {e}")
                # 异常时回退到删除模式
                removed_records.extend(no_sql_records)
                reanalyzed_failed.extend(no_sql_records)
        
        else:
            # 不重新分析，直接删除所有 <NO SQL GENERATE> 记录
            removed_records.extend(no_sql_records)
        
        # 更新当前数据为过滤后的记录
        self.current_data = filtered_records
        
        if reanalyze_no_sql:
            logger.info(f"从 {original_count:,} 条记录中处理了 {len(reanalyzed_success) + len(reanalyzed_failed):,} 条 '<NO SQL GENERATE>' 记录:")
            logger.info(f"  - 重新分析并更新成功: {len(reanalyzed_success):,} 条")
            logger.info(f"  - 重新分析后仍无SQL（已保留）: {len(reanalyzed_failed):,} 条")
            logger.info(f"  - 最终记录总数: {len(filtered_records):,} 条 (无记录被删除)")
        else:
            logger.info(f"从 {original_count:,} 条记录中删除了 {len(removed_records):,} 条 '<NO SQL GENERATE>' 记录，保留了 {len(filtered_records):,} 条记录。")

        # 保存删除后的数据
        remove_output_dir = self.workflow_dir / "remove_no_sql_records"
        remove_output_dir.mkdir(exist_ok=True)
        
        remove_output_file = remove_output_dir / f"{step_name}.json"
        with open(remove_output_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_data, f, ensure_ascii=False, indent=2)
        
        # 记录工作流步骤
        step_info = {
            'step_name': step_name,
            'step_type': 'remove_no_sql_records',
            'timestamp': datetime.now().isoformat(),
            'input_records': original_count,
            'removed_records': 0, # 在重分析模式下，此值应为0
            'remaining_records': len(filtered_records),
            'removal_rate': 0.0,
            'output_file': str(remove_output_file),
            'reanalyze_enabled': reanalyze_no_sql
        }
        
        # 添加重新分析统计信息
        if reanalyze_no_sql:
            step_info.update({
                'reanalyzed_success': len(reanalyzed_success),
                'reanalyzed_failed_kept': len(reanalyzed_failed), # 明确表示失败但保留
                'reanalyzed_total': len(reanalyzed_success) + len(reanalyzed_failed),
                'reanalysis_success_rate': len(reanalyzed_success) / (len(reanalyzed_success) + len(reanalyzed_failed)) * 100 if (len(reanalyzed_success) + len(reanalyzed_failed)) > 0 else 0.0,
                'validator_config': validator_config_path,
                'concurrency': concurrency,
                'concurrent_processing_enabled': bool(validator and no_sql_records)
            })
        else: # 如果不是重分析模式，才计算正常的删除统计
            step_info['removed_records'] = len(removed_records)
            step_info['removal_rate'] = len(removed_records) / original_count * 100 if original_count > 0 else 0.0

        
        self.workflow_steps.append(step_info)
        
        if reanalyze_no_sql:
            logger.info(f"处理完成 - 重新分析并更新 {len(reanalyzed_success):,} 条，保留 {len(reanalyzed_failed):,} 条无SQL记录，最终记录数 {len(filtered_records):,}")
        else:
            logger.info(f"删除完成 - 删除了 {len(removed_records):,} 条记录，保留了 {len(filtered_records):,} 条记录")
        return step_info

    async def validate_control_flow_records(self, step_name: str = "control_flow_validation_step") -> Dict[str, Any]:
        """
        验证包含控制流语句的记录
        
        Args:
            step_name: 步骤名称
            
        Returns:
            验证结果信息
        """
        if self.current_data is None:
            raise ValueError("请先加载并处理数据")
        
        logger.info(f"开始验证控制流记录: {step_name}")
        
        # 动态导入控制流验证器
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
        
        try:
            from data_processing.cleaning.control_flow_validator import ControlFlowValidator
        except ImportError as e:
            logger.error(f"无法导入控制流验证器: {e}")
            raise ValueError("控制流验证器不可用，无法执行验证")
        
        # 创建控制流验证器
        validation_output_dir = self.workflow_dir / "control_flow_validation"
        validator = ControlFlowValidator(str(validation_output_dir), llm_server="v3")
        
        # 动态获取并发数
        from config.data_clean.workflow_config import get_workflow_config
        workflow_config = get_workflow_config()
        concurrency = workflow_config.get_concurrency('control_flow_validation')
        
        # 执行验证
        validation_result = await validator.validate_dataset(self.current_data, max_concurrent=concurrency)
        
        # 记录工作流步骤
        step_info = {
            'step_name': step_name,
            'step_type': 'control_flow_validation',
            'timestamp': datetime.now().isoformat(),
            'total_records': validation_result['total_records'],
            'control_flow_records': validation_result['control_flow_records'],
            'control_flow_rate': validation_result['control_flow_rate'],
            'validated_records': validation_result['validated_records'],
            'correct_records': validation_result['correct_records'],
            'incorrect_records': validation_result['incorrect_records'],
            'error_records': validation_result['error_records'],
            'regenerated_records': validation_result.get('regenerated_records', 0),
            'validation_file': validation_result.get('validation_file'),
            'problematic_file': validation_result.get('problematic_file'),
            'concurrent_requests': concurrency
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"控制流验证完成 - 检测到 {validation_result['control_flow_records']} 条控制流记录，验证正确: {validation_result['correct_records']}, 错误: {validation_result['incorrect_records']}")
        return step_info

    async def process_keyword_data_with_llm(self, step_name: str = "process_keyword_data_step") -> Dict[str, Any]:
        """
        使用LLM处理被识别为包含关键词的数据，根据指定prompt重新生成SQL。
        """
        if not self.extracted_data:
            logger.info("没有提取到关键词数据，跳过LLM处理步骤。")
            step_info = {
                'step_name': step_name,
                'step_type': 'keyword_data_processing',
                'timestamp': datetime.now().isoformat(),
                'status': 'skipped',
                'message': 'No extracted data to process.'
            }
            self.workflow_steps.append(step_info)
            return step_info

        logger.info(f"开始使用LLM处理 {len(self.extracted_data)} 条关键词数据: {step_name}")

        prompt_template = KEYWORD_PROCESSING_PROMPT

        from utils.llm_client import LLMClient
        from config.data_clean.workflow_config import get_workflow_config
        import aiohttp
        from tqdm.asyncio import tqdm_asyncio

        llm_client = LLMClient("v3")
        workflow_config = get_workflow_config()
        concurrency = workflow_config.get_concurrency('keyword_data_processing')
        semaphore = asyncio.Semaphore(concurrency)

        async def process_single_record(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
            try:
                keywords = record.get('llm_keyword_analysis', {}).get('matched_keywords', [])

                # 1️⃣ 安全替换，仅替换我们预定义的占位符，避免模板中其他 JSON 花括号触发 KeyError
                replacements = {
                    '{function_name}': record.get('function_name', ''),
                    '{orm_code}': record.get('orm_code', ''),
                    '{keyword}': ', '.join(keywords),
                    '{caller}': record.get('caller', ''),
                    '{code_meta}': json.dumps(record.get('code_meta_data', []), ensure_ascii=False, indent=2),
                }

                prompt = prompt_template
                for placeholder, value in replacements.items():
                    prompt = prompt.replace(placeholder, value)

                response = await llm_client.call_async(session, prompt, temperature=0.0, max_retries=1000)

                # 使用新的、更健壮的解析器
                from utils.response_parser import parse_model_response
                new_sql_list = parse_model_response(response)
                
                # 检查解析结果是否有效（例如，不是原始字符串的回退）
                is_successfully_parsed = True
                if isinstance(new_sql_list, list) and len(new_sql_list) == 1 and isinstance(new_sql_list[0], str) and new_sql_list[0] == response.strip():
                    is_successfully_parsed = False
                    logger.warning(f"Failed to parse LLM response for {record.get('function_name')}. Response: {response[:200]}")
                    # 🔧 修复：即使解析失败，也要添加处理信息确保记录完整性
                    updated_record = record.copy()
                    updated_record['keyword_processing_info'] = {
                        'status': 'parse_failed',
                        'timestamp': datetime.now().isoformat(),
                        'original_sql_list': record.get('sql_statement_list'),
                        'raw_response': response[:500],
                        'error': 'LLM response parsing failed'
                    }
                    return updated_record

                updated_record = record.copy()
                updated_record['sql_statement_list'] = new_sql_list
                updated_record['keyword_processing_info'] = {
                    'status': 'processed',
                    'timestamp': datetime.now().isoformat(),
                    'original_sql_list': record.get('sql_statement_list')
                }
                return updated_record
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                # Include raw response if available
                raw_resp = locals().get('response', '<<no response captured>>')
                logger.error(
                    f"❌ 处理记录 {record.get('function_name')} 失败:\n"
                    f"Exception: {e}\n"
                    f"Traceback:\n{tb}\n"
                    f"Raw LLM Response (first 500 chars):\n{str(raw_resp)[:500]}\n"
                    f"Prompt (excerpt): {prompt[:200]} ..."
                )
                # 🔧 修复：即使出现异常，也要确保记录被保留并标记
                error_record = record.copy()
                error_record['keyword_processing_info'] = {
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'original_sql_list': record.get('sql_statement_list'),
                    'error': str(e),
                    'traceback': tb
                }
                return error_record

        async def process_with_semaphore(session: aiohttp.ClientSession, record: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await process_single_record(session, record)

        tasks = []
        async with aiohttp.ClientSession() as session:
            for record in self.extracted_data:
                tasks.append(process_with_semaphore(session, record))
            results = await tqdm_asyncio.gather(*tasks, desc="Processing keyword data with LLM")

        # 🔍 记录输入数量，确保数据完整性
        input_record_count = len(self.extracted_data)
        
        success_count = 0
        failure_count = 0
        processed_records = []
        for res in results:
            if res is None:
                logger.error("❌ 发现空记录！这不应该发生。")
                failure_count += 1
                continue
            processed_records.append(res)
            
            # 根据处理状态进行统计
            processing_status = res.get('keyword_processing_info', {}).get('status', 'unknown')
            if processing_status == 'processed':
                success_count += 1
            else:
                failure_count += 1

        # 🔍 数据完整性检查
        if len(processed_records) != input_record_count:
            logger.error(f"❌ 处理结果数量不匹配！输入: {input_record_count}, 输出: {len(processed_records)}")
            
        self.extracted_data = processed_records
        
        output_dir = self.workflow_dir / "keyword_data_processing"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{step_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.extracted_data, f, ensure_ascii=False, indent=2)

        step_info = {
            'step_name': step_name,
            'step_type': 'keyword_data_processing',
            'timestamp': datetime.now().isoformat(),
            'input_records': input_record_count,  # 🔧 修复：使用正确的输入记录数
            'output_records': len(processed_records),  # 🔧 新增：明确的输出记录数
            'processed_successfully': success_count,
            'processing_failed': failure_count,
            'output_file': str(output_file)
        }
        self.workflow_steps.append(step_info)

        logger.info(f"关键词数据处理完成 - 输入 {input_record_count} 条, 输出 {len(processed_records)} 条, 成功处理 {success_count} 条, 失败 {failure_count} 条.")
        return step_info


def run_complete_workflow_from_raw_data(data_dir: str, keywords: Optional[List[str]] = None, base_output_dir: str = "workflow_output") -> Dict[str, Any]:
    """
    运行完整的数据处理工作流（新架构：清洗 -> 标签 -> 提取 -> 处理 -> 合并）
    
    Args:
        data_dir: 原始数据目录
        keywords: 关键词列表，如果为None则使用GORM关键词
        base_output_dir: 输出基目录
        
    Returns:
        工作流结果信息
    """
    logger.info("开始新架构的完整数据处理工作流")
    
    # 创建工作流管理器
    workflow = WorkflowManager(base_output_dir)
    
    try:
        # 步骤1: 加载原始数据集
        load_result = workflow.load_raw_dataset(data_dir)
        
        # 步骤2: 对全体数据进行SQL清洗
        cleaning_result = workflow.run_sql_cleaning("sql_cleaning_step1")
        
        # 步骤2.5: 使用LLM检查SQL完整性并标记缺少信息的数据
        logger.info("开始执行SQL完整性检查和数据标记...")
        tagging_result = asyncio.run(workflow.tag_lack_information_data("sql_completeness_check_step2"))
        
        # 步骤2.6: 使用LLM检查SQL正确性
        logger.info("开始执行SQL正确性检查...")
        correctness_result = asyncio.run(workflow.check_sql_correctness("sql_correctness_check_step2.6"))
        
        # 步骤3: 从清洗后的数据中提取关键词数据
        extraction_result = workflow.extract_keyword_data(keywords, "keyword_extraction_step3")
        
        # 步骤4: 对提取的数据进行特殊处理
        processing_result = workflow.process_extracted_data("special_processing_step4")
        
        # 步骤5: 将处理后的数据合并回原数据集
        merge_result = workflow.merge_processed_data_back("merge_back_step5")
        
        # 导出最终数据
        final_data_path = workflow.export_final_data("final_processed_dataset.json")
        
        # 保存工作流摘要
        summary_path = workflow.save_workflow_summary()
        
        # 打印摘要
        workflow.print_workflow_summary()
        
        result = {
            'workflow_completed': True,
            'workflow_directory': str(workflow.workflow_dir),
            'final_data_path': final_data_path,
            'summary_path': summary_path,
            'load_result': load_result,
            'cleaning_result': cleaning_result,
            'tagging_result': tagging_result,
            'correctness_result': correctness_result,
            'extraction_result': extraction_result,
            'processing_result': processing_result,
            'merge_result': merge_result
        }
        
        logger.info("新架构的完整数据处理工作流执行成功")
        return result
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        raise



# 保留旧的函数以兼容现有代码
def run_complete_sql_cleaning_workflow(extracted_data_path: str, base_output_dir: str = "workflow_output") -> Dict[str, Any]:
    """
    运行SQL清洗工作流（从已提取数据开始）- 保留兼容性
    """
    logger.warning("使用旧版workflow，建议使用 run_complete_workflow_from_raw_data")
    
    workflow = WorkflowManager(base_output_dir)
    
    try:
        # 加载已提取的数据
        with open(extracted_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        workflow.current_data = data
        
        # SQL清洗
        cleaning_result = workflow.run_sql_cleaning("sql_cleaning_step1")
        
        # 导出最终数据
        final_data_path = workflow.export_final_data()
        
        # 保存工作流摘要
        summary_path = workflow.save_workflow_summary()
        
        workflow.print_workflow_summary()
        
        return {
            'workflow_completed': True,
            'workflow_directory': str(workflow.workflow_dir),
            'final_data_path': final_data_path,
            'summary_path': summary_path,
            'cleaning_result': cleaning_result
        }
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        raise

def run_new_workflow(args):
    """运行全新的工作流"""
    print("🚀 开始运行全新的关键词优先数据处理工作流")
    
    workflow = WorkflowManager(args.output_dir)
    
    try:
        # 步骤 1: 加载原始数据集
        load_result = workflow.load_raw_dataset(args.data_dir)
        
        # 重要：立即保存原始完整数据集，确保数据完整性
        original_complete_dataset = workflow.current_data.copy() if workflow.current_data else []
        original_dataset_count = len(original_complete_dataset)
        
        logger.info(f"原始数据集已保存，共 {original_dataset_count:,} 条记录")
        
        # 如果是测试模式，随机抽样数据
        if args.test:
            print("🧪 测试模式开启，随机抽取20条数据进行处理。")
            logging.info("🧪 测试模式开启，随机抽取20条数据进行处理。")
            if workflow.current_data and len(workflow.current_data) > 100:
                workflow.current_data = random.sample(workflow.current_data, 100)
                # 同时更新保存的原始数据集
                original_complete_dataset = workflow.current_data.copy()
                original_dataset_count = len(original_complete_dataset)
                logging.info(f"测试模式：数据已采样，剩余 {original_dataset_count} 条记录。")

        # 步骤 2: 提取关键词数据（默认 GORM 关键词）
        extraction_result = asyncio.run(workflow.extract_keyword_data(args.keywords, "keyword_extraction_step1", use_llm=True))
        
        # 重要：保存关键词提取后的数据集，用于后续分离
        keyword_data_after_extraction = workflow.extracted_data.copy() if workflow.extracted_data else []
        
        # 使用更可靠的方式来标识记录
        def get_record_id(record):
            """生成记录的唯一标识 - 使用function_name:orm_code:caller三元组"""
            orm_code = record.get('orm_code', '')
            # 如果orm_code太长，取前100个字符作为标识的一部分
            orm_code_short = orm_code[:100] if len(orm_code) > 100 else orm_code
            return f"{record.get('function_name', '')}:{orm_code_short}:{record.get('caller', '')}"
        
        # 创建已匹配记录的ID集合
        matched_record_ids = {get_record_id(rec) for rec in keyword_data_after_extraction}
        
        # 从原始数据集中分离非关键词数据
        non_keyword_data = []
        for rec in original_complete_dataset:
            record_id = get_record_id(rec)
            if record_id not in matched_record_ids:
                non_keyword_data.append(rec)
        
        # 数据完整性验证（第一次）
        # if len(keyword_data_after_extraction) + len(non_keyword_data) != original_dataset_count:
        #     logger.error(f"❌ 关键词提取后数据分离不完整！原始: {original_dataset_count}, 关键词: {len(keyword_data_after_extraction)}, 非关键词: {len(non_keyword_data)}")
        #     raise ValueError("数据完整性检查失败：关键词提取后数据分离不完整")
        # else:
        #     logger.info(f"✅ 关键词提取后数据完整性验证通过：{original_dataset_count} = {len(keyword_data_after_extraction)} + {len(non_keyword_data)}")

        # 步骤 3: 使用LLM处理关键词数据
        workflow.extracted_data = keyword_data_after_extraction  # 确保使用完整的关键词数据集
        process_keyword_result = asyncio.run(workflow.process_keyword_data_with_llm(step_name="process_keyword_data_step2"))
        
        # 获取关键词处理后的数据
        keyword_data_after_processing = workflow.extracted_data.copy() if workflow.extracted_data else []
        
        # 记录关键词处理前后的数据变化
        logger.info(f"关键词数据处理前后变化：提取 {len(keyword_data_after_extraction)} → 处理后 {len(keyword_data_after_processing)}")
        
        # 记录分离步骤信息
        separation_step = {
            "step_name": "data_separation_and_processing",
            "step_type": "data_separation",
            "timestamp": datetime.now().isoformat(),
            "total_original_records": original_dataset_count,
            "keyword_data": {
                "extracted": len(keyword_data_after_extraction),
                "processed": len(keyword_data_after_processing)
            },
            "non_keyword_records": len(non_keyword_data)
        }
        workflow.workflow_steps.append(separation_step)
        
        # 步骤 4: 对非关键词数据进行清洗（保留llm_keyword_analysis字段）
        # 保存非关键词数据的llm_keyword_analysis字段
        non_keyword_data_with_analysis = []
        for rec in non_keyword_data:
            # 确保保留llm_keyword_analysis字段
            if 'llm_keyword_analysis' not in rec:
                rec['llm_keyword_analysis'] = {
                    'matched_keywords': [],
                    'llm_response': '"No"',
                    'analysis_timestamp': datetime.now().isoformat(),
                    'has_special_keywords': False
                }
            non_keyword_data_with_analysis.append(rec)
        
        workflow.current_data = non_keyword_data_with_analysis  # 设置工作流数据为非关键词数据
        cleaning_result = workflow.run_sql_cleaning("sql_cleaning_after_extraction")
        no_sql_removal_result = asyncio.run(workflow.remove_no_sql_records("remove_no_sql_records_step", reanalyze_no_sql=True))
        fix_result = asyncio.run(workflow.run_redundant_sql_validation(
            apply_fix=True,
            step_name="redundant_sql_validation_with_fix",
        ))
        
        # 获取清洗后的非关键词数据
        cleaned_non_keyword_data = workflow.current_data.copy() if workflow.current_data else []
        logger.info(f"非关键词数据清洗前后变化：原始 {len(non_keyword_data)} → 清洗后 {len(cleaned_non_keyword_data)}")

        # 步骤 5: 合并所有处理过的数据
        final_data = keyword_data_after_processing + cleaned_non_keyword_data
        workflow.current_data = final_data
        
        # 步骤 6: 控制流验证 - 检测包含switch、if等控制流语句的ORM代码
        logger.info("开始执行控制流验证步骤...")
        control_flow_validation_result = asyncio.run(workflow.validate_control_flow_records("control_flow_validation_step"))
        
        # 最终数据完整性检查
        total_after_processing = len(final_data)
        
        # 记录数据处理步骤
        data_processing_step = {
            "step_name": "data_processing_summary",
            "step_type": "data_processing",
            "timestamp": datetime.now().isoformat(),
            "original_total": original_dataset_count,
            "keyword_data": {
                "extracted": len(keyword_data_after_extraction),
                "processed": len(keyword_data_after_processing)
            },
            "non_keyword_data": {
                "original": len(non_keyword_data),
                "cleaned": len(cleaned_non_keyword_data)
            },
            "final_total": total_after_processing
        }
        workflow.workflow_steps.append(data_processing_step)
        
        # 步骤 6: 导出最终数据和摘要
        final_data_path = workflow.export_final_data("final_processed_dataset.json")
        summary_path = workflow.save_workflow_summary()
        workflow.print_workflow_summary()

        result = {
            "workflow_completed": True,
            "workflow_directory": str(workflow.workflow_dir),
            "final_data_path": final_data_path,
            "summary_path": summary_path,
            "load_result": load_result,
            "extraction_result": extraction_result,
            "process_keyword_result": process_keyword_result,
            "cleaning_result": cleaning_result,
            "no_sql_removal_result": no_sql_removal_result,
            "fix_result": fix_result,
            "control_flow_validation_result": control_flow_validation_result,
            "data_processing_summary": data_processing_step
        }

        print("\n✅ 工作流执行成功!")
        print(f"📁 输出目录: {result['workflow_directory']}")
        print(f"📄 最终数据: {result['final_data_path']}")
        print(f"📋 摘要文件: {result['summary_path']}")
        
        return result
        
    except Exception as e:
        logging.error(f"关键词优先工作流执行失败: {e}")
        raise


def run_resume_workflow(args):
    """运行resume工作流"""
    print(f"🔄 从工作流目录 {args.resume} 继续执行")
    
    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp(prefix="temp_workflow_")
    
    try:
        # 创建工作流管理器，使用临时目录避免创建不需要的目录
        workflow = WorkflowManager(base_output_dir=temp_dir)
        
        if not workflow.load_from_existing_workflow(args.resume):
            print(f"❌ 无法从工作流目录加载状态: {args.resume}")
            return None
        
        print(f"✅ 成功加载工作流状态")
        
        # 如果是测试模式，随机抽样数据
        if args.test:
            print("🧪 测试模式开启，随机抽取20条数据进行处理。")
            logging.info("🧪 测试模式开启，随机抽取20条数据进行处理。")
            if workflow.current_data and len(workflow.current_data) > 6000:
                workflow.current_data = random.sample(workflow.current_data, 6000)
                logging.info(f"数据已采样，剩余 {len(workflow.current_data)} 条记录。")

        # 如果指定了步骤，从该步骤开始执行
        if args.from_step:
            print(f"🎯 从步骤 '{args.from_step}' 开始执行")
            
            # 准备步骤参数
            step_kwargs = {}
            if args.from_step == 'remove_no_sql_records':
                step_kwargs['reanalyze_no_sql'] = args.reanalyze_no_sql
            elif args.from_step == 'redundant_sql_validation':
                step_kwargs['apply_fix'] = args.apply_fix
            elif args.from_step == 'keyword_extraction':
                step_kwargs['keywords'] = args.keywords
            
            try:
                # 执行单个步骤
                result = workflow.resume_from_step(args.from_step, **step_kwargs)
                
                # 如果不是最后一步，继续执行后续步骤
                if args.from_step != 'export_final_data':
                    print("🔄 继续执行后续步骤...")
                    
                    # 定义步骤顺序
                    step_order = [
                        'remove_no_sql_records',
                        'redundant_sql_validation', 
                        'export_final_data'
                    ]
                    
                    # 找到当前步骤的位置
                    current_index = step_order.index(args.from_step)
                    
                    # 执行后续步骤
                    for next_step in step_order[current_index + 1:]:
                        print(f"🔄 执行步骤: {next_step}")
                        
                        next_kwargs = {}
                        if next_step == 'remove_no_sql_records':
                            next_kwargs['reanalyze_no_sql'] = args.reanalyze_no_sql
                        elif next_step == 'redundant_sql_validation':
                            next_kwargs['apply_fix'] = args.apply_fix
                        
                        result = workflow.resume_from_step(next_step, **next_kwargs)
                
                print("\n✅ Resume工作流执行成功!")
                print(f"📁 工作流目录: {workflow.workflow_dir}")
                
                if isinstance(result, dict) and 'final_data_path' in result:
                    print(f"📄 最终数据: {result['final_data_path']}")
                    print(f"📋 摘要文件: {result['summary_path']}")
                
                return result
                
            except Exception as e:
                print(f"❌ Resume工作流执行失败: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print("⚠️ 未指定--from-step参数，请指定要从哪个步骤开始执行")
            print("可用步骤: remove_no_sql_records, redundant_sql_validation, sql_cleaning, keyword_extraction, export_final_data")
            return None
            
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"⚠️ 清理临时目录失败: {e}")