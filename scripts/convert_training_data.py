#!/usr/bin/env python3
"""
训练数据转换快速启动脚本

用于将workflow处理后的ORM数据转换为微调训练格式
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root))

from data_processing.converter.training_data_converter import TrainingDataConverter

def main():
    """主函数"""
    print("🚀 开始ORM到SQL训练数据转换...")
    
    converter = TrainingDataConverter()
    
    try:
        # 执行转换
        output_path, dataset_info = converter.run_conversion()
        
        print(f"\n✅ 数据转换完成!")
        print(f"📁 训练数据保存路径: {output_path}")
        print(f"📊 样本数量: {dataset_info[list(dataset_info.keys())[0]]['num_samples']}")
        print(f"📝 数据集信息: {converter.training_data_dir / 'dataset_info.json'}")
        print(f"\n🎯 下一步：")
        print(f"   1. 将数据复制到LLaMA-Factory数据目录")
        print(f"   2. 更新LLaMA-Factory的dataset_info.json")
        print(f"   3. 配置训练参数开始微调")
        
    except Exception as e:
        print(f"❌ 数据转换失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 