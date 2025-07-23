"""
LLM一致性评估模块 - 纯异步实现
"""
import sys
import os
import json
import re
import asyncio
from typing import Dict, Any, Optional, Set, List
import openai

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from utils.sql_feature_extractor import SQLFeatureExtractor
from utils.response_parser import parse_model_response, recursively_extract_sql


async def _async_extract_tables_and_columns(client: openai.AsyncClient, orm_code: str, 
                                           code_meta_data: List[Dict], function_name: str, 
                                           caller: str, config: Dict[str, Any], 
                                           debug_mode: bool = False) -> Dict[str, Set[str]]:
    """使用AsyncClient并发抽取表名/字段名"""
    
    # 格式化元数据
    meta_data_str = ""
    for meta in code_meta_data or []:
        if 'code_key' in meta and 'code_value' in meta:
            meta_data_str += f"\n**{meta['code_key']}**:\n{meta['code_value']}"
            if 'code_file' in meta:
                meta_data_str += f"\n(文件: {meta['code_file']})"

    # 构建提示词
    table_prompt = config.get("table_extraction_prompt", "").format(
        function_name=function_name, caller=caller, orm_code=orm_code, meta_data_str=meta_data_str
    )
    column_prompt = config.get("column_extraction_prompt", "").format(
        function_name=function_name, caller=caller, orm_code=orm_code, meta_data_str=meta_data_str
    )

    # LLM配置
    llm_cfg = config.get("llm_config", {})
    model = llm_cfg.get("server_name", "v3")
    max_tokens = llm_cfg.get("max_tokens", 1024)
    temperature = llm_cfg.get("temperature", 0.0)

    async def call_llm(prompt: str):
        """异步调用LLM"""
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content if resp.choices else ""
        except Exception as e:
            if debug_mode:
                print(f"[LLM一致性] LLM调用失败: {e}")
            return ""

    # 并发发起两次请求
    table_task = asyncio.create_task(call_llm(table_prompt))
    column_task = asyncio.create_task(call_llm(column_prompt))
    table_resp, column_resp = await asyncio.gather(table_task, column_task)

    def _parse_response(resp_text: str, key: str) -> Set[str]:
        """解析LLM响应"""
        items: Set[str] = set()
        try:
            # 尝试提取JSON
            m = re.search(r"\{.*\}", resp_text, re.DOTALL)
            if m:
                data = json.loads(m.group())
                items = set(data.get(key, []))
            else:
                # 使用备选解析器
                parsed = parse_model_response(resp_text)
                if parsed and isinstance(parsed, list):
                    items = {str(p).strip() for p in parsed if p}
        except Exception as e:
            if debug_mode:
                print(f"[LLM一致性] 解析{key}失败: {e}")
        return items

    return {
        "tables": _parse_response(table_resp, "tables"), 
        "columns": _parse_response(column_resp, "columns")
    }


def _compare_extraction_results(llm_result: Dict[str, Set[str]], 
                               sqlglot_result: Dict[str, Any], 
                               config: Dict[str, Any],
                               debug_mode: bool = False) -> float:
    """比较LLM抽取结果与sqlglot解析结果的一致性"""
    try:
        # 获取权重配置
        consistency_config = config.get("consistency_config", {})
        table_weight = consistency_config.get("table_weight", 0.6)
        column_weight = consistency_config.get("column_weight", 0.4)
        
        # 获取并规范化结果（统一小写并去除包裹字符）

        def _normalize(name: str) -> str:
            """统一标识符格式：去除反引号/引号并转为小写"""
            return re.sub(r'["`\']', '', name).lower().strip()

        llm_tables = {_normalize(t) for t in llm_result.get("tables", set()) if t}
        llm_columns = {_normalize(c) for c in llm_result.get("columns", set()) if c}
        sqlglot_tables = {_normalize(t) for t in sqlglot_result.get("tables", set()) if t}
        sqlglot_columns = {_normalize(c) for c in sqlglot_result.get("columns", set()) if c}

        if debug_mode:
            print(f"[LLM一致性] 规范化结果 -> LLM表:{llm_tables} SQL表:{sqlglot_tables}")
            print(f"[LLM一致性] 规范化结果 -> LLM列:{list(llm_columns)[:10]} SQL列:{list(sqlglot_columns)[:10]}")
        
        # 计算一致性（Jaccard相似度）
        table_intersection = len(llm_tables & sqlglot_tables)
        table_union = len(llm_tables | sqlglot_tables)
        table_similarity = table_intersection / table_union if table_union > 0 else 0.0
        
        column_intersection = len(llm_columns & sqlglot_columns)
        column_union = len(llm_columns | sqlglot_columns)
        column_similarity = column_intersection / column_union if column_union > 0 else 0.0
        
        # 加权平均
        final_score = (table_similarity * table_weight + column_similarity * column_weight)
        final_score = max(0.0, min(1.0, round(final_score, 2)))
        
        if debug_mode:
            print(f"[LLM一致性] 表名相似度:{table_similarity:.2f}, 字段相似度:{column_similarity:.2f}, 综合:{final_score:.2f}")
        
        return final_score
        
    except Exception as e:
        if debug_mode:
            print(f"[LLM一致性] 比较失败: {e}")
        return 0.0


