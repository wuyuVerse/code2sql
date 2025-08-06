"""
分支互斥一致性评估模块
"""
import sys
import os
import json
import re
from typing import Dict, Any, Optional, Tuple
import openai

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from utils.response_parser import recursively_extract_sql


async def async_evaluate_branch_exclusivity(
    client: openai.AsyncClient,
    solution_str: str,
    extra_info: Optional[dict],
    config: Dict[str, Any],
    debug_mode: bool = False,
) -> Tuple[float, Dict[str, Any]]:
    """评估单条样本的分支互斥一致性。

    Returns
    -------
    Tuple[float, Dict[str, Any]]
        (score ∈ [0, 1], detail_dict)
    """
    # 基本校验
    if not extra_info:
        return 0.0, {"error": "no_extra_info"}

    orm_code: str = extra_info.get("orm_code", "")
    caller: str = extra_info.get("caller", "")
    function_name: str = extra_info.get("function_name", "")
    meta_data_str: str = extra_info.get("code_meta_data", "")
    
    if not orm_code or not caller:
        return 0.0, {"error": "missing_orm_or_caller"}

    sql_variants = recursively_extract_sql(solution_str) or []
    if not sql_variants:
        return 0.0, {"error": "no_sql"}

    # 构造 prompt
    prompt_template: str = config.get("branch_exclusivity_prompt", "")
    if not prompt_template:
        return 0.0, {"error": "missing_prompt"}

    variants_text = "\n".join([f"{i + 1}. {sql}" for i, sql in enumerate(sql_variants)])
    prompt = prompt_template.format(
        function_name=function_name,
        orm_code=orm_code,
        caller=caller,
        meta_data_str=meta_data_str,
        sql_variants_list=variants_text,
    )

    llm_cfg = config.get("llm_config", {})
    try:
        resp = await client.chat.completions.create(
            model=llm_cfg.get("server_name", "v3"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=llm_cfg.get("max_tokens", 8192),
            temperature=llm_cfg.get("temperature", 0.0),
        )
        content = resp.choices[0].message.content if resp.choices else ""
    except Exception as e:
        if debug_mode:
            print(f"[BranchEx] LLM call failed: {e}")
        return 0.0, {"error": f"llm_call_failed: {e}"}

    # 提取 JSON
    m = re.search(r"\{[\s\S]*\}", content)
    if not m:
        if debug_mode:
            print(f"[BranchEx] No JSON in response: {content[:200]}")
        return 0.0, {"error": "json_not_found", "raw": content[:200]}

    try:
        parsed = json.loads(m.group())
    except json.JSONDecodeError as e:
        if debug_mode:
            print(f"[BranchEx] JSON decode error: {e}")
        return 0.0, {"error": "json_decode_error", "raw": content[:200]}

    # 提取得分：优先顶层，其次 final_evaluation.score，再次 evaluation.score
    raw_score = (
        parsed.get("score")
        or parsed.get("final_evaluation", {}).get("score")
        or parsed.get("evaluation", {}).get("score")
        or 0.0
    )

    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0

    # 归一化到 [0,1]
    score = max(0.0, min(1.0, score))

    # 将解析出的分数写回，便于调试
    parsed["__extracted_score__"] = score
    
    return score, parsed 