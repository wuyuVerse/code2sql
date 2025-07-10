#!/bin/bash
# 指纹评估快速启动脚本 - 从项目根目录运行

set -e

echo "🚀 开始指纹模型评估..."

# 默认参数
MODEL_PATH="saves/qwen3-14b-ft-20250709_171410"
CONFIG_FILE="config/evaluation/model_evaluation_config.yaml"
EVAL_MODE="test"  # test | full

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --model)
            MODEL_PATH="$2"
            shift 2
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --mode)
            EVAL_MODE="$2"
            shift 2
            ;;
        --help)
            echo "使用方法: $0 [选项]"
            echo "选项:"
            echo "  --model PATH     模型路径 (默认: $MODEL_PATH)"
            echo "  --config FILE    配置文件 (默认: $CONFIG_FILE)"
            echo "  --mode MODE      评估模式: test|full (默认: test)"
            echo "  --help           显示帮助信息"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            echo "使用 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

echo "📋 评估配置:"
echo "  模型路径: $MODEL_PATH"
echo "  配置文件: $CONFIG_FILE"
echo "  评估模式: $EVAL_MODE"

# 检查是否在项目根目录
if [ ! -f "config/evaluation/model_evaluation_config.yaml" ]; then
    echo "❌ 请在项目根目录运行此脚本"
    exit 1
fi

# 检查模型路径
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ 模型路径不存在: $MODEL_PATH"
    exit 1
fi

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

DATASETS=(cbs cos)

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

for DS in "${DATASETS[@]}"; do
    echo "\n🚀 开始处理数据集: $DS"
    RESULT_DIR="model/evaluation/fingerprint_eval/results/${TIMESTAMP}_${DS}_evaluation"
    mkdir -p "$RESULT_DIR"
    echo "📁 结果将保存到: $RESULT_DIR"

    # 计算数据与缓存路径
    if [ "$DS" == "cbs" ]; then
        EVAL_DATA_PATH="model/evaluation/fingerprint_eval/data/cbs.json"
        FP_DB_PATH="model/evaluation/fingerprint_eval/data/cbs_528_final.pkl"
    else
        EVAL_DATA_PATH="model/evaluation/fingerprint_eval/data/cos.json"
        FP_DB_PATH="model/evaluation/fingerprint_eval/data/cos_526_final.pkl"
    fi

    echo "🔧 更新配置文件..."
    python3 - <<PY
import yaml, sys
cfg_path = '$CONFIG_FILE'
with open(cfg_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
cfg['model_config']['model_path'] = '$MODEL_PATH'
cfg['output_config']['output_dir'] = '$RESULT_DIR'
cfg['data_config']['eval_data_path'] = '$EVAL_DATA_PATH'
cfg['data_config']['fingerprint_db_path'] = '$FP_DB_PATH' # 使用新的变量
if '$EVAL_MODE' == 'test':
    cfg['debug_config']['test_mode'] = True
    cfg['debug_config']['test_samples'] = 10
else:
    cfg['debug_config']['test_mode'] = False
with open(cfg_path, 'w', encoding='utf-8') as f:
    yaml.dump(cfg, f, allow_unicode=True, indent=2)
print('✅ 配置文件已更新 \n   数据集:', '$DS')
PY

    echo "🔄 开始运行评估..."
    python3 model/evaluation/fingerprint_eval/scripts/run_evaluation.py --config "$CONFIG_FILE"

    RESULTS_FILE="$RESULT_DIR/evaluation_results.json"
    if [ -f "$RESULTS_FILE" ]; then
        echo "📊 评估分析已由 run_evaluation.py 内部完成。"
        # echo "📊 生成评估报告..."
        # REPORTS_SUBDIR="$RESULT_DIR/reports"
        # mkdir -p "$REPORTS_SUBDIR"
        # python3 model/evaluation/fingerprint_eval/scripts/evaluation_report_generator.py \
        #     --results_file "$RESULTS_FILE" \
        #     --output_dir "$REPORTS_SUBDIR"

        echo "✅ $DS 评估完成！请通过Web服务器查看详细报告。"
    else
        echo "⚠️ 未找到评估结果文件: $RESULTS_FILE"
    fi
done

echo "🎉 指纹评估流程(全部数据集)完成！" 