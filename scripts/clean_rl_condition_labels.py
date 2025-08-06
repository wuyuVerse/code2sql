#!/usr/bin/env python3
"""
RL数据condition标签清理脚本

该脚本用于清理已生成的RL数据中的condition标签：
- 只保留来自workflow_mutual_exclusive_conditions的数据的"if-else"标签
- 删除其他数据源中错误添加的"if-else"标签
- 保留所有"keyword"标签（基于LLM分析结果）

使用方法:
    python scripts/clean_rl_condition_labels.py --input INPUT_FILE [--output OUTPUT_FILE] [--mapping-dir MAPPING_DIR]

参数:
    --input: 输入的RL数据文件路径
    --output: 输出文件路径（默认覆盖原文件）
    --mapping-dir: workflow_mutual_exclusive_conditions目录路径（默认: synthetic_output/workflow_mutual_exclusive_conditions）
    --dry-run: 仅显示将要修改的统计信息，不实际修改
"""

import argparse
import json
import glob
import os
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_condition_mapping_data(mapping_dir: str) -> List[Dict[str, Any]]:
    """
    加载workflow_mutual_exclusive_conditions目录中的所有数据
    
    Args:
        mapping_dir: workflow_mutual_exclusive_conditions目录路径
        
    Returns:
        所有condition mapping数据列表
    """
    condition_data = []
    
    if not os.path.exists(mapping_dir):
        logger.warning(f"workflow_mutual_exclusive_conditions目录不存在: {mapping_dir}")
        return condition_data
    
    # 首先查找sql_generation子目录中的json文件
    sql_gen_dir = os.path.join(mapping_dir, 'sql_generation')
    if os.path.exists(sql_gen_dir):
        pattern = os.path.join(sql_gen_dir, '*.json')
        json_files = glob.glob(pattern)
        logger.info(f"在 {sql_gen_dir} 中找到 {len(json_files)} 个JSON文件")
    else:
        # 如果没有sql_generation子目录，查找根目录
        pattern = os.path.join(mapping_dir, '*.json')
        json_files = glob.glob(pattern)
        logger.info(f"在 {mapping_dir} 中找到 {len(json_files)} 个JSON文件")
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                condition_data.extend(data)
                logger.info(f"从 {os.path.basename(file_path)} 加载了 {len(data)} 条记录")
            elif isinstance(data, dict):
                condition_data.append(data)
                logger.info(f"从 {os.path.basename(file_path)} 加载了 1 条记录")
                
        except Exception as e:
            logger.error(f"加载文件 {file_path} 时出错: {e}")
            continue
    
    logger.info(f"总共加载了 {len(condition_data)} 条workflow_mutual_exclusive_conditions记录")
    return condition_data


def create_record_identifier_set(data: List[Dict[str, Any]]) -> Set[Tuple]:
    """
    为数据记录创建唯一标识符集合
    
    Args:
        data: 数据记录列表
        
    Returns:
        记录标识符集合
    """
    identifier_set = set()
    
    for record in data:
        # 使用多个字段组合作为唯一标识
        record_id = (
            record.get('function_name', ''),
            record.get('orm_code', ''),
            record.get('caller', ''),
            str(record.get('sql_statement_list', []))
        )
        identifier_set.add(record_id)
    
    return identifier_set


