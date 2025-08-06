#!/usr/bin/env python3
"""
Code2SQL 奖励函数 0802版本 - 融合多维度评估

融合架构：
1. 继承code2sql_reward_v2的四个维度：SQL有效性、LLM一致性、关键词对齐、控制流惩罚
2. 新增branch_exclusivity_reward的分支互斥性维度
3. 统一异步评估框架，五维度并发执行
4. 加权平均计算最终分数
5. 完全兼容VERL框架接口
"""

import os
import sys
import time
import json
import yaml
import logging
import datetime
import asyncio
import openai
import torch
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# 配置日志输出到终端
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 导入评估维度模块
from model.rl.eval_dimensions.sql_validity import async_evaluate_sql_validity
from model.rl.eval_dimensions.llm_consistency import async_evaluate_llm_consistency
from model.rl.eval_dimensions.keyword_alignment import async_evaluate_keyword_alignment
from model.rl.eval_dimensions.control_flow_penalty import async_evaluate_control_flow_penalty
from model.rl.eval_dimensions.branch_exclusivity import async_evaluate_branch_exclusivity

# 导入配置和工具函数
from model.rl.code2sql_reward_v2 import load_llm_prompts_config, load_rl_config

# 常量配置
MAX_WORKERS = 32
DEBUG_DUMP_FILE = "/data/local_disk3/zuowei/verl-main/reward_logs/code2sql_reward_0802_debug.jsonl"

def save_reward_result(solution_str: str,
                      ground_truth: str,
                      final_score: float,
                      details: dict,
                      extra_info: Optional[dict] = None,
                      dimension_scores: Optional[dict] = None,
                      dimension_details: Optional[dict] = None,
                      dump_path: str = DEBUG_DUMP_FILE):
    """将评分详情追加写入 JSONL 文件"""
    record = {
        "timestamp": int(time.time()),
        "index": (extra_info or {}).get("index", -1),
        "function_name": (extra_info or {}).get("function_name", ""),
        "orm_code": (extra_info or {}).get("orm_code", ""),
        "score": final_score,
        "dimension_scores": dimension_scores or {},
        "dimension_details": dimension_details or {},
        "details": details,
        "solution_preview": solution_str[:500],
        "ground_truth_preview": ground_truth[:500],
    }
    
    try:
        os.makedirs(os.path.dirname(dump_path), exist_ok=True)
        with open(dump_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"[WARNING] 保存调试信息失败: {e}")

