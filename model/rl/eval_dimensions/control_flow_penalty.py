"""
控制流惩罚评估模块 - 纯异步实现
"""
import sys
import os
import json
import re
from typing import Dict, Any, Optional, List
import openai

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from utils.response_parser import recursively_extract_sql


async def async_evaluate_control_flow_penalty(client: openai.AsyncClient, solution_str: str,
                                             extra_info: Optional[dict], config: Dict[str, Any],
                                             debug_mode: bool = False) -> float:
    """
    异步评估控制流合理性惩罚
    
    Args:
        client: 共享的AsyncClient
        solution_str: 模型响应文本
        extra_info: 额外信息
        config: 配置字典
        debug_mode: 调试模式
        
    Returns:
        惩罚严重程度 (0.0-1.0)，0.0表示无惩罚，1.0表示最大惩罚
    """
    try:
        # 检查是否启用控制流惩罚
        penalty_config = config.get('control_flow_penalty', {})
        if not penalty_config.get('enabled', False):
            return 0.0
        
        if not extra_info:
            return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": [], "error": "no_extra_info"}
        
        # 获取ORM相关信息
        orm_code = extra_info.get('orm_code', '')
        caller = extra_info.get('caller', '')
        code_meta_data = str(extra_info.get('code_meta_data', []))
        
        if not orm_code:
            return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": [], "error": "no_orm_code"}
        
        # 提取SQL变体
        generated_sql_variants = recursively_extract_sql(solution_str)
        if not generated_sql_variants:
            return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": [], "error": "no_sql_variants"}
        
        # 格式化SQL变体用于prompt
        variants_text = "\n".join([f"{i+1}. {sql}" for i, sql in enumerate(generated_sql_variants)])
        
        # 获取控制流惩罚评估提示词模板
        control_flow_prompt_template = config.get("control_flow_penalty_prompt", "")
        if not control_flow_prompt_template:
            if debug_mode:
                print("[控制流惩罚] 未找到控制流惩罚评估提示词配置")
            return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": generated_sql_variants[:3], "error": "missing_prompt_config"}
        
        # 构建prompt
        prompt = control_flow_prompt_template.format(
            orm_code=orm_code,
            caller=caller,
            code_meta_data=code_meta_data,
            current_sql_variants=variants_text
        )
        
        # 获取LLM配置
        llm_config = config.get("llm_config", {})
        model = llm_config.get("server_name", "v3")
        max_tokens = llm_config.get("max_tokens", 2048)
        temperature = llm_config.get("temperature", 0.0)
        
        if debug_mode:
            print(f"[控制流惩罚] 开始评估，SQL变体数量: {len(generated_sql_variants)}")
        
        # 异步调用LLM进行评估
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            result_text = response.choices[0].message.content if response.choices else ""
        except Exception as e:
            if debug_mode:
                print(f"[控制流惩罚] LLM调用失败: {e}")
            return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": generated_sql_variants[:3], "error": f"llm_call_failed: {e}"}
        
        if not result_text:
            if debug_mode:
                print("[控制流惩罚] LLM返回空响应")
            return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": generated_sql_variants[:3], "error": "empty_llm_response"}
        
        # 解析结果（多级容错）
        def _safe_json_loads(text: str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return None

        parsed = _safe_json_loads(result_text)

        # 1) 解析 ```json ... ``` 代码块
        if parsed is None:
            m = re.search(r"```json\s*([\s\S]+?)\s*```", result_text, re.IGNORECASE)
            if m:
                parsed = _safe_json_loads(m.group(1))

        # 2) 解析任意 ``` ... ``` 代码块
        if parsed is None:
            m = re.search(r"```[\s\S]*?```", result_text)
            if m:
                content = re.sub(r"```[a-zA-Z0-9_]*", "", m.group()).rstrip("`")
                parsed = _safe_json_loads(content)

        # 3) 截取首个 '{...}'
        if parsed is None:
            m = re.search(r"\{[\s\S]*\}", result_text)
            if m:
                parsed = _safe_json_loads(m.group())

        if parsed is None:
            if debug_mode:
                print(f"[控制流惩罚] 结果解析失败，原始响应: {result_text[:300]}")
            return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": generated_sql_variants[:3], "error": "json_parse_failed", "raw_response": result_text[:200]}

        # 兼容多种字段层级
        def _extract_severity(js):
            if isinstance(js, dict):
                for key in ("penalty_severity", "severity"):
                    if key in js and isinstance(js[key], (int, float, str)):
                        return float(js[key])
                if "penalty_evaluation" in js:
                    return _extract_severity(js["penalty_evaluation"])
            return None

        sev = _extract_severity(parsed)
        if sev is None:
            if debug_mode:
                print(f"[控制流惩罚] 无法在解析结果中找到惩罚字段，解析结果: {parsed}")
            return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": generated_sql_variants[:3], "error": "severity_field_not_found", "parsed_result": str(parsed)[:200]}

        penalty_severity = max(0.0, min(1.0, float(sev)))

        if debug_mode:
            print(f"[控制流惩罚] 惩罚严重程度: {penalty_severity:.2f}")

        # 构建详细信息
        detail_dict = {
            "enabled": True,
            "penalty_severity": penalty_severity,
            "sql_variants": generated_sql_variants[:3],  # 最多保存3条SQL示例
            "variants_count": len(generated_sql_variants)
        }

        return penalty_severity, detail_dict
        
    except Exception as e:
        if debug_mode:
            print(f"[控制流惩罚] 评估失败: {e}")
        return 0.0, {"enabled": True, "penalty_severity": 0.0, "sql_variants": [], "error": str(e)} 