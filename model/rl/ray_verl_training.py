#!/usr/bin/env python3
"""
Ray VERL 强化学习训练启动脚本
专门用于多节点分布式训练，使用 ray job submit
"""

import os
import sys
import logging
import yaml
import subprocess
import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import asyncio

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data_processing.converter.rl_data_converter import RLDataConverter

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO,
    )

def load_config(config_path: str) -> Dict[str, Any]:
    """加载YAML配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config

def expand_env_vars(value: Any) -> Any:
    """递归展开环境变量"""
    if isinstance(value, str):
        return os.path.expandvars(value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    else:
        return value

def build_train_files_list(config: Dict[str, Any]) -> str:
    """构建训练文件列表字符串"""
    data_config = config.get("data", {})
    
    if "train_files" in data_config:
        train_files = data_config["train_files"]
        if isinstance(train_files, str):
            return train_files
        elif isinstance(train_files, list):
            return str(train_files).replace("'", '"')
    
    # 向后兼容
    train_files = []
    if "gsm8k_train_path" in data_config:
        train_files.append(data_config["gsm8k_train_path"])
    if "math_train_path" in data_config:
        train_files.append(data_config["math_train_path"])
    
    return str(train_files).replace("'", '"')

def build_test_files_list(config: Dict[str, Any]) -> str:
    """构建测试文件列表字符串"""
    data_config = config.get("data", {})
    
    if "val_files" in data_config:
        val_files = data_config["val_files"]
        if isinstance(val_files, str):
            return val_files
        elif isinstance(val_files, list):
            return str(val_files).replace("'", '"')
    
    # 向后兼容
    test_files = []
    if "gsm8k_test_path" in data_config:
        test_files.append(data_config["gsm8k_test_path"])
    if "math_test_path" in data_config:
        test_files.append(data_config["math_test_path"])
    
    return str(test_files).replace("'", '"')

def flatten_config(config: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """将嵌套配置展平为点分隔的键值对"""
    items = []
    for k, v in config.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_config(v, new_key, sep=sep).items())
        elif isinstance(v, list) and all(isinstance(item, str) for item in v):
            items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)

def build_runtime_env(config: Dict[str, Any]) -> Dict[str, Any]:
    """构建Ray运行时环境配置"""
    env_config = config.get("environment", {})
    
    # 基础环境变量（移除会冲突的NCCL_DEBUG）
    env_vars = {
        "PYTHONPATH": str(project_root),
        "CUDA_VISIBLE_DEVICES": "0,1,2,3,4,5,6,7",
        "HF_MODULES_CACHE": env_config.get("HF_MODULES_CACHE", f"{project_root}/saves/rl/hf_modules_cache"),
        "TRANSFORMERS_CACHE": env_config.get("TRANSFORMERS_CACHE", f"{project_root}/saves/rl/transformers_cache"),
        "HF_HOME": env_config.get("HF_HOME", f"{project_root}/saves/rl/huggingface"),
        "VERL_SAVE_DIR": env_config.get("VERL_SAVE_DIR", f"{project_root}/saves/rl"),
        "GLOO_SOCKET_IFNAME": "eth0",
        "NCCL_SOCKET_IFNAME": "eth0",
        "NCCL_IB_DISABLE": "1",
        "GLOO_SOCKET_FAMILY": "AF_INET",
        # "NCCL_DEBUG": "INFO",
    }
    
    # 添加配置中的环境变量
    env_vars.update({k: str(v) for k, v in env_config.items()})
    
    # 排除大文件和不必要的目录
    excludes = [
        # 大型日志文件
        "files_to_transfer.txt",
        "model/rl/reward_*.jsonl",
        "model/rl/reward_logs/",
        "logs/",
        "workflow_output*/",
        "rerun_outputs/",
        
        # Git相关
        ".git/",
        ".gitignore",
        
        # 缓存和临时文件
        "__pycache__/",
        "*.pyc",
        ".pytest_cache/",
        "*.log",
        "nohup.out",
        
        # 数据文件
        "datasets/",
        "saves/",
        "*.parquet",
        "*.json",
        "*.jsonl",
        
        # 其他大文件
        "*.zip",
        "*.tar.gz",
        "*.model",
        "*.bin",
        "*.safetensors"
    ]
    
    runtime_env = {
        "working_dir": str(project_root),
        "excludes": excludes,
        "env_vars": env_vars,
        "pip": [
            "torch",
            "transformers", 
            "datasets",
            "accelerate",
        ]
    }
    
    return runtime_env

async def run_data_conversion_async(config: Dict[str, Any], logger: logging.Logger):
    """运行数据转换步骤"""
    try:
        data_conversion_config = config.get("data_conversion", {})
        auto_convert = data_conversion_config.get("auto_convert", True)
        
        if not auto_convert:
            logger.info("跳过数据转换步骤")
            return None
        
        logger.info("开始运行数据转换...")
        
        converter = RLDataConverter()
        
        workflow_dir = data_conversion_config.get("workflow_dir")
        if workflow_dir:
            workflow_dir = Path(workflow_dir)
            if not workflow_dir.is_absolute():
                workflow_dir = project_root / workflow_dir
        
        output_name = data_conversion_config.get("output_name")
        val_ratio = data_conversion_config.get("val_ratio", 0.1)
        
        train_path, val_path, dataset_info = await converter.run_conversion(
            workflow_dir=workflow_dir,
            output_name=output_name,
            val_ratio=val_ratio
        )
        
        logger.info(f"数据转换完成:")
        logger.info(f"  训练集: {train_path}")
        logger.info(f"  验证集: {val_path}")
        logger.info(f"  训练样本数: {dataset_info['train']['num_samples']}")
        logger.info(f"  验证样本数: {dataset_info['val']['num_samples']}")
        
        return str(train_path), str(val_path)
        
    except Exception as e:
        logger.error(f"数据转换失败: {e}")
        return None

def build_ray_job_command(config: Dict[str, Any], converted_data_paths: Optional[Tuple[str, str]] = None, 
                         extra_args: Optional[List[str]] = None) -> List[str]:
    """构建Ray Job Submit命令"""
    # 展开环境变量
    config = expand_env_vars(config)
    
    # 构建运行时环境
    runtime_env = build_runtime_env(config)
    
    # 基础Ray命令
    
    cmd = [
        "ray", "job", "submit",
        "--runtime-env-json", json.dumps(runtime_env),
        "--"
    ]
    
    # VERL训练命令
    verl_cmd = ["python3", "-m", "verl.trainer.main_ppo"]
    
    # 添加数据文件参数
    if converted_data_paths:
        train_path, val_path = converted_data_paths
        verl_cmd.extend([
            f'data.train_files=["{train_path}"]',
            f'data.val_files=["{val_path}"]'
        ])
    else:
        train_files = build_train_files_list(config)
        test_files = build_test_files_list(config)
        verl_cmd.extend([
            f'data.train_files={train_files}',
            f'data.val_files={test_files}'
        ])
    
    # 展平配置并添加参数
    flat_config = flatten_config(config)
    
    excluded_keys = {
        'data.gsm8k_train_path', 'data.gsm8k_test_path', 
        'data.math_train_path', 'data.math_test_path',
        'data.train_files', 'data.val_files',
        'environment', 'logging', 'data_conversion', 'trainer.save_dir',
        'custom_reward_function.debug_mode'
    }
    
    for key, value in flat_config.items():
        should_exclude = any(key == excluded_key or key.startswith(f"{excluded_key}.") 
                           for excluded_key in excluded_keys)
        
        if not should_exclude:
            if isinstance(value, bool):
                value = str(value).lower()
            elif isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                pass
            else:
                value = str(value)
            
            verl_cmd.append(f"{key}={value}")
    
    # 添加额外参数
    if extra_args:
        verl_cmd.extend(extra_args)
    
    # 合并命令
    cmd.extend(verl_cmd)
    
    return cmd

def check_ray_cluster():
    """检查Ray集群状态"""
    try:
        result = subprocess.run(["ray", "status"], capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 设置Ray环境变量覆盖
    os.environ['RAY_OVERRIDE_JOB_RUNTIME_ENV'] = '1'
    
    parser = argparse.ArgumentParser(description="Ray VERL强化学习训练启动脚本")
    parser.add_argument("--config", type=str, default="qwen2_14b_rf_0802.yaml", 
                       help="配置文件名（位于config/rl/qwen/目录下）")
    parser.add_argument("--debug", action="store_true", help="开启调试模式，只打印命令不执行")
    parser.add_argument("--check-cluster", action="store_true", help="检查Ray集群状态")
    
    args, extra_args = parser.parse_known_args()
    
    # 检查Ray集群状态
    if args.check_cluster:
        cluster_ok, status_info = check_ray_cluster()
        if cluster_ok:
            logger.info("Ray集群状态正常:")
            logger.info(status_info)
        else:
            logger.error("Ray集群状态异常:")
            logger.error(status_info)
            return 1
    
    # 构建配置文件路径
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    config_path = str(project_root / "config" / "rl" / "qwen" / args.config)
    
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        return 1
    
    # 加载配置
    try:
        config = load_config(config_path)
        logger.info(f"已加载配置文件: {config_path}")
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return 1
    
    # 检查是否为多节点训练
    trainer_config = config.get('trainer', {})
    nnodes = trainer_config.get('nnodes', 1)
    
    if nnodes <= 1:
        logger.warning("配置显示为单节点训练，建议使用 run_verl_training.py")
        logger.warning("继续使用Ray Job Submit...")
    
    # 运行数据转换和训练
    async def async_main():
        # 数据转换
        converted_data_paths = await run_data_conversion_async(config, logger)
        
        # 构建Ray Job命令
        try:
            cmd = build_ray_job_command(config, converted_data_paths, extra_args)
            
            logger.info("构建的Ray Job Submit命令:")
            logger.info(f"  {' '.join(cmd[:10])}...")  # 只显示前10个参数
            logger.info(f"完整命令已保存到: ray_job_command.txt")
            
            # 保存完整命令到文件
            with open("ray_job_command.txt", "w") as f:
                f.write(" ".join(cmd))
            
            if args.debug:
                logger.info("调试模式：仅显示命令，不执行训练")
                logger.info("完整命令:")
                for i, arg in enumerate(cmd):
                    logger.info(f"  [{i}] {arg}")
                return 0
            
            # 检查Ray集群
            cluster_ok, _ = check_ray_cluster()
            if not cluster_ok:
                logger.error("Ray集群未运行，请先启动Ray集群:")
                logger.error("  ray start --head --port=6379")
                return 1
            
            # 执行Ray Job Submit
            logger.info("开始提交Ray训练任务...")
            result = subprocess.run(cmd, check=True)
            logger.info("训练任务提交成功！")
            return result.returncode
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Ray Job提交失败，退出码: {e.returncode}")
            return e.returncode
        except Exception as e:
            logger.error(f"训练过程中出现错误: {e}")
            return 1
    
    return asyncio.run(async_main())

if __name__ == "__main__":
    sys.exit(main())
