"""
多语句 SQL 惩罚维度（同步实现）

检测通过 `recursively_extract_sql` 提取出的每一条 SQL 字符串中是否包含多条 SQL 语句
（常见格式形如："INSERT ...; INSERT ...;"）。如果出现该情况，视为违反规范并施加惩罚。

返回 `(score, detail_dict)`：
    score ∈ [0,1]，1 表示没有违规，0 表示全部违规。可用于上层按照
    `penalty_cap * (1 - score)` 的形式扣分。
"""
from __future__ import annotations

import os
import sys
from typing import Tuple, List

# 第三方：纯解析无需数据库
import sqlparse  # type: ignore

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from utils.response_parser import recursively_extract_sql

__all__ = ["async_evaluate_multi_sql_penalty"]


def _is_multi_statement(sql: str) -> bool:
    """判断给定 SQL 字符串是否包含多条语句。"""
    # `sqlparse.split` 会根据语法安全地分割语句，忽略字符串与注释中的分号
    statements: List[str] = [stmt for stmt in sqlparse.split(sql) if stmt.strip()]
    # 多于 1 条即视为多语句
    return len(statements) > 1


async def async_evaluate_multi_sql_penalty(
    solution_str: str,
    debug_mode: bool = False,
):
    """异步接口，但实现为同步逻辑，方便直接 `asyncio.create_task` 调用。"""
    try:
        extracted_sqls = recursively_extract_sql(solution_str)
        total_count = len(extracted_sqls)
        if total_count == 0:
            # 若未检测到 SQL，视为无惩罚（score = 1）
            return 1.0, {
                "total_count": 0,
                "multi_sql_count": 0,
                "ratio": 0.0,
            }

        multi_sql_count = 0
        example_sqls: List[str] = []
        sql_analysis: List[dict] = []
        
        for i, sql in enumerate(extracted_sqls):
            statements = [stmt for stmt in sqlparse.split(sql) if stmt.strip()]
            is_multi = len(statements) > 1
            
            # 记录每条SQL的分析结果
            sql_analysis.append({
                "sql_index": i,
                "sql_content": sql,
                "statement_count": len(statements),
                "is_multi_statement": is_multi,
                "statements": statements if is_multi else []
            })
            
            if is_multi:
                multi_sql_count += 1
                if len(example_sqls) < 3:
                    # 记录前 3 个示例的完整内容，便于调试
                    example_sqls.append(sql)

        ratio = multi_sql_count / total_count
        score = 1.0 - ratio  # 0~1, 越高越好

        if debug_mode:
            print(
                f"[多语句惩罚] 检测到 {multi_sql_count}/{total_count} 条 SQL 含多语句, score={score:.2f}"
            )

        detail_dict = {
            "total_count": total_count,
            "multi_sql_count": multi_sql_count,
            "ratio": round(ratio, 3),
            "example_multi_sqls": example_sqls,
            "all_extracted_sqls": extracted_sqls,  # 保存所有提取的SQL，便于调试
            "sql_analysis": sql_analysis,  # 每条SQL的详细分析结果
        }

        return round(score, 2), detail_dict

    except Exception as e:
        if debug_mode:
            print(f"[多语句惩罚] 评估失败: {e}")
        # 出现异常时给 0.0 分，最大惩罚
        return 0.0, {"error": str(e)} 