"""
合成数据生成器使用示例
"""
import json
from pathlib import Path

from config.data_processing.synthetic_data_generator.config import SyntheticDataConfig
from .generator import SyntheticDataGenerator


def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 创建配置
    config = SyntheticDataConfig(
        llm_server="v3",
        max_workers=2,
        temperature=0.7,
        max_tokens=2048
    )
    
    # 创建生成器
    generator = SyntheticDataGenerator(config)
    
    # 生成单个包
    scenarios = config.list_scenarios()
    if scenarios:
        test_scenario = scenarios[0]  # 使用第一个场景
        print(f"生成场景: {test_scenario}")
        
        try:
            pack = generator.generate_pack(test_scenario)
            print(f"成功生成包: {list(pack.keys())[0]}")
            
            # 验证生成的包
            if generator.validate_pack(pack):
                print("✅ 包验证通过")
            else:
                print("❌ 包验证失败")
                
        except Exception as e:
            print(f"生成失败: {e}")


def example_parallel_generation():
    """并行生成示例"""
    print("\n=== 并行生成示例 ===")
    
    # 创建配置
    config = SyntheticDataConfig(
        llm_server="v3",
        max_workers=4,
        temperature=0.7,
        max_tokens=2048
    )
    
    # 创建生成器
    generator = SyntheticDataGenerator(config)
    
    # 定义要生成的场景和数量
    scenarios_and_counts = [
        ("单chunk", 2),
        ("caller+chunk", 2)
    ]
    
    print(f"开始并行生成 {sum(count for _, count in scenarios_and_counts)} 个包...")
    
    try:
        all_packs = generator.generate_multiple_packs_parallel(scenarios_and_counts)
        print(f"成功生成 {len(all_packs)} 个包")
        
        # 显示生成的包键
        for key in all_packs.keys():
            print(f"  - {key}")
            
        # 显示统计信息
        generator.print_generation_stats()
        
    except Exception as e:
        print(f"并行生成失败: {e}")


def example_custom_config():
    """自定义配置示例"""
    print("\n=== 自定义配置示例 ===")
    
    # 从配置获取max_tokens
    from config.data_processing.workflow.workflow_config import get_workflow_config
    workflow_config = get_workflow_config()
    max_tokens = workflow_config.get_max_tokens("synthetic_data_generator")
    
    # 创建自定义配置
    config = SyntheticDataConfig(
        llm_server="r1",  # 使用r1服务器
        full_scenario_path="/path/to/your/full_scenario.json",
        output_path="custom_output.json",
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
    print("前5个场景:")
    for i, scenario in enumerate(scenarios[:5]):
        desc = config.get_scenario_description(scenario)
        print(f"  {i+1}. {scenario}: {desc}")


def main():
    """主函数"""
    print("🧪 合成数据生成器使用示例")
    print("=" * 50)
    
    try:
        example_basic_usage()
        example_parallel_generation()
        example_custom_config()
        
        print("\n🎉 所有示例运行完成！")
        
    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 