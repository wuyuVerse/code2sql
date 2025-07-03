"""
数据分析器

提供高级的数据分析和可视化功能，
用于深入理解Code2SQL数据集的特征和模式。
"""

from typing import Dict, List, Any, Tuple, Optional
import re
from collections import Counter, defaultdict
import statistics
from pathlib import Path
import json


class DataAnalyzer:
    """数据分析器"""
    
    def __init__(self, records: List[Any]):
        """
        初始化分析器
        
        Args:
            records: FunctionRecord列表
        """
        self.records = records
    
    def analyze_function_patterns(self) -> Dict[str, Any]:
        """分析函数名模式"""
        function_names = [record.function_name for record in self.records]
        
        # 提取函数名（最后一部分）
        pure_function_names = []
        for func_name in function_names:
            if ':' in func_name:
                pure_function_names.append(func_name.split(':')[-1])
            else:
                pure_function_names.append(func_name.split('/')[-1])
        
        # 分析命名模式
        patterns = {
            'camelCase': 0,
            'PascalCase': 0,
            'snake_case': 0,
            'kebab-case': 0,
            'mixed': 0
        }
        
        for name in pure_function_names:
            if re.match(r'^[a-z][a-zA-Z0-9]*$', name):
                patterns['camelCase'] += 1
            elif re.match(r'^[A-Z][a-zA-Z0-9]*$', name):
                patterns['PascalCase'] += 1
            elif '_' in name and not '-' in name:
                patterns['snake_case'] += 1
            elif '-' in name and not '_' in name:
                patterns['kebab-case'] += 1
            else:
                patterns['mixed'] += 1
        
        # 常见前缀后缀
        prefixes = Counter()
        suffixes = Counter()
        
        for name in pure_function_names:
            if len(name) > 3:
                prefixes[name[:3]] += 1
                suffixes[name[-3:]] += 1
        
        return {
            'total_functions': len(pure_function_names),
            'naming_patterns': patterns,
            'top_prefixes': dict(prefixes.most_common(10)),
            'top_suffixes': dict(suffixes.most_common(10)),
            'average_name_length': statistics.mean(len(name) for name in pure_function_names),
            'unique_names': len(set(pure_function_names))
        }
    
    def analyze_sql_complexity(self) -> Dict[str, Any]:
        """分析SQL复杂度"""
        sql_stats = {
            'total_functions': len(self.records),
            'functions_with_sql': 0,
            'total_sql_statements': 0,
            'simple_sql_count': 0,
            'complex_sql_count': 0,
            'sql_length_stats': [],
            'keyword_frequency': Counter(),
            'table_patterns': Counter(),
            'join_patterns': Counter()
        }
        
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'JOIN', 'LEFT JOIN', 
                       'RIGHT JOIN', 'INNER JOIN', 'WHERE', 'GROUP BY', 'ORDER BY', 
                       'HAVING', 'UNION', 'SUBQUERY']
        
        for record in self.records:
            if record.sql_statement_list:
                sql_stats['functions_with_sql'] += 1
                sql_stats['total_sql_statements'] += len(record.sql_statement_list)
                
                for stmt in record.sql_statement_list:
                    if isinstance(stmt, str):
                        sql_text = stmt.upper()
                        sql_stats['sql_length_stats'].append(len(stmt))
                        
                        # 关键词频率
                        for keyword in sql_keywords:
                            if keyword in sql_text:
                                sql_stats['keyword_frequency'][keyword] += 1
                        
                        # 表名模式（简单提取）
                        from_matches = re.findall(r'FROM\s+(\w+)', sql_text)
                        join_matches = re.findall(r'JOIN\s+(\w+)', sql_text)
                        
                        for table in from_matches + join_matches:
                            sql_stats['table_patterns'][table] += 1
                        
                        # JOIN类型统计
                        if 'LEFT JOIN' in sql_text:
                            sql_stats['join_patterns']['LEFT JOIN'] += 1
                        elif 'RIGHT JOIN' in sql_text:
                            sql_stats['join_patterns']['RIGHT JOIN'] += 1
                        elif 'INNER JOIN' in sql_text:
                            sql_stats['join_patterns']['INNER JOIN'] += 1
                        elif 'JOIN' in sql_text:
                            sql_stats['join_patterns']['SIMPLE JOIN'] += 1
                        
                        # 复杂度分类
                        complexity_indicators = ['JOIN', 'SUBQUERY', 'UNION', 'GROUP BY', 'HAVING']
                        if any(indicator in sql_text for indicator in complexity_indicators):
                            sql_stats['complex_sql_count'] += 1
                        else:
                            sql_stats['simple_sql_count'] += 1
                    
                    elif isinstance(stmt, dict):
                        # 复杂SQL对象
                        sql_stats['complex_sql_count'] += 1
        
        # 计算统计值
        if sql_stats['sql_length_stats']:
            sql_stats['avg_sql_length'] = statistics.mean(sql_stats['sql_length_stats'])
            sql_stats['median_sql_length'] = statistics.median(sql_stats['sql_length_stats'])
            sql_stats['max_sql_length'] = max(sql_stats['sql_length_stats'])
            sql_stats['min_sql_length'] = min(sql_stats['sql_length_stats'])
        
        return sql_stats
    
    def analyze_project_distribution(self) -> Dict[str, Any]:
        """分析项目分布"""
        project_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'total_functions': 0,
            'functions_with_sql': 0,
            'total_sql_statements': 0,
            'sql_types': Counter(),
            'avg_sql_per_function': 0.0
        })
        
        for record in self.records:
            # 从function_name中提取项目名
            parts = record.function_name.split('/')
            project = 'unknown'
            
            if len(parts) > 6:
                project_part = parts[6]
                if '__' in project_part:
                    project = project_part.split('__')[0]
                else:
                    project = project_part
            
            stats = project_stats[project]
            stats['total_functions'] += 1
            
            if record.sql_statement_list:
                stats['functions_with_sql'] += 1
                stats['total_sql_statements'] += len(record.sql_statement_list)
                
                for sql_type in record.sql_types:
                    stats['sql_types'][sql_type] += 1
        
        # 计算平均值
        for project, stats in project_stats.items():
            if stats['total_functions'] > 0:
                stats['avg_sql_per_function'] = stats['total_sql_statements'] / stats['total_functions']
                stats['sql_coverage'] = stats['functions_with_sql'] / stats['total_functions'] * 100
        
        return dict(project_stats)
    
    def analyze_code_patterns(self) -> Dict[str, Any]:
        """分析代码模式"""
        code_stats = {
            'total_functions': len(self.records),
            'avg_code_length': 0,
            'functions_with_caller': 0,
            'language_indicators': Counter(),
            'orm_patterns': Counter(),
            'error_handling_patterns': Counter()
        }
        
        code_lengths = []
        orm_keywords = ['gorm', 'db.', 'Query', 'Exec', 'Raw', 'Model', 'Table']
        error_keywords = ['error', 'err', 'Error', 'panic', 'recover']
        
        for record in self.records:
            # 代码长度统计
            code_lengths.append(len(record.orm_code))
            
            if record.caller:
                code_stats['functions_with_caller'] += 1
            
            # ORM模式识别
            code_text = record.orm_code
            for keyword in orm_keywords:
                if keyword in code_text:
                    code_stats['orm_patterns'][keyword] += 1
            
            # 错误处理模式
            for keyword in error_keywords:
                if keyword in code_text:
                    code_stats['error_handling_patterns'][keyword] += 1
            
            # 语言特征识别
            if 'func ' in code_text and 'import' not in code_text:
                code_stats['language_indicators']['Go'] += 1
            elif 'def ' in code_text:
                code_stats['language_indicators']['Python'] += 1
            elif 'function' in code_text or '=>' in code_text:
                code_stats['language_indicators']['JavaScript'] += 1
        
        if code_lengths:
            code_stats['avg_code_length'] = statistics.mean(code_lengths)
            code_stats['median_code_length'] = statistics.median(code_lengths)
        
        return code_stats
    
    def generate_quality_report(self) -> Dict[str, Any]:
        """生成数据质量报告"""
        quality_metrics = {
            'completeness': {},
            'consistency': {},
            'validity': {},
            'accuracy': {}
        }
        
        total_records = len(self.records)
        
        # 完整性检查
        fields_completeness = {
            'function_name': sum(1 for r in self.records if r.function_name),
            'orm_code': sum(1 for r in self.records if r.orm_code),
            'sql_statement_list': sum(1 for r in self.records if r.sql_statement_list),
            'sql_types': sum(1 for r in self.records if r.sql_types),
            'code_meta_data': sum(1 for r in self.records if r.code_meta_data),
            'source_file': sum(1 for r in self.records if r.source_file)
        }
        
        quality_metrics['completeness'] = {
            field: (count / total_records * 100) for field, count in fields_completeness.items()
        }
        
        # 一致性检查
        sql_type_consistency = 0
        for record in self.records:
            if record.sql_statement_list and record.sql_types:
                # 检查SQL类型和语句数量的一致性
                if len(record.sql_types) > 0:
                    sql_type_consistency += 1
        
        quality_metrics['consistency']['sql_type_alignment'] = (
            sql_type_consistency / total_records * 100 if total_records > 0 else 0
        )
        
        # 有效性检查
        valid_function_names = sum(
            1 for r in self.records 
            if r.function_name and ':' in r.function_name and '/' in r.function_name
        )
        
        quality_metrics['validity']['function_name_format'] = (
            valid_function_names / total_records * 100 if total_records > 0 else 0
        )
        
        return quality_metrics
    
    def export_analysis_report(self, output_path: str) -> None:
        """导出完整的分析报告"""
        report = {
            'metadata': {
                'total_records': len(self.records),
                'analysis_timestamp': str(Path().resolve()),
            },
            'function_patterns': self.analyze_function_patterns(),
            'sql_complexity': self.analyze_sql_complexity(),
            'project_distribution': self.analyze_project_distribution(),
            'code_patterns': self.analyze_code_patterns(),
            'quality_report': self.generate_quality_report()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"分析报告已导出到: {output_path}")


