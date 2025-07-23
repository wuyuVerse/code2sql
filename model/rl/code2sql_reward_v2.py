#!/usr/bin/env python3
"""
Code2SQL 奖励函数 V2 - 三层架构版本（对标composite_reward）

架构设计：
1. compute_score_batch：批量处理入口（ThreadPoolExecutor）
2. compute_score：单样本包装器
3. format_and_llm_reward：核心评估逻辑（asyncio.run + AsyncClient）

重构要点：
1. 三层清晰分工：完全对标composite_reward的调用链
2. 统一异步：所有LLM调用都在单个AsyncClient内完成
3. 维度拆分：清晰的模块边界和职责分离  
4. 配置兼容：支持新旧权重配置，优雅向前兼容
5. 接口一致：可直接替换composite_reward的YAML配置
"""
# 在第17行附近添加
import yaml  # 新增：解决NameError
import logging
import datetime

# 配置日志输出到终端
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
import sys
import os
import json
import time
import asyncio
import openai
import yaml
import logging
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

# 导入评估维度模块
from .eval_dimensions.sql_validity import async_evaluate_sql_validity
from .eval_dimensions.llm_consistency import async_evaluate_llm_consistency
from .eval_dimensions.keyword_alignment import async_evaluate_keyword_alignment
from .eval_dimensions.control_flow_penalty import async_evaluate_control_flow_penalty


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


# 动态构造调试日志文件路径：优先读取 REWARD_DUMP_FILE；否则按日期+版本命名写入指定目录
def _build_default_dump_path() -> str:
    """写入model/rl/reward_logs/目录，文件名含日期时间"""
    # 获取当前文件所在目录的reward_logs子目录
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.join(current_dir, "reward_logs")
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        pass  # 如果创建失败则继续使用当前工作目录
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    return os.path.join(base_dir, f"reward_{ts}_v2.jsonl")

# 固定写入 model/rl/reward_logs，不再依赖环境变量
DEBUG_DUMP_FILE = _build_default_dump_path()
_dump_lock = Lock()





# 替换第75-78行的debug_print函数
def debug_print(message: str, debug_mode: bool = False):
    """调试打印函数，直接使用print确保在任何环境下都可见"""
    if debug_mode:
        print(f"[DEBUG] {message}")  # 直接print，确保终端可见

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
            "table_extraction_prompt": "请从以下GORM代码中提取所有涉及的表名。\n\n**函数名称：** {function_name}\n**调用者：** {caller}\n\n**ORM代码：**\n```go\n{orm_code}\n```\n\n**代码元数据：**\n{meta_data_str}\n\n请以JSON格式输出，格式如下：\n```json\n{{\n    \"tables\": [\"表名1\", \"表名2\", ...]\n}}\n```\n\n只输出JSON格式，不要其他内容：",
            "column_extraction_prompt": "请从以下GORM代码中提取所有涉及的字段名。\n\n**函数名称：** {function_name}\n**调用者：** {caller}\n\n**ORM代码：**\n```go\n{orm_code}\n```\n\n**代码元数据：**\n{meta_data_str}\n\n请以JSON格式输出，格式如下：\n```json\n{{\n    \"columns\": [\"字段名1\", \"字段名2\", ...]\n}}\n```\n\n只输出JSON格式，不要其他内容：",
            "llm_config": {
                "server_name": "v3",
                "max_tokens": 1024,
                "temperature": 0.0,
                "max_retries": 3,
                "retry_delay": 1.0
            },
            "consistency_config": {
                "table_weight": 0.6,
                "column_weight": 0.4,
                "consistency_weight": 0.4,
                "validity_weight": 0.6
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
        "solution_preview": solution_str,  # 保留完整内容
        "ground_truth_preview": ground_truth,  # 保留完整内容
    }
    with _dump_lock:
        try:
            with open(dump_path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(record, ensure_ascii=False) + "\n")
                # 立即刷新到磁盘，确保实时可见
                fp.flush()
                os.fsync(fp.fileno())
        except Exception as e:
            # 在无法写入文件时，打印错误但程序不中断
            print(f"Error saving reward result: {e}")

# 全局线程池，用于批量处理
MAX_WORKERS = 32

# ============================= 统一异步评估主函数 =============================

