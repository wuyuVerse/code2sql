#!/usr/bin/env python3
"""
简化的模型评估运行脚本

直接使用transformers库进行推理，避免LLaMA-Factory CLI的复杂性
"""

import os
import sys
import json
import logging
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse
from tqdm import tqdm
import torch
from utils.response_parser import parse_model_response, recursively_extract_sql

# 添加项目根目录到sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 延迟导入，避免环境问题
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, GenerationConfig
    from data_processing.cleaning.sql_feature_extractor import (
        process_json_and_compare,
        load_fingerprints,
    )
    from config.training.data_conversion.orm2sql_prompt_template import PROMPT_TEMPLATE
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保已安装transformers和其他必要依赖")
    sys.exit(1)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleModelEvaluator:
    """简化的模型评估器"""
    
    def __init__(self, config_path: str, output_dir_override: Optional[str] = None):
        """
        初始化评估器
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self.load_config(config_path)
        self.model = None
        self.tokenizer = None
        
        # 从配置加载或使用覆盖的输出目录，并确保是Path对象
        output_dir_str = output_dir_override or self.config.get('output_config', {}).get('output_dir', 'evaluation_results')
        self.output_dir = Path(output_dir_str).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化结果存储
        self.eval_results = []
        self.stats = {
            'total_samples': 0,
            'successful_inference': 0,
            'valid_sql_generated': 0, # 基于解析是否成功
            'parse_errors': 0, # 基于通用解析函数
            'inference_errors': 0
        }
        
        logger.info(f"评估器初始化完成，输出目录: {self.output_dir}")
    
    def load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"已加载配置文件: {config_path}")
        return config
    
    def load_model(self):
        """加载模型和分词器"""
        model_path = self.config['model_config']['model_path']
        logger.info(f"正在加载模型: {model_path}")
        
        try:
            # 加载分词器
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=self.config['environment_config']['trust_remote_code']
            )
            
            # 加载模型
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.bfloat16 if self.config['environment_config']['bf16'] else torch.float32,
                device_map="auto",
                trust_remote_code=self.config['environment_config']['trust_remote_code']
            )
            
            logger.info("模型加载成功")
            
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    def load_eval_data(self) -> List[Dict]:
        """加载验证集数据"""
        eval_data_path = Path(self.config['data_config']['eval_data_path'])
        logger.info(f"正在加载验证集: {eval_data_path}")
        
        with open(eval_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 转换为列表格式
        eval_samples = []
        for key, value in data.items():
            sample = value.copy()
            sample['sample_id'] = key
            eval_samples.append(sample)
        
        # 限制样本数量（如果配置了）
        max_samples = self.config['data_config'].get('max_samples')
        if max_samples:
            eval_samples = eval_samples[:max_samples]
            logger.info(f"限制评估样本数量为: {max_samples}")
        
        # 测试模式
        if self.config['debug_config'].get('test_mode', False):
            test_samples = self.config['debug_config'].get('test_samples', 10)
            eval_samples = eval_samples[:test_samples]
            logger.info(f"测试模式，使用 {test_samples} 个样本")
        
        logger.info(f"成功加载 {len(eval_samples)} 条验证样本")
        return eval_samples
    
    def create_prompt(self, sample: Dict) -> str:
        """创建推理提示词"""
        function_name = sample.get('code_key', '未知函数')
        orm_code = sample.get('code_value', '')
        
        # 处理callers
        callers = sample.get('callers', [])
        caller = json.dumps(callers[0], ensure_ascii=False) if callers else ""
        callee = ""
        
        # 构建code_meta_data
        code_meta_data = [{
            'code_file': sample.get('code_file', ''),
            'code_start_line': sample.get('code_start_line', 0),
            'code_end_line': sample.get('code_end_line', 0),
            'code_key': sample.get('code_key', ''),
            'code_value': sample.get('code_value', ''),
            'code_label': sample.get('code_label', 0),
            'code_type': sample.get('code_type', 0),
            'code_version': sample.get('code_version', '')
        }]
        code_meta_data_str = json.dumps(code_meta_data, ensure_ascii=False, indent=2)
        
        prompt = PROMPT_TEMPLATE.format(
            function_name=function_name,
            orm_code=orm_code,
            caller=caller,
            callee=callee,
            code_meta_data_str=code_meta_data_str
        )
        return prompt.strip()
    
    def run_inference(self, prompt: str) -> str:
        """运行单个样本的推理"""
        if self.model is None or self.tokenizer is None:
            logger.error("模型或分词器未加载")
            return ""
            
        try:
            # 构建对话格式的输入
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            # 使用分词器的chat template
            text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
            
            # 创建 GenerationConfig
            generation_config = GenerationConfig(
                max_new_tokens=self.config['model_config'].get('max_new_tokens', 1024),
                do_sample=self.config['model_config'].get('do_sample', True),
                top_p=self.config['model_config'].get('top_p', 0.7),
                temperature=self.config['model_config'].get('temperature', 0.95),
            )

            generated_ids = self.model.generate(
                model_inputs.input_ids,
                attention_mask=model_inputs.attention_mask,
                generation_config=generation_config
            )
            
            # 解码时跳过特殊token
            response = self.tokenizer.decode(generated_ids[0], skip_special_tokens=True)
            
            # 清理 response，只取模型生成的部分
            # response 通常会包含输入的prompt，需要移除
            # 找到 text 在 response 中的位置并截取之后的内容
            prompt_in_response_index = response.find(text)
            if prompt_in_response_index != -1:
                response = response[prompt_in_response_index + len(text):].strip()
            
            # 更进一步，找到 assistant 角色的开始标记
            assistant_marker = "assistant\n"
            marker_index = response.find(assistant_marker)
            if marker_index != -1:
                response = response[marker_index + len(assistant_marker):].strip()

            return response
            
        except Exception as e:
            logger.error(f"推理过程中发生错误: {e}", exc_info=True)
            return ""
    
    def run_evaluation(self):
        """运行完整的评估流程"""
        if not self.model or not self.tokenizer:
            self.load_model()
        
        eval_samples = self.load_eval_data()
        self.stats['total_samples'] = len(eval_samples)
        
        # 加载指纹库
        fingerprint_db_path = self.config['data_config'].get('fingerprint_db_path')
        csv_fingerprints, fingerprint_to_sql = None, None
        if not fingerprint_db_path:
            logger.warning("配置文件中未指定 fingerprint_db_path，无法进行指纹覆盖率计算")
        else:
            try:
                csv_fingerprints, fingerprint_to_sql = load_fingerprints(fingerprint_db_path)
                logger.info(f"成功加载 {len(csv_fingerprints)} 个指纹")
            except Exception as e:
                logger.error(f"加载指纹库失败: {e}", exc_info=True)
                fingerprint_db_path = None # 标记为失败，后续不再尝试

        pbar = tqdm(total=self.stats['total_samples'], desc="模型评估中")

        for sample in eval_samples:
            try:
                prompt = self.create_prompt(sample)
                response = self.run_inference(prompt)
            
                if response:
                    self.stats['successful_inference'] += 1
                    # 使用通用解析函数
                    parsed_response = parse_model_response(response)
                    sql_list = recursively_extract_sql(parsed_response)

                    result_entry = {
                        'sample_id': sample['sample_id'],
                        'prompt': prompt,
                        'response': response,
                        'parsed_sql': sql_list, # 保存提取后的SQL列表
                        'ground_truth_sql': sample.get('sql', 'N/A')
                    }
                    
                    if sql_list:
                        self.stats['valid_sql_generated'] += 1
                    
                    self.eval_results.append(result_entry)
                else:
                    self.stats['inference_errors'] += 1
            except Exception as e:
                logger.error(f"处理样本 {sample.get('sample_id', 'N/A')} 时发生严重错误: {e}", exc_info=True)
                self.stats['inference_errors'] += 1
            
            pbar.update(1)

        pbar.close()
        
        # 将原始推理结果保存到文件，供后续分析使用
        raw_results_path = self.output_dir / "evaluation_results.json"
        
        # --- 防御性修复 ---
        # 在写入文件前，再次确保输出目录一定存在，避免因未知状态问题导致目录丢失
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(raw_results_path, 'w', encoding='utf-8') as f:
            json.dump(self.eval_results, f, indent=4, ensure_ascii=False)
        logger.info(f"原始评估结果已保存到: {raw_results_path}")

        # 调用指纹分析函数，该函数会将结果直接写入文件，而不是返回
        if fingerprint_db_path and csv_fingerprints is not None:
            logger.info("开始进行指纹覆盖率分析...")
            try:
                # 调用函数，但不期望有返回值
                process_json_and_compare(
                    json_filepath=str(raw_results_path),
                    csv_fingerprints=csv_fingerprints,
                    fingerprint_to_sql=fingerprint_to_sql,
                    output_dir=str(self.output_dir),
                    sql_key='parsed_sql'
                )
                logger.info("指纹覆盖率分析完成，结果已写入输出目录。")

                # 由于核心报告由 process_json_and_compare 生成，我们尝试读取它创建的摘要文件
                analysis_report = self.load_generated_report()

            except Exception as e:
                logger.error(f"指纹覆盖率分析失败: {e}", exc_info=True)
                analysis_report = None # 分析失败，报告为空
        else:
            analysis_report = None # 未进行分析，报告为空
        
        # 保存并打印我们能获取到的信息
        self.save_inference_summary()
        self.print_summary(analysis_report if analysis_report else self.stats)

    def load_generated_report(self) -> Optional[Dict]:
        """尝试加载由 process_json_and_compare 生成的统计报告"""
        report_path = self.output_dir / "statistics_summary.json"
        if report_path.exists():
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                logger.info(f"成功加载分析报告: {report_path}")
                return report
            except Exception as e:
                logger.error(f"加载分析报告失败: {e}", exc_info=True)
        else:
            logger.warning(f"分析报告文件不存在: {report_path}")
        return None

    def save_inference_summary(self):
        """仅保存本次推理的基本统计信息"""
        summary_stats = self.generate_final_statistics()
        summary_path = self.output_dir / "evaluation_summary.json"
        try:
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_stats, f, indent=4, ensure_ascii=False)
            logger.info(f"推理过程摘要已保存到: {summary_path}")
        except Exception as e:
            logger.error(f"保存推理过程摘要失败: {e}", exc_info=True)
    
    def generate_final_statistics(self) -> Dict:
        """
        生成最终的统计数据。
        注意：这个方法现在更多的是一个占位符，因为核心统计已移至 process_json_and_compare。
        我们只计算一些基本的推理统计。
        """
        return self.stats

    def save_results(self, analysis_report: Optional[Dict]):
        """
        此方法的功能已被拆分和重构。
        - 推理摘要保存由 save_inference_summary() 完成。
        - 详细报告由 process_json_and_compare() 直接写入。
        保留此方法以防万一，但标记为废弃。
        """
        logger.warning("方法 `save_results` 已被废弃。")
        pass


    def _compute_fingerprint_coverage(self):
        """
        此方法已被 process_json_and_compare 函数替代，保留为空或标记为废弃。
        """
        logger.warning("方法 `_compute_fingerprint_coverage` 已被废弃。")
        pass


    def print_summary(self, final_report: Dict):
        """
        打印评估总结。
        
        Args:
            final_report: 最终的报告字典，可以是详细报告或基本统计。
        """
        logger.info("\n" + "="*20 + " 评估总结 " + "="*20)
        
        if not final_report:
            logger.warning("没有可用的报告信息。")
            final_report = self.stats # Fallback

        # 优雅地打印报告内容
        for key, value in final_report.items():
            if isinstance(value, dict):
                logger.info(f"\n--- {key.replace('_', ' ').title()} ---")
                for sub_key, sub_value in value.items():
                    # 格式化浮点数
                    if isinstance(sub_value, float):
                        sub_value_str = f"{sub_value:.2%}"
                    else:
                        sub_value_str = str(sub_value)
                    logger.info(f"  {sub_key.replace('_', ' ').title()}: {sub_value_str}")
            elif isinstance(value, list):
                 logger.info(f"{key.replace('_', ' ').title()}: (包含 {len(value)} 项)")
            else:
                logger.info(f"{key.replace('_', ' ').title()}: {value}")
        
        logger.info("="*52 + "\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="模型评估脚本")
    parser.add_argument("--config", type=str, required=True, help="配置文件路径")
    parser.add_argument("--output_dir", type=str, default=None, help="覆盖配置文件中的输出目录")
    
    args = parser.parse_args()
    
    try:
        # 初始化评估器
        evaluator = SimpleModelEvaluator(config_path=args.config, output_dir_override=args.output_dir)
        
        # 运行评估
        evaluator.run_evaluation()
        
        print(f"\n✅ 评估完成！结果已保存到: {evaluator.output_dir}")
        
    except Exception as e:
        logger.error(f"评估失败: {e}")
        raise


if __name__ == "__main__":
    main() 