#!/usr/bin/env python3
"""
RL数据生成脚本

该脚本用于生成强化学习（RL）训练数据：
1. 从synthetic_output目录收集数据：
   - 所有sql_generation文件夹中的JSON数据
   - workflow_mutual_exclusive_conditions目录中的JSON数据
2. 智能抽样策略（默认2000条）：
   - 确保100%包含workflow_mutual_exclusive_conditions的所有数据
   - 从其他数据源随机补充至目标数量
3. 使用LLM进行关键词判断分析
4. 设置condition字段：
   - 只有来自workflow_mutual_exclusive_conditions的记录才添加"if-else"标签
   - 只有has_special_keywords为true的记录才添加"keyword"标签
   - 可能的组合：[], ["if-else"], ["keyword"], ["if-else", "keyword"]
5. 输出到workflow_output/rl_vxxx目录

使用方法:
    python scripts/generate_rl_data.py [--input-dir INPUT_DIR] [--output-dir OUTPUT_DIR] [--sample-size SAMPLE_SIZE] [--version VERSION]

参数:
    --input-dir: 输入目录 (默认: synthetic_output)
    --output-dir: 输出目录 (默认: workflow_output)
    --sample-size: 抽样数量 (默认: 2000)
    --version: RL版本号 (默认: 自动检测下一个版本)
    --seed: 随机种子，用于复现抽样结果
    --dry-run: 仅显示将要处理的文件，不实际处理
"""

import argparse
import asyncio
import sys
import os
import json
import glob
import random
import re
from pathlib import Path
from typing import List, Dict, Any
import logging

# 支持直接脚本运行
sys.path.append(str(Path(__file__).parent.parent))
from data_processing.workflow.workflow_manager import WorkflowManager

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_next_rl_version(output_dir: str) -> int:
    """
    获取下一个RL版本号
    
    Args:
        output_dir: 输出目录路径
        
    Returns:
        下一个RL版本号
    """
    if not os.path.exists(output_dir):
        return 1
    
    # 查找现有的rl_v*文件夹
    existing_versions = []
    for item in os.listdir(output_dir):
        if os.path.isdir(os.path.join(output_dir, item)) and item.startswith('rl_v'):
            match = re.search(r'rl_v(\d+)', item)
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


def find_all_data_files(input_dir: str) -> List[str]:
    """
    查找所有需要处理的json文件，包括sql_generation文件夹和workflow_condition_field_mapping
    
    Args:
        input_dir: 输入目录
        
    Returns:
        json文件路径列表
    """
    json_files = []
    
    if not os.path.exists(input_dir):
        logger.warning(f"输入目录不存在: {input_dir}")
        return json_files
    
    # 1. 遍历synthetic_output目录查找sql_generation文件夹
    mutual_exclusive_processed = False
    
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
            
            # 特别标记workflow_mutual_exclusive_conditions
            if item == 'workflow_mutual_exclusive_conditions':
                mutual_exclusive_processed = True
                logger.info(f"在 {item}/sql_generation 中找到 {len(files)} 个json文件 (特殊处理)")
            else:
                logger.info(f"在 {item}/sql_generation 中找到 {len(files)} 个json文件")
    
    # 2. 如果workflow_mutual_exclusive_conditions还没有被处理，单独处理
    if not mutual_exclusive_processed:
        mutual_exclusive_path = os.path.join(input_dir, 'workflow_mutual_exclusive_conditions')
        if os.path.exists(mutual_exclusive_path) and os.path.isdir(mutual_exclusive_path):
            # 查找sql_generation子目录中的json文件
            sql_gen_path = os.path.join(mutual_exclusive_path, 'sql_generation')
            if os.path.exists(sql_gen_path):
                pattern = os.path.join(sql_gen_path, '*.json')
                mapping_files = glob.glob(pattern)
                json_files.extend(mapping_files)
                logger.info(f"在 workflow_mutual_exclusive_conditions/sql_generation 中找到 {len(mapping_files)} 个json文件 (补充处理)")
    
    return json_files


