#!/bin/bash
# 用法: ./transfer_model.sh /abs/path/to/model_dir

set -euo pipefail

########## 配置 ##########
# 定义内网IP列表
IPS="10.0.0.38 10.0.0.6 10.0.0.25 10.0.0.43 10.0.0.20 10.0.0.12 10.0.0.29"

# 日志配置
log_dir="./logs"
mkdir -p "$log_dir"
log_file="$log_dir/model_transfer_$(date +%Y%m%d_%H%M%S).log"
################################

[[ $# -eq 1 ]] || { echo "用法: $0 <本地模型目录>"; exit 1; }

src_dir=$(realpath "$1")
[[ -d $src_dir ]] || { echo "目录不存在: $src_dir"; exit 1; }
parent_dir=$(dirname "$src_dir")

echo -e "源目录:      $src_dir"
echo -e "父级目录:    $parent_dir"
echo -e "日志文件:    $log_file"
echo "---------------------------------------"

# 循环推送到每台机器
for ip in $IPS; do
    echo "正在向 $ip 推送模型文件..." | tee -a "$log_file"
    echo "时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$log_file"
    
    # 创建目标目录
    echo "创建目标目录: $parent_dir" | tee -a "$log_file"
    ssh "$ip" "mkdir -p '$parent_dir'" 2>&1 | tee -a "$log_file"
    
    # 使用scp传输
    echo "开始传输..." | tee -a "$log_file"
    if scp -r "$src_dir" "$ip:$parent_dir/" 2>&1 | tee -a "$log_file"; then
        echo "✅ 向 $ip 推送完成" | tee -a "$log_file"
    else
        echo "❌ 向 $ip 推送失败" | tee -a "$log_file"
    fi
    echo "---------------------------------------" | tee -a "$log_file"
done

echo "✅ 所有模型文件推送完成！详细日志见: $log_file"