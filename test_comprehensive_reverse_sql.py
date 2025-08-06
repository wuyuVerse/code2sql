#!/usr/bin/env python3
"""
全面的反向SQL生成测试脚本

测试所有11种场景，每个场景生成10个案例
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_processing.workflow.workflow_manager import run_reverse_sql_generation_workflow


async def test_all_scenarios():
    """测试所有场景的反向SQL生成"""
    
    print("🚀 开始全面反向SQL生成测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 定义所有支持的场景
    all_scenarios = [
        "if-else+caller",      # if-else+caller场景
        "if-else+orm",         # if-else+orm场景
        "switch",              # switch场景
        "dynamic_query",       # 动态查询场景
        "complex_control",     # 复杂控制流场景
        "fixed_params",        # 固定参数场景
        "if-else+switch",      # if-else+switch混合场景
        "conditional_chain",   # 条件链式查询场景
        "multi_branch_transaction",  # 多分支事务处理场景
        "state_machine_branch",      # 状态机式分支场景
        "conditional_meta"           # 条件分支+meta场景
    ]
    
    print("📋 测试场景列表:")
    for i, scenario in enumerate(all_scenarios, 1):
        print(f"  {i:2d}. {scenario}")
    print()
    
    # 测试配置
    test_config = {
        "base_output_dir": "workflow_output",
        "scenarios": all_scenarios,
        "count_per_scenario": 10,  # 每个场景生成10个案例
        "llm_server": "v3",        # 使用v3服务器
        "temperature": 0.7,        # 温度参数
        "max_tokens": 4096,        # 最大token数
        "parallel": True,          # 启用并行模式
        "max_workers": 4,          # 4个并行worker
        "validate": True           # 启用验证
    }
    
    print("⚙️ 测试配置:")
    for key, value in test_config.items():
        print(f"  {key}: {value}")
    print()
    
    try:
        # 执行反向SQL生成工作流
        print("🔄 开始执行反向SQL生成工作流...")
        print("-" * 60)
        
        result = await run_reverse_sql_generation_workflow(**test_config)
        
        print("-" * 60)
        
        # 分析结果
        if result["status"] == "success":
            print("✅ 测试成功完成!")
            print()
            print("📊 测试结果统计:")
            print(f"  - 总生成案例数: {result.get('total_count', 0)}")
            print(f"  - 验证通过案例数: {result.get('valid_count', 0)}")
            print(f"  - 成功率: {result.get('valid_count', 0)/result.get('total_count', 1)*100:.1f}%" if result.get('total_count', 0) > 0 else "  - 成功率: 0%")
            print(f"  - 工作流摘要文件: {result.get('workflow_summary', 'N/A')}")
            print()
            
            # 分析每个场景的结果
            if "generated_cases" in result:
                generated_cases = result["generated_cases"]
                print("📈 各场景生成统计:")
                scenario_stats = {}
                
                for case_key, case_data in generated_cases.items():
                    # 从case_key中提取场景信息
                    # case_key格式通常是: "scenario_complexity_index"
                    parts = case_key.split("_")
                    if len(parts) >= 2:
                        scenario = parts[0]
                        if scenario not in scenario_stats:
                            scenario_stats[scenario] = {"total": 0, "valid": 0}
                        scenario_stats[scenario]["total"] += 1
                        
                        # 检查案例是否有效
                        if case_data.get("sql_statement_list") and case_data.get("orm_code"):
                            scenario_stats[scenario]["valid"] += 1
                
                # 打印场景统计
                for scenario in all_scenarios:
                    stats = scenario_stats.get(scenario, {"total": 0, "valid": 0})
                    success_rate = stats["valid"] / stats["total"] * 100 if stats["total"] > 0 else 0
                    print(f"  - {scenario:25s}: {stats['valid']:2d}/{stats['total']:2d} ({success_rate:5.1f}%)")
                
                print()
                
                # 检查是否有失败的场景
                failed_scenarios = []
                for scenario in all_scenarios:
                    stats = scenario_stats.get(scenario, {"total": 0, "valid": 0})
                    if stats["total"] == 0:
                        failed_scenarios.append(scenario)
                
                if failed_scenarios:
                    print("⚠️  失败的场景:")
                    for scenario in failed_scenarios:
                        print(f"  - {scenario}")
                    print()
                
                # 检查成功率较低的场景
                low_success_scenarios = []
                for scenario in all_scenarios:
                    stats = scenario_stats.get(scenario, {"total": 0, "valid": 0})
                    if stats["total"] > 0 and stats["valid"] / stats["total"] < 0.5:
                        low_success_scenarios.append(scenario)
                
                if low_success_scenarios:
                    print("⚠️  成功率较低的场景 (< 50%):")
                    for scenario in low_success_scenarios:
                        stats = scenario_stats.get(scenario, {"total": 0, "valid": 0})
                        success_rate = stats["valid"] / stats["total"] * 100
                        print(f"  - {scenario}: {success_rate:.1f}%")
                    print()
            
            print("🎉 全面测试完成!")
            return result
            
        else:
            print("❌ 测试失败!")
            print(f"错误信息: {result.get('error', '未知错误')}")
            return result
            
    except Exception as e:
        print(f"❌ 测试执行异常: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


async def test_single_scenario(scenario: str, count: int = 5):
    """测试单个场景
    
    Args:
        scenario: 场景名称
        count: 生成数量
    """
    print(f"🎯 测试单个场景: {scenario}")
    print("=" * 50)
    
    test_config = {
        "base_output_dir": f"single_test_output_{scenario}",
        "scenarios": [scenario],
        "count_per_scenario": count,
        "llm_server": "v3",
        "temperature": 0.7,
        "max_tokens": 4096,
        "parallel": False,  # 单个场景测试使用串行模式
        "max_workers": 1,
        "validate": True
    }
    
    result = await run_reverse_sql_generation_workflow(**test_config)
    
    if result["status"] == "success":
        print(f"✅ {scenario} 测试成功!")
        print(f"  - 生成案例数: {result.get('total_count', 0)}")
        print(f"  - 验证通过数: {result.get('valid_count', 0)}")
    else:
        print(f"❌ {scenario} 测试失败: {result.get('error', '未知错误')}")
    
    return result


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="反向SQL生成全面测试")
    parser.add_argument("--scenario", type=str, help="测试单个场景")
    parser.add_argument("--count", type=int, default=10, help="每个场景生成的数量")
    parser.add_argument("--all", action="store_true", help="测试所有场景")
    
    args = parser.parse_args()
    
    if args.scenario:
        # 测试单个场景
        await test_single_scenario(args.scenario, args.count)
    elif args.all:
        # 测试所有场景
        await test_all_scenarios()
    else:
        # 默认测试所有场景
        print("默认测试所有场景，每个场景生成10个案例")
        await test_all_scenarios()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main()) 