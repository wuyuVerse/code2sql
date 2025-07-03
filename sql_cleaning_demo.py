#!/usr/bin/env python3
"""
SQL清洗工作流演示脚本

展示新架构的数据处理工作流：
1. 加载原始数据集
2. SQL清洗
3. 关键词提取
4. 特殊处理（预留）
5. 数据合并

使用方法:
python sql_cleaning_demo.py
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """主演示函数"""
    print("🚀 数据处理工作流演示 - 新架构")
    print("=" * 60)
    
    # 原始数据目录
    data_dir = "./datasets/claude_output"
    
    if not Path(data_dir).exists():
        print(f"❌ 错误: 数据目录 '{data_dir}' 不存在")
        print("请确保数据目录包含必要的输入文件")
        return 1
    
    choice = None
    if len(sys.argv) > 1:
        choice = sys.argv[1]
        print(f"✅ 已通过命令行参数选择模式: {choice}")
    else:
        # 工作流选项
        print("请选择工作流模式:")
        print("1. 完整新架构工作流（推荐）- 从原始数据集开始")
        print("2. 自定义步骤演示 - 逐步展示各处理阶段")
        print("3. 测试工作流 - 使用小样本数据")
        print("\n💡 您也可以通过命令行参数指定模式, 例如: python sql_cleaning_demo.py 1")
        choice = input("请输入选择 (1-3): ").strip()
    
    try:
        if choice == "1":
            run_complete_new_workflow(data_dir)
        elif choice == "2":
            run_step_by_step_demo(data_dir)
        elif choice == "3":
            run_test_workflow(data_dir)
        else:
            print(f"❌ 无效选择: '{choice}'。将运行默认的完整工作流。")
            run_complete_new_workflow(data_dir)
        
        print("\n✅ 工作流演示完成!")
        return 0
        
    except Exception as e:
        logger.error(f"演示执行失败: {e}")
        print(f"\n❌ 演示失败: {e}")
        print("请检查数据目录和依赖是否正确配置")
        return 1

def run_complete_new_workflow(data_dir: str):
    """运行完整的新架构工作流"""
    print("\n🔄 运行完整新架构工作流")
    print("-" * 40)
    
    try:
        from data_processing.workflow import run_complete_workflow_from_raw_data
        
        # 运行完整工作流
        result = run_complete_workflow_from_raw_data(
            data_dir=data_dir,
            keywords=None,  # 使用默认GORM关键词
            base_output_dir="workflow_output"
        )
        
        print(f"\n🎉 新架构工作流执行成功!")
        print(f"📁 工作流目录: {result['workflow_directory']}")
        print(f"📄 最终数据: {result['final_data_path']}")
        print(f"📊 工作流摘要: {result['summary_path']}")
        
        # 显示关键统计信息
        if 'cleaning_result' in result:
            cleaning = result['cleaning_result']
            print(f"\n📈 SQL清洗统计:")
            print(f"   输入记录: {cleaning['input_records_count']:,}")
            print(f"   移除无效SQL: {cleaning['invalid_sql_removed']:,}")
            print(f"   修改记录: {cleaning['records_modified']:,}")
        
        if 'extraction_result' in result:
            extraction = result['extraction_result']
            print(f"\n🎯 关键词提取统计:")
            print(f"   输入记录: {extraction['input_records']:,}")
            print(f"   提取记录: {extraction['extracted_records']:,}")
            print(f"   提取率: {extraction['extraction_rate']:.2f}%")
        
        if 'merge_result' in result:
            merge = result['merge_result']
            print(f"\n🔄 数据合并统计:")
            print(f"   总记录数: {merge['total_records']:,}")
            print(f"   更新记录: {merge['updated_records']:,}")
            print(f"   更新率: {merge['update_rate']:.2f}%")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保data_processing模块已正确安装")
    except Exception as e:
        print(f"❌ 执行错误: {e}")
        raise

def run_step_by_step_demo(data_dir: str):
    """运行逐步演示"""
    print("\n🔧 逐步演示新架构工作流")
    print("-" * 40)
    
    try:
        from data_processing.workflow.workflow_manager import WorkflowManager
        
        # 创建工作流管理器
        workflow = WorkflowManager("step_by_step_demo")
        
        print("📥 步骤1: 加载原始数据集...")
        load_result = workflow.load_raw_dataset(data_dir)
        print(f"   ✅ 加载了 {load_result['total_records_loaded']:,} 条记录")
        
        input("\n按回车继续下一步...")
        
        print("🧹 步骤2: SQL清洗全体数据...")
        cleaning_result = workflow.run_sql_cleaning("sql_cleaning_step1")
        print(f"   ✅ 移除了 {cleaning_result['invalid_sql_removed']:,} 个无效SQL")
        print(f"   ✅ 修改了 {cleaning_result['records_modified']:,} 条记录")
        
        input("\n按回车继续下一步...")
        
        print("🎯 步骤3: 从清洗数据中提取关键词...")
        extraction_result = workflow.extract_keyword_data(None, "keyword_extraction_step2")
        print(f"   ✅ 提取了 {extraction_result['extracted_records']:,} 条匹配记录")
        print(f"   ✅ 提取率: {extraction_result['extraction_rate']:.2f}%")
        
        input("\n按回车继续下一步...")
        
        print("🔧 步骤4: 特殊处理提取的数据...")
        processing_result = workflow.process_extracted_data("special_processing_step3")
        print(f"   ✅ 处理了 {processing_result['input_records']:,} 条记录")
        print("   💡 当前为预留接口，可添加数据增强、标注等功能")
        
        input("\n按回车继续下一步...")
        
        print("🔄 步骤5: 将处理数据合并回原数据集...")
        merge_result = workflow.merge_processed_data_back("merge_back_step4")
        print(f"   ✅ 更新了 {merge_result['updated_records']:,} 条记录")
        print(f"   ✅ 保持了 {merge_result['unchanged_records']:,} 条原始记录")
        
        print("\n📤 导出最终数据...")
        final_data_path = workflow.export_final_data("step_by_step_final.json")
        summary_path = workflow.save_workflow_summary()
        
        print(f"\n🎉 逐步演示完成!")
        print(f"📁 工作流目录: {workflow.workflow_dir}")
        print(f"📄 最终数据: {final_data_path}")
        print(f"📊 工作流摘要: {summary_path}")
        
        # 打印最终摘要
        workflow.print_workflow_summary()
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保data_processing模块已正确安装")
    except Exception as e:
        print(f"❌ 执行错误: {e}")
        raise

def run_test_workflow(data_dir: str):
    """运行测试工作流（小样本）"""
    print("\n🧪 运行测试工作流")
    print("-" * 40)
    
    try:
        from data_processing.workflow.workflow_manager import WorkflowManager
        
        # 创建工作流管理器
        workflow = WorkflowManager("test_workflow")
        
        # 步骤1: 加载原始数据集
        print("📥 加载原始数据集...")
        load_result = workflow.load_raw_dataset(data_dir)
        original_count = len(workflow.current_data)
        
        # 限制为小样本进行测试（前100条记录）
        if original_count > 100:
            workflow.current_data = workflow.current_data[:100]
            print(f"   📊 限制为前100条记录进行测试（原始: {original_count:,} 条）")
        
        # 步骤2: SQL清洗
        print("🧹 SQL清洗测试...")
        cleaning_result = workflow.run_sql_cleaning("test_sql_cleaning")
        
        # 步骤3: 关键词提取
        print("🎯 关键词提取测试...")
        extraction_result = workflow.extract_keyword_data(None, "test_keyword_extraction")
        
        # 步骤4: 特殊处理
        print("🔧 特殊处理测试...")
        processing_result = workflow.process_extracted_data("test_special_processing")
        
        # 步骤5: 数据合并
        print("🔄 数据合并测试...")
        merge_result = workflow.merge_processed_data_back("test_merge_back")
        
        # 导出结果
        final_data_path = workflow.export_final_data("test_final.json")
        summary_path = workflow.save_workflow_summary()
        
        print(f"\n🎉 测试工作流完成!")
        print(f"📊 测试统计:")
        print(f"   原始记录: {original_count:,}")
        print(f"   测试记录: {len(workflow.current_data):,}")
        print(f"   提取记录: {extraction_result['extracted_records']:,}")
        print(f"   更新记录: {merge_result['updated_records']:,}")
        
        print(f"\n📁 输出:")
        print(f"   工作流目录: {workflow.workflow_dir}")
        print(f"   最终数据: {final_data_path}")
        print(f"   摘要文件: {summary_path}")
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保data_processing模块已正确安装")
    except Exception as e:
        print(f"❌ 执行错误: {e}")
        raise

if __name__ == "__main__":
    sys.exit(main()) 