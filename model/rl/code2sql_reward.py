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
        print(f"[配置] 成功加载LLM提示词配置: {config_path}")
        return config
    except Exception as e:
        print(f"[配置] 加载LLM提示词配置失败: {e}")
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
                                       function_name: str = "", caller: str = "") -> Dict[str, Set[str]]:
    """
    使用LLM从代码和元信息中抽取表名和字段名
    
    Args:
        orm_code: ORM代码
        code_meta_data: 代码元数据
        function_name: 函数名称
        caller: 调用者信息
        
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
        print(f"[LLM抽取] 开始调用LLM抽取表名，使用服务器: {server_name}")
        table_response = client.call_openai(table_extraction_prompt, max_tokens=max_tokens, temperature=temperature)
        print(f"[LLM抽取] 表名抽取原始响应: {repr(table_response)}")
        
        # 调用LLM抽取字段名
        print(f"[LLM抽取] 开始调用LLM抽取字段名，使用服务器: {server_name}")
        column_response = client.call_openai(column_extraction_prompt, max_tokens=max_tokens, temperature=temperature)
        print(f"[LLM抽取] 字段名抽取原始响应: {repr(column_response)}")
        
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
                    print(f"[LLM抽取] 表名JSON字符串: {repr(json_str)}")
                    table_data = json.loads(json_str)
                    tables = set(table_data.get("tables", []))
                    extraction_method = table_data.get("extraction_method", "")
                    extraction_notes = table_data.get("notes", "")
                    print(f"[LLM抽取] 解析到的表名: {tables}")
                    print(f"[LLM抽取] 提取方法: {extraction_method}")
                    print(f"[LLM抽取] 提取说明: {extraction_notes}")
                else:
                    print(f"[LLM抽取] 未找到表名JSON格式，原始响应: {repr(table_response)}")
                    # 尝试使用增强的解析器
                    parsed_response = parse_model_response(table_response)
                    if parsed_response:
                        print(f"[LLM抽取] 使用增强解析器解析表名: {parsed_response}")
                        # 如果解析出的是列表，尝试提取表名
                        if isinstance(parsed_response, list):
                            for item in parsed_response:
                                if isinstance(item, str) and item.strip():
                                    tables.add(item.strip())
            except Exception as e:
                print(f"[LLM抽取] 解析表名结果失败: {e}")
                print(f"[LLM抽取] 表名响应内容: {repr(table_response)}")
                # 尝试使用增强的解析器作为备选
                try:
                    parsed_response = parse_model_response(table_response)
                    if parsed_response:
                        print(f"[LLM抽取] 备选解析器解析表名: {parsed_response}")
                        if isinstance(parsed_response, list):
                            for item in parsed_response:
                                if isinstance(item, str) and item.strip():
                                    tables.add(item.strip())
                except Exception as backup_e:
                    print(f"[LLM抽取] 备选解析也失败: {backup_e}")
        
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
                    print(f"[LLM抽取] 字段名JSON字符串: {repr(json_str)}")
                    column_data = json.loads(json_str)
                    columns = set(column_data.get("columns", []))
                    column_extraction_method = column_data.get("extraction_method", "")
                    column_extraction_notes = column_data.get("notes", "")
                    print(f"[LLM抽取] 解析到的字段名: {columns}")
                    print(f"[LLM抽取] 字段提取方法: {column_extraction_method}")
                    print(f"[LLM抽取] 字段提取说明: {column_extraction_notes}")
                else:
                    print(f"[LLM抽取] 未找到字段名JSON格式，原始响应: {repr(column_response)}")
                    # 尝试使用增强的解析器
                    parsed_response = parse_model_response(column_response)
                    if parsed_response:
                        print(f"[LLM抽取] 使用增强解析器解析字段名: {parsed_response}")
                        # 如果解析出的是列表，尝试提取字段名
                        if isinstance(parsed_response, list):
                            for item in parsed_response:
                                if isinstance(item, str) and item.strip():
                                    columns.add(item.strip())
            except Exception as e:
                print(f"[LLM抽取] 解析字段名结果失败: {e}")
                print(f"[LLM抽取] 字段名响应内容: {repr(column_response)}")
                # 尝试使用增强的解析器作为备选
                try:
                    parsed_response = parse_model_response(column_response)
                    if parsed_response:
                        print(f"[LLM抽取] 备选解析器解析字段名: {parsed_response}")
                        if isinstance(parsed_response, list):
                            for item in parsed_response:
                                if isinstance(item, str) and item.strip():
                                    columns.add(item.strip())
                except Exception as backup_e:
                    print(f"[LLM抽取] 备选解析也失败: {backup_e}")
        
        result = {
            "tables": tables,
            "columns": columns,
            "table_extraction_method": extraction_method,
            "column_extraction_method": column_extraction_method,
            "table_extraction_notes": extraction_notes,
            "column_extraction_notes": column_extraction_notes
        }
        print(f"[LLM抽取] 最终抽取结果: {result}")
        return result
        
    except Exception as e:
        print(f"[LLM抽取] LLM调用失败: {e}")
        return {
            "tables": set(),
            "columns": set()
        }

def compare_extraction_results(llm_result: Dict[str, Set[str]], 
                             sqlglot_result: Dict[str, Any]) -> float:
    """
    比较LLM抽取结果与sqlglot解析结果的一致性
    
    Args:
        llm_result: LLM抽取的表名和字段名
        sqlglot_result: sqlglot解析的结果
        
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
        
        # 打印详细的对比信息
        print(f"[LLM抽取对比] 详细对比信息:")
        print(f"  - LLM表名: {llm_tables}")
        print(f"  - LLM字段名: {llm_columns}")
        print(f"  - sqlglot表名: {sqlglot_tables}")
        print(f"  - sqlglot字段名: {sqlglot_columns}")
        print(f"  - 表名提取方法: {table_extraction_method}")
        print(f"  - 字段名提取方法: {column_extraction_method}")
        if table_extraction_notes:
            print(f"  - 表名提取说明: {table_extraction_notes}")
        if column_extraction_notes:
            print(f"  - 字段名提取说明: {column_extraction_notes}")
        
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
        
        print(f"[LLM抽取对比] 一致性计算结果:")
        print(f"  - 表名交集: {table_intersection} | 表名并集: {table_union} | 表名一致性: {table_similarity:.2%}")
        print(f"  - 字段名交集: {column_intersection} | 字段名并集: {column_union} | 字段名一致性: {column_similarity:.2%}")
        print(f"  - 表名权重: {table_weight} | 字段名权重: {column_weight}")
        print(f"  - 综合分数: {final_score}")
        
        return final_score
        
    except Exception as e:
        print(f"[LLM抽取对比] 比较失败: {e}")
        import traceback
        traceback.print_exc()
        return 0.0

