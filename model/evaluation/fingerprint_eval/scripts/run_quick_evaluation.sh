#!/bin/bash

# run_quick_evaluation.sh
# 一个快速启动模型评估流程的脚本

# 设置默认配置文件路径
CONFIG_FILE="config/evaluation/model_evaluation_config.yaml"

echo "🚀 开始模型评估..."

# 1. 从主配置中获取根输出目录
BASE_OUTPUT_DIR=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['output_config']['output_dir'])")

if [ -z "$BASE_OUTPUT_DIR" ]; then
    echo "❌ 无法从 $CONFIG_FILE 中读取 output_dir 配置。"
    exit 1
fi

# 2. 创建本次运行的专属目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="$BASE_OUTPUT_DIR/$TIMESTAMP"
DATA_DIR="$RUN_DIR/data"
REPORTS_DIR="$RUN_DIR/reports"

mkdir -p "$DATA_DIR"
mkdir -p "$REPORTS_DIR"

echo "📂 本次评估结果将保存在: $RUN_DIR"

# 3. 运行评估脚本，并指定输出到 data 目录
echo "🔄 开始运行评估..."
python3 model/evaluation/fingerprint_eval/scripts/run_evaluation.py \
    --config "$CONFIG_FILE" \
    --output_dir "$DATA_DIR"

# 4. 运行报告生成器
RESULTS_FILE="$DATA_DIR/evaluation_results.json"
echo "📊 生成评估报告..."

if [ -f "$RESULTS_FILE" ]; then
    python3 model/evaluation/fingerprint_eval/scripts/evaluation_report_generator.py \
        --results_file "$RESULTS_FILE" \
        --output_dir "$REPORTS_DIR"
else
    echo "⚠️ 未找到评估结果文件: $RESULTS_FILE"
    echo "评估可能已失败，请检查上面的日志。"
    exit 1
fi

# 5. 运行覆盖率计算
echo "📈 计算指纹覆盖率..."
FINGERPRINT_CACHE=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['data_config']['fingerprint_cache_path'])")
python3 model/evaluation/fingerprint_eval/scripts/calculate_coverage.py \
    --results_file "$RESULTS_FILE" \
    --fingerprint_cache "$FINGERPRINT_CACHE"

echo "✅ 评估流程完成！"
echo "📂 结果保存在: $RUN_DIR"
echo "📄 报告文件: $REPORTS_DIR/evaluation_report.html"
echo "📄 详细结果: $DATA_DIR/evaluation_results.json" 