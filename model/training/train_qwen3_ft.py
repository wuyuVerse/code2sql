#!/usr/bin/env python3
"""
Qwen3-14B 全量微调训练脚本
使用 LLaMA-Factory 进行全量微调
"""

import os
import sys
import logging
import yaml
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO,
    )

def load_config(config_path: str) -> dict:
    """加载YAML配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config

def check_model_path(model_path: str) -> bool:
    """检查模型路径是否存在"""
    return os.path.exists(model_path)

def create_output_dir(output_dir: str):
    """创建输出目录"""
    os.makedirs(output_dir, exist_ok=True)

def run_train_command(config, unique_output_dir: str, unique_run_name: str):
    """使用llamafactory-cli运行训练"""
    cmd = [
        "llamafactory-cli", "train",
        "--stage", config.get("stage", "sft"),
        "--model_name_or_path", config["model_path"],
        "--dataset", config["dataset"],
        "--template", config["template"],
        "--finetuning_type", config["finetuning_type"],
        "--cutoff_len", str(config["cutoff_len"]),
        "--max_samples", str(config["max_samples"]),
        "--preprocessing_num_workers", str(config["preprocessing_num_workers"]),
        "--learning_rate", str(config["learning_rate"]),
        "--num_train_epochs", str(config["num_train_epochs"]),
        "--max_grad_norm", str(config["max_grad_norm"]),
        "--per_device_train_batch_size", str(config["per_device_train_batch_size"]),
        "--gradient_accumulation_steps", str(config["gradient_accumulation_steps"]),
        "--lr_scheduler_type", config["lr_scheduler_type"],
        "--warmup_ratio", str(config["warmup_ratio"]),
        "--logging_steps", str(config["logging_steps"]),
        "--save_steps", str(config["save_steps"]),
        "--save_total_limit", str(config["save_total_limit"]),
        "--output_dir", unique_output_dir,
        "--overwrite_output_dir"
    ]
    
    # 添加必要参数
    if config.get("do_train", True):
        cmd.append("--do_train")
    
    if config.get("trust_remote_code", True):
        cmd.append("--trust_remote_code")
    
    if config.get("bf16", False):
        cmd.append("--bf16")
    
    if config.get("save_safetensors", False):
        cmd.append("--save_safetensors")
    
    if config.get("overwrite_cache", False):
        cmd.append("--overwrite_cache")
    
    if config.get("plot_loss", False):
        cmd.append("--plot_loss")
    
    if config.get("save_only_model", False):
        cmd.append("--save_only_model")
    
    # 添加数据集配置
    if config.get("dataset_dir"):
        cmd.extend(["--dataset_dir", config["dataset_dir"]])
    
    if config.get("dataloader_num_workers"):
        cmd.extend(["--dataloader_num_workers", str(config["dataloader_num_workers"])])
    
    # 添加DeepSpeed配置
    if config.get("deepspeed"):
        cmd.extend(["--deepspeed", config["deepspeed"]])
    
    # 添加其他配置
    if config.get("rope_scaling"):
        cmd.extend(["--rope_scaling", config["rope_scaling"]])
    
    if config.get("flash_attn"):
        cmd.extend(["--flash_attn", config["flash_attn"]])
    
    if config.get("eval_steps"):
        cmd.extend(["--eval_steps", str(config["eval_steps"])])
    
    if config.get("ddp_timeout"):
        cmd.extend(["--ddp_timeout", str(config["ddp_timeout"])])
    
    if config.get("weight_decay"):
        cmd.extend(["--weight_decay", str(config["weight_decay"])])
    
    # 添加实验跟踪配置
    if config.get("use_swanlab", False):
        cmd.extend(["--report_to", "swanlab"])
        # 如果提供了swanlab_run_name，就使用它，否则使用默认生成的
        run_name = config.get("swanlab_run_name", unique_run_name)
        cmd.extend(["--run_name", run_name])
    else:
        # 如果不使用swanlab，可以恢复默认或其他的报告方式
        report_to = config.get("report_to", "none")
        if report_to != "none":
            cmd.extend(["--report_to", report_to])
    
    return cmd

def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 配置文件路径 - 支持命令行参数
    parser = argparse.ArgumentParser(description="Qwen3-14B微调训练脚本")
    parser.add_argument("--config", type=str, default="qwen3_14b_ft.yaml", help="配置文件名")
    args = parser.parse_args()
    
    config_path = str(Path(__file__).parents[1] / "configs" / args.config)
    
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        return
    
    # 加载配置
    config = load_config(config_path)
    logger.info(f"已加载配置文件: {config_path}")
    
    # 检查模型路径
    model_path = config.get("model_path", "")
    if not check_model_path(model_path):
        logger.warning(f"模型路径不存在: {model_path}")
        logger.info("程序将继续运行，LLaMA-Factory会尝试自动下载模型")
    else:
        logger.info(f"模型路径验证成功: {model_path}")
    
    # 生成唯一的运行名称和输出目录（包含时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_run_name = f"qwen3-14b-ft-{timestamp}"
    unique_output_dir = f"saves/qwen3-14b-ft-{timestamp}"
    
    # 创建输出目录
    create_output_dir(unique_output_dir)
    logger.info(f"输出目录已创建: {unique_output_dir}")
    logger.info(f"运行名称: {unique_run_name}")
    
    # 设置环境变量
    # 从配置文件读取GPU设置，如果环境变量未设置的话
    if "CUDA_VISIBLE_DEVICES" not in os.environ:
        cuda_devices = config.get("cuda_visible_devices", "0")
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_devices
        logger.info(f"从配置文件设置GPU设备: {cuda_devices}")
    else:
        logger.info(f"使用环境变量GPU设备: {os.environ['CUDA_VISIBLE_DEVICES']}")
    
    visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "0")
    gpu_count = len(visible_devices.split(',')) if visible_devices else 1
    logger.info(f"最终使用GPU设备: {visible_devices}")
    logger.info(f"GPU数量: {gpu_count}")
    
    # 强制使用torchrun启动DeepSpeed分布式训练
    os.environ["FORCE_TORCHRUN"] = "1"
    
    # 禁用 W&B，如果配置了 SwanLab
    if config.get("use_swanlab", False):
        os.environ["WANDB_DISABLED"] = "true"  # 禁用 W&B
        logger.info("已禁用 W&B，启用 SwanLab 实验跟踪")
    
    logger.info("开始训练...")
    logger.info(f"使用模型: {config['model_path']}")
    logger.info(f"微调类型: {config['finetuning_type']}")
    logger.info(f"输出目录: {unique_output_dir}")
    logger.info(f"分布式训练: {'是' if gpu_count > 1 else '否'}")
    
    try:
        # 使用命令行方式运行训练
        cmd = run_train_command(config, unique_output_dir, unique_run_name)
        logger.info(f"执行命令: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=True, capture_output=False)
        logger.info("训练完成！")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"训练过程中出现错误，退出码: {e.returncode}")
        raise
    except Exception as e:
        logger.error(f"训练过程中出现错误: {e}")
        raise

if __name__ == "__main__":
    main() 