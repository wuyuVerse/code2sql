"""
数据处理模块

提供数据读取、分析、清洗等功能
"""

# 只导入核心模块，避免依赖问题
from .data_reader import DataReader, DataSampler, FunctionRecord, CodeMetaData

# 按需导入其他模块，避免依赖问题
def get_data_cleaner():
    """按需导入数据清洗器"""
    try:
        from .cleaning.sql_cleaner import SQLCleaner
        return SQLCleaner
    except ImportError as e:
        raise ImportError(f"SQL清洗器导入失败: {e}")

def get_data_analyzer():
    """按需导入数据分析器"""
    try:
        from .data_analyzer import DataAnalyzer
        return DataAnalyzer
    except ImportError as e:
        raise ImportError(f"数据分析器导入失败: {e}")

def get_workflow_manager():
    """按需导入工作流管理器"""
    try:
        from .workflow.workflow_manager import WorkflowManager, run_complete_sql_cleaning_workflow, run_complete_workflow_from_raw_data
        return WorkflowManager, run_complete_sql_cleaning_workflow, run_complete_workflow_from_raw_data
    except ImportError as e:
        raise ImportError(f"工作流管理器导入失败: {e}")

def get_training_data_converter():
    """按需导入训练数据转换器"""
    try:
        from .converter.training_data_converter import TrainingDataConverter
        return TrainingDataConverter
    except ImportError as e:
        raise ImportError(f"训练数据转换器导入失败: {e}")

__all__ = [
    'DataReader', 
    'DataSampler', 
    'FunctionRecord', 
    'CodeMetaData',
    'get_data_cleaner',
    'get_data_analyzer',
    'get_workflow_manager',
    'get_training_data_converter'
] 