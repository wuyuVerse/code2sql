"""
Code2SQL数据集读取器

用于读取和解析claude_output文件夹中的JSON数据，
为后续的数据处理和清洗workflow提供基础功能。
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Iterator, Tuple
from dataclasses import dataclass, field
import logging
from datetime import datetime
import glob

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CodeMetaData:
    """代码元数据结构"""
    code_file: str
    code_start_line: int
    code_end_line: int
    code_key: str
    code_value: str
    code_label: Optional[int] = None
    code_type: Optional[int] = None
    code_version: Optional[str] = None


@dataclass
class SqlScenario:
    """SQL场景结构"""
    condition: str
    sql: str
    when: Optional[str] = None


@dataclass
class ComplexSqlStatement:
    """复杂SQL语句结构"""
    description: str
    scenarios: List[Union[SqlScenario, Dict[str, Any]]]
    parameters: Optional[Dict[str, Any]] = None
    execution_condition: Optional[str] = None


@dataclass
class FunctionRecord:
    """函数记录数据结构"""
    function_name: str
    orm_code: str
    caller: str
    sql_statement_list: List[Union[str, Dict[str, Any]]]
    sql_types: List[str]
    code_meta_data: List[CodeMetaData]
    sql_pattern_cnt: int
    source_file: str
    
    # 解析后的字段
    parsed_sql_statements: List[Union[str, ComplexSqlStatement]] = field(default_factory=list)
    
    def __post_init__(self):
        """后处理，解析复杂的SQL语句结构"""
        self.parsed_sql_statements = []
        for stmt in self.sql_statement_list:
            if isinstance(stmt, str):
                self.parsed_sql_statements.append(stmt)
            elif isinstance(stmt, dict):
                # 解析复杂的SQL语句结构
                scenarios = []
                if 'scenarios' in stmt:
                    for scenario in stmt['scenarios']:
                        if isinstance(scenario, dict):
                            scenarios.append(SqlScenario(**scenario))
                        else:
                            scenarios.append(scenario)
                
                complex_stmt = ComplexSqlStatement(
                    description=stmt.get('description', ''),
                    scenarios=scenarios,
                    parameters=stmt.get('parameters'),
                    execution_condition=stmt.get('execution_condition')
                )
                self.parsed_sql_statements.append(complex_stmt)


class DataReader:
    """Code2SQL数据集读取器"""
    
    def __init__(self, data_dir: Union[str, Path] = "datasets/claude_output"):
        """
        初始化数据读取器
        
        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = Path(data_dir)
        self.records: List[FunctionRecord] = []
        self.file_stats: Dict[str, Dict[str, Any]] = {}
        
        if not self.data_dir.exists():
            raise FileNotFoundError(f"数据目录不存在: {self.data_dir}")
    
    def get_file_list(self, pattern: str = "*.json") -> List[Path]:
        """
        获取数据文件列表
        
        Args:
            pattern: 文件匹配模式
            
        Returns:
            文件路径列表
        """
        files = list(self.data_dir.glob(pattern))
        logger.info(f"找到 {len(files)} 个JSON文件")
        return sorted(files)
    
    def read_single_file(self, file_path: Union[str, Path]) -> List[FunctionRecord]:
        """
        读取单个JSON文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            函数记录列表
        """
        file_path = Path(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                logger.warning(f"文件 {file_path} 不是预期的列表格式")
                return []
            
            records = []
            for item in data:
                try:
                    # 解析code_meta_data
                    code_meta_list = []
                    for meta in item.get('code_meta_data', []):
                        code_meta_list.append(CodeMetaData(**meta))
                    
                    # 创建FunctionRecord
                    record = FunctionRecord(
                        function_name=item.get('function_name', ''),
                        orm_code=item.get('orm_code', ''),
                        caller=item.get('caller', ''),
                        sql_statement_list=item.get('sql_statement_list', []),
                        sql_types=item.get('sql_types', []),
                        code_meta_data=code_meta_list,
                        sql_pattern_cnt=item.get('sql_pattern_cnt', 0),
                        source_file=item.get('source_file', str(file_path))
                    )
                    records.append(record)
                    
                except Exception as e:
                    logger.error(f"解析记录时出错: {e}")
                    logger.error(f"问题记录: {item}")
                    continue
            
            # 统计文件信息
            self.file_stats[str(file_path)] = {
                'total_records': len(records),
                'file_size_mb': file_path.stat().st_size / (1024 * 1024),
                'has_sql_records': len([r for r in records if r.sql_statement_list]),
                'avg_sql_per_record': sum(len(r.sql_statement_list) for r in records) / len(records) if records else 0
            }
            
            logger.info(f"成功读取文件 {file_path}: {len(records)} 条记录")
            return records
            
        except Exception as e:
            logger.error(f"读取文件 {file_path} 时出错: {e}")
            return []
    
    def read_all_files(self, pattern: str = "*.json") -> "DataReader":
        """
        读取所有匹配的文件
        
        Args:
            pattern: 文件匹配模式
            
        Returns:
            自身，支持链式调用
        """
        files = self.get_file_list(pattern)
        self.records = []
        
        for file_path in files:
            records = self.read_single_file(file_path)
            self.records.extend(records)
        
        logger.info(f"总共读取了 {len(self.records)} 条记录")
        return self
    
    def read_files(self, file_names: List[str]) -> "DataReader":
        """
        读取指定的文件列表
        
        Args:
            file_names: 文件名列表
            
        Returns:
            自身，支持链式调用
        """
        self.records = []
        
        for file_name in file_names:
            file_path = self.data_dir / file_name
            if file_path.exists():
                records = self.read_single_file(file_path)
                self.records.extend(records)
            else:
                logger.warning(f"文件不存在: {file_path}")
        
        logger.info(f"读取了 {len(file_names)} 个文件，总共 {len(self.records)} 条记录")
        return self
    
    def filter_records(self, 
                      has_sql: Optional[bool] = None,
                      sql_types: Optional[List[str]] = None,
                      min_sql_count: Optional[int] = None,
                      function_name_contains: Optional[str] = None,
                      source_file_pattern: Optional[str] = None) -> List[FunctionRecord]:
        """
        过滤记录
        
        Args:
            has_sql: 是否包含SQL语句
            sql_types: SQL类型列表
            min_sql_count: 最小SQL语句数量
            function_name_contains: 函数名包含的字符串
            source_file_pattern: 源文件名模式
            
        Returns:
            过滤后的记录列表
        """
        filtered = self.records
        
        if has_sql is not None:
            filtered = [r for r in filtered if bool(r.sql_statement_list) == has_sql]
        
        if sql_types:
            filtered = [r for r in filtered if any(t in r.sql_types for t in sql_types)]
        
        if min_sql_count is not None:
            filtered = [r for r in filtered if len(r.sql_statement_list) >= min_sql_count]
        
        if function_name_contains:
            filtered = [r for r in filtered if function_name_contains in r.function_name]
        
        if source_file_pattern:
            import fnmatch
            filtered = [r for r in filtered if fnmatch.fnmatch(r.source_file, source_file_pattern)]
        
        logger.info(f"过滤后剩余 {len(filtered)} 条记录")
        return filtered
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据集统计信息
        
        Returns:
            统计信息字典
        """
        if not self.records:
            return {"error": "没有加载数据"}
        
        total_records = len(self.records)
        records_with_sql = [r for r in self.records if r.sql_statement_list]
        
        # SQL类型统计
        sql_type_counts = {}
        for record in self.records:
            for sql_type in record.sql_types:
                sql_type_counts[sql_type] = sql_type_counts.get(sql_type, 0) + 1
        
        # 文件统计
        file_counts = {}
        for record in self.records:
            source = record.source_file
            file_counts[source] = file_counts.get(source, 0) + 1
        
        stats = {
            "total_records": total_records,
            "records_with_sql": len(records_with_sql),
            "records_without_sql": total_records - len(records_with_sql),
            "sql_coverage_rate": len(records_with_sql) / total_records * 100,
            "avg_sql_per_record": sum(len(r.sql_statement_list) for r in self.records) / total_records,
            "total_sql_statements": sum(len(r.sql_statement_list) for r in self.records),
            "sql_type_distribution": dict(sorted(sql_type_counts.items(), key=lambda x: x[1], reverse=True)),
            "top_10_files_by_records": dict(sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "file_stats": self.file_stats,
            "generated_at": datetime.now().isoformat()
        }
        
        return stats
    
    def get_records_by_project(self, project_name: str) -> List[FunctionRecord]:
        """
        根据项目名获取记录
        
        Args:
            project_name: 项目名（如 "IVC", "KAMP" 等）
            
        Returns:
            该项目的记录列表
        """
        return [r for r in self.records if project_name in r.function_name]
    
    def get_unique_sql_patterns(self) -> List[str]:
        """
        获取唯一的SQL模式
        
        Returns:
            SQL模式列表
        """
        patterns = set()
        for record in self.records:
            for stmt in record.sql_statement_list:
                if isinstance(stmt, str):
                    patterns.add(stmt)
                elif isinstance(stmt, dict) and 'description' in stmt:
                    patterns.add(stmt['description'])
        
        return sorted(list(patterns))
    
    def export_to_format(self, output_path: Union[str, Path], format_type: str = "json") -> None:
        """
        导出数据到指定格式
        
        Args:
            output_path: 输出文件路径
            format_type: 格式类型 ("json", "csv", "jsonl")
        """
        output_path = Path(output_path)
        
        if format_type == "json":
            # 将记录转换为可序列化的字典
            data = []
            for record in self.records:
                record_dict = {
                    "function_name": record.function_name,
                    "orm_code": record.orm_code,
                    "caller": record.caller,
                    "sql_statement_list": record.sql_statement_list,
                    "sql_types": record.sql_types,
                    "sql_pattern_cnt": record.sql_pattern_cnt,
                    "source_file": record.source_file
                }
                data.append(record_dict)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        elif format_type == "jsonl":
            with open(output_path, 'w', encoding='utf-8') as f:
                for record in self.records:
                    record_dict = {
                        "function_name": record.function_name,
                        "orm_code": record.orm_code,
                        "caller": record.caller,
                        "sql_statement_list": record.sql_statement_list,
                        "sql_types": record.sql_types,
                        "sql_pattern_cnt": record.sql_pattern_cnt,
                        "source_file": record.source_file
                    }
                    f.write(json.dumps(record_dict, ensure_ascii=False) + '\n')
                    
        elif format_type == "csv":
            import csv
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(['function_name', 'orm_code', 'caller', 'sql_count', 
                               'sql_types', 'sql_pattern_cnt', 'source_file'])
                
                # 写入数据
                for record in self.records:
                    writer.writerow([
                        record.function_name,
                        record.orm_code[:200] + '...' if len(record.orm_code) > 200 else record.orm_code,
                        record.caller[:200] + '...' if len(record.caller) > 200 else record.caller,
                        len(record.sql_statement_list),
                        '|'.join(record.sql_types),
                        record.sql_pattern_cnt,
                        record.source_file
                    ])
        else:
            raise ValueError(f"不支持的格式类型: {format_type}")
        
        logger.info(f"数据已导出到 {output_path}")
    
    def __iter__(self) -> Iterator[FunctionRecord]:
        """迭代器支持"""
        return iter(self.records)
    
    def __len__(self) -> int:
        """获取记录数量"""
        return len(self.records)
    
    def __getitem__(self, index: int) -> FunctionRecord:
        """索引访问"""
        return self.records[index]

    def extract_by_keywords(self, keywords: List[str], output_dir: str = "extracted_data", step_name: str = "keyword_extraction") -> Dict[str, Any]:
        """
        根据关键词提取数据
        
        Args:
            keywords: 目标关键词列表
            output_dir: 输出根目录
            step_name: 处理步骤名称，用于创建子文件夹
            
        Returns:
            提取结果统计
        """
        import json
        from pathlib import Path
        from datetime import datetime
        
        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        step_dir = f"{step_name}_{timestamp}"
        output_path = Path(output_dir) / step_dir
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"开始根据关键词提取数据，目标关键词: {len(keywords)}个")
        
        # 如果还没有读取数据，则读取所有文件
        if not self.records:
            logger.info("数据未加载，正在读取所有JSON文件...")
            self.read_all_files()
        
        total_records = len(self.records)
        logger.info(f"总共处理 {total_records:,} 条记录")
        
        # 提取匹配的记录
        matched_records = []
        keyword_stats = {keyword: 0 for keyword in keywords}
        file_stats = {}
        
        for i, record in enumerate(self.records):
            if i % 5000 == 0 and i > 0:
                logger.info(f"处理进度: {i:,}/{total_records:,} ({i/total_records*100:.1f}%)")
            
            # 检查记录中是否包含目标关键词
            matched_keywords = []
            
            # 检查code_meta_data中的code_value
            for meta in record.code_meta_data:
                code_value = meta.code_value
                for keyword in keywords:
                    if keyword in code_value:
                        if keyword not in matched_keywords:
                            matched_keywords.append(keyword)
            
            # 也检查orm_code中是否包含关键词（作为补充）
            for keyword in keywords:
                if keyword in record.orm_code:
                    if keyword not in matched_keywords:
                        matched_keywords.append(keyword)
            
            if matched_keywords:
                # 构建记录字典
                record_dict = {
                    'function_name': record.function_name,
                    'orm_code': record.orm_code,
                    'caller': record.caller,
                    'sql_statement_list': record.sql_statement_list,
                    'sql_types': record.sql_types,
                    'code_meta_data': [
                        {
                            'code_file': meta.code_file,
                            'code_start_line': meta.code_start_line,
                            'code_end_line': meta.code_end_line,
                            'code_key': meta.code_key,
                            'code_value': meta.code_value,
                            'code_label': meta.code_label,
                            'code_type': meta.code_type,
                            'code_version': meta.code_version
                        } for meta in record.code_meta_data
                    ],
                    'sql_pattern_cnt': record.sql_pattern_cnt,
                    'source_file': record.source_file,
                    'matched_keywords': matched_keywords
                }
                matched_records.append(record_dict)
                
                # 统计关键词频率
                for keyword in matched_keywords:
                    keyword_stats[keyword] += 1
                
                # 统计来源文件
                source_file = Path(record.source_file).name
                if source_file not in file_stats:
                    file_stats[source_file] = 0
                file_stats[source_file] += 1
        
        logger.info(f"关键词匹配完成，找到 {len(matched_records):,} 条匹配记录")
        
        # 保存主数据文件
        output_file = output_path / "keyword_matched_records.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(matched_records, f, ensure_ascii=False, indent=2)
        logger.info(f"主数据文件已保存: {output_file}")
        
        # 生成按关键词分类的文件
        keyword_dir = output_path / "by_keyword"
        keyword_dir.mkdir(exist_ok=True)
        
        for keyword in keywords:
            keyword_records = []
            for record in matched_records:
                if keyword in record.get('matched_keywords', []):
                    keyword_records.append(record)
            
            if keyword_records:
                keyword_file = keyword_dir / f"{keyword}_records.json"
                with open(keyword_file, 'w', encoding='utf-8') as f:
                    json.dump(keyword_records, f, ensure_ascii=False, indent=2)
                logger.info(f"{keyword}: {len(keyword_records)} 条记录 -> {keyword_file}")
        
        # 生成统计报告
        stats = {
            'total_records_processed': total_records,
            'matched_records': len(matched_records),
            'match_rate': len(matched_records) / total_records * 100 if total_records > 0 else 0,
            'keyword_frequency': dict(sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True)),
            'source_file_distribution': dict(sorted(file_stats.items(), key=lambda x: x[1], reverse=True)),
            'target_keywords': keywords,
            'output_directory': str(output_path),
            'generated_at': datetime.now().isoformat()
        }
        
        stats_file = output_path / "extraction_statistics.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"统计报告已保存: {stats_file}")
        
        return stats

    def extract_gorm_keywords(self, output_dir: str = "extracted_data") -> Dict[str, Any]:
        """
        提取包含GORM相关关键词的数据
        
        Args:
            output_dir: 输出根目录
            
        Returns:
            提取结果统计
        """
        gorm_keywords = [
            "Preload",
            "Transaction", 
            "Scopes",
            "FindInBatches",
            "FirstOrInit",
            "Association",
            "Locking",
            "Pluck",
            "Callbacks",
            "AutoMigrate",
            "ForeignKey",
            "References",
            "NamedQuery",
            "Hooks",
            "NamedParameters",
            "save",
            "createorupdate"
        ]
        
        logger.info(f"使用预定义的GORM关键词列表: {gorm_keywords}")
        return self.extract_by_keywords(gorm_keywords, output_dir, "gorm_keywords")


class DataSampler:
    """数据采样器"""
    
    def __init__(self, reader: DataReader):
        self.reader = reader
    
    def random_sample(self, n: int, seed: Optional[int] = None) -> List[FunctionRecord]:
        """
        随机采样
        
        Args:
            n: 采样数量
            seed: 随机种子
            
        Returns:
            采样记录列表
        """
        import random
        if seed is not None:
            random.seed(seed)
        
        if n >= len(self.reader.records):
            return self.reader.records.copy()
        
        return random.sample(self.reader.records, n)
    
    def stratified_sample(self, n: int, by_sql_type: bool = True) -> List[FunctionRecord]:
        """
        分层采样
        
        Args:
            n: 总采样数量
            by_sql_type: 是否按SQL类型分层
            
        Returns:
            采样记录列表
        """
        if by_sql_type:
            # 按SQL类型分组
            groups = {}
            for record in self.reader.records:
                key = tuple(sorted(record.sql_types)) if record.sql_types else "no_sql"
                if key not in groups:
                    groups[key] = []
                groups[key].append(record)
            
            # 按比例采样
            samples = []
            total_records = len(self.reader.records)
            
            for group_key, group_records in groups.items():
                group_size = len(group_records)
                sample_size = max(1, int(n * group_size / total_records))
                
                if sample_size >= group_size:
                    samples.extend(group_records)
                else:
                    import random
                    samples.extend(random.sample(group_records, sample_size))
            
            # 如果采样数量不足，随机补充
            if len(samples) < n:
                remaining = [r for r in self.reader.records if r not in samples]
                if remaining:
                    import random
                    additional = min(n - len(samples), len(remaining))
                    samples.extend(random.sample(remaining, additional))
            
            return samples[:n]
        
        return self.random_sample(n)


# 使用示例和测试函数
def main():
    """示例用法"""
    
    # 创建数据读取器
    reader = DataReader("datasets/claude_output")
    
    # 读取所有数据
    reader.read_all_files()
    
    # 获取统计信息
    stats = reader.get_statistics()
    print("数据集统计信息:")
    print(f"总记录数: {stats['total_records']}")
    print(f"包含SQL的记录: {stats['records_with_sql']}")
    print(f"SQL覆盖率: {stats['sql_coverage_rate']:.2f}%")
    
    # 过滤数据
    sql_records = reader.filter_records(has_sql=True, min_sql_count=1)
    print(f"包含SQL的记录数: {len(sql_records)}")
    
    # 获取项目记录
    ivc_records = reader.get_records_by_project("IVC")
    print(f"IVC项目记录数: {len(ivc_records)}")
    
    # 数据采样
    sampler = DataSampler(reader)
    sample = sampler.random_sample(100)
    print(f"随机采样100条记录: {len(sample)}")


if __name__ == "__main__":
    main() 