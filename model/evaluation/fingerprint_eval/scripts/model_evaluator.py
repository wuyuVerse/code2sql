#!/usr/bin/env python3
"""
模型评估器

使用训练好的模型对验证集进行推理，并使用sql_feature_extractor进行验证
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import argparse
import pickle
import re
from tqdm import tqdm
import subprocess

# 添加项目根目录到sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 延迟导入，避免环境问题
try:
    from data_processing.cleaning.sql_feature_extractor import SQLFeatureExtractor, match_single_sql
    from config.training.data_conversion.orm2sql_prompt_template import PROMPT_TEMPLATE
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保项目依赖已正确安装")
    sys.exit(1)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelEvaluator:
    """模型评估器"""
    
    def __init__(self, 
                 model_path: str,
                 eval_data_path: str,
                 output_dir: str = "evaluation_results",
                 fingerprint_cache_path: Optional[str] = None):
        """
        初始化评估器
        
        Args:
            model_path: 训练好的模型路径
            eval_data_path: 验证集数据路径
            output_dir: 评估结果输出目录
            fingerprint_cache_path: SQL指纹缓存文件路径
        """
        self.model_path = Path(model_path)
        self.eval_data_path = Path(eval_data_path)
        self.output_dir = Path(output_dir)
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置指纹缓存路径
        if fingerprint_cache_path is None:
            self.fingerprint_cache_path = PROJECT_ROOT / "data_processing" / "cleaning" / "fingerprint_cache.pkl"
        else:
            self.fingerprint_cache_path = Path(fingerprint_cache_path)
        
        # 验证路径
        if not self.model_path.exists():
            raise FileNotFoundError(f"模型路径不存在: {self.model_path}")
        if not self.eval_data_path.exists():
            raise FileNotFoundError(f"验证集路径不存在: {self.eval_data_path}")
        
        logger.info(f"模型路径: {self.model_path}")
        logger.info(f"验证集路径: {self.eval_data_path}")
        logger.info(f"输出目录: {self.output_dir}")
        logger.info(f"指纹缓存: {self.fingerprint_cache_path}")
        
        # 初始化结果存储
        self.eval_results = []
        self.evaluation_stats = {
            'total_samples': 0,
            'successful_inference': 0,
            'valid_sql_generated': 0,
            'fingerprint_matched': 0,
            'parse_errors': 0,
            'inference_errors': 0
        }
    
    def load_eval_data(self) -> List[Dict]:
        """加载验证集数据"""
        logger.info("正在加载验证集数据...")
        
        with open(self.eval_data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 转换为列表格式以便处理
        eval_samples = []
        for key, value in data.items():
            sample = value.copy()
            sample['sample_id'] = key
            eval_samples.append(sample)
        
        logger.info(f"成功加载 {len(eval_samples)} 条验证样本")
        return eval_samples
    
    def format_code_metadata(self, sample: Dict) -> str:
        """格式化代码元数据"""
        # 提取callers信息
        callers = sample.get('callers', [])
        caller_str = ""
        if callers:
            caller_str = json.dumps(callers[0], ensure_ascii=False) if callers else ""
        
        # 构建code_meta_data格式
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
        
        return json.dumps(code_meta_data, ensure_ascii=False, indent=2)
    
    def create_prompt(self, sample: Dict) -> str:
        """根据验证样本创建推理提示词"""
        function_name = sample.get('code_key', '未知函数')
        orm_code = sample.get('code_value', '')
        caller = json.dumps(sample.get('callers', []), ensure_ascii=False) if sample.get('callers') else ""
        callee = ""  # 验证集中可能没有这个字段
        code_meta_data_str = self.format_code_metadata(sample)
        
        prompt = PROMPT_TEMPLATE.format(
            function_name=function_name,
            orm_code=orm_code,
            caller=caller,
            callee=callee,
            code_meta_data_str=code_meta_data_str
        )
        return prompt.strip()
    
    def run_inference_with_llamafactory(self, prompts: List[str], batch_size: int = 1) -> List[str]:
        """
        使用LLaMA-Factory进行批量推理
        
        Args:
            prompts: 提示词列表
            batch_size: 批处理大小
            
        Returns:
            推理结果列表
        """
        logger.info(f"开始使用LLaMA-Factory进行推理，共 {len(prompts)} 个样本")
        
        # 创建临时输入文件
        temp_input_file = self.output_dir / "temp_input.jsonl"
        
        # 写入JSONL格式的输入数据
        with open(temp_input_file, 'w', encoding='utf-8') as f:
            for i, prompt in enumerate(prompts):
                sample = {
                    "instruction": prompt,
                    "input": "",
                    "output": "",
                    "sample_id": i
                }
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        # 设置输出文件
        temp_output_file = self.output_dir / "temp_output.jsonl"
        
        # 构建LLaMA-Factory推理命令
        cmd = [
            "llamafactory-cli", "train",  # 使用train命令但配置为预测模式
            "--stage", "sft",
            "--model_name_or_path", str(self.model_path),
            "--template", "qwen",  # 根据实际模型调整
            "--finetuning_type", "full",
            "--dataset_dir", str(self.output_dir),
            "--dataset", "temp_eval",
            "--cutoff_len", "2048",
            "--max_samples", str(len(prompts)),
            "--per_device_eval_batch_size", str(batch_size),
            "--predict_with_generate",
            "--do_predict",
            "--output_dir", str(self.output_dir / "temp_prediction"),
            "--overwrite_output_dir"
        ]
        
        # 创建临时数据集配置
        dataset_info = {
            "temp_eval": {
                "file_name": "temp_input.jsonl",
                "columns": {
                    "prompt": "instruction",
                    "response": "output"
                }
            }
        }
        
        dataset_info_file = self.output_dir / "dataset_info.json"
        with open(dataset_info_file, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)
        
        try:
            # 执行推理命令
            logger.info("执行LLaMA-Factory推理命令...")
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  cwd=str(PROJECT_ROOT / "model" / "training" / "LLaMA-Factory"),
                                  timeout=3600)  # 1小时超时
            
            if result.returncode != 0:
                logger.error(f"推理命令执行失败: {result.stderr}")
                raise RuntimeError(f"推理失败: {result.stderr}")
            
            # 读取推理结果
            prediction_file = self.output_dir / "temp_prediction" / "generated_predictions.jsonl"
            if not prediction_file.exists():
                raise FileNotFoundError("推理结果文件不存在")
            
            responses = []
            with open(prediction_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        pred_data = json.loads(line)
                        responses.append(pred_data.get('predict', ''))
            
            logger.info(f"成功完成推理，获得 {len(responses)} 个结果")
            return responses
            
        except Exception as e:
            logger.error(f"推理过程出错: {e}")
            # 返回空结果列表，长度与输入相同
            return [""] * len(prompts)
        
        finally:
            # 清理临时文件
            try:
                temp_input_file.unlink(missing_ok=True)
                dataset_info_file.unlink(missing_ok=True)
            except:
                pass
    
    def parse_sql_response(self, response: str) -> List[str]:
        """
        解析模型响应，提取SQL语句列表
        
        Args:
            response: 模型生成的响应
            
        Returns:
            SQL语句列表
        """
        if not response.strip():
            return []
        
        try:
            # 尝试直接解析JSON
            sql_list = json.loads(response)
            if isinstance(sql_list, list):
                return [str(sql) for sql in sql_list if sql]
            elif isinstance(sql_list, str):
                return [sql_list] if sql_list else []
            else:
                return []
        except json.JSONDecodeError:
            # JSON解析失败，尝试其他方法
            pass
        
        # 尝试提取JSON数组模式
        json_pattern = r'\[(.*?)\]'
        matches = re.findall(json_pattern, response, re.DOTALL)
        if matches:
            try:
                sql_array = json.loads(f'[{matches[0]}]')
                return [str(sql) for sql in sql_array if sql]
            except:
                pass
        
        # 尝试提取引号包围的SQL语句
        sql_pattern = r'"([^"]*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)[^"]*)"'
        sql_matches = re.findall(sql_pattern, response, re.IGNORECASE)
        if sql_matches:
            return sql_matches
        
        # 如果都失败了，返回原始响应作为单个SQL
        return [response.strip()] if response.strip() else []
    
    def evaluate_sql_with_fingerprint(self, sql_list: List[str]) -> Dict:
        """
        使用SQL指纹验证SQL质量
        
        Args:
            sql_list: SQL语句列表
            
        Returns:
            评估结果字典
        """
        if not sql_list:
            return {
                'total_sql': 0,
                'valid_sql': 0,
                'matched_sql': 0,
                'excluded_sql': 0,
                'fingerprint_results': []
            }
        
        fingerprint_results = []
        valid_count = 0
        matched_count = 0
        excluded_count = 0
        
        for sql in sql_list:
            if not sql.strip():
                continue
                
            try:
                # 使用sql_feature_extractor的验证函数
                match_result = match_single_sql(sql.strip(), str(self.fingerprint_cache_path))
                fingerprint_results.append({
                    'sql': sql,
                    'match_result': match_result
                })
                
                # 统计
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
    
    def run_evaluation(self, max_samples: Optional[int] = None, batch_size: int = 1) -> Dict:
        """
        运行完整的模型评估
        
        Args:
            max_samples: 最大评估样本数（用于测试）
            batch_size: 推理批处理大小
            
        Returns:
            评估结果统计
        """
        logger.info("开始模型评估...")
        
        # 加载验证数据
        eval_samples = self.load_eval_data()
        
        if max_samples:
            eval_samples = eval_samples[:max_samples]
            logger.info(f"限制评估样本数量为: {max_samples}")
        
        self.evaluation_stats['total_samples'] = len(eval_samples)
        
        # 创建提示词
        logger.info("生成推理提示词...")
        prompts = []
        for sample in tqdm(eval_samples, desc="生成提示词"):
            prompt = self.create_prompt(sample)
            prompts.append(prompt)
        
        # 批量推理
        logger.info("开始批量推理...")
        responses = self.run_inference_with_llamafactory(prompts, batch_size)
        
        # 处理推理结果
        logger.info("处理推理结果...")
        for i, (sample, response) in enumerate(tqdm(zip(eval_samples, responses), desc="处理结果", total=len(eval_samples))):
            
            result = {
                'sample_id': sample['sample_id'],
                'prompt': prompts[i],
                'response': response,
                'parsed_sql': [],
                'fingerprint_evaluation': {},
                'inference_success': bool(response.strip())
            }
            
            if response.strip():
                self.evaluation_stats['successful_inference'] += 1
                
                try:
                    # 解析SQL
                    sql_list = self.parse_sql_response(response)
                    result['parsed_sql'] = sql_list
                    
                    if sql_list:
                        # SQL指纹验证
                        fingerprint_eval = self.evaluate_sql_with_fingerprint(sql_list)
                        result['fingerprint_evaluation'] = fingerprint_eval
                        
                        # 更新统计
                        if fingerprint_eval['valid_sql'] > 0:
                            self.evaluation_stats['valid_sql_generated'] += 1
                        if fingerprint_eval['matched_sql'] > 0:
                            self.evaluation_stats['fingerprint_matched'] += 1
                    
                except Exception as e:
                    logger.warning(f"解析第 {i} 个样本时出错: {e}")
                    result['parse_error'] = str(e)
                    self.evaluation_stats['parse_errors'] += 1
            else:
                self.evaluation_stats['inference_errors'] += 1
            
            self.eval_results.append(result)
        
        # 生成最终统计
        final_stats = self.generate_final_statistics()
        
        # 保存结果
        self.save_evaluation_results()
        
        logger.info("评估完成!")
        return final_stats
    
    def generate_final_statistics(self) -> Dict:
        """生成最终统计结果"""
        stats = self.evaluation_stats.copy()
        
        # 计算比率
        total = stats['total_samples']
        if total > 0:
            stats['inference_success_rate'] = stats['successful_inference'] / total
            stats['valid_sql_rate'] = stats['valid_sql_generated'] / total
            stats['fingerprint_match_rate'] = stats['fingerprint_matched'] / total
            stats['parse_error_rate'] = stats['parse_errors'] / total
            stats['inference_error_rate'] = stats['inference_errors'] / total
        
        # SQL级别的统计
        total_sql = sum(len(r.get('parsed_sql', [])) for r in self.eval_results)
        valid_sql = sum(r.get('fingerprint_evaluation', {}).get('valid_sql', 0) for r in self.eval_results)
        matched_sql = sum(r.get('fingerprint_evaluation', {}).get('matched_sql', 0) for r in self.eval_results)
        
        stats['total_sql_generated'] = total_sql
        stats['total_valid_sql'] = valid_sql
        stats['total_matched_sql'] = matched_sql
        
        if total_sql > 0:
            stats['sql_validity_rate'] = valid_sql / total_sql
            stats['sql_match_rate'] = matched_sql / total_sql
        
        return stats
    
    def save_evaluation_results(self):
        """保存评估结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存详细结果
        detailed_results_file = self.output_dir / f"evaluation_results_{timestamp}.json"
        with open(detailed_results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'evaluation_config': {
                    'model_path': str(self.model_path),
                    'eval_data_path': str(self.eval_data_path),
                    'fingerprint_cache_path': str(self.fingerprint_cache_path),
                    'timestamp': timestamp
                },
                'statistics': self.evaluation_stats,
                'detailed_results': self.eval_results
            }, f, ensure_ascii=False, indent=2)
        
        # 保存统计摘要
        stats = self.generate_final_statistics()
        summary_file = self.output_dir / f"evaluation_summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"详细结果已保存: {detailed_results_file}")
        logger.info(f"统计摘要已保存: {summary_file}")
        
        # 打印摘要
        self.print_evaluation_summary(stats)
    
    def print_evaluation_summary(self, stats: Dict):
        """打印评估摘要"""
        print("\n" + "="*80)
        print("模型评估结果摘要")
        print("="*80)
        print(f"模型路径: {self.model_path}")
        print(f"验证集: {self.eval_data_path}")
        print(f"总样本数: {stats['total_samples']}")
        print("\n推理结果:")
        print(f"  成功推理: {stats['successful_inference']}/{stats['total_samples']} ({stats.get('inference_success_rate', 0):.2%})")
        print(f"  推理错误: {stats['inference_errors']} ({stats.get('inference_error_rate', 0):.2%})")
        print(f"  解析错误: {stats['parse_errors']} ({stats.get('parse_error_rate', 0):.2%})")
        
        print("\nSQL生成质量:")
        print(f"  生成有效SQL样本: {stats['valid_sql_generated']}/{stats['total_samples']} ({stats.get('valid_sql_rate', 0):.2%})")
        print(f"  指纹匹配样本: {stats['fingerprint_matched']}/{stats['total_samples']} ({stats.get('fingerprint_match_rate', 0):.2%})")
        
        print(f"\nSQL语句级别统计:")
        print(f"  总生成SQL数: {stats.get('total_sql_generated', 0)}")
        print(f"  有效SQL数: {stats.get('total_valid_sql', 0)} ({stats.get('sql_validity_rate', 0):.2%})")
        print(f"  指纹匹配SQL数: {stats.get('total_matched_sql', 0)} ({stats.get('sql_match_rate', 0):.2%})")
        print("="*80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="模型评估器")
    parser.add_argument("--model_path", type=str, required=True, help="训练好的模型路径")
    parser.add_argument("--eval_data", type=str, default="model/evaluation/eval_data.json", help="验证集数据路径")
    parser.add_argument("--output_dir", type=str, default="model/evaluation/results", help="评估结果输出目录")
    parser.add_argument("--fingerprint_cache", type=str, help="SQL指纹缓存文件路径")
    parser.add_argument("--max_samples", type=int, help="最大评估样本数（用于测试）")
    parser.add_argument("--batch_size", type=int, default=1, help="推理批处理大小")
    
    args = parser.parse_args()
    
    try:
        # 创建评估器
        evaluator = ModelEvaluator(
            model_path=args.model_path,
            eval_data_path=args.eval_data,
            output_dir=args.output_dir,
            fingerprint_cache_path=args.fingerprint_cache
        )
        
        # 运行评估
        results = evaluator.run_evaluation(
            max_samples=args.max_samples,
            batch_size=args.batch_size
        )
        
        print(f"\n✅ 评估完成！结果已保存到: {evaluator.output_dir}")
        
    except Exception as e:
        logger.error(f"评估失败: {e}")
        raise


if __name__ == "__main__":
    main() 