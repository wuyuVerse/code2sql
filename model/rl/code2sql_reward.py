import sys
import os
import json
import re
import yaml
from typing import Dict, Any, Optional, Set, List

# 添加项目根目录到Python路径，以便导入sql_feature_extractor
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils.sql_feature_extractor import SQLFeatureExtractor
from utils.response_parser import parse_model_response, recursively_extract_sql
from utils.llm_client import LLMClientManager

# === 【修改点3】新增导入，从配置文件中获取关键词评估提示词 ===
# 注意：不再从独立文件导入，而是从配置文件中读取

# ============================= 控制流惩罚评估 =============================

# ============================= 调试模式支持 =============================

import logging

def debug_print(message: str, debug_mode: bool = False):
    """调试打印函数，只有在调试模式下才输出"""
    if debug_mode:
        print(message)

# ============================= 配置加载函数 =============================

def load_llm_prompts_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载LLM提示词配置文件
    
    Args:
        config_path: 配置文件路径，如果为None则使用默认路径
        
    Returns:
        配置字典
    """
    if config_path is None:
        # 使用默认配置文件路径
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "rl", "qwen", "llm_prompts.yaml"
        )
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        debug_print(f"[配置] 成功加载LLM提示词配置: {config_path}")
        return config
    except Exception as e:
        debug_print(f"[配置] 加载LLM提示词配置失败: {e}")
        # 返回默认配置
        return {
            "table_extraction_prompt": "请从以下GORM代码中提取所有涉及的表名。\n\n**函数名称：** {function_name}\n**调用者：** {caller}\n\n**ORM代码：**\n```go\n{orm_code}\n```\n\n**代码元数据：**\n{meta_data_str}\n\n请以JSON格式输出，格式如下：\n```json\n{{\n    \"tables\": [\"表名1\", \"表名2\", ...]\n}}\n```\n\n只输出JSON格式，不要其他内容：",
            "column_extraction_prompt": "请从以下GORM代码中提取所有涉及的字段名。\n\n**函数名称：** {function_name}\n**调用者：** {caller}\n\n**ORM代码：**\n```go\n{orm_code}\n```\n\n**代码元数据：**\n{meta_data_str}\n\n请以JSON格式输出，格式如下：\n```json\n{{\n    \"columns\": [\"字段名1\", \"字段名2\", ...]\n}}\n```\n\n只输出JSON格式，不要其他内容：",
            "llm_config": {
                "server_name": "v3",
                "max_tokens": 1024,
                "temperature": 0.0,
                "max_retries": 3,
                "retry_delay": 1.0
            },
            "consistency_config": {
                "table_weight": 0.6,
                "column_weight": 0.4,
                "consistency_weight": 0.4,
                "validity_weight": 0.6
            }
        }

def load_rl_config() -> Dict[str, Any]:
    """
    加载RL训练配置文件，获取调试模式等参数
    
    Returns:
        配置字典
    """
    try:
        # 尝试加载RL配置文件
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "rl", "qwen", "qwen2_14b_rf.yaml"
        )
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 获取自定义奖励函数配置
        custom_reward_config = config.get("custom_reward_function", {})
        debug_mode = custom_reward_config.get("debug_mode", False)
        
        debug_print(f"[配置] 成功加载RL配置，调试模式: {debug_mode}")
        return {"debug_mode": debug_mode}
        
    except Exception as e:
        debug_print(f"[配置] 加载RL配置失败: {e}，使用默认调试模式: False")
        return {"debug_mode": False}

# 全局配置变量
_llm_prompts_config = None

def get_llm_prompts_config() -> Dict[str, Any]:
    """获取LLM提示词配置（单例模式）"""
    global _llm_prompts_config
    if _llm_prompts_config is None:
        _llm_prompts_config = load_llm_prompts_config()
    return _llm_prompts_config

# ============================= LLM抽取表/字段奖励函数 =============================

def extract_tables_and_columns_with_llm(orm_code: str, code_meta_data: List[Dict], 
                                       function_name: str = "", caller: str = "", debug_mode: bool = False) -> Dict[str, Set[str]]:
    """
    使用LLM从代码和元信息中抽取表名和字段名
    
    Args:
        orm_code: ORM代码
        code_meta_data: 代码元数据
        function_name: 函数名称
        caller: 调用者信息
        debug_mode: 调试模式开关
        
    Returns:
        包含表名和字段名的字典
    """
    # 获取配置
    config = get_llm_prompts_config()
    
    # 初始化LLM客户端管理器
    llm_manager = LLMClientManager()
    
    # 格式化代码元数据
    meta_data_str = ""
    if code_meta_data:
        for meta in code_meta_data:
            if 'code_key' in meta and 'code_value' in meta:
                meta_data_str += f"\n**{meta['code_key']}**:\n{meta['code_value']}"
                if 'code_file' in meta:
                    meta_data_str += f"\n(文件: {meta['code_file']})"
    
    # 从配置中获取提示词模板
    table_extraction_prompt_template = config.get("table_extraction_prompt", "")
    column_extraction_prompt_template = config.get("column_extraction_prompt", "")
    
    # 格式化提示词
    table_extraction_prompt = table_extraction_prompt_template.format(
        function_name=function_name,
        caller=caller,
        orm_code=orm_code,
        meta_data_str=meta_data_str
    )
    
    column_extraction_prompt = column_extraction_prompt_template.format(
        function_name=function_name,
        caller=caller,
        orm_code=orm_code,
        meta_data_str=meta_data_str
    )
    
    # 从配置中获取LLM参数
    llm_config = config.get("llm_config", {})
    server_name = llm_config.get("server_name", "v3")
    max_tokens = llm_config.get("max_tokens", 1024)
    temperature = llm_config.get("temperature", 0.0)
    
    try:
        # 获取LLM客户端
        client = llm_manager.get_client(server_name)
        
        # 调用LLM抽取表名
        table_response = client.call_openai(table_extraction_prompt, max_tokens=max_tokens, temperature=temperature)
        
        # 调用LLM抽取字段名
        column_response = client.call_openai(column_extraction_prompt, max_tokens=max_tokens, temperature=temperature)
        
        # 解析表名结果
        tables = set()
        extraction_method = ""
        extraction_notes = ""
        if table_response:
            try:
                # 提取JSON部分
                table_json_match = re.search(r'\{.*\}', table_response, re.DOTALL)
                if table_json_match:
                    json_str = table_json_match.group()
                    table_data = json.loads(json_str)
                    tables = set(table_data.get("tables", []))
                    extraction_method = table_data.get("extraction_method", "")
                    extraction_notes = table_data.get("notes", "")
                else:
                    # 尝试使用增强的解析器
                    parsed_response = parse_model_response(table_response)
                    if parsed_response and isinstance(parsed_response, list):
                        for item in parsed_response:
                            if isinstance(item, str) and item.strip():
                                tables.add(item.strip())
            except Exception as e:
                debug_print(f"[解析错误] 表名解析失败: {e}", debug_mode)
                # 尝试使用增强的解析器作为备选
                try:
                    parsed_response = parse_model_response(table_response)
                    if parsed_response and isinstance(parsed_response, list):
                        for item in parsed_response:
                            if isinstance(item, str) and item.strip():
                                tables.add(item.strip())
                except Exception as backup_e:
                    debug_print(f"[解析错误] 表名备选解析也失败: {backup_e}", debug_mode)
        
        # 解析字段名结果
        columns = set()
        column_extraction_method = ""
        column_extraction_notes = ""
        if column_response:
            try:
                # 提取JSON部分
                column_json_match = re.search(r'\{.*\}', column_response, re.DOTALL)
                if column_json_match:
                    json_str = column_json_match.group()
                    column_data = json.loads(json_str)
                    columns = set(column_data.get("columns", []))
                    column_extraction_method = column_data.get("extraction_method", "")
                    column_extraction_notes = column_data.get("notes", "")
                else:
                    # 尝试使用增强的解析器
                    parsed_response = parse_model_response(column_response)
                    if parsed_response and isinstance(parsed_response, list):
                        for item in parsed_response:
                            if isinstance(item, str) and item.strip():
                                columns.add(item.strip())
            except Exception as e:
                debug_print(f"[解析错误] 字段名解析失败: {e}", debug_mode)
                # 尝试使用增强的解析器作为备选
                try:
                    parsed_response = parse_model_response(column_response)
                    if parsed_response and isinstance(parsed_response, list):
                        for item in parsed_response:
                            if isinstance(item, str) and item.strip():
                                columns.add(item.strip())
                except Exception as backup_e:
                    debug_print(f"[解析错误] 字段名备选解析也失败: {backup_e}", debug_mode)
        
        result = {
            "tables": tables,
            "columns": columns,
            "table_extraction_method": extraction_method,
            "column_extraction_method": column_extraction_method,
            "table_extraction_notes": extraction_notes,
            "column_extraction_notes": column_extraction_notes
        }
        return result
        
    except Exception as e:
        debug_print(f"[LLM抽取] LLM调用失败: {e}", debug_mode)
        return {
            "tables": set(),
            "columns": set()
        }

def compare_extraction_results(llm_result: Dict[str, Set[str]], 
                             sqlglot_result: Dict[str, Any], debug_mode: bool = False) -> float:
    """
    比较LLM抽取结果与sqlglot解析结果的一致性
    
    Args:
        llm_result: LLM抽取的表名和字段名
        sqlglot_result: sqlglot解析的结果
        debug_mode: 调试模式开关
        
    Returns:
        一致性分数 (0.0-1.0)
    """
    try:
        # 获取配置
        config = get_llm_prompts_config()
        consistency_config = config.get("consistency_config", {})
        table_weight = consistency_config.get("table_weight", 0.6)
        column_weight = consistency_config.get("column_weight", 0.4)
        
        # 获取LLM抽取的结果
        llm_tables = llm_result.get("tables", set())
        llm_columns = llm_result.get("columns", set())
        
        # 获取提取方法信息（用于调试）
        table_extraction_method = llm_result.get("table_extraction_method", "")
        column_extraction_method = llm_result.get("column_extraction_method", "")
        table_extraction_notes = llm_result.get("table_extraction_notes", "")
        column_extraction_notes = llm_result.get("column_extraction_notes", "")
        
        # 获取sqlglot解析的结果
        sqlglot_tables = sqlglot_result.get("tables", set())
        sqlglot_columns = sqlglot_result.get("columns", set())
        
        # 计算表名一致性
        table_intersection = len(llm_tables & sqlglot_tables)
        table_union = len(llm_tables | sqlglot_tables)
        table_similarity = table_intersection / table_union if table_union > 0 else 0.0
        
        # 计算字段名一致性
        column_intersection = len(llm_columns & sqlglot_columns)
        column_union = len(llm_columns | sqlglot_columns)
        column_similarity = column_intersection / column_union if column_union > 0 else 0.0
        
        # 综合分数（表名和字段名的加权平均）
        final_score = (table_similarity * table_weight + column_similarity * column_weight)
        final_score = round(final_score, 2)
        
        # 确保分数在有效范围内
        final_score = max(0.0, min(1.0, final_score))
        
        debug_print(f"[一致性得分] {final_score:.2f} (表名:{table_similarity:.2f}, 字段:{column_similarity:.2f})", debug_mode)
        
        return final_score
        
    except Exception as e:
        debug_print(f"[LLM抽取对比] 比较失败: {e}", debug_mode)
        import traceback
        traceback.print_exc()
        return 0.0

def evaluate_control_flow_penalty(orm_code: str, generated_sql_variants: List[str], 
                                caller: str, code_meta_data: str, 
                                debug_mode: bool = False) -> float:
    """
    评估控制流合理性惩罚
    
    Args:
        orm_code: ORM代码
        generated_sql_variants: 生成的SQL变体列表
        caller: 调用者信息
        code_meta_data: 代码元数据
        debug_mode: 调试模式
        
    Returns:
        惩罚严重程度 (0.0-1.0)，0.0表示无惩罚，1.0表示最大惩罚
    """
    try:
        # 格式化SQL变体用于prompt
        variants_text = "\n".join([f"{i+1}. {sql}" for i, sql in enumerate(generated_sql_variants)])
        
        # 获取配置文件中的控制流惩罚评估提示词模板
        config = get_llm_prompts_config()
        if not config:
            debug_print(f"控制流惩罚评估失败: 配置为空", debug_mode)
            return 0.0
        
        control_flow_prompt_template = config.get("control_flow_penalty_prompt", "")
        if not control_flow_prompt_template:
            debug_print(f"[控制流惩罚] 未找到控制流惩罚评估提示词配置", debug_mode)
            return 0.0
        
        # 构建prompt
        prompt = control_flow_prompt_template.format(
            orm_code=orm_code,
            caller=caller,
            code_meta_data=code_meta_data,
            current_sql_variants=variants_text
        )
        
        # 调用LLM
        timeout = config.get('control_flow_penalty', {}).get('llm_timeout', 8)
        
        # 获取LLM配置
        llm_config = config.get("llm_config", {})
        server_name = llm_config.get("server_name", "v3")
        max_tokens = llm_config.get("max_tokens", 2048)
        temperature = llm_config.get("temperature", 0.0)
        
        # 调用LLM进行评估
        llm_manager = LLMClientManager()
        client = llm_manager.get_client(server_name)
        
        result = client.call_openai(
            prompt, 
            max_tokens=max_tokens, 
            temperature=temperature
        )
        
        # 解析结果
        result_json = json.loads(result)
        penalty_severity = result_json.get('penalty_evaluation', {}).get('penalty_severity', 0.0)
        
        debug_print(f"控制流惩罚评估: severity={penalty_severity}", debug_mode)
        return float(penalty_severity)
        
    except Exception as e:
        debug_print(f"控制流惩罚评估失败: {e}", debug_mode)
        return 0.0  # 失败时不惩罚

def compare_with_pre_extraction(pre_tables: Set[str], pre_columns: Set[str], 
                               sqlglot_result: Dict[str, Any], debug_mode: bool = False) -> float:
    """
    使用预处理抽取结果与sqlglot解析结果比较一致性
    复用现有的计算逻辑
    
    Args:
        pre_tables: 预处理阶段抽取的表名
        pre_columns: 预处理阶段抽取的字段名  
        sqlglot_result: sqlglot解析的结果
        debug_mode: 调试模式开关
        
    Returns:
        一致性分数 (0.0-1.0)
    """
    try:
        # 获取配置（复用现有逻辑）
        config = get_llm_prompts_config()
        consistency_config = config.get("consistency_config", {})
        table_weight = consistency_config.get("table_weight", 0.6)
        column_weight = consistency_config.get("column_weight", 0.4)
        
        # 获取sqlglot解析的结果
        sqlglot_tables = sqlglot_result.get("tables", set())
        sqlglot_columns = sqlglot_result.get("columns", set())
        
        # === 复用现有的计算逻辑（294-313行） ===
        # 计算表名一致性
        table_intersection = len(pre_tables & sqlglot_tables)
        table_union = len(pre_tables | sqlglot_tables)
        table_similarity = table_intersection / table_union if table_union > 0 else 0.0
        
        # 计算字段名一致性
        column_intersection = len(pre_columns & sqlglot_columns)
        column_union = len(pre_columns | sqlglot_columns)
        column_similarity = column_intersection / column_union if column_union > 0 else 0.0
        
        # 综合分数（表名和字段名的加权平均）
        final_score = (table_similarity * table_weight + column_similarity * column_weight)
        final_score = round(final_score, 2)
        
        # 确保分数在有效范围内
        final_score = max(0.0, min(1.0, final_score))
        
        debug_print(f"[预处理一致性得分] {final_score:.2f} (表名:{table_similarity:.2f}, 字段:{column_similarity:.2f})", debug_mode)
        
        return final_score
        
    except Exception as e:
        debug_print(f"[预处理一致性对比] 比较失败: {e}", debug_mode)
        return 0.0

def evaluate_llm_extraction_reward(data_source: dict, solution_str: str, 
                                 ground_truth: str, extra_info: Optional[dict] = None, debug_mode: bool = False) -> float:
    """
    LLM抽取表/字段一致性奖励函数
    
    Args:
        data_source: 数据源信息（包含ORM代码和元数据）
        solution_str: 模型响应文本（包含SQL语句）
        ground_truth: 期望的排查步骤文本（框架要求，但此处不使用）
        extra_info: 额外信息（包含ORM代码、调用者、元数据等）
        debug_mode: 调试模式开关
        
    Returns:
        一致性奖励分数 (0.0-1.0)
    """
    try:
        # 从extra_info中获取ORM相关信息
        orm_code = ""
        code_meta_data = []
        function_name = ""
        caller = ""
        
        if extra_info and isinstance(extra_info, dict):
            orm_code = extra_info.get("orm_code", "")
            code_meta_data = extra_info.get("code_meta_data", [])
            function_name = extra_info.get("function_name", "")
            caller = extra_info.get("caller", "")
        else:
            debug_print(f"[LLM抽取评估] extra_info为空，返回默认分数: 0.0", debug_mode)
            return 0.0
        
        if not orm_code:
            debug_print("[LLM抽取评估] 未找到ORM代码，得分: 0.0", debug_mode)
            return 0.0
        
        # 使用标准解析器提取SQL
        parsed = parse_model_response(solution_str)
        extracted_sqls = recursively_extract_sql(parsed)
        
        if not extracted_sqls:
            debug_print("[LLM抽取评估] 未找到SQL语句，得分: 0.0", debug_mode)
            return 0.0
        
        # 使用LLM抽取表名和字段名
        llm_result = extract_tables_and_columns_with_llm(orm_code, code_meta_data, function_name, caller, debug_mode)
        
        # 对每个SQL语句进行对比评估
        total_score = 0.0
        valid_sql_count = 0
        
        for i, sql in enumerate(extracted_sqls):
            try:
                # 检查LLM抽取结果是否有效
                llm_tables = llm_result.get("tables", set())
                llm_columns = llm_result.get("columns", set())
                table_extraction_method = llm_result.get("table_extraction_method", "")
                column_extraction_method = llm_result.get("column_extraction_method", "")
                table_extraction_notes = llm_result.get("table_extraction_notes", "")
                column_extraction_notes = llm_result.get("column_extraction_notes", "")
                
                # 检查是否有LACK INFORMATION标签
                has_lack_info = ("<LACK INFORMATION>" in table_extraction_method or 
                                "<LACK INFORMATION>" in column_extraction_method or
                                "<LACK INFORMATION>" in table_extraction_notes or
                                "<LACK INFORMATION>" in column_extraction_notes)
                
                # 检查是否为空
                is_empty = (len(llm_tables) == 0 and len(llm_columns) == 0)
                
                if has_lack_info or is_empty:
                    debug_print(f"跳过SQL (信息不足): {sql[:100]}...", debug_mode)
                    continue
                
                # 使用sqlglot解析SQL
                extractor = SQLFeatureExtractor()
                sqlglot_result = extractor.extract_tables_and_columns(sql)
                
                # 比较LLM抽取结果与sqlglot解析结果
                consistency_score = compare_extraction_results(llm_result, sqlglot_result, debug_mode)
                total_score += consistency_score
                valid_sql_count += 1
                debug_print(f"SQL: {sql[:100]}... 得分: {consistency_score:.2f}", debug_mode)
                
            except Exception as e:
                debug_print(f"SQL解析失败: {sql[:100]}... 错误: {e}", debug_mode)
                continue
        
        # 计算平均分数
        final_score = total_score / valid_sql_count if valid_sql_count > 0 else 0.0
        final_score = round(final_score, 2)
        
        # 确保分数在有效范围内
        final_score = max(0.0, min(1.0, final_score))
        
        debug_print(f"[LLM抽取评估] 最终得分: {final_score:.2f} (有效SQL: {valid_sql_count})", debug_mode)
        
        return final_score
        
    except Exception as e:
        debug_print(f"[LLM抽取评估] 评估失败: {e}", debug_mode)
        import traceback
        traceback.print_exc()
        return 0.0

# ============================= SQL有效性评估函数 =============================

def evaluate_sql_validity(sql_text: str, debug_mode: bool = False) -> float:
    """
    评估SQL语句的有效性
    
    Args:
        sql_text: 要评估的SQL语句
        debug_mode: 调试模式开关
        
    Returns:
        有效性分数 (0.0-1.0)
        - 1.0: SQL语句有效（extract函数不返回"invalid_sql"）
        - 0.0: SQL语句无效（extract函数返回"invalid_sql"）
    """
    try:
        extractor = SQLFeatureExtractor()
        fingerprint = extractor.extract(sql_text)
        
        # 如果返回"invalid_sql"，说明SQL无效
        if fingerprint == "invalid_sql":
            return 0.0
        else:
            return 1.0
            
    except Exception as e:
        debug_print(f"❌ SQL有效性评估失败: {e}", debug_mode)
        return 0.0

# === 【修改点4】新增关键词契合度评估函数 ===
def evaluate_keyword_reward_with_llm(orm_code: str, matched_keywords: List[str], 
                                    function_name: str, caller: str, 
                                    generated_sql_json: str, code_metadata: str,
                                    debug_mode: bool = False) -> Optional[float]:
    """
    使用LLM评估生成的SQL是否正确体现了特殊GORM关键词的行为特征
    
    Args:
        orm_code: 原始GORM代码
        matched_keywords: 检测到的特殊关键词列表
        function_name: 函数名称
        caller: 调用者信息
        generated_sql_json: 模型生成的SQL-JSON结果
        code_metadata: 代码元数据
        debug_mode: 调试模式开关
        
    Returns:
        关键词契合度分数 (0.0-1.0)，如果没有关键词则返回None
    """
    try:
        # 如果没有关键词，返回None（不参与梯度计算）
        if not matched_keywords:
            return None
        
        # 获取配置
        config = get_llm_prompts_config()
        
        # 从配置文件中获取关键词评估提示词模板
        keyword_evaluation_prompt_template = config.get("keyword_evaluation_prompt", "")
        if not keyword_evaluation_prompt_template:
            debug_print(f"[关键词评估] 未找到关键词评估提示词配置", debug_mode)
            return 0.0
        
        # 格式化代码元数据
        formatted_metadata = ""
        if code_metadata:
            formatted_metadata = code_metadata
        
        # 构建评估提示词
        evaluation_prompt = keyword_evaluation_prompt_template.format(
            function_name=function_name or "<未知函数>",
            caller=caller or "<未知调用者>",
            matched_keywords=", ".join(matched_keywords),
            orm_code=orm_code,
            generated_sql_json=generated_sql_json,
            code_metadata=formatted_metadata
        )
        
        # 获取LLM配置
        llm_config = config.get("llm_config", {})
        server_name = llm_config.get("server_name", "v3")
        max_tokens = llm_config.get("max_tokens", 2048)  # 增加token数量以容纳详细评估
        temperature = llm_config.get("temperature", 0.0)
        
        # 调用LLM进行评估
        llm_manager = LLMClientManager()
        client = llm_manager.get_client(server_name)
        
        debug_print(f"[关键词评估] 开始评估关键词: {matched_keywords}", debug_mode)
        
        response = client.call_openai(
            evaluation_prompt, 
            max_tokens=max_tokens, 
            temperature=temperature
        )
        
        if not response:
            debug_print(f"[关键词评估] LLM返回空响应", debug_mode)
            return 0.0
        
        # === 【修改点10】简化调试输出，只保留关键分数信息 ===
        # 解析LLM响应
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result_data = json.loads(json_str)
                
                # 获取关键词分数
                keyword_score = float(result_data.get("keyword_score", 0.0))
                keyword_score = max(0.0, min(1.0, keyword_score))  # 确保分数在有效范围内
                
                debug_print(f"[关键词评估] 关键词: {matched_keywords}, 得分: {keyword_score:.2f}", debug_mode)
                
                return keyword_score
                
            else:
                debug_print(f"[关键词评估] 无法从响应中提取JSON", debug_mode)
                return 0.0
                
        except json.JSONDecodeError as e:
            debug_print(f"[关键词评估] JSON解析失败: {e}", debug_mode)
            return 0.0
            
    except Exception as e:
        debug_print(f"[关键词评估] 评估失败: {e}", debug_mode)
        import traceback
        if debug_mode:
            traceback.print_exc()
        return 0.0

# ============================= 框架适配的主奖励函数 =============================

def format_and_llm_reward(data_source: dict, solution_str: str, ground_truth: str, extra_info: Optional[dict] = None, debug_mode: bool = False) -> float:
    """
    综合奖励函数：评估生成的SQL语句的有效性和一致性
    
    Args:
        data_source: 数据源信息（包含ORM代码和元数据）
        solution_str: 模型响应文本（包含SQL语句）
        ground_truth: 期望的排查步骤文本（框架要求，但此处不使用）
        extra_info: 额外信息（包含ORM代码、调用者、元数据等）
        debug_mode: 调试模式开关
        
    Returns:
        最终奖励分数 (0.0-1.0)
    """
    
    try:
        
        # 获取配置
        config = get_llm_prompts_config()
        consistency_config = config.get("consistency_config", {})
        validity_weight = consistency_config.get("validity_weight", 0.6)
        consistency_weight = consistency_config.get("consistency_weight", 0.4)
        
        # === 【修改点5】新增关键词权重配置 ===
        keyword_weight = consistency_config.get("keyword_weight", 0.1)
        
        # 使用标准解析器提取SQL
        parsed = parse_model_response(solution_str)
        extracted_sqls = recursively_extract_sql(parsed)
        
        if not extracted_sqls:
            debug_print("[评估] 未找到SQL语句，得分: 0.0", debug_mode)
            return 0.0
        
        # 评估SQL有效性
        validity_score = 0.0
        valid_sql_count = 0
        
        for i, sql in enumerate(extracted_sqls):
            score = evaluate_sql_validity(sql, debug_mode)
            validity_score += score
            if score > 0:
                valid_sql_count += 1
            debug_print(f"SQL: {sql[:100]}... 有效性: {score:.2f}", debug_mode)
        
        # 计算有效性平均分数
        avg_validity_score = validity_score / len(extracted_sqls) if extracted_sqls else 0.0
        
        # 使用预处理结果进行一致性评估
        if extra_info and isinstance(extra_info, dict) and extra_info.get("pre_tables") is not None:
            # 使用预处理结果进行一致性评估
            pre_tables = set(extra_info.get("pre_tables", []))
            pre_columns = set(extra_info.get("pre_columns", []))
            
            # 对每个SQL语句进行对比评估
            total_score = 0.0
            valid_sql_count = 0
            
            for i, sql in enumerate(extracted_sqls):
                try:
                    # 使用sqlglot解析SQL（复用现有逻辑）
                    extractor = SQLFeatureExtractor()
                    sqlglot_result = extractor.extract_tables_and_columns(sql)
                    
                    # 使用预处理结果比较一致性
                    consistency_score_single = compare_with_pre_extraction(pre_tables, pre_columns, sqlglot_result, debug_mode)
                    total_score += consistency_score_single
                    valid_sql_count += 1
                    debug_print(f"SQL: {sql[:100]}... 得分: {consistency_score_single:.2f}", debug_mode)
                    
                except Exception as e:
                    debug_print(f"SQL解析失败: {sql[:100]}... 错误: {e}", debug_mode)
                    continue
            
            # 计算平均分数
            consistency_score = total_score / valid_sql_count if valid_sql_count > 0 else 0.0
            consistency_score = round(consistency_score, 2)
            
            debug_print(f"[一致性评估] 最终得分: {consistency_score:.2f} (有效SQL: {valid_sql_count})", debug_mode)
        else:
            # 理论上不应该到这里，因为预处理已过滤掉无效样本
            debug_print("[一致性评估] 未找到预处理结果，得分: 0.0", debug_mode)
            consistency_score = 0.0
        
        # === 【修改点6】新增关键词契合度评估逻辑 ===
        # 评估关键词契合度
        keyword_reward = None
        if extra_info and isinstance(extra_info, dict):
            # 获取关键词分析结果
            llm_keyword_analysis = extra_info.get("llm_keyword_analysis", {})
            has_special_keywords = llm_keyword_analysis.get("has_special_keywords", False)
            matched_keywords = llm_keyword_analysis.get("matched_keywords", [])
            
            # 如果有特殊关键词，则进行关键词契合度评估
            if has_special_keywords and matched_keywords:
                # 获取必要的信息
                orm_code = extra_info.get("orm_code", "")
                function_name = extra_info.get("function_name", "")
                caller = extra_info.get("caller", "")
                
                # 格式化代码元数据
                code_meta_data = extra_info.get("code_meta_data", [])
                formatted_metadata = ""
                if code_meta_data:
                    for meta in code_meta_data:
                        if 'code_key' in meta and 'code_value' in meta:
                            formatted_metadata += f"\n**{meta['code_key']}**:\n{meta['code_value']}"
                            if 'code_file' in meta:
                                formatted_metadata += f"\n(文件: {meta['code_file']})"
                
                # 调用关键词评估函数
                keyword_reward = evaluate_keyword_reward_with_llm(
                    orm_code=orm_code,
                    matched_keywords=matched_keywords,
                    function_name=function_name,
                    caller=caller,
                    generated_sql_json=solution_str,
                    code_metadata=formatted_metadata,
                    debug_mode=debug_mode
                )
                
                debug_print(f"[关键词评估] 关键词: {matched_keywords}, 得分: {keyword_reward}", debug_mode)
        
        # === 【修改点7】修改综合分数计算，实现动态权重归一化 ===
        # 综合分数计算（动态权重归一化）
        if keyword_reward is None:
            # 没有关键词奖励，只使用有效性和一致性，需要权重归一化
            total_weight = validity_weight + consistency_weight
            final_score = (avg_validity_score * validity_weight + 
                          consistency_score * consistency_weight) / total_weight
        else:
            # 有关键词奖励，使用三个维度完整计算
            final_score = (avg_validity_score * validity_weight + 
                          consistency_score * consistency_weight + 
                          keyword_reward * keyword_weight)
        
        final_score = round(final_score, 2)
        
        # 确保分数在有效范围内
        final_score = max(0.0, min(1.0, final_score))
        
        # === 控制流惩罚评估 ===
        # 应用控制流惩罚
        config = get_llm_prompts_config()
        if config and config.get('control_flow_penalty', {}).get('enabled', False):
            penalty_severity = evaluate_control_flow_penalty(
                orm_code=extra_info.get('orm_code', '') if extra_info else '',
                generated_sql_variants=extracted_sqls,
                caller=extra_info.get('caller', '') if extra_info else '',
                code_meta_data=str(extra_info.get('code_meta_data', [])) if extra_info else '',
                debug_mode=debug_mode
            )
            penalty_cap = config['control_flow_penalty']['penalty_cap']
            penalty_amount = penalty_cap * penalty_severity
            final_score = max(final_score - penalty_amount, 0.0)
            
            debug_print(f"控制流惩罚: severity={penalty_severity}, amount={penalty_amount:.3f}, final={final_score:.3f}", debug_mode)
        
        # === 【修改点8】更新评估结果输出，包含关键词信息 ===
        # 输出评估结果
        if keyword_reward is not None:
            debug_print(f"[综合评估] 最终得分: {final_score:.2f} (有效性:{avg_validity_score:.2f}, 一致性:{consistency_score:.2f}, 关键词:{keyword_reward:.2f})", debug_mode)
        else:
            debug_print(f"[综合评估] 最终得分: {final_score:.2f} (有效性:{avg_validity_score:.2f}, 一致性:{consistency_score:.2f})", debug_mode)
        
        return final_score
        
    except Exception as e:
        debug_print(f"[错误] 综合评估失败: {e}", debug_mode)
        import traceback
        traceback.print_exc()
        return 0.0

# ============================= 批量处理函数 =============================

def compute_score(data_source, solution_str, ground_truth, extra_info, debug_mode=False):
    """
    计算单个样本的综合奖励分数
    
    Args:
        data_source: 数据源信息
        solution_str: 模型响应文本
        ground_truth: 期望的排查步骤文本
        extra_info: 额外信息
        debug_mode: 调试模式开关
        
    Returns:
        最终奖励分数 (0.0-1.0)
    """
    return format_and_llm_reward(data_source, solution_str, ground_truth, extra_info, debug_mode)

def compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos, debug_mode=False):
    """
    批量并行计算综合奖励分数
    
    Args:
        data_sources: 数据源信息列表
        solution_strs: 模型响应文本列表
        ground_truths: 期望的排查步骤文本列表
        extra_infos: 额外信息列表
        debug_mode: 调试模式开关
        
    Returns:
        每个解决方案对应的最终奖励分数列表
    """
    from concurrent.futures import ThreadPoolExecutor
    MAX_WORKERS = 32
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for data_source, solution_str, ground_truth, extra_info in zip(data_sources, solution_strs, ground_truths, extra_infos):
            future = executor.submit(compute_score, data_source, solution_str, ground_truth, extra_info, debug_mode)
            futures.append(future)

        results = [future.result() for future in futures]

    return results

# ============================= VERL框架入口函数 =============================

def code2sql_reward(data_source=None, solution_str=None, ground_truth=None, extra_info=None, 
                    data_sources=None, solution_strs=None, ground_truths=None, extra_infos=None, **kwargs):
    """
    VERL框架的Code2SQL奖励函数入口
    
    支持两种调用方式：
    1. 单个样本：code2sql_reward(data_source, solution_str, ground_truth, extra_info)
    2. 批量样本：code2sql_reward(data_sources=data_sources, solution_strs=solution_strs, ...)
    
    Args:
        data_source: 单个数据源信息（单个样本调用）
        solution_str: 单个模型响应文本（单个样本调用）
        ground_truth: 单个标准答案（单个样本调用）
        extra_info: 单个额外信息（单个样本调用）
        data_sources: 数据源信息列表（批量调用）
        solution_strs: 模型响应文本列表（批量调用）
        ground_truths: 标准答案列表（批量调用）
        extra_infos: 额外信息列表（批量调用）
        **kwargs: 其他可能的参数
        
    Returns:
        单个样本：最终奖励分数 (0.0-1.0)
        批量样本：每个解决方案对应的最终奖励分数列表
    """
    # 获取调试模式配置
    rl_config = load_rl_config()
    debug_mode = rl_config.get("debug_mode", True)
    
    # 判断是单个样本还是批量样本
    if data_sources is not None and solution_strs is not None:
        # 批量处理
        return compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos, debug_mode)
    else:
        # 单个样本处理
        if data_source is None or solution_str is None or ground_truth is None:
            debug_print("[错误] 单个样本调用时，data_source、solution_str、ground_truth参数不能为None", debug_mode)
            return 0.0
        return format_and_llm_reward(data_source, solution_str, ground_truth, extra_info, debug_mode)

# ============================= 测试函数 =============================

def test_sql_validity():
    """测试SQL有效性评估函数"""
    test_cases = [
        # 有效的SQL
        ("SELECT * FROM users WHERE id = 1", 1.0),
        ("INSERT INTO users (name, email) VALUES ('test', 'test@example.com')", 1.0),
        ("UPDATE users SET name = 'new_name' WHERE id = 1", 1.0),
        ("DELETE FROM users WHERE id = 1", 1.0),
        
        # 无效的SQL
        ("SELECT * FROM", 0.0),  # 不完整的SQL
        ("INVALID SQL STATEMENT", 0.0),  # 无效SQL
        ("SELECT * FROM users WHERE", 0.0),  # 不完整的WHERE子句
    ]
    
    debug_print("=== SQL有效性评估测试 ===", True)
    for sql, expected_score in test_cases:
        actual_score = evaluate_sql_validity(sql, True)
        status = "✅" if abs(actual_score - expected_score) < 0.01 else "❌"
        debug_print(f"{status} SQL: {sql[:50]}... | 期望: {expected_score} | 实际: {actual_score}", True)

def test_llm_extraction():
    """测试LLM抽取功能"""
    test_orm_code = """
    func GetUserInfo(ctx context.Context, db *gorm.DB, userID int) (*User, error) {
        var user User
        err := db.Where("id = ?", userID).First(&user).Error
        return &user, err
    }
    """
    
    test_meta_data = [
        {
            "code_key": "User",
            "code_value": "type User struct {\n    ID   int    `gorm:\"column:id;primary_key\"`\n    Name string `gorm:\"column:name\"`\n    Email string `gorm:\"column:email\"`\n}",
            "code_file": "models/user.go"
        }
    ]
    
    debug_print("=== LLM抽取测试 ===", True)
    result = extract_tables_and_columns_with_llm(test_orm_code, test_meta_data, "GetUserInfo", "", True)
    debug_print(f"抽取结果: {result}", True)

def test_config_loading():
    """测试配置加载功能"""
    debug_print("=== 配置加载测试 ===", True)
    config = get_llm_prompts_config()
    debug_print(f"配置加载成功，包含以下键: {list(config.keys())}", True)
    debug_print(f"表名抽取提示词长度: {len(config.get('table_extraction_prompt', ''))}", True)
    debug_print(f"字段名抽取提示词长度: {len(config.get('column_extraction_prompt', ''))}", True)

if __name__ == "__main__":
    test_config_loading()
    test_sql_validity()
    test_llm_extraction() 