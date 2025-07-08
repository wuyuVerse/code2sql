import json
import os
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Any, Optional
import logging
from datetime import datetime
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
    ORM代码SQL指纹分析器 - 重构版
    
    新逻辑：
    1. 统计每个ORM代码下不同caller的SQL指纹集合
    2. 选择最完整的caller作为参考指纹集合(Reference Set)
    3. 检测其他caller的包含关系(冗余)和新增指纹(可能错误)
    4. 生成待LLM验证的候选项
    """
    
    def __init__(self):
        self.extractor = SQLFeatureExtractor()
        self.orm_data = defaultdict(lambda: defaultdict(list))  # {orm_code: {caller: [sql_records]}}
        self.fingerprint_cache = {}  # SQL指纹缓存
        self.logger = logging.getLogger(__name__)
        
        # 新增：分析结果缓存
        self.reference_sets = {}  # {orm_code: {'caller': str, 'fingerprints': set}}
        self.analysis_results = {}  # {orm_code: analysis_result}
        
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
                        'original_sql_item': sql_item,
                        'original_record': record  # 保存完整的原始记录
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
    
    def _select_reference_set(self, orm_code: str, callers_data: Dict[str, List[Dict]]) -> Optional[Dict[str, Any]]:
        """
        选择参考指纹集合(Reference Set)
        
        策略：选择指纹数量最多且质量最好的caller作为参考
        
        Args:
            orm_code: ORM代码
            callers_data: caller数据 {caller: [sql_records]}
            
        Returns:
            Optional[Dict]: 参考集合信息，如果没有数据返回None
        """
        if len(callers_data) <= 1:
            # 只有一个或没有caller，无法比较
            if callers_data:
                single_caller = list(callers_data.keys())[0]
                single_fingerprints = set(r['fingerprint'] for r in callers_data[single_caller])
                return {
                    'caller': single_caller,
                    'fingerprints': single_fingerprints,
                    'fingerprint_count': len(single_fingerprints),
                    'reason': 'only_caller'
                }
            return None
        
        # 计算每个caller的指纹统计
        caller_stats = {}
        for caller, records in callers_data.items():
            fingerprints = set(record['fingerprint'] for record in records)
            caller_stats[caller] = {
                'fingerprints': fingerprints,
                'fingerprint_count': len(fingerprints),
                'sql_count': len(records),
                'avg_sql_per_fingerprint': len(records) / len(fingerprints) if fingerprints else 0
            }
        
        # 选择策略：优先指纹数量最多，其次考虑SQL覆盖度
        best_caller = max(caller_stats.keys(), key=lambda c: (
            caller_stats[c]['fingerprint_count'],
            caller_stats[c]['sql_count']
        ))
        
        reference_info = {
            'caller': best_caller,
            'fingerprints': caller_stats[best_caller]['fingerprints'],
            'fingerprint_count': caller_stats[best_caller]['fingerprint_count'],
            'reason': 'most_comprehensive',
            'all_caller_stats': caller_stats
        }
        
        self.reference_sets[orm_code] = reference_info
        return reference_info
    
    def _analyze_fingerprint_differences(self, orm_code: str, callers_data: Dict[str, List[Dict]], 
                                       reference_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析指纹差异，识别冗余、缺漏、新增指纹
        
        Args:
            orm_code: ORM代码
            callers_data: caller数据
            reference_info: 参考集合信息
            
        Returns:
            Dict: 差异分析结果
        """
        reference_caller = reference_info['caller']
        reference_fingerprints = reference_info['fingerprints']
        
        analysis_result = {
            'orm_code': orm_code,
            'reference_caller': reference_caller,
            'reference_fingerprints': list(reference_fingerprints),
            'reference_count': len(reference_fingerprints),
            'caller_analysis': {},
            'redundant_candidates': [],  # 冗余候选（被包含）
            'missing_candidates': [],   # 缺漏候选
            'new_fingerprint_candidates': [],  # 新增指纹候选
            'summary': {}
        }
        
        # 遍历所有 caller 与参考集合比较
        for caller, records in callers_data.items():
            if caller == reference_caller:
                continue  # 跳过参考 caller
            
            caller_fingerprints = set(record['fingerprint'] for record in records)
            
            # 计算集合关系
            intersection = caller_fingerprints & reference_fingerprints
            missing_in_caller = reference_fingerprints - caller_fingerprints  # 缺漏
            extra_in_caller = caller_fingerprints - reference_fingerprints    # 新增
            
            caller_analysis = {
                'caller': caller,
                'fingerprints': list(caller_fingerprints),
                'fingerprint_count': len(caller_fingerprints),
                'common_with_reference': list(intersection),
                'common_count': len(intersection),
                'missing_from_reference': list(missing_in_caller),
                'missing_count': len(missing_in_caller),
                'extra_beyond_reference': list(extra_in_caller),
                'extra_count': len(extra_in_caller),
                'is_subset_of_reference': caller_fingerprints.issubset(reference_fingerprints),
                'is_superset_of_reference': caller_fingerprints.issuperset(reference_fingerprints),
                'jaccard_similarity': len(intersection) / len(caller_fingerprints | reference_fingerprints) if caller_fingerprints | reference_fingerprints else 0
            }
            
            analysis_result['caller_analysis'][caller] = caller_analysis
            
            # 生成验证候选项
            
            # 1. 冗余候选：caller是参考集合的真子集
            if caller_analysis['is_subset_of_reference'] and caller_fingerprints != reference_fingerprints:
                redundant_candidate = {
                    'type': 'redundant',
                    'caller': caller,
                    'orm_code': orm_code,
                    'reason': f'caller指纹集合被参考集合完全包含',
                    'redundant_fingerprints': list(caller_fingerprints),
                    'redundant_sqls': [r for r in records if r['fingerprint'] in caller_fingerprints]
                }
                analysis_result['redundant_candidates'].append(redundant_candidate)
            
            # 2. 缺漏候选：参考集合中有但caller中没有的指纹
            if missing_in_caller:
                # 获取缺漏指纹对应的SQL示例
                missing_sql_examples = []
                for missing_fp in missing_in_caller:
                    # 从参考caller中找到对应的SQL
                    ref_records = callers_data[reference_caller]
                    examples = [r for r in ref_records if r['fingerprint'] == missing_fp]
                    if examples:
                        missing_sql_examples.append(examples[0])  # 取第一个作为示例
                
                missing_candidate = {
                    'type': 'missing',
                            'caller': caller,
                    'orm_code': orm_code,
                    'reason': f'caller缺少{len(missing_in_caller)}个参考指纹',
                    'missing_fingerprints': list(missing_in_caller),
                    'missing_sql_examples': missing_sql_examples
                }
                analysis_result['missing_candidates'].append(missing_candidate)
            
            # 3. 新增指纹候选：caller有但参考集合中没有的指纹
            if extra_in_caller:
                extra_sqls = [r for r in records if r['fingerprint'] in extra_in_caller]
                
                new_fp_candidate = {
                    'type': 'new_fingerprint',
                    'caller': caller,
                    'orm_code': orm_code,
                    'reason': f'caller包含{len(extra_in_caller)}个新指纹',
                    'new_fingerprints': list(extra_in_caller),
                    'new_sqls': extra_sqls
                }
                analysis_result['new_fingerprint_candidates'].append(new_fp_candidate)
        
        # 生成摘要统计
        analysis_result['summary'] = {
            'total_callers': len(callers_data),
            'analyzed_callers': len(analysis_result['caller_analysis']),
            'redundant_callers': len(analysis_result['redundant_candidates']),
            'callers_with_missing': len(analysis_result['missing_candidates']),
            'callers_with_new_fps': len(analysis_result['new_fingerprint_candidates']),
            'total_candidates_for_llm': (len(analysis_result['redundant_candidates']) + 
                                       len(analysis_result['missing_candidates']) + 
                                       len(analysis_result['new_fingerprint_candidates']))
        }
        
        return analysis_result
    
    def analyze_orm_fingerprint_differences(self) -> Dict[str, Any]:
        """
        分析所有ORM代码的指纹差异
        
        Returns:
            Dict: 完整的差异分析结果
        """
        all_results = {}
        
        self.logger.info(f"开始分析 {len(self.orm_data)} 个ORM代码的指纹差异...")
        
        pbar = tqdm(self.orm_data.items(), desc="分析ORM指纹差异")
        for orm_code, callers_data in pbar:
            pbar.set_postfix({'ORM': orm_code[:30]})
            
            # 选择参考指纹集合
            reference_info = self._select_reference_set(orm_code, callers_data)
            if not reference_info:
                continue  # 跳过没有数据的ORM
            
            # 分析指纹差异
            analysis_result = self._analyze_fingerprint_differences(orm_code, callers_data, reference_info)
            all_results[orm_code] = analysis_result
            
            # 缓存结果
            self.analysis_results[orm_code] = analysis_result
        
        return all_results
    
    def generate_llm_validation_candidates(self, limit_per_type: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        生成需要LLM验证的候选项列表
        
        Args:
            limit_per_type: 每种类型的候选项数量限制 (None表示无限制，处理全部)
            
        Returns:
            List[Dict]: LLM验证候选项列表
        """
        if not self.analysis_results:
            self.analyze_orm_fingerprint_differences()
        
        llm_candidates = []
        
        # 统计各类型候选项
        type_counts = {'redundant': 0, 'missing': 0, 'new_fingerprint': 0}
        
        for orm_code, analysis in self.analysis_results.items():
            # 获取ORM代码的完整内容
            orm_records = self.orm_data[orm_code]
            orm_code_content = ""
            if orm_records:
                first_caller_records = list(orm_records.values())[0]
                if first_caller_records:
                    orm_code_content = first_caller_records[0].get('original_record', {}).get('orm_code', '')
            
            # 添加冗余候选项 - 全量处理
            for candidate in analysis['redundant_candidates']:
                if limit_per_type is not None and type_counts['redundant'] >= limit_per_type:
                    break
                
                llm_candidate = {
                    'validation_type': 'redundant',
                    'orm_code': orm_code,
                    'orm_code_content': orm_code_content,
                    'target_caller': candidate['caller'],
                    'reference_caller': analysis['reference_caller'],
                    'candidate_info': candidate,
                    'priority': 'high',  # 冗余检测优先级高
                    'validation_id': f"redundant_{orm_code}_{candidate['caller']}"
                }
                llm_candidates.append(llm_candidate)
                type_counts['redundant'] += 1
            
            # 添加新增指纹候选项 - 全量处理
            for candidate in analysis['new_fingerprint_candidates']:
                if limit_per_type is not None and type_counts['new_fingerprint'] >= limit_per_type:
                    break
                
                llm_candidate = {
                    'validation_type': 'new_fingerprint',
                    'orm_code': orm_code,
                    'orm_code_content': orm_code_content,
                    'target_caller': candidate['caller'],
                    'reference_caller': analysis['reference_caller'],
                    'candidate_info': candidate,
                    'priority': 'high',  # 新增指纹检测优先级高
                    'validation_id': f"new_fp_{orm_code}_{candidate['caller']}"
                }
                llm_candidates.append(llm_candidate)
                type_counts['new_fingerprint'] += 1
            
            # 添加缺漏候选项 - 全量处理
            for candidate in analysis['missing_candidates']:
                if limit_per_type is not None and type_counts['missing'] >= limit_per_type:
                    break
                
                llm_candidate = {
                    'validation_type': 'missing',
                    'orm_code': orm_code,
                    'orm_code_content': orm_code_content,
                    'target_caller': candidate['caller'],
                    'reference_caller': analysis['reference_caller'],
                    'candidate_info': candidate,
                    'priority': 'medium',  # 缺漏检测优先级中等
                    'validation_id': f"missing_{orm_code}_{candidate['caller']}"
                }
                llm_candidates.append(llm_candidate)
                type_counts['missing'] += 1
        
        if limit_per_type is None:
            self.logger.info(f"生成全量LLM验证候选项: 冗余={type_counts['redundant']}, "
                            f"新增指纹={type_counts['new_fingerprint']}, 缺漏={type_counts['missing']}, "
                            f"总计={len(llm_candidates)}")
        else:
            self.logger.info(f"生成LLM验证候选项: 冗余={type_counts['redundant']}, "
                            f"新增指纹={type_counts['new_fingerprint']}, 缺漏={type_counts['missing']}")
        
        return llm_candidates

    def generate_reports(self, output_dir: str = "."):
        """
        生成分析报告文件
        
        Args:
            output_dir: 输出目录
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. 执行完整分析
        self.logger.info("开始执行指纹差异分析...")
        analysis_results = self.analyze_orm_fingerprint_differences()
        
        # 2. 生成指纹差异分析报告
        analysis_file = os.path.join(output_dir, "orm_fingerprint_analysis.json")
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        self.logger.info(f"指纹差异分析报告已保存到: {analysis_file}")
        
        # 3. 生成参考集合报告
        reference_file = os.path.join(output_dir, "reference_sets.json")
        with open(reference_file, 'w', encoding='utf-8') as f:
            # 转换set为list以便JSON序列化
            serializable_refs = {}
            for orm_code, ref_info in self.reference_sets.items():
                serializable_ref = ref_info.copy()
                # 转换顶层指纹集合
                serializable_ref['fingerprints'] = list(ref_info.get('fingerprints', []))
                # 深度转换 all_caller_stats 内部的 set
                caller_stats = serializable_ref.get('all_caller_stats', {})
                for caller, stats in caller_stats.items():
                    if isinstance(stats.get('fingerprints'), set):
                        stats['fingerprints'] = list(stats['fingerprints'])
                serializable_refs[orm_code] = serializable_ref
            json.dump(serializable_refs, f, ensure_ascii=False, indent=2)
        self.logger.info(f"参考集合报告已保存到: {reference_file}")
        
        # 4. 生成LLM验证候选项 - 全量处理模式
        self.logger.info("生成全量LLM验证候选项...")
        llm_candidates = self.generate_llm_validation_candidates(limit_per_type=None)  # 无限制全量处理
        candidates_file = os.path.join(output_dir, "llm_validation_candidates.json")
        with open(candidates_file, 'w', encoding='utf-8') as f:
            json.dump(llm_candidates, f, ensure_ascii=False, indent=2)
        self.logger.info(f"全量LLM验证候选项已保存到: {candidates_file}")
        
        # 5. 生成摘要统计
        summary = self._generate_analysis_summary(analysis_results, llm_candidates)
        summary_file = os.path.join(output_dir, "analysis_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        self.logger.info(f"分析摘要已保存到: {summary_file}")
        
        return {
            'analysis_file': analysis_file,
            'reference_file': reference_file,
            'candidates_file': candidates_file,
            'summary_file': summary_file,
            'summary': summary
        }
    
    def _generate_analysis_summary(self, analysis_results: Dict[str, Any], 
                                 llm_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成分析摘要
        
        Args:
            analysis_results: 分析结果
            llm_candidates: LLM候选项
            
        Returns:
            Dict: 摘要统计
        """
        total_orm_codes = len(analysis_results)
        total_redundant_candidates = sum(len(r['redundant_candidates']) for r in analysis_results.values())
        total_missing_candidates = sum(len(r['missing_candidates']) for r in analysis_results.values())
        total_new_fp_candidates = sum(len(r['new_fingerprint_candidates']) for r in analysis_results.values())
        
        # 按验证类型统计LLM候选项
        llm_type_counts = Counter(c['validation_type'] for c in llm_candidates)
        
        summary = {
            'analysis_timestamp': datetime.now().isoformat(),
            'total_orm_codes_analyzed': total_orm_codes,
            'total_candidates': {
                'redundant': total_redundant_candidates,
                'missing': total_missing_candidates,
                'new_fingerprint': total_new_fp_candidates,
                'total': total_redundant_candidates + total_missing_candidates + total_new_fp_candidates
            },
            'llm_validation_queue': {
                'redundant': llm_type_counts.get('redundant', 0),
                'missing': llm_type_counts.get('missing', 0),
                'new_fingerprint': llm_type_counts.get('new_fingerprint', 0),
                'total': len(llm_candidates)
            },
            'orm_distribution': {
                'with_redundant_candidates': len([r for r in analysis_results.values() if r['redundant_candidates']]),
                'with_missing_candidates': len([r for r in analysis_results.values() if r['missing_candidates']]),
                'with_new_fp_candidates': len([r for r in analysis_results.values() if r['new_fingerprint_candidates']]),
            }
        }
        
        return summary
    
    # 保留原有方法以确保向后兼容
    def identify_redundant_sql(self) -> Dict[str, List[Dict]]:
        """
        保留原有接口，但使用新逻辑
        """
        if not self.analysis_results:
            self.analyze_orm_fingerprint_differences()
        
        # 转换为原有格式
        redundant_info = {}
        for orm_code, analysis in self.analysis_results.items():
            if analysis['redundant_candidates']:
                redundant_info[orm_code] = analysis['redundant_candidates']
        
        return redundant_info
    
    def mark_redundant_sql_in_dataset(self, dataset: List[Dict]) -> List[Dict]:
        """
        在数据集中标记冗余SQL - 使用新的冗余检测逻辑
        
        Args:
            dataset: 原始数据集
            
        Returns:
            List[Dict]: 标记后的数据集
        """
        # 执行新的冗余分析
        if not self.analysis_results:
            self.analyze_orm_fingerprint_differences()
        
        # 创建指纹到冗余标记的映射
        redundant_fingerprints = {}
        for orm_code, analysis in self.analysis_results.items():
            for candidate in analysis['redundant_candidates']:
                caller = candidate['caller']
                for fingerprint in candidate['redundant_fingerprints']:
                    key = f"{orm_code}:{caller}:{fingerprint}"
                redundant_fingerprints[key] = True
        
        # 标记数据集
        marked_dataset = []
        for record in dataset:
            marked_record = record.copy()
            
            orm_code = record.get('orm_code', '')
            caller = record.get('caller', 'unknown_caller')
            sql_statements = record.get('sql_statement_list', [])

            # 保持"<NO SQL GENERATE>"为字符串类型
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
        if not self.analysis_results:
            self.analyze_orm_fingerprint_differences()
        
        total_orm_codes = len(self.orm_data)
        total_callers = sum(len(callers) for callers in self.orm_data.values())
        total_sql_records = sum(
            len(records) 
            for callers in self.orm_data.values() 
            for records in callers.values()
        )
        
        # 计算详细分析统计
        orm_with_redundant_candidates = len([
            orm_code for orm_code, analysis in self.analysis_results.items()
            if analysis.get('redundant_candidates', [])
        ])
        
        orm_with_missing_candidates = len([
            orm_code for orm_code, analysis in self.analysis_results.items()
            if analysis.get('missing_candidates', [])
        ])
        
        orm_with_new_fp_candidates = len([
            orm_code for orm_code, analysis in self.analysis_results.items()
            if analysis.get('new_fingerprint_candidates', [])
        ])
        
        total_redundant_candidates = sum(
            len(analysis.get('redundant_candidates', []))
            for analysis in self.analysis_results.values()
        )
        
        total_missing_candidates = sum(
            len(analysis.get('missing_candidates', []))
            for analysis in self.analysis_results.values()
        )
        
        total_new_fp_candidates = sum(
            len(analysis.get('new_fingerprint_candidates', []))
            for analysis in self.analysis_results.values()
        )
        
        return {
            # 基本统计信息
            'total_orm_codes': total_orm_codes,
            'total_callers': total_callers,
            'total_sql_records': total_sql_records,
            'orm_codes_analyzed': len(self.analysis_results),
            'reference_sets_created': len(self.reference_sets),
            'analysis_completed': bool(self.analysis_results),
            'average_callers_per_orm': total_callers / total_orm_codes if total_orm_codes > 0 else 0,
            'average_sql_per_orm': total_sql_records / total_orm_codes if total_orm_codes > 0 else 0,
            
            # 详细分析统计
            'detailed_analysis': {
                'orm_with_redundant_candidates': orm_with_redundant_candidates,
                'orm_with_missing_candidates': orm_with_missing_candidates,
                'orm_with_new_fp_candidates': orm_with_new_fp_candidates,
                'total_redundant_candidates': total_redundant_candidates,
                'total_missing_candidates': total_missing_candidates,
                'total_new_fp_candidates': total_new_fp_candidates,
                'total_candidates': total_redundant_candidates + total_missing_candidates + total_new_fp_candidates
            }
        } 