#!/usr/bin/env python3
"""
分支互斥奖励函数 - 单维度版本

架构设计：完全复制code2sql_reward_v2.py的三层架构
1. compute_score_batch：批量处理入口（ThreadPoolExecutor）
2. compute_score：单样本包装器
3. format_and_llm_reward：核心评估逻辑（asyncio.run + AsyncClient）

重构要点：
1. 三层清晰分工：完全对标code2sql_reward_v2的调用链
2. 统一异步：所有LLM调用都在单个AsyncClient内完成
3. 单一维度：只有分支互斥一个维度
4. 配置兼容：支持相同的配置结构
5. 接口一致：可直接替换原版奖励函数
"""

import yaml
import logging
import datetime
import sys
import os
import json
import time
import asyncio
import openai
from threading import Lock
from typing import Dict, Any, Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor

# 配置日志输出到终端
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 导入分支互斥评估模块
from model.rl.eval_dimensions.branch_exclusivity import async_evaluate_branch_exclusivity


def load_rl_config() -> Dict[str, Any]:
    """
    加载RL训练配置文件，获取调试模式等参数
    
    Returns:
        配置字典
    """
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "rl", "qwen", "qwen2_14b_rf.yaml"
        ) 
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 获取自定义奖励函数配置
        custom_reward_config = config.get("custom_reward_function", {})
        debug_mode = custom_reward_config.get("debug_mode", False)
        
        return {"debug_mode": debug_mode}
    except Exception as e:
        return {"debug_mode": False}


# 动态构造调试日志文件路径
def _build_default_dump_path() -> str:
    """写入model/rl/reward_logs/目录，文件名含日期时间"""
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.join(current_dir, "reward_logs")
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        pass
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    return os.path.join(base_dir, f"branch_exclusivity_reward_{ts}.jsonl")

# 固定写入 model/rl/reward_logs
DEBUG_DUMP_FILE = _build_default_dump_path()
_dump_lock = Lock()


def debug_print(message: str, debug_mode: bool = False):
    """调试打印函数，直接使用print确保在任何环境下都可见"""
    if debug_mode:
        print(f"[DEBUG] {message}")

# ============================= 配置加载函数 =============================

def load_llm_prompts_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载LLM提示词配置文件
    
    Args:
        config_path: 配置文件路径，如果为None则使用默认路径
        
    Returns:
        配置字典
    """
    if config_path is None:
        # 使用默认配置文件路径
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "rl", "qwen", "llm_prompts.yaml"
        )
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        debug_print(f"[配置] 加载LLM提示词配置失败: {e}")
        # 返回默认配置
        return {
            "branch_exclusivity_prompt": "默认分支互斥分析提示词",
            "llm_config": {
                "server_name": "v3",
                "max_tokens": 4096,
                "temperature": 0.0,
                "max_retries": 3,
                "retry_delay": 1.0
            }
        }


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
        "solution_preview": solution_str,
        "ground_truth_preview": ground_truth,
    }
    with _dump_lock:
        try:
            with open(dump_path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(record, ensure_ascii=False) + "\n")
                fp.flush()
                os.fsync(fp.fileno())
        except Exception as e:
            print(f"Error saving reward result: {e}")

# 全局线程池，用于批量处理
MAX_WORKERS = 32

# ============================= 统一异步评估主函数 =============================

async def _async_evaluate_branch_exclusivity_only(client: openai.AsyncClient, 
                                                  data_source: dict, 
                                                  solution_str: str, 
                                                  ground_truth: str,
                                                  extra_info: Optional[dict], 
                                                  config: Dict[str, Any],
                                                  debug_mode: bool = True) -> float:
    """
    统一异步评估分支互斥维度 - 核心评估逻辑
    
    完全复制code2sql_reward_v2的架构，但只评估分支互斥维度
    
    Args:
        client: 共享的AsyncClient实例
        data_source: 数据源信息
        solution_str: 模型响应文本
        ground_truth: 期望答案
        extra_info: 额外信息
        config: 完整配置字典
        debug_mode: 调试模式
        
    Returns:
        最终综合分数 (0.0-1.0)
    """
    try:
        # 1. 分支互斥评估（异步LLM调用）
        exclusivity_result = await async_evaluate_branch_exclusivity(
            client, solution_str, extra_info, config, debug_mode
        )
        
        if isinstance(exclusivity_result, tuple) and len(exclusivity_result) == 2:
            exclusivity_score, exclusivity_detail = exclusivity_result
        else:
            exclusivity_score, exclusivity_detail = float(exclusivity_result), {}
        
        # 提取SQL变体用于维度详情
        from utils.response_parser import recursively_extract_sql
        extracted_sqls = recursively_extract_sql(solution_str)

        # 提前提取ORM代码，便于后续维度详情使用
        orm_code = (extra_info or {}).get("orm_code", "")
        
        # 2. 由于只有一个维度，直接使用分支互斥得分作为最终得分
        final_score = exclusivity_score
        
        # 3. 分数归一化和取整
        final_score = max(0.0, min(1.0, round(final_score, 2)))
        
        # 4. 收集维度得分
        dimension_scores = {
            "branch_exclusivity_score": exclusivity_score
        }
        
        # 5. 收集维度详细信息
        dimension_details = {
            "branch_exclusivity": {
                **exclusivity_detail,
                "score": exclusivity_score,
                "sql_count": len(extracted_sqls),
                "extracted_sqls": extracted_sqls[:3],  # 最多保存3条SQL示例
                "orm_code": orm_code[:200]
            }
        }
        
        # 6. 强制打印维度得分（便于诊断）
        print(f"[SCORE] 分支互斥:{exclusivity_score:.3f} 最终:{final_score:.3f}")
        
        # 7. 调试信息输出
        if debug_mode:
            print(f"[分支互斥评估] 得分:{exclusivity_score:.2f} 最终:{final_score:.2f}")
        
        # 8. 保存评估结果（始终执行，保证日志完整）
        details = {
            "branch_exclusivity_score": exclusivity_score,
            "dimension": "branch_exclusivity_only"
        }
        save_reward_result(solution_str, ground_truth, final_score, details, extra_info,
                         dimension_scores=dimension_scores, dimension_details=dimension_details)
        
        return final_score
        
    except Exception as e:
        print(f"[ERROR] 分支互斥评估失败: {type(e).__name__} - {e}")
        if debug_mode:
            import traceback
            traceback.print_exc()
        return 0.0

# ============================= 三层架构：对标code2sql_reward_v2 =============================

def format_and_llm_reward(data_source: dict, solution_str: str, ground_truth: str, 
                         extra_info: Optional[dict] = None, return_detail: bool = False):
    """
    单样本奖励评估核心逻辑 - 对标code2sql_reward_v2的format_and_llm_reward
    
    Args:
        data_source: 数据源信息
        solution_str: 模型响应文本
        ground_truth: 期望答案
        extra_info: 额外信息
        return_detail: 是否返回详细信息
        
    Returns:
        最终奖励分数 (0.0-1.0) 或 (分数, 详细信息) 元组
    """
    async def async_runner():
        """异步执行器，管理AsyncClient生命周期"""
        # 配置API连接
        api_base = os.getenv("V3_API_URL", "http://10.0.0.31:8081/v1")
        api_key = "EMPTY"
        
        print(f"[API] 连接地址: {api_base}")
        
        # 加载配置
        config = load_llm_prompts_config()
        rl_config = load_rl_config()
        
        # 支持force_debug覆盖
        force_debug = (extra_info or {}).get("force_debug", False)
        debug_mode = force_debug or rl_config.get("debug_mode", False)       
        
        # 创建AsyncClient并执行评估
        async with openai.AsyncClient(base_url=api_base, api_key=api_key) as client:
            return await _async_evaluate_branch_exclusivity_only(
                client, data_source, solution_str, ground_truth, extra_info, config, debug_mode
            )
    
    try:
        # 在同步环境中启动异步评估
        score = asyncio.run(async_runner())
        
        if return_detail:
            # 返回详细信息
            dimension_scores = {"branch_exclusivity_score": score}
            return score, dimension_scores
        else:
            return score
    except Exception as e:
        print(f"[ERROR] 单样本评估失败: {type(e).__name__} - {e}")
        if return_detail:
            return 0.0, {"branch_exclusivity_score": 0.0}
        return 0.0

def compute_score(data_source: dict, solution_str: str, ground_truth: str, 
                 extra_info: Optional[dict] = None) -> float:
    """
    计算单个样本的奖励分数 - 对标code2sql_reward_v2的compute_score
    
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
    批量并行计算奖励分数 - 对标code2sql_reward_v2的compute_score_batch
    
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

