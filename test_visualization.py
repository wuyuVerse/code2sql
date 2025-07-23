#!/usr/bin/env python3
"""
测试工作流可视化功能
"""

import json
import tempfile
from pathlib import Path
from utils.workflow_visualizer import generate_workflow_visualization

def create_test_workflow_summary():
    """创建测试用的工作流摘要数据"""
    test_summary = {
        'workflow_id': 'workflow_20250717_143000',
        'start_time': '2025-07-17T14:30:00',
        'end_time': '2025-07-17T15:30:00',
        'total_steps': 6,
        'steps': [
            {
                'step_name': 'data_loading_step',
                'step_type': 'data_loading',
                'timestamp': '2025-07-17T14:30:00',
                'total_records_loaded': 10000,
                'data_size_mb': 15.5
            },
            {
                'step_name': 'keyword_extraction_step1',
                'step_type': 'keyword_extraction',
                'timestamp': '2025-07-17T14:35:00',
                'input_records': 10000,
                'extracted_records': 2500,
                'extraction_rate': 25.0
            },
            {
                'step_name': 'process_keyword_data_step2',
                'step_type': 'keyword_data_processing',
                'timestamp': '2025-07-17T14:45:00',
                'input_records': 2500,
                'output_records': 2500,
                'processed_successfully': 2300,
                'processing_failed': 200
            },
            {
                'step_name': 'sql_cleaning_after_extraction',
                'step_type': 'sql_cleaning',
                'timestamp': '2025-07-17T15:00:00',
                'input_records': 7500,
                'output_records': 6800,
                'records_modified': 700,
                'modification_rate': 9.3,
                'invalid_sql_removed': 500,
                'valid_sql_retained': 6300
            },
            {
                'step_name': 'remove_no_sql_records_step',
                'step_type': 'remove_no_sql_records',
                'timestamp': '2025-07-17T15:10:00',
                'input_records': 6800,
                'output_records': 6200,
                'removed_records': 600,
                'reanalyzed_records': 100
            },
            {
                'step_name': 'redundant_sql_validation_with_fix',
                'step_type': 'redundant_sql_validation',
                'timestamp': '2025-07-17T15:20:00',
                'total_candidates': 6200,
                'validation_stats': {
                    'modified_records': 150,
                    'correct_records': 5800,
                    'incorrect_records': 250
                }
            },
            {
                'step_name': 'control_flow_validation_step',
                'step_type': 'control_flow_validation',
                'timestamp': '2025-07-17T15:25:00',
                'total_records': 8700,
                'control_flow_records': 300,
                'control_flow_rate': 3.4,
                'correct_records': 280,
                'incorrect_records': 20,
                'error_records': 0,
                'regenerated_records': 15
            }
        ],
        'final_data_count': 8700,
        'extracted_data_count': 2500,
        'workflow_directory': '/tmp/test_workflow'
    }
    return test_summary

def test_visualization():
    """测试可视化功能"""
    print("🧪 开始测试工作流可视化功能...")
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 创建测试摘要文件
        test_summary = create_test_workflow_summary()
        summary_file = temp_path / "test_workflow_summary.json"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(test_summary, f, ensure_ascii=False, indent=2)
        
        print(f"📄 测试摘要文件已创建: {summary_file}")
        
        # 生成可视化图表
        try:
            visualization_dir = temp_path / "visualizations"
            results = generate_workflow_visualization(
                str(summary_file),
                str(visualization_dir),
                "test_20250717"
            )
            
            if results:
                print("✅ 可视化图表生成成功!")
                print("📊 生成的文件:")
                for chart_type, filepath in results.items():
                    print(f"   📈 {chart_type}: {filepath}")
                    
                    # 检查文件是否存在
                    if Path(filepath).exists():
                        file_size = Path(filepath).stat().st_size
                        print(f"      ✅ 文件存在，大小: {file_size:,} 字节")
                    else:
                        print(f"      ❌ 文件不存在: {filepath}")
            else:
                print("❌ 可视化图表生成失败")
                
        except Exception as e:
            print(f"❌ 生成可视化图表时出错: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_visualization() 