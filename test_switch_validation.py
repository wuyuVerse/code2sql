#!/usr/bin/env python3
"""
测试switch场景的格式验证
"""
import json
from utils.format_validators import validate_orm_response

def test_switch_validation():
    """测试switch场景的验证"""
    print("开始测试switch场景验证...")
    
    # 测试用例1：正常的switch场景（有code_value）
    test_case_1 = {
        "scenario": "switch",
        "code_key": "ProcessPayment",
        "code_value": "func (p *Payment) ProcessPayment() error {\n\tswitch p.Status {\n\tcase Pending:\n\t\treturn p.processPending()\n\tcase Approved:\n\t\treturn p.processApproved()\n\tdefault:\n\t\treturn errors.New(\"invalid status\")\n\t}\n}",
        "sql_pattern_cnt": 1
    }
    
    # 测试用例2：switch场景但缺少code_value（应该通过验证）
    test_case_2 = {
        "scenario": "switch", 
        "code_key": "ProcessPayment",
        "sql_pattern_cnt": 1
    }
    
    # 测试用例3：非switch场景但缺少code_value（应该失败）
    test_case_3 = {
        "scenario": "对象var+chunk",
        "code_key": "FindUser",
        "sql_pattern_cnt": 1
    }
    
    # 测试用例4：switch场景有orm_code但没有code_value（应该通过验证）
    test_case_4 = {
        "scenario": "switch",
        "code_key": "ProcessPayment", 
        "orm_code": "func (p *Payment) ProcessPayment() error {\n\tswitch p.Status {\n\tcase Pending:\n\t\treturn p.processPending()\n\tcase Approved:\n\t\treturn p.processApproved()\n\tdefault:\n\t\treturn errors.New(\"invalid status\")\n\t}\n}",
        "sql_pattern_cnt": 1
    }
    
    test_cases = [
        ("正常switch场景（有code_value）", test_case_1),
        ("switch场景缺少code_value", test_case_2),
        ("非switch场景缺少code_value", test_case_3),
        ("switch场景有orm_code", test_case_4)
    ]
    
    for name, test_case in test_cases:
        print(f"\n=== 测试: {name} ===")
        result = validate_orm_response(test_case)
        
        if result is True:
            print("✅ 验证通过")
        else:
            print(f"❌ 验证失败: {result.get('error', '未知错误')}")
        
        print(f"测试数据: {json.dumps(test_case, ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    test_switch_validation() 