def evaluate_llm_extraction_reward(data_source: dict, solution_str: str, 
                                 ground_truth: str, extra_info: Optional[dict] = None) -> float:
    """
    LLM抽取表/字段一致性奖励函数
    
    Args:
        data_source: 数据源信息（包含ORM代码和元数据）
        solution_str: 模型响应文本（包含SQL语句）
        ground_truth: 期望的排查步骤文本（框架要求，但此处不使用）
        extra_info: 额外信息（可选）
        
    Returns:
        一致性奖励分数 (0.0-1.0)
    """
    try:
        # 添加调试信息
        print(f"[LLM抽取评估] data_source类型: {type(data_source)}")
        print(f"[LLM抽取评估] data_source内容: {repr(data_source)}")
        
        # 处理data_source为字符串的情况
        if isinstance(data_source, str):
            print(f"[LLM抽取评估] data_source是字符串类型，尝试解析字符串内容")
            # 如果data_source是字符串，尝试从extra_info中获取ORM代码
            orm_code = ""
            code_meta_data = []
            function_name = ""
            caller = ""
            
            if extra_info and isinstance(extra_info, dict):
                orm_code = extra_info.get("orm_code", "")
                code_meta_data = extra_info.get("code_meta_data", [])
                function_name = extra_info.get("function_name", "")
                caller = extra_info.get("caller", "")
                print(f"[LLM抽取评估] 从extra_info中提取信息:")
                print(f"  - orm_code长度: {len(orm_code)}")
                print(f"  - code_meta_data类型: {type(code_meta_data)}, 长度: {len(code_meta_data)}")
                print(f"  - function_name: {function_name}")
                print(f"  - caller: {caller}")
            
            if not orm_code:
                print(f"[LLM抽取评估] 无法从extra_info中获取ORM代码，尝试从data_source字符串中解析")
                # 尝试将data_source字符串作为ORM代码使用
                orm_code = data_source
                print(f"[LLM抽取评估] 使用data_source字符串作为ORM代码，长度: {len(orm_code)}")
        elif isinstance(data_source, dict):
            # 从data_source中提取源信息
            orm_code = data_source.get("orm_code", "")
            code_meta_data = data_source.get("code_meta_data", [])
            function_name = data_source.get("function_name", "")
            caller = data_source.get("caller", "")
            
            print(f"[LLM抽取评估] 从data_source字典中提取信息:")
            print(f"  - orm_code长度: {len(orm_code)}")
            print(f"  - code_meta_data类型: {type(code_meta_data)}, 长度: {len(code_meta_data)}")
            print(f"  - function_name: {function_name}")
            print(f"  - caller: {caller}")
        else:
            print(f"[LLM抽取评估] data_source类型不支持: {type(data_source)}，无法进行LLM抽取评估，返回默认分数: 0.0")
            return 0.0
        
        if not orm_code:
            print("[LLM抽取评估] 未找到ORM代码，得分: 0.0")
            return 0.0
        
        # 使用标准解析器提取SQL
        parsed = parse_model_response(solution_str)
        extracted_sqls = recursively_extract_sql(parsed)
        
        print(f"[LLM抽取评估] 提取到的SQL数量: {len(extracted_sqls)}")
        for i, sql in enumerate(extracted_sqls):
            print(f"  - SQL {i+1}: {repr(sql)}")
        
        if not extracted_sqls:
            print("[LLM抽取评估] 未找到SQL语句，得分: 0.0")
            return 0.0
        
        # 使用LLM抽取表名和字段名
        llm_result = extract_tables_and_columns_with_llm(orm_code, code_meta_data, function_name, caller)
        
        # 对每个SQL语句进行对比评估
        total_score = 0.0
        valid_sql_count = 0
        
        for i, sql in enumerate(extracted_sqls):
            try:
                print(f"[LLM抽取评估] 处理SQL {i+1}: {repr(sql)}")
                # 使用sqlglot解析SQL
                extractor = SQLFeatureExtractor()
                sqlglot_result = extractor.extract_tables_and_columns(sql)
                print(f"[LLM抽取评估] sqlglot解析结果: {sqlglot_result}")
                
                # 比较LLM抽取结果与sqlglot解析结果
                consistency_score = compare_extraction_results(llm_result, sqlglot_result)
                total_score += consistency_score
                valid_sql_count += 1
                print(f"[LLM抽取评估] SQL {i+1} 一致性得分: {consistency_score}")
                
            except Exception as e:
                print(f"[LLM抽取评估] SQL {i+1} 解析失败: {e}")
                continue
        
        # 计算平均分数
        final_score = total_score / valid_sql_count if valid_sql_count > 0 else 0.0
        final_score = round(final_score, 2)
        
        # 确保分数在有效范围内
        final_score = max(0.0, min(1.0, final_score))
        
        print(f"[LLM抽取评估] 一致性得分: {final_score} | 有效SQL数: {valid_sql_count}")
        
        return final_score
        
    except Exception as e:
        print(f"[LLM抽取评估] 评估失败: {e}")
        import traceback
        traceback.print_exc()
        return 0.0

