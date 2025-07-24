#!/usr/bin/env python3
"""
测试SQL类型映射
"""
import asyncio
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data_processing.reverse_sql_generator.generator import ReverseSQLGenerator
from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig


async def test_sql_types():
    """测试SQL类型映射"""
    print("🚀 开始测试SQL类型映射...")
    
    # 创建配置
    config = ReverseSQLConfig(
        llm_server="v3",
        temperature=0.7,
        max_tokens=4096
    )
    
    # 创建生成器
    generator = ReverseSQLGenerator(config)
    
    try:
        # 测试不同场景的SQL类型映射
        scenarios = [
            ("if-else+caller", "simple"),
            ("if-else+orm", "simple"),
            ("switch", "simple"),
            ("dynamic_query", "simple"),
            ("complex_control", "simple"),
            ("fixed_params", "simple")
        ]
        
        results = {}
        
        for scenario, complexity in scenarios:
            print(f"\n📋 测试 {scenario} ({complexity})...")
            
            try:
                case = await generator.generate_complete_case(scenario, complexity)
                case_key = list(case.keys())[0]
                case_data = case[case_key]
                
                # 检查SQL类型
                sql_types = case_data.get("sql_types", [])
                sql_statement_list = case_data.get("sql_statement_list", [])
                
                print(f"  ✅ 生成成功")
                print(f"  SQL类型: {sql_types}")
                print(f"  SQL语句列表长度: {len(sql_statement_list)}")
                
                if sql_statement_list:
                    for i, sql_item in enumerate(sql_statement_list):
                        sql_type = sql_item.get("type", "unknown")
                        variants = sql_item.get("variants", [])
                        print(f"  SQL项目{i+1}: {sql_type}, 变体数量: {len(variants)}")
                
                results[scenario] = {
                    "sql_types": sql_types,
                    "sql_statement_list": sql_statement_list
                }
                
            except Exception as e:
                print(f"  ❌ 生成失败: {e}")
                results[scenario] = {"error": str(e)}
        
        # 总结结果
        print(f"\n📊 测试结果总结:")
        print(f"{'场景':<20} {'SQL类型':<15} {'变体数量':<10}")
        print("-" * 50)
        
        for scenario, result in results.items():
            if "error" not in result:
                sql_types = result["sql_types"]
                sql_statement_list = result["sql_statement_list"]
                variant_count = 0
                if sql_statement_list:
                    for sql_item in sql_statement_list:
                        variants = sql_item.get("variants", [])
                        variant_count += len(variants)
                
                print(f"{scenario:<20} {str(sql_types):<15} {variant_count:<10}")
            else:
                print(f"{scenario:<20} {'ERROR':<15} {'N/A':<10}")
        
        # 验证映射关系
        print(f"\n✅ 映射关系验证:")
        print(f"  所有场景 → PARAM_DEPENDENT (都有动态参数)")
        
        # 验证所有场景都是PARAM_DEPENDENT
        all_param_dependent = True
        for scenario, result in results.items():
            if "error" not in result:
                sql_types = result["sql_types"]
                if "PARAM_DEPENDENT" not in sql_types:
                    all_param_dependent = False
                    print(f"  ❌ {scenario}: {sql_types}")
        
        if all_param_dependent:
            print(f"  ✅ 所有场景都正确映射到 PARAM_DEPENDENT")
        else:
            print(f"  ❌ 部分场景映射错误")
        
        # 保存结果
        output_file = "test_sql_types_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 详细结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await generator.close()


async def main():
    """主函数"""
    await test_sql_types()


if __name__ == "__main__":
    asyncio.run(main()) 