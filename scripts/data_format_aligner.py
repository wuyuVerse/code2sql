#!/usr/bin/env python3
"""
数据格式对齐处理器

将源数据格式对齐到目标格式，保留指定字段
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataFormatAligner:
    """数据格式对齐器"""
    
    def __init__(self):
        # 目标格式需要保留的字段
        self.target_fields = {
            'function_name',
            'orm_code', 
            'caller',
            'sql_statement_list',
            'sql_types',
            'code_meta_data',
            'sql_pattern_cnt',
            'source_file'
        }
    
    def align_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        对齐单条记录的格式
        
        Args:
            record: 源记录
            
        Returns:
            对齐后的记录
        """
        aligned_record = {}
        
        # 只保留目标字段
        for field in self.target_fields:
            if field in record:
                aligned_record[field] = record[field]
            else:
                # 如果缺少必要字段，设置默认值
                if field == 'caller':
                    aligned_record[field] = ""
                elif field == 'sql_statement_list':
                    aligned_record[field] = []
                elif field == 'sql_types':
                    aligned_record[field] = []
                elif field == 'code_meta_data':
                    aligned_record[field] = []
                elif field == 'sql_pattern_cnt':
                    aligned_record[field] = 0
                else:
                    aligned_record[field] = ""
        
        return aligned_record
    
    def process_file(self, source_file: str, target_file: str) -> Dict[str, Any]:
        """
        处理整个文件
        
        Args:
            source_file: 源文件路径
            target_file: 目标文件路径
            
        Returns:
            处理结果统计
        """
        logger.info(f"开始处理文件: {source_file}")
        
        # 读取源数据
        with open(source_file, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
        
        if not isinstance(source_data, list):
            raise ValueError("源数据必须是列表格式")
        
        # 对齐每条记录
        aligned_data = []
        removed_fields_stats = {}
        
        for i, record in enumerate(source_data):
            # 统计被移除的字段
            for field in record.keys():
                if field not in self.target_fields:
                    removed_fields_stats[field] = removed_fields_stats.get(field, 0) + 1
            
            # 对齐记录
            aligned_record = self.align_record(record)
            aligned_data.append(aligned_record)
        
        # 保存对齐后的数据
        target_path = Path(target_file)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(aligned_data, f, ensure_ascii=False, indent=2)
        
        # 统计结果
        result = {
            'source_file': source_file,
            'target_file': target_file,
            'total_records': len(source_data),
            'aligned_records': len(aligned_data),
            'retained_fields': list(self.target_fields),
            'removed_fields_stats': removed_fields_stats
        }
        
        logger.info(f"处理完成，共处理 {len(source_data)} 条记录")
        logger.info(f"移除的字段统计: {removed_fields_stats}")
        
        return result
    
    def compare_formats(self, source_file: str, target_file: str):
        """
        比较两个文件的格式差异
        
        Args:
            source_file: 源文件路径
            target_file: 目标文件路径
        """
        logger.info("开始比较文件格式...")
        
        # 读取两个文件
        with open(source_file, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
        
        with open(target_file, 'r', encoding='utf-8') as f:
            target_data = json.load(f)
        
        if not source_data or not target_data:
            logger.warning("文件为空，无法比较")
            return
        
        # 获取字段集合
        source_fields = set(source_data[0].keys()) if source_data else set()
        target_fields = set(target_data[0].keys()) if target_data else set()
        
        # 比较差异
        only_in_source = source_fields - target_fields
        only_in_target = target_fields - source_fields
        common_fields = source_fields & target_fields
        
        logger.info(f"源文件字段数: {len(source_fields)}")
        logger.info(f"目标文件字段数: {len(target_fields)}")
        logger.info(f"共同字段数: {len(common_fields)}")
        logger.info(f"仅源文件有的字段: {sorted(only_in_source)}")
        logger.info(f"仅目标文件有的字段: {sorted(only_in_target)}")
        logger.info(f"共同字段: {sorted(common_fields)}")


def main():
    """主函数"""
    source_file = "workflow_output/workflow_v1/0709111.json"
    target_reference = "workflow_output/workflow_v1/final_processed_dataset.json"
    output_file = "workflow_output/workflow_v1/aligned_data.json"
    
    aligner = DataFormatAligner()
    
    try:
        # 比较格式差异
        aligner.compare_formats(source_file, target_reference)
        
        print("\n" + "="*50)
        print("开始数据格式对齐...")
        
        # 执行格式对齐
        result = aligner.process_file(source_file, output_file)
        
        print("\n✅ 数据格式对齐完成!")
        print(f"📁 源文件: {result['source_file']}")
        print(f"📁 输出文件: {result['target_file']}")
        print(f"📊 处理记录数: {result['total_records']:,}")
        print(f"📋 保留字段: {len(result['retained_fields'])} 个")
        print(f"🗑️  移除字段统计:")
        
        for field, count in result['removed_fields_stats'].items():
            print(f"   - {field}: {count} 条记录")
        
        print(f"\n📄 保留的字段列表:")
        for field in sorted(result['retained_fields']):
            print(f"   - {field}")
            
    except Exception as e:
        logger.error(f"处理失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main()) 