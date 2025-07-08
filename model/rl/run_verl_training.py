#!/usr/bin/env python3
"""
VERL 强化学习训练启动脚本
支持通过YAML配置文件进行参数配置
"""

import os
import sys
import logging
import yaml
import subprocess
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

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
    
    # 支持新的直接文件路径格式
    if "train_files" in data_config:
        train_files = data_config["train_files"]
        if isinstance(train_files, str):
            return train_files
        elif isinstance(train_files, list):
            return str(train_files).replace("'", '"')
    
    # 向后兼容旧的分散文件路径格式
    train_files = []
    if "gsm8k_train_path" in data_config:
        train_files.append(data_config["gsm8k_train_path"])
    if "math_train_path" in data_config:
        train_files.append(data_config["math_train_path"])
    
    return str(train_files).replace("'", '"')

def build_test_files_list(config: Dict[str, Any]) -> str:
    """构建测试文件列表字符串"""
    data_config = config.get("data", {})
    
    # 支持新的直接文件路径格式
    if "val_files" in data_config:
        val_files = data_config["val_files"]
        if isinstance(val_files, str):
            return val_files
        elif isinstance(val_files, list):
            return str(val_files).replace("'", '"')
    
    # 向后兼容旧的分散文件路径格式
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
            # 处理字符串列表，如 logger
            items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)

def setup_environment(config: Dict[str, Any]):
    """设置环境变量"""
    env_config = config.get("environment", {})
    for key, value in env_config.items():
        os.environ[key] = str(value)

def build_verl_command(config: Dict[str, Any], extra_args: Optional[List[str]] = None) -> List[str]:
    """构建VERL训练命令"""
    # 设置环境变量
    setup_environment(config)
    
    # 展开环境变量
    config = expand_env_vars(config)
    
    # 基础命令
    cmd = ["python3", "-m", "verl.trainer.main_ppo"]
    
    # 构建训练和测试文件列表
    train_files = build_train_files_list(config)
    test_files = build_test_files_list(config)
    
    # 添加文件路径参数
    cmd.append(f'data.train_files={train_files}')
    cmd.append(f'data.val_files={test_files}')
    
    # 展平配置并添加到命令中
    flat_config = flatten_config(config)
    
    # 排除已经处理的文件路径配置和其他非训练参数
    excluded_keys = {
        'data.gsm8k_train_path', 'data.gsm8k_test_path', 
        'data.math_train_path', 'data.math_test_path',
        'data.train_files', 'data.val_files',
        'environment', 'logging'
    }
    
    for key, value in flat_config.items():
        if key not in excluded_keys:
            # 处理布尔值
            if isinstance(value, bool):
                value = str(value).lower()
            # 处理列表（如logger）
            elif isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                # 保持列表格式
                pass
            else:
                value = str(value)
            
            cmd.append(f"{key}={value}")
    
    # 添加额外参数
    if extra_args is not None:
        cmd.extend(extra_args)
    
    return cmd

def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="VERL强化学习训练启动脚本")
    parser.add_argument("--config", type=str, default="qwen2_14b_rf.yaml", 
                       help="配置文件名（位于config/rl/qwen/目录下）")
    parser.add_argument("--debug", action="store_true", help="开启调试模式，只打印命令不执行")
    
    # 解析已知参数，其余参数传递给VERL
    args, extra_args = parser.parse_known_args()
    
    # 构建配置文件路径
    config_path = str(Path(__file__).parents[2] / "config" / "rl" / "qwen" / args.config)
    
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
    
    # 构建训练命令
    try:
        cmd = build_verl_command(config, extra_args)
        logger.info(f"构建的训练命令:")
        logger.info(f"  {' '.join(cmd)}")
        
        if args.debug:
            logger.info("调试模式：仅显示命令，不执行训练")
            return 0
        
        # 执行训练
        logger.info("开始VERL强化学习训练...")
        result = subprocess.run(cmd, check=True)
        logger.info("训练完成！")
        return result.returncode
        
    except subprocess.CalledProcessError as e:
        logger.error(f"训练过程中出现错误，退出码: {e.returncode}")
        return e.returncode
    except Exception as e:
        logger.error(f"训练过程中出现错误: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 