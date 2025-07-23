import json
import re
import logging
from typing import Any, List, Union

logger = logging.getLogger(__name__)

__all__ = [
    "parse_model_response",
    "recursively_extract_sql",
    "validate_sql_output_format",
]


def parse_model_response(response: str) -> Union[List[Any], Any]:
    """尝试从大模型输出中提取 JSON/列表/字典等可解析结构。

    解析顺序：
    1. 直接 json.loads 整段响应。
    2. 解析 ```json ... ``` 代码块内容。
    3. 解析任意 ``` ... ``` 代码块内容（去掉围栏与语言标记）。
    4. 截取首个 '[' 或 '{' 到最后 ']' 或 '}' 的子串后解析。
    5. 尝试提取 SQL 语句（以 SELECT、INSERT、UPDATE、DELETE、CREATE、DROP 开头）。
    6. 全部失败时，返回原始字符串列表以保证后续流程不中断。
    """
    if not response or not response.strip():
        return []

    # 1) 直接解析
    try:
        parsed = json.loads(response)
        # 确保总是返回列表
        if isinstance(parsed, dict):
            return [parsed]
        return parsed
    except json.JSONDecodeError:
        pass

    # 2) 解析 ```json ... ``` 代码块
    code_blocks = re.findall(r"```json\s*([\s\S]+?)\s*```", response, flags=re.IGNORECASE)
    for block in code_blocks:
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict):
                return [parsed]
            return parsed
        except json.JSONDecodeError:
            logger.debug("无法解析 json 代码块，继续尝试其它方式。")

    # 3) 解析任意 ``` ... ``` 代码块
    generic_blocks = re.findall(r"```[\s\S]*?```", response)
    for gb in generic_blocks:
        content = re.sub(r"```[a-zA-Z0-9_]*", "", gb).rstrip("`")
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return [parsed]
            return parsed
        except json.JSONDecodeError:
            continue

    # 4) 截取首尾括号片段
    for start_sym, end_sym in (("[", "]"), ("{", "}")):
        start_idx = response.find(start_sym)
        end_idx = response.rfind(end_sym)
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            snippet = response[start_idx : end_idx + 1]
            try:
                parsed = json.loads(snippet)
                if isinstance(parsed, dict):
                    return [parsed]
                return parsed
            except json.JSONDecodeError:
                continue

    # 5) 尝试提取 SQL 语句
    sql_keywords = [
        # DML (数据操作语言)
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE',
        
        # DDL (数据定义语言)
        'CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'RENAME',
        
        # DCL (数据控制语言)
        'GRANT', 'REVOKE', 'DENY',
        
        # TCL (事务控制语言)
        'BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'SET TRANSACTION',
        
        # 其他 SQL 语句
        'USE', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN', 'ANALYZE',
        'WITH', 'WITH RECURSIVE', 'UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT',
        'CALL', 'EXECUTE', 'PREPARE', 'DEALLOCATE',
        
        # 存储过程和函数
        'PROCEDURE', 'FUNCTION', 'TRIGGER', 'EVENT',
        
        # 索引和约束
        'INDEX', 'UNIQUE', 'PRIMARY', 'FOREIGN', 'CHECK', 'DEFAULT',
        
        # 视图
        'VIEW', 'MATERIALIZED VIEW',
        
        # 其他
        'LOCK', 'UNLOCK', 'FLUSH', 'RESET', 'SET', 'SHUTDOWN'
    ]
    sql_statements = []
    
    # 按行分割，查找 SQL 语句
    lines = response.split('\n')
    for line in lines:
        line = line.strip()
        if line:
            # 检查是否以 SQL 关键字开头
            for keyword in sql_keywords:
                if line.upper().startswith(keyword):
                    sql_statements.append(line)
                    break
    
    if sql_statements:
        return sql_statements

    # 6) 尝试从文本中提取引号内的内容
    quoted_content = re.findall(r'"([^"]*)"', response)
    if quoted_content:
        return quoted_content

    # 7) 尝试提取方括号内的内容
    bracket_content = re.findall(r'\[([^\]]*)\]', response)
    if bracket_content:
        return bracket_content

    logger.warning("❌ 无法将模型响应解析为JSON，将原始文本作为单条 SQL 返回。")
    return [response.strip()]


