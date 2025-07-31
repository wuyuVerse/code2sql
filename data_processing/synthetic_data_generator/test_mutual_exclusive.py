#!/usr/bin/env python3
"""
测试修正后的mutual_exclusive_conditions场景的数据生成和SQL分析
"""
import asyncio
import json
from pathlib import Path

from config.data_processing.synthetic_data_generator.config import SyntheticDataConfig
from .generator import SyntheticDataGenerator
from .get_sql import analyze_mutual_exclusive_sql, verify_mutual_exclusive_sql


async def test_mutual_exclusive_generation():
    """测试修正后的mutual_exclusive_conditions场景的数据生成"""
    print("🧪 开始测试修正后的 mutual_exclusive_conditions 场景数据生成...")
    
    # 创建配置
    config = SyntheticDataConfig(
        llm_server="v3",
        temperature=0.7,
        max_tokens=4096,
        output_path="test_mutual_exclusive_output.json"
    )
    
    # 创建生成器
    generator = SyntheticDataGenerator(config)
    
    try:
        # 生成一个mutual_exclusive_conditions包
        print("📝 生成 mutual_exclusive_conditions 数据包...")
        pack = await generator.generate_pack("mutual_exclusive_conditions")
        
        # 验证生成的数据
        print("✅ 验证生成的数据...")
        if generator.validate_pack(pack):
            print("✅ 数据验证通过")
            
            # 保存结果
            output_file = Path("test_mutual_exclusive_output.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(pack, f, ensure_ascii=False, indent=2)
            print(f"💾 结果已保存到: {output_file}")
            
            # 显示生成统计
            generator.print_generation_stats()
            
            # 分析生成的内容
            print("\n📊 生成内容分析:")
            for key, value in pack.items():
                print(f"  - {key}:")
                print(f"    场景: {value.get('scenario', 'N/A')}")
                print(f"    方法: {value.get('code_key', 'N/A')}")
                print(f"    调用者数量: {len(value.get('callers', []))}")
                print(f"    元数据数量: {len(value.get('code_meta_data', []))}")
                
                # 检查ORM代码中的互斥条件和其他filter条件
                orm_code = value.get('code_value', '')
                if 'if' in orm_code and 'else' in orm_code:
                    print(f"    ✅ 包含if-else逻辑")
                else:
                    print(f"    ❌ 缺少if-else逻辑")
                
                # 检查是否包含其他filter条件（如status、created_at等）
                other_conditions = ['status', 'created_at', 'deleted_at', 'updated_at', 'is_active', 'is_deleted']
                found_other_conditions = []
                for condition in other_conditions:
                    if condition in orm_code.lower():
                        found_other_conditions.append(condition)
                
                if found_other_conditions:
                    print(f"    ✅ 包含其他filter条件: {found_other_conditions}")
                else:
                    print(f"    ❌ 缺少其他filter条件")
                
                # 检查Caller代码中的互斥条件和其他filter条件
                callers = value.get('callers', [])
                if callers:
                    caller_code = callers[0].get('code_value', '')
                    if 'if' in caller_code and 'else' in caller_code:
                        print(f"    ✅ Caller包含if-else逻辑")
                    else:
                        print(f"    ❌ Caller缺少if-else逻辑")
                    
                    # 检查callers是否为空
                    if len(callers) > 0:
                        print(f"    ✅ Callers不为空（符合要求）")
                    else:
                        print(f"    ❌ Callers为空（不符合要求）")
                    
                    # 检查Caller是否包含其他filter条件
                    found_caller_conditions = []
                    for condition in other_conditions:
                        if condition in caller_code.lower():
                            found_caller_conditions.append(condition)
                    
                    if found_caller_conditions:
                        print(f"    ✅ Caller包含其他filter条件: {found_caller_conditions}")
                    else:
                        print(f"    ❌ Caller缺少其他filter条件")
                else:
                    print(f"    ❌ 没有callers（不符合要求）")
                
                print()
            
            return pack
            
        else:
            print("❌ 数据验证失败")
            return None
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_mutual_exclusive_sql_analysis(pack):
    """测试修正后的mutual_exclusive_conditions场景的SQL分析"""
    print("\n🧪 开始测试修正后的 mutual_exclusive_conditions SQL分析...")
    
    if not pack:
        print("❌ 没有可用的数据包进行SQL分析")
        return
    
    try:
        from utils.llm_client import LLMClient
        
        # 创建LLM客户端
        llm_client = LLMClient("v3")
        
        # 获取第一个数据包进行测试
        first_key = list(pack.keys())[0]
        data = pack[first_key]
        
        orm_code = data.get('code_value', '')
        function_name = data.get('code_key', '')
        callers = data.get('callers', [])
        code_meta_data = data.get('code_meta_data', [])
        
        # 格式化元数据
        meta_data_str = json.dumps(code_meta_data, ensure_ascii=False, indent=2)
        
        # 格式化调用者信息
        caller_str = json.dumps(callers, ensure_ascii=False, indent=2) if callers else ""
        
        print(f"📝 分析ORM代码: {function_name}")
        print(f"  代码长度: {len(orm_code)} 字符")
        print(f"  调用者数量: {len(callers)}")
        print(f"  元数据数量: {len(code_meta_data)}")
        
        # 执行SQL分析
        print("🔍 执行SQL分析...")
        sql_analysis = await analyze_mutual_exclusive_sql(
            orm_code=orm_code,
            function_name=function_name,
            caller=caller_str,
            code_meta_data=meta_data_str,
            llm_client=llm_client
        )
        
        print("✅ SQL分析完成:")
        print(f"  分析结果类型: {type(sql_analysis)}")
        print(f"  结果长度: {len(str(sql_analysis))} 字符")
        
        # 验证SQL分析结果
        print("🔍 验证SQL分析结果...")
        verified_sql = await verify_mutual_exclusive_sql(
            sql_analysis=sql_analysis,
            orm_code=orm_code,
            function_name=function_name,
            caller=caller_str,
            code_meta_data=meta_data_str,
            llm_client=llm_client
        )
        
        print("✅ SQL验证完成:")
        print(f"  验证结果类型: {type(verified_sql)}")
        
        # 保存SQL分析结果
        sql_output_file = Path("test_mutual_exclusive_sql_analysis.json")
        with open(sql_output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "original_analysis": sql_analysis,
                "verified_analysis": verified_sql,
                "orm_code": orm_code,
                "function_name": function_name,
                "callers": callers
            }, f, ensure_ascii=False, indent=2)
        print(f"💾 SQL分析结果已保存到: {sql_output_file}")
        
        # 分析SQL结果
        print("\n📊 SQL分析结果分析:")
        if isinstance(verified_sql, list):
            print(f"  SQL语句数量: {len(verified_sql)}")
            for i, sql_item in enumerate(verified_sql):
                if isinstance(sql_item, dict):
                    if sql_item.get('type') == 'param_dependent':
                        variants = sql_item.get('variants', [])
                        print(f"  变体组{i+1}: {len(variants)} 个变体")
                        for j, variant in enumerate(variants):
                            scenario = variant.get('scenario', 'N/A')
                            sql = variant.get('sql', 'N/A')
                            print(f"    变体{j+1}: {scenario[:50]}...")
                            print(f"    SQL: {sql[:100]}...")
                            
                            # 检查SQL是否包含其他filter条件
                            other_conditions = ['status', 'created_at', 'deleted_at', 'updated_at', 'is_active', 'is_deleted']
                            found_conditions = []
                            for condition in other_conditions:
                                if condition in sql.lower():
                                    found_conditions.append(condition)
                            
                            if found_conditions:
                                print(f"      包含其他条件: {found_conditions}")
                    elif sql_item.get('type') in ['LACK_INFORMATION', 'NO_SQL_GENERATE']:
                        print(f"  边界条件{i+1}: {sql_item.get('type')}")
                        variants = sql_item.get('variants', [])
                        for variant in variants:
                            scenario = variant.get('scenario', 'N/A')
                            print(f"    原因: {scenario}")
                else:
                    print(f"  固定SQL{i+1}: {str(sql_item)[:100]}...")
        else:
            print(f"  结果类型: {type(verified_sql)}")
            print(f"  内容: {str(verified_sql)[:200]}...")
        
    except Exception as e:
        print(f"❌ SQL分析失败: {e}")
        import traceback
        traceback.print_exc()


async def test_mutual_exclusive_integration():
    """测试修正后的mutual_exclusive_conditions场景的完整集成流程"""
    print("\n🧪 开始测试修正后的 mutual_exclusive_conditions 完整集成流程...")
    
    try:
        # 1. 生成数据
        pack = await test_mutual_exclusive_generation()
        
        # 2. 分析SQL
        if pack:
            await test_mutual_exclusive_sql_analysis(pack)
        
        print("\n✅ 完整集成测试完成!")
        
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    print("🚀 开始测试修正后的 mutual_exclusive_conditions 场景...")
    
    # 测试完整集成流程
    await test_mutual_exclusive_integration()
    
    print("\n✅ 所有测试完成!")


if __name__ == "__main__":
    asyncio.run(main()) 