# ============================= SQL有效性评估函数 =============================

def evaluate_sql_validity(sql_text: str) -> float:
    """
    评估SQL语句的有效性
    
    Args:
        sql_text: 要评估的SQL语句
        
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
        print(f"❌ SQL有效性评估失败: {e}")
        return 0.0

# ============================= 框架适配的主奖励函数 =============================

def format_and_llm_reward(data_source: dict, solution_str: str, ground_truth: str, extra_info: Optional[dict] = None) -> float:
    """
    综合奖励函数：评估生成的SQL语句的有效性和一致性
    
    Args:
        data_source: 数据源信息（包含ORM代码和元数据）
        solution_str: 模型响应文本（包含SQL语句）
        ground_truth: 期望的排查步骤文本（框架要求，但此处不使用）
        extra_info: 额外信息（可选）
        
    Returns:
        最终奖励分数 (0.0-1.0)
    """
    
    try:
        # 添加调试信息
        print(f"[综合评估] 输入参数:")
        print(f"  - data_source类型: {type(data_source)}")
        print(f"  - solution_str类型: {type(solution_str)}, 长度: {len(solution_str) if solution_str else 0}")
        print(f"  - ground_truth类型: {type(ground_truth)}")
        print(f"  - extra_info类型: {type(extra_info)}")
        
        if solution_str:
            print(f"  - solution_str内容: {repr(solution_str[:200])}...")
        
        # 获取配置
        config = get_llm_prompts_config()
        consistency_config = config.get("consistency_config", {})
        validity_weight = consistency_config.get("validity_weight", 0.6)
        consistency_weight = consistency_config.get("consistency_weight", 0.4)
        
        # 使用标准解析器提取SQL
        parsed = parse_model_response(solution_str)
        extracted_sqls = recursively_extract_sql(parsed)
        
        print(f"[综合评估] 提取到的SQL数量: {len(extracted_sqls)}")
        for i, sql in enumerate(extracted_sqls):
            print(f"  - SQL {i+1}: {repr(sql)}")
        
        if not extracted_sqls:
            print("[评估] 未找到SQL语句，得分: 0.0")
            return 0.0
        
        # 评估SQL有效性
        validity_score = 0.0
        valid_sql_count = 0
        
        for i, sql in enumerate(extracted_sqls):
            score = evaluate_sql_validity(sql)
            validity_score += score
            if score > 0:
                valid_sql_count += 1
            print(f"[综合评估] SQL {i+1} 有效性得分: {score}")
        
        # 计算有效性平均分数
        avg_validity_score = validity_score / len(extracted_sqls) if extracted_sqls else 0.0
        
        # 检查data_source是否为字典类型，决定是否进行LLM抽取评估
        if isinstance(data_source, dict) or isinstance(data_source, str):
            # 进行LLM抽取一致性评估（支持字典和字符串类型）
            consistency_score = evaluate_llm_extraction_reward(data_source, solution_str, ground_truth, extra_info)
        else:
            # data_source类型不支持，跳过LLM抽取评估
            print(f"[综合评估] data_source类型不支持: {type(data_source)}，跳过LLM抽取评估，一致性得分设为0.0")
            consistency_score = 0.0
        
        # 综合分数（有效性 + 一致性）
        final_score = avg_validity_score * validity_weight + consistency_score * consistency_weight
        final_score = round(final_score, 2)
        
        # 确保分数在有效范围内
        final_score = max(0.0, min(1.0, final_score))
        
        # 输出评估结果
        print(f"[评估] 综合得分: {final_score} | 有效性: {avg_validity_score:.2f} | 一致性: {consistency_score:.2f} | 总SQL数: {len(extracted_sqls)} | 有效SQL数: {valid_sql_count}")
        
        return final_score
        
    except Exception as e:
        print(f"[错误] 综合评估失败: {e}")
        import traceback
        traceback.print_exc()
        return 0.0

# ============================= 批量处理函数 =============================

def compute_score(data_source, solution_str, ground_truth, extra_info):
    """
    计算单个样本的综合奖励分数
    
    Args:
        data_source: 数据源信息
        solution_str: 模型响应文本
        ground_truth: 期望的排查步骤文本
        extra_info: 额外信息
        
    Returns:
        最终奖励分数 (0.0-1.0)
    """
    return format_and_llm_reward(data_source, solution_str, ground_truth, extra_info)

def compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos):
    """
    批量并行计算综合奖励分数
    
    Args:
        data_sources: 数据源信息列表
        solution_strs: 模型响应文本列表
        ground_truths: 期望的排查步骤文本列表
        extra_infos: 额外信息列表
        
    Returns:
        每个解决方案对应的最终奖励分数列表
    """
    from concurrent.futures import ThreadPoolExecutor
    MAX_WORKERS = 32
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for data_source, solution_str, ground_truth, extra_info in zip(data_sources, solution_strs, ground_truths, extra_infos):
            future = executor.submit(compute_score, data_source, solution_str, ground_truth, extra_info)
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
    # 判断是单个样本还是批量样本
    if data_sources is not None and solution_strs is not None:
        # 批量处理
        return compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos)
    else:
        # 单个样本处理
        if data_source is None or solution_str is None or ground_truth is None:
            print("[错误] 单个样本调用时，data_source、solution_str、ground_truth参数不能为None")
            return 0.0
        return format_and_llm_reward(data_source, solution_str, ground_truth, extra_info)

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
    
    print("=== SQL有效性评估测试 ===")
    for sql, expected_score in test_cases:
        actual_score = evaluate_sql_validity(sql)
        status = "✅" if abs(actual_score - expected_score) < 0.01 else "❌"
        print(f"{status} SQL: {sql[:50]}... | 期望: {expected_score} | 实际: {actual_score}")

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
    
    print("=== LLM抽取测试 ===")
    result = extract_tables_and_columns_with_llm(test_orm_code, test_meta_data, "GetUserInfo", "")
    print(f"抽取结果: {result}")

def test_config_loading():
    """测试配置加载功能"""
    print("=== 配置加载测试 ===")
    config = get_llm_prompts_config()
    print(f"配置加载成功，包含以下键: {list(config.keys())}")
    print(f"表名抽取提示词长度: {len(config.get('table_extraction_prompt', ''))}")
    print(f"字段名抽取提示词长度: {len(config.get('column_extraction_prompt', ''))}")

if __name__ == "__main__":
    test_config_loading()
    test_sql_validity()
    test_llm_extraction() 