async def async_evaluate_llm_consistency(client: openai.AsyncClient, solution_str: str, 
                                        extra_info: Optional[dict], config: Dict[str, Any],
                                        debug_mode: bool = False) -> float:
    """
    异步评估LLM抽取一致性
    
    Args:
        client: 共享的AsyncClient
        solution_str: 模型响应文本
        extra_info: 额外信息（包含ORM代码等）
        config: 配置字典
        debug_mode: 调试模式
        
    Returns:
        一致性分数 (0.0-1.0)
    """
    try:
        if not extra_info:
            if debug_mode:
                print("[LLM一致性] extra_info为空")
            return 0.0
        
        # 获取ORM相关信息
        orm_code = extra_info.get("orm_code", "")
        code_meta_data = extra_info.get("code_meta_data", [])
        function_name = extra_info.get("function_name", "")
        caller = extra_info.get("caller", "")
        
        if not orm_code:
            if debug_mode:
                print("[LLM一致性] 未找到ORM代码")
            return 0.0
        
        # 提取SQL语句
        extracted_sqls = recursively_extract_sql(solution_str)
        if not extracted_sqls:
            if debug_mode:
                print("[LLM一致性] 未找到SQL语句")
            return 0.0
        
        # 使用LLM抽取表名和字段名
        llm_result = await _async_extract_tables_and_columns(
            client, orm_code, code_meta_data, function_name, caller, config, debug_mode
        )
        
        # 对每个SQL语句进行对比评估
        total_score = 0.0
        valid_sql_count = 0
        extractor = SQLFeatureExtractor()
        
        for sql in extracted_sqls:
            try:
                # 使用sqlglot解析SQL
                sqlglot_result = extractor.extract_tables_and_columns(sql)
                
                # 比较结果
                consistency_score = _compare_extraction_results(llm_result, sqlglot_result, config, debug_mode)
                total_score += consistency_score
                valid_sql_count += 1
                
                if debug_mode:
                    print(f"[LLM一致性] SQL: {sql[:50]}... 得分: {consistency_score:.2f}")
                    
            except Exception as e:
                if debug_mode:
                    print(f"[LLM一致性] SQL解析失败: {sql[:50]}... 错误: {e}")
                continue
        
        # 计算平均分数
        final_score = total_score / valid_sql_count if valid_sql_count > 0 else 0.0
        final_score = max(0.0, min(1.0, round(final_score, 2)))
        
        if debug_mode:
            print(f"[LLM一致性] 最终得分: {final_score:.2f} (有效SQL: {valid_sql_count})")
        
        # 构建详细信息
        detail_dict = {
            "llm_tables": list(llm_result.get("tables", set())),
            "llm_columns": list(llm_result.get("columns", set())),
            "valid_sql_count": valid_sql_count,
            "total_sqls": len(extracted_sqls)
        }
        
        return final_score, detail_dict
        
    except Exception as e:
        if debug_mode:
            print(f"[LLM一致性] 评估失败: {e}")
        return 0.0, {"llm_tables": [], "llm_columns": [], "valid_sql_count": 0, "total_sqls": 0, "error": str(e)} 