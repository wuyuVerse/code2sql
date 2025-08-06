#!/bin/bash

# VERL 环境自动安装脚本
# 用于批量在多台服务器上配置 VERL 训练环境

set -e  # 遇到错误时退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 配置参数
ENV_NAME="verl"
PYTHON_VERSION="3.10.14"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查 conda 是否安装
check_conda() {
    log_info "检查 conda 是否已安装..."
    if ! command -v conda &> /dev/null; then
        log_error "conda 未找到，请先安装 Anaconda 或 Miniconda"
        exit 1
    fi
    log_success "conda 已安装: $(conda --version)"

        # 接受 conda 服务条款
    log_info "接受 conda 服务条款..."
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main || true
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r || true
    log_success "conda 服务条款已接受"
}

# 删除已存在的环境（如果存在）
remove_existing_env() {
    log_info "检查是否存在同名环境..."
    if conda env list | grep -q "^${ENV_NAME} "; then
        log_warning "发现已存在的 ${ENV_NAME} 环境，正在删除..."
        conda env remove -n ${ENV_NAME} -y
        log_success "已删除旧环境"
    fi
}

# 创建 conda 环境
create_conda_env() {
    log_info "创建 conda 环境: ${ENV_NAME} (Python ${PYTHON_VERSION})"
    conda create -n ${ENV_NAME} python=${PYTHON_VERSION} -y
    log_success "conda 环境创建完成"
}

# 激活环境并安装基础包
install_base_packages() {
    log_info "激活环境并安装基础 PyTorch 包..."
    
    # 使用 conda run 来在指定环境中执行命令
    conda run -n ${ENV_NAME} pip install --no-cache-dir \
        "vllm==0.8.5.post1" \
        "torch==2.6.0" \
        "torchvision==0.21.0" \
        "torchaudio==2.6.0" \
        "tensordict==0.6.2" \
        torchdata
    
    log_success "基础 PyTorch 包安装完成"
}

# 安装依赖包
install_dependencies() {
    log_info "安装其他依赖包..."
    
    conda run -n ${ENV_NAME} pip install \
        "nvidia-ml-py>=12.560.30" \
        "fastapi[standard]>=0.115.0" \
        "optree>=0.13.0" \
        "pydantic>=2.9" \
        "grpcio>=1.62.1"
    
    log_success "依赖包安装完成"
}

# 安装本地 wheel 文件
install_local_wheels() {
    log_info "安装本地 wheel 文件..."
    
    # 检查 wheel 文件是否存在（wheel 文件在 verl 子目录下）
    FLASH_ATTN_WHEEL="${SCRIPT_DIR}/verl/flash_attn-2.7.4.post1+cu12torch2.6cxx11abiFALSE-cp310-cp310-linux_x86_64.whl"
    FLASHINFER_WHEEL="${SCRIPT_DIR}/verl/flashinfer_python-0.2.2.post1+cu124torch2.6-cp38-abi3-linux_x86_64.whl"
    
    if [[ -f "${FLASH_ATTN_WHEEL}" ]]; then
        log_info "安装 flash_attn wheel..."
        conda run -n ${ENV_NAME} pip install --no-cache-dir "${FLASH_ATTN_WHEEL}"
        log_success "flash_attn 安装完成"
    else
        log_warning "未找到 flash_attn wheel 文件: ${FLASH_ATTN_WHEEL}"
        log_info "尝试从 PyPI 安装 flash-attn..."
        conda run -n ${ENV_NAME} pip install flash-attn --no-build-isolation || log_warning "flash-attn 安装失败，可能需要手动处理"
    fi
    
    if [[ -f "${FLASHINFER_WHEEL}" ]]; then
        log_info "安装 flashinfer wheel..."
        conda run -n ${ENV_NAME} pip install --no-cache-dir "${FLASHINFER_WHEEL}"
        log_success "flashinfer 安装完成"
    else
        log_warning "未找到 flashinfer wheel 文件: ${FLASHINFER_WHEEL}"
    fi
}

# 安装其他常用包
install_additional_packages() {
    log_info "安装其他常用包..."
    
    conda run -n ${ENV_NAME} pip install \
        "transformers[hf_xet]>=4.51.0" \
        accelerate \
        datasets \
        peft \
        hf-transfer \
        "numpy<2.0.0" \
        "pyarrow>=15.0.0" \
        pandas \
        ray[default] \
        codetiming \
        hydra-core \
        pylatexenc \
        qwen-vl-utils \
        wandb \
        dill \
        pybind11 \
        liger-kernel \
        mathruler \
        pytest \
        py-spy \
        pyext \
        pre-commit \
        ruff
    
    log_success "其他常用包安装完成"
}

# 安装本地 VERL 包
install_verl_package() {
    log_info "安装本地 VERL 包..."
    
    local verl_dir="/data/cloud_disk_1/home/wuyu/code2sql/model/rl/verl"
    
    if [[ -d "${verl_dir}" ]]; then
        log_info "切换到 VERL 目录: ${verl_dir}"
        cd "${verl_dir}"
        
        if [[ -f "setup.py" ]] || [[ -f "pyproject.toml" ]]; then
            log_info "执行 pip install -e . 安装 VERL 包..."
            conda run -n ${ENV_NAME} pip install -e .
            log_success "VERL 包安装完成"
        else
            log_warning "在 ${verl_dir} 中未找到 setup.py 或 pyproject.toml 文件"
        fi
        
        # 切换回原目录
        cd "${SCRIPT_DIR}"
    else
        log_error "VERL 目录不存在: ${verl_dir}"
        log_error "请确保 VERL 源码已正确下载到该位置"
    fi
}

# 验证安装
verify_installation() {
    log_info "验证安装结果..."
    
    # 检查关键包是否安装成功
    local packages=("torch" "vllm" "transformers" "ray")
    
    for package in "${packages[@]}"; do
        if conda run -n ${ENV_NAME} python -c "import ${package}; print(f'${package} version: {${package}.__version__}')" 2>/dev/null; then
            log_success "${package} 安装验证通过"
        else
            log_error "${package} 安装验证失败"
        fi
    done
    
    # 验证 VERL 包是否安装成功
    if conda run -n ${ENV_NAME} python -c "import verl" 2>/dev/null; then
        log_success "VERL 包安装验证通过"
    else
        log_warning "VERL 包导入失败，可能需要检查安装"
    fi
}

# 显示环境信息
show_env_info() {
    log_info "环境安装完成！"
    echo ""
    echo "=========================="
    echo "  VERL 环境配置完成"
    echo "=========================="
    echo "环境名称: ${ENV_NAME}"
    echo "Python 版本: ${PYTHON_VERSION}"
    echo ""
    echo "激活环境命令:"
    echo "  conda activate ${ENV_NAME}"
    echo ""
    echo "已安装的主要包:"
    conda run -n ${ENV_NAME} pip list | grep -E "(torch|vllm|transformers|ray|flash)" || true
    echo ""
}

# 主函数
main() {
    log_info "开始 VERL 环境自动安装..."
    log_info "脚本路径: ${SCRIPT_DIR}"
    
    # 执行安装步骤
    check_conda
    remove_existing_env
    create_conda_env
    install_base_packages
    install_dependencies
    install_local_wheels
    install_additional_packages
    install_verl_package
    verify_installation
    show_env_info
    
    log_success "VERL 环境安装完成！"
}

# 错误处理
trap 'log_error "脚本执行过程中发生错误，退出码: $?"' ERR

# 执行主函数
main "$@" 