async def _async_evaluate_all_dimensions(client: openai.AsyncClient, 
                                        data_source: dict, 
                                        solution_str: str, 
                                        ground_truth: str,
                                        extra_info: Optional[dict], 
                                        config: Dict[str, Any],
                                        debug_mode: bool = True) -> float:
    """
    统一异步评估所有维度 - 核心重构逻辑
    
    参考composite_reward.py的设计：
    1. 单个AsyncClient贯穿所有LLM调用
    2. 并发执行所有异步任务
    3. 统一权重计算和分数归一化
    
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
        # 1. SQL有效性评估（同步，CPU密集型）
        validity_result = async_evaluate_sql_validity(solution_str, debug_mode)
        if isinstance(validity_result, tuple) and len(validity_result) == 2:
            validity_score, validity_detail = validity_result
        else:
            validity_score, validity_detail = float(validity_result), {}
        
        # 提取SQL变体用于维度详情
        from utils.response_parser import recursively_extract_sql
        extracted_sqls = recursively_extract_sql(solution_str)

        # 提前提取ORM代码与关键词，便于后续维度详情使用
        orm_code = (extra_info or {}).get("orm_code", "")
        matched_keywords = (extra_info or {}).get("llm_keyword_analysis", {}).get("matched_keywords", []) if extra_info else []
        
        # 2. 并发执行所有异步LLM评估任务
        tasks = []
        
        # LLM一致性评估
        consistency_task = asyncio.create_task(
            async_evaluate_llm_consistency(client, solution_str, extra_info, config, debug_mode)
        )
        tasks.append(consistency_task)
        
        # 关键词对齐评估（可选）
        keyword_task = asyncio.create_task(
            async_evaluate_keyword_alignment(client, solution_str, extra_info, config, debug_mode)
        )
        tasks.append(keyword_task)
        
        # 控制流惩罚评估（可选）
        penalty_task = asyncio.create_task(
            async_evaluate_control_flow_penalty(client, solution_str, extra_info, config, debug_mode)
        )
        tasks.append(penalty_task)
        
        # 等待所有异步任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果，确保异常安全，同时提取详细信息
        consistency_score, consistency_detail = 0.0, {}
        keyword_score, keyword_detail = None, {}
        penalty_severity, penalty_detail = 0.0, {}
        
        if len(results) >= 1 and not isinstance(results[0], Exception):
            if isinstance(results[0], tuple) and len(results[0]) == 2:
                consistency_score, consistency_detail = results[0]
            else:
                consistency_score = float(results[0]) if results[0] is not None else 0.0
        elif isinstance(results[0], Exception):
            print(f"[ERROR] LLM一致性评估失败: {type(results[0]).__name__} - {results[0]}")
            
        if len(results) >= 2 and not isinstance(results[1], Exception):
            if isinstance(results[1], tuple) and len(results[1]) == 2:
                keyword_score, keyword_detail = results[1]
            else:
                keyword_score = float(results[1]) if results[1] is not None else None
        elif isinstance(results[1], Exception):
            print(f"[ERROR] 关键词对齐评估失败: {type(results[1]).__name__} - {results[1]}")
            
        if len(results) >= 3 and not isinstance(results[2], Exception):
            if isinstance(results[2], tuple) and len(results[2]) == 2:
                penalty_severity, penalty_detail = results[2]
            else:
                penalty_severity = float(results[2]) if results[2] is not None else 0.0
        elif isinstance(results[2], Exception):
            print(f"[ERROR] 控制流惩罚评估失败: {type(results[2]).__name__} - {results[2]}")
        
        # 3. 权重配置获取（优先使用新配置，向后兼容旧配置）
        weights_config = config.get("reward_weights", {})
        old_consistency_config = config.get("consistency_config", {})
        
        # 权重优先级：reward_weights > consistency_config > 默认值
        validity_weight = weights_config.get("validity_weight", 
                                           old_consistency_config.get("validity_weight", 0.3))
        consistency_weight = weights_config.get("consistency_weight", 
                                               old_consistency_config.get("consistency_weight", 0.2))
        keyword_weight = weights_config.get("keyword_weight", 
                                           old_consistency_config.get("keyword_weight", 0.5))
        
        penalty_config = config.get("control_flow_penalty", {})
        penalty_cap = penalty_config.get("penalty_cap", 0.3)
        
        # 4. 分数计算和加权
        if keyword_score is None:
            # 没有关键词时，重新分配权重
            total_weight = validity_weight + consistency_weight
            final_score = (validity_score * validity_weight + consistency_score * consistency_weight) / total_weight if total_weight > 0 else 0.0
        else:
            # 有关键词时，使用三维度加权
            final_score = (validity_score * validity_weight + 
                          consistency_score * consistency_weight + 
                          keyword_score * keyword_weight)
        
        # 5. 应用控制流惩罚
        penalty_amount = penalty_cap * penalty_severity
        final_score = max(final_score - penalty_amount, 0.0)
        
        # 6. 分数归一化和取整
        final_score = max(0.0, min(1.0, round(final_score, 2)))
        
        # 7. 收集维度得分和详细信息
        dimension_scores = {
            "validity_score": validity_score,
            "consistency_score": consistency_score,
            "keyword_score": keyword_score,
            "penalty_severity": penalty_severity,
            "penalty_amount": penalty_amount
        }
        
        # 8. 收集维度详细信息
        dimension_details = {
            "validity": {
                **validity_detail,
                "score": validity_score,
                "sql_count": len(extracted_sqls),
                "extracted_sqls": extracted_sqls[:3]  # 最多保存3条SQL示例
            },
            "consistency": {
                **consistency_detail,
                "score": consistency_score,
                "orm_code": orm_code[:200]
            },
            "keyword": {
                **keyword_detail,
                "score": keyword_score,
                "has_keywords": keyword_score is not None,
                "matched_keywords": matched_keywords
            },
            "penalty": {
                **penalty_detail,
                "score": penalty_severity,
                "penalty_amount": penalty_amount,
                "enabled": penalty_severity > 0 or penalty_amount > 0
            }
        }
        
        # 9. 强制打印维度得分（便于诊断）
        print(f"[SCORE] 有效性:{validity_score:.3f} 一致性:{consistency_score:.3f} 关键词:{keyword_score} 惩罚:{penalty_amount:.3f} 最终:{final_score:.3f}")
        
        # 10. 调试信息输出
        if debug_mode:
            print(f"[综合评估] 有效性:{validity_score:.2f} 一致性:{consistency_score:.2f} "
                  f"关键词:{keyword_score} 惩罚:{penalty_amount:.2f} 最终:{final_score:.2f}")
        
        # 11. 保存评估结果（始终执行，保证日志完整）
        details = {
            "validity_score": validity_score,
            "consistency_score": consistency_score, 
            "keyword_score": keyword_score,
            "penalty_severity": penalty_severity,
            "penalty_amount": penalty_amount,
            "weights": weights_config,
            "penalty_config": penalty_config
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

# ============================= 三层架构：对标composite_reward =============================

def format_and_llm_reward(data_source: dict, solution_str: str, ground_truth: str, 
                         extra_info: Optional[dict] = None) -> float:
    """
    单样本奖励评估核心逻辑 - 对标composite_reward的format_and_llm_reward
    
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
        api_base = os.getenv("V3_API_URL", "http://212.64.90.3:8081/v1")  # 使用环境变量
        api_key = "EMPTY"
        
        print(f"[API] 连接地址: {api_base}")  # 始终打印API地址
        
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
    计算单个样本的奖励分数 - 对标composite_reward的compute_score
    
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
    批量并行计算奖励分数 - 对标composite_reward的compute_score_batch
    
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

