"""
冗余SQL验证器

使用SQLGlot解析SQL并通过LLM验证冗余标记的正确性
"""

import asyncio
import aiohttp
import json
import logging
import os
import csv
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from tqdm.asyncio import tqdm_asyncio

import sqlglot
from sqlglot.expressions import Column, Select, Insert, Update, Delete

try:
    from utils.llm_client import LLMClientManager
except ImportError:
    # 备用导入路径
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from utils.llm_client import LLMClientManager

logger = logging.getLogger(__name__)


class RedundantSQLValidator:
    """
    冗余SQL验证器
    
    用于验证被标记为 <REDUNDANT SQL> 的SQL语句是否确实冗余
    """
    
    def __init__(self, output_dir: str = ".", llm_server: str = "v3"):
        """
        初始化验证器
        
        Args:
            output_dir: 输出目录
            llm_server: LLM服务器名称
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 初始化LLM客户端管理器
        self.llm_manager = LLMClientManager()
        self.llm_client = self.llm_manager.get_client(llm_server)
        
        logger.info(f"冗余SQL验证器初始化完成，输出目录: {self.output_dir}")
    
    def _extract_redundant_sql_records(self, dataset: List[Dict]) -> List[Dict]:
        """
        提取包含冗余SQL标记的记录
        
        Args:
            dataset: 数据集
            
        Returns:
            List[Dict]: 包含冗余SQL的记录列表，每个记录包含:
                - function_name: 函数名
                - orm_code: ORM代码
                - caller: 调用者
                - redundant_sql_items: 冗余SQL项列表
        """
        redundant_records = []
        
        for record in dataset:
            # 跳过 <NO SQL GENERATE> 记录
            sql_list = record.get('sql_statement_list', [])
            if isinstance(sql_list, str) and sql_list == '<NO SQL GENERATE>':
                continue
            
            # 提取冗余SQL项
            redundant_sql_items = []
            
            if isinstance(sql_list, list):
                for sql_item in sql_list:
                    redundant_items = self._extract_redundant_from_item(sql_item)
                    redundant_sql_items.extend(redundant_items)
            elif isinstance(sql_list, str) and " <REDUNDANT SQL>" in sql_list:
                redundant_sql_items.append(sql_list)
            
            if redundant_sql_items:
                redundant_records.append({
                    'function_name': record.get('function_name', ''),
                    'orm_code': record.get('orm_code', ''),
                    'caller': record.get('caller', ''),
                    'redundant_sql_items': redundant_sql_items,
                    'original_record': record
                })
        
        return redundant_records
    
    def _extract_redundant_from_item(self, sql_item: Any) -> List[str]:
        """
        从SQL项中提取冗余SQL
        
        Args:
            sql_item: SQL项（可能是字符串、字典或列表）
            
        Returns:
            List[str]: 冗余SQL列表
        """
        redundant_sqls = []
        
        if isinstance(sql_item, str) and " <REDUNDANT SQL>" in sql_item:
            redundant_sqls.append(sql_item)
        elif isinstance(sql_item, dict) and sql_item.get("type") == "param_dependent":
            variants = sql_item.get("variants", [])
            for variant in variants:
                if isinstance(variant, dict) and "sql" in variant:
                    variant_sql = variant["sql"]
                    if isinstance(variant_sql, str) and " <REDUNDANT SQL>" in variant_sql:
                        redundant_sqls.append(variant_sql)
        elif isinstance(sql_item, list):
            for item in sql_item:
                redundant_sqls.extend(self._extract_redundant_from_item(item))
        
        return redundant_sqls
    
    def _parse_sql_with_sqlglot(self, sql_text: str) -> Tuple[Optional[str], List[str], bool]:
        """
        使用SQLGlot解析SQL语句
        
        Args:
            sql_text: SQL文本（包含 <REDUNDANT SQL> 标记）
            
        Returns:
            Tuple[stmt_type, where_columns, parse_error]:
                - stmt_type: 语句类型 (SELECT/INSERT/UPDATE/DELETE)
                - where_columns: WHERE子句中的列名列表
                - parse_error: 是否解析错误
        """
        # 移除 <REDUNDANT SQL> 标记
        clean_sql = sql_text.replace(" <REDUNDANT SQL>", "").strip()
        
        try:
            # 解析SQL
            parsed = sqlglot.parse_one(clean_sql, read='mysql')
            if not parsed:
                return None, [], True
            
            # 获取语句类型
            stmt_type = parsed.key.upper()
            
            # 提取WHERE子句中的列名
            where_columns = []
            
            # 查找所有列引用
            for column in parsed.find_all(Column):
                col_name = column.alias_or_name
                if col_name and col_name.lower() not in ['*', '1', '0']:
                    # 简单过滤：排除常见的非列名
                    if not re.match(r'^\d+$', col_name):  # 排除纯数字
                        where_columns.append(col_name)
            
            # 去重并排序
            where_columns = sorted(list(set(where_columns)))
            
            return stmt_type, where_columns, False
            
        except Exception as e:
            logger.warning(f"SQL解析失败: {e}, SQL: {clean_sql[:100]}...")
            return None, [], True
    
    def _build_validation_prompt(self, sql_text: str, stmt_type: Optional[str], where_columns: List[str]) -> str:
        """
        构造LLM验证prompt
        
        Args:
            sql_text: 原始SQL文本（包含 <REDUNDANT SQL>）
            stmt_type: 解析出的语句类型
            where_columns: 解析出的WHERE列名
            
        Returns:
            str: LLM验证prompt
        """
        clean_sql = sql_text.replace(" <REDUNDANT SQL>", "").strip()
        
        prompt = f"""请验证以下SQL解析信息是否正确。

