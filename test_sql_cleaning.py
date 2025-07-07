#!/usr/bin/env python3
"""
测试SQL清洗功能（包含ORM SQL指纹分析）
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from data_processing.workflow.workflow_manager import WorkflowManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """主函数"""
    print("🧹 开始测试SQL清洗功能（包含ORM SQL指纹分析）")
    
    # 配置参数
    data_dir = "datasets/claude_output"  # 原始数据目录
    output_dir = "workflow_output"
    
    try:
        # 创建工作流管理器
        workflow = WorkflowManager(base_output_dir=output_dir)
        
        print(f"📁 工作流输出目录: {workflow.workflow_dir}")
        
        # 步骤1: 加载原始数据集
        print("\n📥 步骤1: 加载原始数据集...")
        load_result = workflow.load_raw_dataset(data_dir)
        print(f"   ✅ 成功加载 {load_result['total_records_loaded']:,} 条记录")
        
        # 获取原始数据统计
        original_data = workflow.current_data
        if original_data is None:
            print("❌ 无法获取原始数据")
            return 1
        total_records = len(original_data)
        
        # 统计原始SQL数据
        sql_stats = {
            'records_with_sql': 0,
            'total_sql_items': 0,
            'empty_sql_lists': 0,
            'records_with_orm_code': 0,
            'unique_orm_codes': set(),
            'unique_callers': set()
        }
        
        for record in original_data:
            sql_list = record.get('sql_statement_list', [])
            orm_code = record.get('orm_code', '')
            caller = record.get('caller', '')
            
            if sql_list:
                if isinstance(sql_list, list) and len(sql_list) > 0:
                    sql_stats['records_with_sql'] += 1
                    sql_stats['total_sql_items'] += len(sql_list)
                else:
                    sql_stats['empty_sql_lists'] += 1
            else:
                sql_stats['empty_sql_lists'] += 1
            
            if orm_code and orm_code.strip():
                sql_stats['records_with_orm_code'] += 1
                sql_stats['unique_orm_codes'].add(orm_code.strip())
            
            if caller and caller.strip():
                sql_stats['unique_callers'].add(caller.strip())
        
        print(f"\n📊 原始数据统计:")
        print(f"   📋 总记录数: {total_records:,}")
        print(f"   📝 有SQL的记录: {sql_stats['records_with_sql']:,}")
        print(f"   📄 总SQL项数: {sql_stats['total_sql_items']:,}")
        print(f"   📭 空SQL列表: {sql_stats['empty_sql_lists']:,}")
        print(f"   🔧 有ORM代码的记录: {sql_stats['records_with_orm_code']:,}")
        print(f"   🏷️ 唯一ORM代码数: {len(sql_stats['unique_orm_codes']):,}")
        print(f"   👤 唯一caller数: {len(sql_stats['unique_callers']):,}")
        
        # 步骤2: 执行SQL清洗（包含ORM指纹分析）
        print("\n🧹 步骤2: 执行SQL清洗（包含ORM指纹分析）...")
        cleaning_result = workflow.run_sql_cleaning("sql_cleaning_with_orm_analysis")
        
        print(f"   ✅ SQL清洗完成!")
        print(f"   📊 清洗统计:")
        print(f"      📥 输入记录: {cleaning_result['input_records_count']:,}")
        print(f"      📤 输出记录: {cleaning_result['output_records_count']:,}")
        print(f"      🔄 修改记录: {cleaning_result['records_modified']:,}")
        print(f"      ❌ 移除无效SQL: {cleaning_result['invalid_sql_removed']:,}")
        print(f"      ✅ 保留有效SQL: {cleaning_result['valid_sql_retained']:,}")
        print(f"      🔧 保留参数依赖SQL: {cleaning_result['param_dependent_sql_retained']:,}")
        print(f"      📭 发现空SQL列表: {cleaning_result.get('empty_sql_lists_found', 0):,}")
        print(f"      🗂️ 清洗后变空列表: {cleaning_result.get('lists_emptied_after_cleaning', 0):,}")
        
        # 显示ORM分析结果
        if 'orm_analysis_summary' in cleaning_result and cleaning_result['orm_analysis_summary']:
            orm_summary = cleaning_result['orm_analysis_summary']
            print(f"\n🔍 ORM SQL指纹分析结果:")
            print(f"   📊 分析的ORM代码数: {orm_summary['total_orm_codes']:,}")
            print(f"   👥 总caller数: {orm_summary['total_callers']:,}")
            print(f"   📝 总SQL记录数: {orm_summary['total_sql_records']:,}")
            print(f"   🔄 有多个caller的ORM: {orm_summary['orm_with_multiple_callers']:,}")
            print(f"   🔁 有冗余SQL的ORM: {orm_summary['orm_with_redundant_sql']:,}")
            print(f"   ⚠️ 有潜在缺漏的ORM: {orm_summary['orm_with_potential_missing_extra']:,}")
            print(f"   📈 平均每ORM的caller数: {orm_summary['average_callers_per_orm']:.2f}")
            print(f"   📈 平均每ORM的SQL数: {orm_summary['average_sql_per_orm']:.2f}")
        
        # 显示输出文件路径
        if 'orm_analysis_reports' in cleaning_result and cleaning_result['orm_analysis_reports']:
            reports = cleaning_result['orm_analysis_reports']
            print(f"\n📄 生成的分析报告文件:")
            print(f"   📊 ORM统计报告: {reports['orm_stats_file']}")
            print(f"   🔁 冗余SQL报告: {reports['redundant_sql_file']}")
            print(f"   ⚠️ 缺漏SQL报告: {reports['missing_extra_file']}")
            
            if 'summary' in reports:
                summary = reports['summary']
                print(f"\n📋 报告摘要:")
                print(f"   📊 总ORM代码数: {summary['total_orm_codes']:,}")
                print(f"   🔁 有冗余SQL的ORM: {summary['orm_with_redundant_sql']:,}")
                print(f"   ⚠️ 有缺漏/额外SQL的ORM: {summary['orm_with_missing_extra']:,}")
        
        # 显示输出目录信息
        print(f"\n📁 清洗结果已保存到: {cleaning_result['output_directory']}")
        
        # 检查是否生成了标记冗余SQL的文件
        from pathlib import Path
        output_path = Path(cleaning_result['output_directory'])
        marked_file = output_path / "cleaned_records_with_redundant_marks.json"
        if marked_file.exists():
            print(f"   🏷️ 冗余SQL标记文件: {marked_file}")
        
        # 保存工作流摘要
        summary_path = workflow.save_workflow_summary()
        print(f"   📋 工作流摘要: {summary_path}")
        
        print(f"\n🎉 SQL清洗测试完成!")
        
    except Exception as e:
        print(f"❌ SQL清洗测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 