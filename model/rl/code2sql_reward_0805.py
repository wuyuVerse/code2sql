#!/usr/bin/env python3
"""
Code2SQL 五维度动态权重奖励函数
基于 code2sql_reward_0802 重构，新增多语句SQL惩罚维度

五个评估维度：
1. SQL 语句有效性（必选正向维度）
2. 表名/字段名一致性（必选正向维度）  
3. 关键词惩罚（可选负向维度，基于数据预处理结果）
4. 分支互斥惩罚（可选负向维度，基于冲突检测）
5. 多语句SQL惩罚（必选负向维度，始终启用）

特点：
- 固定权重归一化：两个正向维度权重固定 0.55 + 0.45 = 1.0
- 三重惩罚机制：关键词惩罚 + 分支互斥惩罚 + 多语句惩罚独立扣分
- 完全兼容VERL框架接口
- 保持异步+批量处理架构

惩罚系数调整：
- 分支互斥惩罚：0.20 → 0.70（严厉惩罚，扣70%）
- 多语句惩罚：0.10 → 0.60（严厉惩罚，扣60%）
- 关键词惩罚：0.15 → 0.20（适度提升）
- 累积惩罚：多问题并发时额外增加20%惩罚
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

# 导入四个维度的评估模块
from model.rl.eval_dimensions.sql_validity import async_evaluate_sql_validity
from model.rl.eval_dimensions.llm_consistency import async_evaluate_llm_consistency
from model.rl.eval_dimensions.keyword_alignment import async_evaluate_keyword_alignment
from model.rl.eval_dimensions.branch_exclusivity import async_evaluate_branch_exclusivity
from model.rl.eval_dimensions.multi_sql_penalty import async_evaluate_multi_sql_penalty

# 导入配置和工具函数
from model.rl.code2sql_reward_v2 import load_llm_prompts_config, load_rl_config

# 常量配置
MAX_WORKERS = 32
DEBUG_DUMP_FILE = "/data/cloud_disk_1/home/wuyu/code2sql/model/rl/reward_logs/four_dimensions_reward_detailed.jsonl"

def save_reward_result(solution_str: str,
                      ground_truth: str,
                      final_score: float,
                      details: dict,
                      extra_info: Optional[dict] = None,
                      dimension_scores: Optional[dict] = None,
                      dimension_details: Optional[dict] = None,
                      dump_path: str = DEBUG_DUMP_FILE):
    """将四维度奖励机制的完整评分详情追加写入 JSONL 文件"""
    
    # 基础信息
    record = {
        "timestamp": int(time.time()),
        "datetime": datetime.datetime.now().isoformat(),
        "reward_mechanism": "five_dimensions_v1",
        
        # 样本基础信息
        "sample_info": {
            "index": (extra_info or {}).get("index", -1),
            "function_name": (extra_info or {}).get("function_name", ""),
            "source_file": (extra_info or {}).get("source_file", ""),
            "sql_pattern_cnt": (extra_info or {}).get("sql_pattern_cnt", 0),
            "condition": (extra_info or {}).get("condition", []),
        },
        
        # 代码信息
        "code_info": {
            "orm_code": (extra_info or {}).get("orm_code", ""),
            "caller": (extra_info or {}).get("caller", ""),
            "callee": (extra_info or {}).get("callee", ""),
            "code_meta_data": (extra_info or {}).get("code_meta_data", []),
        },
        
        # 关键词分析结果
        "keyword_analysis": (extra_info or {}).get("llm_keyword_analysis", {}),
        
        # 最终评分结果
        "final_result": {
            "score": final_score,
            "score_breakdown": {
                "positive_score": details.get("positive_dimensions", {}).get("normalized_scores", {}),
                "keyword_penalty": details.get("keyword_penalty_amount", 0.0),
                "branch_penalty": details.get("branch_penalty_amount", 0.0),
                "multi_sql_penalty": details.get("multi_sql_penalty_amount", 0.0),
                "total_penalty": details.get("keyword_penalty_amount", 0.0) + details.get("branch_penalty_amount", 0.0) + details.get("multi_sql_penalty_amount", 0.0)
            }
        },
        
        # 五个维度的详细得分
        "dimension_results": {
            "validity": {
                "enabled": True,
                "score": dimension_scores.get("validity_score", 0.0) if dimension_scores else 0.0,
                "weight": dimension_details.get("validity", {}).get("weight", 0.55) if dimension_details else 0.55,
                "weighted_score": (dimension_scores.get("validity_score", 0.0) * dimension_details.get("validity", {}).get("weight", 0.55)) if dimension_scores and dimension_details else 0.0,
                "details": dimension_details.get("validity", {}) if dimension_details else {}
            },
            "consistency": {
                "enabled": True,
                "score": dimension_scores.get("consistency_score", 0.0) if dimension_scores else 0.0,
                "weight": dimension_details.get("consistency", {}).get("weight", 0.45) if dimension_details else 0.45,
                "weighted_score": (dimension_scores.get("consistency_score", 0.0) * dimension_details.get("consistency", {}).get("weight", 0.45)) if dimension_scores and dimension_details else 0.0,
                "details": dimension_details.get("consistency", {}) if dimension_details else {}
            },
            "keyword_penalty": {
                "enabled": dimension_details.get("keyword_penalty", {}).get("enabled", False) if dimension_details else False,
                "original_score": dimension_details.get("keyword_penalty", {}).get("original_score") if dimension_details else None,
                "penalty_amount": dimension_scores.get("keyword_penalty_amount", 0.0) if dimension_scores else 0.0,
                "penalty_cap": dimension_details.get("keyword_penalty", {}).get("penalty_cap", 0.15) if dimension_details else 0.15,
                "details": dimension_details.get("keyword_penalty", {}) if dimension_details else {}
            },
            "branch_penalty": {
                "enabled": dimension_details.get("branch_penalty", {}).get("enabled", False) if dimension_details else False,
                "severity": dimension_scores.get("branch_severity", 0.0) if dimension_scores else 0.0,
                "penalty_amount": dimension_scores.get("branch_penalty_amount", 0.0) if dimension_scores else 0.0,
                "penalty_cap": dimension_details.get("branch_penalty", {}).get("penalty_cap", 0.20) if dimension_details else 0.20,
                "details": dimension_details.get("branch_penalty", {}) if dimension_details else {}
            },
            "multi_sql_penalty": {
                "enabled": True,
                "original_score": dimension_scores.get("multi_sql_score", 1.0) if dimension_scores else 1.0,
                "penalty_amount": dimension_scores.get("multi_sql_penalty_amount", 0.0) if dimension_scores else 0.0,
                "penalty_cap": dimension_details.get("multi_sql_penalty", {}).get("penalty_cap", 0.50) if dimension_details else 0.50,
                "details": dimension_details.get("multi_sql_penalty", {}) if dimension_details else {}
            }
        },
        
        # 权重配置
        "weights_config": details.get("weights", {}),
        
        # 动态权重计算
        "positive_dimensions": details.get("positive_dimensions", {}),
        
        # 原始输入输出（完整版本，便于调试）
        "io_data": {
            "solution_full": solution_str,
            "ground_truth_full": ground_truth,
            "solution_length": len(solution_str),
            "ground_truth_length": len(ground_truth)
        },
        
        # 完整的原始details（向后兼容）
        "raw_details": details,
        "raw_dimension_scores": dimension_scores or {},
        "raw_dimension_details": dimension_details or {}
    }
    
    try:
        os.makedirs(os.path.dirname(dump_path), exist_ok=True)
        with open(dump_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"[WARNING] 保存调试信息失败: {e}")

async def _async_evaluate_four_dimensions(client: openai.AsyncClient, 
                                        data_source: dict, 
                                        solution_str: str, 
                                        ground_truth: str,
                                        extra_info: Optional[dict], 
                                        config: Dict[str, Any],
                                        debug_mode: bool = True) -> float:
    """
    五维度异步评估核心逻辑
    
    维度说明：
    1. SQL有效性 - 同步执行（CPU密集型，正向维度）
    2. 表名/字段一致性 - LLM异步评估（正向维度）
    3. 关键词惩罚 - 可选，基于预处理结果触发（负向惩罚）
    4. 分支互斥惩罚 - 可选，基于冲突检测触发（负向惩罚）
    5. 多语句SQL惩罚 - 始终启用，检测多条SQL拼接（负向惩罚）
    """
    
    def check_condition_flags(extra_info):
        """检查样本条件标记，决定启用哪些惩罚维度"""
        if not extra_info:
            return False, False
        
        condition_list = extra_info.get("condition", [])
        enable_keyword = "keyword" in condition_list
        enable_branch = "if-else" in condition_list
        
        return enable_keyword, enable_branch
    
    try:
        # 【新增】根据condition决定维度启用
        enable_keyword, enable_branch = check_condition_flags(extra_info)
        
        if debug_mode:
            cond_info = (extra_info or {}).get("condition", [])
            print(f"[四维度] condition标记: {cond_info}, 启用关键词:{enable_keyword}, 启用分支:{enable_branch}")
        
        # 维度1: SQL有效性评估（同步执行，因为它是CPU密集型的）
        validity_result = async_evaluate_sql_validity(solution_str, debug_mode)
        if isinstance(validity_result, tuple) and len(validity_result) == 2:
            validity_score, validity_detail = validity_result
        else:
            validity_score, validity_detail = float(validity_result), {}
        
        # 维度2-4: 根据条件动态创建异步任务
        tasks = []
        
        # 表名/字段一致性评估（必选）
        consistency_task = asyncio.create_task(
            async_evaluate_llm_consistency(client, solution_str, extra_info, config, debug_mode)
        )
        tasks.append(("consistency", consistency_task))
        
        # 多语句惩罚维度（始终启用，纯本地计算）
        multi_sql_task = asyncio.create_task(
            async_evaluate_multi_sql_penalty(solution_str, debug_mode)
        )
        tasks.append(("multi_sql", multi_sql_task))
        
        # 关键词匹配评估（条件启用）
        if enable_keyword:
            keyword_task = asyncio.create_task(
                async_evaluate_keyword_alignment(client, solution_str, extra_info, config, debug_mode)
            )
            tasks.append(("keyword", keyword_task))
            if debug_mode:
                print("[四维度] 启用关键词惩罚维度")
        else:
            keyword_result = (None, {})
            if debug_mode:
                print("[四维度] 跳过关键词惩罚维度")
        
        # 分支互斥性评估（条件启用）
        if enable_branch:
            branch_task = asyncio.create_task(
                async_evaluate_branch_exclusivity(client, solution_str, extra_info, config, debug_mode)
            )
            tasks.append(("branch", branch_task))
            if debug_mode:
                print("[四维度] 启用分支互斥惩罚维度")
        else:
            # 禁用分支惩罚时，直接视为完全符合（score=1），确保不扣分
            branch_result = (1.0, {})
            if debug_mode:
                print("[四维度] 跳过分支互斥惩罚维度")
        
        # 等待启用的异步任务完成
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        # 按任务类型写回结果
        result_idx = 0
        consistency_result = (0.0, {})  # 默认值
        multi_sql_result = (1.0, {})     # 默认值（1 表示无惩罚）
        for task_name, _ in tasks:
            if task_name == "consistency":
                consistency_result = results[result_idx] if not isinstance(results[result_idx], Exception) else (0.0, {})
            elif task_name == "keyword" and enable_keyword:
                keyword_result = results[result_idx] if not isinstance(results[result_idx], Exception) else (None, {})
            elif task_name == "branch" and enable_branch:
                branch_result = results[result_idx] if not isinstance(results[result_idx], Exception) else (0.0, {})
            elif task_name == "multi_sql":
                multi_sql_result = results[result_idx] if not isinstance(results[result_idx], Exception) else (1.0, {})
            result_idx += 1

        # 处理 multi_sql 结果（始终在 tasks 中，位序最后固定）
        if tasks and tasks[-1][0] == "multi_sql":
            multi_sql_result = results[-1] if not isinstance(results[-1], Exception) else (1.0, {})
        
        # 提取分数和详情
        if isinstance(consistency_result, tuple) and len(consistency_result) == 2:
            consistency_score, consistency_detail = consistency_result
        else:
            consistency_score, consistency_detail = float(consistency_result), {}
            
        if keyword_result and isinstance(keyword_result, tuple) and len(keyword_result) == 2 and keyword_result[0] is not None:
            keyword_score, keyword_detail = keyword_result
        else:
            keyword_score, keyword_detail = None, {}
            
        if isinstance(branch_result, tuple) and len(branch_result) == 2:
            branch_score, branch_detail = branch_result  # branch_score 越高表示越符合约束
            # 统一转换为严重度: 0=无冲突, 1=最严重
            branch_severity = max(0.0, min(1.0, 1.0 - branch_score))
        else:
            branch_score = float(branch_result)
            branch_severity = max(0.0, min(1.0, 1.0 - branch_score))
            branch_detail = {}

        if isinstance(multi_sql_result, tuple) and len(multi_sql_result) == 2:
            multi_sql_score, multi_sql_detail = multi_sql_result
        else:
            multi_sql_score, multi_sql_detail = 1.0, {}
        
        # 权重配置获取
        weights_config = config.get("reward_weights_four_dimensions", {})
        
        # 默认权重配置
        validity_weight = weights_config.get("validity_weight", 0.55)
        consistency_weight = weights_config.get("consistency_weight", 0.45)
        keyword_penalty_cap = weights_config.get("keyword_penalty_cap", 0.30)
        branch_penalty_cap = weights_config.get("branch_penalty_cap", 0.70)  # 严厉惩罚：分支冲突扣70%
        multi_sql_penalty_cap = weights_config.get("multi_sql_penalty_cap", 0.70)  # 严厉惩罚：多语句扣60%
        
        # 只有两个正向维度参与计算
        enabled_dimensions = {}
        enabled_dimensions["validity"] = validity_score * validity_weight
        enabled_dimensions["consistency"] = consistency_score * consistency_weight
        
        # 总权重固定为两个正向维度
        total_weight = validity_weight + consistency_weight
        
        if total_weight > 0:
            final_score = sum(enabled_dimensions.values()) / total_weight
        else:
            final_score = 0.0
        
        # 计算关键词惩罚
        if keyword_score is not None:
            # 有关键词时：1-score 作为惩罚程度，score越低惩罚越重
            keyword_penalty_amount = keyword_penalty_cap * (1 - keyword_score)
        else:
            # 无关键词时：不惩罚
            keyword_penalty_amount = 0.0

        # 计算多语句惩罚：score 越低惩罚越重
        multi_sql_penalty_amount = multi_sql_penalty_cap * (1 - multi_sql_score)
        
        # 应用三重惩罚（独立扣分）
        # 仅当启用了分支惩罚时才计算扣分
        branch_penalty_amount = branch_penalty_cap * branch_severity if enable_branch else 0.0
        
        # 累积惩罚机制：多个问题同时出现时加重惩罚
        total_penalty = branch_penalty_amount + keyword_penalty_amount + multi_sql_penalty_amount
        penalty_multiplier = 1.0
        active_penalties = sum([
            1 if branch_penalty_amount > 0 else 0,
            1 if keyword_penalty_amount > 0 else 0, 
            1 if multi_sql_penalty_amount > 0 else 0
        ])
        
        # 如果有2个及以上问题，加重惩罚
        if active_penalties >= 2:
            penalty_multiplier = 1.2  # 额外增加20%惩罚
            total_penalty *= penalty_multiplier
        
        final_score = max(final_score - total_penalty, 0.0)
        
        # 分数归一化和取整
        final_score = max(0.0, min(1.0, round(final_score, 2)))
        
        # 收集维度得分和详细信息
        dimension_scores = {
            "validity_score": validity_score,
            "consistency_score": consistency_score,
            "keyword_penalty_amount": keyword_penalty_amount,
            "branch_score": branch_score,
            "branch_severity": branch_severity,
            "branch_penalty_amount": branch_penalty_amount,
            "multi_sql_score": multi_sql_score,
            "multi_sql_penalty_amount": multi_sql_penalty_amount,
            "total_penalty": total_penalty,
            "penalty_multiplier": penalty_multiplier,
            "active_penalties": active_penalties,
            "enabled_dimensions": list(enabled_dimensions.keys()),
            "total_weight": total_weight
        }
        
        dimension_details = {
            "validity": {**validity_detail, "score": validity_score, "weight": validity_weight},
            "consistency": {**consistency_detail, "score": consistency_score, "weight": consistency_weight},
            "keyword_penalty": {
                **keyword_detail, 
                "original_score": keyword_score,
                "penalty_amount": keyword_penalty_amount,
                "penalty_cap": keyword_penalty_cap,
                "enabled": keyword_score is not None
            },
            "branch_penalty": {
                **branch_detail, 
                "original_score": branch_score,
                "severity": branch_severity, 
                "penalty_amount": branch_penalty_amount,
                "penalty_cap": branch_penalty_cap,
                "enabled": enable_branch
            },
            "multi_sql_penalty": {
                **multi_sql_detail,
                "original_score": multi_sql_score,
                "penalty_amount": multi_sql_penalty_amount,
                "penalty_cap": multi_sql_penalty_cap,
            }
        }
        
        # 强制打印维度得分
        keyword_display = f"-{keyword_penalty_amount:.3f}" if keyword_score is not None else "N/A"
        multiplier_display = f"(x{penalty_multiplier:.1f})" if penalty_multiplier > 1.0 else ""
        print(f"[五维度] 有效性:{validity_score:.3f} 一致性:{consistency_score:.3f} "
              f"关键词:{keyword_display} 分支:-{branch_penalty_amount:.3f} "
              f"多语句:-{multi_sql_penalty_amount:.3f} 总惩罚:-{total_penalty:.3f}{multiplier_display} 最终:{final_score:.3f}")
        
        # 保存评估结果
        details = {
            "validity_score": validity_score,
            "consistency_score": consistency_score, 
            "keyword_penalty_amount": keyword_penalty_amount,
            "branch_severity": branch_severity,
            "branch_penalty_amount": branch_penalty_amount,
            "multi_sql_penalty_amount": multi_sql_penalty_amount,
            "total_penalty": total_penalty,
            "penalty_multiplier": penalty_multiplier,
            "active_penalties": active_penalties,
            "weights": weights_config,
            "positive_dimensions": {
                "enabled_dimensions": list(enabled_dimensions.keys()),
                "total_weight": total_weight,
                "normalized_scores": {k: v/total_weight for k, v in enabled_dimensions.items()} if total_weight > 0 else {}
            }
        }
        save_reward_result(solution_str, ground_truth, final_score, details, extra_info,
                         dimension_scores=dimension_scores, dimension_details=dimension_details)
        
        return final_score
        
    except Exception as e:
        print(f"[ERROR] 四维度评估失败: {type(e).__name__} - {e}")
        if debug_mode:
            import traceback
            traceback.print_exc()
        return 0.0

def format_and_llm_reward(data_source: dict, solution_str: str, ground_truth: str, 
                         extra_info: Optional[dict] = None) -> float:
    """
    单样本奖励评估核心逻辑 - 四维度版本
    
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
        
        print(f"[API-四维度] 连接地址: {api_base}")
        
        # 加载配置
        config = load_llm_prompts_config()
        rl_config = load_rl_config()
        
        # 支持force_debug覆盖
        force_debug = (extra_info or {}).get("force_debug", False)
        debug_mode = force_debug or rl_config.get("debug_mode", False)       
        
        # 创建AsyncClient并执行评估
        async with openai.AsyncClient(base_url=api_base, api_key=api_key) as client:
            return await _async_evaluate_four_dimensions(
                client, data_source, solution_str, ground_truth, extra_info, config, debug_mode
            )
    
    try:
        # 在同步环境中启动异步评估
        return asyncio.run(async_runner())
    except Exception as e:
        print(f"[ERROR] 四维度单样本评估失败: {type(e).__name__} - {e}")
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

def code2sql_reward_four_dimensions(data_source=None, solution_str=None, ground_truth=None, extra_info=None, 
                                   data_sources=None, solution_strs=None, ground_truths=None, extra_infos=None, 
                                   return_dict=False, **kwargs):
    """
    五维度版本向后兼容接口
    
    维度包括：
    1. SQL语句有效性（必选）
    2. 表名/字段名一致性（必选）  
    3. 关键词匹配度（可选）
    4. 分支互斥惩罚（可选）
    5. 多语句SQL惩罚（必选，始终启用）
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
    
    score = code2sql_reward_four_dimensions(
        data_source=test_data_source,
        solution_str=test_solution,
        ground_truth=test_ground_truth,
        extra_info=test_extra_info
    )
    print(f"五维度测试分数: {score}") 