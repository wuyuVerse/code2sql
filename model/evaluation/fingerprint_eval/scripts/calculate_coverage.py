#!/usr/bin/env python3
"""
指纹覆盖率计算脚本

该脚本用于在模型评估完成后，分析评估结果，计算指纹库的覆盖率。
"""

import os
import sys
import json
import pickle
import logging
from pathlib import Path
import argparse
from typing import Set, Dict, Any, List, Tuple

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_fingerprints(cache_path: Path) -> Tuple[Set[str], Dict[str, Any]]:
    """
    从.pkl文件加载指纹库。
    
    Args:
        cache_path: 指纹库文件路径 (.pkl)

    Returns:
        一个元组，包含:
        - a set of all fingerprint strings.
        - a dictionary mapping fingerprints to example SQLs.
    """
    if not cache_path.exists():
        logger.error(f"指纹库文件不存在: {cache_path}")
        raise FileNotFoundError(f"指纹库文件不存在: {cache_path}")
    
    try:
        with open(cache_path, 'rb') as f:
            data = pickle.load(f)
        
        if isinstance(data, tuple) and len(data) == 2:
            fingerprints, fingerprint_to_sql = data
            return fingerprints, fingerprint_to_sql
        else:
            # 兼容旧格式
            fingerprints = data
            return fingerprints, {}
            
    except Exception as e:
        logger.error(f"加载指纹库失败: {e}")
        raise

def get_valid_fingerprints(all_fingerprints: Set[str]) -> Set[str]:
    """
    从指纹集合中过滤掉被排除的指纹类型。
    
    Args:
        all_fingerprints: 所有的指纹集合。

    Returns:
        有效的指纹集合。
    """
    excluded_fingerprints = {
        "transaction_begin",
        "transaction_end",
        "session_setting",
        "show_command",
        "ddl_command",
        "empty_sql",
        "not_sql",
        "invalid_sql"
    }
    
    valid_fingerprints = {
        fp for fp in all_fingerprints 
        if fp not in excluded_fingerprints 
        and not fp.startswith("system_function_")
        and not fp.startswith("invalid_sql_")
        and not fp.startswith("session_setting")
    }
    
    return valid_fingerprints

def get_matched_fingerprints_from_results(results_path: Path) -> Set[str]:
    """
    从评估结果JSON文件中提取所有成功匹配的指纹。
    
    Args:
        results_path: 评估结果文件路径 (.json)

    Returns:
        一个包含所有唯一匹配指纹的集合。
    """
    if not results_path.exists():
        logger.error(f"评估结果文件不存在: {results_path}")
        raise FileNotFoundError(f"评估结果文件不存在: {results_path}")
        
    try:
        with open(results_path, 'r', encoding='utf-8') as f:
            eval_results_data = json.load(f)
    except Exception as e:
        logger.error(f"加载或解析评估结果文件失败: {e}")
        raise

    detailed_results: List[Dict] = eval_results_data.get('detailed_results', [])
    if not detailed_results:
        logger.warning("评估结果文件中没有找到 'detailed_results'，无法计算覆盖率。")
        return set()

    matched_fingerprints = set()
    for result in detailed_results:
        sql_eval = result.get('sql_evaluation', {})
        if not sql_eval:
            continue
            
        fingerprint_results = sql_eval.get('fingerprint_results', [])
        for fp_result in fingerprint_results:
            match_res = fp_result.get('match_result', {})
            if match_res.get('matched', False):
                fingerprint = match_res.get('fingerprint')
                if fingerprint:
                    matched_fingerprints.add(fingerprint)
                    
    return matched_fingerprints

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="计算模型评估的指纹覆盖率。")
    parser.add_argument(
        "--results_file", 
        type=str, 
        required=True,
        help="指向评估结果的JSON文件路径 (通常是 evaluation_results.json)。"
    )
    parser.add_argument(
        "--fingerprint_cache", 
        type=str, 
        required=True,
        help="指向指纹库的.pkl文件路径 (例如 cbs_528_final.pkl)。"
    )
    
    args = parser.parse_args()
    
    results_file_path = Path(args.results_file)
    fingerprint_cache_path = Path(args.fingerprint_cache)

    try:
        # 1. 从评估结果中加载命中的指纹
        logger.info(f"正在从 '{results_file_path.name}' 中提取命中的指纹...")
        matched_fingerprints = get_matched_fingerprints_from_results(results_file_path)
        logger.info(f"提取完成，共找到 {len(matched_fingerprints)} 个被命中的独立指纹。")

        # 2. 从指纹库加载所有指纹
        logger.info(f"正在从 '{fingerprint_cache_path.name}' 加载标准指纹库...")
        all_fingerprints, _ = load_fingerprints(fingerprint_cache_path)
        logger.info(f"加载完成，指纹库包含 {len(all_fingerprints)} 个指纹。")

        # 3. 过滤得到有效的标准指纹
        valid_db_fingerprints = get_valid_fingerprints(all_fingerprints)
        logger.info(f"从标准库中筛选出 {len(valid_db_fingerprints)} 个有效指纹进行覆盖率计算。")
        
        # 4. 计算最终的覆盖率
        # 确保我们只考虑在有效指纹库中存在的命中
        final_matched_set = matched_fingerprints.intersection(valid_db_fingerprints)
        
        total_valid_count = len(valid_db_fingerprints)
        total_matched_count = len(final_matched_set)
        
        if total_valid_count == 0:
            coverage_rate = 0.0
            logger.warning("有效指纹库为空，覆盖率记为0。")
        else:
            coverage_rate = total_matched_count / total_valid_count

        # 5. 打印报告
        print("\n" + "="*80)
        print(" Fingerprint Coverage Report")
        print("="*80)
        print(f"  - Total Valid Fingerprints in Database : {total_valid_count}")
        print(f"  - Matched Unique Fingerprints          : {total_matched_count}")
        print(f"  - Coverage Rate                        : {coverage_rate:.2%}")
        print("="*80)

    except Exception as e:
        logger.error(f"计算覆盖率时发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 