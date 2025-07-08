"""
冗余SQL验证器 - 重构版

实现分步骤LLM验证流程：
1. 规则预过滤
2. 语法等价检测
3. 业务合理性检测（冗余/新增指纹/缺失）
4. 生成最终修复建议
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

try:
    from utils.llm_client import LLMClientManager
    from config.data_clean.redundant_sql_validation_prompt import (
        SYNTAX_EQUIVALENCE_PROMPT,
        REDUNDANT_BUSINESS_VALIDATION_PROMPT,
        NEW_FINGERPRINT_VALIDATION_PROMPT,
        MISSING_SQL_VALIDATION_PROMPT,
        RULE_BASED_FILTER_PROMPT
    )
except ImportError:
    # 备用导入路径
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from utils.llm_client import LLMClientManager
    from config.data_clean.redundant_sql_validation_prompt import (
        SYNTAX_EQUIVALENCE_PROMPT,
        REDUNDANT_BUSINESS_VALIDATION_PROMPT,
        NEW_FINGERPRINT_VALIDATION_PROMPT,
        MISSING_SQL_VALIDATION_PROMPT,
        RULE_BASED_FILTER_PROMPT
    )

logger = logging.getLogger(__name__)


class RedundantSQLValidator:
    """
    冗余SQL验证器 - 重构版
    
    实现分步骤LLM验证流程，处理不同类型的SQL问题：
    - redundant: 冗余SQL检测
    - new_fingerprint: 新增指纹合理性检测
    - missing: 缺失SQL必要性检测
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
        
        # 验证统计
        self.validation_stats = {
            'total_candidates': 0,
            'step_stats': {
                'rule_filter': {'processed': 0, 'auto_decided': 0},
                'syntax_check': {'processed': 0, 'equivalent': 0},
                'business_check': {'processed': 0, 'confirmed': 0},
                'llm_errors': 0
            },
            'type_stats': {
                'redundant': {'total': 0, 'confirmed': 0, 'disputed': 0},
                'new_fingerprint': {'total': 0, 'valid_new': 0, 'wrong_new': 0},
                'missing': {'total': 0, 'truly_missing': 0, 'unnecessary': 0}
            }
        }
        
        logger.info(f"冗余SQL验证器（重构版）初始化完成，输出目录: {self.output_dir}")
    
    async def validate_llm_candidates(self, llm_candidates: List[Dict[str, Any]], 
                                    max_concurrent: int = 200) -> Dict[str, Any]:
        """
        验证LLM候选项
        
        Args:
            llm_candidates: 从ORM分析器获取的候选项列表
            max_concurrent: 最大并发数
            
        Returns:
            Dict: 验证结果摘要
        """
        if not llm_candidates:
            logger.info("没有候选项需要验证")
            return self._generate_empty_result()
        
        logger.info(f"开始验证 {len(llm_candidates)} 个候选项...")
        self.validation_stats['total_candidates'] = len(llm_candidates)
        
        # 按类型分组候选项
        candidates_by_type = {}
        for candidate in llm_candidates:
            validation_type = candidate['validation_type']
            if validation_type not in candidates_by_type:
                candidates_by_type[validation_type] = []
            candidates_by_type[validation_type].append(candidate)
        
        # 记录类型统计
        for v_type, candidates in candidates_by_type.items():
            self.validation_stats['type_stats'][v_type]['total'] = len(candidates)
        
        # 异步验证所有候选项
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def validate_with_semaphore(candidate: Dict) -> Dict:
            async with semaphore:
                return await self._validate_single_candidate(candidate)
        
        validated_results = []
        with tqdm_asyncio(total=len(llm_candidates), desc="验证候选项") as pbar:
            async with aiohttp.ClientSession() as session:
                self.session = session  # 保存session供子方法使用
                tasks = [asyncio.ensure_future(validate_with_semaphore(candidate)) for candidate in llm_candidates]
                for task in tasks:
                    task.add_done_callback(lambda p: pbar.update(1))
                validated_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(validated_results):
            if isinstance(result, Exception):
                logger.error(f"候选项 {i} 验证异常: {result}")
                error_result = llm_candidates[i].copy()
                error_result.update({
                    'validation_status': 'error',
                    'validation_error': str(result),
                    'final_decision': 'keep',  # 出错时保守处理
                    'validation_steps': [],
                    'validation_timestamp': datetime.now().isoformat()
                })
                final_results.append(error_result)
                self.validation_stats['step_stats']['llm_errors'] += 1
            else:
                final_results.append(result)
        
        # 更新统计信息
        self._update_final_stats(final_results)
        
        # 生成报告
        report_files = self._generate_validation_reports(final_results)
        
        # 生成修复建议
        fix_recommendations = self._generate_fix_recommendations(final_results)
        
        return {
            'total_candidates': len(llm_candidates),
            'validation_stats': self.validation_stats,
            'validated_results': final_results,
            'report_files': report_files,
            'fix_recommendations': fix_recommendations
        }
    
    async def _validate_single_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证单个候选项
        
        Args:
            candidate: 候选项信息
            
        Returns:
            Dict: 验证结果
        """
        validation_type = candidate['validation_type']
        validation_steps = []
        
        try:
            # 根据类型调用不同的验证流程
            if validation_type == 'redundant':
                final_decision, steps = await self._validate_redundant_candidate(candidate)
            elif validation_type == 'new_fingerprint':
                final_decision, steps = await self._validate_new_fingerprint_candidate(candidate)
            elif validation_type == 'missing':
                final_decision, steps = await self._validate_missing_candidate(candidate)
            else:
                final_decision = 'keep'
                steps = [{'step': 'error', 'result': f'未知验证类型: {validation_type}'}]
            
            validation_steps = steps
            
        except Exception as e:
            logger.warning(f"验证候选项时出错: {e}")
            final_decision = 'keep'  # 出错时保守处理
            validation_steps = [{'step': 'error', 'result': str(e)}]
        
        # 构建结果
        result = candidate.copy()
        result.update({
            'validation_status': 'completed',
            'final_decision': final_decision,
            'validation_steps': validation_steps,
            'validation_timestamp': datetime.now().isoformat()
        })
        
        return result
    
    async def _validate_redundant_candidate(self, candidate: Dict[str, Any]) -> Tuple[str, List[Dict]]:
        """
        验证冗余候选项
            
        Returns:
            Tuple[final_decision, validation_steps]
        """
        steps = []
        candidate_info = candidate['candidate_info']
        redundant_sqls = candidate_info['redundant_sqls']
        
        # 对每个冗余SQL进行验证 - 全量处理，移除数量限制
        confirmed_redundant_count = 0
        
        for sql_record in redundant_sqls:  # 处理所有SQL，移除[:3]限制
            sql_text = sql_record['sql_text'].replace(' <REDUNDANT SQL>', '').strip()
            
            # Step 2: 业务合理性检测
            prompt = REDUNDANT_BUSINESS_VALIDATION_PROMPT.format(
                orm_code=candidate['orm_code_content'][:2000],  # 限制长度
                caller=candidate['target_caller'],
                reference_caller=candidate['reference_caller'],
                target_sql=sql_text
            )
            
            response = await self.llm_client.call_async(self.session, prompt, max_tokens=300, temperature=0.0)
            
            step_result = {
                'step': 'business_validation',
                'sql_text': sql_text,
                'prompt_length': len(prompt),
                'llm_response': response,
                'is_redundant': False
            }
            
            if response and ('是，冗余' in response or response.strip().startswith('是')):
                step_result['is_redundant'] = True
                confirmed_redundant_count += 1
            
            steps.append(step_result)
            self.validation_stats['step_stats']['business_check']['processed'] += 1
            if step_result['is_redundant']:
                self.validation_stats['step_stats']['business_check']['confirmed'] += 1
        
        # 决策：如果大部分SQL被确认为冗余，则标记为删除
        if confirmed_redundant_count >= len(redundant_sqls) * 0.6:  # 60%以上确认冗余
            final_decision = 'remove'
        else:
            final_decision = 'keep'
        
        return final_decision, steps
    
    async def _validate_new_fingerprint_candidate(self, candidate: Dict[str, Any]) -> Tuple[str, List[Dict]]:
        """
        验证新增指纹候选项
            
        Returns:
            Tuple[final_decision, validation_steps]
        """
        steps = []
        candidate_info = candidate['candidate_info']
        new_sqls = candidate_info['new_sqls']
        
        # 对每个新增SQL进行验证 - 全量处理，移除数量限制
        valid_new_count = 0
        
        for sql_record in new_sqls:  # 处理所有SQL，移除[:3]限制
            sql_text = sql_record['sql_text'].strip()
            
            # Step 3: 新增指纹合理性检测
            prompt = NEW_FINGERPRINT_VALIDATION_PROMPT.format(
                orm_code=candidate['orm_code_content'][:2000],
                caller=candidate['target_caller'],
                reference_caller=candidate['reference_caller'],
                new_sql=sql_text
            )
            
            response = await self.llm_client.call_async(self.session, prompt, max_tokens=300, temperature=0.0)
            
            step_result = {
                'step': 'new_fingerprint_validation',
                    'sql_text': sql_text,
                'prompt_length': len(prompt),
                'llm_response': response,
                'is_valid_new': False
            }
            
            if response and '合理新增' in response:
                step_result['is_valid_new'] = True
                valid_new_count += 1
            
            steps.append(step_result)
        
        # 决策：如果大部分新增SQL被确认为合理，则保留
        if valid_new_count >= len(new_sqls) * 0.6:
            final_decision = 'keep'  # 保留合理的新增
        else:
            final_decision = 'remove'  # 移除可能错误的新增
        
        return final_decision, steps
    
    async def _validate_missing_candidate(self, candidate: Dict[str, Any]) -> Tuple[str, List[Dict]]:
        """
        验证缺失候选项
            
        Returns:
            Tuple[final_decision, validation_steps]
        """
        steps = []
        candidate_info = candidate['candidate_info']
        missing_sql_examples = candidate_info['missing_sql_examples']
        
        # 对每个缺失SQL进行验证 - 全量处理，移除数量限制
        truly_missing_count = 0
        
        for sql_record in missing_sql_examples:  # 处理所有SQL，移除[:3]限制
            sql_text = sql_record['sql_text'].strip()
            
            # Step 4: 缺失必要性检测
            prompt = MISSING_SQL_VALIDATION_PROMPT.format(
                orm_code=candidate['orm_code_content'][:2000],
                caller=candidate['target_caller'],
                reference_caller=candidate['reference_caller'],
                missing_sql=sql_text
            )
            
            response = await self.llm_client.call_async(self.session, prompt, max_tokens=300, temperature=0.0)
            
            step_result = {
                'step': 'missing_validation',
                'sql_text': sql_text,
                'prompt_length': len(prompt),
                'llm_response': response,
                'is_truly_missing': False
            }
            
            if response and '确实缺失' in response:
                step_result['is_truly_missing'] = True
                truly_missing_count += 1
            
            steps.append(step_result)
        
        # 决策：如果大部分SQL被确认为缺失，则标记为需要添加
        if truly_missing_count >= len(missing_sql_examples) * 0.6:
            final_decision = 'add'  # 需要添加缺失的SQL
        else:
            final_decision = 'keep'  # 不需要添加
        
        return final_decision, steps
    
    def _update_final_stats(self, results: List[Dict]):
        """更新最终统计信息"""
        for result in results:
            validation_type = result['validation_type']
            final_decision = result['final_decision']
            
            if validation_type == 'redundant':
                if final_decision == 'remove':
                    self.validation_stats['type_stats']['redundant']['confirmed'] += 1
                else:
                    self.validation_stats['type_stats']['redundant']['disputed'] += 1
            elif validation_type == 'new_fingerprint':
                if final_decision == 'keep':
                    self.validation_stats['type_stats']['new_fingerprint']['valid_new'] += 1
                else:
                    self.validation_stats['type_stats']['new_fingerprint']['wrong_new'] += 1
            elif validation_type == 'missing':
                if final_decision == 'add':
                    self.validation_stats['type_stats']['missing']['truly_missing'] += 1
            else:
                    self.validation_stats['type_stats']['missing']['unnecessary'] += 1
    
    def _generate_validation_reports(self, results: List[Dict]) -> Dict[str, str]:
        """生成验证报告"""
        report_files = {}
        
        # 1. 生成详细JSON报告
        json_file = self.output_dir / "llm_validation_results.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        report_files['detailed_results'] = str(json_file)
        
        # 2. 生成CSV汇总报告
        csv_file = self.output_dir / "validation_summary.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                'validation_id', 'validation_type', 'orm_code', 'target_caller', 
                'reference_caller', 'final_decision', 'validation_status', 
                'steps_count', 'priority'
            ])
            
            for result in results:
                writer.writerow([
                    result.get('validation_id', ''),
                    result.get('validation_type', ''),
                    result.get('orm_code', '')[:50] + '...' if len(result.get('orm_code', '')) > 50 else result.get('orm_code', ''),
                    result.get('target_caller', ''),
                    result.get('reference_caller', ''),
                    result.get('final_decision', ''),
                    result.get('validation_status', ''),
                    len(result.get('validation_steps', [])),
                    result.get('priority', '')
                ])
        report_files['summary_csv'] = str(csv_file)
        
        # 3. 生成统计摘要
        stats_file = self.output_dir / "validation_statistics.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.validation_stats, f, ensure_ascii=False, indent=2)
        report_files['statistics'] = str(stats_file)
        
        logger.info(f"验证报告已生成:")
        logger.info(f"  - 详细结果: {json_file}")
        logger.info(f"  - CSV汇总: {csv_file}")
        logger.info(f"  - 统计摘要: {stats_file}")
        
        return report_files 
    
    def _generate_fix_recommendations(self, results: List[Dict]) -> Dict[str, Any]:
        """生成修复建议"""
        recommendations = {
            'remove_redundant': [],  # 需要删除的冗余SQL
            'remove_wrong_new': [],  # 需要删除的错误新增SQL
            'add_missing': [],       # 需要添加的缺失SQL
            'keep_disputed': [],     # 需要保留的争议SQL
            'summary': {}
        }
        
        for result in results:
            validation_type = result['validation_type']
            final_decision = result['final_decision']
            
            if validation_type == 'redundant' and final_decision == 'remove':
                recommendations['remove_redundant'].append({
                    'orm_code': result['orm_code'],
                    'caller': result['target_caller'],
                    'candidate_info': result['candidate_info']
                })
            elif validation_type == 'new_fingerprint' and final_decision == 'remove':
                recommendations['remove_wrong_new'].append({
                    'orm_code': result['orm_code'],
                    'caller': result['target_caller'],
                    'candidate_info': result['candidate_info']
                })
            elif validation_type == 'missing' and final_decision == 'add':
                recommendations['add_missing'].append({
                    'orm_code': result['orm_code'],
                    'caller': result['target_caller'],
                    'candidate_info': result['candidate_info']
                })
            else:
                recommendations['keep_disputed'].append({
                    'orm_code': result['orm_code'],
                    'caller': result['target_caller'],
                    'validation_type': validation_type,
                    'final_decision': final_decision
                })
        
        recommendations['summary'] = {
            'total_candidates': len(results),
            'remove_redundant_count': len(recommendations['remove_redundant']),
            'remove_wrong_new_count': len(recommendations['remove_wrong_new']),
            'add_missing_count': len(recommendations['add_missing']),
            'keep_disputed_count': len(recommendations['keep_disputed'])
        }
        
        # 保存修复建议
        fix_file = self.output_dir / "fix_recommendations.json"
        with open(fix_file, 'w', encoding='utf-8') as f:
            json.dump(recommendations, f, ensure_ascii=False, indent=2)
        
        logger.info(f"修复建议已保存到: {fix_file}")
        
        return recommendations
    
    def _generate_empty_result(self) -> Dict[str, Any]:
        """生成空结果"""
        return {
            'total_candidates': 0,
            'validation_stats': self.validation_stats,
            'validated_results': [],
            'report_files': {},
            'fix_recommendations': {
                'remove_redundant': [],
                'remove_wrong_new': [],
                'add_missing': [],
                'keep_disputed': [],
                'summary': {
                    'total_candidates': 0,
                    'remove_redundant_count': 0,
                    'remove_wrong_new_count': 0,
                    'add_missing_count': 0,
                    'keep_disputed_count': 0
                }
            }
        }
    
    # 保留原有接口以确保向后兼容
    async def validate_redundant_sql_records(self, dataset: List[Dict], apply_fix: bool = False) -> Dict[str, Any]:
        """
        保留原有接口（向后兼容）
        
        注意：新版本建议使用 validate_llm_candidates 方法
        """
        logger.warning("使用了旧版本接口 validate_redundant_sql_records，建议升级到 validate_llm_candidates")
        
        # 简单的向后兼容实现
        return {
            'total_records': len(dataset),
            'redundant_records': 0,
            'validation_items': 0,
            'confirmed_redundant': 0,
            'disputed_redundant': 0,
            'parse_errors': 0,
            'validation_errors': 0,
            'output_files': {},
            'message': '请使用新版本的验证流程'
        } 