def load_and_merge_data(json_files: List[str]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    加载并合并所有JSON文件的数据，分别统计不同来源的数据
    
    Args:
        json_files: JSON文件路径列表
        
    Returns:
        (所有数据, workflow_mutual_exclusive_conditions数据, 其他数据源数据)
    """
    all_data = []
    condition_mapping_data = []
    other_data = []
    total_files = len(json_files)
    
    logger.info(f"开始处理 {total_files} 个JSON文件...")
    
    for i, file_path in enumerate(json_files, 1):
        logger.info(f"处理文件 {i}/{total_files}: {os.path.basename(file_path)}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 如果数据是列表，直接扩展；如果是字典，包装成列表
            if isinstance(data, list):
                file_data = data
            elif isinstance(data, dict):
                file_data = [data]
            else:
                logger.warning(f"文件 {file_path} 包含未知数据类型: {type(data)}")
                continue
            
            # 判断是否来自workflow_mutual_exclusive_conditions目录
            if 'workflow_mutual_exclusive_conditions' in file_path:
                condition_mapping_data.extend(file_data)
                logger.info(f"从 workflow_mutual_exclusive_conditions/{os.path.basename(file_path)} 加载了 {len(file_data)} 条记录")
            else:
                other_data.extend(file_data)
                logger.info(f"从 {file_path} 加载了 {len(file_data)} 条记录")
            
            all_data.extend(file_data)
                
        except Exception as e:
            logger.error(f"加载文件 {file_path} 时出错: {e}")
            continue
    
    logger.info(f"数据加载完成:")
    logger.info(f"  - workflow_mutual_exclusive_conditions: {len(condition_mapping_data)} 条记录")
    logger.info(f"  - 其他数据源: {len(other_data)} 条记录")
    logger.info(f"  - 总计: {len(all_data)} 条记录")
    
    return all_data, condition_mapping_data, other_data


def smart_sample_data(condition_mapping_data: List[Dict[str, Any]], 
                      other_data: List[Dict[str, Any]], 
                      sample_size: int) -> List[Dict[str, Any]]:
    """
    智能抽样数据：确保包含所有workflow_mutual_exclusive_conditions数据，然后从其他数据源补充
    
    Args:
        condition_mapping_data: workflow_mutual_exclusive_conditions数据
        other_data: 其他数据源数据
        sample_size: 总抽样数量
        
    Returns:
        抽样后的数据列表
    """
    total_available = len(condition_mapping_data) + len(other_data)
    
    logger.info(f"智能抽样策略:")
    logger.info(f"  - workflow_mutual_exclusive_conditions数据: {len(condition_mapping_data)} 条 (全部包含)")
    logger.info(f"  - 其他数据源: {len(other_data)} 条")
    logger.info(f"  - 目标抽样数量: {sample_size} 条")
    
    # 1. 首先包含所有workflow_mutual_exclusive_conditions数据
    sampled_data = condition_mapping_data.copy()
    
    # 2. 计算还需要从其他数据源抽取多少条
    remaining_needed = sample_size - len(condition_mapping_data)
    
    if remaining_needed <= 0:
        logger.info(f"workflow_mutual_exclusive_conditions数据({len(condition_mapping_data)})已达到或超过目标数量，仅返回这些数据")
        return sampled_data[:sample_size]
    
    # 3. 从其他数据源随机抽样补充
    if len(other_data) <= remaining_needed:
        logger.info(f"其他数据源数量({len(other_data)})不足，全部包含")
        sampled_data.extend(other_data)
    else:
        logger.info(f"从其他数据源随机抽取 {remaining_needed} 条")
        other_sampled = random.sample(other_data, remaining_needed)
        sampled_data.extend(other_sampled)
    
    # 4. 最终统计
    final_count = len(sampled_data)
    condition_mapping_count = len(condition_mapping_data)
    other_count = final_count - condition_mapping_count
    
    logger.info(f"抽样完成:")
    logger.info(f"  - workflow_mutual_exclusive_conditions: {condition_mapping_count} 条 (100%)")
    logger.info(f"  - 其他数据源: {other_count} 条 ({other_count/len(other_data)*100:.1f}%)" if other_data else "  - 其他数据源: 0 条")
    logger.info(f"  - 总计: {final_count} 条")
    
    return sampled_data


def process_rl_condition_fields(processed_data: List[Dict[str, Any]], 
                                condition_mapping_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    处理RL数据的condition字段，根据数据来源和关键词分析结果设置条件标签
    
    Args:
        processed_data: LLM处理后的数据
        condition_mapping_data: 来自workflow_mutual_exclusive_conditions的原始数据
        
    Returns:
        处理condition字段后的数据
    """
    # 创建一个集合来快速查找哪些记录来自workflow_mutual_exclusive_conditions
    condition_mapping_ids = set()
    for record in condition_mapping_data:
        # 使用多个字段组合作为唯一标识
        record_id = (
            record.get('function_name', ''),
            record.get('orm_code', ''),
            record.get('caller', ''),
            str(record.get('sql_statement_list', []))
        )
        condition_mapping_ids.add(record_id)
    
    logger.info(f"workflow_mutual_exclusive_conditions数据标识符数量: {len(condition_mapping_ids)}")
    
    for record in processed_data:
        condition_list = []
        
        # 检查是否来自workflow_mutual_exclusive_conditions
        record_id = (
            record.get('function_name', ''),
            record.get('orm_code', ''),
            record.get('caller', ''),
            str(record.get('sql_statement_list', []))
        )
        
        is_from_condition_mapping = record_id in condition_mapping_ids
        
        # 只有来自workflow_mutual_exclusive_conditions的数据才添加if-else标签
        if is_from_condition_mapping:
            condition_list.append("if-else")
        
        # 检查是否有关键词分析结果且has_special_keywords为true
        llm_analysis = record.get('llm_keyword_analysis', {})
        has_special_keywords = llm_analysis.get('has_special_keywords', False)
        
        if has_special_keywords:
            condition_list.append("keyword")
        
        # 更新condition字段
        record['condition'] = condition_list
        
        source_type = "condition_mapping" if is_from_condition_mapping else "other"
        logger.debug(f"记录 {record.get('function_name', 'unknown')} ({source_type}) 的condition设置为: {condition_list}")
    
    # 统计condition分布
    condition_stats = {}
    source_stats = {"condition_mapping": 0, "other": 0}
    
    for record in processed_data:
        condition_list = record.get('condition', [])
        condition_key = tuple(sorted(condition_list))
        condition_stats[condition_key] = condition_stats.get(condition_key, 0) + 1
        
        # 统计数据来源
        if "if-else" in condition_list:
            source_stats["condition_mapping"] += 1
        else:
            source_stats["other"] += 1
    
    logger.info("Condition字段分布统计:")
    for condition_tuple, count in sorted(condition_stats.items()):
        logger.info(f"  {list(condition_tuple)}: {count} 条记录")
    
    logger.info("数据来源统计:")
    logger.info(f"  - workflow_mutual_exclusive_conditions: {source_stats['condition_mapping']} 条")
    logger.info(f"  - 其他数据源: {source_stats['other']} 条")
    
    return processed_data


async def process_rl_data_with_llm(data: List[Dict[str, Any]], 
                                   condition_mapping_data: List[Dict[str, Any]], 
                                   output_dir: str) -> str:
    """
    使用LLM处理RL数据
    
    Args:
        data: 要处理的数据
        condition_mapping_data: 来自workflow_condition_field_mapping的原始数据
        output_dir: 输出目录
        
    Returns:
        输出文件路径
    """
    # 创建临时文件保存抽样数据
    temp_file = Path(output_dir) / "temp_sampled_data.json"
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"抽样数据已保存到临时文件: {temp_file}")
    
    # 初始化WorkflowManager
    workflow = WorkflowManager(base_output_dir=str(temp_file.parent))
    
    # 执行LLM关键词分析
    try:
        result_path = await workflow.extract_keywords_from_file_and_export_all(
            input_file=str(temp_file),
            output_file="rl_processed_data.json"
        )
        
        logger.info(f"✅ RL数据LLM分析完成: {result_path}")
        
        # 读取处理后的数据
        with open(result_path, 'r', encoding='utf-8') as f:
            processed_data = json.load(f)
        
        # 处理condition字段
        processed_data = process_rl_condition_fields(processed_data, condition_mapping_data)
        
        # 重新保存处理后的数据
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
        
        logger.info("✅ Condition字段处理完成")
        
        # 清理临时文件
        temp_file.unlink()
        logger.info("临时文件已清理")
        
        return result_path
        
    except Exception as e:
        logger.error(f"LLM处理过程中出错: {e}")
        # 清理临时文件
        if temp_file.exists():
            temp_file.unlink()
        raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生成RL训练数据')
    parser.add_argument('--input-dir', default='synthetic_output', help='输入目录 (默认: synthetic_output)')
    parser.add_argument('--output-dir', default='workflow_output', help='输出目录 (默认: workflow_output)')
    parser.add_argument('--sample-size', type=int, default=2000, help='抽样数量 (默认: 2000)')
    parser.add_argument('--version', type=int, help='RL版本号 (默认: 自动检测)')
    parser.add_argument('--dry-run', action='store_true', help='仅显示将要处理的文件，不实际处理')
    parser.add_argument('--seed', type=int, help='随机种子，用于复现抽样结果')
    
    args = parser.parse_args()
    
    # 设置随机种子
    if args.seed is not None:
        random.seed(args.seed)
        logger.info(f"设置随机种子: {args.seed}")
    
    # 获取版本号
    if args.version is None:
        version = get_next_rl_version(args.output_dir)
        logger.info(f"自动检测到下一个RL版本号: {version}")
    else:
        version = args.version
        logger.info(f"使用指定RL版本号: {version}")
    
    # 构建输出路径
    rl_output_dir = os.path.join(args.output_dir, f'rl_v{version}')
    logger.info(f"RL输出目录: {rl_output_dir}")
    
    # 查找所有需要处理的JSON文件
    json_files = find_all_data_files(args.input_dir)
    
    if not json_files:
        logger.warning("未找到任何需要处理的JSON文件")
        return
    
    logger.info(f"找到 {len(json_files)} 个JSON文件需要处理:")
    for file_path in json_files:
        logger.info(f"  - {file_path}")
    
    if args.dry_run:
        logger.info("干运行模式：仅显示文件列表，不进行实际处理")
        return
    
    # 加载并合并数据
    all_data, condition_mapping_data, other_data = load_and_merge_data(json_files)
    
    if not all_data:
        logger.warning("没有数据需要处理")
        return
    
    # 智能抽样：确保包含所有workflow_condition_field_mapping数据
    sampled_data = smart_sample_data(condition_mapping_data, other_data, args.sample_size)
    
    # 使用LLM处理数据
    try:
        result_path = asyncio.run(
            process_rl_data_with_llm(sampled_data, condition_mapping_data, rl_output_dir)
        )
        logger.info(f"✅ RL数据生成完成: {result_path}")
        
        # 移动结果文件到正确的位置
        final_output_path = Path(rl_output_dir) / "rl_processed_data.json"
        if Path(result_path).exists() and str(Path(result_path).parent) != rl_output_dir:
            # 如果结果文件不在目标目录，移动它
            final_output_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.move(result_path, final_output_path)
            logger.info(f"结果文件已移动到: {final_output_path}")
        
        # 生成统计报告
        with open(final_output_path, 'r', encoding='utf-8') as f:
            processed_data = json.load(f)
        
        # 统计condition字段分布
        condition_distribution = {}
        keyword_match_count = 0
        for record in processed_data:
            condition_list = record.get('condition', [])
            condition_key = tuple(sorted(condition_list))
            condition_distribution[condition_key] = condition_distribution.get(condition_key, 0) + 1
            
            # 统计有关键词匹配的记录数
            if 'keyword' in condition_list:
                keyword_match_count += 1
        
        # 转换为可序列化的格式
        condition_stats = {}
        for condition_tuple, count in condition_distribution.items():
            condition_stats[str(list(condition_tuple))] = count
        
        stats = {
            'total_source_files': len(json_files),
            'total_merged_records': len(all_data),
            'condition_mapping_records': len(condition_mapping_data),
            'other_source_records': len(other_data),
            'sampled_records': len(sampled_data),
            'processed_records': len(processed_data),
            'sample_rate': len(sampled_data) / len(all_data) * 100 if all_data else 0,
            'condition_mapping_coverage': 100.0 if condition_mapping_data else 0.0,  # 始终100%
            'keyword_match_count': keyword_match_count,
            'keyword_match_rate': keyword_match_count / len(processed_data) * 100 if processed_data else 0,
            'condition_distribution': condition_stats,
            'rl_version': version,
            'processing_timestamp': Path(final_output_path).stat().st_mtime,
            'output_directory': str(rl_output_dir),
            'random_seed': args.seed
        }
        
        stats_file = Path(rl_output_dir) / "rl_generation_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"统计报告已保存: {stats_file}")
        logger.info("RL数据生成完成！")
        
    except Exception as e:
        logger.error(f"RL数据生成失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 