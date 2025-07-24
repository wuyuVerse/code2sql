#!/usr/bin/env python3
"""
简单的并行测试脚本

专门测试并行功能和multi_branch_transaction场景
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_processing.workflow.workflow_manager import run_reverse_sql_generation_workflow


async def test_parallel_and_multi_branch():
    """测试并行功能和multi_branch_transaction场景"""
    
    print("🚀 开始并行功能和multi_branch_transaction测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 测试场景
    test_scenarios = [    # 简单场景
        "multi_branch_transaction",  # 复杂场景（之前错误率高的）
    ]
    
    print("📋 测试场景:")
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"  {i}. {scenario}")
    print()
    
    # 测试配置
    test_config = {
        "base_output_dir": "parallel_test_output",
        "scenarios": test_scenarios,
        "count_per_scenario": 2,   # 每个场景生成2个案例
        "llm_server": "v3",
        "temperature": 0.7,
        "max_tokens": 4096,
        "parallel": True,          # 启用并行模式
        "max_workers": 2,          # 2个并行worker
        "validate": True
    }
    
    print("⚙️ 测试配置:")
    for key, value in test_config.items():
        print(f"  {key}: {value}")
    print()
    
    try:
        print("🔄 开始执行并行测试...")
        print("-" * 40)
        
        start_time = datetime.now()
        result = await run_reverse_sql_generation_workflow(**test_config)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        print("-" * 40)
        
        if result["status"] == "success":
            print("✅ 并行测试成功完成!")
            print()
            print("📊 测试结果:")
            print(f"  - 总生成案例数: {result.get('total_count', 0)}")
            print(f"  - 验证通过案例数: {result.get('valid_count', 0)}")
            success_rate = result.get('valid_count', 0) / result.get('total_count', 1) * 100 if result.get('total_count', 0) > 0 else 0
            print(f"  - 成功率: {success_rate:.1f}%")
            print(f"  - 总耗时: {duration:.1f} 秒")
            print(f"  - 平均每个案例: {duration/result.get('total_count', 1):.1f} 秒")
            print()
            
            # 分析每个场景的结果
            if "generated_cases" in result:
                generated_cases = result["generated_cases"]
                print("📈 各场景生成统计:")
                
                for scenario in test_scenarios:
                    scenario_cases = [k for k in generated_cases.keys() if k.startswith(scenario)]
                    print(f"  - {scenario}: {len(scenario_cases)} 个案例")
                    
                    # 检查multi_branch_transaction的成功率
                    if scenario == "multi_branch_transaction":
                        if len(scenario_cases) > 0:
                            print(f"    ✅ multi_branch_transaction 场景修复成功!")
                        else:
                            print(f"    ❌ multi_branch_transaction 场景仍然失败")
            
            print("🎉 并行测试完成!")
            
        else:
            print("❌ 并行测试失败!")
            print(f"错误信息: {result.get('error', '未知错误')}")
        
        return result
        
    except Exception as e:
        print(f"❌ 并行测试异常: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


async def test_serial_vs_parallel():
    """对比串行和并行模式的性能"""
    
    print("🔄 对比串行和并行模式性能")
    print("=" * 50)
    
    test_scenarios = ["if-else+caller", "switch"]
    
    # 串行测试
    print("📊 串行模式测试...")
    serial_config = {
        "base_output_dir": "serial_test_output",
        "scenarios": test_scenarios,
        "count_per_scenario": 1,
        "llm_server": "v3",
        "temperature": 0.7,
        "max_tokens": 4096,
        "parallel": False,
        "max_workers": 1,
        "validate": True
    }
    
    start_time = datetime.now()
    serial_result = await run_reverse_sql_generation_workflow(**serial_config)
    serial_duration = (datetime.now() - start_time).total_seconds()
    
    # 并行测试
    print("📊 并行模式测试...")
    parallel_config = {
        "base_output_dir": "parallel_test_output",
        "scenarios": test_scenarios,
        "count_per_scenario": 1,
        "llm_server": "v3",
        "temperature": 0.7,
        "max_tokens": 4096,
        "parallel": True,
        "max_workers": 2,
        "validate": True
    }
    
    start_time = datetime.now()
    parallel_result = await run_reverse_sql_generation_workflow(**parallel_config)
    parallel_duration = (datetime.now() - start_time).total_seconds()
    
    # 对比结果
    print("\n📈 性能对比结果:")
    print(f"  - 串行模式耗时: {serial_duration:.1f} 秒")
    print(f"  - 并行模式耗时: {parallel_duration:.1f} 秒")
    if serial_duration > 0:
        speedup = serial_duration / parallel_duration
        print(f"  - 加速比: {speedup:.2f}x")
    
    return {
        "serial": {"result": serial_result, "duration": serial_duration},
        "parallel": {"result": parallel_result, "duration": parallel_duration}
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="并行功能测试")
    parser.add_argument("--compare", action="store_true", help="对比串行和并行模式")
    
    args = parser.parse_args()
    
    if args.compare:
        asyncio.run(test_serial_vs_parallel())
    else:
        asyncio.run(test_parallel_and_multi_branch()) 