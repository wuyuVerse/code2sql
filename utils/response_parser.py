import json
import re
import logging
from typing import Any, List, Union

logger = logging.getLogger(__name__)

__all__ = [
    "parse_model_response",
    "recursively_extract_sql",
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
                # 普通字符串，直接添加
                sql_list.append(data.strip())
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