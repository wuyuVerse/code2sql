import sys
import os
import asyncio
import openai
from pathlib import Path
from typing import Dict, Any, Optional, Set, List, Tuple

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from model.rl.eval_dimensions.llm_consistency import _async_extract_tables_and_columns
from model.rl.code2sql_reward_v2 import load_llm_prompts_config

async def preprocess_record(record: Dict) -> Tuple[bool, Set[str], Set[str]]:
    """
    预处理单条记录，仅进行表名和字段名抽取（异步）
    
    Args:
        record: 单条ORM记录
        
    Returns:
        (是否保留, 预抽取表名, 预抽取字段名)
    """
    try:
        # 获取必要信息
        orm_code = record.get("orm_code", "")
        code_meta_data = record.get("code_meta_data", [])
        function_name = record.get("function_name", "")
        caller = record.get("caller", "")
        
        if not orm_code:
            return False, set(), set()
        
        # 加载配置
        config = load_llm_prompts_config()
        
        # 创建AsyncClient并调用LLM抽取逻辑
        api_base = os.getenv("V3_API_URL", "http://212.64.90.3:8081/v1")
        api_key = "EMPTY"
        
        async with openai.AsyncClient(base_url=api_base, api_key=api_key) as client:
            # 正确调用_async_extract_tables_and_columns（按正确的参数顺序）
            llm_result = await _async_extract_tables_and_columns(
                client, orm_code, code_meta_data, function_name, caller, config, debug_mode=True
            )
        
        # 检查是否有LACK INFORMATION
        table_extraction_method = llm_result.get("table_extraction_method", "")
        column_extraction_method = llm_result.get("column_extraction_method", "")
        table_extraction_notes = llm_result.get("table_extraction_notes", "")
        column_extraction_notes = llm_result.get("column_extraction_notes", "")
        
        has_lack_info = ("<LACK INFORMATION>" in table_extraction_method or 
                        "<LACK INFORMATION>" in column_extraction_method or
                        "<LACK INFORMATION>" in table_extraction_notes or
                        "<LACK INFORMATION>" in column_extraction_notes)
        
        # 检查抽取结果是否为空
        pre_tables = llm_result.get("tables", set())
        pre_columns = llm_result.get("columns", set())
        is_empty = (len(pre_tables) == 0 and len(pre_columns) == 0)
        
        # 如果有LACK INFORMATION或为空，则丢弃
        if has_lack_info or is_empty:
            return False, set(), set()
        
        return True, pre_tables, pre_columns
        
    except Exception as e:
        print(f"预处理记录失败: {e}")
        return False, set(), set() 