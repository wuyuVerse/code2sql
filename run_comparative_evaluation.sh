#!/bin/bash

# run_comparative_evaluation.sh
# 启动模型对比评估流程的脚本

# 设置默认配置文件路径
CONFIG_FILE="config/evaluation/comparative_evaluation_config.yaml"

# 帮助信息
function show_help {
    echo "使用方法: $0 [选项]"
    echo "选项:"
    echo "  --config FILE    指定配置文件路径 (默认: $CONFIG_FILE)"
    echo "  --mode MODE      评估模式: 'full' 或 'test' (默认: full)"
    echo "  --help           显示此帮助信息"
}

# 默认评估模式
EVAL_MODE="full"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --mode)
            if [[ "$2" == "test" || "$2" == "full" ]]; then
                EVAL_MODE="$2"
            else
                echo "错误: --mode 参数必须是 'test' 或 'full'" >&2
                exit 1
            fi
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "🚀 开始模型对比评估..."
echo "模式: $EVAL_MODE"
echo "配置文件: $CONFIG_FILE"


# 1. 从主配置中获取根输出目录
BASE_OUTPUT_DIR=$(python3 -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['output_config']['output_dir'])")

if [ -z "$BASE_OUTPUT_DIR" ]; then
    echo "❌ 无法从 $CONFIG_FILE 中读取 output_dir 配置。"
    exit 1
fi

# 2. 创建本次运行的专属目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_DIR="$BASE_OUTPUT_DIR/$TIMESTAMP"
mkdir -p "$RUN_DIR"

echo "📂 本次评估结果将保存在: $RUN_DIR"

# 3. 运行对比评估脚本
echo "🔄 开始运行对比评估..."
python3 model/evaluation/comparative_eval/scripts/run_comparison.py \
    --config "$CONFIG_FILE" \
    --output_dir "$RUN_DIR" \
    --mode "$EVAL_MODE"

# 检查评估是否成功
if [ $? -ne 0 ]; then
    echo "❌ 对比评估脚本执行失败。"
    exit 1
fi

echo "✅ 对比评估流程完成！"
echo "📂 结果保存在: $RUN_DIR/comparative_results.json"
echo "下一步: 启动Web服务器查看详细报告。"
echo "命令: uvicorn web_server.main:app --reload" 