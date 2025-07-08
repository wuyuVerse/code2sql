#!/usr/bin/env python3
"""
测试复杂SQL结构的修复逻辑
验证param_dependent、嵌套列表、边界情况等的处理
"""

import json
import logging
from typing import Dict, List, Any, Optional

# 模拟修复逻辑（简化版）
class SQLFixTester:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def _process_string_sql(self, sql_string: str, remove_set: set, add_list: List) -> Any:
        """处理单个SQL字符串"""
        if sql_string == '<NO SQL GENERATE>':
            return add_list if add_list else '<NO SQL GENERATE>'
        
        clean_sql = sql_string.replace(' <REDUNDANT SQL>', '').strip()
        if clean_sql in remove_set:
            return add_list if add_list else '<NO SQL GENERATE>'
        else:
            if add_list:
                result = [clean_sql] if clean_sql else []
                result.extend(add_list)
                return result if len(result) > 1 else (result[0] if result else '<NO SQL GENERATE>')
            else:
                return clean_sql if clean_sql else '<NO SQL GENERATE>'
    
    def _process_list_sql(self, sql_list: List, remove_set: set, add_list: List) -> Any:
        """处理SQL列表"""
        cleaned = []
        
        for item in sql_list:
            if isinstance(item, str):
                clean_sql = item.replace(' <REDUNDANT SQL>', '').strip()
                if clean_sql and clean_sql not in remove_set:
                    cleaned.append(clean_sql)
            elif isinstance(item, dict):
                processed_item = self._process_dict_sql(item, remove_set, [])
                if processed_item is not None:
                    cleaned.append(processed_item)
            elif isinstance(item, list):
                processed_nested = self._process_list_sql(item, remove_set, [])
                if processed_nested != '<NO SQL GENERATE>' and processed_nested:
                    cleaned.append(processed_nested)
            else:
                cleaned.append(item)
        
        cleaned.extend(add_list)
        return cleaned if cleaned else '<NO SQL GENERATE>'
    
    def _process_dict_sql(self, sql_dict: Dict, remove_set: set, add_list: List) -> Any:
        """处理字典类型的SQL"""
        if sql_dict.get("type") == "param_dependent":
            return self._process_param_dependent_sql(sql_dict, remove_set, add_list)
        else:
            if 'sql' in sql_dict:
                sql_content = sql_dict['sql']
                processed_dict = sql_dict.copy()
                
                if isinstance(sql_content, str):
                    clean_sql = sql_content.replace(' <REDUNDANT SQL>', '').strip()
                    if clean_sql not in remove_set:
                        processed_dict['sql'] = clean_sql
                        return processed_dict
                elif isinstance(sql_content, list):
                    processed_sql_list = self._process_list_sql(sql_content, remove_set, [])
                    if processed_sql_list != '<NO SQL GENERATE>' and processed_sql_list:
                        processed_dict['sql'] = processed_sql_list
                        return processed_dict
            
            important_fields = ['scenario', 'description', 'condition', 'when']
            if any(field in sql_dict for field in important_fields):
                return sql_dict
            
            return None
    
    def _process_param_dependent_sql(self, param_dependent_item: Dict, remove_set: set, add_list: Optional[List] = None) -> Any:
        """处理param_dependent类型的SQL项"""
        if not isinstance(param_dependent_item, dict) or param_dependent_item.get("type") != "param_dependent":
            return param_dependent_item
        
        cleaned_item = param_dependent_item.copy()
        cleaned_variants = []
        
        variants = param_dependent_item.get("variants", [])
        for variant in variants:
            if isinstance(variant, dict) and "sql" in variant:
                variant_sql = variant["sql"]
                cleaned_variant = variant.copy()
                
                if isinstance(variant_sql, str):
                    clean_sql = variant_sql.replace(' <REDUNDANT SQL>', '').strip()
                    if clean_sql not in remove_set:
                        cleaned_variant["sql"] = clean_sql
                        cleaned_variants.append(cleaned_variant)
                elif isinstance(variant_sql, list):
                    cleaned_sql_list = []
                    for sql in variant_sql:
                        if isinstance(sql, str):
                            clean_sql = sql.replace(' <REDUNDANT SQL>', '').strip()
                            if clean_sql and clean_sql not in remove_set:
                                cleaned_sql_list.append(clean_sql)
                    
                    if cleaned_sql_list:
                        cleaned_variant["sql"] = cleaned_sql_list
                        cleaned_variants.append(cleaned_variant)
                else:
                    cleaned_variants.append(cleaned_variant)
            else:
                cleaned_variants.append(variant)
        
        # 添加缺失的SQL变体
        if add_list is not None:
            for add_item in add_list:
                if isinstance(add_item, str):
                    new_variant = {
                        "scenario": "补充的必要SQL",
                        "sql": add_item
                    }
                    cleaned_variants.append(new_variant)
                elif isinstance(add_item, dict) and add_item.get("type") == "param_dependent":
                    for variant in add_item.get("variants", []):
                        cleaned_variants.append(variant)
                elif isinstance(add_item, dict) and "sql" in add_item:
                    cleaned_variants.append(add_item)
        
        if cleaned_variants:
            cleaned_item["variants"] = cleaned_variants
            return cleaned_item
        else:
            return None

