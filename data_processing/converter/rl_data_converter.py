#!/usr/bin/env python3
"""
RL训练数据转换器

将训练数据转换为RLHF训练格式，输出为parquet文件
"""

import json
import os
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import glob
import sys
import asyncio
from tqdm import tqdm
import yaml

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 现在可以导入项目内的模块
from config.rl.data_conversion.orm2sql_prompt_template import PROMPT_TEMPLATE
from utils.preprocess import preprocess_record

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RLDataConverter:
    """RL训练数据转换器"""
    
    def __init__(self, project_root: Optional[str] = None, config_path: Optional[str] = None):
        """
        初始化转换器
        
        Args:
            project_root: 项目根目录路径
            config_path: 配置文件路径
        """
        if project_root is None:
            self.project_root = Path(__file__).parent.parent.parent
        else:
            self.project_root = Path(project_root)
        
        # 加载配置文件
        if config_path is None:
            config_path = self.project_root / "config" / "rl" / "data_conversion" / "conversion_config.yaml"
        
        self.config = self.load_config(config_path)
        
        # 创建RL数据目录
        self.rl_data_dir = self.project_root / "model" / "data" / "orm2sql_rl_data"
        self.rl_data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"RL数据转换器初始化完成")
        logger.info(f"项目根目录: {self.project_root}")
        logger.info(f"RL数据目录: {self.rl_data_dir}")
        logger.info(f"配置文件: {config_path}")
    
    def load_config(self, config_path: Path) -> Dict:
        """加载配置文件"""
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"成功加载配置文件: {config_path}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return {}
    
    def find_latest_workflow_output(self) -> Optional[Path]:
        """查找最新的workflow输出目录"""
        workflow_dir = self.project_root / "workflow_output"
        if not workflow_dir.exists():
            return None
        
        # 查找最新的子目录
        subdirs = [d for d in workflow_dir.iterdir() if d.is_dir()]
        if not subdirs:
            return None
        
        # 按修改时间排序，返回最新的
        latest_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        logger.info(f"找到最新workflow输出: {latest_dir}")
        return latest_dir

    def load_workflow_data(self, workflow_dir: Path) -> List[Dict]:
        """加载workflow处理后的数据"""
        # 从配置中获取文件名，如果没有配置则使用默认值
        final_data_filename = self.config.get('input', {}).get('final_data_filename', 'final_processed_dataset.json')
        
        # 尝试多个可能的数据文件名
        possible_files = [
            workflow_dir / final_data_filename,
            workflow_dir / "final_processed_dataset.json"  # 保留默认文件名作为备选
        ]
        
        data_file = None
        for file_path in possible_files:
            if file_path.exists():
                data_file = file_path
                break
        
        if not data_file:
            raise FileNotFoundError(f"数据文件不存在，尝试过的文件: {[str(f) for f in possible_files]}")
        
        logger.info(f"使用数据文件: {data_file}")
        
        # 根据文件扩展名决定读取方式
        if data_file.suffix == '.jsonl':
            # JSONL格式：每行一个JSON对象
            data = []
            with open(data_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
        else:
            # JSON格式：整个文件是一个JSON数组
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        logger.info(f"加载了 {len(data)} 条数据记录")
        return data

    def format_code_metadata(self, code_meta_data: List[dict]) -> str:
        """格式化代码元数据为字符串"""
        if not code_meta_data:
            return ""
        
        formatted_parts = []
        for meta in code_meta_data:
            if isinstance(meta, dict):
                # 提取关键信息
                code_key = meta.get('code_key', meta.get('key', meta.get('name', '')))
                code_value = meta.get('code_value', meta.get('value', meta.get('content', '')))
                code_file = meta.get('code_file', meta.get('file', meta.get('source', '')))
                
                if code_key and code_value:
                    part = f"**{code_key}**: {code_value}"
                    if code_file:
                        part += f" (文件: {code_file})"
                    formatted_parts.append(part)
            else:
                # 如果不是字典，直接转换为字符串
                formatted_parts.append(str(meta))
        
        return "\n".join(formatted_parts)

    def create_rl_prompt(self, record: Dict) -> List[Dict]:
        """创建RL训练用的聊天格式提示词"""
        # 提取基本信息
        function_name = record.get('function_name', 'N/A')
        orm_code = record.get('orm_code', '')
        caller = record.get('caller', '')
        code_meta_data = record.get('code_meta_data', [])
        
        # 格式化代码元数据
        meta_data_str = self.format_code_metadata(code_meta_data)
        
        # 使用orm2sql_prompt_template中的模板
        user_content = PROMPT_TEMPLATE.format(
            function_name=function_name,
            code_value=orm_code,
            caller=caller,
            code_meta_data_str=meta_data_str
        )

        return [
            {"role": "user", "content": user_content}
        ]

    def extract_ground_truth(self, record: Dict) -> str:
        """提取标准答案（SQL语句）"""
        # 从记录中提取SQL语句
        sql_statements = record.get('sql_statements', [])
        if not sql_statements:
            return "[]"
        
        # 返回JSON格式的SQL语句数组
        return json.dumps(sql_statements, ensure_ascii=False)

    async def process_single_record(self, record: Dict, index: int) -> Optional[Dict]:
        """处理单条记录（异步）"""
        try:
            # 预处理步骤（仅表名字段名抽取）
            ok, pre_tables, pre_columns = await preprocess_record(record)
            if not ok:
                return None
            
            # 创建聊天格式的提示词
            prompt = self.create_rl_prompt(record)
            
            # 提取标准答案
            ground_truth = self.extract_ground_truth(record)
            
            # 构建reward_model配置
            reward_model = {
                "style": "rule",  # 使用规则评分，不是模型评分
                "ground_truth": ground_truth
            }
            
            # 构建extra_info，包含所有ORM相关信息
            extra_info = {
                "index": index,
                "split": "train",  # 默认为训练集
                "function_name": record.get('function_name', ''),
                "source_file": record.get('source_file', ''),
                "sql_pattern_cnt": record.get('sql_pattern_cnt', 0),
                "sql_types": record.get('sql_types', []),
                # 保持原有ORM信息
                "orm_code": record.get('orm_code', ''),
                "caller": record.get('caller', ''),
                "callee": record.get('callee', ''),
                "code_meta_data": record.get('code_meta_data', []),
                # 预处理的表名字段名结果
                "pre_tables": list(pre_tables),
                "pre_columns": list(pre_columns),
                # 保持原有关键词信息不变
                "llm_keyword_analysis": record.get("llm_keyword_analysis", {})
            }
            
            return {
                "data_source": "code2sql_orm",
                "prompt": prompt,
                "ability": "code_generation",
                "reward_model": reward_model,
                "extra_info": extra_info
            }
            
        except Exception as e:
            logger.error(f"处理第 {index} 条记录时出错: {e}")
            return None

    async def convert_to_rl_format(self, data: List[Dict]) -> pd.DataFrame:
        """
        将ORM数据转换为RL训练格式（并发处理）
        
        Args:
            data: workflow处理后的数据
            
        Returns:
            转换后的RL训练数据DataFrame
        """
        logger.info("开始转换RL训练数据...")
        
        # 打印第一条数据用于调试
        if data:
            logger.info("=== 第一条数据示例 ===")
            first_record = data[0]
            logger.info(f"function_name: {first_record.get('function_name', 'N/A')}")
            logger.info(f"orm_code: {first_record.get('orm_code', 'N/A')[:100]}...")
            logger.info(f"caller: {first_record.get('caller', 'N/A')}")
            logger.info(f"code_meta_data 类型: {type(first_record.get('code_meta_data', []))}")
            logger.info(f"code_meta_data 长度: {len(first_record.get('code_meta_data', []))}")
            if first_record.get('code_meta_data'):
                logger.info(f"第一条 code_meta_data: {first_record['code_meta_data'][0]}")
                logger.info(f"第一条 code_meta_data 类型: {type(first_record['code_meta_data'][0])}")
                if isinstance(first_record['code_meta_data'][0], dict):
                    logger.info(f"第一条 code_meta_data 键: {list(first_record['code_meta_data'][0].keys())}")
            logger.info("=== 数据示例结束 ===")
        
        # 统计信息
        total_records = len(data)
        filtered_count = 0
        has_keywords_count = 0
        
        # 设置并发数（可以根据需要调整）
        max_concurrent = 10
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(record, index):
            async with semaphore:
                return await self.process_single_record(record, index)
        
        # 使用进度条和并发处理
        results = []
        with tqdm(total=total_records, desc="处理记录", unit="条") as pbar:
            # 分批处理，避免内存占用过大
            batch_size = 100
            for i in range(0, total_records, batch_size):
                batch = data[i:i + batch_size]
                batch_tasks = [process_with_semaphore(record, j) for j, record in enumerate(batch, i)]
                
                # 并发处理当前批次
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # 处理结果
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"处理第 {i + j} 条记录时出错: {result}")
                        filtered_count += 1
                    elif result is None:
                        filtered_count += 1
                    else:
                        # 检查是否有关键词
                        original_record = data[i + j]
                        if original_record.get("llm_keyword_analysis", {}).get("has_special_keywords", False):
                            has_keywords_count += 1
                        results.append(result)
                
                # 更新进度条
                pbar.update(len(batch))
                pbar.set_postfix({
                    '已处理': f"{i + len(batch)}/{total_records}",
                    '保留': len(results),
                    '过滤': filtered_count,
                    '并发数': max_concurrent
                })
        
        # 转换为DataFrame
        if not results:
            logger.warning("没有成功处理任何记录")
            return pd.DataFrame()
        
        rl_data = {
            "data_source": [r["data_source"] for r in results],
            "prompt": [r["prompt"] for r in results],
            "ability": [r["ability"] for r in results],
            "reward_model": [r["reward_model"] for r in results],
            "extra_info": [r["extra_info"] for r in results]
        }
        
        # 输出统计信息
        final_count = len(results)
        logger.info(f"=== 预处理统计信息 ===")
        logger.info(f"原始样本数: {total_records}")
        logger.info(f"过滤样本数: {filtered_count}")
        logger.info(f"保留样本数: {final_count}")
        logger.info(f"保留率: {final_count/total_records*100:.1f}%")
        logger.info(f"有关键词样本数: {has_keywords_count}")
        if final_count > 0:
            logger.info(f"关键词样本占比: {has_keywords_count/final_count*100:.1f}%")
        
        logger.info(f"转换完成，共生成 {final_count} 条RL训练样本")
        
        # 打印前3条转换后的数据示例
        logger.info("=== 转换后的RL训练数据示例 ===")
        for i, record in enumerate(results[:3]):
            logger.info(f"--- 第 {i+1} 条数据 ---")
            logger.info(f"data_source: {record.get('data_source', 'N/A')}")
            logger.info(f"ability: {record.get('ability', 'N/A')}")
            
            # 打印prompt内容（截取前200字符）
            prompt = record.get('prompt', [])
            if prompt and len(prompt) > 0:
                user_content = prompt[0].get('content', '')
                logger.info(f"prompt内容预览: {user_content[:200]}...")
            
            # 打印reward_model
            reward_model = record.get('reward_model', {})
            logger.info(f"reward_model: {reward_model}")
            
            # 打印extra_info的关键信息
            extra_info = record.get('extra_info', {})
            logger.info(f"function_name: {extra_info.get('function_name', 'N/A')}")
            logger.info(f"pre_tables: {extra_info.get('pre_tables', [])}")
            logger.info(f"pre_columns: {extra_info.get('pre_columns', [])}")
            logger.info("")
        
        logger.info("=== 数据示例结束 ===")
        
        return pd.DataFrame(rl_data)
    
    def split_train_val(self, df: pd.DataFrame, val_ratio: float = 0.1) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        划分训练集和验证集
        
        Args:
            df: 完整数据集DataFrame
            val_ratio: 验证集比例
            
        Returns:
            (训练集DataFrame, 验证集DataFrame)
        """
        # 随机打乱数据
        df_shuffled = df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        # 计算划分点
        val_size = int(len(df_shuffled) * val_ratio)
        
        val_df = df_shuffled.iloc[:val_size].copy()
        train_df = df_shuffled.iloc[val_size:].copy()
        
        # 更新split标记
        train_df.loc[:, 'extra_info'] = train_df['extra_info'].apply(
            lambda x: {**x, 'split': 'train'}
        )
        val_df.loc[:, 'extra_info'] = val_df['extra_info'].apply(
            lambda x: {**x, 'split': 'val'}
        )
        
        logger.info(f"数据集划分完成: 训练集 {len(train_df)} 条, 验证集 {len(val_df)} 条")
        return train_df, val_df
    
    def save_rl_data(self, train_df: pd.DataFrame, val_df: pd.DataFrame, 
                     output_name: Optional[str] = None) -> Tuple[Path, Path]:
        """
        保存RL训练数据为parquet格式
        
        Args:
            train_df: 训练集DataFrame
            val_df: 验证集DataFrame
            output_name: 输出文件名前缀（可选）
            
        Returns:
            (训练集文件路径, 验证集文件路径)
        """
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"orm2sql_rl_{timestamp}"
        
        train_path = self.rl_data_dir / f"{output_name}_train.parquet"
        val_path = self.rl_data_dir / f"{output_name}_val.parquet"
        
        logger.info(f"正在保存训练集到: {train_path}")
        train_df.to_parquet(train_path, index=False)
        train_size = train_path.stat().st_size / (1024 * 1024)
        logger.info(f"训练集保存完成，文件大小: {train_size:.1f} MB")
        
        logger.info(f"正在保存验证集到: {val_path}")
        val_df.to_parquet(val_path, index=False)
        val_size = val_path.stat().st_size / (1024 * 1024)
        logger.info(f"验证集保存完成，文件大小: {val_size:.1f} MB")
        
        return train_path, val_path
    
    def create_dataset_info(self, train_df: pd.DataFrame, val_df: pd.DataFrame, 
                           dataset_name: str) -> Dict:
        """
        创建数据集信息文件
        
        Args:
            train_df: 训练集DataFrame
            val_df: 验证集DataFrame
            dataset_name: 数据集名称
            
        Returns:
            数据集信息字典
        """
        return {
            "dataset_name": dataset_name,
            "description": "ORM到SQL转换的RL训练数据集，基于真实代码分析生成",
            "data_source": "code2sql_orm",
            "ability": "code_generation",
            "train": {
                "file_name": f"{dataset_name}_train.parquet",
                "num_samples": len(train_df),
                "size_mb": f"{(self.rl_data_dir / f'{dataset_name}_train.parquet').stat().st_size / (1024*1024):.1f}"
            },
            "val": {
                "file_name": f"{dataset_name}_val.parquet",
                "num_samples": len(val_df),
                "size_mb": f"{(self.rl_data_dir / f'{dataset_name}_val.parquet').stat().st_size / (1024*1024):.1f}"
            },
            "total_samples": len(train_df) + len(val_df),
            "reward_model_style": "rule",
            "format": "RLHF parquet format with chat template"
        }
    
    async def run_conversion(self, workflow_dir: Optional[Path] = None, output_name: Optional[str] = None,
                      val_ratio: float = 0.1) -> Tuple[Path, Path, Dict]:
        """
        运行数据转换步骤
        
        Args:
            workflow_dir: workflow输出目录
            output_name: 输出文件名
            val_ratio: 验证集比例
        Returns:
            (训练集路径, 验证集路径, 数据集信息)
        """
        # 1. 根据配置确定workflow目录
        if workflow_dir is None:
            use_latest_workflow = self.config.get('input', {}).get('use_latest_workflow', True)
            
            if use_latest_workflow:
                # 使用最新的workflow输出
                workflow_dir = self.find_latest_workflow_output()
                if workflow_dir is None:
                    raise FileNotFoundError("未找到workflow输出目录")
                logger.info(f"使用最新workflow输出: {workflow_dir}")
            else:
                # 使用指定的workflow目录
                specific_dir = self.config.get('input', {}).get('specific_workflow_dir')
                if specific_dir:
                    workflow_dir = Path(specific_dir)
                    if not workflow_dir.exists():
                        raise FileNotFoundError(f"指定的workflow目录不存在: {workflow_dir}")
                    logger.info(f"使用指定workflow目录: {workflow_dir}")
                else:
                    raise ValueError("配置中use_latest_workflow为false但未指定specific_workflow_dir")
        
        # 2. 加载数据
        data = self.load_workflow_data(workflow_dir)
        
        # 3. 转换为RL格式
        rl_df = await self.convert_to_rl_format(data)
        
        # 4. 划分训练集和验证集
        train_df, val_df = self.split_train_val(rl_df, val_ratio)
        
        # 5. 保存数据
        if output_name is None:
            # 从配置中获取输出文件名前缀
            output_prefix = self.config.get('output', {}).get('output_name_prefix', 'orm2sql_rl')
            include_timestamp = self.config.get('output', {}).get('include_timestamp', True)
            
            if include_timestamp:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_name = f"{output_prefix}_{timestamp}"
            else:
                output_name = output_prefix
        
        train_path, val_path = self.save_rl_data(train_df, val_df, output_name)
        
        # 6. 创建数据集信息
        dataset_info = self.create_dataset_info(train_df, val_df, output_name or "dataset")
        
        # 7. 保存数据集信息文件
        info_filename = self.config.get('output', {}).get('dataset_info_filename', f"{output_name}_info.json")
        info_path = self.rl_data_dir / info_filename
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据集信息已保存到: {info_path}")
        
        return train_path, val_path, dataset_info


async def main():
    """主函数"""
    converter = RLDataConverter()
    
    try:
        # 执行转换
        train_path, val_path, dataset_info = await converter.run_conversion()
        
        print(f"\n✅ RL数据转换完成!")
        print(f"📁 训练集保存路径: {train_path}")
        print(f"📁 验证集保存路径: {val_path}")
        print(f"📊 训练集样本数: {dataset_info['train']['num_samples']}")
        print(f"📊 验证集样本数: {dataset_info['val']['num_samples']}")
        print(f"📊 总样本数: {dataset_info['total_samples']}")
        info_file = converter.rl_data_dir / f"{dataset_info['dataset_name']}_info.json"
        print(f"📝 数据集信息: {info_file}")
        
    except Exception as e:
        logger.error(f"RL数据转换失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 