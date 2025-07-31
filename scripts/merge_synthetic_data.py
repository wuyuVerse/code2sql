#!/usr/bin/env python3
"""
合成数据整合脚本

该脚本用于将synthetic_output文件夹中所有不是workflow_年份的文件夹中的sql_generation文件夹的所有json文件中的数据整合起来，
加入到workflow_output/workflow_v{version}这个文件夹的final_processed_dataset.json中。

使用方法:
    python scripts/merge_synthetic_data.py [--version VERSION] [--input-dir INPUT_DIR] [--output-dir OUTPUT_DIR]

参数:
    --version: 工作流版本号 (默认: 自动检测下一个版本)
    --input-dir: 输入目录 (默认: synthetic_output)
    --output-dir: 输出目录 (默认: workflow_output)
"""

import os
import json
import glob
import argparse
import re
from pathlib import Path
from typing import List, Dict, Any
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_next_version(output_dir: str) -> int:
    """
    获取下一个版本号
    
    Args:
        output_dir: 输出目录路径
        
    Returns:
        下一个版本号
    """
    if not os.path.exists(output_dir):
        return 1
    
    # 查找现有的workflow_v*文件夹
    existing_versions = []
    for item in os.listdir(output_dir):
        if os.path.isdir(os.path.join(output_dir, item)) and item.startswith('workflow_v'):
            match = re.search(r'workflow_v(\d+)', item)
            if match:
                existing_versions.append(int(match.group(1)))
    
    if not existing_versions:
        return 1
    
    return max(existing_versions) + 1


def is_workflow_year_folder(folder_name: str) -> bool:
    """
    判断是否为workflow_年份文件夹
    
    Args:
        folder_name: 文件夹名称
        
    Returns:
        是否为workflow_年份文件夹
    """
    # 匹配workflow_YYYY格式
    return bool(re.match(r'workflow_\d{4}', folder_name))


def find_sql_generation_files(input_dir: str) -> List[str]:
    """
    查找所有sql_generation文件夹中的json文件
    
    Args:
        input_dir: 输入目录
        
    Returns:
        json文件路径列表
    """
    json_files = []
    
    if not os.path.exists(input_dir):
        logger.warning(f"输入目录不存在: {input_dir}")
        return json_files
    
    # 遍历synthetic_output目录
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        
        # 跳过非目录项和workflow_年份文件夹
        if not os.path.isdir(item_path) or is_workflow_year_folder(item):
            continue
        
        # 查找sql_generation文件夹
        sql_gen_path = os.path.join(item_path, 'sql_generation')
        if os.path.exists(sql_gen_path) and os.path.isdir(sql_gen_path):
            # 查找所有json文件
            pattern = os.path.join(sql_gen_path, '*.json')
            files = glob.glob(pattern)
            json_files.extend(files)
            logger.info(f"在 {item} 中找到 {len(files)} 个json文件")
    
    return json_files


def load_json_data(file_path: str) -> List[Dict[str, Any]]:
    """
    加载JSON文件数据
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        数据列表
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 如果数据是列表，直接返回；如果是字典，包装成列表
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            logger.warning(f"文件 {file_path} 包含未知数据类型: {type(data)}")
            return []
            
    except Exception as e:
        logger.error(f"加载文件 {file_path} 时出错: {e}")
        return []


def merge_data(json_files: List[str]) -> List[Dict[str, Any]]:
    """
    合并所有JSON文件的数据
    
    Args:
        json_files: JSON文件路径列表
        
    Returns:
        合并后的数据列表
    """
    merged_data = []
    total_files = len(json_files)
    
    logger.info(f"开始处理 {total_files} 个JSON文件...")
    
    for i, file_path in enumerate(json_files, 1):
        logger.info(f"处理文件 {i}/{total_files}: {os.path.basename(file_path)}")
        
        data = load_json_data(file_path)
        if data:
            merged_data.extend(data)
            logger.info(f"从 {file_path} 加载了 {len(data)} 条记录")
    
    logger.info(f"总共合并了 {len(merged_data)} 条记录")
    return merged_data


def save_merged_data(data: List[Dict[str, Any]], output_path: str):
    """
    保存合并后的数据
    
    Args:
        data: 合并后的数据
        output_path: 输出文件路径
    """
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据已保存到: {output_path}")
        logger.info(f"总共保存了 {len(data)} 条记录")
        
    except Exception as e:
        logger.error(f"保存文件时出错: {e}")
        raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='合并合成数据到workflow输出目录')
    parser.add_argument('--version', type=int, help='工作流版本号 (默认: 自动检测)')
    parser.add_argument('--input-dir', default='synthetic_output', help='输入目录 (默认: synthetic_output)')
    parser.add_argument('--output-dir', default='workflow_output', help='输出目录 (默认: workflow_output)')
    parser.add_argument('--dry-run', action='store_true', help='仅显示将要处理的文件，不实际合并')
    
    args = parser.parse_args()
    
    # 获取版本号
    if args.version is None:
        version = get_next_version(args.output_dir)
        logger.info(f"自动检测到下一个版本号: {version}")
    else:
        version = args.version
        logger.info(f"使用指定版本号: {version}")
    
    # 构建输出路径
    workflow_dir = os.path.join(args.output_dir, f'workflow_v{version}')
    output_file = os.path.join(workflow_dir, 'final_processed_dataset.json')
    
    logger.info(f"输出目录: {workflow_dir}")
    logger.info(f"输出文件: {output_file}")
    
    # 查找所有需要处理的JSON文件
    json_files = find_sql_generation_files(args.input_dir)
    
    if not json_files:
        logger.warning("未找到任何需要处理的JSON文件")
        return
    
    logger.info(f"找到 {len(json_files)} 个JSON文件需要处理:")
    for file_path in json_files:
        logger.info(f"  - {file_path}")
    
    if args.dry_run:
        logger.info("干运行模式：仅显示文件列表，不进行实际合并")
        return
    
    # 合并数据
    merged_data = merge_data(json_files)
    
    if not merged_data:
        logger.warning("没有数据需要保存")
        return
    
    # 保存合并后的数据
    save_merged_data(merged_data, output_file)
    
    logger.info("数据整合完成！")


if __name__ == '__main__':
    main() 