#!/bin/bash

#================================================================================================
# 合成数据整合脚本包装器
# 
# 该脚本用于将synthetic_output文件夹中所有不是workflow_年份的文件夹中的sql_generation文件夹的所有json文件中的数据整合起来，
# 加入到workflow_output/workflow_v{version}这个文件夹的final_processed_dataset.json中。
#
# 使用方法:
#   1. 自动检测版本号: bash scripts/merge_synthetic_data.sh
#   2. 指定版本号: bash scripts/merge_synthetic_data.sh --version 7
#   3. 干运行模式: bash scripts/merge_synthetic_data.sh --dry-run
#   4. 指定输入输出目录: bash scripts/merge_synthetic_data.sh --input-dir custom_input --output-dir custom_output
#================================================================================================

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查Python脚本是否存在
PYTHON_SCRIPT="$SCRIPT_DIR/merge_synthetic_data.py"
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "错误: 找不到Python脚本 $PYTHON_SCRIPT"
    exit 1
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 找不到python3命令"
    exit 1
fi

# 设置默认参数
VERSION=""
INPUT_DIR="synthetic_output"
OUTPUT_DIR="workflow_output"
DRY_RUN=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --input-dir)
            INPUT_DIR="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        -h|--help)
            echo "使用方法:"
            echo "  $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --version VERSION     指定工作流版本号 (默认: 自动检测)"
            echo "  --input-dir DIR       指定输入目录 (默认: synthetic_output)"
            echo "  --output-dir DIR      指定输出目录 (默认: workflow_output)"
            echo "  --dry-run             仅显示将要处理的文件，不实际合并"
            echo "  -h, --help            显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                                    # 自动检测版本号"
            echo "  $0 --version 7                       # 指定版本号7"
            echo "  $0 --dry-run                         # 干运行模式"
            echo "  $0 --input-dir custom_input --output-dir custom_output"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            echo "使用 $0 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

# 构建Python脚本参数
PYTHON_ARGS=""
if [ -n "$VERSION" ]; then
    PYTHON_ARGS="$PYTHON_ARGS --version $VERSION"
fi
if [ -n "$INPUT_DIR" ]; then
    PYTHON_ARGS="$PYTHON_ARGS --input-dir $INPUT_DIR"
fi
if [ -n "$OUTPUT_DIR" ]; then
    PYTHON_ARGS="$PYTHON_ARGS --output-dir $OUTPUT_DIR"
fi
if [ -n "$DRY_RUN" ]; then
    PYTHON_ARGS="$PYTHON_ARGS $DRY_RUN"
fi

# 显示执行信息
echo "=================================================================="
echo "合成数据整合脚本"
echo "=================================================================="
echo "项目根目录: $PROJECT_ROOT"
echo "Python脚本: $PYTHON_SCRIPT"
echo "输入目录: $INPUT_DIR"
echo "输出目录: $OUTPUT_DIR"
if [ -n "$VERSION" ]; then
    echo "指定版本号: $VERSION"
else
    echo "版本号: 自动检测"
fi
if [ -n "$DRY_RUN" ]; then
    echo "模式: 干运行"
fi
echo "=================================================================="

# 检查输入目录是否存在
if [ ! -d "$INPUT_DIR" ]; then
    echo "错误: 输入目录不存在: $INPUT_DIR"
    exit 1
fi

# 执行Python脚本
echo "开始执行数据整合..."
python3 "$PYTHON_SCRIPT" $PYTHON_ARGS

# 检查执行结果
if [ $? -eq 0 ]; then
    echo "=================================================================="
    echo "数据整合完成！"
    echo "=================================================================="
else
    echo "=================================================================="
    echo "数据整合失败！"
    echo "=================================================================="
    exit 1
fi 