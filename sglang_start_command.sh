#!/bin/bash

# 根据当前运行的sglang服务配置生成的启动命令
# 基于日志中的ServerArgs参数

echo "启动sglang服务..."

# 激活sglang环境
conda activate sglang

# 完整的启动命令
nohup env CUDA_VISIBLE_DEVICES=7,8 python -m sglang.launch_server \
  --model-path /data/local_disk0/wuyu/save_model/saves/qwen3-14b-ft-20250710_154849 \
  --tp 2 \
  --host 0.0.0.0 \
  --port 8081 \
  --disable-cuda-graph \
  --disable-radix-cache \
  > code2sql_sglang_8001.log 2>&1 &

echo "sglang服务启动完成，进程ID: $!"
echo "查看日志: tail -f code2sql_sglang_8001.log"
echo "查看进程: ps aux | grep sglang" 