def code2sql_reward_v2(data_source=None, solution_str=None, ground_truth=None, extra_info=None, 
                      data_sources=None, solution_strs=None, ground_truths=None, extra_infos=None, 
                      return_dict=False, **kwargs):
    """
    V2版本向后兼容接口
    
    保持原有的参数分支判断逻辑，便于现有代码无感切换
    """
    # 判断调用模式
    if data_sources is not None and solution_strs is not None:
        # 批量处理模式
        if return_dict:
            # 收集所有维度得分用于可视化
            results = compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos)
            
            # 分离维度得分
            validity_scores = []
            consistency_scores = []
            keyword_scores = []
            penalty_scores = []
            
            for i, (data_source, solution_str, ground_truth, extra_info) in enumerate(zip(data_sources, solution_strs, ground_truths, extra_infos)):
                # 调用单样本获取详细得分
                try:
                    result = format_and_llm_reward(data_source, solution_str, ground_truth, extra_info, return_detail=True)
                    if isinstance(result, tuple):
                        final_score, dimension_scores = result
                        validity_scores.append(dimension_scores.get("validity_score", 0.0))
                        consistency_scores.append(dimension_scores.get("consistency_score", 0.0))
                        keyword_scores.append(dimension_scores.get("keyword_score", 0.0) if dimension_scores.get("keyword_score") is not None else 0.0)
                        penalty_scores.append(dimension_scores.get("penalty_severity", 0.0))
                    else:
                        # 如果没有详细得分，使用默认值
                        validity_scores.append(0.0)
                        consistency_scores.append(0.0)
                        keyword_scores.append(0.0)
                        penalty_scores.append(0.0)
                except:
                    validity_scores.append(0.0)
                    consistency_scores.append(0.0)
                    keyword_scores.append(0.0)
                    penalty_scores.append(0.0)
            
            return {
                "reward_tensor": torch.tensor(results, dtype=torch.float32),
                "reward_extra_info": {
                    "validity": validity_scores,
                    "consistency": consistency_scores,
                    "keyword": keyword_scores,
                    "penalty": penalty_scores
                }
            }
        else:
            return compute_score_batch(data_sources, solution_strs, ground_truths, extra_infos)
    else:
        # 单样本处理模式
        if data_source is None or solution_str is None or ground_truth is None:
            print("[错误] 单样本调用时，data_source、solution_str、ground_truth参数不能为None")
            if return_dict:
                return {"score": 0.0, "validity": 0.0, "consistency": 0.0, "keyword": 0.0, "penalty": 0.0}
            return 0.0
        
        if return_dict:
            result = format_and_llm_reward(data_source, solution_str, ground_truth, extra_info, return_detail=True)
            if isinstance(result, tuple):
                final_score, dimension_scores = result
                return {
                    "score": final_score,
                    "validity": dimension_scores.get("validity_score", 0.0),
                    "consistency": dimension_scores.get("consistency_score", 0.0),
                    "keyword": dimension_scores.get("keyword_score", 0.0) if dimension_scores.get("keyword_score") is not None else 0.0,
                    "penalty": dimension_scores.get("penalty_severity", 0.0)
                }
            else:
                return {"score": result, "validity": 0.0, "consistency": 0.0, "keyword": 0.0, "penalty": 0.0}
        else:
            return compute_score(data_source, solution_str, ground_truth, extra_info)

# V2函数别名（向后兼容）
compute_single_score_v2 = compute_score
compute_score_batch_v2 = compute_score_batch
