#!/usr/bin/env python3
"""
数据格式转换脚本
将 urs_results_723.json 格式转换为 IVC__ivc-urs_results.json 格式
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path


def extract_function_name(code_key: str) -> str:
    """从code_key中提取函数名"""
    if ":" in code_key:
        return code_key.split(":")[-1]
    return code_key


def extract_orm_code(code_value: str) -> str:
    """提取ORM代码"""
    return code_value


def extract_sql_statements(entry_data: Dict) -> List[str]:
    """从条目数据中提取SQL语句"""
    sql_statements = []
    
    # 检查是否有sql_statement_list字段
    if "sql_statement_list" in entry_data:
        sql_list = entry_data["sql_statement_list"]
        for sql_item in sql_list:
            if isinstance(sql_item, dict) and "variants" in sql_item:
                # 处理复杂格式的SQL语句
                for variant in sql_item["variants"]:
                    if "sql" in variant:
                        sql_statements.append(variant["sql"])
            elif isinstance(sql_item, str):
                # 直接是字符串格式的SQL语句
                sql_statements.append(sql_item)
    
    return sql_statements


def extract_sql_types(sql_statements: List[str]) -> List[str]:
    """从SQL语句中提取SQL类型"""
    sql_types = []
    for sql in sql_statements:
        if sql.strip().upper().startswith("SELECT"):
            sql_types.append("SELECT")
        elif sql.strip().upper().startswith("INSERT"):
            sql_types.append("INSERT")
        elif sql.strip().upper().startswith("UPDATE"):
            sql_types.append("UPDATE")
        elif sql.strip().upper().startswith("DELETE"):
            sql_types.append("DELETE")
        else:
            sql_types.append("OTHER")
    return sql_types


def build_code_meta_data(entry: Dict, callers: List[Dict]) -> List[Dict]:
    """构建代码元数据"""
    meta_data = []
    
    # 添加主函数的元数据
    if "code_file" in entry:
        meta_data.append({
            "code_file": entry["code_file"],
            "code_start_line": entry["code_start_line"],
            "code_end_line": entry["code_end_line"],
            "code_key": entry["code_key"],
            "code_value": entry["code_value"],
            "code_label": entry.get("code_label"),
            "code_type": entry.get("code_type"),
            "code_version": entry.get("code_version")
        })
    
    # 添加调用者的元数据
    for caller in callers:
        meta_data.append({
            "code_file": caller["code_file"],
            "code_start_line": caller["code_start_line"],
            "code_end_line": caller["code_end_line"],
            "code_key": caller["code_key"],
            "code_value": caller["code_value"],
            "code_label": caller.get("code_label"),
            "code_type": caller.get("code_type"),
            "code_version": caller.get("code_version")
        })
    
    return meta_data


def convert_entry(entry_key: str, entry_data: Dict) -> Dict:
    """转换单个条目"""
    function_name = extract_function_name(entry_data["code_key"])
    orm_code = extract_orm_code(entry_data["code_value"])
    
    # 提取调用者信息
    callers = entry_data.get("callers", [])
    caller_info = ""
    # 根据目标格式，caller字段保持为空字符串
    
    # 提取SQL语句
    sql_statements = extract_sql_statements(entry_data)
    sql_types = extract_sql_types(sql_statements)
    
    # 构建代码元数据
    code_meta_data = build_code_meta_data(entry_data, callers)
    
    return {
        "function_name": function_name,
        "orm_code": orm_code,
        "caller": caller_info,
        "sql_statement_list": sql_statements,
        "sql_types": sql_types,
        "code_meta_data": code_meta_data,
        "sql_pattern_cnt": entry_data.get("sql_pattern_cnt", 0),
        "source_file": entry_data.get("code_file", "")
    }


def convert_data_format(source_file: str, output_file: str):
    """转换数据格式"""
    print(f"正在读取源文件: {source_file}")
    
    with open(source_file, 'r', encoding='utf-8') as f:
        source_data = json.load(f)
    
    print(f"源数据包含 {len(source_data)} 个条目")
    
    converted_data = []
    
    for entry_key, entry_data in source_data.items():
        try:
            converted_entry = convert_entry(entry_key, entry_data)
            converted_data.append(converted_entry)
        except Exception as e:
            print(f"转换条目 {entry_key} 时出错: {e}")
            continue
    
    print(f"成功转换 {len(converted_data)} 个条目")
    
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=2)
    
    print(f"转换完成，输出文件: {output_file}")


def main():
    """主函数"""
    if len(sys.argv) != 3:
        print("用法: python convert_data_format.py <源文件> <输出文件>")
        print("示例: python convert_data_format.py datasets/urs_results_723.json datasets/test_data/converted_results.json")
        sys.exit(1)
    
    source_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(source_file):
        print(f"错误: 源文件 {source_file} 不存在")
        sys.exit(1)
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    convert_data_format(source_file, output_file)


if __name__ == "__main__":
    main() 