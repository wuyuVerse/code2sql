"""
Workflow管理器

管理数据处理的整个工作流，包括数据读取、清洗、验证等步骤
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from ..data_reader import DataReader
from ..cleaning.sql_cleaner import SQLCleaner

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
        
        logger.info(f"工作流管理器初始化完成，输出目录: {self.workflow_dir}")
    
    def load_raw_dataset(self, data_dir: str, keywords: List[str] = None) -> Dict[str, Any]:
        """
        从原始数据集开始加载和提取数据
        
        Args:
            data_dir: 原始数据目录
            keywords: 关键词列表，如果为None则使用GORM关键词
            
        Returns:
            加载和提取结果信息
        """
        logger.info(f"开始从原始数据集加载数据: {data_dir}")
        
        # 创建数据读取器
        reader = DataReader(data_dir)
        
        # 执行关键词提取
        if keywords is None:
            # 使用GORM关键词
            extraction_output_dir = self.workflow_dir / "keyword_extraction"
            extract_result = reader.extract_gorm_keywords(str(extraction_output_dir))
        else:
            # 使用自定义关键词
            extraction_output_dir = self.workflow_dir / "keyword_extraction"
            extract_result = reader.extract_by_keywords(
                keywords=keywords,
                output_dir=str(extraction_output_dir),
                step_name="custom_keyword_extraction"
            )
        
        # 加载提取的数据
        extracted_data_file = Path(extract_result['output_directory']) / "keyword_matched_records.json"
        with open(extracted_data_file, 'r', encoding='utf-8') as f:
            self.current_data = json.load(f)
        
        step_info = {
            'step_name': 'load_raw_dataset_and_extract',
            'step_type': 'data_loading_and_extraction',
            'timestamp': datetime.now().isoformat(),
            'input_source': str(data_dir),
            'total_raw_records': extract_result['total_records_processed'],
            'extracted_records': extract_result['matched_records'],
            'extraction_rate': extract_result['match_rate'],
            'keywords_used': keywords or "GORM预定义关键词",
            'output_directory': extract_result['output_directory']
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"数据加载和提取完成，从 {extract_result['total_records_processed']:,} 条原始记录中提取了 {len(self.current_data):,} 条匹配记录")
        return step_info
    
    def load_extracted_data(self, extracted_data_path: str) -> Dict[str, Any]:
        """
        加载已提取的数据
        
        Args:
            extracted_data_path: 提取数据的路径
            
        Returns:
            加载结果信息
        """
        logger.info(f"开始加载提取的数据: {extracted_data_path}")
        
        data_path = Path(extracted_data_path)
        
        # 查找关键词匹配记录文件
        if data_path.is_dir():
            keyword_file = data_path / "keyword_matched_records.json"
            if not keyword_file.exists():
                raise FileNotFoundError(f"在目录 {data_path} 中未找到 keyword_matched_records.json")
        else:
            keyword_file = data_path
        
        # 加载数据
        with open(keyword_file, 'r', encoding='utf-8') as f:
            self.current_data = json.load(f)
        
        step_info = {
            'step_name': 'load_extracted_data',
            'step_type': 'data_loading',
            'timestamp': datetime.now().isoformat(),
            'input_source': str(keyword_file),
            'records_loaded': len(self.current_data),
            'output_file': None
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"数据加载完成，共 {len(self.current_data)} 条记录")
        return step_info
    
    def run_sql_cleaning(self, step_name: str = "sql_cleaning") -> Dict[str, Any]:
        """
        运行SQL清洗步骤
        
        Args:
            step_name: 步骤名称
            
        Returns:
            清洗结果信息
        """
        if self.current_data is None:
            raise ValueError("请先加载数据")
        
        logger.info(f"开始SQL清洗步骤: {step_name}")
        
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
            'output_directory': cleaning_result['output_directory']
        }
        
        self.workflow_steps.append(step_info)
        
        logger.info(f"SQL清洗完成 - 移除了 {cleaning_result['invalid_sql_removed']} 个无效SQL，修改了 {cleaning_result['records_modified']} 条记录")
        return cleaning_result
    
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
            'workflow_directory': str(self.workflow_dir)
        }
        
        summary_file = self.workflow_dir / "workflow_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"工作流摘要已保存: {summary_file}")
        return str(summary_file)
    
    def get_current_data_sample(self, sample_size: int = 3) -> List[Dict[str, Any]]:
        """
        获取当前数据的样本
        
        Args:
            sample_size: 样本大小
            
        Returns:
            数据样本
        """
        if not self.current_data:
            return []
        
        return self.current_data[:sample_size]
    
    def export_final_data(self, output_file: str = "final_cleaned_data.json") -> str:
        """
        导出最终清洗后的数据
        
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
        print("🔄 数据清洗工作流摘要")
        print("=" * 60)
        
        print(f"📁 工作流目录: {self.workflow_dir}")
        print(f"⏰ 工作流ID: workflow_{self.workflow_timestamp}")
        print(f"📊 总步骤数: {len(self.workflow_steps)}")
        print(f"📋 最终数据量: {len(self.current_data) if self.current_data else 0} 条记录")
        
        print(f"\n🔍 处理步骤详情:")
        for i, step in enumerate(self.workflow_steps, 1):
            print(f"  {i}. {step['step_name']} ({step['step_type']})")
            if step['step_type'] == 'data_loading':
                print(f"     📥 加载记录: {step['records_loaded']:,}")
            elif step['step_type'] == 'data_loading_and_extraction':
                print(f"     📥 原始记录: {step['total_raw_records']:,}")
                print(f"     🎯 提取记录: {step['extracted_records']:,}")
                print(f"     📈 提取率: {step['extraction_rate']:.2f}%")
            elif step['step_type'] == 'sql_cleaning':
                print(f"     📊 输入记录: {step['input_records']:,}")
                print(f"     📊 输出记录: {step['output_records']:,}")
                print(f"     🗑️ 移除无效SQL: {step['invalid_sql_removed']:,}")
                print(f"     ✏️ 修改记录: {step['records_modified']:,}")
                print(f"     ✅ 保留有效SQL: {step['valid_sql_retained']:,}")
                print(f"     🔧 保留参数SQL: {step['param_dependent_sql_retained']:,}")
        
        print(f"\n💾 输出文件:")
        for step in self.workflow_steps:
            if 'output_directory' in step and step['output_directory']:
                print(f"   📁 {step['step_name']}: {step['output_directory']}")