SQL语句:
```sql
{clean_sql}
```

系统解析结果:
- 语句类型: {stmt_type or '解析失败'}
- WHERE子句涉及的列: {', '.join(where_columns) if where_columns else '无'}

请判断系统解析结果是否准确。如果准确，请回答"是"；如果有错误，请回答"否，应该是..."并说明正确的解析结果。

注意：只需要验证语句类型和WHERE列的识别是否正确，不需要验证SQL语法正确性。"""

        return prompt
    
    async def _validate_single_record(self, session: aiohttp.ClientSession, validation_item: Dict) -> Dict:
        """
        验证单个冗余SQL记录
        
        Args:
            session: aiohttp会话
            validation_item: 验证项，包含sql_text, stmt_type, where_columns等
            
        Returns:
            Dict: 验证结果
        """
        try:
            prompt = self._build_validation_prompt(
                validation_item['sql_text'],
                validation_item['stmt_type'],
                validation_item['where_columns']
            )
            
            response = await self.llm_client.call_async(
                session, prompt, max_tokens=200, temperature=0.0
            )
            
            # 解析LLM响应
            is_confirmed = False
            reason = ""
            
            if response:
                response = response.strip()
                if response.startswith('是'):
                    is_confirmed = True
                    reason = "LLM确认解析正确"
                elif response.startswith('否'):
                    is_confirmed = False
                    reason = response.replace('否', '').strip('，, ')
                else:
                    reason = f"LLM响应格式不规范: {response[:50]}..."
            else:
                reason = "LLM响应为空"
            
            result = validation_item.copy()
            result.update({
                'is_confirmed': is_confirmed,
                'llm_response': response,
                'reason': reason,
                'validation_timestamp': datetime.now().isoformat(),
                'validation_error': False
            })
            
            return result
            
        except Exception as e:
            logger.warning(f"验证单个记录失败: {e}")
            result = validation_item.copy()
            result.update({
                'is_confirmed': False,  # 默认不确认
                'llm_response': '',
                'reason': f'验证失败: {str(e)}',
                'validation_timestamp': datetime.now().isoformat(),
                'validation_error': True
            })
            return result
    
    async def validate_redundant_sql_records(self, dataset: List[Dict], apply_fix: bool = False) -> Dict[str, Any]:
        """
        验证冗余SQL记录
        
        Args:
            dataset: 数据集
            apply_fix: 是否应用修复（移除或取消标记）
            
        Returns:
            Dict: 验证结果摘要
        """
        logger.info("开始提取冗余SQL记录...")
        redundant_records = self._extract_redundant_sql_records(dataset)
        
        if not redundant_records:
            logger.info("未找到冗余SQL记录")
            return {
                'total_records': len(dataset),
                'redundant_records': 0,
                'validation_items': 0,
                'confirmed_redundant': 0,
                'disputed_redundant': 0,
                'parse_errors': 0,
                'validation_errors': 0,
                'output_files': {}
            }
        
        logger.info(f"找到 {len(redundant_records)} 个包含冗余SQL的记录")
        
        # 准备验证项
        validation_items = []
        for record in redundant_records:
            for sql_text in record['redundant_sql_items']:
                stmt_type, where_columns, parse_error = self._parse_sql_with_sqlglot(sql_text)
                
                validation_items.append({
                    'function_name': record['function_name'],
                    'orm_code': record['orm_code'],
                    'caller': record['caller'],
                    'sql_text': sql_text,
                    'clean_sql': sql_text.replace(" <REDUNDANT SQL>", "").strip(),
                    'stmt_type': stmt_type,
                    'where_columns': where_columns,
                    'parse_error': parse_error,
                    'original_record': record['original_record']
                })
        
        logger.info(f"准备验证 {len(validation_items)} 个冗余SQL项")
        
        # 异步验证
        semaphore = asyncio.Semaphore(100)  # 限制并发数
        
        async def validate_with_semaphore(session: aiohttp.ClientSession, item: Dict) -> Dict:
            async with semaphore:
                return await self._validate_single_record(session, item)
        
        validated_items = []
        with tqdm_asyncio(total=len(validation_items), desc="验证冗余SQL") as pbar:
            async with aiohttp.ClientSession() as session:
                tasks = [asyncio.ensure_future(validate_with_semaphore(session, item)) for item in validation_items]
                for task in tasks:
                    task.add_done_callback(lambda p: pbar.update(1))
                validated_items = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_validated_items = []
        for i, result in enumerate(validated_items):
            if isinstance(result, Exception):
                logger.error(f"验证项 {i} 处理异常: {result}")
                error_item = validation_items[i].copy()
                error_item.update({
                    'is_confirmed': False,
                    'llm_response': '',
                    'reason': f'处理异常: {str(result)}',
                    'validation_timestamp': datetime.now().isoformat(),
                    'validation_error': True
                })
                final_validated_items.append(error_item)
            else:
                final_validated_items.append(result)
        
        # 统计结果
        stats = {
            'total_records': len(dataset),
            'redundant_records': len(redundant_records),
            'validation_items': len(final_validated_items),
            'confirmed_redundant': sum(1 for item in final_validated_items if item.get('is_confirmed', False)),
            'disputed_redundant': sum(1 for item in final_validated_items if not item.get('is_confirmed', False) and not item.get('validation_error', False)),
            'parse_errors': sum(1 for item in final_validated_items if item.get('parse_error', False)),
            'validation_errors': sum(1 for item in final_validated_items if item.get('validation_error', False))
        }
        
        # 生成报告
        report_files = self._generate_reports(final_validated_items, stats)
        stats['output_files'] = report_files
        
        # 可选：应用修复
        if apply_fix:
            fixed_dataset = self._apply_fixes(dataset, final_validated_items)
            stats['fixed_dataset'] = fixed_dataset
            
            # 保存修复后的数据集
            fixed_file = self.output_dir / "fixed_dataset.json"
            with open(fixed_file, 'w', encoding='utf-8') as f:
                json.dump(fixed_dataset, f, ensure_ascii=False, indent=2)
            stats['output_files']['fixed_dataset'] = str(fixed_file)
            
            logger.info(f"已应用修复并保存到: {fixed_file}")
        
        logger.info(f"冗余SQL验证完成 - 确认冗余: {stats['confirmed_redundant']}, 争议: {stats['disputed_redundant']}, 解析错误: {stats['parse_errors']}")
        return stats
    
    def _apply_fixes(self, dataset: List[Dict], validated_items: List[Dict]) -> List[Dict]:
        """
        应用修复：移除确认冗余的SQL或取消争议标记
        
        Args:
            dataset: 原始数据集
            validated_items: 验证结果列表
            
        Returns:
            List[Dict]: 修复后的数据集
        """
        # 构建修复映射
        fixes_map = {}  # function_name -> list of fixes
        
        for item in validated_items:
            function_name = item['function_name']
            if function_name not in fixes_map:
                fixes_map[function_name] = []
            
            fixes_map[function_name].append({
                'sql_text': item['sql_text'],
                'is_confirmed': item['is_confirmed'],
                'validation_error': item.get('validation_error', False)
            })
        
        # 应用修复
        fixed_dataset = []
        for record in dataset:
            function_name = record.get('function_name', '')
            
            if function_name in fixes_map:
                fixed_record = record.copy()
                fixed_record['sql_statement_list'] = self._fix_sql_list(
                    record.get('sql_statement_list', []),
                    fixes_map[function_name]
                )
                fixed_dataset.append(fixed_record)
            else:
                fixed_dataset.append(record)
        
        return fixed_dataset
    
    def _fix_sql_list(self, sql_list: Any, fixes: List[Dict]) -> Any:
        """
        修复SQL列表
        
        Args:
            sql_list: 原始SQL列表
            fixes: 修复信息列表
            
        Returns:
            Any: 修复后的SQL列表
        """
        if isinstance(sql_list, str):
            if sql_list == '<NO SQL GENERATE>':
                return sql_list
            
            # 查找对应的修复
            for fix in fixes:
                if fix['sql_text'] == sql_list:
                    if fix['is_confirmed'] and not fix['validation_error']:
                        # 确认冗余，移除
                        return '<NO SQL GENERATE>'
                    elif not fix['is_confirmed'] and not fix['validation_error']:
                        # 争议，取消标记
                        return sql_list.replace(' <REDUNDANT SQL>', '')
            return sql_list
        
        elif isinstance(sql_list, list):
            fixed_list = []
            for sql_item in sql_list:
                fixed_item = self._fix_sql_item(sql_item, fixes)
                if fixed_item is not None:  # None表示被移除
                    fixed_list.append(fixed_item)
            return fixed_list if fixed_list else ['<NO SQL GENERATE>']
        
        return sql_list
    
    def _fix_sql_item(self, sql_item: Any, fixes: List[Dict]) -> Any:
        """
        修复单个SQL项
        
        Args:
            sql_item: SQL项
            fixes: 修复信息列表
            
        Returns:
            Any: 修复后的SQL项，None表示应被移除
        """
        if isinstance(sql_item, str):
            for fix in fixes:
                if fix['sql_text'] == sql_item:
                    if fix['is_confirmed'] and not fix['validation_error']:
                        return None  # 移除
                    elif not fix['is_confirmed'] and not fix['validation_error']:
                        return sql_item.replace(' <REDUNDANT SQL>', '')  # 取消标记
            return sql_item
        
        elif isinstance(sql_item, dict) and sql_item.get("type") == "param_dependent":
            fixed_item = sql_item.copy()
            fixed_variants = []
            
            for variant in sql_item.get("variants", []):
                if isinstance(variant, dict) and "sql" in variant:
                    variant_sql = variant["sql"]
                    fixed_variant = variant.copy()
                    
                    for fix in fixes:
                        if fix['sql_text'] == variant_sql:
                            if fix['is_confirmed'] and not fix['validation_error']:
                                # 跳过此变体（移除）
                                fixed_variant = None
                                break
                            elif not fix['is_confirmed'] and not fix['validation_error']:
                                # 取消标记
                                fixed_variant["sql"] = variant_sql.replace(' <REDUNDANT SQL>', '')
                    
                    if fixed_variant is not None:
                        fixed_variants.append(fixed_variant)
                else:
                    fixed_variants.append(variant)
            
            if fixed_variants:
                fixed_item["variants"] = fixed_variants
                return fixed_item
            else:
                return None  # 所有变体都被移除
        
        elif isinstance(sql_item, list):
            fixed_list = []
            for item in sql_item:
                fixed_item = self._fix_sql_item(item, fixes)
                if fixed_item is not None:
                    fixed_list.append(fixed_item)
            return fixed_list if fixed_list else None
        
        return sql_item
    
    def _generate_reports(self, validated_items: List[Dict], stats: Dict) -> Dict[str, str]:
        """
        生成验证报告
        
        Args:
            validated_items: 验证结果列表
            stats: 统计信息
            
        Returns:
            Dict[str, str]: 报告文件路径映射
        """
        report_files = {}
        
        # 1. 生成详细JSON报告
        json_file = self.output_dir / "validation_records.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(validated_items, f, ensure_ascii=False, indent=2)
        report_files['validation_records'] = str(json_file)
        
        # 2. 生成CSV汇总报告
        csv_file = self.output_dir / "validation_report.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'function_name', 'caller', 'sql_text', 'clean_sql', 'stmt_type', 
                'where_columns', 'is_confirmed', 'reason', 'parse_error', 'validation_error'
            ])
            
            for item in validated_items:
                writer.writerow([
                    item.get('function_name', ''),
                    item.get('caller', ''),
                    item.get('sql_text', ''),
                    item.get('clean_sql', ''),
                    item.get('stmt_type', ''),
                    ', '.join(item.get('where_columns', [])),
                    item.get('is_confirmed', False),
                    item.get('reason', ''),
                    item.get('parse_error', False),
                    item.get('validation_error', False)
                ])
        report_files['validation_csv'] = str(csv_file)
        
        # 3. 生成统计摘要
        summary_file = self.output_dir / "validation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        report_files['validation_summary'] = str(summary_file)
        
        logger.info(f"验证报告已生成:")
        logger.info(f"  - 详细记录: {json_file}")
        logger.info(f"  - CSV汇总: {csv_file}")
        logger.info(f"  - 统计摘要: {summary_file}")
        
        return report_files 