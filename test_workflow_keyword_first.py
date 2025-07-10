#!/usr/bin/env python3
# 从workflow_output/workflow_20250709_205236 继续执行remove_no_sql_records步骤
#nohup uv run python test_workflow_keyword_first.py --resume workflow_output/workflow_20250709_205236 --from-step remove_no_sql_records >> output.txt 2>&1 &
"""
测试以关键词提取优先的新工作流
"""

import logging
import sys
import argparse
from pathlib import Path

# 将项目根目录加入 Python 路径，方便导入
sys.path.append(str(Path(__file__).parent))

from data_processing.workflow.workflow_manager import run_keyword_first_workflow_from_raw_data, WorkflowManager

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
    parser.add_argument('--reanalyze-no-sql', action='store_true', default=True,
                        help='在remove_no_sql_records步骤中是否重新分析NO SQL记录 (默认: True)')
    parser.add_argument('--apply-fix', action='store_true', default=True,
                        help='在redundant_sql_validation步骤中是否应用修复 (默认: True)')
    
    return parser.parse_args()


def run_new_workflow(args):
    """运行全新的工作流"""
    print("🚀 开始运行全新的关键词优先数据处理工作流")
    
    result = run_keyword_first_workflow_from_raw_data(
        data_dir=args.data_dir,
        keywords=args.keywords,
        base_output_dir=args.output_dir
    )
    
    print("\n✅ 工作流执行成功!")
    print(f"📁 输出目录: {result['workflow_directory']}")
    print(f"📄 最终数据: {result['final_data_path']}")
    print(f"📋 摘要文件: {result['summary_path']}")
    
    return result


def run_resume_workflow(args):
    """运行resume工作流"""
    print(f"🔄 从工作流目录 {args.resume} 继续执行")
    
    # 在resume模式下，使用临时目录创建WorkflowManager，避免在workflow_output中创建新目录
    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp(prefix="temp_workflow_")
    
    try:
        # 创建工作流管理器，使用临时目录避免创建不需要的目录
        workflow = WorkflowManager(base_output_dir=temp_dir)
    
    if not workflow.load_from_existing_workflow(args.resume):
        print(f"❌ 无法从工作流目录加载状态: {args.resume}")
        return None
    
    print(f"✅ 成功加载工作流状态")
        
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"⚠️ 清理临时目录失败: {e}")
    
    # 如果指定了步骤，从该步骤开始执行
    if args.from_step:
        print(f"🎯 从步骤 '{args.from_step}' 开始执行")
        
        # 准备步骤参数
        step_kwargs = {}
        if args.from_step == 'remove_no_sql_records':
            step_kwargs['reanalyze_no_sql'] = args.reanalyze_no_sql
        elif args.from_step == 'redundant_sql_validation':
            step_kwargs['apply_fix'] = args.apply_fix
        elif args.from_step == 'keyword_extraction':
            step_kwargs['keywords'] = args.keywords
        
        try:
            # 执行单个步骤
            result = workflow.resume_from_step(args.from_step, **step_kwargs)
            
            # 如果不是最后一步，继续执行后续步骤
            if args.from_step != 'export_final_data':
                print("🔄 继续执行后续步骤...")
                
                # 定义步骤顺序
                step_order = [
                    'remove_no_sql_records',
                    'redundant_sql_validation', 
                    'export_final_data'
                ]
                
                # 找到当前步骤的位置
                current_index = step_order.index(args.from_step)
                
                # 执行后续步骤
                for next_step in step_order[current_index + 1:]:
                    print(f"🔄 执行步骤: {next_step}")
                    
                    next_kwargs = {}
                    if next_step == 'remove_no_sql_records':
                        next_kwargs['reanalyze_no_sql'] = args.reanalyze_no_sql
                    elif next_step == 'redundant_sql_validation':
                        next_kwargs['apply_fix'] = args.apply_fix
                    
                    result = workflow.resume_from_step(next_step, **next_kwargs)
            
            print("\n✅ Resume工作流执行成功!")
            print(f"📁 工作流目录: {workflow.workflow_dir}")
            
            if isinstance(result, dict) and 'final_data_path' in result:
                print(f"📄 最终数据: {result['final_data_path']}")
                print(f"📋 摘要文件: {result['summary_path']}")
            
            return result
            
        except Exception as e:
            print(f"❌ Resume工作流执行失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    else:
        print("⚠️ 未指定--from-step参数，请指定要从哪个步骤开始执行")
        print("可用步骤: remove_no_sql_records, redundant_sql_validation, sql_cleaning, keyword_extraction, export_final_data")
        return None


def main():
    """主函数"""
    args = parse_args()
    
    try:
        if args.resume:
            # Resume模式
            result = run_resume_workflow(args)
        else:
            # 新工作流模式
            result = run_new_workflow(args)
        
        if result:
            # 显示结果摘要
            if 'extraction_result' in result:
                ext_res = result['extraction_result']
                print("\n🔑 关键词提取结果:")
                print(f"   📊 输入记录: {ext_res.get('input_records', 0):,}")
                print(f"   🎯 提取记录: {ext_res.get('extracted_records', 0):,}")
                print(f"   📈 提取率: {ext_res.get('extraction_rate', 0.0):.2f}%")

            if 'cleaning_result' in result:
                clean_res = result['cleaning_result']
                print("\n🧹 SQL 清洗结果:")
                print(f"   📊 输入记录: {clean_res.get('input_records', 0):,}")
                print(f"   📊 输出记录: {clean_res.get('output_records', 0):,}")
                print(f"   🗑️  移除无效 SQL: {clean_res.get('invalid_sql_removed', 0):,}")
                print(f"   ✏️  修改记录: {clean_res.get('records_modified', 0):,}")
            
            return 0
        else:
            return 1

    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 