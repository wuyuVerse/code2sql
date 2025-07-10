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

# 生成带时间戳的结果目录
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULT_DIR="model/evaluation/fingerprint_eval/results/${TIMESTAMP}_evaluation"
mkdir -p "$RESULT_DIR"

echo "📁 结果将保存到: $RESULT_DIR"

# 更新配置文件中的模型路径和输出目录
echo "🔧 更新配置文件..."
python3 -c "
import yaml
with open('$CONFIG_FILE', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
config['model_config']['model_path'] = '$MODEL_PATH'
config['output_config']['output_dir'] = '$RESULT_DIR'
if '$EVAL_MODE' == 'test':
    config['debug_config']['test_mode'] = True
    config['debug_config']['test_samples'] = 10
else:
    config['debug_config']['test_mode'] = False
with open('$CONFIG_FILE', 'w', encoding='utf-8') as f:
    yaml.dump(config, f, allow_unicode=True, indent=2)
print('✅ 配置文件已更新')
"

# 运行评估
echo "🔄 开始运行评估..."
python3 model/evaluation/fingerprint_eval/scripts/run_evaluation.py --config "$CONFIG_FILE"

# 检查评估结果并生成报告
if [ -d "$RESULT_DIR" ]; then
    LATEST_RESULT=$(ls -t "$RESULT_DIR"/evaluation_results_*.json 2>/dev/null | head -1)
    if [ -f "$LATEST_RESULT" ]; then
        echo "📊 生成评估报告..."
        mkdir -p "$RESULT_DIR/reports"
        python3 model/evaluation/fingerprint_eval/scripts/evaluation_report_generator.py \
            --results "$LATEST_RESULT" \
            --output_dir "$RESULT_DIR/reports"
        
        echo "📈 计算指纹覆盖率..."
        FINGERPRINT_CACHE=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['data_config']['fingerprint_cache_path'])")
        python3 model/evaluation/fingerprint_eval/scripts/calculate_coverage.py \
            --results_file "$LATEST_RESULT" \
            --fingerprint_cache "$FINGERPRINT_CACHE"

        echo "✅ 评估完成！"
        echo "📁 结果目录: $RESULT_DIR"
        echo "📄 评估结果: $LATEST_RESULT"
        echo "📋 报告目录: $RESULT_DIR/reports"
        
        # 显示报告文件
        if [ -d "$RESULT_DIR/reports" ]; then
            echo "📊 生成的报告文件:"
            ls -la "$RESULT_DIR/reports"/*.html 2>/dev/null || echo "  (未生成HTML报告)"
        fi
    else
        echo "⚠️ 未找到评估结果文件"
    fi
else
    echo "⚠️ 评估结果目录不存在"
fi

echo "🎉 指纹评估流程完成！" 