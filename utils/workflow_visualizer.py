"""
工作流可视化器

用于生成数据处理工作流的数据流向图
"""
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime

# 设置字体 - 使用英文避免中文显示问题
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

logger = logging.getLogger(__name__)


class WorkflowVisualizer:
    """工作流可视化器"""
    
    def __init__(self, output_dir: str = "workflow_visualizations"):
        """
        初始化可视化器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 定义颜色方案
        self.colors = {
            'input': '#4CAF50',      # 绿色 - 输入
            'output': '#2196F3',     # 蓝色 - 输出
            'process': '#FF9800',     # 橙色 - 处理
            'error': '#F44336',       # 红色 - 错误
            'success': '#4CAF50',     # 绿色 - 成功
            'warning': '#FFC107',     # 黄色 - 警告
            'merge': '#9C27B0',       # 紫色 - 合并
            'validation': '#00BCD4',  # 青色 - 验证
            'cleaning': '#795548',    # 棕色 - 清洗
            'extraction': '#E91E63',  # 粉色 - 提取
            'separation': '#607D8B',  # 蓝灰色 - 分离
        }
        
        # 步骤类型到颜色的映射
        self.step_type_colors = {
            'data_loading': self.colors['input'],
            'llm_keyword_extraction': self.colors['extraction'],
            'keyword_data_processing': self.colors['process'],
            'data_separation': self.colors['separation'],
            'sql_cleaning': self.colors['cleaning'],
            'remove_no_sql_records': self.colors['cleaning'],
            'redundant_sql_validation': self.colors['validation'],
            'control_flow_validation': self.colors['validation'],
            'data_processing': self.colors['merge'],
            'default': self.colors['process']
        }
        
    def extract_workflow_stats(self, workflow_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        从工作流摘要中提取统计数据
        
        Args:
            workflow_summary: 工作流摘要数据
            
        Returns:
            提取的统计数据
        """
        stats = {
            'workflow_id': workflow_summary.get('workflow_id', 'unknown'),
            'start_time': workflow_summary.get('start_time', ''),
            'end_time': workflow_summary.get('end_time', ''),
            'total_steps': workflow_summary.get('total_steps', 0),
            'steps': [],
            'step_summary': {},
            'final_output': {'total': 0, 'retention_rate': 0}
        }
        
        # 从工作流步骤中提取数据
        steps = workflow_summary.get('steps', [])
        original_count = 0
        
        for step in steps:
            step_type = step.get('step_type', '')
            step_name = step.get('step_name', '')
            
            # 提取步骤数据
            step_data = {
                'name': step_name,
                'type': step_type,
                'timestamp': step.get('timestamp', ''),
                'input_records': step.get('input_records', 0),
                'output_records': step.get('output_records', 0),
                'total_records_loaded': step.get('total_records_loaded', 0),
                'extracted_records': step.get('extracted_records', 0),
                'unmatched_records': step.get('unmatched_records', 0),
                'extraction_rate': step.get('extraction_rate', 0),
                'processed_successfully': step.get('processed_successfully', 0),
                'processing_failed': step.get('processing_failed', 0),
                'records_modified': step.get('records_modified', 0),
                'removed_records': step.get('removed_records', 0),
                'remaining_records': step.get('remaining_records', 0),
                'total_records': step.get('total_records', 0),
                'control_flow_records': step.get('control_flow_records', 0),
                'correct_records': step.get('correct_records', 0),
                'incorrect_records': step.get('incorrect_records', 0),
                'total_candidates': step.get('total_candidates', 0),
                'validation_stats': step.get('validation_stats', {}),
                'keyword_statistics': step.get('keyword_statistics', {}),
                'non_keyword_records': step.get('non_keyword_records', 0),
                'keyword_data': step.get('keyword_data', {})
            }
            
            stats['steps'].append(step_data)
            
            # 更新步骤摘要
            if step_type not in stats['step_summary']:
                stats['step_summary'][step_type] = []
            stats['step_summary'][step_type].append(step_data)
            
            # 获取原始数据量
            if step_type == 'data_loading':
                original_count = step.get('total_records_loaded', 0)
            elif step_type == 'llm_keyword_extraction' and original_count == 0:
                original_count = step.get('input_records', 0)
        
        # 计算最终输出
        if steps:
            last_step = steps[-1]
            if last_step.get('step_type') == 'data_processing':
                stats['final_output']['total'] = last_step.get('total_records', 0)
            else:
                # 尝试从最后几个步骤中获取最终数据量
                for step in reversed(steps):
                    if step.get('output_records', 0) > 0:
                        stats['final_output']['total'] = step.get('output_records', 0)
                        break
                    elif step.get('total_records', 0) > 0:
                        stats['final_output']['total'] = step.get('total_records', 0)
                        break
        
        # 计算保留率
        if original_count > 0:
            stats['original_count'] = original_count
            stats['final_output']['retention_rate'] = (stats['final_output']['total'] / original_count) * 100
        
        return stats
    
    def create_data_flow_diagram(self, stats: Dict[str, Any], title: str = "Data Processing Workflow") -> str:
        """
        创建数据流向图 - 使用英文标签避免字体问题
        
        Args:
            stats: 统计数据
            title: 图表标题
            
        Returns:
            保存的文件路径
        """
        fig, ax = plt.subplots(1, 1, figsize=(20, 24))  # 再次提升图表高度
        ax.set_xlim(0, 12)
        ax.set_ylim(0, 24)  # 再次提升y轴范围
        ax.axis('off')
        
        # 标题
        ax.text(6, 23.5, title, fontsize=20, fontweight='bold', ha='center')
        
        # 重新设计数据流向逻辑
        nodes = self._create_workflow_nodes(stats['steps'])
        
        # 绘制节点
        for node_name, node_info in nodes.items():
            pos, step_data, node_type = node_info
            self._draw_node(ax, pos, step_data, node_type)
        
        # 绘制数据流向连接
        self._draw_data_flow_connections(ax, nodes, stats)
        
        # 添加统计信息
        self._add_statistics(ax, stats)
        
        # 保存图片
        timestamp = stats.get('workflow_id', 'workflow')
        filename = f"data_flow_diagram_{timestamp}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        logger.info(f"Data flow diagram saved: {filepath}")
        return str(filepath)
    
    def _create_workflow_nodes(self, steps: List[Dict[str, Any]]) -> Dict[str, Tuple[Tuple[float, float], Dict[str, Any], str]]:
        """
        创建工作流节点 - 重新设计布局以正确显示数据流向
        
        Args:
            steps: 工作流步骤列表
            
        Returns:
            节点信息字典
        """
        nodes = {}
        
        if not steps:
            return nodes
        
        # 分析工作流结构
        workflow_structure = self._analyze_workflow_structure(steps)
        
        # 创建节点位置 - 进一步调整布局避免重叠
        y_levels = {
            'input': 14,
            'extraction': 12,
            'branch': 10,
            'processing': 8,
            'validation': 6,
            'merge': 4,
            'control_flow': 2,
            'output': 0
        }
        
        # 数据加载节点
        if workflow_structure['has_data_loading']:
            nodes['data_loading'] = ((6, y_levels['input']), 
                                   workflow_structure['data_loading'], 'input')
        
        # 关键词提取节点
        if workflow_structure['has_keyword_extraction']:
            nodes['keyword_extraction'] = ((6, y_levels['extraction']), 
                                         workflow_structure['keyword_extraction'], 'extraction')
        
        # 数据分离节点 - 显示分支
        if workflow_structure['has_data_separation']:
            nodes['keyword_data'] = ((3, y_levels['branch']), 
                                   workflow_structure['keyword_data'], 'branch')
            nodes['non_keyword_data'] = ((9, y_levels['branch']), 
                                        workflow_structure['non_keyword_data'], 'branch')
        
        # 关键词处理节点
        if workflow_structure['has_keyword_processing']:
            nodes['keyword_processing'] = ((3, y_levels['processing']), 
                                         workflow_structure['keyword_processing'], 'processing')
        
        # SQL清洗节点
        if workflow_structure['has_sql_cleaning']:
            nodes['sql_cleaning'] = ((9, y_levels['processing']), 
                                   workflow_structure['sql_cleaning'], 'processing')
        
        # 无SQL移除节点
        if workflow_structure['has_no_sql_removal']:
            nodes['no_sql_removal'] = ((9, y_levels['validation']), 
                                      workflow_structure['no_sql_removal'], 'validation')
        
        # 冗余验证节点 - 调整位置避免重叠
        if workflow_structure['has_redundant_validation']:
            nodes['redundant_validation'] = ((9, y_levels['validation']), 
                                           workflow_structure['redundant_validation'], 'validation')
        
        # 数据合并节点
        if workflow_structure['has_merge']:
            nodes['data_merge'] = ((6, y_levels['merge']), 
                                 workflow_structure['data_merge'], 'merge')
        
        # 控制流验证节点 - 调整位置，在数据合并之后
        if workflow_structure['has_control_flow_validation']:
            nodes['control_flow_validation'] = ((6, y_levels['control_flow']), 
                                              workflow_structure['control_flow_validation'], 'validation')
        
        # 最终输出节点
        nodes['final_output'] = ((6, y_levels['output']), 
                               workflow_structure['final_output'], 'output')
        
        return nodes
    
    def _analyze_workflow_structure(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析工作流结构，确定数据流向
        
        Args:
            steps: 工作流步骤列表
            
        Returns:
            工作流结构信息
        """
        structure = {
            'has_data_loading': False,
            'has_keyword_extraction': False,
            'has_data_separation': False,
            'has_keyword_processing': False,
            'has_sql_cleaning': False,
            'has_no_sql_removal': False,
            'has_redundant_validation': False,
            'has_control_flow_validation': False,
            'has_merge': False,
            'data_loading': {},
            'keyword_extraction': {},
            'keyword_data': {},
            'non_keyword_data': {},
            'keyword_processing': {},
            'sql_cleaning': {},
            'no_sql_removal': {},
            'redundant_validation': {},
            'control_flow_validation': {},
            'data_merge': {},
            'final_output': {}
        }
        
        original_count = 0
        
        for step in steps:
            step_type = step.get('type', '')
            
            if step_type == 'data_loading':
                structure['has_data_loading'] = True
                structure['data_loading'] = step
                original_count = step.get('total_records_loaded', 0)
                
            elif step_type == 'llm_keyword_extraction':
                structure['has_keyword_extraction'] = True
                structure['keyword_extraction'] = step
                if original_count == 0:
                    original_count = step.get('input_records', 0)
                    
            elif step_type == 'data_separation':
                structure['has_data_separation'] = True
                structure['keyword_data'] = {
                    'name': 'Keyword Data',
                    'type': 'keyword_data',
                    'extracted': step.get('keyword_data', {}).get('extracted', 0),
                    'processed': step.get('keyword_data', {}).get('processed', 0)
                }
                structure['non_keyword_data'] = {
                    'name': 'Non-Keyword Data',
                    'type': 'non_keyword_data',
                    'count': step.get('non_keyword_records', 0)
                }
                
            elif step_type == 'keyword_data_processing':
                structure['has_keyword_processing'] = True
                structure['keyword_processing'] = step
                
            elif step_type == 'sql_cleaning':
                structure['has_sql_cleaning'] = True
                structure['sql_cleaning'] = step
                
            elif step_type == 'remove_no_sql_records':
                structure['has_no_sql_removal'] = True
                structure['no_sql_removal'] = step
                
            elif step_type == 'redundant_sql_validation':
                structure['has_redundant_validation'] = True
                structure['redundant_validation'] = step
                
            elif step_type == 'control_flow_validation':
                structure['has_control_flow_validation'] = True
                structure['control_flow_validation'] = step
                
            elif step_type == 'data_processing':
                structure['has_merge'] = True
                structure['data_merge'] = step
        
        # 计算最终输出
        final_total = 0
        if structure['has_keyword_processing']:
            final_total += structure['keyword_processing'].get('output_records', 0)
        if structure['has_no_sql_removal']:
            final_total += structure['no_sql_removal'].get('remaining_records', 0)
        elif structure['has_sql_cleaning']:
            final_total += structure['sql_cleaning'].get('output_records', 0)
        
        structure['final_output'] = {
            'name': 'Final Output',
            'type': 'final_output',
            'total': final_total,
            'retention_rate': (final_total / original_count * 100) if original_count > 0 else 0
        }
        
        return structure
    
    def _draw_node(self, ax, pos: Tuple[float, float], step_data: Dict[str, Any], node_type: str):
        """绘制节点"""
        x, y = pos
        step_type = step_data.get('type', 'unknown')
        step_name = step_data.get('name', 'Unknown')
        
        # 获取颜色
        color = self.step_type_colors.get(step_type, self.step_type_colors['default'])
        
        # 生成节点文本
        node_text = self._generate_node_text(step_data)
        
        # 根据文本长度调整节点大小
        text_lines = node_text.count('\n') + 1
        node_height = max(1.0, text_lines * 0.4)
        
        # 绘制圆角矩形
        rect = FancyBboxPatch((x-1.2, y-node_height/2), 2.4, node_height, 
                             boxstyle="round,pad=0.1", 
                             facecolor=color, 
                             edgecolor='black', 
                             linewidth=1.5,
                             alpha=0.8)
        ax.add_patch(rect)
        
        # 添加文本 - 调整字体大小避免重叠
        fontsize = 8 if len(node_text) > 30 else 9
        ax.text(x, y, node_text, fontsize=fontsize, ha='center', va='center', 
                fontweight='bold', color='white')
    
    def _generate_node_text(self, step_data: Dict[str, Any]) -> str:
        """
        根据步骤数据生成节点文本 - 使用英文，优化布局避免重叠
        
        Args:
            step_data: 步骤数据
            
        Returns:
            节点文本
        """
        step_type = step_data.get('type', 'unknown')
        step_name = step_data.get('name', 'Unknown')
        
        # 根据步骤类型生成不同的文本
        if step_type == 'data_loading':
            total = step_data.get('total_records_loaded', 0)
            return f"Data Loading\n{total:,} records"
            
        elif step_type == 'llm_keyword_extraction':
            extracted = step_data.get('extracted_records', 0)
            rate = step_data.get('extraction_rate', 0)
            return f"Keyword Extraction\n{extracted:,} records\n({rate:.1f}%)"
            
        elif step_type == 'keyword_data_processing':
            output = step_data.get('output_records', 0)
            success = step_data.get('processed_successfully', 0)
            return f"Keyword Processing\n{output:,} records\nSuccess:{success:,}"
            
        elif step_type == 'keyword_data':
            extracted = step_data.get('extracted', 0)
            return f"Keyword Data\n{extracted:,} records"
            
        elif step_type == 'non_keyword_data':
            count = step_data.get('count', 0)
            return f"Non-Keyword Data\n{count:,} records"
            
        elif step_type == 'sql_cleaning':
            output = step_data.get('output_records', 0)
            modified = step_data.get('records_modified', 0)
            return f"SQL Cleaning\n{output:,} records\nModified:{modified:,}"
            
        elif step_type == 'remove_no_sql_records':
            output = step_data.get('remaining_records', 0)
            removed = step_data.get('removed_records', 0)
            return f"No-SQL Removal\n{output:,} records\nRemoved:{removed:,}"
            
        elif step_type == 'redundant_sql_validation':
            candidates = step_data.get('total_candidates', 0)
            validation_stats = step_data.get('validation_stats', {})
            modified = validation_stats.get('modified_records', 0)
            # 避免重复和冗余信息
            if candidates == modified:
                return f"Redundant Validation\n{candidates:,} modified"
            elif candidates > 0 and modified > 0:
                return f"Redundant Validation\nCandidates: {candidates:,}\nModified: {modified:,}"
            elif candidates > 0:
                return f"Redundant Validation\nCandidates: {candidates:,}"
            elif modified > 0:
                return f"Redundant Validation\nModified: {modified:,}"
            else:
                return f"Redundant Validation\nNo changes"
            
        elif step_type == 'control_flow_validation':
            total = step_data.get('total_records', 0)
            detected = step_data.get('control_flow_records', 0)
            correct = step_data.get('correct_records', 0)
            return f"Control Flow Validation\nDetected:{detected:,}\nCorrect:{correct:,}"
            
        elif step_type == 'data_processing':
            total = step_data.get('total_records', 0)
            return f"Data Processing\n{total:,} records"
            
        elif step_type == 'final_output':
            total = step_data.get('total', 0)
            rate = step_data.get('retention_rate', 0)
            return f"Final Output\n{total:,} records\nRetention:{rate:.1f}%"
            
        else:
            # 通用格式
            input_records = step_data.get('input_records', 0)
            output_records = step_data.get('output_records', 0)
            return f"{step_name}\nInput:{input_records:,}\nOutput:{output_records:,}"
    
    def _draw_data_flow_connections(self, ax, nodes: Dict[str, Tuple[Tuple[float, float], Dict[str, Any], str]], stats: Dict[str, Any]):
        """绘制数据流向连接 - 重新设计以正确显示数据分支和合并"""
        
        # 定义连接关系
        connections = []
        
        # 数据加载 -> 关键词提取
        if 'data_loading' in nodes and 'keyword_extraction' in nodes:
            connections.append(('data_loading', 'keyword_extraction', 'Input'))
        
        # 关键词提取 -> 数据分离（分支）
        if 'keyword_extraction' in nodes and 'keyword_data' in nodes:
            connections.append(('keyword_extraction', 'keyword_data', 'Extract'))
        if 'keyword_extraction' in nodes and 'non_keyword_data' in nodes:
            connections.append(('keyword_extraction', 'non_keyword_data', 'Separate'))
        
        # 关键词数据 -> 关键词处理
        if 'keyword_data' in nodes and 'keyword_processing' in nodes:
            connections.append(('keyword_data', 'keyword_processing', 'Process'))
        
        # 非关键词数据 -> SQL清洗
        if 'non_keyword_data' in nodes and 'sql_cleaning' in nodes:
            connections.append(('non_keyword_data', 'sql_cleaning', 'Clean'))
        
        # SQL清洗 -> 无SQL移除
        if 'sql_cleaning' in nodes and 'no_sql_removal' in nodes:
            connections.append(('sql_cleaning', 'no_sql_removal', 'Filter'))
        
        # 无SQL移除 -> 冗余验证
        if 'no_sql_removal' in nodes and 'redundant_validation' in nodes:
            connections.append(('no_sql_removal', 'redundant_validation', 'Validate'))
        
        # 关键词处理 -> 数据合并
        if 'keyword_processing' in nodes and 'data_merge' in nodes:
            connections.append(('keyword_processing', 'data_merge', 'Merge'))
        
        # 冗余验证 -> 数据合并
        if 'redundant_validation' in nodes and 'data_merge' in nodes:
            connections.append(('redundant_validation', 'data_merge', 'Merge'))
        
        # 数据合并 -> 控制流验证（修正流程顺序）
        if 'data_merge' in nodes and 'control_flow_validation' in nodes:
            connections.append(('data_merge', 'control_flow_validation', 'Validate'))
        
        # 控制流验证 -> 最终输出（修正流程顺序）
        if 'control_flow_validation' in nodes and 'final_output' in nodes:
            connections.append(('control_flow_validation', 'final_output', 'Output'))
        
        # 如果没有数据合并节点，但有控制流验证，直接从处理节点连接
        if 'data_merge' not in nodes and 'control_flow_validation' in nodes:
            # 尝试从关键词处理连接
            if 'keyword_processing' in nodes:
                connections.append(('keyword_processing', 'control_flow_validation', 'Validate'))
            # 尝试从冗余验证连接
            elif 'redundant_validation' in nodes:
                connections.append(('redundant_validation', 'control_flow_validation', 'Validate'))
            # 尝试从无SQL移除连接
            elif 'no_sql_removal' in nodes:
                connections.append(('no_sql_removal', 'control_flow_validation', 'Validate'))
        
        # 绘制连接
        for start_node, end_node, label in connections:
            if start_node in nodes and end_node in nodes:
                start_pos = nodes[start_node][0]
                end_pos = nodes[end_node][0]
                
                # 绘制箭头
                arrow = ConnectionPatch(start_pos, end_pos, "data", "data",
                                      arrowstyle="->", shrinkA=5, shrinkB=5,
                                      mutation_scale=20, fc="black", ec="black",
                                      linewidth=2)
                ax.add_patch(arrow)
                
                # 添加标签
                mid_x = (start_pos[0] + end_pos[0]) / 2
                mid_y = (start_pos[1] + end_pos[1]) / 2
                ax.text(mid_x, mid_y, label, fontsize=8, ha='center', va='center',
                        bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
    
    def _add_statistics(self, ax, stats: Dict[str, Any]):
        """添加统计信息"""
        # 在右侧添加统计信息
        stats_text = self._generate_statistics_text(stats)
        
        ax.text(10.5, 7, stats_text, fontsize=9, va='top', ha='left',
                bbox=dict(boxstyle="round,pad=0.5", facecolor='lightblue', alpha=0.8))
    
    def _generate_statistics_text(self, stats: Dict[str, Any]) -> str:
        """
        生成统计信息文本 - 使用英文
        
        Args:
            stats: 统计数据
            
        Returns:
            统计信息文本
        """
        steps = stats.get('steps', [])
        if not steps:
            return "No workflow step data"
        
        # 提取关键指标
        original_count = stats.get('original_count', 0)
        final_total = stats.get('final_output', {}).get('total', 0)
        retention_rate = stats.get('final_output', {}).get('retention_rate', 0)
        
        # 按步骤类型统计
        step_stats = {}
        for step in steps:
            step_type = step.get('type', 'unknown')
            if step_type not in step_stats:
                step_stats[step_type] = {
                    'count': 0,
                    'total_input': 0,
                    'total_output': 0
                }
            
            step_stats[step_type]['count'] += 1
            step_stats[step_type]['total_input'] += step.get('input_records', 0)
            step_stats[step_type]['total_output'] += step.get('output_records', 0)
        
        # 生成统计文本
        text = f"Workflow Statistics\n\n"
        text += f"Workflow ID: {stats.get('workflow_id', 'unknown')}\n"
        text += f"Total Steps: {stats.get('total_steps', 0)}\n"
        text += f"Original Data: {original_count:,} records\n"
        text += f"Final Output: {final_total:,} records\n"
        text += f"Retention Rate: {retention_rate:.1f}%\n\n"
        
        text += "Step Statistics\n"
        for step_type, step_data in step_stats.items():
            if step_data['count'] > 0:
                text += f"- {step_type}: {step_data['count']} times\n"
                if step_data['total_input'] > 0:
                    text += f"  Input: {step_data['total_input']:,} records\n"
                if step_data['total_output'] > 0:
                    text += f"  Output: {step_data['total_output']:,} records\n"
        
        return text
    
    def create_performance_chart(self, stats: Dict[str, Any], title: str = "Workflow Performance Analysis") -> str:
        """
        创建性能分析图表
        
        Args:
            stats: 统计数据
            title: 图表标题
            
        Returns:
            保存的文件路径
        """
        steps = stats.get('steps', [])
        if not steps:
            logger.warning("No step data, skipping performance chart generation")
            return ""
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=16, fontweight='bold')
        
        # 1. 数据流向柱状图
        step_names = [step.get('name', 'Unknown') for step in steps]
        input_counts = [step.get('input_records', 0) for step in steps]
        output_counts = [step.get('output_records', 0) for step in steps]
        
        x = np.arange(len(step_names))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, input_counts, width, label='Input', color='#4CAF50')
        bars2 = ax1.bar(x + width/2, output_counts, width, label='Output', color='#2196F3')
        
        ax1.set_title('Data Volume Changes by Step')
        ax1.set_ylabel('Record Count')
        ax1.set_xticks(x)
        ax1.set_xticklabels(step_names, rotation=45, ha='right')
        ax1.legend()
        
        # 添加数值标签
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax1.text(bar.get_x() + bar.get_width()/2., height + max(max(input_counts), max(output_counts))*0.01,
                            f'{int(height):,}', ha='center', va='bottom', fontsize=8)
        
        # 2. 步骤类型分布饼图
        step_types = {}
        for step in steps:
            step_type = step.get('type', 'unknown')
            step_types[step_type] = step_types.get(step_type, 0) + 1
        
        if step_types:
            labels = list(step_types.keys())
            sizes = list(step_types.values())
            colors = [self.step_type_colors.get(step_type, self.step_type_colors['default']) for step_type in labels]
            
            ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax2.set_title('Step Type Distribution')
        
        # 3. 关键指标柱状图
        key_metrics = []
        metric_names = []
        
        for step in steps:
            step_type = step.get('type', '')
            if step_type == 'llm_keyword_extraction':
                rate = step.get('extraction_rate', 0)
                key_metrics.append(rate)
                metric_names.append('Keyword Extraction Rate')
            elif step_type == 'keyword_data_processing':
                success = step.get('processed_successfully', 0)
                total = step.get('input_records', 1)
                rate = (success / total * 100) if total > 0 else 0
                key_metrics.append(rate)
                metric_names.append('Keyword Processing Success Rate')
            elif step_type == 'control_flow_validation':
                detected = step.get('control_flow_records', 0)
                total = step.get('total_records', 1)
                rate = (detected / total * 100) if total > 0 else 0
                key_metrics.append(rate)
                metric_names.append('Control Flow Detection Rate')
        
        if key_metrics:
            bars = ax3.bar(metric_names, key_metrics, color=['#FF9800', '#4CAF50', '#00BCD4'])
            ax3.set_title('Key Performance Metrics')
            ax3.set_ylabel('Percentage (%)')
            ax3.set_ylim(0, 100)
            
            # 添加数值标签
            for bar, value in zip(bars, key_metrics):
                height = bar.get_height()
                ax3.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{value:.1f}%', ha='center', va='bottom', fontsize=10)
        
        # 4. 数据保留率
        retention_rate = stats.get('final_output', {}).get('retention_rate', 0)
        ax4.bar(['Data Retention Rate'], [retention_rate], color='#2196F3', width=0.5)
        ax4.set_ylim(0, 100)
        ax4.set_ylabel('Percentage (%)')
        ax4.set_title('Final Data Retention Rate')
        ax4.text(0, retention_rate + 2, f'{retention_rate:.1f}%', 
                ha='center', va='bottom', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        
        # 保存图片
        timestamp = stats.get('workflow_id', 'workflow')
        filename = f"performance_analysis_{timestamp}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        logger.info(f"Performance analysis chart saved: {filepath}")
        return str(filepath)
    
    def generate_workflow_visualization(self, workflow_summary_path: str, timestamp: Optional[str] = None) -> Dict[str, str]:
        """
        生成完整的工作流可视化
        
        Args:
            workflow_summary_path: 工作流摘要文件路径
            timestamp: 时间戳
            
        Returns:
            生成的文件路径字典
        """
        try:
            # 加载工作流摘要
            with open(workflow_summary_path, 'r', encoding='utf-8') as f:
                workflow_summary = json.load(f)
            
            # 提取统计数据
            stats = self.extract_workflow_stats(workflow_summary)
            if timestamp:
                stats['timestamp'] = timestamp
            
            # 生成可视化图表
            flow_diagram_path = self.create_data_flow_diagram(stats)
            performance_chart_path = self.create_performance_chart(stats)
            
            # 保存统计数据
            stats_file = self.output_dir / f"workflow_stats_{stats.get('workflow_id', 'workflow')}.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            
            return {
                'flow_diagram': flow_diagram_path,
                'performance_chart': performance_chart_path,
                'stats_file': str(stats_file)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate workflow visualization: {e}")
            return {}


def generate_workflow_visualization(workflow_summary_path: str, output_dir: str = "workflow_visualizations", timestamp: Optional[str] = None) -> Dict[str, str]:
    """
    生成工作流可视化的便捷函数
    
    Args:
        workflow_summary_path: 工作流摘要文件路径
        output_dir: 输出目录
        timestamp: 时间戳
        
    Returns:
        生成的文件路径字典
    """
    visualizer = WorkflowVisualizer(output_dir)
    return visualizer.generate_workflow_visualization(workflow_summary_path, timestamp)


if __name__ == "__main__":
    # 测试代码
    import sys
    if len(sys.argv) > 1:
        workflow_summary_path = sys.argv[1]
        timestamp = sys.argv[2] if len(sys.argv) > 2 else None
        result = generate_workflow_visualization(workflow_summary_path, timestamp=timestamp)
        print(f"Visualization files generated: {result}")
    else:
        print("Usage: python workflow_visualizer.py <workflow_summary_path> [timestamp]") 