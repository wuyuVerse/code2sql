#!/bin/bash

#================================================================================================
# 脚本说明:
# 该脚本用于启动两个并行的Qwen3-14B模型微调任务。
# 每个任务使用不同的GPU集合和独立的配置文件。
#
# 使用方法:
# 1. 确保已经通过 `pip install -r requirements.txt` 安装了所有依赖。
# 2. 确保配置文件 'qwen3_14b_ft.yaml' 和 'qwen3_14b_ft_gpu4567.yaml' 已按需配置。
# 3. 在项目根目录下执行: bash model/training/start_finetune.sh
#================================================================================================

# 激活Python虚拟环境
VENV_PATH="model/LLaMA-Factory/.venv/bin/activate"
if [ -f "$VENV_PATH" ]; then
    echo "Activating Python virtual environment from $VENV_PATH"
    source "$VENV_PATH"
else
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# 训练脚本路径
TRAIN_SCRIPT="model/training/train_qwen3_ft.py"

# 配置文件路径
CONFIG_1="qwen3_14b_ft.yaml"
CONFIG_2="qwen3_14b_ft_gpu4567.yaml"

# 创建日志目录
LOG_DIR="model/training/logs"
mkdir -p "$LOG_DIR"

# 获取当前时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# --- 任务1: 使用GPU 0,1,2,3 ---
LOG_FILE_1="${LOG_DIR}/train_gpus0123_${TIMESTAMP}.log"
echo "Starting training task 1 on GPUs 0,1,2,3..."
echo "Config: ${CONFIG_1}"
echo "Log file: ${LOG_FILE_1}"

CUDA_VISIBLE_DEVICES=0,1,2,3 nohup python -u "$TRAIN_SCRIPT" --config "$CONFIG_1" > "$LOG_FILE_1" 2>&1 &
PID_1=$!
echo "Task 1 started with PID: $PID_1"
echo "-----------------------------------------------------"


# --- 任务2: 使用GPU 4,5,6,7 ---
# (注意: 这里假设您有8个GPU, 索引从0到7)
LOG_FILE_2="${LOG_DIR}/train_gpus4567_${TIMESTAMP}.log"
echo "Starting training task 2 on GPUs 4,5,6,7..."
echo "Config: ${CONFIG_2}"
echo "Log file: ${LOG_FILE_2}"

CUDA_VISIBLE_DEVICES=4,5,6,7 nohup python -u "$TRAIN_SCRIPT" --config "$CONFIG_2" > "$LOG_FILE_2" 2>&1 &
PID_2=$!
echo "Task 2 started with PID: $PID_2"
echo "-----------------------------------------------------"

echo "Both training tasks have been launched in the background."
echo "You can monitor the training progress using the log files in ${LOG_DIR}"
echo "To check the status of the processes, use: ps -p $PID_1,$PID_2"
echo "To stop a task, use: kill $PID_1 or kill $PID_2" 