def analyze_sample_data():
    """分析示例数据"""
    print("数据分析示例")
    print("=" * 50)
    
    # 这里需要导入DataReader，但为了避免导入问题，我们创建一个简化版本
    # 实际使用时应该从data_reader模块导入
    
    # 模拟一些示例数据进行演示
    from dataclasses import dataclass
    from typing import List, Dict, Any
    
    @dataclass
    class MockRecord:
        function_name: str
        orm_code: str
        caller: str
        sql_statement_list: List[Any]
        sql_types: List[str]
        code_meta_data: List[Any]
        sql_pattern_cnt: int
        source_file: str
    
    # 创建示例数据
    sample_records = [
        MockRecord(
            function_name="/path/to/IVC__ivc-event-alarm/repo.go:10:20:GetAlarms",
            orm_code="func GetAlarms() { db.Query('SELECT * FROM alarms') }",
            caller="handler.go",
            sql_statement_list=["SELECT * FROM alarms WHERE status = ?"],
            sql_types=["SELECT"],
            code_meta_data=[],
            sql_pattern_cnt=1,
            source_file="test.json"
        ),
        MockRecord(
            function_name="/path/to/KAMP__camp-server/service.go:15:30:CreateUser",
            orm_code="func CreateUser() { db.Create(&user) }",
            caller="api.go",
            sql_statement_list=["INSERT INTO users (name, email) VALUES (?, ?)"],
            sql_types=["INSERT"],
            code_meta_data=[],
            sql_pattern_cnt=1,
            source_file="test.json"
        )
    ]
    
    analyzer = DataAnalyzer(sample_records)
    
    # 执行各种分析
    print("1. 函数模式分析:")
    func_patterns = analyzer.analyze_function_patterns()
    print(f"   总函数数: {func_patterns['total_functions']}")
    print(f"   命名模式: {func_patterns['naming_patterns']}")
    
    print("\n2. SQL复杂度分析:")
    sql_complexity = analyzer.analyze_sql_complexity()
    print(f"   包含SQL的函数: {sql_complexity['functions_with_sql']}")
    print(f"   关键词频率: {dict(sql_complexity['keyword_frequency'])}")
    
    print("\n3. 项目分布分析:")
    project_dist = analyzer.analyze_project_distribution()
    for project, stats in project_dist.items():
        print(f"   {project}: {stats['total_functions']} 个函数")
    
    print("\n4. 数据质量报告:")
    quality = analyzer.generate_quality_report()
    print(f"   完整性: {quality['completeness']}")


if __name__ == "__main__":
    analyze_sample_data() 