def test_complex_sql_structures():
    """测试复杂SQL结构的处理"""
    tester = SQLFixTester()
    
    # 测试用例
    test_cases = [
        {
            "name": "简单字符串SQL - 删除",
            "input": "SELECT * FROM users <REDUNDANT SQL>",
            "remove_set": {"SELECT * FROM users"},
            "add_list": [],
            "expected": "<NO SQL GENERATE>"
        },
        {
            "name": "简单字符串SQL - 保留并添加",
            "input": "SELECT * FROM users",
            "remove_set": {"SELECT * FROM orders"},
            "add_list": ["INSERT INTO logs VALUES (?)"],
            "expected": ["SELECT * FROM users", "INSERT INTO logs VALUES (?)"]
        },
        {
            "name": "param_dependent - 部分删除",
            "input": {
                "type": "param_dependent",
                "variants": [
                    {"scenario": "场景1", "sql": "SELECT * FROM users <REDUNDANT SQL>"},
                    {"scenario": "场景2", "sql": "SELECT * FROM orders"}
                ]
            },
            "remove_set": {"SELECT * FROM users"},
            "add_list": [],
            "expected": {
                "type": "param_dependent",
                "variants": [
                    {"scenario": "场景2", "sql": "SELECT * FROM orders"}
                ]
            }
        },
        {
            "name": "param_dependent - 全部删除",
            "input": {
                "type": "param_dependent",
                "variants": [
                    {"scenario": "场景1", "sql": "SELECT * FROM users"},
                    {"scenario": "场景2", "sql": "SELECT * FROM orders"}
                ]
            },
            "remove_set": {"SELECT * FROM users", "SELECT * FROM orders"},
            "add_list": [],
            "expected": None
        },
        {
            "name": "param_dependent - 添加缺失SQL",
            "input": {
                "type": "param_dependent",
                "variants": [
                    {"scenario": "场景1", "sql": "SELECT * FROM users"}
                ]
            },
            "remove_set": set(),
            "add_list": ["INSERT INTO audit_log VALUES (?)"],
            "expected": {
                "type": "param_dependent",
                "variants": [
                    {"scenario": "场景1", "sql": "SELECT * FROM users"},
                    {"scenario": "补充的必要SQL", "sql": "INSERT INTO audit_log VALUES (?)"}
                ]
            }
        },
        {
            "name": "SQL列表 - 混合处理",
            "input": [
                "SELECT * FROM users <REDUNDANT SQL>",
                "SELECT * FROM orders",
                {
                    "type": "param_dependent",
                    "variants": [
                        {"scenario": "场景1", "sql": "UPDATE users SET status = ?"}
                    ]
                }
            ],
            "remove_set": {"SELECT * FROM users"},
            "add_list": ["DELETE FROM temp_table"],
            "expected": [
                "SELECT * FROM orders",
                {
                    "type": "param_dependent",
                    "variants": [
                        {"scenario": "场景1", "sql": "UPDATE users SET status = ?"}
                    ]
                },
                "DELETE FROM temp_table"
            ]
        },
        {
            "name": "嵌套列表",
            "input": [
                ["SELECT * FROM users", "SELECT * FROM orders <REDUNDANT SQL>"],
                "INSERT INTO logs VALUES (?)"
            ],
            "remove_set": {"SELECT * FROM orders"},
            "add_list": [],
            "expected": [
                ["SELECT * FROM users"],
                "INSERT INTO logs VALUES (?)"
            ]
        },
        {
            "name": "空输入处理",
            "input": "<NO SQL GENERATE>",
            "remove_set": set(),
            "add_list": ["SELECT 1"],
            "expected": ["SELECT 1"]
        }
    ]
    
    print("开始测试复杂SQL结构处理...")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test_case['name']}")
        print(f"输入: {json.dumps(test_case['input'], ensure_ascii=False, indent=2)}")
        print(f"删除集合: {test_case['remove_set']}")
        print(f"添加列表: {test_case['add_list']}")
        
        try:
            if isinstance(test_case['input'], str):
                result = tester._process_string_sql(
                    test_case['input'], 
                    test_case['remove_set'], 
                    test_case['add_list']
                )
            elif isinstance(test_case['input'], list):
                result = tester._process_list_sql(
                    test_case['input'], 
                    test_case['remove_set'], 
                    test_case['add_list']
                )
            elif isinstance(test_case['input'], dict):
                result = tester._process_dict_sql(
                    test_case['input'], 
                    test_case['remove_set'], 
                    test_case['add_list']
                )
            else:
                result = test_case['input']
            
            print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
            print(f"期望: {json.dumps(test_case['expected'], ensure_ascii=False, indent=2)}")
            
            # 简单的结果比较
            if result == test_case['expected']:
                print("✅ 测试通过")
            else:
                print("❌ 测试失败")
                print("详细比较:")
                print(f"  实际类型: {type(result)}")
                print(f"  期望类型: {type(test_case['expected'])}")
        
        except Exception as e:
            print(f"❌ 测试异常: {e}")
        
        print("-" * 40)
    
    print("\n测试完成!")

if __name__ == "__main__":
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)
    
    # 运行测试
    test_complex_sql_structures() 