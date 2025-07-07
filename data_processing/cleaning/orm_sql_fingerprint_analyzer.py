import json
import os
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Any
import logging
from tqdm import tqdm

# 尝试导入SQL特征提取器
try:
    from .sql_feature_extractor import SQLFeatureExtractor, DMLType
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    try:
        from data_processing.cleaning.sql_feature_extractor import SQLFeatureExtractor, DMLType
    except ImportError:
        # # 如果都失败，定义简单的替代类
        # class SQLFeatureExtractor:
        #     def extract(self, sql_text: str) -> str:
        #         """简单的SQL指纹生成"""
        #         import hashlib
        #         return hashlib.md5(sql_text.encode()).hexdigest()
        
        # class DMLType:
        #     SELECT = 1
        #     INSERT = 2
        #     UPDATE = 3
        #     DELETE = 4
        raise ImportError("Failed to import SQLFeatureExtractor and DMLType")


class ORM_SQLFingerprintAnalyzer:
    """
    ORM代码SQL指纹分析器
    用于分析同一ORM代码下不同caller生成的SQL语句多样性，
    识别冗余SQL和可能的缺漏SQL
    """
    
    def __init__(self):
        self.extractor = SQLFeatureExtractor()
        self.orm_data = defaultdict(lambda: defaultdict(list))  # {orm_code: {caller: [sql_records]}}
        self.fingerprint_cache = {}  # SQL指纹缓存
        self.logger = logging.getLogger(__name__)
        
    def add_record(self, record: Dict[str, Any]):
        """
        添加一条记录到分析器
        
        Args:
            record: 包含function_name, orm_code, caller, sql_statement_list等字段的记录
        """
        function_name = record.get('function_name', 'unknown')
        orm_code = record.get('orm_code', '')
        caller = record.get('caller', 'unknown_caller')
        sql_statements = record.get('sql_statement_list', [])
        
        # 如果没有ORM代码，跳过
        if not orm_code or not orm_code.strip():
            return
            
        # 处理sql_statement_list
        if not isinstance(sql_statements, list):
            sql_statements = [sql_statements] if sql_statements else []
            
        for sql_item in sql_statements:
            # 处理不同类型的SQL项
            sql_texts = self._extract_sql_texts(sql_item)
            
            for sql_text in sql_texts:
                if sql_text and sql_text.strip():
                    # 计算指纹
                    fingerprint = self._get_fingerprint(sql_text.strip())
                    
                    # 创建记录
                    sql_record = {
                        'function_name': function_name,
                        'sql_text': sql_text.strip(),
                        'fingerprint': fingerprint,
                        'original_sql_item': sql_item
                    }
                    
                    self.orm_data[orm_code][caller].append(sql_record)
    
    def _extract_sql_texts(self, sql_item: Any) -> List[str]:
        """
        从SQL项中提取所有SQL文本
        
        Args:
            sql_item: SQL项，可能是字符串、字典或列表
            
        Returns:
            List[str]: 提取的SQL文本列表
        """
        sql_texts = []
        
        if isinstance(sql_item, str):
            sql_texts.append(sql_item)
        elif isinstance(sql_item, dict) and sql_item.get("type") == "param_dependent":
            # 处理param_dependent类型
            variants = sql_item.get("variants", [])
            for variant in variants:
                if isinstance(variant, dict) and "sql" in variant:
                    variant_sql = variant["sql"]
                    if isinstance(variant_sql, str):
                        sql_texts.append(variant_sql)
                    elif isinstance(variant_sql, list):
                        sql_texts.extend([s for s in variant_sql if isinstance(s, str)])
        elif isinstance(sql_item, list):
            for item in sql_item:
                sql_texts.extend(self._extract_sql_texts(item))
                
        return sql_texts
    
    def _get_fingerprint(self, sql_text: str) -> str:
        """
        获取SQL文本的指纹，使用缓存提高性能
        
        Args:
            sql_text: SQL文本
            
        Returns:
            str: SQL指纹
        """
        if sql_text not in self.fingerprint_cache:
            extractor = SQLFeatureExtractor()
            self.fingerprint_cache[sql_text] = extractor.extract(sql_text)
        return self.fingerprint_cache[sql_text]
    
    def _get_table_operation_combinations(self, sql_records: List[Dict]) -> Set[str]:
        """
        获取SQL记录的表-操作组合
        
        Args:
            sql_records: SQL记录列表
            
        Returns:
            Set[str]: 表-操作组合集合
        """
        combinations = set()
        
        for record in sql_records:
            sql_text = record['sql_text']
            extractor = SQLFeatureExtractor()
            extractor.extract(sql_text)
            
            # 获取表名和操作类型
            try:
                tables = list(extractor.table_count_dict.keys()) if hasattr(extractor, 'table_count_dict') else []
                stmt_type = extractor.stmt_type if hasattr(extractor, 'stmt_type') else None
                operation = self._get_operation_type(stmt_type) if stmt_type else "UNKNOWN"
            except:
                print(f"SQL指纹提取失败: {sql_text}")
                # 如果特征提取失败，使用简单的SQL解析
                tables = self._simple_table_extraction(sql_text)
                operation = self._simple_operation_extraction(sql_text)
            
            for table in tables:
                if table and table != 'null':  # 过滤无效表名
                    combinations.add(f"{table}:{operation}")
                    
        return combinations
    
    def _get_operation_type(self, stmt_type: int) -> str:
        """
        将语句类型转换为操作类型字符串
        
        Args:
            stmt_type: 语句类型
            
        Returns:
            str: 操作类型字符串
        """
        # 使用数字常量而不是导入
        if stmt_type == 1:  # SELECT
            return "SELECT"
        elif stmt_type == 2:  # INSERT
            return "INSERT"
        elif stmt_type == 3:  # UPDATE
            return "UPDATE"
        elif stmt_type == 4:  # DELETE
            return "DELETE"
        else:
            return "OTHER"
    
    def _simple_table_extraction(self, sql_text: str) -> List[str]:
        """
        简单的表名提取方法
        
        Args:
            sql_text: SQL文本
            
        Returns:
            List[str]: 提取的表名列表
        """
        import re
        tables = []
        sql_upper = sql_text.upper()
        
        # 提取FROM子句中的表名
        from_matches = re.findall(r'FROM\s+(\w+)', sql_upper)
        tables.extend(from_matches)
        
        # 提取INSERT INTO中的表名
        insert_matches = re.findall(r'INSERT\s+INTO\s+(\w+)', sql_upper)
        tables.extend(insert_matches)
        
        # 提取UPDATE中的表名
        update_matches = re.findall(r'UPDATE\s+(\w+)', sql_upper)
        tables.extend(update_matches)
        
        # 提取DELETE FROM中的表名
        delete_matches = re.findall(r'DELETE\s+FROM\s+(\w+)', sql_upper)
        tables.extend(delete_matches)
        
        # 提取JOIN中的表名
        join_matches = re.findall(r'JOIN\s+(\w+)', sql_upper)
        tables.extend(join_matches)
        
        return list(set(tables))  # 去重
    
    def _simple_operation_extraction(self, sql_text: str) -> str:
        """
        简单的操作类型提取方法
        
        Args:
            sql_text: SQL文本
            
        Returns:
            str: 操作类型
        """
        sql_upper = sql_text.upper().strip()
        
        if sql_upper.startswith('SELECT'):
            return "SELECT"
        elif sql_upper.startswith('INSERT'):
            return "INSERT"
        elif sql_upper.startswith('UPDATE'):
            return "UPDATE"
        elif sql_upper.startswith('DELETE'):
            return "DELETE"
        else:
            return "OTHER"
    
    def analyze_orm_diversity(self) -> Dict[str, Any]:
        """
        分析ORM代码的SQL多样性
        
        Returns:
            Dict: 分析结果
        """
        results = {}
        
        # 添加进度条
        pbar = tqdm(self.orm_data.items(), desc="分析ORM SQL多样性")
        for orm_code, callers_data in pbar:
            pbar.set_postfix({'ORM': orm_code[:20]})  # 显示当前处理的ORM代码（限制长度）
            # 统计每个ORM代码的基本信息
            total_sql_count = sum(len(records) for records in callers_data.values())
            unique_fingerprints = set()
            all_table_operations = set()
            
            caller_stats = {}
            
            for caller, records in callers_data.items():
                # 统计每个caller的信息
                caller_fingerprints = set()
                caller_sql_count = len(records)
                
                for record in records:
                    fingerprint = record['fingerprint']
                    unique_fingerprints.add(fingerprint)
                    caller_fingerprints.add(fingerprint)
                
                # 获取表-操作组合
                table_operations = self._get_table_operation_combinations(records)
                all_table_operations.update(table_operations)
                
                caller_stats[caller] = {
                    'sql_count': caller_sql_count,
                    'unique_fingerprints': len(caller_fingerprints),
                    'fingerprint_list': list(caller_fingerprints),
                    'table_operations': list(table_operations),
                    'table_operation_count': len(table_operations)
                }
            
            # 计算ORM级别统计
            results[orm_code] = {
                'total_callers': len(callers_data),
                'total_sql_count': total_sql_count,
                'unique_fingerprints': len(unique_fingerprints),
                'unique_table_operations': len(all_table_operations),
                'callers': caller_stats,
                'all_fingerprints': list(unique_fingerprints),
                'all_table_operations': list(all_table_operations)
            }
            
        return results
    
    def identify_redundant_sql(self) -> Dict[str, List[Dict]]:
        """
        识别冗余SQL（同一caller中重复的指纹）
        
        Returns:
            Dict: 冗余SQL信息
        """
        redundant_info = {}
        
        # 添加进度条
        pbar = tqdm(self.orm_data.items(), desc="识别冗余SQL")
        for orm_code, callers_data in pbar:
            pbar.set_postfix({'ORM': orm_code[:20]})  # 显示当前处理的ORM代码
            orm_redundant = []
            
            for caller, records in callers_data.items():
                # 统计每个指纹出现的次数
                fingerprint_counts = Counter(record['fingerprint'] for record in records)
                
                # 找出重复的指纹
                for fingerprint, count in fingerprint_counts.items():
                    if count > 1:
                        # 找到所有使用此指纹的记录
                        redundant_records = [r for r in records if r['fingerprint'] == fingerprint]
                        
                        orm_redundant.append({
                            'caller': caller,
                            'fingerprint': fingerprint,
                            'count': count,
                            'function_names': [r['function_name'] for r in redundant_records],
                            'sql_examples': [r['sql_text'] for r in redundant_records[:2]]  # 只保存前2个例子
                        })
            
            if orm_redundant:
                redundant_info[orm_code] = orm_redundant
                
        return redundant_info
    
    def identify_missing_or_extra_sql(self) -> Dict[str, Dict]:
        """
        识别可能的缺漏或额外SQL
        基于假设：如果某个caller的指纹集合是其他caller的真子集，
        可能表示该caller缺少某些SQL或其他caller有额外SQL
        
        Returns:
            Dict: 缺漏或额外SQL信息
        """
        missing_extra_info = {}
        
        # 添加进度条
        pbar = tqdm(self.orm_data.items(), desc="分析SQL缺漏情况")
        for orm_code, callers_data in pbar:
            pbar.set_postfix({'ORM': orm_code[:20]})  # 显示当前处理的ORM代码
            if len(callers_data) < 2:  # 至少需要2个caller才能比较
                continue
                
            caller_fingerprints = {}
            for caller, records in callers_data.items():
                caller_fingerprints[caller] = set(record['fingerprint'] for record in records)
            
            orm_analysis = {
                'caller_comparisons': [],
                'potential_missing': [],
                'potential_extra': []
            }
            
            callers = list(caller_fingerprints.keys())
            
            # 两两比较caller
            for i, caller1 in enumerate(callers):
                for caller2 in callers[i+1:]:
                    fp1 = caller_fingerprints[caller1]
                    fp2 = caller_fingerprints[caller2]
                    
                    # 计算交集和差集
                    intersection = fp1 & fp2
                    only_in_1 = fp1 - fp2
                    only_in_2 = fp2 - fp1
                    
                    comparison = {
                        'caller1': caller1,
                        'caller2': caller2,
                        'caller1_fingerprints': len(fp1),
                        'caller2_fingerprints': len(fp2),
                        'common_fingerprints': len(intersection),
                        'only_in_caller1': len(only_in_1),
                        'only_in_caller2': len(only_in_2),
                        'jaccard_similarity': len(intersection) / len(fp1 | fp2) if fp1 | fp2 else 0
                    }
                    
                    orm_analysis['caller_comparisons'].append(comparison)
                    
                    # 检查子集关系
                    if fp1.issubset(fp2) and fp1 != fp2:
                        # caller1是caller2的真子集，caller1可能缺少SQL
                        missing_fps = fp2 - fp1
                        orm_analysis['potential_missing'].append({
                            'caller': caller1,
                            'compared_to': caller2,
                            'missing_fingerprints': list(missing_fps),
                            'missing_count': len(missing_fps),
                            'reason': f'{caller1}的指纹集合是{caller2}的真子集'
                        })
                    elif fp2.issubset(fp1) and fp1 != fp2:
                        # caller2是caller1的真子集，caller2可能缺少SQL
                        missing_fps = fp1 - fp2
                        orm_analysis['potential_missing'].append({
                            'caller': caller2,
                            'compared_to': caller1,
                            'missing_fingerprints': list(missing_fps),
                            'missing_count': len(missing_fps),
                            'reason': f'{caller2}的指纹集合是{caller1}的真子集'
                        })
            
            # 识别可能的额外SQL（指纹只在一个caller中出现且该caller指纹数量明显较多）
            if len(callers) >= 2:
                # 计算每个caller的独有指纹
                for caller in callers:
                    other_callers_fps = set()
                    for other_caller in callers:
                        if other_caller != caller:
                            other_callers_fps.update(caller_fingerprints[other_caller])
                    
                    unique_to_caller = caller_fingerprints[caller] - other_callers_fps
                    
                    if unique_to_caller:
                        # 如果独有指纹数量较多，可能是额外SQL
                        total_fps = len(caller_fingerprints[caller])
                        unique_ratio = len(unique_to_caller) / total_fps if total_fps > 0 else 0
                        
                        if unique_ratio > 0.3:  # 如果30%以上的指纹是独有的
                            orm_analysis['potential_extra'].append({
                                'caller': caller,
                                'unique_fingerprints': list(unique_to_caller),
                                'unique_count': len(unique_to_caller),
                                'total_fingerprints': total_fps,
                                'unique_ratio': unique_ratio,
                                'reason': f'{caller}有{unique_ratio:.1%}的指纹是独有的，可能包含额外SQL'
                            })
            
            if (orm_analysis['caller_comparisons'] or 
                orm_analysis['potential_missing'] or 
                orm_analysis['potential_extra']):
                missing_extra_info[orm_code] = orm_analysis
                
        return missing_extra_info
    
    def _generate_simplified_report(self, missing_extra_info: Dict[str, Dict], limit: int = 100) -> Dict[str, Dict]:
        """
        生成精简版的缺漏或额外SQL报告
        
        Args:
            missing_extra_info: 完整的缺漏或额外SQL信息
            limit: 限制记录数量
            
        Returns:
            Dict: 精简版报告
        """
        simplified_report = {}
        record_count = 0
        
        for orm_code, analysis in missing_extra_info.items():
            if record_count >= limit:
                break
                
            simplified_analysis = {
                'caller_comparisons': [],
                'potential_missing': [],
                'potential_extra': []
            }
            
            # 添加caller比较结果（最多添加limit/3条）
            comparison_limit = min(len(analysis['caller_comparisons']), limit // 3)
            simplified_analysis['caller_comparisons'] = analysis['caller_comparisons'][:comparison_limit]
            record_count += comparison_limit
            
            # 添加潜在缺失SQL（最多添加limit/3条）
            if record_count < limit:
                missing_limit = min(len(analysis['potential_missing']), (limit - record_count) // 2)
                simplified_analysis['potential_missing'] = analysis['potential_missing'][:missing_limit]
                record_count += missing_limit
            
            # 添加潜在额外SQL（最多添加剩余配额）
            if record_count < limit:
                extra_limit = min(len(analysis['potential_extra']), limit - record_count)
                simplified_analysis['potential_extra'] = analysis['potential_extra'][:extra_limit]
                record_count += extra_limit
            
            if (simplified_analysis['caller_comparisons'] or 
                simplified_analysis['potential_missing'] or 
                simplified_analysis['potential_extra']):
                simplified_report[orm_code] = simplified_analysis
                
        return simplified_report

    def generate_reports(self, output_dir: str = "."):
        """
        生成分析报告文件
        
        Args:
            output_dir: 输出目录
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. 生成ORM SQL统计报告
        self.logger.info("开始生成ORM SQL统计报告...")
        orm_stats = self.analyze_orm_diversity()
        stats_file = os.path.join(output_dir, "orm_sql_stats.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(orm_stats, f, ensure_ascii=False, indent=2)
        self.logger.info(f"ORM SQL统计报告已保存到: {stats_file}")
        
        # 2. 生成冗余SQL标记报告
        self.logger.info("开始生成冗余SQL标记报告...")
        redundant_sql = self.identify_redundant_sql()
        redundant_file = os.path.join(output_dir, "redundant_sql_marks.json")
        with open(redundant_file, 'w', encoding='utf-8') as f:
            json.dump(redundant_sql, f, ensure_ascii=False, indent=2)
        self.logger.info(f"冗余SQL标记报告已保存到: {redundant_file}")
        
        # 3. 生成缺漏或额外SQL报告
        self.logger.info("开始生成SQL缺漏分析报告...")
        missing_extra = self.identify_missing_or_extra_sql()
        missing_file = os.path.join(output_dir, "missing_or_extra_sql_report.json")
        with open(missing_file, 'w', encoding='utf-8') as f:
            json.dump(missing_extra, f, ensure_ascii=False, indent=2)
        self.logger.info(f"缺漏或额外SQL报告已保存到: {missing_file}")
        
        # 4. 生成精简版缺漏或额外SQL报告（限制100条记录）
        self.logger.info("开始生成精简版SQL缺漏分析报告...")
        simplified_missing_extra = self._generate_simplified_report(missing_extra, limit=100)
        simplified_missing_file = os.path.join(output_dir, "missing_or_extra_sql_report_simplified.json")
        with open(simplified_missing_file, 'w', encoding='utf-8') as f:
            json.dump(simplified_missing_extra, f, ensure_ascii=False, indent=2)
        self.logger.info(f"精简版缺漏或额外SQL报告已保存到: {simplified_missing_file}")
        
        return {
            'orm_stats_file': stats_file,
            'redundant_sql_file': redundant_file,
            'missing_extra_file': missing_file,
            'simplified_missing_extra_file': simplified_missing_file,
            'summary': {
                'total_orm_codes': len(orm_stats),
                'orm_with_redundant_sql': len(redundant_sql),
                'orm_with_missing_extra': len(missing_extra)
            }
        }
    
    def mark_redundant_sql_in_dataset(self, dataset: List[Dict]) -> List[Dict]:
        """
        在数据集中标记冗余SQL
        
        Args:
            dataset: 原始数据集
            
        Returns:
            List[Dict]: 标记后的数据集
        """
        # 获取冗余SQL信息
        redundant_info = self.identify_redundant_sql()
        
        # 创建指纹到冗余标记的映射
        redundant_fingerprints = {}
        for orm_code, redundant_list in redundant_info.items():
            for item in redundant_list:
                key = f"{orm_code}:{item['caller']}:{item['fingerprint']}"
                redundant_fingerprints[key] = True
        
        # 标记数据集
        marked_dataset = []
        for record in dataset:
            marked_record = record.copy()
            
            orm_code = record.get('orm_code', '')
            caller = record.get('caller', 'unknown_caller')
            sql_statements = record.get('sql_statement_list', [])

            # 新增：保持"<NO SQL GENERATE>"为字符串类型
            if isinstance(sql_statements, str) and sql_statements == '<NO SQL GENERATE>':
                marked_record['sql_statement_list'] = '<NO SQL GENERATE>'
                marked_dataset.append(marked_record)
                continue
            
            if not isinstance(sql_statements, list):
                sql_statements = [sql_statements] if sql_statements else []
            
            # 处理SQL语句列表
            marked_sql_statements = []
            for sql_item in sql_statements:
                marked_sql_item = self._mark_sql_item(sql_item, orm_code, caller, redundant_fingerprints)
                marked_sql_statements.append(marked_sql_item)
            
            # 如果原始sql_statements是空且返回空，仍保持列表类型
            marked_record['sql_statement_list'] = marked_sql_statements if marked_sql_statements else sql_statements
            marked_dataset.append(marked_record)
        
        return marked_dataset
    
    def _mark_sql_item(self, sql_item: Any, orm_code: str, caller: str, redundant_fingerprints: Dict) -> Any:
        """
        标记单个SQL项
        
        Args:
            sql_item: SQL项
            orm_code: ORM代码
            caller: 调用者
            redundant_fingerprints: 冗余指纹映射
            
        Returns:
            Any: 标记后的SQL项
        """
        if isinstance(sql_item, str):
            # 检查是否冗余
            fingerprint = self._get_fingerprint(sql_item.strip())
            key = f"{orm_code}:{caller}:{fingerprint}"
            
            if key in redundant_fingerprints:
                return f"{sql_item} <REDUNDANT SQL>"
            else:
                return sql_item
                
        elif isinstance(sql_item, dict) and sql_item.get("type") == "param_dependent":
            # 处理param_dependent类型
            marked_item = sql_item.copy()
            marked_variants = []
            
            variants = sql_item.get("variants", [])
            for variant in variants:
                if isinstance(variant, dict) and "sql" in variant:
                    marked_variant = variant.copy()
                    variant_sql = variant["sql"]
                    
                    if isinstance(variant_sql, str):
                        fingerprint = self._get_fingerprint(variant_sql.strip())
                        key = f"{orm_code}:{caller}:{fingerprint}"
                        
                        if key in redundant_fingerprints:
                            marked_variant["sql"] = f"{variant_sql} <REDUNDANT SQL>"
                    
                    marked_variants.append(marked_variant)
                else:
                    marked_variants.append(variant)
            
            marked_item["variants"] = marked_variants
            return marked_item
            
        elif isinstance(sql_item, list):
            # 处理列表类型
            return [self._mark_sql_item(item, orm_code, caller, redundant_fingerprints) for item in sql_item]
        
        return sql_item
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        获取分析摘要
        
        Returns:
            Dict: 分析摘要
        """
        total_orm_codes = len(self.orm_data)
        total_callers = sum(len(callers) for callers in self.orm_data.values())
        total_sql_records = sum(
            len(records) 
            for callers in self.orm_data.values() 
            for records in callers.values()
        )
        
        # 分析多样性
        diversity_stats = self.analyze_orm_diversity()
        redundant_stats = self.identify_redundant_sql()
        missing_extra_stats = self.identify_missing_or_extra_sql()
        
        return {
            'total_orm_codes': total_orm_codes,
            'total_callers': total_callers,
            'total_sql_records': total_sql_records,
            'orm_with_multiple_callers': len([
                orm for orm, callers in self.orm_data.items() 
                if len(callers) > 1
            ]),
            'orm_with_redundant_sql': len(redundant_stats),
            'orm_with_potential_missing_extra': len(missing_extra_stats),
            'average_callers_per_orm': total_callers / total_orm_codes if total_orm_codes > 0 else 0,
            'average_sql_per_orm': total_sql_records / total_orm_codes if total_orm_codes > 0 else 0
        } 