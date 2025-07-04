#!/usr/bin/env python3
"""
训练数据转换器

将workflow处理后的ORM数据转换为LLM微调训练格式
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import glob

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
        function_name = record.get('function_name', '未知函数')
        orm_code = record.get('orm_code', '')
        caller = record.get('caller', '')
        callee = record.get('callee', '')  # 如果有被调用者信息
        code_meta_data = record.get('code_meta_data', [])
        
        # 格式化元数据
        code_meta_data_str = self.format_code_metadata(code_meta_data)
        
        # 构建提示词
        prompt = f"""请基于以下分析要求，直接输出GORM代码对应的SQL语句JSON格式结果：

**首要判断：SQL生成有效性**
在开始分析前，请判断给定的ORM代码是否真的会生成SQL语句：
- 代码必须包含实际的数据库操作方法（Find、Create、Update、Delete、Count、First等）
- 仅有查询构建方法（Where、Select、Join等）而没有执行方法的代码不会生成SQL
- 如果代码不会生成任何SQL，请返回空数组[]

**分析步骤：**
1. **识别表名和字段映射**：
   **表名优先级：**
   · 元数据中TableName()函数显式返回值（最高优先级）
   · 配置文件中的表名映射（const常量、type定义等）
   · 代码中直接写出的表名（如Table("user_info")）- 必须原样保留
   · 默认命名规则：驼峰转下划线，严禁自动复数化（UserInfo→user_info，不是user_infos）
   
   **字段名优先级：**
   · 结构体tag中的column标签（如gorm:"column:user_name"）
   · 配置文件中的字段映射
   · 代码中直接写出的字段名（如Where("user_id = ?")）- 必须原样保留
   · 默认转换：驼峰转下划线（UserName→user_name）

2. **处理JOIN操作和表别名**：
   · 主表使用简短别名，关联表使用有意义的别名
   · SELECT、WHERE、ORDER BY、GROUP BY、HAVING子句中的所有列名必须带表别名前缀
   · ON条件必须使用完整格式：`ON t1.foreign_key = t2.primary_key`
   · 确保避免列名歧义，保持表别名一致性

3. **枚举所有可能的SQL结构**：
   · **忽略注释代码**：完全忽略//和/* */注释中的所有代码
   · 分析所有可能的WHERE条件字段组合（单条件、多条件AND、OR组合）
   · 考虑动态条件构建（if判断、循环遍历、switch分支等）
   · 识别GORM特性影响（关联查询、作用域、事务、软删/硬删等）
   · DELETE操作需包含显式Where条件＋主键自动条件

4. **上下文约束分析**（根据提供的信息进行）：
   · 如果提供调用者信息：只分析当前调用者触发的执行路径，排除其他独立路径
   · 如果提供被调用者信息：考虑内部调用可能产生的额外SQL操作
   · 如果信息不完整：基于现有信息进行最佳推断，但不臆测缺失部分

5. **生成标准SQL语句**：
   · 确保SQL完整可执行，参数用?占位
   · 不含省略号或[其他字段]等占位符
   · 每条SQL以分号结尾
   · 同结构SQL仅保留一条代表性模板

**输出格式要求：**
输出标准JSON数组，结构如下：
[
  "固定SQL语句;",
  {{
    "type": "param_dependent",
    "variants": [
      {{"scenario": "条件描述", "sql": "完整SQL语句;"}},
      {{"scenario": "条件描述", "sql": "完整SQL语句;"}}
    ]
  }},
  "另一个固定SQL;"
]

**严格要求：**
- 仅输出纯JSON数组，无其他文字说明
- SQL语句必须完整可执行，以分号结尾
- 不含省略号、占位符或解释性文本
- 参数使用问号(?)表示
- 只有SQL结构不同才视为不同变体

**分析目标代码：**
函数名称：{function_name}
{orm_code}

**元数据信息：**
以下元数据可能包含表名和列名的关键信息，请根据实际提供的内容进行分析：

· **表结构信息**（如提供）：数据库表的定义、字段标签、主键信息等，用于确定准确的表名和字段名
· **调用者代码**（如提供）：上层函数的调用方式、传递参数、业务条件等，用于限定执行路径
· **被调用者代码**（如提供）：内部调用的函数、嵌套查询、回调方法等，可能产生额外SQL

**注意**：如果某类信息未提供，请基于ORM代码本身和已有信息进行分析，不要为缺失信息创造假设。

调用者：{caller}
元数据：{code_meta_data_str}
被调用者：{callee if callee else ''}
**最终要求：仅输出纯JSON数组，无其他文字说明。**"""

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
    
    def convert_to_training_format(self, data: List[Dict]) -> List[Dict]:
        """
        将ORM数据转换为训练格式
        
        Args:
            data: workflow处理后的数据
            
        Returns:
            转换后的训练数据
        """
        training_data = []
        
        logger.info("开始转换训练数据...")
        
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
                training_sample["metadata"] = {
                    "function_name": record.get('function_name', ''),
                    "source_file": record.get('source_file', ''),
                    "sql_pattern_cnt": record.get('sql_pattern_cnt', 0),
                    "sql_types": record.get('sql_types', [])
                }
                
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
        
        # 3. 转换为训练格式
        training_data = self.convert_to_training_format(data)
        
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