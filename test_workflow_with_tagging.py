#!/usr/bin/env python3
"""
测试带有SQL完整性检查和标签功能的工作流
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent))

from data_processing.workflow.workflow_manager import run_complete_workflow_from_raw_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """主函数"""
    print("🚀 开始测试带有LLM标签功能的数据处理工作流")
    
    # 配置参数
    data_dir = "datasets/claude_output"  # 原始数据目录
    keywords = None  # 使用默认GORM关键词
    output_dir = "workflow_output"
    
    try:
        # 运行完整工作流
        result = run_complete_workflow_from_raw_data(
            data_dir=data_dir,
            keywords=keywords,
            base_output_dir=output_dir
        )
        
        print(f"\n✅ 工作流执行成功!")
        print(f"📁 输出目录: {result['workflow_directory']}")
        print(f"📄 最终数据: {result['final_data_path']}")
        print(f"📋 摘要文件: {result['summary_path']}")
        
        # 显示标签结果
        if 'tagging_result' in result:
            tagging = result['tagging_result']
            print(f"\n🏷️ SQL完整性检查结果:")
            print(f"   📊 总记录: {tagging['input_records']:,}")
            print(f"   ⚠️  缺少信息: {tagging['lack_info_records']:,}")
            print(f"   ✅ 完整记录: {tagging['complete_records']:,}")
            print(f"   ❌ 错误记录: {tagging['error_records']:,}")
            print(f"   📈 缺少信息率: {tagging['lack_info_rate']:.2f}%")
        
    except Exception as e:
        print(f"❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 