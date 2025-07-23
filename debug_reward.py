#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

def debug_reward_parsing():
    """调试reward日志解析"""
    reward_file_path = Path("model/rl/reward_logs/reward_20250721_2020_v2.jsonl")
    
    if not reward_file_path.exists():
        print("文件不存在")
        return
    
    reward_data = []
    with open(reward_file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    data = json.loads(line.strip())
                    data['line_number'] = line_num
                    
                    # 检查score字段
                    score = data.get('score')
                    if score is None:
                        print(f"第{line_num}行: score为None")
                    elif not isinstance(score, (int, float)):
                        print(f"第{line_num}行: score类型异常 - {type(score)}: {score}")
                    
                    reward_data.append(data)
                except json.JSONDecodeError as e:
                    print(f"解析第{line_num}行JSON失败: {e}")
                    continue
    
    print(f"总记录数: {len(reward_data)}")
    
    # 测试统计计算
    try:
        valid_scores = [item.get('score', 0) for item in reward_data if item.get('score') is not None]
        print(f"有效分数数量: {len(valid_scores)}")
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        print(f"平均分数: {avg_score}")
        
        # 测试分数分组
        score_ranges = {
            '优秀 (0.8-1.0)': len([item for item in reward_data if item.get('score') is not None and 0.8 <= item.get('score', 0) <= 1.0]),
            '良好 (0.6-0.8)': len([item for item in reward_data if item.get('score') is not None and 0.6 <= item.get('score', 0) < 0.8]),
            '一般 (0.4-0.6)': len([item for item in reward_data if item.get('score') is not None and 0.4 <= item.get('score', 0) < 0.6]),
            '较差 (0.0-0.4)': len([item for item in reward_data if item.get('score') is not None and 0.0 <= item.get('score', 0) < 0.4])
        }
        print("分数分布:", score_ranges)
        
    except Exception as e:
        print(f"统计计算失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_reward_parsing() 