def clean_condition_labels(rl_data: List[Dict[str, Any]], 
                          condition_mapping_ids: Set[Tuple]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    清理RL数据中的condition标签
    
    Args:
        rl_data: RL数据列表
        condition_mapping_ids: workflow_mutual_exclusive_conditions记录标识符集合
        
    Returns:
        (清理后的数据, 统计信息)
    """
    stats = {
        'total_records': len(rl_data),
        'condition_mapping_records': 0,
        'other_records': 0,
        'if_else_removed': 0,
        'if_else_kept': 0,
        'keyword_kept': 0
    }
    
    for record in rl_data:
        # 检查是否来自workflow_mutual_exclusive_conditions
        record_id = (
            record.get('function_name', ''),
            record.get('orm_code', ''),
            record.get('caller', ''),
            str(record.get('sql_statement_list', []))
        )
        
        is_from_condition_mapping = record_id in condition_mapping_ids
        current_condition = record.get('condition', [])
        new_condition = []
        
        if is_from_condition_mapping:
            stats['condition_mapping_records'] += 1
            # 保留if-else标签
            if 'if-else' in current_condition:
                new_condition.append('if-else')
                stats['if_else_kept'] += 1
        else:
            stats['other_records'] += 1
            # 移除if-else标签
            if 'if-else' in current_condition:
                stats['if_else_removed'] += 1
        
        # 保留keyword标签（所有记录）
        if 'keyword' in current_condition:
            new_condition.append('keyword')
            stats['keyword_kept'] += 1
        
        # 更新condition字段
        record['condition'] = new_condition
    
    return rl_data, stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='清理RL数据中的condition标签')
    parser.add_argument('--input', required=True, help='输入的RL数据文件路径')
    parser.add_argument('--output', help='输出文件路径（默认覆盖原文件）')
    parser.add_argument('--mapping-dir', default='synthetic_output/workflow_mutual_exclusive_conditions', 
                       help='workflow_mutual_exclusive_conditions目录路径')
    parser.add_argument('--dry-run', action='store_true', help='仅显示统计信息，不实际修改')
    
    args = parser.parse_args()
    
    # 设置输出路径
    output_path = args.output if args.output else args.input
    
    logger.info(f"开始清理RL数据condition标签:")
    logger.info(f"  - 输入文件: {args.input}")
    logger.info(f"  - 输出文件: {output_path}")
    logger.info(f"  - 映射目录: {args.mapping_dir}")
    logger.info(f"  - 干运行: {args.dry_run}")
    
    # 1. 加载workflow_mutual_exclusive_conditions数据
    condition_mapping_data = load_condition_mapping_data(args.mapping_dir)
    if not condition_mapping_data:
        logger.error("未找到workflow_mutual_exclusive_conditions数据，无法进行清理")
        return
    
    # 2. 创建标识符集合
    condition_mapping_ids = create_record_identifier_set(condition_mapping_data)
    logger.info(f"创建了 {len(condition_mapping_ids)} 个workflow_mutual_exclusive_conditions记录标识符")
    
    # 3. 加载RL数据
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            rl_data = json.load(f)
        
        if not isinstance(rl_data, list):
            logger.error("输入文件不是记录列表格式")
            return
        
        logger.info(f"加载了 {len(rl_data)} 条RL数据记录")
        
    except Exception as e:
        logger.error(f"加载输入文件时出错: {e}")
        return
    
    # 4. 清理condition标签
    cleaned_data, stats = clean_condition_labels(rl_data, condition_mapping_ids)
    
    # 5. 显示统计信息
    logger.info("清理统计结果:")
    logger.info(f"  - 总记录数: {stats['total_records']}")
    logger.info(f"  - workflow_mutual_exclusive_conditions记录: {stats['condition_mapping_records']}")
    logger.info(f"  - 其他数据源记录: {stats['other_records']}")
    logger.info(f"  - 保留的if-else标签: {stats['if_else_kept']}")
    logger.info(f"  - 移除的if-else标签: {stats['if_else_removed']}")
    logger.info(f"  - 保留的keyword标签: {stats['keyword_kept']}")
    
    # 6. 显示condition分布统计
    condition_distribution = {}
    for record in cleaned_data:
        condition_list = record.get('condition', [])
        condition_key = tuple(sorted(condition_list))
        condition_distribution[condition_key] = condition_distribution.get(condition_key, 0) + 1
    
    logger.info("清理后的condition分布:")
    for condition_tuple, count in sorted(condition_distribution.items()):
        condition_str = str(list(condition_tuple)) if condition_tuple else "[]"
        logger.info(f"  {condition_str}: {count} 条记录")
    
    if args.dry_run:
        logger.info("干运行模式：未实际修改文件")
        return
    
    # 7. 保存清理后的数据
    try:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 清理完成，数据已保存到: {output_path}")
        
        # 如果是覆盖原文件，创建备份
        if output_path == args.input:
            backup_path = f"{args.input}.backup"
            if not os.path.exists(backup_path):
                import shutil
                shutil.copy2(args.input, backup_path)
                logger.info(f"原文件已备份到: {backup_path}")
        
    except Exception as e:
        logger.error(f"保存文件时出错: {e}")
        return


if __name__ == '__main__':
    main() 