def run_complete_sql_cleaning_workflow(extracted_data_path: str, base_output_dir: str = "workflow_output") -> Dict[str, Any]:
    """
    运行完整的SQL清洗工作流（从已提取数据开始）
    
    Args:
        extracted_data_path: 提取数据的路径
        base_output_dir: 输出基目录
        
    Returns:
        工作流结果信息
    """
    logger.info("开始完整的SQL清洗工作流")
    
    # 创建工作流管理器
    workflow = WorkflowManager(base_output_dir)
    
    try:
        # 步骤1: 加载提取的数据
        load_result = workflow.load_extracted_data(extracted_data_path)
        
        # 步骤2: SQL清洗
        cleaning_result = workflow.run_sql_cleaning("sql_cleaning_step1")
        
        # 导出最终数据
        final_data_path = workflow.export_final_data()
        
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
            'cleaning_result': cleaning_result
        }
        
        logger.info("完整的SQL清洗工作流执行成功")
        return result
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        raise


def run_complete_workflow_from_raw_data(data_dir: str, keywords: List[str] = None, base_output_dir: str = "workflow_output") -> Dict[str, Any]:
    """
    运行完整的数据处理工作流（从原始数据集开始）
    
    Args:
        data_dir: 原始数据目录
        keywords: 关键词列表，如果为None则使用GORM关键词
        base_output_dir: 输出基目录
        
    Returns:
        工作流结果信息
    """
    logger.info("开始从原始数据集的完整工作流")
    
    # 创建工作流管理器
    workflow = WorkflowManager(base_output_dir)
    
    try:
        # 步骤1: 从原始数据集加载并提取
        load_result = workflow.load_raw_dataset(data_dir, keywords)
        
        # 步骤2: SQL清洗
        cleaning_result = workflow.run_sql_cleaning("sql_cleaning_step1")
        
        # 导出最终数据
        final_data_path = workflow.export_final_data("final_cleaned_data_from_raw.json")
        
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
            'cleaning_result': cleaning_result
        }
        
        logger.info("从原始数据集的完整工作流执行成功")
        return result
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        raise 