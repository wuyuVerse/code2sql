#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模型对比评估脚本

该脚本用于比较一个被评估模型与一个基准答案集，在相同输入下，
生成的SQL列表的差异。

核心逻辑：
1. 加载被评估模型和基准答案集。
2. 遍历基准集，对每个输入，使用模型进行推理。
3. 对基准SQL和模型生成的SQL进行指纹化。
4. 比较两个指纹集合，找出“一致”、“缺失”、“多余”的SQL。
5. 生成详细的JSON对比报告。
"""

import os
import sys
import json
import yaml
import logging
from pathlib import Path
import argparse
from typing import Dict, List, Any, Set, Tuple
import re # Added missing import for re
from utils.response_parser import parse_model_response, recursively_extract_sql
from datetime import datetime # Added missing import for datetime

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# --- 动态添加项目根目录到sys.path ---
# 这使得我们可以导入项目根目录下的模块，如 'data_processing'
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[4]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
        logger.info(f"项目根目录已添加: {PROJECT_ROOT}")
except IndexError:
    logger.error("无法确定项目根目录，请确保脚本位于预期的目录结构中。")
    sys.exit(1)


# --- 延迟导入核心模块 ---
# 这确保了在检查路径和配置之前不会因缺少依赖而崩溃
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from data_processing.cleaning.sql_feature_extractor import SQLFeatureExtractor
except ImportError as e:
    logger.error(f"导入核心模块失败: {e}")
    logger.error("请确保已安装 'torch', 'transformers' 等依赖，并检查项目结构是否正确。")
    sys.exit(1)


class ComparativeEvaluator:
    """对比评估器"""

    def __init__(self, config_path: str, output_dir: str, mode: str):
        self.config_path = Path(config_path)
        self.output_dir = Path(output_dir)
        self.mode = mode
        self.config = self._load_config()
        
        self.tokenizer = None
        self.model = None
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

    def _load_model_and_tokenizer(self):
        """加载分词器和模型"""
        model_path = self.config['model_config']['model_path']
        device = self.config['model_config']['device']
        logger.info(f"正在从 '{model_path}' 加载模型和分词器到 '{device}'...")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.bfloat16,
                device_map=device,
                trust_remote_code=True
            ).eval()
            logger.info("模型和分词器加载成功。")
        except Exception as e:
            logger.error(f"加载模型或分词器失败: {e}")
            sys.exit(1)

    def _load_baseline_data(self) -> List[Dict]:
        """从目录中加载所有基准评估数据集"""
        baseline_path = Path(self.config['data_config']['baseline_data_path'])
        logger.info(f"正在从目录中加载所有基准评估集: {baseline_path}")

        if not baseline_path.is_dir():
            logger.error(f"基准评估集路径不是一个有效的目录: {baseline_path}")
            sys.exit(1)
        
        all_data = []
        json_files = sorted(list(baseline_path.glob('*.json'))) # 排序以保证一致性
        
        if not json_files:
            logger.error(f"在目录 {baseline_path} 中未找到任何 .json 文件。")
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

        if not all_data:
            logger.error("未能从任何文件中加载有效数据。")
            sys.exit(1)

        logger.info(f"总共加载了 {len(all_data)} 条基准记录。")
        
        if self.test_samples and isinstance(all_data, list):
            logger.info(f"已截取前 {self.test_samples} 个样本进行测试。")
            return all_data[:self.test_samples]
            
        return all_data

    def _build_prompt(self, sample: Dict) -> str:
        """根据模板构建prompt"""
        template = self.config.get('prompt_config', {}).get('template', "{orm_code}")
        
        # 提取元数据
        code_meta_list = sample.get('code_meta_data', [])
        code_meta_data_str = json.dumps(code_meta_list, ensure_ascii=False) if code_meta_list else "{}"

        return template.format(
            function_name=sample.get('function_name', ''),
            orm_code=sample.get('orm_code', ''),
            caller=sample.get('caller', ''),
            callee=sample.get('callee', ''),
            code_meta_data_str=code_meta_data_str
        ).strip()

    def _run_inference(self, prompt: str) -> str:
        """运行单个样本的推理"""
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("模型或分词器未加载。")
            
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.config['model_config']['device'])

        generated_ids = self.model.generate(
            model_inputs.input_ids,
            max_new_tokens=1024,
            do_sample=False
        )
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        
        response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return response

    def _get_fingerprints_from_sql_list(self, model_output: Any) -> Set[str]:
        """
        从模型输出的任何结构中递归提取SQL，然后计算指纹集合。
        """
        # 首先，使用递归工具从复杂结构中提取出扁平的SQL列表
        sql_list = recursively_extract_sql(model_output)
        
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
        """执行完整的对比评估流程"""
        self._load_model_and_tokenizer()
        baseline_data = self._load_baseline_data()
        
        comparison_results = []

        logger.info(f"开始对 {len(baseline_data)} 个样本进行对比评估...")
        for i, sample in enumerate(baseline_data):
            logger.info(f"--- 正在处理样本 {i+1}/{len(baseline_data)} (ID: {sample.get('id', 'N/A')}) ---")
            
            prompt = self._build_prompt(sample)
            
            try:
                # 1. 模型推理
                model_response_raw = self._run_inference(prompt)
                
                # 2. 解析模型输出为结构化数据 (JSON/List/Dict)
                model_generated_structured = parse_model_response(model_response_raw)
                
                # 3. 从基准答案和模型输出中提取指纹
                baseline_sql_list = sample.get('sql', [])
                baseline_fingerprints = self._get_fingerprints_from_sql_list(baseline_sql_list)
                model_fingerprints = self._get_fingerprints_from_sql_list(model_generated_structured)
                
                # 4. 对比指纹
                common_fingerprints = baseline_fingerprints.intersection(model_fingerprints)
                missing_fingerprints = baseline_fingerprints.difference(model_fingerprints)
                extra_fingerprints = model_fingerprints.difference(baseline_fingerprints)
                
                # 5. 存储结果
                comparison_results.append({
                    "sample_id": sample.get('id', f'sample_{i}'),
                    "function_name": sample.get('function_name', 'N/A'),
                    "orm_code": sample.get('orm_code', ''),
                    "prompt": prompt,
                    "baseline_sql": baseline_sql_list,
                    "model_response_raw": model_response_raw,
                    "model_generated_structured": model_generated_structured, # 保存完整的结构化输出
                    "metrics": {
                        "baseline_fingerprint_count": len(baseline_fingerprints),
                        "model_fingerprint_count": len(model_fingerprints),
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
                    "sample_id": sample.get('id', f'sample_{i}'),
                    "function_name": sample.get('function_name', 'N/A'),
                    "error": str(e),
                    "prompt": prompt
                })

        self._save_results(comparison_results)
        logger.info("对比评估流程全部完成。")

    def _save_results(self, results: List[Dict]):
        """将结果保存到文件"""
        output_file = self.output_dir / "comparative_results.json"
        logger.info(f"正在将详细对比结果保存到: {output_file}")

        final_output = {
            "metadata": {
                "run_timestamp": datetime.now().isoformat(),
                "config_file": str(self.config_path),
                "evaluation_mode": self.mode,
                "model_path": self.config.get('model_config', {}).get('model_path'),
                "baseline_data_path": self.config.get('data_config', {}).get('baseline_data_path'),
                "total_samples": len(results),
            },
            "results": results
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)
        
        logger.info("结果保存成功。")


def main():
    """程序入口"""
    parser = argparse.ArgumentParser(description="模型对比评估脚本")
    parser.add_argument("--config", type=str, required=True, help="配置文件路径")
    parser.add_argument("--output_dir", type=str, required=True, help="本次运行的结果输出目录")
    parser.add_argument("--mode", type=str, choices=['test', 'full'], default='full', help="评估模式: 'test' 或 'full'")
    
    args = parser.parse_args()

    try:
        evaluator = ComparativeEvaluator(
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