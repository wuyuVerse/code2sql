"""
SQL清洗器

用于清洗数据中的SQL语句，移除无效SQL，保留有效的固定SQL和参数依赖SQL变体
"""

import re
import json
import logging
from typing import List, Dict, Any, Union, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class SQLCleaner:
    """SQL清洗器
    
    主要功能：
    1. 识别并移除无效SQL（如中文描述文本）
    2. 保留有效的固定SQL语句
    3. 保留参数依赖的SQL变体对象
    4. 记录清洗过程和统计信息
    """
    
    def __init__(self, output_dir: str = "cleaned_data"):
        """
        初始化SQL清洗器
        
        Args:
            output_dir: 清洗结果输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # SQL关键词模式（用于识别有效SQL）
        self.sql_keywords = {
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 
            'ALTER', 'TRUNCATE', 'REPLACE', 'SHOW', 'DESCRIBE', 'EXPLAIN',
            'WITH', 'UNION', 'HAVING', 'GROUP BY', 'ORDER BY', 'LIMIT'
        }
        
        # SQL语句模式（更严格的SQL检测）
        self.sql_patterns = [
            r'^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|REPLACE|SHOW|DESCRIBE|EXPLAIN|WITH)\s+',
            r'.*\s+(FROM|INTO|SET|WHERE|VALUES|TABLE|DATABASE|INDEX)\s+',
            r'.*;\s*$'  # 以分号结尾
        ]
        
        # 编译正则表达式
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE | re.MULTILINE) 
                                 for pattern in self.sql_patterns]
        
        # 清洗统计
        self.cleaning_stats = {}
        self.reset_stats()
        
        # 清洗日志
        self.cleaning_log = []
        
        logger.info("SQL清洗器初始化完成")
    
    def reset_stats(self):
        """重置统计信息"""
        self.cleaning_stats = {
            'total_records_processed': 0,
            'total_sql_items_processed': 0,
            'valid_sql_retained': 0,
            'invalid_sql_removed': 0,
            'param_dependent_sql_retained': 0,
            'records_modified': 0,
            'records_unchanged': 0,
            'empty_sql_lists_found': 0,
            'lists_emptied_after_cleaning': 0
        }
    
    def is_valid_sql(self, sql_item: Union[str, Dict[str, Any]]) -> bool:
        """
        判断SQL项是否有效
        
        Args:
            sql_item: SQL字符串或参数依赖对象
            
        Returns:
            是否为有效SQL
        """
        # 如果是参数依赖对象，直接认为有效
        if isinstance(sql_item, dict) and 'type' in sql_item and sql_item['type'] == 'param_dependent':
            return True
        
        # 如果不是字符串，认为无效
        if not isinstance(sql_item, str):
            return False
        
        sql_text = sql_item.strip()
        
        # 空字符串无效
        if not sql_text:
            return False
        
        
        # 检查是否包含SQL关键词（只要包含就认为有效）
        sql_upper = sql_text.upper()
        for keyword in self.sql_keywords:
            if keyword in sql_upper:
                return True
        
        # 如果是JSON数组格式，尝试解析并检查内容
        if sql_text.startswith('[') and sql_text.endswith(']'):
            try:
                import json
                parsed = json.loads(sql_text)
                if isinstance(parsed, list):
                    # 检查数组中是否有SQL语句
                    for item in parsed:
                        if isinstance(item, str):
                            item_upper = item.upper()
                            for keyword in self.sql_keywords:
                                if keyword in item_upper:
                                    return True
            except:
                pass
        
        # 检查是否匹配基本SQL模式（放宽条件）
        basic_sql_indicators = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER']
        for indicator in basic_sql_indicators:
            if indicator in sql_upper:
                return True
        
        # 检查常见SQL结构
        if any(x in sql_upper for x in ['FROM ', 'INTO ', 'SET ', 'WHERE ', 'VALUES']):
            return True
        
        return False
    
    def clean_sql_statement_list(self, sql_statement_list: List[Union[str, Dict[str, Any]]]) -> Tuple[List[Union[str, Dict[str, Any]]], List[Dict[str, Any]]]:
        """
        清洗SQL语句列表
        
        Args:
            sql_statement_list: 原始SQL语句列表
            
        Returns:
            (清洗后的SQL列表, 被移除的无效SQL列表)
        """
        cleaned_list = []
        removed_items = []
        
        for i, sql_item in enumerate(sql_statement_list):
            self.cleaning_stats['total_sql_items_processed'] += 1
            
            if self.is_valid_sql(sql_item):
                cleaned_list.append(sql_item)
                
                if isinstance(sql_item, dict) and sql_item.get('type') == 'param_dependent':
                    self.cleaning_stats['param_dependent_sql_retained'] += 1
                else:
                    self.cleaning_stats['valid_sql_retained'] += 1
            else:
                removed_items.append({
                    'position': i,
                    'content': str(sql_item)[:200] + '...' if len(str(sql_item)) > 200 else str(sql_item),
                    'reason': 'Invalid SQL detected'
                })
                self.cleaning_stats['invalid_sql_removed'] += 1
        
        return cleaned_list, removed_items
    
    def clean_record(self, record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        清洗单条记录
        
        Args:
            record: 原始记录
            
        Returns:
            (清洗后的记录, 清洗日志)
        """
        cleaned_record = record.copy()
        log_entry = {
            'function_name': record.get('function_name', 'Unknown'),
            'original_sql_count': len(record.get('sql_statement_list', [])),
            'modifications': []
        }
        
        # 清洗sql_statement_list
        if 'sql_statement_list' in record:
            original_sql_list = record['sql_statement_list']
            is_originally_empty = isinstance(original_sql_list, list) and not original_sql_list

            if is_originally_empty:
                self.cleaning_stats['empty_sql_lists_found'] += 1
                cleaned_record['sql_statement_list'] = "<NO SQL GENERATE>"
                log_entry['modifications'].append({
                    'field': 'sql_statement_list',
                    'action': 'set_to_no_sql_generate',
                    'reason': 'Original list was empty'
                })
                self.cleaning_stats['records_modified'] += 1
            else:
                cleaned_sql_list, removed_items = self.clean_sql_statement_list(original_sql_list)
                
                if not cleaned_sql_list and removed_items:
                    # 列表在清洗后变为空
                    self.cleaning_stats['lists_emptied_after_cleaning'] += 1
                    cleaned_record['sql_statement_list'] = "<NO SQL GENERATE>"
                    log_entry['modifications'].append({
                        'field': 'sql_statement_list',
                        'action': 'set_to_no_sql_generate',
                        'reason': 'List became empty after cleaning'
                    })
                else:
                    cleaned_record['sql_statement_list'] = cleaned_sql_list

                log_entry['cleaned_sql_count'] = len(cleaned_sql_list) if isinstance(cleaned_sql_list, list) else 0
                log_entry['removed_sql_count'] = len(removed_items)

                if removed_items:
                    log_entry['modifications'].append({
                        'field': 'sql_statement_list',
                        'action': 'removed_invalid_sql',
                        'removed_items': removed_items
                    })
                
                if removed_items or is_originally_empty:
                    self.cleaning_stats['records_modified'] += 1
                else:
                    self.cleaning_stats['records_unchanged'] += 1
        else:
             self.cleaning_stats['records_unchanged'] += 1

        return cleaned_record, log_entry
    
    def clean_dataset(self, data: List[Dict[str, Any]], step_name: str = "sql_cleaning") -> Dict[str, Any]:
        """
        清洗整个数据集
        
        Args:
            data: 原始数据集
            step_name: 清洗步骤名称
            
        Returns:
            清洗结果信息
        """
        logger.info(f"开始SQL清洗，数据集大小: {len(data)} 条记录")
        
        # 重置统计信息
        self.reset_stats()
        self.cleaning_log = []
        
        cleaned_data = []
        
        # 处理每条记录
        for i, record in enumerate(data):
            self.cleaning_stats['total_records_processed'] += 1
            
            if i % 1000 == 0:
                logger.info(f"清洗进度: {i}/{len(data)} ({i/len(data)*100:.1f}%)")
            
            cleaned_record, log_entry = self.clean_record(record)
            cleaned_data.append(cleaned_record)
            
            if log_entry['modifications']:
                self.cleaning_log.append(log_entry)
        
        logger.info("SQL清洗完成，开始保存结果...")
        
        # 创建带时间戳的输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        step_output_dir = self.output_dir / f"{step_name}_{timestamp}"
        step_output_dir.mkdir(exist_ok=True)
        
        # 保存清洗后的数据
        cleaned_data_file = step_output_dir / "cleaned_records.json"
        with open(cleaned_data_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        
        # 保存清洗日志
        cleaning_log_file = step_output_dir / "cleaning_log.json"
        with open(cleaning_log_file, 'w', encoding='utf-8') as f:
            json.dump(self.cleaning_log, f, ensure_ascii=False, indent=2)
        
        # 保存清洗统计
        cleaning_stats_file = step_output_dir / "cleaning_statistics.json"
        stats_with_meta = {
            **self.cleaning_stats,
            'step_name': step_name,
            'timestamp': timestamp,
            'input_records_count': len(data),
            'output_records_count': len(cleaned_data),
            'output_directory': str(step_output_dir)
        }
        
        with open(cleaning_stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_with_meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"清洗结果已保存到: {step_output_dir}")
        logger.info(f"清洗统计 - 总记录: {self.cleaning_stats['total_records_processed']}, "
                   f"修改记录: {self.cleaning_stats['records_modified']}, "
                   f"移除无效SQL: {self.cleaning_stats['invalid_sql_removed']}")
        
        return stats_with_meta
    
    def get_cleaning_summary(self) -> Dict[str, Any]:
        """获取清洗摘要"""
        return {
            'statistics': self.cleaning_stats,
            'log_entries_count': len(self.cleaning_log),
            'sample_log_entries': self.cleaning_log[:5] if self.cleaning_log else []
        } 