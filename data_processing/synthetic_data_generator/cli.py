"""
合成数据生成器命令行接口
"""
import argparse
import json
import time
from pathlib import Path
from typing import Dict, List

from config.data_processing.synthetic_data_generator.config import SyntheticDataConfig
from .generator import SyntheticDataGenerator


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="生成伪造的ORM场景数据")
    parser.add_argument("--scenario", choices=SyntheticDataConfig().list_scenarios(), 
                       help="要生成的场景标签", default=None)
    parser.add_argument("--count", type=int, default=1, help="每个场景生成多少个包")
    parser.add_argument("--out", type=Path, default=Path("synthetic_scenarios.json"), 
                       help="输出文件路径")
    parser.add_argument("--validate", action="store_true", help="验证生成的数据格式")
    parser.add_argument("--list-scenarios", action="store_true", help="列出所有支持的场景")
    parser.add_argument("--full-scenario-path", type=str, default=SyntheticDataConfig().full_scenario_path,
                       help="full_scenario.json文件路径")
    
    # 并行相关参数
    parser.add_argument("--parallel", action="store_true", help="启用并行模式")
    parser.add_argument("--workers", type=int, default=4, help="并行worker数量 (默认: 4)")
    parser.add_argument("--no-delay", action="store_true", help="禁用请求间延迟（并行模式下自动禁用）")
    parser.add_argument("--stats", action="store_true", help="显示详细统计信息")
    
    # LLM相关参数
    parser.add_argument("--llm-server", type=str, default="v3", help="LLM服务器名称")
    parser.add_argument("--temperature", type=float, default=0.7, help="LLM温度参数")
    parser.add_argument("--top-p", type=float, default=0.8, help="LLM top_p参数")
    parser.add_argument("--max-tokens", type=int, default=4096, help="最大token数")
    
    args = parser.parse_args()

    if args.list_scenarios:
        print("支持的场景列表:")
        config = SyntheticDataConfig()
        for scenario in config.list_scenarios():
            desc = config.get_scenario_description(scenario)
            print(f"  - {scenario}: {desc}")
        return

    # 创建配置
    config = SyntheticDataConfig(
        llm_server=args.llm_server,
        full_scenario_path=args.full_scenario_path,
        output_path=str(args.out),
        max_workers=args.workers,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens
    )

    # 创建生成器
    generator = SyntheticDataGenerator(config)
    
    # 加载参考样例
    print(f"加载参考样例: {config.full_scenario_path}")
    if generator.full_scenarios:
        print(f"成功加载 {len(generator.full_scenarios)} 个参考样例")
        # 统计各场景的样例数量
        scenario_counts = {}
        for value in generator.full_scenarios.values():
            scenario = value.get('scenario', '未知')
            scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
        
        print("各场景样例数量:")
        for scenario, count in scenario_counts.items():
            print(f"  - {scenario}: {count} 个")
    else:
        print("警告: 未能加载参考样例，将使用通用模板生成")

    scenarios = [args.scenario] if args.scenario else config.list_scenarios()

    # 记录开始时间
    start_time = time.time()
    all_packs: Dict = {}
    total_generated = 0
    
    if args.parallel:
        # 并行模式
        print(f"\n🚀 启用并行模式 (workers: {args.workers})")
        scenarios_and_counts = [(sc, args.count) for sc in scenarios]
        
        try:
            all_packs = generator.generate_multiple_packs_parallel(scenarios_and_counts)
            total_generated = len(all_packs)
            
        except Exception as e:
            print(f"并行生成时出错: {e}")
            return
    else:
        # 串行模式
        print(f"\n📝 串行模式生成")
        for sc in scenarios:
            print(f"\n开始生成场景: {sc}")
            print(f"场景描述: {config.get_scenario_description(sc)}")
            for i in range(args.count):
                print(f"生成第 {i+1}/{args.count} 个包...")
                try:
                    pack = generator.generate_pack(sc)
                    
                    if args.validate and not generator.validate_pack(pack):
                        print(f"包验证失败，跳过...")
                        continue
                    
                    all_packs.update(pack)
                    total_generated += 1
                    
                    # 串行模式下的延迟（除非禁用）
                    if not args.no_delay:
                        time.sleep(0.5)
                    
                except Exception as e:
                    print(f"生成包时出错: {e}")
                    continue

    # 计算总耗时
    elapsed_time = time.time() - start_time
    
    # 验证生成的数据（如果启用）
    if args.validate:
        print(f"\n🔍 验证生成的数据...")
        valid_count = 0
        for key, pack_data in all_packs.items():
            if generator.validate_pack({key: pack_data}):
                valid_count += 1
        print(f"验证结果: {valid_count}/{len(all_packs)} 个包通过验证")

    # 保存结果
    try:
        config.output_path.write_text(json.dumps(all_packs, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"\n✅ 成功生成 {total_generated} 个包 → {config.output_path}")
        print(f"包含以下场景: {scenarios}")
        print(f"总耗时: {elapsed_time:.2f} 秒")
        
        if total_generated > 0:
            print(f"平均每包耗时: {elapsed_time/total_generated:.2f} 秒")
        
        # 显示生成的包的键
        if all_packs and len(all_packs) <= 10:
            print("\n生成的包键:")
            for key in all_packs.keys():
                print(f"  - {key}")
        elif all_packs:
            print(f"\n生成了 {len(all_packs)} 个包 (键列表略)")
                
    except Exception as e:
        print(f"保存文件时出错: {e}")
        return
    
    # 显示统计信息
    if args.stats or args.parallel:
        generator.print_generation_stats()


if __name__ == "__main__":
    main() 