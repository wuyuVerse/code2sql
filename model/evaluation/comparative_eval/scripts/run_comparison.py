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
                device_map="auto",
                trust_remote_code=True
            ).to(device).eval()
            logger.info("模型和分词器加载成功。")
        except Exception as e:
            logger.error(f"加载模型或分词器失败: {e}")
            sys.exit(1)

    def _load_baseline_data(self) -> List[Dict]:
        """加载基准评估数据集"""
        baseline_path = Path(self.config['data_config']['baseline_data_path'])
        logger.info(f"正在加载基准评估集: {baseline_path}")
        if not baseline_path.exists():
            logger.error(f"基准评估集文件不存在: {baseline_path}")
            sys.exit(1)
            
        with open(baseline_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if self.test_samples and isinstance(data, list):
            logger.info(f"已截取前 {self.test_samples} 个样本进行测试。")
            return data[:self.test_samples]
        return data

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

    def _extract_sql_from_response(self, response: str) -> List[Any]:
        """从模型响应中提取SQL列表"""
        try:
            # 尝试直接解析JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # 如果失败，尝试从Markdown代码块中提取
            match = re.search(r"```json\s*([\s\S]+?)\s*```", response)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    logger.warning(f"无法解析Markdown代码块中的JSON: {match.group(1)}")
            else:
                logger.warning(f"响应不是有效的JSON，也未找到JSON代码块: {response}")
        return []

    def _get_fingerprints_from_sql_list(self, sql_list: List[Any]) -> Set[str]:
        """从SQL列表中提取所有指纹"""
        fingerprints = set()
        if not isinstance(sql_list, list):
            sql_list = [sql_list]

        for sql_item in sql_list:
            sql_text = ""
            if isinstance(sql_item, str):
                sql_text = sql_item
            elif isinstance(sql_item, dict) and sql_item.get("type") == "param_dependent":
                # 对于param_dependent，我们将其所有变体的sql合并处理
                for variant in sql_item.get("variants", []):
                    if isinstance(variant.get("sql"), str):
                        fp = self.sql_extractor.extract(variant["sql"])
                        if fp: fingerprints.add(fp)
                continue # 跳过后续处理
            elif isinstance(sql_item, dict) and "sql" in sql_item:
                sql_text = sql_item["sql"]

            if isinstance(sql_text, str) and sql_text.strip():
                fp = self.sql_extractor.extract(sql_text)
                if fp: fingerprints.add(fp)
        return fingerprints

    def run(self):
        """主执行函数"""
        logger.info("开始执行对比评估流程...")
        self._load_model_and_tokenizer()
        baseline_data = self._load_baseline_data()

        all_results = []
        
        from tqdm import tqdm
        for i, sample in enumerate(tqdm(baseline_data, desc="对比评估进度")):
            sample_id = sample.get('function_name', f'sample_{i}')
            logger.info(f"--- 正在处理样本: {sample_id} ---")

            # 1. 构建Prompt并推理
            prompt = self._build_prompt(sample)
            model_response = self._run_inference(prompt)
            model_sql_list = self._extract_sql_from_response(model_response)

            # 2. 获取基准和模型的指纹集
            baseline_sql_list = sample.get('sql_statement_list', [])
            baseline_fingerprints = self._get_fingerprints_from_sql_list(baseline_sql_list)
            model_fingerprints = self._get_fingerprints_from_sql_list(model_sql_list)

            # 3. 计算差异
            consistent_fps = baseline_fingerprints.intersection(model_fingerprints)
            missing_fps = baseline_fingerprints.difference(model_fingerprints)
            superfluous_fps = model_fingerprints.difference(baseline_fingerprints)
            
            # 4. 汇总结果
            result_summary = {
                "sample_id": sample_id,
                "prompt": prompt,
                "baseline_sql": baseline_sql_list,
                "model_response": model_response,
                "model_sql": model_sql_list,
                "comparison": {
                    "consistent_count": len(consistent_fps),
                    "missing_count": len(missing_fps),
                    "superfluous_count": len(superfluous_fps),
                    "consistent_fingerprints": list(consistent_fps),
                    "missing_fingerprints": list(missing_fps),
                    "superfluous_fingerprints": list(superfluous_fps),
                }
            }
            all_results.append(result_summary)
        
        # 5. 保存结果
        self._save_results(all_results)
        logger.info("对比评估全部完成！")

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