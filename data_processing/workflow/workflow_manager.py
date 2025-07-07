"""
Workflow管理器

管理数据处理的整个工作流，包括数据读取、清洗、验证等步骤
"""

import json
import logging
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from tqdm.asyncio import tqdm_asyncio
import re

# 尝试相对导入，如果失败则直接导入
try:
    from ..data_reader import DataReader
    from ..cleaning.sql_cleaner import SQLCleaner
except ImportError:
    from data_reader import DataReader
    from cleaning.sql_cleaner import SQLCleaner

logger = logging.getLogger(__name__)


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
        
        # 加载清洗后的数据作为当前数据
        cleaned_data_file = Path(cleaning_result['output_directory']) / "cleaned_records.json"
        with open(cleaned_data_file, 'r', encoding='utf-8') as f:
            self.current_data = json.load(f)
        
        # 记录工作流步骤
        step_info = {
            'step_name': step_name,
            'step_type': 'sql_cleaning',
            'timestamp': datetime.now().isoformat(),
            'input_records': cleaning_result['input_records_count'],
            'output_records': cleaning_result['output_records_count'],
            'records_modified': cleaning_result['records_modified'],
            'invalid_sql_removed': cleaning_result['invalid_sql_removed'],
            'valid_sql_retained': cleaning_result['valid_sql_retained'],
            'param_dependent_sql_retained': cleaning_result['param_dependent_sql_retained'],
            'empty_sql_lists_found': cleaning_result.get('empty_sql_lists_found', 0),
            'lists_emptied_after_cleaning': cleaning_result.get('lists_emptied_after_cleaning', 0),
            'output_directory': cleaning_result['output_directory']
        }
        
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
                # 假设 sql_statement_list 存在
                if record.get('sql_statement_list') == '<NO SQL GENERATE>':
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
                caller = record.get('caller', '')
                orm_code = record.get('orm_code', '')
                sql_statements = str(record.get('sql_statement_list', []))
                
                # 处理元数据
                code_meta_data = record.get('code_meta_data', [])
                if isinstance(code_meta_data, list) and code_meta_data:
                    code_meta = str(code_meta_data[0]) if code_meta_data else ''
                else:
                    code_meta = str(code_meta_data)
                
                # 生成提示词
                prompt = get_sql_completeness_check_prompt(
                    caller=caller,
                    code_meta=code_meta,
                    orm_code=orm_code,
                    sql_statements=sql_statements
                )
                
                # 调用LLM
                response = await llm_client.call_async(session, prompt, max_tokens=100, temperature=0.0)
                
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
        
        # 使用100并发处理所有记录
        semaphore = asyncio.Semaphore(100)
        
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
            'concurrent_requests': 100,
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
            is_no_sql = record.get('sql_statement_list') == '<NO SQL GENERATE>'
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
                prompt = get_sql_correctness_check_prompt(
                    caller=record.get('caller', ''),
                    code_meta=str(record.get('code_meta_data', [{}])[0]),
                    orm_code=record.get('orm_code', ''),
                    sql_statements=str(record.get('sql_statement_list', []))
                )
                
                response = await llm_client.call_async(session, prompt, max_tokens=100, temperature=0.0)
                
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

        semaphore = asyncio.Semaphore(100)
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

    def extract_keyword_data(self, keywords: Optional[List[str]] = None, step_name: str = "keyword_extraction_step2") -> Dict[str, Any]:
        """
        从清洗后的数据中提取关键词数据
        
        Args:
            keywords: 关键词列表，如果为None则使用GORM关键词
            step_name: 步骤名称
            
        Returns:
            提取结果信息
        """
        if self.current_data is None:
            raise ValueError("请先加载并清洗数据")
        
        logger.info(f"开始从清洗后的数据中提取关键词: {step_name}")
        
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
                # 如果不在提取数据中，保留原始记录
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
    
    def print_workflow_summary(self):
        """打印工作流摘要"""
        print("\n" + "=" * 60)
        print("🔄 数据处理工作流摘要")
        print("=" * 60)
        
        print(f"📁 工作流目录: {self.workflow_dir}")
        print(f"⏰ 工作流ID: workflow_{self.workflow_timestamp}")
        print(f"📊 总步骤数: {len(self.workflow_steps)}")
        print(f"📋 最终数据量: {len(self.current_data) if self.current_data else 0} 条记录")
        print(f"🎯 提取数据量: {len(self.extracted_data) if self.extracted_data else 0} 条记录")
        
        print(f"\n🔍 处理步骤详情:")
        for i, step in enumerate(self.workflow_steps, 1):
            print(f"  {i}. {step['step_name']} ({step['step_type']})")
            
            if step['step_type'] == 'data_loading':
                print(f"     📥 加载记录: {step['total_records_loaded']:,}")
                print(f"     💾 数据大小: {step['data_size_mb']:.2f} MB")
                
            elif step['step_type'] == 'sql_cleaning':
                print(f"     📊 输入记录: {step['input_records']:,}")
                print(f"     📊 输出记录: {step['output_records']:,}")
                print(f"     🗑️ 移除无效SQL: {step['invalid_sql_removed']:,}")
                print(f"     ✏️ 修改记录: {step['records_modified']:,}")
                print(f"     ✅ 保留有效SQL: {step['valid_sql_retained']:,}")
                if 'empty_sql_lists_found' in step:
                    print(f"     📋 原始空列表: {step['empty_sql_lists_found']:,}")
                if 'lists_emptied_after_cleaning' in step:
                    print(f"     🧹 清洗后空列表: {step['lists_emptied_after_cleaning']:,}")
                
            elif step['step_type'] == 'sql_completeness_check':
                print(f"     📊 输入记录: {step['input_records']:,}")
                print(f"     🏷️ 标记缺少信息: {step['lack_info_records']:,}")
                print(f"     ✅ 完整记录: {step['complete_records']:,}")
                print(f"     ❌ 处理错误: {step['error_records']:,}")
                print(f"     📈 缺少信息率: {step['lack_info_rate']:.2f}%")
                print(f"     🔄 并发请求数: {step['concurrent_requests']}")
                
            elif step['step_type'] == 'sql_correctness_check':
                print(f"     📊 输入记录: {step['records_to_check']:,} (从 {step['input_records']:,} 中筛选)")
                overridden_count = step.get('overridden_as_correct', 0)
                if overridden_count > 0:
                    print(f"     ✅ 正确记录: {step['correct_records']:,} (其中 {overridden_count:,} 条为关键词覆盖)")
                else:
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
        
        print(f"\n💾 输出文件:")
        for step in self.workflow_steps:
            if 'output_directory' in step and step['output_directory']:
                print(f"   📁 {step['step_name']}: {step['output_directory']}")
            elif 'output_file' in step and step['output_file']:
                print(f"   📄 {step['step_name']}: {step['output_file']}")


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