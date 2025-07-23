"""
反向SQL生成器使用示例
"""
import json
import asyncio
from pathlib import Path

from config.data_processing.reverse_sql_generator.config import ReverseSQLConfig
from .generator import ReverseSQLGenerator


async def example_basic_usage():
    """基本使用示例"""
    print("=== 反向SQL生成器基本使用示例 ===")
    
    # 创建配置
    config = ReverseSQLConfig(
        llm_server="v3",
        max_workers=2,
        temperature=0.7,
        max_tokens=2048
    )
    
    # 创建生成器
    generator = ReverseSQLGenerator(config)
    
    # 生成简单案例
    scenarios = config.list_scenarios()
    if scenarios:
        test_scenario = scenarios[0]  # 使用第一个场景
        print(f"生成场景: {test_scenario}")
        
        try:
            case = await generator.generate_complete_case(test_scenario, "simple")
            print(f"成功生成案例: {list(case.keys())[0]}")
            
            # 验证生成的案例
            if generator.validate_case(case):
                print("✅ 案例验证通过")
            else:
                print("❌ 案例验证失败")
                
        except Exception as e:
            print(f"生成失败: {e}")


async def example_if_else_case():
    """if-else案例生成示例"""
    print("\n=== if-else案例生成示例 ===")
    
    # 创建配置
    config = ReverseSQLConfig(
        llm_server="v3",
        max_workers=2,
        temperature=0.7,
        max_tokens=2048
    )
    
    # 创建生成器
    generator = ReverseSQLGenerator(config)
    
    try:
        # 生成if-else案例
        case = await generator.generate_if_else_case("if-else+caller")
        print(f"成功生成if-else案例: {list(case.keys())[0]}")
        
        # 显示案例结构
        case_key = list(case.keys())[0]
        case_data = case[case_key]
        
        print(f"  - 场景: {case_data.get('scenario')}")
        print(f"  - 基础SQL: {case_data.get('base_sql', {}).get('query', 'N/A')[:50]}...")
        print(f"  - ORM方法: {case_data.get('orm_code', {}).get('method_name', 'N/A')}")
        print(f"  - Caller方法: {case_data.get('caller_code', {}).get('method_name', 'N/A')}")
        print(f"  - SQL变体数量: {len(case_data.get('control_flow_sqls', []))}")
        
    except Exception as e:
        print(f"if-else案例生成失败: {e}")


async def example_switch_case():
    """switch案例生成示例"""
    print("\n=== switch案例生成示例 ===")
    
    # 创建配置
    config = ReverseSQLConfig(
        llm_server="v3",
        max_workers=2,
        temperature=0.7,
        max_tokens=2048
    )
    
    # 创建生成器
    generator = ReverseSQLGenerator(config)
    
    try:
        # 生成switch案例
        case = await generator.generate_switch_case("switch")
        print(f"成功生成switch案例: {list(case.keys())[0]}")
        
        # 显示案例结构
        case_key = list(case.keys())[0]
        case_data = case[case_key]
        
        print(f"  - 场景: {case_data.get('scenario')}")
        print(f"  - 基础SQL: {case_data.get('base_sql', {}).get('query', 'N/A')[:50]}...")
        print(f"  - ORM方法: {case_data.get('orm_code', {}).get('method_name', 'N/A')}")
        print(f"  - Caller方法: {case_data.get('caller_code', {}).get('method_name', 'N/A')}")
        print(f"  - SQL变体数量: {len(case_data.get('control_flow_sqls', []))}")
        
    except Exception as e:
        print(f"switch案例生成失败: {e}")


async def example_dynamic_case():
    """动态查询案例生成示例"""
    print("\n=== 动态查询案例生成示例 ===")
    
    # 创建配置
    config = ReverseSQLConfig(
        llm_server="v3",
        max_workers=2,
        temperature=0.7,
        max_tokens=2048
    )
    
    # 创建生成器
    generator = ReverseSQLGenerator(config)
    
    try:
        # 生成动态查询案例
        case = await generator.generate_dynamic_case("dynamic_query")
        print(f"成功生成动态查询案例: {list(case.keys())[0]}")
        
        # 显示案例结构
        case_key = list(case.keys())[0]
        case_data = case[case_key]
        
        print(f"  - 场景: {case_data.get('scenario')}")
        print(f"  - 基础SQL: {case_data.get('base_sql', {}).get('query', 'N/A')[:50]}...")
        print(f"  - ORM方法: {case_data.get('orm_code', {}).get('method_name', 'N/A')}")
        print(f"  - Caller方法: {case_data.get('caller_code', {}).get('method_name', 'N/A')}")
        print(f"  - SQL变体数量: {len(case_data.get('control_flow_sqls', []))}")
        
    except Exception as e:
        print(f"动态查询案例生成失败: {e}")


async def example_batch_generation():
    """批量生成示例"""
    print("\n=== 批量生成示例 ===")
    
    # 创建配置
    config = ReverseSQLConfig(
        llm_server="v3",
        max_workers=4,
        temperature=0.7,
        max_tokens=2048
    )
    
    # 创建生成器
    generator = ReverseSQLGenerator(config)
    
    # 定义要生成的场景和复杂度
    scenarios_and_complexities = [
        ("if-else+caller", "simple"),
        ("switch", "medium"),
        ("dynamic_query", "simple")
    ]
    
    print(f"开始批量生成 {len(scenarios_and_complexities)} 个案例...")
    
    try:
        all_cases = await generator.generate_multiple_cases(scenarios_and_complexities)
        print(f"成功生成 {len(all_cases)} 个案例")
        
        # 显示生成的案例键
        for key in all_cases.keys():
            print(f"  - {key}")
            
    except Exception as e:
        print(f"批量生成失败: {e}")


async def example_custom_config():
    """自定义配置示例"""
    print("\n=== 自定义配置示例 ===")
    
    # 从配置获取max_tokens
    from config.data_processing.workflow.workflow_config import get_workflow_config
    workflow_config = get_workflow_config()
    max_tokens = workflow_config.get_max_tokens("reverse_sql_generator")
    
    # 创建自定义配置
    config = ReverseSQLConfig(
        llm_server="r1",  # 使用r1服务器
        output_path="custom_reverse_cases.json",
        max_workers=8,
        temperature=0.8,
        top_p=0.9,
        max_tokens=max_tokens,
    )
    
    print(f"LLM服务器: {config.llm_server}")
    print(f"输出路径: {config.output_path}")
    print(f"最大worker数: {config.max_workers}")
    print(f"温度参数: {config.temperature}")
    print(f"Top-p参数: {config.top_p}")
    print(f"最大token数: {config.max_tokens}")
    
    # 显示支持的场景
    scenarios = config.list_scenarios()
    print(f"\n支持的场景数量: {len(scenarios)}")
    print("支持的场景:")
    for i, scenario in enumerate(scenarios):
        desc = config.get_scenario_description(scenario)
        print(f"  {i+1}. {scenario}: {desc}")
    
    # 显示复杂度级别
    complexities = config.list_complexities()
    print(f"\n复杂度级别数量: {len(complexities)}")
    print("复杂度级别:")
    for complexity in complexities:
        config_data = config.get_complexity_config(complexity)
        print(f"  - {complexity}: {config_data['description']}")


async def main():
    """主函数"""
    print("🔄 反向SQL生成器使用示例")
    print("=" * 50)
    
    try:
        await example_basic_usage()
        await example_if_else_case()
        await example_switch_case()
        await example_dynamic_case()
        await example_batch_generation()
        await example_custom_config()
        
        print("\n🎉 所有示例运行完成！")
        
    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 