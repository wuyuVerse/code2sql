#!/usr/bin/env python3
"""
测试 SQL 清洗 + 冗余 SQL 验证工作流

步骤:
1. 加载原始数据集
2. 运行 SQL 清洗 (含 ORM 指纹分析)
3. 运行冗余 SQL 验证 (dry-run 或可选修复)

用法:
    python test_redundant_validation.py [data_dir] [--apply-fix]

默认 data_dir 为 "datasets/claude_output"，dry-run 模式。
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径，防止相对导入失败
sys.path.append(str(Path(__file__).parent))

from data_processing.workflow.workflow_manager import WorkflowManager

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def parse_args() -> tuple[str, bool]:
    """简单解析命令行参数"""
    data_dir = "datasets/claude_output"
    apply_fix = True

    if len(sys.argv) >= 2:
        data_dir = sys.argv[1]
    if len(sys.argv) >= 3 and sys.argv[2] in ("--apply-fix", "--fix", "-f"):
        apply_fix = True
    return data_dir, apply_fix


async def run_workflow(data_dir: str, apply_fix: bool) -> None:
    """执行工作流"""
    print("🧹 开始 SQL 清洗 + 冗余 SQL 验证 测试")

    # 创建工作流管理器
    workflow = WorkflowManager(base_output_dir="workflow_output")
    print(f"📁 工作流输出目录: {workflow.workflow_dir}")

    # 步骤 1: 加载数据
    print("\n📥 步骤 1: 加载原始数据集 …")
    load_info = workflow.load_raw_dataset(data_dir)
    print(f"   ✅ 已加载 {load_info['total_records_loaded']:,} 条记录")

    # 步骤 2: SQL 清洗 (含 ORM 分析)
    print("\n🧹 步骤 2: 执行 SQL 清洗 (含 ORM 指纹分析) …")
    cleaning_result = workflow.run_sql_cleaning("sql_cleaning_with_orm_analysis")
    print(f"   ✅ 清洗完成，输出记录: {cleaning_result['output_records_count']:,}")

    # 步骤 3: 冗余 SQL 验证
    mode = "修复" if apply_fix else "dry-run"
    print(f"\n🔍 步骤 3: 运行冗余 SQL 验证 ({mode}) …")
    validation_info = await workflow.run_redundant_sql_validation(
        apply_fix=apply_fix,
        step_name="redundant_sql_validation_test"
    )

    print("   ✅ 冗余 SQL 验证完成")
    print("   📊 统计:")

    total_candidates = validation_info.get('total_candidates', 0)
    v_stats = validation_info.get('validation_stats', {})
    type_stats = v_stats.get('type_stats', {}).get('redundant', {})
    step_stats = v_stats.get('step_stats', {})

    print(f"      📝 验证 SQL 项数: {total_candidates:,}")
    print(f"      🔁 冗余候选: {type_stats.get('total', 0):,}")
    print(f"      ✅ 确认冗余: {type_stats.get('confirmed', 0):,}")
    print(f"      ❓ 争议冗余: {type_stats.get('disputed', 0):,}")
    print(f"      ⚠️ LLM 错误: {step_stats.get('llm_errors', 0):,}")

    # 保存工作流摘要
    summary_path = workflow.save_workflow_summary()
    print(f"\n📋 工作流摘要已保存: {summary_path}")
    print("🎉 测试结束！")


def main() -> int:
    data_dir, apply_fix = parse_args()
    try:
        asyncio.run(run_workflow(data_dir, apply_fix))
    except KeyboardInterrupt:
        print("⏹️ 测试被用户中断")
        return 1
    except Exception as exc:
        print(f"❌ 测试失败: {exc}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main()) 

# uv run python test_redundant_validation.py --apply-fix