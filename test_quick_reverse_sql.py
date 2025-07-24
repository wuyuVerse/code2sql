#!/usr/bin/env python3
"""
快速反向SQL生成测试脚本

测试几个关键场景，每个场景生成3个案例
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_processing.workflow.workflow_manager import run_reverse_sql_generation_workflow


async def quick_test():
    """快速测试几个关键场景"""
    
    print("🚀 开始快速反向SQL生成测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 选择几个关键场景进行快速测试
    key_scenarios = [
        "if-else+caller",      # 基础if-else场景
        "switch",              # switch场景
        "dynamic_query",       # 动态查询场景
        "multi_branch_transaction",  # 复杂场景（之前错误率高的）
    ]
    
    print("📋 快速测试场景:")
    for i, scenario in enumerate(key_scenarios, 1):
        print(f"  {i}. {scenario}")
    print()
    
    # 测试配置
    test_config = {
        "base_output_dir": "quick_test_output",
        "scenarios": key_scenarios,
        "count_per_scenario": 3,   # 每个场景生成3个案例
        "llm_server": "v3",
        "temperature": 0.7,
        "max_tokens": 4096,
        "parallel": True,
        "max_workers": 2,          # 减少worker数量
        "validate": True
    }
    
    print("⚙️ 测试配置:")
    for key, value in test_config.items():
        print(f"  {key}: {value}")
    print()
    
    try:
        print("🔄 开始执行快速测试...")
        print("-" * 40)
        
        result = await run_reverse_sql_generation_workflow(**test_config)
        
        print("-" * 40)
        
        if result["status"] == "success":
            print("✅ 快速测试成功完成!")
            print()
            print("📊 测试结果:")
            print(f"  - 总生成案例数: {result.get('total_count', 0)}")
            print(f"  - 验证通过案例数: {result.get('valid_count', 0)}")
            success_rate = result.get('valid_count', 0) / result.get('total_count', 1) * 100 if result.get('total_count', 0) > 0 else 0
            print(f"  - 成功率: {success_rate:.1f}%")
            print()
            
            # 简单统计
            if "generated_cases" in result:
                generated_cases = result["generated_cases"]
                print(f"📈 生成案例数: {len(generated_cases)}")
                
                # 检查每个场景的生成情况
                for scenario in key_scenarios:
                    scenario_cases = [k for k in generated_cases.keys() if k.startswith(scenario)]
                    print(f"  - {scenario}: {len(scenario_cases)} 个案例")
            
            print("🎉 快速测试完成!")
            
        else:
            print("❌ 快速测试失败!")
            print(f"错误信息: {result.get('error', '未知错误')}")
        
        return result
        
    except Exception as e:
        print(f"❌ 快速测试异常: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    # 运行快速测试
    asyncio.run(quick_test()) 