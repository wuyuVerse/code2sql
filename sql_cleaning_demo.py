#!/usr/bin/env python3
"""
SQL清洗工作流演示脚本

演示如何使用数据清洗workflow来清洗提取的数据中的无效SQL
"""

import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """主函数"""
    print("🚀 开始从原始数据集的完整SQL清洗workflow演示...")
    
    try:
        # 导入工作流管理器
        from data_processing import get_workflow_manager
        WorkflowManager, run_complete_sql_cleaning_workflow, run_complete_workflow_from_raw_data = get_workflow_manager()
        
        # 检查是否存在原始数据集
        raw_data_path = "datasets/claude_output"
        if not Path(raw_data_path).exists():
            print(f"❌ 未找到原始数据目录: {raw_data_path}")
            print("请确保原始数据集存在")
            return
        
        print(f"📁 使用原始数据集: {raw_data_path}")
        print("🎯 将执行：数据加载 -> 关键词提取 -> SQL清洗 -> 结果导出")
        
        # 运行从原始数据集开始的完整工作流
        result = run_complete_workflow_from_raw_data(
            data_dir=raw_data_path,
            keywords=None,  # 使用GORM预定义关键词
            base_output_dir="workflow_output"
        )
        
        print("\n✅ SQL清洗工作流完成!")
        print(f"📊 工作流目录: {result['workflow_directory']}")
        print(f"📄 最终数据: {result['final_data_path']}")
        print(f"📋 摘要文件: {result['summary_path']}")
        
        # 显示清洗统计
        cleaning_stats = result['cleaning_result']
        print(f"\n📈 清洗统计:")
        print(f"   输入记录: {cleaning_stats['input_records_count']:,}")
        print(f"   输出记录: {cleaning_stats['output_records_count']:,}")
        print(f"   修改记录: {cleaning_stats['records_modified']:,}")
        print(f"   移除无效SQL: {cleaning_stats['invalid_sql_removed']:,}")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保数据处理模块正确安装")
    except FileNotFoundError as e:
        print(f"❌ 文件未找到: {e}")
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()


def run_custom_workflow():
    """运行自定义工作流示例"""
    print("\n🔧 运行自定义工作流示例...")
    
    try:
        from data_processing import get_workflow_manager, get_data_cleaner
        WorkflowManager, _, _ = get_workflow_manager()
        SQLCleaner = get_data_cleaner()
        
        # 创建工作流管理器
        workflow = WorkflowManager("custom_workflow_output")
        
        # 步骤1: 加载数据
        extracted_data_path = "extracted_data/gorm_keywords_20250703_121119"
        load_result = workflow.load_extracted_data(extracted_data_path)
        print(f"✅ 数据加载完成: {load_result['records_loaded']:,} 条记录")
        
        # 步骤2: SQL清洗
        cleaning_result = workflow.run_sql_cleaning("custom_sql_cleaning")
        print(f"✅ SQL清洗完成: 移除了 {cleaning_result['invalid_sql_removed']:,} 个无效SQL")
        
        # 步骤3: 导出和总结
        final_path = workflow.export_final_data("custom_cleaned_data.json")
        summary_path = workflow.save_workflow_summary()
        
        workflow.print_workflow_summary()
        
        print(f"\n🎉 自定义工作流完成!")
        print(f"📄 最终数据: {final_path}")
        print(f"📋 摘要文件: {summary_path}")
        
    except Exception as e:
        print(f"❌ 自定义工作流失败: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--custom":
        run_custom_workflow()
    else:
        main()
        
        # 可选：也运行自定义工作流示例
        user_input = input("\n是否运行自定义工作流示例? (y/N): ")
        if user_input.lower() in ['y', 'yes']:
            run_custom_workflow() 