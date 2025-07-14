#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
解析模型响应和基准答案的工具模块
"""

import json
from typing import Any, List, Union, Dict

def recursively_extract_sql(data: Any) -> List[str]:
    """
    递归提取任何数据结构中的SQL语句。
    
    处理以下情况：
    1. 直接的SQL字符串
    2. 包含variants的结构化JSON
    3. 列表中的SQL
    4. 字典中的SQL字段
    """
    sql_list = []
    
    if isinstance(data, str):
        # 如果是字符串且不为空，直接添加
        if data.strip() and not data.strip().startswith('[') and not data.strip().startswith('{'):
            sql_list.append(data.strip())
        else:
            # 尝试解析JSON字符串
            try:
                parsed = json.loads(data)
                sql_list.extend(recursively_extract_sql(parsed))
            except (json.JSONDecodeError, TypeError):
                pass
                
    elif isinstance(data, list):
        # 处理列表中的每个元素
        for item in data:
            sql_list.extend(recursively_extract_sql(item))
            
    elif isinstance(data, dict):
        # 处理字典中的特定字段
        if 'sql' in data and isinstance(data['sql'], str) and data['sql'].strip():
            sql_list.append(data['sql'].strip())
            
        if 'variants' in data and isinstance(data['variants'], list):
            for variant in data['variants']:
                if isinstance(variant, dict) and 'sql' in variant:
                    sql = variant['sql']
                    if isinstance(sql, str) and sql.strip():
                        sql_list.append(sql.strip())
                        
        # 递归处理字典中的所有值
        for value in data.values():
            sql_list.extend(recursively_extract_sql(value))
            
    return [sql for sql in sql_list if sql]  # 过滤掉空字符串

def parse_model_response(response: str) -> Union[List, Dict]:
    """
    解析模型的原始响应为结构化数据。
    
    Args:
        response: 模型的原始文本响应
        
    Returns:
        解析后的结构化数据（列表或字典）
    """
    # 1. 清理响应文本
    clean_response = response.strip()
    
    # 2. 尝试直接解析为JSON
    try:
        return json.loads(clean_response)
    except json.JSONDecodeError:
        pass
    
    # 3. 尝试提取JSON部分（如果响应包含其他文本）
    try:
        # 查找第一个 [ 或 { 的位置
        start = clean_response.find('[')
        if start == -1:
            start = clean_response.find('{')
        
        if start != -1:
            # 查找对应的结束括号
            stack = []
            for i, char in enumerate(clean_response[start:], start):
                if char in '[{':
                    stack.append(char)
                elif char in ']}':
                    if stack and ((stack[-1] == '[' and char == ']') or 
                                (stack[-1] == '{' and char == '}')):
                        stack.pop()
                        if not stack:  # 找到匹配的结束括号
                            json_str = clean_response[start:i+1]
                            return json.loads(json_str)
                            
    except (json.JSONDecodeError, IndexError):
        pass
    
    # 4. 如果无法解析为JSON，返回原始响应
    return [clean_response] if clean_response else [] 