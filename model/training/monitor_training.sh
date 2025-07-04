#!/bin/bash

# 训练监控脚本
echo "=== Qwen3-14B 双实例训练监控 ==="
echo "时间: $(date)"
echo ""

# 检查训练进程
echo "🔍 训练进程状态:"
ps aux | grep train_qwen3_ft | grep -v grep | while read line; do
    echo "  $line"
done
echo ""

# 检查GPU使用情况
echo "🚀 GPU使用情况:"
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits | while IFS=',' read gpu_id name util mem_used mem_total temp power; do
    printf "  GPU%s: %s%% 利用率, %sMB/%sMB 显存, %s°C, %sW\n" "$gpu_id" "$util" "$mem_used" "$mem_total" "$temp" "$power"
done
echo ""

# 检查日志文件
echo "📋 最新日志:"
for log_file in model/training/logs/train_*.log; do
    if [[ -f "$log_file" ]]; then
        echo "  📄 $(basename $log_file):"
        tail -2 "$log_file" | grep -E "(it\]|step|epoch)" | tail -1
    fi
done
echo ""

# 检查后台任务
echo "⚙️  后台任务:"
jobs
echo ""

echo "💡 监控命令:"
echo "  查看GPU: nvidia-smi"
echo "  查看进程: ps aux | grep train_qwen3_ft"
echo "  查看日志: tail -f model/training/logs/train_gpu*.log"
echo "  停止训练: kill -9 PID 或 pkill -f train_qwen3_ft" 