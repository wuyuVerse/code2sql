#!/usr/bin/env python3
"""
测试SQL生成器处理缺少code_value字段的情况
"""
import json
import asyncio
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_processing.synthetic_data_generator.get_sql import process_json_file_async

async def test_sql_generation():
    """测试SQL生成"""
    print("开始测试SQL生成...")
    
    # 创建测试数据
    test_data = {
        "synthetic_switch_TestFunction1": {
            "scenario": "switch",
            "code_key": "TestFunction1",
            "code_value": "func (p *Payment) ProcessPayment() error {\n\tswitch p.Status {\n\tcase Pending:\n\t\treturn p.processPending()\n\tcase Approved:\n\t\treturn p.processApproved()\n\tdefault:\n\t\treturn errors.New(\"invalid status\")\n\t}\n}",
            "sql_pattern_cnt": 1,
            "callers": [],
            "code_meta_data": []
        },
        "synthetic_switch_TestFunction2": {
            "scenario": "switch",
            "code_key": "TestFunction2",
            # 缺少code_value字段
            "sql_pattern_cnt": 1,
            "callers": [],
            "code_meta_data": []
        },
        "synthetic_switch_TestFunction3": {
            "scenario": "switch",
            "code_key": "TestFunction3",
            # 使用orm_code字段
            "orm_code": "func (p *Payment) ProcessPayment() error {\n\tswitch p.Status {\n\tcase Pending:\n\t\treturn p.processPending()\n\tcase Approved:\n\t\treturn p.processApproved()\n\tdefault:\n\t\treturn errors.New(\"invalid status\")\n\t}\n}",
            "sql_pattern_cnt": 1,
            "callers": [],
            "code_meta_data": []
        }
    }
    
    # 保存测试数据
    test_input_file = "test_sql_input.json"
    with open(test_input_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    
    print(f"测试数据已保存到: {test_input_file}")
    
    try:
        # 运行SQL生成
        output_file = "test_sql_output.json"
        valid_count, invalid_count = await process_json_file_async(
            input_file=test_input_file,
            output_file=output_file,
            concurrency=2  # 使用较小的并发数进行测试
        )
        
        print(f"\n✅ SQL生成测试完成!")
        print(f"📊 有效记录: {valid_count}")
        print(f"📊 无效记录: {invalid_count}")
        print(f"📁 输出文件: {output_file}")
        
        # 检查输出文件
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                output_data = json.load(f)
            print(f"📊 输出文件包含 {len(output_data)} 条记录")
        else:
            print("❌ 输出文件不存在")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理测试文件
        if os.path.exists(test_input_file):
            os.remove(test_input_file)
        print("🧹 测试文件已清理")

if __name__ == "__main__":
    asyncio.run(test_sql_generation()) 