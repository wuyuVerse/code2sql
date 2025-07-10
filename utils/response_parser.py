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
    5. 全部失败时，返回原始字符串列表以保证后续流程不中断。
    """
    if not response or not response.strip():
        return []

    # 1) 直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 2) 解析 ```json ... ``` 代码块
    code_blocks = re.findall(r"```json\s*([\s\S]+?)\s*```", response, flags=re.IGNORECASE)
    for block in code_blocks:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            logger.debug("无法解析 json 代码块，继续尝试其它方式。")

    # 3) 解析任意 ``` ... ``` 代码块
    generic_blocks = re.findall(r"```[\s\S]*?```", response)
    for gb in generic_blocks:
        content = re.sub(r"```[a-zA-Z0-9_]*", "", gb).rstrip("`")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            continue

    # 4) 截取首尾括号片段
    for start_sym, end_sym in (("[", "]"), ("{", "}")):
        start_idx = response.find(start_sym)
        end_idx = response.rfind(end_sym)
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            snippet = response[start_idx : end_idx + 1]
            try:
                parsed_data = json.loads(snippet)
                # 确保总是返回列表
                if isinstance(parsed_data, dict):
                    return [parsed_data]
                return parsed_data
            except json.JSONDecodeError:
                continue

    logger.warning("❌ 无法将模型响应解析为JSON，将原始文本作为单条 SQL 返回。")
    return [response.strip()]


def recursively_extract_sql(data: Any) -> List[str]:
    """递归遍历任意数据结构，提取内部所有 SQL 字符串。"""
    sql_list: List[str] = []

    if isinstance(data, str):
        if data.strip():
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