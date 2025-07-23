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

async def run_data_conversion_async(config: Dict[str, Any], logger: logging.Logger):
    """
    运行数据转换步骤
    
    Args:
        config: 训练配置
        logger: 日志记录器
        
    Returns:
        (训练集路径, 验证集路径) 或 None（如果转换失败）
    """
    try:
        # 检查是否需要数据转换
        data_conversion_config = config.get("data_conversion", {})
        auto_convert = data_conversion_config.get("auto_convert", True)
        
        if not auto_convert:
            logger.info("跳过数据转换步骤")
            return None
        
        logger.info("开始运行数据转换...")
        
        # 创建数据转换器
        converter = RLDataConverter()
        
        # 获取workflow目录（如果指定）
        workflow_dir = data_conversion_config.get("workflow_dir")
        if workflow_dir:
            workflow_dir = Path(workflow_dir)
            if not workflow_dir.is_absolute():
                workflow_dir = project_root / workflow_dir
        
        # 获取输出名称
        output_name = data_conversion_config.get("output_name")
        
        # 获取验证集比例
        val_ratio = data_conversion_config.get("val_ratio", 0.1)
        
        # 运行转换
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

def build_verl_command(config: Dict[str, Any], converted_data_paths: Optional[Tuple[str, str]] = None, 
                      extra_args: Optional[List[str]] = None) -> List[str]:
    """构建VERL训练命令"""
    # 设置环境变量
    setup_environment(config)
    
    # 展开环境变量
    config = expand_env_vars(config)
    
    # 基础命令
    cmd = ["python3", "-m", "verl.trainer.main_ppo"]
    
    # 如果提供了转换后的数据路径，使用它们
    if converted_data_paths:
        train_path, val_path = converted_data_paths
        cmd.append(f'data.train_files=["{train_path}"]')
        cmd.append(f'data.val_files=["{val_path}"]')
    else:
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
        'environment', 'logging', 'data_conversion', 'trainer.save_dir',
        'custom_reward_function.debug_mode'  # 排除自定义调试模式参数
    }
    
    for key, value in flat_config.items():
        # 检查是否应该排除这个键
        should_exclude = False
        for excluded_key in excluded_keys:
            if key == excluded_key or key.startswith(f"{excluded_key}."):
                should_exclude = True
                break
        
        if not should_exclude:
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
    # 从当前脚本位置计算项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # 从 model/rl 回到项目根目录
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
    
    # 运行数据转换步骤
    async def async_main():
        converted_data_paths = await run_data_conversion_async(config, logger)
        # 构建训练命令
        try:
            cmd = build_verl_command(config, converted_data_paths, extra_args)
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
    return asyncio.run(async_main())

if __name__ == "__main__":
    sys.exit(main()) 