def recursively_extract_sql(data: Any) -> List[str]:
    """递归遍历任意数据结构，提取内部所有 SQL 字符串。"""
    sql_list: List[str] = []

    if isinstance(data, str):
        if data.strip():
            # 1) 尝试将字符串解析为JSON，如果成功则递归处理其内容，避免把JSON整体当作SQL
            try:
                parsed_json = json.loads(data)
                return recursively_extract_sql(parsed_json)
            except (json.JSONDecodeError, TypeError):
                pass  # 解析失败继续按普通字符串处理

            # 检查字符串是否包含 SQL 语句
            sql_keywords = [
                # DML (数据操作语言)
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE',
                
                # DDL (数据定义语言)
                'CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'RENAME',
                
                # DCL (数据控制语言)
                'GRANT', 'REVOKE', 'DENY',
                
                # TCL (事务控制语言)
                'BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'SET TRANSACTION',
                
                # 其他 SQL 语句
                'USE', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN', 'ANALYZE',
                'WITH', 'WITH RECURSIVE', 'UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT',
                'CALL', 'EXECUTE', 'PREPARE', 'DEALLOCATE',
                
                # 存储过程和函数
                'PROCEDURE', 'FUNCTION', 'TRIGGER', 'EVENT',
                
                # 索引和约束
                'INDEX', 'UNIQUE', 'PRIMARY', 'FOREIGN', 'CHECK', 'DEFAULT',
                
                # 视图
                'VIEW', 'MATERIALIZED VIEW',
                
                # 其他
                'LOCK', 'UNLOCK', 'FLUSH', 'RESET', 'SET', 'SHUTDOWN'
            ]
            data_upper = data.upper()
            
            # 如果字符串以 SQL 关键字开头，直接添加
            if any(data_upper.startswith(keyword) for keyword in sql_keywords):
                sql_list.append(data.strip())
            # 如果字符串包含 SQL 关键字，尝试提取
            elif any(keyword in data_upper for keyword in sql_keywords):
                # 尝试从字符串中提取 SQL 语句
                lines = data.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and any(line.upper().startswith(keyword) for keyword in sql_keywords):
                        sql_list.append(line)
                # 如果没有提取到，将整个字符串作为 SQL
                if not sql_list:
                    sql_list.append(data.strip())
            else:
                # 普通字符串，直接忽略（不视为SQL），防止误判
                pass
    elif isinstance(data, list):
        for item in data:
            sql_list.extend(recursively_extract_sql(item))
    elif isinstance(data, dict):
        # param_dependent 特殊结构
        if data.get("type") == "param_dependent" and "variants" in data:
            for variant in data.get("variants", []):
                sql_list.extend(recursively_extract_sql(variant.get("sql")))
        # 其他字典若含 sql 字段
        elif "sql" in data:
            sql_list.extend(recursively_extract_sql(data["sql"]))
        else:
            for value in data.values():
                sql_list.extend(recursively_extract_sql(value))


    return sql_list


def validate_sql_output_format(sql_output: Any) -> tuple[bool, str]:
    """
    验证SQL输出格式是否符合要求
    
    Args:
        sql_output: 要验证的SQL输出（可以是列表、字典或字符串）
        
    Returns:
        tuple[bool, str]: (是否有效, 错误信息)
    """
    allowed_types = {"param_dependent", "LACK_INFORMATION", "NO_SQL_GENERATE"}
    
    def validate_item(item):
        """验证单个SQL项"""
        if isinstance(item, str):
            # 字符串类型的SQL语句是允许的
            return True, ""
        
        elif isinstance(item, dict):
            # 检查是否有type字段
            if "type" not in item:
                return False, f"缺少type字段: {item}"
            
            item_type = item.get("type")
            if item_type not in allowed_types:
                return False, f"不支持的type类型: {item_type}，只允许: {allowed_types}"
            
            # 检查是否有variants字段
            if "variants" not in item:
                return False, f"缺少variants字段: {item}"
            
            # 验证variants是列表
            if not isinstance(item["variants"], list):
                return False, f"variants必须是列表: {item}"
            
            # 验证每个variant
            for i, variant in enumerate(item["variants"]):
                if not isinstance(variant, dict):
                    return False, f"variant {i} 必须是字典: {variant}"
                
                # 检查必要的字段
                if "scenario" not in variant:
                    return False, f"variant {i} 缺少scenario字段: {variant}"
                
                if "sql" not in variant:
                    return False, f"variant {i} 缺少sql字段: {variant}"
                
                # 对于LACK_INFORMATION和NO_SQL_GENERATE，sql字段可以为空字符串
                if item_type in ["LACK_INFORMATION", "NO_SQL_GENERATE"]:
                    if not isinstance(variant["sql"], str):
                        return False, f"variant {i} 的sql字段必须是字符串: {variant}"
                else:
                    # 对于param_dependent，sql字段不能为空
                    if not variant["sql"] or not isinstance(variant["sql"], str):
                        return False, f"variant {i} 的sql字段不能为空且必须是字符串: {variant}"
            
            return True, ""
        
        else:
            return False, f"不支持的项类型: {type(item)}"
    
    # 处理输入
    if isinstance(sql_output, list):
        for i, item in enumerate(sql_output):
            is_valid, error_msg = validate_item(item)
            if not is_valid:
                return False, f"第{i}项验证失败: {error_msg}"
        return True, ""
    
    elif isinstance(sql_output, dict):
        return validate_item(sql_output)
    
    elif isinstance(sql_output, str):
        # 尝试解析为JSON
        try:
            parsed = json.loads(sql_output)
            return validate_sql_output_format(parsed)
        except json.JSONDecodeError:
            # 如果无法解析为JSON，检查是否为纯SQL字符串
            if sql_output.strip():
                return True, ""
            else:
                return False, "空字符串"
    
    else:
        return False, f"不支持的输出类型: {type(sql_output)}" 