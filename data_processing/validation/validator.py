"""
核心验证器模块
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

import yaml
from tqdm import tqdm

from utils.llm_client import LLMClientManager
from config.prompts import REANALYSIS_PROMPT
from config.validation_prompts import (
    ANALYSIS_PROMPT_TEMPLATE,
    VERIFICATION_PROMPT_TEMPLATE,
    FORMATTING_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class RerunValidator:
    """封装重新运行分析和验证逻辑的类"""

    def __init__(self, config_path="config/rerun_config.yaml"):
        """
        初始化验证器。
        Args:
            config_path: 配置文件的路径。
        """
        self.config = self._load_config(config_path)
        self.client_manager = LLMClientManager()
        self._setup_logging()

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
        
        return REANALYSIS_PROMPT.format(
            function_name=function_name,
            code_value=code_value,
            caller=caller,
            code_meta_data_str=code_meta_data_str,
            callee=callee
        )

    async def _run_single_analysis(self, semaphore: asyncio.Semaphore, record: dict, pbar: tqdm, output_file, file_lock) -> dict:
        """对单个记录进行分析，并立即将结果写入文件"""
        async with semaphore:
            prompt = self._format_rerun_prompt(record)
            client = self.client_manager.get_client(self.config['server'])
            
            try:
                loop = asyncio.get_event_loop()
                result_content = await loop.run_in_executor(
                    None, 
                    lambda: client.call_openai(prompt, max_tokens=4096, temperature=0.0)
                )
                
                try:
                    new_sql = json.loads(result_content)
                except (json.JSONDecodeError, TypeError):
                    new_sql = result_content
                
                analysis_result = {
                    "function_name": record["function_name"],
                    "source_file": record["source_file"],
                    "original_orm_code": record.get("orm_code", ""),
                    "new_sql_analysis_result": new_sql
                }
            except Exception as e:
                logger.error(f"分析失败: {record['function_name']} - {e}")
                analysis_result = {
                    "function_name": record["function_name"],
                    "source_file": record["source_file"],
                    "error": str(e)
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
            "code_meta_data_str": json.dumps(record.get('code_meta_data', []), ensure_ascii=False, indent=2)
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

    async def run_rerun_analysis(self):
        """执行重新分析的完整流程"""
        logger.info(f"开始重新分析过程，输入文件: {self.config['input_file']}")
        
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

        logger.info(f"找到 {len(records_to_process)} 条记录需要重新分析。")
        
        output_dir = Path(self.config['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / self.config['output_filename']
        
        semaphore = asyncio.Semaphore(self.config['concurrency'])
        file_lock = asyncio.Lock()
        
        results = []
        with open(output_path, 'w', encoding='utf-8') as f:
            with tqdm(total=len(records_to_process), desc="重新分析进度") as pbar:
                tasks = [
                    self._run_single_analysis(semaphore, record, pbar, f, file_lock) 
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
        
        logger.info(f"✅ 重新分析完成。结果已保存到: {output_path}")
        
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