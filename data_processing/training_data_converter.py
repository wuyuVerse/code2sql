#!/usr/bin/env python3
"""
训练数据转换器

将workflow处理后的ORM数据转换为LLM微调训练格式
"""

import json
import os
import logging
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import glob
from config.training.data_conversion.orm2sql_prompt_template import PROMPT_TEMPLATE

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TrainingDataConverter:
    """训练数据转换器"""
    
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
        self.training_data_dir = self.project_root / "model" / "data" / "orm2sql_training_data"
        
        # 确保输出目录存在
        self.training_data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"项目根目录: {self.project_root}")
        logger.info(f"工作流输出目录: {self.workflow_output_dir}")
        logger.info(f"训练数据输出目录: {self.training_data_dir}")
    
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
    
    def create_training_prompt(self, record: Dict) -> str:
        """
        根据记录创建训练提示词
        
        Args:
            record: 单条ORM记录
            
        Returns:
            格式化的提示词
        """
        function_name = record.get("function_name", "未知函数")
        orm_code = record.get("orm_code", "")
        caller = record.get("caller", "")
        callee = record.get("callee", "")
        code_meta_data_str = self.format_code_metadata(record.get("code_meta_data", []))
        prompt = PROMPT_TEMPLATE.format(
            function_name=function_name,
            orm_code=orm_code,
            caller=caller,
            code_meta_data_str=code_meta_data_str,
        )
        return prompt.strip()
    
    def create_training_response(self, record: Dict) -> str:
        """
        创建训练响应（标准答案）
        
        Args:
            record: 单条ORM记录
            
        Returns:
            JSON格式的SQL语句列表
        """
        sql_statement_list = record.get('sql_statement_list', [])
        return json.dumps(sql_statement_list, ensure_ascii=False, indent=None)
    
    def convert_to_training_format(self, data: List[Dict], shuffle: bool = True) -> List[Dict]:
        """
        将ORM数据转换为训练格式
        
        Args:
            data: workflow处理后的数据
            shuffle: 是否打乱数据顺序，默认True
            
        Returns:
            转换后的训练数据
        """
        training_data = []
        
        logger.info("开始转换训练数据...")
        
        # 如果需要打乱数据，先打乱原始数据
        if shuffle:
            logger.info("正在打乱数据顺序...")
            data_copy = data.copy()
            random.shuffle(data_copy)
            data = data_copy
            logger.info("数据打乱完成")
        
        for i, record in enumerate(data):
            if i % 1000 == 0:
                logger.info(f"已处理 {i}/{len(data)} 条记录")
            
            try:
                # 创建提示词和响应
                prompt = self.create_training_prompt(record)
                response = self.create_training_response(record)
                
                # 构建训练样本
                training_sample = {
                    "instruction": prompt,
                    "output": response
                }
                
                # 可选：添加额外的元信息用于调试
                metadata = {
                    "function_name": record.get('function_name', ''),
                    "source_file": record.get('source_file', ''),
                    "sql_types": record.get('sql_types', [])
                }
                training_sample["metadata"] = metadata
                
                training_data.append(training_sample)
                
            except Exception as e:
                logger.error(f"处理第 {i} 条记录时出错: {e}")
                continue
        
        logger.info(f"转换完成，共生成 {len(training_data)} 条训练样本")
        return training_data
    
    def save_training_data(self, training_data: List[Dict], output_name: Optional[str] = None) -> Path:
        """
        保存训练数据
        
        Args:
            training_data: 转换后的训练数据
            output_name: 输出文件名（可选）
            
        Returns:
            保存的文件路径
        """
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"orm2sql_training_data_{timestamp}.json"
        
        output_path = self.training_data_dir / output_name
        
        logger.info(f"正在保存训练数据到: {output_path}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        
        # 计算文件大小
        file_size = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"训练数据保存完成，文件大小: {file_size:.1f} MB")
        
        return output_path
    
    def create_dataset_info(self, training_data: List[Dict], dataset_name: str) -> Dict:
        """
        创建数据集信息文件
        
        Args:
            training_data: 训练数据
            dataset_name: 数据集名称
            
        Returns:
            数据集信息字典
        """
        return {
            dataset_name: {
                "file_name": f"{dataset_name}.json",
                "columns": {
                    "prompt": "instruction",
                    "response": "output"
                },
                "file_sha1": "",  # 可以后续计算
                "num_samples": len(training_data),
                "description": "ORM到SQL转换训练数据集，基于真实代码分析生成"
            }
        }
    
    def run_conversion(self, workflow_dir: Optional[Path] = None, output_name: Optional[str] = None) -> Tuple[Path, Dict]:
        """
        执行完整的数据转换流程
        
        Args:
            workflow_dir: 指定的workflow目录（可选）
            output_name: 输出文件名（可选）
            
        Returns:
            (训练数据文件路径, 数据集信息)
        """
        # 1. 查找或使用指定的workflow目录
        if workflow_dir is None:
            workflow_dir = self.find_latest_workflow_output()
            if workflow_dir is None:
                raise FileNotFoundError("未找到workflow输出目录")
        
        # 2. 加载数据
        data = self.load_workflow_data(workflow_dir)
        
        # 3. 转换为训练格式（默认打乱数据）
        training_data = self.convert_to_training_format(data, shuffle=True)
        
        # 4. 保存训练数据
        output_path = self.save_training_data(training_data, output_name)
        
        # 5. 创建数据集信息
        dataset_name = output_path.stem
        dataset_info = self.create_dataset_info(training_data, dataset_name)
        
        # 6. 保存数据集信息文件
        info_path = self.training_data_dir / "dataset_info.json"
        if info_path.exists():
            with open(info_path, 'r', encoding='utf-8') as f:
                existing_info = json.load(f)
            existing_info.update(dataset_info)
        else:
            existing_info = dataset_info
        
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(existing_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据集信息已保存到: {info_path}")
        
        return output_path, dataset_info


def main():
    """主函数"""
    converter = TrainingDataConverter()
    
    try:
        # 执行转换
        output_path, dataset_info = converter.run_conversion()
        
        print(f"\n✅ 数据转换完成!")
        print(f"📁 训练数据保存路径: {output_path}")
        print(f"📊 样本数量: {dataset_info[list(dataset_info.keys())[0]]['num_samples']}")
        print(f"📝 数据集信息: {converter.training_data_dir / 'dataset_info.json'}")
        
    except Exception as e:
        logger.error(f"数据转换失败: {e}")
        raise


if __name__ == "__main__":
    main() 