async def _async_evaluate_all_dimensions(client: openai.AsyncClient, 
                                        data_source: dict, 
                                        solution_str: str, 
                                        ground_truth: str,
                                        extra_info: Optional[dict], 
                                        config: Dict[str, Any],
                                        debug_mode: bool = True) -> float:
    """
    统一异步评估所有维度
    """
    try:
        # 1. SQL有效性评估（同步执行，因为它是CPU密集型的）
        validity_result = async_evaluate_sql_validity(solution_str, debug_mode)
        if isinstance(validity_result, tuple) and len(validity_result) == 2:
            validity_score, validity_detail = validity_result
        else:
            validity_score, validity_detail = float(validity_result), {}
        
        # 2. 并发执行所有异步LLM评估任务
        tasks = []
        
        # LLM一致性评估
        consistency_task = asyncio.create_task(
            async_evaluate_llm_consistency(client, solution_str, extra_info, config, debug_mode)
        )
        tasks.append(consistency_task)
        
        # 关键词对齐评估
        keyword_task = asyncio.create_task(
            async_evaluate_keyword_alignment(client, solution_str, extra_info, config, debug_mode)
        )
        tasks.append(keyword_task)
        
        # 控制流惩罚评估
        penalty_task = asyncio.create_task(
            async_evaluate_control_flow_penalty(client, solution_str, extra_info, config, debug_mode)
        )
        tasks.append(penalty_task)
        
        # 分支互斥性评估
        branch_task = asyncio.create_task(
            async_evaluate_branch_exclusivity(client, solution_str, extra_info, config, debug_mode)
        )
        tasks.append(branch_task)
        
        # 等待所有异步任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 解析结果
        consistency_result = results[0] if not isinstance(results[0], Exception) else (0.0, {})
        keyword_result = results[1] if not isinstance(results[1], Exception) else (None, {})
        penalty_result = results[2] if not isinstance(results[2], Exception) else (0.0, {})
        branch_result = results[3] if not isinstance(results[3], Exception) else (0.0, {})
        
        # 提取分数和详情
        consistency_score, consistency_detail = consistency_result
        keyword_score, keyword_detail = keyword_result if keyword_result[0] is not None else (None, {})
        penalty_severity, penalty_detail = penalty_result
        branch_score, branch_detail = branch_result
        
        # 2. 权重配置获取
        weights_config = config.get("reward_weights_0802", {})
        
        # 默认权重配置
        validity_weight = weights_config.get("validity_weight", 0.25)
        consistency_weight = weights_config.get("consistency_weight", 0.20)
        keyword_weight = weights_config.get("keyword_weight", 0.15)
        branch_weight = weights_config.get("branch_weight", 0.20)
        penalty_cap = weights_config.get("penalty_cap", 0.20)
        
        # 3. 分数计算和加权
        if keyword_score is None:
            # 没有关键词时，重新分配权重到其他维度
            total_weight = validity_weight + consistency_weight + branch_weight
            final_score = (validity_score * validity_weight + 
                          consistency_score * consistency_weight + 
                          branch_score * branch_weight) / total_weight if total_weight > 0 else 0.0
        else:
            # 有关键词时，使用四维度加权
            final_score = (validity_score * validity_weight + 
                          consistency_score * consistency_weight + 
                          keyword_score * keyword_weight +
                          branch_score * branch_weight)
        
        # 4. 应用控制流惩罚
        penalty_amount = penalty_cap * penalty_severity
        final_score = max(final_score - penalty_amount, 0.0)
        
        # 5. 分数归一化和取整
        final_score = max(0.0, min(1.0, round(final_score, 2)))
        
        # 6. 收集维度得分和详细信息
        dimension_scores = {
            "validity_score": validity_score,
            "consistency_score": consistency_score,
            "keyword_score": keyword_score,
            "branch_score": branch_score,
            "penalty_severity": penalty_severity,
            "penalty_amount": penalty_amount
        }
        
        dimension_details = {
            "validity": {**validity_detail, "score": validity_score},
            "consistency": {**consistency_detail, "score": consistency_score},
            "keyword": {**keyword_detail, "score": keyword_score, "has_keywords": keyword_score is not None},
            "branch": {**branch_detail, "score": branch_score},
            "penalty": {**penalty_detail, "score": penalty_severity, "penalty_amount": penalty_amount}
        }
        
        # 7. 强制打印维度得分
        print(f"[SCORE-0802] 有效性:{validity_score:.3f} 一致性:{consistency_score:.3f} "
              f"关键词:{keyword_score} 分支:{branch_score:.3f} 惩罚:{penalty_amount:.3f} 最终:{final_score:.3f}")
        
        # 8. 保存评估结果
        details = {
            "validity_score": validity_score,
            "consistency_score": consistency_score, 
            "keyword_score": keyword_score,
            "branch_score": branch_score,
            "penalty_severity": penalty_severity,
            "penalty_amount": penalty_amount,
            "weights": weights_config
        }
        save_reward_result(solution_str, ground_truth, final_score, details, extra_info,
                         dimension_scores=dimension_scores, dimension_details=dimension_details)
        
        return final_score
        
    except Exception as e:
        print(f"[ERROR] 综合评估失败: {type(e).__name__} - {e}")
        if debug_mode:
            import traceback
            traceback.print_exc()
        return 0.0

