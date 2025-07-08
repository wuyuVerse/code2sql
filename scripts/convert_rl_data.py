#!/usr/bin/env python3
"""
RL训练数据转换快速启动脚本

用于将workflow处理后的ORM数据转换为RLHF训练格式（parquet文件）
"""

import sys
import os
import pandas as pd
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root))

from data_processing.rl_data_converter import RLDataConverter

def show_data_sample(parquet_path: Path, num_samples: int = 3):
    """
    显示数据样例
    
    Args:
        parquet_path: parquet文件路径
        num_samples: 显示的样例数量
    """
    print(f"\n📋 数据样例 ({parquet_path.name}):")
    print("=" * 80)
    
    df = pd.read_parquet(parquet_path)
    
    for i in range(min(num_samples, len(df))):
        row = df.iloc[i]
        print(f"\n样例 {i+1}:")
        print("-" * 40)
        
        print(f"🎯 数据源: {row['data_source']}")
        print(f"🧠 能力类别: {row['ability']}")
        
        print(f"\n💬 提示词 (prompt):")
        for j, message in enumerate(row['prompt']):
            role = message['role']
            content = message['content'][:200] + "..." if len(message['content']) > 200 else message['content']
            print(f"  [{j+1}] {role}: {content}")
        
        print(f"\n🏆 奖励模型配置:")
        reward_model = row['reward_model']
        print(f"  样式: {reward_model['style']}")
        ground_truth = reward_model['ground_truth']
        if isinstance(ground_truth, str) and len(ground_truth) > 100:
            ground_truth = ground_truth[:100] + "..."
        print(f"  标准答案: {ground_truth}")
        
        print(f"\n📊 额外信息:")
        extra_info = row['extra_info']
        print(f"  索引: {extra_info['index']}")
        print(f"  分组: {extra_info['split']}")
        print(f"  函数名: {extra_info['function_name']}")
        print(f"  SQL类型数: {extra_info['sql_pattern_cnt']}")
        
        if i < min(num_samples, len(df)) - 1:
            print("\n" + "="*60)

def show_data_format_info():
    """显示RL数据格式说明"""
    print("\n📖 RL数据格式说明:")
    print("=" * 80)
    print("""
RL训练数据采用RLHF (Reinforcement Learning from Human Feedback) 格式，
存储为parquet文件，包含以下字段：

🔹 data_source (str): 数据来源标识
   - 用于在RewardManager中选择对应的奖励函数
   - 本项目中为: "code2sql_orm"

🔹 prompt (list): 聊天格式的提示词
   - 格式: [{"role": "user", "content": "..."}]
   - 支持多轮对话，但本项目主要使用单轮
   - 内容包含ORM代码分析要求和上下文信息

🔹 ability (str): 任务能力类别
   - 用于任务分类和评估
   - 本项目中为: "code_generation"

🔹 reward_model (dict): 奖励模型配置
   - style: "rule" (基于规则评分) 或 "model" (基于模型评分)
   - ground_truth: 标准答案，用于计算奖励分数
   - 本项目使用SQL语句的JSON数组作为标准答案

🔹 extra_info (dict): 额外元信息
   - index: 数据索引
   - split: 数据集划分 ("train" 或 "val")
   - function_name, source_file, sql_pattern_cnt 等调试信息

这种格式与verl框架完全兼容，可直接用于PPO、DPO等RL算法训练。
""")

def main():
    """主函数"""
    print("🚀 开始ORM到SQL的RL训练数据转换...")
    
    converter = RLDataConverter()
    
    try:
        # 执行转换
        train_path, val_path, dataset_info = converter.run_conversion(val_ratio=0.1)
        
        print(f"\n✅ RL数据转换完成!")
        print(f"📁 训练集路径: {train_path}")
        print(f"📁 验证集路径: {val_path}")
        print(f"📊 训练集样本数: {dataset_info['train']['num_samples']}")
        print(f"📊 验证集样本数: {dataset_info['val']['num_samples']}")
        print(f"📊 总样本数: {dataset_info['total_samples']}")
        info_file = converter.rl_data_dir / f"{dataset_info['dataset_name']}_info.json"
        print(f"📝 数据集信息: {info_file}")
        
        # 显示数据格式说明
        show_data_format_info()
        
        # 显示训练集样例
        show_data_sample(train_path, num_samples=2)
        
        # 显示验证集样例
        show_data_sample(val_path, num_samples=1)
        
        print(f"\n🎯 下一步：")
        print(f"   1. 使用 {train_path} 和 {val_path} 进行RL训练")
        print(f"   2. 配置verl训练脚本，指定数据路径")
        print(f"   3. 设置奖励函数来评估SQL生成质量")
        print(f"   4. 启动PPO或其他RL算法进行模型优化")
        
        # 显示数据集统计信息
        print(f"\n📈 数据集统计:")
        df_train = pd.read_parquet(train_path)
        df_val = pd.read_parquet(val_path)
        
        print(f"   训练集大小: {train_path.stat().st_size / (1024*1024):.1f} MB")
        print(f"   验证集大小: {val_path.stat().st_size / (1024*1024):.1f} MB")
        print(f"   数据源分布: {df_train['data_source'].value_counts().to_dict()}")
        print(f"   能力类别分布: {df_train['ability'].value_counts().to_dict()}")
        
    except Exception as e:
        print(f"❌ RL数据转换失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 