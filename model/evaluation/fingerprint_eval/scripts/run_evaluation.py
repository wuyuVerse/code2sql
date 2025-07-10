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

# 添加项目根目录到sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 延迟导入，避免环境问题
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, GenerationConfig
    from data_processing.cleaning.sql_feature_extractor import match_single_sql
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
        
        # 从配置加载或使用覆盖的输出目录
        self.output_dir = self.config.get('output_config', {}).get('output_dir', 'evaluation_results')
        if output_dir_override:
            self.output_dir = output_dir_override
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化结果存储
        self.eval_results = []
        self.stats = {
            'total_samples': 0,
            'successful_inference': 0,
            'valid_sql_generated': 0,
            'fingerprint_matched': 0,
            'parse_errors': 0,
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
            
            # 编码输入
            inputs = self.tokenizer.encode(text, return_tensors="pt")
            inputs = inputs.to(self.model.device)
            
            # 生成配置
            gen_config = GenerationConfig(
                max_new_tokens=self.config['inference_config']['generate_config']['max_new_tokens'],
                temperature=self.config['inference_config']['generate_config']['temperature'],
                top_p=self.config['inference_config']['generate_config']['top_p'],
                do_sample=self.config['inference_config']['generate_config']['do_sample'],
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            # 推理
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    generation_config=gen_config
                )
            
            # 解码输出
            response = self.tokenizer.decode(
                outputs[0][len(inputs[0]):], 
                skip_special_tokens=True
            )
            
            return response.strip()
            
        except Exception as e:
            logger.warning(f"推理失败: {e}")
            return ""

    def _recursively_extract_sql(self, data: Any) -> List[str]:
        """
        递归地遍历数据结构以提取所有SQL字符串。
        """
        extracted_sql = []
        if isinstance(data, str):
            # 基本情况：它是一个SQL字符串
            if data.strip():
                extracted_sql.append(data.strip())
        elif isinstance(data, dict):
            # 如果是param_dependent结构
            if data.get("type") == "param_dependent" and "variants" in data:
                for variant in data.get("variants", []):
                    # 从变体的sql字段中递归提取
                    extracted_sql.extend(self._recursively_extract_sql(variant.get("sql")))
            # 这里可以添加其他字典结构的处理
        elif isinstance(data, list):
            # 如果是列表，则迭代并递归
            for item in data:
                extracted_sql.extend(self._recursively_extract_sql(item))
        
        return extracted_sql

    def parse_sql_response(self, response: str) -> List[str]:
        """
        解析模型的JSON类响应以提取所有SQL语句，
        能处理像 'param_dependent' 这样的复杂结构。
        """
        if not response.strip():
            return []

        # 尝试将响应解析为JSON对象
        try:
            # LLM可能返回一个不完全是JSON的字符串，我们尝试找到其中的JSON部分
            # 通常是我们期望的列表格式 `[...]`
            start = response.find('[')
            end = response.rfind(']')
            if start != -1 and end != -1 and start < end:
                json_string = response[start:end+1]
                parsed_data = json.loads(json_string)
            else:
                # 如果找不到 `[]`，尝试直接解析整个字符串
                try:
                    parsed_data = json.loads(response)
                except json.JSONDecodeError:
                    # 如果不能解析为JSON，则将其视为单个原始SQL语句
                    logger.debug(f"响应不是有效的JSON，将其视为原始字符串: {response}")
                    return [response.strip()] if response.strip() else []
        except json.JSONDecodeError:
            logger.warning(f"无法将模型响应解析为JSON。将其视为原始字符串。响应: {response}")
            return [response.strip()] if response.strip() else []
        
        # 获得解析后的数据后 (很可能是一个列表)，递归地提取SQL
        return self._recursively_extract_sql(parsed_data)
    
    def evaluate_sql_quality(self, sql_list: List[str]) -> Dict:
        """评估SQL质量"""
        if not sql_list:
            return {
                'total_sql': 0,
                'valid_sql': 0,
                'matched_sql': 0,
                'excluded_sql': 0,
                'fingerprint_results': []
            }
        
        fingerprint_cache_path = self.config['data_config']['fingerprint_cache_path']
        fingerprint_results = []
        valid_count = 0
        matched_count = 0
        excluded_count = 0
        
        for sql in sql_list:
            if not sql.strip():
                continue
            
            try:
                match_result = match_single_sql(sql.strip(), fingerprint_cache_path)
                fingerprint_results.append({
                    'sql': sql,
                    'match_result': match_result
                })
                
                if not match_result.get('excluded', False):
                    valid_count += 1
                    if match_result.get('matched', False):
                        matched_count += 1
                else:
                    excluded_count += 1
                    
            except Exception as e:
                logger.warning(f"SQL验证失败: {e}")
                fingerprint_results.append({
                    'sql': sql,
                    'match_result': {'error': str(e)}
                })
        
        return {
            'total_sql': len(sql_list),
            'valid_sql': valid_count,
            'matched_sql': matched_count,
            'excluded_sql': excluded_count,
            'fingerprint_results': fingerprint_results
        }
    
    def run_evaluation(self):
        """运行完整评估"""
        logger.info("开始模型评估...")
        
        # 加载模型
        self.load_model()
        
        # 加载验证数据
        eval_samples = self.load_eval_data()
        self.stats['total_samples'] = len(eval_samples)
        
        # 逐个处理样本
        for i, sample in enumerate(tqdm(eval_samples, desc="评估进度")):
            
            # 创建提示词
            prompt = self.create_prompt(sample)
            
            # 推理
            response = self.run_inference(prompt)
            
            # 处理结果
            result = {
                'sample_id': sample['sample_id'],
                'prompt': prompt,
                'response': response,
                'parsed_sql': [],
                'sql_evaluation': {},
                'inference_success': bool(response.strip())
            }
            
            if response.strip():
                self.stats['successful_inference'] += 1
                
                try:
                    # 解析SQL
                    sql_list = self.parse_sql_response(response)
                    result['parsed_sql'] = sql_list
                    
                    if sql_list:
                        # SQL质量评估
                        sql_eval = self.evaluate_sql_quality(sql_list)
                        result['sql_evaluation'] = sql_eval
                        
                        # 更新统计
                        if sql_eval['valid_sql'] > 0:
                            self.stats['valid_sql_generated'] += 1
                        if sql_eval['matched_sql'] > 0:
                            self.stats['fingerprint_matched'] += 1
                    
                except Exception as e:
                    logger.warning(f"处理第 {i} 个样本时出错: {e}")
                    result['parse_error'] = str(e)
                    self.stats['parse_errors'] += 1
            else:
                self.stats['inference_errors'] += 1
            
            self.eval_results.append(result)
        
        # 生成和保存结果
        final_stats = self.generate_final_statistics()
        self.save_results(final_stats)
        
        logger.info("评估完成!")
        return final_stats
    
    def generate_final_statistics(self) -> Dict:
        """生成最终统计"""
        stats = self.stats.copy()
        
        total = stats['total_samples']
        if total > 0:
            stats['inference_success_rate'] = stats['successful_inference'] / total
            stats['valid_sql_rate'] = stats['valid_sql_generated'] / total
            stats['fingerprint_match_rate'] = stats['fingerprint_matched'] / total
            stats['parse_error_rate'] = stats['parse_errors'] / total
            stats['inference_error_rate'] = stats['inference_errors'] / total
        
        # SQL级别统计
        total_sql = sum(len(r.get('parsed_sql', [])) for r in self.eval_results)
        valid_sql = sum(r.get('sql_evaluation', {}).get('valid_sql', 0) for r in self.eval_results)
        matched_sql = sum(r.get('sql_evaluation', {}).get('matched_sql', 0) for r in self.eval_results)
        
        stats['total_sql_generated'] = total_sql
        stats['total_valid_sql'] = valid_sql
        stats['total_matched_sql'] = matched_sql
        
        if total_sql > 0:
            stats['sql_validity_rate'] = valid_sql / total_sql
            stats['sql_match_rate'] = matched_sql / total_sql
        
        return stats
    
    def save_results(self, final_stats: Dict):
        """保存评估结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存详细结果
        results_file = self.output_dir / "evaluation_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'config': self.config,
                'statistics': final_stats,
                'detailed_results': self.eval_results
            }, f, ensure_ascii=False, indent=2)
        
        # 保存统计摘要
        summary_file = self.output_dir / f"evaluation_summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(final_stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存: {results_file}")
        logger.info(f"摘要已保存: {summary_file}")
        
        # 打印摘要
        self.print_summary(final_stats)
    
    def print_summary(self, stats: Dict):
        """打印评估摘要"""
        print("\n" + "="*80)
        print("模型评估结果摘要")
        print("="*80)
        print(f"模型路径: {self.config['model_config']['model_path']}")
        print(f"验证集: {self.config['data_config']['eval_data_path']}")
        print(f"总样本数: {stats['total_samples']}")
        
        print("\n📊 推理结果:")
        print(f"  ✅ 成功推理: {stats['successful_inference']}/{stats['total_samples']} ({stats.get('inference_success_rate', 0):.2%})")
        print(f"  ❌ 推理错误: {stats['inference_errors']} ({stats.get('inference_error_rate', 0):.2%})")
        print(f"  ⚠️  解析错误: {stats['parse_errors']} ({stats.get('parse_error_rate', 0):.2%})")
        
        print("\n🎯 SQL生成质量:")
        print(f"  📝 生成有效SQL样本: {stats['valid_sql_generated']}/{stats['total_samples']} ({stats.get('valid_sql_rate', 0):.2%})")
        print(f"  🎯 指纹匹配样本: {stats['fingerprint_matched']}/{stats['total_samples']} ({stats.get('fingerprint_match_rate', 0):.2%})")
        
        print(f"\n📈 SQL语句级别统计:")
        print(f"  总生成SQL数: {stats.get('total_sql_generated', 0)}")
        print(f"  有效SQL数: {stats.get('total_valid_sql', 0)} ({stats.get('sql_validity_rate', 0):.2%})")
        print(f"  指纹匹配SQL数: {stats.get('total_matched_sql', 0)} ({stats.get('sql_match_rate', 0):.2%})")
        print("="*80)


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
        results = evaluator.run_evaluation()
        
        print(f"\n✅ 评估完成！结果已保存到: {evaluator.output_dir}")
        
    except Exception as e:
        logger.error(f"评估失败: {e}")
        raise


if __name__ == "__main__":
    main() 