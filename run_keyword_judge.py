import argparse
import asyncio
import sys
from pathlib import Path

# 支持直接脚本运行
sys.path.append(str(Path(__file__).parent.parent.parent))
from data_processing.workflow.workflow_manager import WorkflowManager

def main():
    parser = argparse.ArgumentParser(description="对指定数据文件进行LLM关键词分析并全部导出（含/不含关键词均保留）")
    parser.add_argument('--input', required=True, help='输入数据文件（JSON，记录列表）')
    parser.add_argument('--output', default='final_processed_data.json', help='输出文件名（默认final_processed_data.json）')
    parser.add_argument('--output_dir', default='workflow_output', help='工作流输出目录')
    args = parser.parse_args()

    # 初始化WorkflowManager
    workflow = WorkflowManager(base_output_dir=args.output_dir)

    # 执行分析与导出
    result_path = asyncio.run(
        workflow.extract_keywords_from_file_and_export_all(
            input_file=args.input,
            output_file=args.output
        )
    )
    print(f"✅ 所有LLM分析后的数据已导出: {result_path}")

if __name__ == '__main__':
    main() 