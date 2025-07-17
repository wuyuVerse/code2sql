#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据集对比评估脚本

该脚本用于直接比较两个数据集（基准数据集和生成数据集），
在相同输入下，生成的SQL列表的差异。

核心逻辑：
1. 加载基准数据集和生成数据集。
2. 遍历基准集，找到对应的生成数据。
3. 对基准SQL和生成SQL进行指纹化。
4. 比较两个指纹集合，找出"一致"、"缺失"、"多余"的SQL。
5. 生成详细的JSON对比报告。
"""

import os
import sys
import json
import yaml
import logging
from pathlib import Path
import argparse
from typing import Dict, List, Any, Set, Tuple, Optional
import re
from utils.response_parser import parse_model_response, recursively_extract_sql
from datetime import datetime

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# --- 动态添加项目根目录到sys.path ---
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[4]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
        logger.info(f"项目根目录已添加: {PROJECT_ROOT}")
except IndexError:
    logger.error("无法确定项目根目录，请确保脚本位于预期的目录结构中。")
    sys.exit(1)


# --- 延迟导入核心模块 ---
try:
    from utils.sql_feature_extractor import SQLFeatureExtractor
except ImportError as e:
    logger.error(f"导入核心模块失败: {e}")
    logger.error("请确保项目结构是否正确。")
    sys.exit(1)


# --- JSON编码器 ---
class ChineseJSONEncoder(json.JSONEncoder):
    """处理中文字符的JSON编码器"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class DatasetComparativeEvaluator:
    """数据集对比评估器"""

    def __init__(self, config_path: str, output_dir: str, mode: str):
        self.config_path = Path(config_path)
        self.output_dir = Path(output_dir)
        self.mode = mode
        self.config = self._load_config()
        
        self.sql_extractor = SQLFeatureExtractor()

        # 根据模式配置测试样本数量
        if self.mode == 'test':
            self.test_samples = self.config.get('debug_config', {}).get('test_samples', 5)
            logger.info(f"进入测试模式，将处理 {self.test_samples} 个样本。")
        else:
            self.test_samples = None
            logger.info("进入完整评估模式。")

    def _load_config(self) -> Dict:
        """加载YAML配置文件"""
        logger.info(f"正在加载配置文件: {self.config_path}")
        if not self.config_path.exists():
            logger.error(f"配置文件不存在: {self.config_path}")
            sys.exit(1)
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _load_dataset(self, data_path: str) -> List[Dict]:
        """从路径加载数据集"""
        dataset_path = Path(data_path)
        logger.info(f"正在从路径加载数据集: {dataset_path}")

        if not dataset_path.exists():
            logger.error(f"数据集路径不存在: {dataset_path}")
            sys.exit(1)
        
        all_data = []
        
        # 如果是目录，加载所有JSON文件
        if dataset_path.is_dir():
            json_files = sorted(list(dataset_path.glob('*.json')))
            if not json_files:
                logger.error(f"在目录 {dataset_path} 中未找到任何 .json 文件。")
                sys.exit(1)
            
            logger.info(f"找到 {len(json_files)} 个JSON文件进行加载。")
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            all_data.extend(data)
                            logger.debug(f"成功加载 {len(data)} 条记录从 {json_file.name}")
                        else:
                            logger.warning(f"文件 {json_file.name} 的内容不是一个列表，已跳过。")
                except Exception as e:
                    logger.error(f"加载文件 {json_file.name} 失败: {e}")
        
        # 如果是单个文件
        elif dataset_path.is_file():
            try:
                with open(dataset_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        all_data = data
                        logger.info(f"成功加载 {len(data)} 条记录从 {dataset_path.name}")
                    else:
                        logger.error(f"文件 {dataset_path.name} 的内容不是一个列表。")
                        sys.exit(1)
            except Exception as e:
                logger.error(f"加载文件 {dataset_path.name} 失败: {e}")
                sys.exit(1)
        else:
            logger.error(f"数据集路径既不是文件也不是目录: {dataset_path}")
            sys.exit(1)

        if not all_data:
            logger.error("未能从任何文件中加载有效数据。")
            sys.exit(1)

        logger.info(f"总共加载了 {len(all_data)} 条记录。")
        
        if self.test_samples and isinstance(all_data, list):
            logger.info(f"已截取前 {self.test_samples} 个样本进行测试。")
            return all_data[:self.test_samples]
            
        return all_data

    def _find_matching_sample(self, baseline_sample: Dict, generated_data: List[Dict]) -> Optional[Dict]:
        """在生成数据中找到匹配的样本，使用source_file、code_line、function_name三元组匹配"""
        baseline_source_file = baseline_sample.get('source_file')
        baseline_code_line = baseline_sample.get('code_line')
        baseline_function_name = baseline_sample.get('function_name')
        
        # 使用三元组进行精确匹配
        for sample in generated_data:
            if (sample.get('source_file') == baseline_source_file and
                sample.get('code_line') == baseline_code_line and
                sample.get('function_name') == baseline_function_name):
                return sample
        
        # 如果三元组匹配失败，尝试通过ID匹配作为备选
        baseline_id = baseline_sample.get('id')
        if baseline_id:
            for sample in generated_data:
                if sample.get('id') == baseline_id:
                    return sample
        
        # 如果都匹配失败，返回None
        return None

    def _get_fingerprints_from_sql_list(self, sql_data: Any) -> Set[str]:
        """
        从SQL数据中提取指纹集合。
        """
        # 首先，使用递归工具从复杂结构中提取出扁平的SQL列表
        sql_list = recursively_extract_sql(sql_data)
        
        fingerprints = set()
        for sql in sql_list:
            if isinstance(sql, str) and sql.strip():
                try:
                    fingerprint = self.sql_extractor.extract(sql.strip())
                    fingerprints.add(fingerprint)
                except Exception as e:
                    logger.warning(f"为SQL计算指纹时出错: '{sql[:100]}...'. 错误: {e}")
        return fingerprints

    def run(self):
        """执行完整的数据集对比评估流程"""
        # 加载基准数据集和生成数据集
        baseline_data_path = self.config['data_config']['baseline_data_path']
        generated_data_path = self.config['data_config']['generated_data_path']
        
        baseline_data = self._load_dataset(baseline_data_path)
        generated_data = self._load_dataset(generated_data_path)
        
        comparison_results = []

        logger.info(f"开始对 {len(baseline_data)} 个基准样本进行对比评估...")
        for i, baseline_sample in enumerate(baseline_data):
            logger.info(f"--- 正在处理样本 {i+1}/{len(baseline_data)} (ID: {baseline_sample.get('id', 'N/A')}) ---")
            
            # 在生成数据中找到匹配的样本
            matching_generated_sample = self._find_matching_sample(baseline_sample, generated_data)
            
            if matching_generated_sample is None:
                logger.warning(f"未找到匹配的生成样本，跳过样本 {i+1}")
                comparison_results.append({
                    "sample_id": baseline_sample.get('id', f'sample_{i}'),
                    "source_file": baseline_sample.get('source_file', ''),
                    "code_line": baseline_sample.get('code_line', ''),
                    "function_name": baseline_sample.get('function_name', 'N/A'),
                    "orm_code": baseline_sample.get('orm_code', ''),
                    "caller": baseline_sample.get('caller', ''),
                    "callee": baseline_sample.get('callee', ''),
                    "code_meta_data": baseline_sample.get('code_meta_data', []),
                    "error": "未找到匹配的生成样本",
                    "baseline_sql": baseline_sample.get('sql_statement_list', baseline_sample.get('sql', [])),
                })
                continue
            
            try:
                # 从基准答案和生成数据中提取指纹
                baseline_sql_list = []
                if 'sql_statement_list' in baseline_sample:
                    baseline_sql_list = baseline_sample['sql_statement_list']
                elif 'sql' in baseline_sample:
                    baseline_sql_list = baseline_sample['sql']
                
                generated_sql_list = []
                if 'sql_statement_list' in matching_generated_sample:
                    generated_sql_list = matching_generated_sample['sql_statement_list']
                elif 'sql' in matching_generated_sample:
                    generated_sql_list = matching_generated_sample['sql']
                
                baseline_fingerprints = self._get_fingerprints_from_sql_list(baseline_sql_list)
                generated_fingerprints = self._get_fingerprints_from_sql_list(generated_sql_list)
                
                # 对比指纹
                common_fingerprints = baseline_fingerprints.intersection(generated_fingerprints)
                missing_fingerprints = baseline_fingerprints.difference(generated_fingerprints)
                extra_fingerprints = generated_fingerprints.difference(baseline_fingerprints)
                
                # 存储结果
                comparison_results.append({
                    "sample_id": baseline_sample.get('id', f'sample_{i}'),
                    "source_file": baseline_sample.get('source_file', ''),
                    "code_line": baseline_sample.get('code_line', ''),
                    "function_name": baseline_sample.get('function_name', 'N/A'),
                    "orm_code": baseline_sample.get('orm_code', ''),
                    "caller": baseline_sample.get('caller', ''),
                    "callee": baseline_sample.get('callee', ''),
                    "code_meta_data": baseline_sample.get('code_meta_data', []),
                    "baseline_sql": baseline_sql_list,
                    "generated_sql": generated_sql_list,
                    "metrics": {
                        "baseline_fingerprint_count": len(baseline_fingerprints),
                        "generated_fingerprint_count": len(generated_fingerprints),
                        "common_fingerprint_count": len(common_fingerprints),
                        "missing_fingerprint_count": len(missing_fingerprints),
                        "extra_fingerprint_count": len(extra_fingerprints),
                    },
                    "fingerprints": {
                        "common": sorted(list(common_fingerprints)),
                        "missing": sorted(list(missing_fingerprints)),
                        "extra": sorted(list(extra_fingerprints)),
                    }
                })
                logger.info(f"样本 {i+1} 处理完成。发现 {len(common_fingerprints)} 个一致指纹, {len(missing_fingerprints)} 个缺失, {len(extra_fingerprints)} 个多余。")

            except Exception as e:
                logger.error(f"处理样本 {i+1} 时发生严重错误: {e}", exc_info=True)
                # 记录失败的样本信息
                comparison_results.append({
                    "sample_id": baseline_sample.get('id', f'sample_{i}'),
                    "source_file": baseline_sample.get('source_file', ''),
                    "code_line": baseline_sample.get('code_line', ''),
                    "function_name": baseline_sample.get('function_name', 'N/A'),
                    "error": str(e),
                    "baseline_sql": baseline_sample.get('sql_statement_list', baseline_sample.get('sql', [])),
                })

        self._save_results(comparison_results)
        logger.info("数据集对比评估流程全部完成。")

    def _save_results(self, results: List[Dict]):
        """将结果保存到文件"""
        output_file = self.output_dir / "dataset_comparative_results.json"
        logger.info(f"正在将详细对比结果保存到: {output_file}")

        final_output = {
            "metadata": {
                "run_timestamp": datetime.now().isoformat(),
                "config_file": str(self.config_path),
                "evaluation_mode": self.mode,
                "baseline_data_path": self.config.get('data_config', {}).get('baseline_data_path'),
                "generated_data_path": self.config.get('data_config', {}).get('generated_data_path'),
                "total_samples": len(results),
            },
            "results": results
        }
        
        # 使用ensure_ascii=False确保中文字符正确保存
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2, cls=ChineseJSONEncoder)
        
        logger.info("结果保存成功。")


def main():
    """程序入口"""
    parser = argparse.ArgumentParser(description="数据集对比评估脚本")
    parser.add_argument("--config", type=str, required=True, help="配置文件路径")
    parser.add_argument("--output_dir", type=str, required=True, help="本次运行的结果输出目录")
    parser.add_argument("--mode", type=str, choices=['test', 'full'], default='full', help="评估模式: 'test' 或 'full'")
    
    args = parser.parse_args()

    try:
        evaluator = DatasetComparativeEvaluator(
            config_path=args.config,
            output_dir=args.output_dir,
            mode=args.mode
        )
        evaluator.run()
    except Exception as e:
        logger.error(f"评估过程中发生致命错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 