"""
关键词对齐评估模块 - 纯异步实现
"""
import sys
import os
import json
import re
from typing import Dict, Any, Optional, List
import openai

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))


async def async_evaluate_keyword_alignment(client: openai.AsyncClient, solution_str: str, 
                                          extra_info: Optional[dict], config: Dict[str, Any],
                                          debug_mode: bool = False) -> Optional[float]:
    """
    异步评估关键词对齐度
    
    Args:
        client: 共享的AsyncClient
        solution_str: 模型响应文本
        extra_info: 额外信息
        config: 配置字典
        debug_mode: 调试模式
        
    Returns:
        关键词对齐分数 (0.0-1.0)，如果没有关键词则返回None
    """
    try:
        if not extra_info:
            return None, {"has_keywords": False, "matched_keywords": []}
            
        # 检查是否有关键词分析结果
        kw_analysis = extra_info.get("llm_keyword_analysis", {})
        if not kw_analysis.get("has_special_keywords"):
            return None, {"has_keywords": False, "matched_keywords": []}

        matched_keywords = kw_analysis.get("matched_keywords", [])
        if not matched_keywords:
            return None, {"has_keywords": False, "matched_keywords": []}

        # 获取ORM相关信息
        orm_code = extra_info.get("orm_code", "")
        function_name = extra_info.get("function_name", "")
        caller = extra_info.get("caller", "")
        code_metadata = str(extra_info.get("code_meta_data", []))

        # 获取关键词评估提示词模板
        keyword_evaluation_prompt_template = config.get("keyword_evaluation_prompt", "")
        if not keyword_evaluation_prompt_template:
            if debug_mode:
                print("[关键词对齐] 未找到关键词评估提示词配置")
            return 0.0, {"has_keywords": True, "matched_keywords": matched_keywords, "error": "missing_prompt_config"}

        # 构建评估提示词
        evaluation_prompt = keyword_evaluation_prompt_template.format(
            function_name=function_name or "<未知函数>",
            caller=caller or "<未知调用者>",
            matched_keywords=", ".join(matched_keywords),
            orm_code=orm_code,
            generated_sql_json=solution_str,
            code_metadata=code_metadata
        )

        # 获取LLM配置
        llm_config = config.get("llm_config", {})
        model = llm_config.get("server_name", "v3")
        max_tokens = llm_config.get("max_tokens", 2048)
        temperature = llm_config.get("temperature", 0.0)

        if debug_mode:
            print(f"[关键词对齐] 开始评估关键词: {matched_keywords}")

        # 异步调用LLM
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": evaluation_prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            result_text = response.choices[0].message.content if response.choices else ""
        except Exception as e:
            if debug_mode:
                print(f"[关键词对齐] LLM调用失败: {e}")
            return 0.0, {"has_keywords": True, "matched_keywords": matched_keywords, "error": f"llm_call_failed: {e}"}

        if not result_text:
            if debug_mode:
                print("[关键词对齐] LLM返回空响应")
            return 0.0, {"has_keywords": True, "matched_keywords": matched_keywords, "error": "empty_llm_response"}

        # 解析LLM响应
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result_data = json.loads(json_str)
                
                # 获取关键词分数
                keyword_score = float(result_data.get("keyword_score", 0.0))
                keyword_score = max(0.0, min(1.0, keyword_score))  # 确保分数在有效范围内
                
                if debug_mode:
                    print(f"[关键词对齐] 关键词: {matched_keywords}, 得分: {keyword_score:.2f}")
                
                # 构建详细信息
                detail_dict = {
                    "has_keywords": True,
                    "matched_keywords": matched_keywords,
                    "keyword_score": keyword_score
                }
                
                return keyword_score, detail_dict
                
            else:
                if debug_mode:
                    print("[关键词对齐] 无法从响应中提取JSON")
                return 0.0, {"has_keywords": True, "matched_keywords": matched_keywords, "error": "json_extraction_failed"}
                
        except json.JSONDecodeError as e:
            if debug_mode:
                print(f"[关键词对齐] JSON解析失败: {e}")
            return 0.0, {"has_keywords": True, "matched_keywords": matched_keywords, "error": f"json_decode_error: {e}"}
            
    except Exception as e:
        if debug_mode:
            print(f"[关键词对齐] 评估失败: {e}")
        return 0.0, {"has_keywords": False, "matched_keywords": [], "error": str(e)}, {"has_keywords": False, "matched_keywords": [], "error": str(e)} 