def format_and_llm_reward(data_source: dict, solution_str: str, ground_truth: str, 
                         extra_info: Optional[dict] = None) -> float:
    """
    单样本奖励评估核心逻辑 - 融合五维度评估
    
    Args:
        data_source: 数据源信息
        solution_str: 模型响应文本
        ground_truth: 期望答案
        extra_info: 额外信息
        
    Returns:
        最终奖励分数 (0.0-1.0)
    """
    async def async_runner():
        """异步执行器，管理AsyncClient生命周期"""
        # 配置API连接
        api_base = os.getenv("V3_API_URL", "http://10.0.0.31:8081/v1")
        api_key = "EMPTY"
        
        print(f"[API-0802] 连接地址: {api_base}")
        
        # 加载配置
        config = load_llm_prompts_config()
        rl_config = load_rl_config()
        
        # 支持force_debug覆盖
        force_debug = (extra_info or {}).get("force_debug", False)
        debug_mode = force_debug or rl_config.get("debug_mode", False)       
        
        # 创建AsyncClient并执行评估
        async with openai.AsyncClient(base_url=api_base, api_key=api_key) as client:
            return await _async_evaluate_all_dimensions(
                client, data_source, solution_str, ground_truth, extra_info, config, debug_mode
            )
    
    try:
        # 在同步环境中启动异步评估
        return asyncio.run(async_runner())
    except Exception as e:
        print(f"[ERROR] 单样本评估失败: {type(e).__name__} - {e}")
        return 0.0

def compute_score(data_source: dict, solution_str: str, ground_truth: str, 
                 extra_info: Optional[dict] = None) -> float:
    """
    计算单个样本的奖励分数
    
    Args:
        data_source: 数据源信息
        solution_str: 模型响应文本
        ground_truth: 期望答案
        extra_info: 额外信息
        
    Returns:
        最终奖励分数 (0.0-1.0)
    """
    return format_and_llm_reward(data_source, solution_str, ground_truth, extra_info)

def compute_score_batch(data_sources: List[dict], solution_strs: List[str], 
                       ground_truths: List[str], extra_infos: List[Optional[dict]]) -> List[float]:
    """
    批量并行计算奖励分数
    
    Args:
        data_sources: 数据源信息列表
        solution_strs: 模型响应文本列表
        ground_truths: 期望答案列表
        extra_infos: 额外信息列表
        
    Returns:
        每个样本对应的最终奖励分数列表
    """
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for data_source, solution_str, ground_truth, extra_info in zip(data_sources, solution_strs, ground_truths, extra_infos):
            future = executor.submit(compute_score, data_source, solution_str, ground_truth, extra_info)
            futures.append(future)

        results = [future.result() for future in futures]

    return results

def code2sql_reward_0802(data_source=None, solution_str=None, ground_truth=None, extra_info=None, 
                        data_sources=None, solution_strs=None, ground_truths=None, extra_infos=None, 
                        return_dict=False, **kwargs):
    """
    0802版本向后兼容接口 - 融合五维度评估
    
    维度包括：
    1. SQL有效性 (来自code2sql_reward_v2)
    2. LLM一致性 (来自code2sql_reward_v2)  
    3. 关键词对齐 (来自code2sql_reward_v2)
    4. 控制流惩罚 (来自code2sql_reward_v2)
    5. 分支互斥性 (来自branch_exclusivity_reward)
    """
    # 判断调用模式
    if data_sources is not None and solution_strs is not None:
        # 批量处理模式
        if return_dict:
            results = compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos)
            return {
                "reward_tensor": torch.tensor(results, dtype=torch.float32),
                "reward_extra_info": {
                    "final_scores": results
                }
            }
        else:
            return compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos)
    else:
        # 单样本处理模式
        if data_source is None or solution_str is None or ground_truth is None:
            print("[错误] 单样本调用时，data_source、solution_str、ground_truth参数不能为None")
            if return_dict:
                return {"score": 0.0}
            return 0.0
        
        if return_dict:
            result = compute_score(data_source, solution_str, ground_truth, extra_info)
            return {"score": result}
        else:
            return compute_score(data_source, solution_str, ground_truth, extra_info)

if __name__ == "__main__":
    # 测试用例
    test_data_source = {"test": "data"}
    test_solution = "SELECT * FROM users WHERE id = 1;"
    test_ground_truth = "查询用户信息"
    test_extra_info = {"orm_code": "db.Model(&User{}).Where(\"id = ?\", 1).Find(&users)"}
    
    score = code2sql_reward_0802(
        data_source=test_data_source,
        solution_str=test_solution,
        ground_truth=test_ground_truth,
        extra_info=test_extra_info
    )
    print(f"测试分数: {score}")
