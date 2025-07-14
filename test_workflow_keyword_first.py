#!/usr/bin/env python3
"""
测试以关键词提取优先的新工作流
"""

import logging
import sys
import argparse
from pathlib import Path

# 将项目根目录加入 Python 路径
sys.path.append(str(Path(__file__).resolve().parents[2]))

# --- 从新位置导入主函数 ---
from data_processing.workflow.workflow_manager import run_new_workflow, run_resume_workflow

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='运行关键词优先的数据处理工作流')
    
    # 基本参数
    parser.add_argument('--data-dir', default='datasets/claude_output',
                        help='原始数据目录 (默认: datasets/claude_output)')
    parser.add_argument('--output-dir', default='workflow_output',
                        help='输出基目录 (默认: workflow_output)')
    parser.add_argument('--keywords', nargs='*', default=None,
                        help='关键词列表，如果不指定则使用默认GORM关键词')
    
    # Resume相关参数
    parser.add_argument('--resume', type=str, metavar='WORKFLOW_DIR',
                        help='从指定的工作流目录继续执行')
    parser.add_argument('--from-step', type=str, metavar='STEP_NAME',
                        choices=['remove_no_sql_records', 'redundant_sql_validation', 
                                'sql_cleaning', 'keyword_extraction', 'export_final_data'],
                        help='从指定步骤开始执行')
    
    # 控制标志
    parser.add_argument('--test', action='store_true',
                        help='开启测试模式，只处理10条数据')
    parser.add_argument('--reanalyze-no-sql', action='store_true', default=True,
                        help='在remove_no_sql_records步骤中是否重新分析NO SQL记录 (默认: True)')
    parser.add_argument('--apply-fix', action='store_true', default=True,
                        help='在redundant_sql_validation步骤中是否应用修复 (默认: True)')
    
    return parser.parse_args()


def main():
    """主函数，调用 workflow_manager 中的逻辑"""
    args = parse_args()
    
    try:
        if args.resume:
            result = run_resume_workflow(args)
        else:
            result = run_new_workflow(args)
        
        if result:
            return 0  # 成功
        else:
            return 1  # 失败

    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 