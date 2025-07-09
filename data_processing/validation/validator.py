"""
核心验证器模块
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

import aiohttp
import yaml
from tqdm import tqdm

from utils.llm_client import LLMClientManager
from config.validation.validation_prompts import (
    ANALYSIS_PROMPT_TEMPLATE,
    VERIFICATION_PROMPT_TEMPLATE,
    FORMATTING_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class RerunValidator:
    """封装重新运行分析和验证逻辑的类"""

    def __init__(self, config_path="config/rerun_config.yaml", custom_output_dir=None):
        """
        初始化验证器。
        Args:
            config_path: 配置文件的路径。
            custom_output_dir: 自定义输出目录，如果提供则覆盖配置文件中的output_dir
        """
        self.config = self._load_config(config_path)
        self.client_manager = LLMClientManager()
        self._setup_logging()
        
        # 如果提供了自定义输出目录，则覆盖配置文件中的设置
        if custom_output_dir:
            self.config['output_dir'] = str(custom_output_dir)
            logger.info(f"使用自定义输出目录: {custom_output_dir}")
        
        # 添加详细结果收集器
        self.detailed_results = []
        self.detailed_results_lock = asyncio.Lock()

    def _load_config(self, config_path: str) -> dict:
        """加载YAML配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"❌ 配置文件未找到: {config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            logger.error(f"❌ 配置文件YAML格式错误: {config_path} - {e}")
            sys.exit(1)

    def _setup_logging(self):
        """配置日志记录器"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _format_rerun_prompt(self, record: dict) -> str:
        """格式化用于重新分析的提示词（旧逻辑）"""
        code_value = record.get('orm_code', '')
        if not code_value:
            if record.get('code_meta_data') and isinstance(record['code_meta_data'], list) and record['code_meta_data']:
                code_value = record['code_meta_data'][0].get('code_value', '')

        function_name = record.get('function_name', 'N/A')
        caller = record.get('caller', 'N/A')
        code_meta_data_str = json.dumps(record.get('code_meta_data', []), ensure_ascii=False, indent=2)
        callee = "N/A"
        
        return ANALYSIS_PROMPT_TEMPLATE.format(
            function_name=function_name,
            code_value=code_value,
            caller=caller,
            code_meta_data_str=code_meta_data_str,
            sql_pattern_cnt=record.get('sql_pattern_cnt', 0)
        )

    async def _run_single_analysis(self, semaphore: asyncio.Semaphore, record: dict, pbar: tqdm, output_file, file_lock, session) -> dict:
        """对单个记录进行分析，并立即将结果写入文件"""
        async with semaphore:
            prompt = self._format_rerun_prompt(record)
            client = self.client_manager.get_client(self.config['server'])
            
            try:
                # 使用带重试机制的call_async方法
                result_content = await client.call_async(
                    session, 
                    prompt, 
                    max_tokens=4096, 
                    temperature=0.0,
                    max_retries=5,
                    retry_delay=1.0
                )
                
                try:
                    new_sql = json.loads(result_content)
                    json_parse_success = True
                    json_parse_error = None
                except (json.JSONDecodeError, TypeError) as e:
                    new_sql = result_content
                    json_parse_success = False
                    json_parse_error = str(e)
                
                analysis_result = {
                    "function_name": record["function_name"],
                    "source_file": record["source_file"],
                    "original_orm_code": record.get("orm_code", ""),
                    "new_sql_analysis_result": new_sql,
                    # 新增：模型回复详细信息
                    "model_response": {
                        "raw_content": result_content,
                        "content_length": len(result_content),
                        "server": self.config.get('server', 'unknown'),
                        "json_parse_success": json_parse_success,
                        "json_parse_error": json_parse_error
                    },
                    # 新增：提示词信息
                    "prompt_info": {
                        "prompt_content": prompt,
                        "prompt_length": len(prompt),
                        "prompt_type": "single_stage_analysis"
                    },
                    # 新增：输入记录元数据
                    "input_metadata": {
                        "caller": record.get('caller', ''),
                        "sql_pattern_cnt": record.get('sql_pattern_cnt', 0),
                        "code_meta_data_count": len(record.get('code_meta_data', []))
                    }
                }
            except Exception as e:
                logger.error(f"分析失败: {record['function_name']} - {e}")
                analysis_result = {
                    "function_name": record["function_name"],
                    "source_file": record["source_file"],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    # 即使出错也保留提示词信息
                    "prompt_info": {
                        "prompt_content": prompt,
                        "prompt_length": len(prompt),
                        "prompt_type": "single_stage_analysis"
                    }
                }

            async with file_lock:
                output_file.write(json.dumps(analysis_result, ensure_ascii=False) + '\n')
                output_file.flush()

            pbar.update(1)
            return analysis_result

    def _get_common_prompt_fields(self, record: dict) -> dict:
        """从记录中提取用于格式化提示词的通用字段"""
        code_value = record.get('orm_code', '')
        if not code_value and record.get('code_meta_data'):
             if isinstance(record['code_meta_data'], list) and record['code_meta_data']:
                code_value = record['code_meta_data'][0].get('code_value', '')

        return {
            "function_name": record.get('function_name', 'N/A'),
            "code_value": code_value,
            "code_meta_data_str": json.dumps(record.get('code_meta_data', []), ensure_ascii=False, indent=2),
            "caller": record.get('caller', 'N/A'),
            "sql_pattern_cnt": record.get('sql_pattern_cnt', 0)
        }

    def generate_precheck_prompts(self, record: dict, analysis_result: str = "") -> dict:
        """
        为给定的记录生成三阶段的预检查提示词。
        
        Args:
            record: 需要分析的数据记录。
            analysis_result: (可选) 第二阶段验证时需要的前一阶段分析结果。

        Returns:
            一个包含三个阶段提示词的字典。
        """
        common_fields = self._get_common_prompt_fields(record)

        prompt1 = ANALYSIS_PROMPT_TEMPLATE.format(**common_fields)
        
        prompt2 = VERIFICATION_PROMPT_TEMPLATE.format(
            analysis_result=analysis_result,
            function_definition=record.get('orm_code', ''),
            code_chain='',  # 如需可填充调用链上下文
            sql_statement=analysis_result,
            **common_fields
        )

        # 第三阶段的输入是第二阶段的输出，这里我们只准备模板
        # 实际使用时，需要用第二阶段的LLM输出来填充 {analysis_to_format}
        prompt3_template = FORMATTING_PROMPT_TEMPLATE

        return {
            "analysis_prompt": prompt1,
            "verification_prompt": prompt2,
            "formatting_prompt_template": prompt3_template
        }

    async def run_three_stage_analysis(self, record: dict, save_detailed_results: bool = True) -> dict:
        """
        执行三段式分析流程并解析JSON结果
        
        Args:
            record: 需要分析的数据记录
            save_detailed_results: 是否保存详细的模型回复结果到文件
            
        Returns:
            包含各阶段结果和解析后JSON的字典
        """
        try:
            # 获取LLM客户端
            client = self.client_manager.get_client(self.config['server'])
            
            async with aiohttp.ClientSession() as session:
                # 第一阶段：分析
                stage_prompts = self.generate_precheck_prompts(record)
                analysis_result = await client.call_async(
                    session,
                    stage_prompts['analysis_prompt'], 
                    max_tokens=4096, 
                    temperature=0.0,
                    max_retries=5,
                    retry_delay=1.0
                )
                
                if not analysis_result:
                    logger.error("❌ 第一阶段返回空结果")
                    return {
                        "analysis_result": "",
                        "verification_result": "",
                        "final_result": "",
                        "parsed_json": None,
                        "success": False,
                        "error": "第一阶段LLM调用失败"
                    }
                
                # 第二阶段：验证
                verification_prompts = self.generate_precheck_prompts(record, analysis_result)
                verification_result = await client.call_async(
                    session,
                    verification_prompts['verification_prompt'],
                    max_tokens=4096,
                    temperature=0.0,
                    max_retries=5,
                    retry_delay=1.0
                )
                
                if not verification_result:
                    logger.error("❌ 第二阶段返回空结果")
                    return {
                        "analysis_result": analysis_result,
                        "verification_result": "",
                        "final_result": "",
                        "parsed_json": None,
                        "success": False,
                        "error": "第二阶段LLM调用失败"
                    }
                
                # 第三阶段：格式化
                format_prompt = FORMATTING_PROMPT_TEMPLATE.format(sql_statement=verification_result)
                final_result = await client.call_async(
                    session,
                    format_prompt,
                    max_tokens=4096,
                    temperature=0.0,
                    max_retries=5,
                    retry_delay=1.0
                )
                
                if not final_result:
                    logger.error("❌ 第三阶段返回空结果")
                    return {
                        "analysis_result": analysis_result,
                        "verification_result": verification_result,
                        "final_result": "",
                        "parsed_json": None,
                        "success": False,
                        "error": "第三阶段LLM调用失败"
                    }
                
                # 尝试解析JSON
                parsed_json = None
                try:
                    parsed_json = json.loads(final_result)
                except (json.JSONDecodeError, TypeError) as e:
                    # 尝试提取JSON部分（可能包含在代码块中）
                    import re
                    # 修复正则表达式，正确处理换行符和嵌套结构
                    json_match = re.search(r'```json\s*(.*?)\s*```', final_result, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1).strip()
                        try:
                            parsed_json = json.loads(json_content)
                        except (json.JSONDecodeError, TypeError):
                            logger.warning(f"⚠️ JSON解析失败: {e}")
                            logger.warning(f"🔍 解析失败的内容: {repr(final_result[:500])}...")
                    else:
                        logger.warning(f"⚠️ JSON解析失败: {e}")
                        logger.warning(f"🔍 解析失败的内容: {repr(final_result[:500])}...")
                
                # 构建详细的结果信息
                detailed_result = {
                    # 基本结果信息（保持向后兼容）
                    "analysis_result": analysis_result,
                    "verification_result": verification_result,
                    "final_result": final_result,
                    "parsed_json": parsed_json,
                    "success": True,
                    
                    # 新增：详细的阶段信息
                    "stage_details": {
                        "stage1_analysis": {
                            "prompt": stage_prompts['analysis_prompt'],
                            "prompt_length": len(stage_prompts['analysis_prompt']),
                            "raw_response": analysis_result,
                            "response_length": len(analysis_result),
                            "stage_type": "ORM代码分析"
                        },
                        "stage2_verification": {
                            "prompt": verification_prompts['verification_prompt'],
                            "prompt_length": len(verification_prompts['verification_prompt']),
                            "raw_response": verification_result,
                            "response_length": len(verification_result),
                            "stage_type": "SQL语句验证"
                        },
                        "stage3_formatting": {
                            "prompt": format_prompt,
                            "prompt_length": len(format_prompt),
                            "raw_response": final_result,
                            "response_length": len(final_result),
                            "stage_type": "结果格式化"
                        }
                    },
                    
                    # 新增：输入记录信息
                    "input_record": {
                        "function_name": record.get('function_name', ''),
                        "source_file": record.get('source_file', ''),
                        "caller": record.get('caller', ''),
                        "sql_pattern_cnt": record.get('sql_pattern_cnt', 0),
                        "orm_code_length": len(record.get('orm_code', '')),
                        "code_meta_data_count": len(record.get('code_meta_data', []))
                    },
                    
                    # 新增：处理元数据
                    "processing_metadata": {
                        "server": self.config.get('server', 'unknown'),
                        "max_tokens": 4096,
                        "temperature": 0.0,
                                    "retry_config": {
                "max_retries": 5,
                "retry_delay": 1.0
                        },
                        "json_parsing": {
                            "final_parse_success": parsed_json is not None,
                            "final_parse_error": None if parsed_json is not None else "解析失败"
                        }
                    }
                }
                
                # 如果需要保存详细结果到文件
                if save_detailed_results:
                    await self._collect_detailed_results(record, detailed_result)
                
                return detailed_result
            
        except Exception as e:
            logger.error(f"❌ 三段式分析流程异常: {e}")
            return {
                "analysis_result": "",
                "verification_result": "",
                "final_result": "",
                "parsed_json": None,
                "success": False,
                "error": f"流程异常: {str(e)}"
            }

    async def _collect_detailed_results(self, record: dict, detailed_result: dict):
        """收集详细的三段式分析结果"""
        async with self.detailed_results_lock:
            self.detailed_results.append(detailed_result)
            logger.debug(f"收集到详细结果: {record['function_name']}")

    async def save_all_detailed_results(self):
        """保存所有收集的详细结果到单个JSON文件"""
        try:
            if not self.detailed_results:
                logger.info("没有详细结果需要保存")
                return
            
            # 创建输出目录
            output_dir = Path(self.config.get('output_dir', 'validator_output'))
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存到单个JSON文件
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"detailed_analysis_results_{timestamp}.json"
            filepath = output_dir / filename
            
            # 构建统一的结果结构
            summary = {
                "metadata": {
                    "total_records": len(self.detailed_results),
                    "timestamp": timestamp,
                    "server": self.config.get('server', 'unknown'),
                    "analysis_type": "three_stage_analysis"
                },
                "results": self.detailed_results
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📁 所有详细结果已保存到: {filepath}")
            logger.info(f"   总共保存了 {len(self.detailed_results)} 条详细分析结果")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"保存详细结果失败: {e}")
            return None

    async def run_rerun_analysis(self):
        """执行重新分析的完整流程"""
        
        try:
            with open(self.config['input_file'], 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except FileNotFoundError:
            logger.error(f"❌ 输入文件未找到: {self.config['input_file']}")
            return
        except json.JSONDecodeError:
            logger.error(f"❌ 输入文件JSON格式错误: {self.config['input_file']}")
            return

        records_to_process = [r for r in all_data if r.get("sql_statement_list") == "<NO SQL GENERATE>"]
        
        if not records_to_process:
            logger.warning("未找到需要重新分析的记录 (<NO SQL GENERATE>)。")
            return
        
        output_dir = Path(self.config['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / self.config['output_filename']
        
        semaphore = asyncio.Semaphore(self.config['concurrency'])
        file_lock = asyncio.Lock()
        
        results = []
        async with aiohttp.ClientSession() as session:
            with open(output_path, 'w', encoding='utf-8') as f:
                with tqdm(total=len(records_to_process), desc="重新分析进度") as pbar:
                    tasks = [
                        self._run_single_analysis(semaphore, record, pbar, f, file_lock, session) 
                        for record in records_to_process
                    ]
                    results = await asyncio.gather(*tasks)

        self._print_summary_report(results, records_to_process, output_path)

    def _print_summary_report(self, results: list, records_to_process: list, output_path: Path):
        """打印最终的总结报告"""
        successful_results = [r for r in results if "error" not in r]
        failed_results = [r for r in results if "error" in r]
        
        newly_generated_count = 0
        for r in successful_results:
            analysis = r.get("new_sql_analysis_result")
            if isinstance(analysis, list) and analysis:
                first_item = analysis[0]
                if isinstance(first_item, dict):
                    should_gen_val = first_item.get("should_generate_sql")
                    if str(should_gen_val).strip().lower() == 'false':
                        newly_generated_count += 1
        
        print("\n" + "="*50)
        print("📊 重新分析总结报告")
        print("="*50)
        print(f"总处理记录数: {len(records_to_process)}")
        print(f"成功分析数: {len(successful_results)}")
        print(f"失败分析数: {len(failed_results)}")
        print("-" * 50)
        print(f"🎉 新生成SQL的记录数: {newly_generated_count}")
        print(f"仍未生成SQL的记录数: {len(successful_results) - newly_generated_count}")
        print("="*50)
        if failed_results:
            print("\n失败的记录 (前5条):")
            for failed in failed_results[:5]:
                print(f"  - {failed['function_name']}: {failed['error']}") 