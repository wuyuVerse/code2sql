#!/usr/bin/env python3
"""
评估报告生成器

分析模型评估结果并生成详细的可视化报告
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import argparse
from collections import defaultdict, Counter
import re

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EvaluationReportGenerator:
    """评估报告生成器"""
    
    def __init__(self, results_file: str, output_dir: str = "evaluation_reports"):
        """
        初始化报告生成器
        
        Args:
            results_file: 评估结果文件路径
            output_dir: 报告输出目录
        """
        self.results_file = Path(results_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载评估结果
        self.evaluation_data = self.load_evaluation_results()
        self.config = self.evaluation_data.get('config', {})
        self.statistics = self.evaluation_data.get('statistics', {})
        self.detailed_results = self.evaluation_data.get('detailed_results', [])
        
        logger.info(f"已加载评估结果: {self.results_file}")
        logger.info(f"报告输出目录: {self.output_dir}")
    
    def load_evaluation_results(self) -> Dict:
        """加载评估结果"""
        if not self.results_file.exists():
            raise FileNotFoundError(f"评估结果文件不存在: {self.results_file}")
        
        with open(self.results_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def analyze_sql_patterns(self) -> Dict:
        """分析SQL模式"""
        logger.info("开始分析SQL模式...")
        
        sql_type_stats = defaultdict(int)
        sql_complexity_stats = defaultdict(int)
        sql_length_stats = []
        common_patterns = defaultdict(int)
        error_patterns = defaultdict(int)
        
        for result in self.detailed_results:
            parsed_sql = result.get('parsed_sql', [])
            sql_evaluation = result.get('sql_evaluation', {})
            
            # 分析每个SQL
            for sql in parsed_sql:
                if not sql.strip():
                    continue
                
                # SQL类型分析
                sql_type = self.determine_sql_type(sql)
                sql_type_stats[sql_type] += 1
                
                # SQL长度统计
                sql_length_stats.append(len(sql))
                
                # 复杂度分析
                complexity = self.analyze_sql_complexity(sql)
                sql_complexity_stats[complexity] += 1
                
                # 常见模式检测
                patterns = self.extract_sql_patterns(sql)
                for pattern in patterns:
                    common_patterns[pattern] += 1
            
            # 错误模式分析
            if result.get('parse_error'):
                error_type = self.classify_error(result['parse_error'])
                error_patterns[error_type] += 1
        
        return {
            'sql_type_distribution': dict(sql_type_stats),
            'complexity_distribution': dict(sql_complexity_stats),
            'length_statistics': {
                'avg_length': sum(sql_length_stats) / len(sql_length_stats) if sql_length_stats else 0,
                'min_length': min(sql_length_stats) if sql_length_stats else 0,
                'max_length': max(sql_length_stats) if sql_length_stats else 0,
                'total_sqls': len(sql_length_stats)
            },
            'common_patterns': dict(sorted(common_patterns.items(), key=lambda x: x[1], reverse=True)[:20]),
            'error_patterns': dict(error_patterns)
        }
    
    def determine_sql_type(self, sql: str) -> str:
        """确定SQL类型"""
        sql_clean = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        sql_clean = re.sub(r'--.*?$', '', sql_clean, flags=re.MULTILINE)
        sql_clean = sql_clean.strip().upper()
        
        if sql_clean.startswith('SELECT'):
            return 'SELECT'
        elif sql_clean.startswith('INSERT'):
            return 'INSERT'
        elif sql_clean.startswith('UPDATE'):
            return 'UPDATE'
        elif sql_clean.startswith('DELETE'):
            return 'DELETE'
        elif sql_clean.startswith(('CREATE', 'ALTER', 'DROP')):
            return 'DDL'
        else:
            return 'OTHER'
    
    def analyze_sql_complexity(self, sql: str) -> str:
        """分析SQL复杂度"""
        sql_upper = sql.upper()
        
        # 计算复杂度特征
        join_count = len(re.findall(r'\bJOIN\b', sql_upper))
        subquery_count = sql.count('(') + sql.count(')')
        where_clauses = len(re.findall(r'\bWHERE\b', sql_upper))
        having_clauses = len(re.findall(r'\bHAVING\b', sql_upper))
        
        # 复杂度评分
        complexity_score = join_count * 2 + subquery_count + where_clauses + having_clauses
        
        if complexity_score <= 2:
            return 'SIMPLE'
        elif complexity_score <= 8:
            return 'MEDIUM'
        else:
            return 'COMPLEX'
    
    def extract_sql_patterns(self, sql: str) -> List[str]:
        """提取SQL模式"""
        patterns = []
        sql_upper = sql.upper()
        
        # 常见模式检测
        if 'JOIN' in sql_upper:
            patterns.append('HAS_JOIN')
        if 'WHERE' in sql_upper:
            patterns.append('HAS_WHERE')
        if 'GROUP BY' in sql_upper:
            patterns.append('HAS_GROUP_BY')
        if 'ORDER BY' in sql_upper:
            patterns.append('HAS_ORDER_BY')
        if 'LIMIT' in sql_upper:
            patterns.append('HAS_LIMIT')
        if 'UNION' in sql_upper:
            patterns.append('HAS_UNION')
        if re.search(r'\bCOUNT\s*\(', sql_upper):
            patterns.append('HAS_COUNT')
        if re.search(r'\b(SUM|AVG|MIN|MAX)\s*\(', sql_upper):
            patterns.append('HAS_AGGREGATION')
        if '?' in sql or ':' in sql:
            patterns.append('HAS_PARAMETERS')
        
        return patterns
    
    def classify_error(self, error_msg: str) -> str:
        """分类错误类型"""
        error_lower = error_msg.lower()
        
        if 'json' in error_lower:
            return 'JSON_PARSE_ERROR'
        elif 'sql' in error_lower:
            return 'SQL_ERROR'
        elif 'timeout' in error_lower:
            return 'TIMEOUT_ERROR'
        elif 'memory' in error_lower:
            return 'MEMORY_ERROR'
        else:
            return 'OTHER_ERROR'
    
    def analyze_fingerprint_coverage(self) -> Dict:
        """分析指纹覆盖情况"""
        logger.info("开始分析指纹覆盖情况...")
        
        total_fingerprints = 0
        matched_fingerprints = 0
        fingerprint_distribution = defaultdict(int)
        unmatched_patterns = defaultdict(int)
        
        for result in self.detailed_results:
            sql_evaluation = result.get('sql_evaluation', {})
            fingerprint_results = sql_evaluation.get('fingerprint_results', [])
            
            for fp_result in fingerprint_results:
                total_fingerprints += 1
                match_result = fp_result.get('match_result', {})
                
                if match_result.get('matched', False):
                    matched_fingerprints += 1
                    fingerprint = match_result.get('fingerprint', 'unknown')
                    fingerprint_distribution[fingerprint] += 1
                else:
                    # 分析未匹配的模式
                    sql = fp_result.get('sql', '')
                    pattern = self.determine_sql_type(sql)
                    unmatched_patterns[pattern] += 1
        
        coverage_rate = matched_fingerprints / total_fingerprints if total_fingerprints > 0 else 0
        
        return {
            'total_fingerprints': total_fingerprints,
            'matched_fingerprints': matched_fingerprints,
            'coverage_rate': coverage_rate,
            'fingerprint_distribution': dict(sorted(fingerprint_distribution.items(), key=lambda x: x[1], reverse=True)[:20]),
            'unmatched_patterns': dict(unmatched_patterns)
        }
    
    def analyze_quality_metrics(self) -> Dict:
        """分析质量指标"""
        logger.info("开始分析质量指标...")
        
        # 按样本分析
        sample_quality = []
        for result in self.detailed_results:
            inference_success = result.get('inference_success', False)
            parsed_sql = result.get('parsed_sql', [])
            sql_evaluation = result.get('sql_evaluation', {})
            
            quality_score = 0
            if inference_success:
                quality_score += 1
            if parsed_sql:
                quality_score += 1
            if sql_evaluation.get('valid_sql', 0) > 0:
                quality_score += 1
            if sql_evaluation.get('matched_sql', 0) > 0:
                quality_score += 2
            
            sample_quality.append(quality_score)
        
        # 质量分布
        quality_distribution = Counter(sample_quality)
        
        # 质量阈值分析
        high_quality_samples = sum(1 for score in sample_quality if score >= 4)
        medium_quality_samples = sum(1 for score in sample_quality if 2 <= score < 4)
        low_quality_samples = sum(1 for score in sample_quality if score < 2)
        
        return {
            'quality_distribution': dict(quality_distribution),
            'quality_thresholds': {
                'high_quality': high_quality_samples,
                'medium_quality': medium_quality_samples,
                'low_quality': low_quality_samples
            },
            'average_quality_score': sum(sample_quality) / len(sample_quality) if sample_quality else 0
        }
    
    def find_representative_examples(self, num_examples: int = 5) -> Dict:
        """寻找代表性示例"""
        logger.info("开始寻找代表性示例...")
        
        examples = {
            'excellent': [],
            'good': [],
            'poor': [],
            'failed': []
        }
        
        for result in self.detailed_results:
            inference_success = result.get('inference_success', False)
            parsed_sql = result.get('parsed_sql', [])
            sql_evaluation = result.get('sql_evaluation', {})
            
            sample_summary = {
                'sample_id': result.get('sample_id', ''),
                'prompt': result.get('prompt', '')[:200] + '...',  # 截取前200字符
                'response': result.get('response', ''),
                'parsed_sql': parsed_sql,
                'valid_sql_count': sql_evaluation.get('valid_sql', 0),
                'matched_sql_count': sql_evaluation.get('matched_sql', 0)
            }
            
            # 分类示例
            if not inference_success:
                if len(examples['failed']) < num_examples:
                    examples['failed'].append(sample_summary)
            elif sql_evaluation.get('matched_sql', 0) > 0:
                if len(examples['excellent']) < num_examples:
                    examples['excellent'].append(sample_summary)
            elif sql_evaluation.get('valid_sql', 0) > 0:
                if len(examples['good']) < num_examples:
                    examples['good'].append(sample_summary)
            else:
                if len(examples['poor']) < num_examples:
                    examples['poor'].append(sample_summary)
        
        return examples
    
    def generate_html_report(self) -> str:
        """生成HTML格式的报告"""
        logger.info("开始生成HTML报告...")
        
        # 分析数据
        sql_analysis = self.analyze_sql_patterns()
        fingerprint_analysis = self.analyze_fingerprint_coverage()
        quality_analysis = self.analyze_quality_metrics()
        examples = self.find_representative_examples()
        
        # 生成HTML内容
        html_content = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>模型评估报告</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                .header {{ text-align: center; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 20px; margin-bottom: 30px; }}
                .section {{ margin-bottom: 30px; }}
                .section-title {{ color: #007bff; font-size: 1.5em; margin-bottom: 15px; border-left: 4px solid #007bff; padding-left: 10px; }}
                .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
                .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #28a745; }}
                .metric-value {{ font-size: 2em; font-weight: bold; color: #28a745; }}
                .metric-label {{ color: #666; font-size: 0.9em; }}
                .chart-container {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #007bff; color: white; }}
                .example-box {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #17a2b8; }}
                .code {{ background: #f4f4f4; padding: 10px; border-radius: 4px; font-family: monospace; margin: 10px 0; overflow-x: auto; }}
                .excellent {{ border-left-color: #28a745; }}
                .good {{ border-left-color: #ffc107; }}
                .poor {{ border-left-color: #fd7e14; }}
                .failed {{ border-left-color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 模型评估报告</h1>
                    <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>模型路径: {self.config.get('model_config', {}).get('model_path', 'Unknown')}</p>
                </div>
                
                <div class="section">
                    <h2 class="section-title">📊 总体统计</h2>
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-value">{self.statistics.get('total_samples', 0)}</div>
                            <div class="metric-label">总样本数</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{self.statistics.get('inference_success_rate', 0):.1%}</div>
                            <div class="metric-label">推理成功率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{self.statistics.get('valid_sql_rate', 0):.1%}</div>
                            <div class="metric-label">有效SQL生成率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{self.statistics.get('fingerprint_match_rate', 0):.1%}</div>
                            <div class="metric-label">指纹匹配率</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{self.statistics.get('total_sql_generated', 0)}</div>
                            <div class="metric-label">总生成SQL数</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{self.statistics.get('sql_validity_rate', 0):.1%}</div>
                            <div class="metric-label">SQL有效性比率</div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2 class="section-title">🎯 SQL模式分析</h2>
                    <div class="chart-container">
                        <h3>SQL类型分布</h3>
                        <table>
                            <tr><th>SQL类型</th><th>数量</th><th>占比</th></tr>
                            {self._generate_table_rows(sql_analysis['sql_type_distribution'])}
                        </table>
                    </div>
                    
                    <div class="chart-container">
                        <h3>SQL复杂度分布</h3>
                        <table>
                            <tr><th>复杂度</th><th>数量</th><th>占比</th></tr>
                            {self._generate_table_rows(sql_analysis['complexity_distribution'])}
                        </table>
                    </div>
                    
                    <div class="chart-container">
                        <h3>常见SQL模式 (Top 10)</h3>
                        <table>
                            <tr><th>模式</th><th>出现次数</th></tr>
                            {self._generate_pattern_table(sql_analysis['common_patterns'])}
                        </table>
                    </div>
                </div>
                
                <div class="section">
                    <h2 class="section-title">🔍 指纹覆盖分析</h2>
                    <div class="metric-grid">
                        <div class="metric-card">
                            <div class="metric-value">{fingerprint_analysis['total_fingerprints']}</div>
                            <div class="metric-label">总指纹数</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{fingerprint_analysis['matched_fingerprints']}</div>
                            <div class="metric-label">匹配指纹数</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{fingerprint_analysis['coverage_rate']:.1%}</div>
                            <div class="metric-label">覆盖率</div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2 class="section-title">⭐ 质量分析</h2>
                    <div class="metric-grid">
                        <div class="metric-card excellent">
                            <div class="metric-value">{quality_analysis['quality_thresholds']['high_quality']}</div>
                            <div class="metric-label">高质量样本</div>
                        </div>
                        <div class="metric-card good">
                            <div class="metric-value">{quality_analysis['quality_thresholds']['medium_quality']}</div>
                            <div class="metric-label">中等质量样本</div>
                        </div>
                        <div class="metric-card poor">
                            <div class="metric-value">{quality_analysis['quality_thresholds']['low_quality']}</div>
                            <div class="metric-label">低质量样本</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{quality_analysis['average_quality_score']:.1f}</div>
                            <div class="metric-label">平均质量分数</div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2 class="section-title">📝 代表性示例</h2>
                    {self._generate_examples_html(examples)}
                </div>
                
                <div class="section">
                    <h2 class="section-title">🔧 配置信息</h2>
                    <div class="code">
                        {json.dumps(self.config, indent=2, ensure_ascii=False)[:1000]}...
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # 保存HTML报告
        html_file = self.output_dir / "evaluation_report.html"
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已保存: {html_file}")
        return str(html_file)
    
    def _generate_table_rows(self, data: Dict) -> str:
        """生成表格行"""
        total = sum(data.values()) if data else 1
        rows = []
        for key, value in data.items():
            percentage = (value / total) * 100
            rows.append(f"<tr><td>{key}</td><td>{value}</td><td>{percentage:.1f}%</td></tr>")
        return "".join(rows)
    
    def _generate_pattern_table(self, data: Dict) -> str:
        """生成模式表格"""
        rows = []
        for pattern, count in list(data.items())[:10]:
            rows.append(f"<tr><td>{pattern}</td><td>{count}</td></tr>")
        return "".join(rows)
    
    def _generate_examples_html(self, examples: Dict) -> str:
        """生成示例HTML"""
        html_parts = []
        
        for category, example_list in examples.items():
            if not example_list:
                continue
                
            category_names = {
                'excellent': '🌟 优秀示例',
                'good': '👍 良好示例', 
                'poor': '⚠️ 较差示例',
                'failed': '❌ 失败示例'
            }
            
            html_parts.append(f"<h3>{category_names.get(category, category)}</h3>")
            
            for i, example in enumerate(example_list[:3]):  # 限制每类最多3个示例
                html_parts.append(f"""
                <div class="example-box {category}">
                    <h4>示例 {i+1}: {example['sample_id']}</h4>
                    <p><strong>提示词片段:</strong> {example['prompt']}</p>
                    <p><strong>模型响应:</strong></p>
                    <div class="code">{example['response'][:300]}{'...' if len(example['response']) > 300 else ''}</div>
                    <p><strong>解析SQL数量:</strong> {len(example['parsed_sql'])}</p>
                    <p><strong>有效SQL:</strong> {example['valid_sql_count']} | <strong>匹配SQL:</strong> {example['matched_sql_count']}</p>
                </div>
                """)
        
        return "".join(html_parts)
    
    def generate_json_report(self) -> str:
        """生成JSON格式的详细报告"""
        logger.info("开始生成JSON报告...")
        
        report_data = {
            'metadata': {
                'generation_time': datetime.now().isoformat(),
                'model_path': self.config.get('model_config', {}).get('model_path'),
                'eval_data_path': self.config.get('data_config', {}).get('eval_data_path'),
                'total_samples': self.statistics.get('total_samples', 0)
            },
            'overall_statistics': self.statistics,
            'sql_analysis': self.analyze_sql_patterns(),
            'fingerprint_analysis': self.analyze_fingerprint_coverage(),
            'quality_analysis': self.analyze_quality_metrics(),
            'representative_examples': self.find_representative_examples(3),
            'configuration': self.config
        }
        
        json_file = self.output_dir / "detailed_analysis.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"JSON报告已保存: {json_file}")
        return str(json_file)
    
    def generate_all_reports(self) -> Dict[str, str]:
        """生成所有格式的报告"""
        logger.info("开始生成完整报告...")
        
        reports = {
            'html_report': self.generate_html_report(),
            'json_report': self.generate_json_report()
        }
        
        logger.info("所有报告生成完成!")
        return reports


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="评估报告生成器")
    parser.add_argument("--results_file", type=str, required=True, help="评估结果文件路径")
    parser.add_argument("--output_dir", type=str, required=True, help="报告输出目录")
    parser.add_argument("--format", type=str, choices=['html', 'json', 'all'], default='all', help="报告格式")
    
    args = parser.parse_args()
    
    try:
        # 创建报告生成器
        generator = EvaluationReportGenerator(args.results_file, args.output_dir)
        
        # 生成报告
        if args.format == 'html':
            html_report = generator.generate_html_report()
            print(f"✅ HTML报告已生成: {html_report}")
        elif args.format == 'json':
            json_report = generator.generate_json_report()
            print(f"✅ JSON报告已生成: {json_report}")
        else:
            reports = generator.generate_all_reports()
            print("✅ 所有报告已生成:")
            for report_type, path in reports.items():
                print(f"  - {report_type}: {path}")
        
    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        raise


if __name__ == "__main__":
    main() 