#!/usr/bin/env python3
"""
Qwen3-14B 全量微调训练脚本
使用 LLaMA-Factory 进行全量微调
"""

import os
import sys
import logging
import yaml
from pathlib import Path
from datetime import datetime

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

def setup_swanlab():
    """配置SwanLab"""
    try:
        import swanlab
        swanlab.init(
            experiment_name="qwen3-ft-finetune",
            tracking_uri="http://localhost:8081",
            save_code=True,
            save_graph=True
        )
    except ImportError:
        logging.warning("SwanLab未安装，将不会记录实验数据")
        return False
    except Exception as e:
        logging.warning(f"SwanLab初始化失败: {e}")
        return False
    return True

def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 配置文件路径
    config_path = str(Path(__file__).parents[2] / "config" / "training" / "qwen" / "qwen3_14b_ft.yaml")
    
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
    
    # 更新配置中的输出目录
    config["output_dir"] = unique_output_dir
    
    # 创建输出目录
    create_output_dir(unique_output_dir)
    logger.info(f"输出目录已创建: {unique_output_dir}")
    logger.info(f"运行名称: {unique_run_name}")
    
    # 设置环境变量，使用所有可用的GPU
    os.environ["CUDA_VISIBLE_DEVICES"] = "0,1,2,3,4,5,6,7"  # 使用所有8张GPU
    
    # 配置SwanLab
    swanlab_enabled = setup_swanlab()
    if swanlab_enabled:
        logger.info("SwanLab已成功配置")
    
    logger.info("开始训练...")
    logger.info(f"使用模型: {config['model_path']}")
    logger.info(f"微调类型: {config['finetuning_type']}")
    logger.info(f"输出目录: {unique_output_dir}")
    
    try:
        # 使用API方式进行训练
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "LLaMA-Factory"))
        
        from llamafactory.train.tuner import run_exp
        
        # 构建训练参数
        args = {
            "stage": "sft",  # 监督微调
            "do_train": True,
            "config_file": config_path,  # 使用yaml配置文件
            "output_dir": unique_output_dir,
            "ddp_backend": "nccl",  # 使用nccl后端进行分布式训练
            "use_swanlab": swanlab_enabled,
            "swanlab_run_name": unique_run_name,
            "swanlab_project": "qwen3-ft-finetune",
        }
        
        run_exp(args)
        logger.info("训练完成！")
        
    except ImportError as e:
        logger.error(f"无法导入LLaMA-Factory: {e}")
        logger.info("请确保已正确安装LLaMA-Factory")
            
    except Exception as e:
        logger.error(f"训练过程中出现错误: {e}")
        raise

if __name__ == "__main__":
    main() 