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

# 添加项目根目录到Python路径
project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root))

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
    
    def __init__(self, project_root: Optional[str] = None):
        """
        初始化转换器
        
        Args:
            project_root: 项目根目录路径
        """
        if project_root is None:
            project_root = str(Path(__file__).parents[1])
        
        self.project_root = Path(project_root)
        self.workflow_output_dir = self.project_root / "workflow_output"
        self.rl_data_dir = self.project_root / "model" / "data" / "orm2sql_rl_data"
        
        # 确保输出目录存在
        self.rl_data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"项目根目录: {self.project_root}")
        logger.info(f"工作流输出目录: {self.workflow_output_dir}")
        logger.info(f"RL数据输出目录: {self.rl_data_dir}")
    
    def find_latest_workflow_output(self) -> Optional[Path]:
        """
        查找最新的workflow输出目录
        
        Returns:
            最新workflow目录路径，如果未找到返回None
        """
        if not self.workflow_output_dir.exists():
            logger.error(f"工作流输出目录不存在: {self.workflow_output_dir}")
            return None
        
        # 查找所有workflow目录
        workflow_dirs = list(self.workflow_output_dir.glob("workflow_*"))
        if not workflow_dirs:
            logger.error("未找到任何workflow输出目录")
            return None
        
        # 按时间戳排序，获取最新的
        workflow_dirs.sort(key=lambda x: x.name, reverse=True)
        latest_dir = workflow_dirs[0]
        
        logger.info(f"找到最新workflow目录: {latest_dir}")
        return latest_dir
    
    def load_workflow_data(self, workflow_dir: Path) -> List[Dict]:
        """
        加载workflow处理后的数据
        
        Args:
            workflow_dir: workflow输出目录
            
        Returns:
            处理后的数据列表
        """
        final_data_file = workflow_dir / "final_processed_dataset.json"
        
        if not final_data_file.exists():
            raise FileNotFoundError(f"未找到最终处理数据文件: {final_data_file}")
        
        logger.info(f"正在加载数据文件: {final_data_file}")
        logger.info(f"文件大小: {final_data_file.stat().st_size / (1024*1024):.1f} MB")
        
        with open(final_data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"成功加载 {len(data)} 条记录")
        return data
    
    def format_code_metadata(self, code_meta_data: List[Dict]) -> str:
        """
        格式化代码元数据为字符串
        
        Args:
            code_meta_data: 代码元数据列表
            
        Returns:
            格式化后的字符串
        """
        if not code_meta_data:
            return ""
        
        formatted_parts = []
        for meta in code_meta_data:
            if 'code_key' in meta and 'code_value' in meta:
                part = f"**{meta['code_key']}**:\n{meta['code_value']}"
                if 'code_file' in meta:
                    part += f"\n(文件: {meta['code_file']})"
                formatted_parts.append(part)
        
        return "\n\n".join(formatted_parts)
    
    def create_rl_prompt(self, record: Dict) -> List[Dict]:
        """
        根据记录创建RL训练提示词（聊天格式）
        
        Args:
            record: 单条ORM记录
            
        Returns:
            聊天格式的提示词列表
        """
        function_name = record.get("function_name", "未知函数")
        orm_code = record.get("orm_code", "")
        caller = record.get("caller", "")
        callee = record.get("callee", "")
        code_meta_data_str = self.format_code_metadata(record.get("code_meta_data", []))
        
        # 使用orm2sql_prompt_template.py中的完整模板
        user_content = PROMPT_TEMPLATE.format(
            function_name=function_name,
            orm_code=orm_code,
            caller=caller,
            code_meta_data_str=code_meta_data_str
        )
        
        return [{"role": "user", "content": user_content}]
    
    def extract_ground_truth(self, record: Dict) -> str:
        """
        提取标准答案作为ground_truth
        
        Args:
            record: 单条ORM记录
            
        Returns:
            标准答案字符串
        """
        sql_statement_list = record.get('sql_statement_list', [])
        return json.dumps(sql_statement_list, ensure_ascii=False, indent=None)
    
    def convert_to_rl_format(self, data: List[Dict]) -> pd.DataFrame:
        """
        将ORM数据转换为RL训练格式
        
        Args:
            data: workflow处理后的数据
            
        Returns:
            转换后的RL训练数据DataFrame
        """
        rl_data = {
            "data_source": [],
            "prompt": [],
            "ability": [],
            "reward_model": [],
            "extra_info": []
        }
        
        logger.info("开始转换RL训练数据...")
        
        # 统计信息
        total_records = len(data)
        filtered_count = 0
        has_keywords_count = 0
        
        for i, record in enumerate(data):
            if i % 1000 == 0:
                logger.info(f"已处理 {i}/{len(data)} 条记录")
            
            try:
                # === 新增：预处理步骤（仅表名字段名抽取） ===
                ok, pre_tables, pre_columns = preprocess_record(record)
                if not ok:
                    filtered_count += 1
                    logger.debug(f"记录 {i} 被过滤：抽取失败或包含LACK INFORMATION")
                    continue
                
                # 统计关键词样本数（使用原始数据）
                if record.get("llm_keyword_analysis", {}).get("has_special_keywords", False):
                    has_keywords_count += 1
                
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
                    "index": i,
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
                    # === 新增：预处理的表名字段名结果 ===
                    "pre_tables": list(pre_tables),
                    "pre_columns": list(pre_columns),
                    # === 保持原有关键词信息不变 ===
                    "llm_keyword_analysis": record.get("llm_keyword_analysis", {})
                }
                
                # 添加到数据集
                rl_data["data_source"].append("code2sql_orm")
                rl_data["prompt"].append(prompt)
                rl_data["ability"].append("code_generation")
                rl_data["reward_model"].append(reward_model)
                rl_data["extra_info"].append(extra_info)
                
            except Exception as e:
                logger.error(f"处理第 {i} 条记录时出错: {e}")
                continue
        
        # 输出统计信息
        final_count = len(rl_data['data_source'])
        logger.info(f"=== 预处理统计信息 ===")
        logger.info(f"原始样本数: {total_records}")
        logger.info(f"过滤样本数: {filtered_count}")
        logger.info(f"保留样本数: {final_count}")
        logger.info(f"保留率: {final_count/total_records*100:.1f}%")
        logger.info(f"有关键词样本数: {has_keywords_count}")
        logger.info(f"关键词样本占比: {has_keywords_count/final_count*100:.1f}%")
        
        logger.info(f"转换完成，共生成 {final_count} 条RL训练样本")
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
    
    def run_conversion(self, workflow_dir: Optional[Path] = None, output_name: Optional[str] = None,
                      val_ratio: float = 0.1) -> Tuple[Path, Path, Dict]:
        """
        执行完整的RL数据转换流程
        
        Args:
            workflow_dir: 指定的workflow目录（可选）
            output_name: 输出文件名前缀（可选）
            val_ratio: 验证集比例
            
        Returns:
            (训练集文件路径, 验证集文件路径, 数据集信息)
        """
        # 1. 查找或使用指定的workflow目录
        if workflow_dir is None:
            workflow_dir = self.find_latest_workflow_output()
            if workflow_dir is None:
                raise FileNotFoundError("未找到workflow输出目录")
        
        # 2. 加载数据
        data = self.load_workflow_data(workflow_dir)
        
        # 3. 转换为RL格式
        rl_df = self.convert_to_rl_format(data)
        
        # 4. 划分训练集和验证集
        train_df, val_df = self.split_train_val(rl_df, val_ratio)
        
        # 5. 保存数据
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"orm2sql_rl_{timestamp}"
        
        train_path, val_path = self.save_rl_data(train_df, val_df, output_name)
        
        # 6. 创建数据集信息
        dataset_info = self.create_dataset_info(train_df, val_df, output_name)
        
        # 7. 保存数据集信息文件
        info_path = self.rl_data_dir / f"{output_name}_info.json"
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据集信息已保存到: {info_path}")
        
        return train_path, val_path, dataset_info


def main():
    """主函数"""
    converter = RLDataConverter()
    
    try:
        # 执行转换
        train_path, val_path, dataset_info = converter.run_conversion()
        
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
    main() 