# ============================= 向后兼容接口 =============================

def branch_exclusivity_reward(data_source=None, solution_str=None, ground_truth=None, extra_info=None, 
                              data_sources=None, solution_strs=None, ground_truths=None, extra_infos=None, 
                              return_dict=False, **kwargs):
    """
    分支互斥奖励函数主入口
    
    完全对标code2sql_reward_v2的参数结构和返回格式
    """
    # 判断调用模式
    if data_sources is not None and solution_strs is not None:
        # 批量处理模式
        if return_dict:
            # 收集所有维度得分用于可视化
            results = compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos)
            
            # 分离维度得分（只有分支互斥一个维度）
            branch_exclusivity_scores = []
            
            for i, (data_source, solution_str, ground_truth, extra_info) in enumerate(zip(data_sources, solution_strs, ground_truths, extra_infos)):
                # 调用单样本获取详细得分
                try:
                    result = format_and_llm_reward(data_source, solution_str, ground_truth, extra_info, return_detail=True)
                    if isinstance(result, tuple):
                        final_score, dimension_scores = result
                        branch_exclusivity_scores.append(dimension_scores.get("branch_exclusivity_score", 0.0))
                    else:
                        branch_exclusivity_scores.append(0.0)
                except:
                    branch_exclusivity_scores.append(0.0)
            
            return {
                "reward_tensor": results,  # 保持和原版相同的结构
                "reward_extra_info": {
                    "branch_exclusivity": branch_exclusivity_scores
                }
            }
        else:
            return compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos)
    else:
        # 单样本处理模式
        if data_source is None or solution_str is None or ground_truth is None:
            print("[错误] 单样本调用时，data_source、solution_str、ground_truth参数不能为None")
            if return_dict:
                return {"score": 0.0, "branch_exclusivity": 0.0}
            return 0.0
        
        if return_dict:
            result = format_and_llm_reward(data_source, solution_str, ground_truth, extra_info, return_detail=True)
            if isinstance(result, tuple):
                final_score, dimension_scores = result
                return {
                    "score": final_score,
                    "branch_exclusivity": dimension_scores.get("branch_exclusivity_score", 0.0)
                }
            else:
                return {"score": result, "branch_exclusivity": 0.0}
        else:
            return compute_score(data_source, solution_str, ground_truth, extra_info)

# 函数别名（向后兼容）
compute_single_score = compute_score
compute_score_batch_exclusive = compute_score_batch 