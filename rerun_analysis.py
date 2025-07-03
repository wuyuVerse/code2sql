#!/usr/bin/env python3
"""
重新分析被标记为 <NO SQL GENERATE> 的记录

使用优化的提示词和高并发设置，对指定数据集中的记录进行重新分析，
以验证它们是否真的无法生成SQL。

此脚本现在是 `validation.validator.RerunValidator` 的一个入口点。
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# 确保项目根目录在Python路径中，以便能够找到 `validation` 模块
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data_processing.validation import RerunValidator

logger = logging.getLogger(__name__)

def main():
    """主函数，用于解析参数并启动验证器"""
    parser = argparse.ArgumentParser(description="通过配置文件重新分析被标记为 <NO SQL GENERATE> 的记录")
    parser.add_argument(
        "--config-file",
        type=str,
        default="config/rerun_config.yaml",
        help="指定包含运行参数的YAML配置文件路径"
    )
    args = parser.parse_args()

    # 初始化并运行验证器
    validator = RerunValidator(config_path=args.config_file)
    
    try:
        asyncio.run(validator.run_rerun_analysis())
    except KeyboardInterrupt:
        print("\n操作被用户中断。")
    except Exception as e:
        logger.error(f"发生未预料的错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 