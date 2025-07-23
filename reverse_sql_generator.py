#!/usr/bin/env python3
"""
反向SQL生成器完整脚本

从SQL开始生成ORM和Caller代码的反向工作流
支持命令行接口和示例功能
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from data_processing.workflow.workflow_manager import WorkflowManager, run_reverse_sql_generation_workflow


async def run_examples():
    """运行示例功能"""
    print("🔄 反向SQL生成器示例")
    print("=" * 50)
    
    try:
        # 示例1: 基本使用
        print("\n=== 示例1: 基本使用 ===")
        scenarios = ["if-else+caller", "switch", "dynamic_query"]
        result = await run_reverse_sql_generation_workflow(
            base_output_dir="example_basic_output",
            scenarios=scenarios,
            count_per_scenario=1,
            llm_server="v3",
            temperature=0.7,
            max_tokens=2048,
            parallel=True,
            max_workers=2,
            validate=True
        )
        
        if result["status"] == "success":
            print("✅ 基本使用示例执行成功!")
            print(f"生成案例数: {result['total_count']}")
            print(f"验证通过数: {result['valid_count']}")
        else:
            print(f"❌ 基本使用示例执行失败: {result.get('error', '未知错误')}")
        
        # 示例2: 复杂场景
        print("\n=== 示例2: 复杂场景 ===")
        scenarios = ["complex_control", "if-else+orm", "dynamic_query"]
        result = await run_reverse_sql_generation_workflow(
            base_output_dir="example_complex_output",
            scenarios=scenarios,
            count_per_scenario=1,
            llm_server="v3",
            temperature=0.8,
            max_tokens=4096,
            parallel=True,
            max_workers=4,
            validate=True
        )
        
        if result["status"] == "success":
            print("✅ 复杂场景示例执行成功!")
            print(f"生成案例数: {result['total_count']}")
            print(f"验证通过数: {result['valid_count']}")
        else:
            print(f"❌ 复杂场景示例执行失败: {result.get('error', '未知错误')}")
        
        # 示例3: 所有场景
        print("\n=== 示例3: 所有场景 ===")
        scenarios = [
            "if-else+caller", "if-else+orm", "switch", 
            "dynamic_query", "fixed_params", "complex_control"
        ]
        result = await run_reverse_sql_generation_workflow(
            base_output_dir="example_all_output",
            scenarios=scenarios,
            count_per_scenario=1,
            llm_server="v3",
            temperature=0.7,
            max_tokens=2048,
            parallel=True,
            max_workers=6,
            validate=True
        )
        
        if result["status"] == "success":
            print("✅ 所有场景示例执行成功!")
            print(f"生成案例数: {result['total_count']}")
            print(f"验证通过数: {result['valid_count']}")
            
            # 显示生成的案例详情
            print("\n📊 生成案例详情:")
            generated_cases = result["generated_cases"]
            for case_key, case_data in generated_cases.items():
                scenario = case_data.get("scenario", "未知")
                complexity = case_data.get("complexity", "未知")
                orm_method = case_data.get("orm_code", {}).get("method_name", "未知")
                caller_method = case_data.get("caller_code", {}).get("method_name", "未知")
                control_flow_count = len(case_data.get("control_flow_sqls", []))
                
                print(f"  - {case_key}")
                print(f"    场景: {scenario}")
                print(f"    复杂度: {complexity}")
                print(f"    ORM方法: {orm_method}")
                print(f"    Caller方法: {caller_method}")
                print(f"    控制流SQL数: {control_flow_count}")
                print()
        else:
            print(f"❌ 所有场景示例执行失败: {result.get('error', '未知错误')}")
        
        # 示例4: 自定义配置
        print("\n=== 示例4: 自定义配置 ===")
        scenarios = ["if-else+caller"]
        result = await run_reverse_sql_generation_workflow(
            base_output_dir="example_custom_output",
            scenarios=scenarios,
            count_per_scenario=2,
            llm_server="r1",  # 使用r1服务器
            temperature=0.9,   # 高温度参数
            max_tokens=3072,   # 自定义token数
            parallel=False,     # 禁用并行模式
            max_workers=1,
            validate=True
        )
        
        if result["status"] == "success":
            print("✅ 自定义配置示例执行成功!")
            print(f"生成案例数: {result['total_count']}")
            print(f"验证通过数: {result['valid_count']}")
        else:
            print(f"❌ 自定义配置示例执行失败: {result.get('error', '未知错误')}")
        
        print("\n🎉 所有示例运行完成!")
        return 0
        
    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def run_command_line(args):
    """运行命令行功能"""
    print("🔄 反向SQL生成器")
    print("=" * 50)
    print(f"输出目录: {args.output_dir}")
    print(f"LLM服务器: {args.llm_server}")
    print(f"温度参数: {args.temperature}")
    print(f"最大token数: {args.max_tokens}")
    print(f"并行模式: {'启用' if args.parallel else '禁用'}")
    print(f"最大worker数: {args.max_workers}")
    print(f"数据验证: {'启用' if args.validate else '禁用'}")
    
    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建工作流管理器
    workflow_manager = WorkflowManager(base_output_dir=str(output_dir))
    
    # 确定要生成的场景
    scenarios = args.scenarios
    if scenarios is None:
        # 使用默认场景列表
        scenarios = [
            "if-else+caller", "if-else+orm", "switch", 
            "dynamic_query", "fixed_params", "complex_control"
        ]
    
    print(f"将生成以下场景的数据:")
    for i, scenario in enumerate(scenarios, 1):
        print(f"  {i}. {scenario}")
    print(f"每个场景生成 {args.count_per_scenario} 个数据包")
    
    try:
        # 执行反向SQL数据生成
        print("\n🚀 开始生成反向SQL数据...")
        result = await workflow_manager.generate_reverse_sql_data(
            scenarios=scenarios,
            count_per_scenario=args.count_per_scenario,
            llm_server=args.llm_server,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            parallel=args.parallel,
            max_workers=args.max_workers,
            validate=args.validate,
            step_name=args.step_name
        )
        
        if result["status"] == "success":
            print("\n✅ 反向SQL数据生成成功!")
            print(f"  - 生成案例数: {result['total_count']}")
            print(f"  - 验证通过数: {result['valid_count']}")
            print(f"  - 输出文件: {result['output_file']}")
            
            # 显示生成的案例概览
            print("\n📊 生成案例概览:")
            generated_cases = result["generated_cases"]
            for case_key, case_data in generated_cases.items():
                scenario = case_data.get("scenario", "未知")
                complexity = case_data.get("complexity", "未知")
                orm_method = case_data.get("orm_code", {}).get("method_name", "未知")
                caller_method = case_data.get("caller_code", {}).get("method_name", "未知")
                control_flow_count = len(case_data.get("control_flow_sqls", []))
                
                print(f"  - {case_key}")
                print(f"    场景: {scenario}")
                print(f"    复杂度: {complexity}")
                print(f"    ORM方法: {orm_method}")
                print(f"    Caller方法: {caller_method}")
                print(f"    控制流SQL数: {control_flow_count}")
                print()
            
            # 保存工作流摘要
            summary_file = workflow_manager.save_workflow_summary()
            print(f"工作流摘要已保存到: {summary_file}")
            
            # 打印工作流摘要
            workflow_manager.print_workflow_summary()
            
        else:
            print(f"\n❌ 反向SQL数据生成失败: {result.get('error', '未知错误')}")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作")
        return 1
    except Exception as e:
        print(f"\n❌ 执行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n🎉 反向SQL生成器执行完成!")
    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="反向SQL生成器 - 从SQL开始生成ORM和Caller代码",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 运行示例
  python reverse_sql_generator.py --examples
  
  # 基本使用
  python reverse_sql_generator.py
  
  # 指定场景
  python reverse_sql_generator.py --scenarios if-else+caller switch dynamic_query
  
  # 自定义参数
  python reverse_sql_generator.py --llm-server v3 --temperature 0.8 --max-workers 6
  
  # 生成多个数据包
  python reverse_sql_generator.py --count-per-scenario 3 --scenarios if-else+caller
        """
    )
    
    # 模式选择
    parser.add_argument("--examples", action="store_true",
                       help="运行示例功能")
    
    # 基本参数
    parser.add_argument("--output-dir", default="reverse_sql_output", 
                       help="输出目录")
    parser.add_argument("--scenarios", nargs="+", 
                       help="要生成的场景列表")
    parser.add_argument("--count-per-scenario", type=int, default=1,
                       help="每个场景生成的数据包数量")
    
    # LLM参数
    parser.add_argument("--llm-server", default="v3",
                       help="LLM服务器名称")
    parser.add_argument("--temperature", type=float, default=0.7,
                       help="LLM温度参数")
    parser.add_argument("--max-tokens", type=int, default=4096,
                       help="最大token数")
    
    # 并行参数
    parser.add_argument("--parallel", action="store_true", default=True,
                       help="启用并行模式")
    parser.add_argument("--max-workers", type=int, default=4,
                       help="并行worker数量")
    
    # 验证参数
    parser.add_argument("--validate", action="store_true", default=True,
                       help="验证生成的数据")
    
    # 工作流参数
    parser.add_argument("--step-name", default="reverse_sql_generation",
                       help="步骤名称")
    
    args = parser.parse_args()
    
    # 根据模式选择执行不同的功能
    if args.examples:
        # 运行示例
        exit_code = asyncio.run(run_examples())
    else:
        # 运行命令行功能
        exit_code = asyncio.run(run_command_line(args))
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main() 