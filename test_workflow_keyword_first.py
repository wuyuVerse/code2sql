#!/usr/bin/env python3
"""
测试以关键词提取优先的新工作流
"""

import logging
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径，方便导入
sys.path.append(str(Path(__file__).parent))

from data_processing.workflow.workflow_manager import run_keyword_first_workflow_from_raw_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """主函数"""
    print("🚀 开始测试关键词优先的数据处理工作流")

    # 配置参数
    data_dir = "datasets/claude_output"  # 原始数据目录
    keywords = None  # 使用默认 GORM 关键词
    output_dir = "workflow_output"

    try:
        # 运行关键词优先工作流
        result = run_keyword_first_workflow_from_raw_data(
            data_dir=data_dir,
            keywords=keywords,
            base_output_dir=output_dir
        )

        print("\n✅ 工作流执行成功!")
        print(f"📁 输出目录: {result['workflow_directory']}")
        print(f"📄 最终数据: {result['final_data_path']}")
        print(f"📋 摘要文件: {result['summary_path']}")

        # 显示关键词提取结果
        ext_res = result.get('extraction_result', {})
        if ext_res:
            print("\n🔑 关键词提取结果:")
            print(f"   📊 输入记录: {ext_res.get('input_records', 0):,}")
            print(f"   🎯 提取记录: {ext_res.get('extracted_records', 0):,}")
            print(f"   📈 提取率: {ext_res.get('extraction_rate', 0.0):.2f}%")

        # 显示清洗结果
        clean_res = result.get('cleaning_result', {})
        if clean_res:
            print("\n🧹 SQL 清洗结果:")
            print(f"   📊 输入记录: {clean_res.get('input_records', 0):,}")
            print(f"   📊 输出记录: {clean_res.get('output_records', 0):,}")
            print(f"   🗑️  移除无效 SQL: {clean_res.get('invalid_sql_removed', 0):,}")
            print(f"   ✏️  修改记录: {clean_res.get('records_modified', 0):,}")

    except Exception as e:
        print(f"❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main()) 