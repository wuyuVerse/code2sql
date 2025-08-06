#!/bin/bash

# Ray 集群一键部署脚本
# 用于自动化完成SSH配置、环境安装和集群启动

set -e

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

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查脚本文件是否存在
check_scripts() {
    log_info "检查脚本文件..."
    
    local scripts=(
        "ray_cluster_manager.sh"
        "setup_ssh_keys.sh"
        "setup_verl_env.sh"
        "ray_cluster_config.txt"
    )
    
    for script in "${scripts[@]}"; do
        if [[ ! -f "${SCRIPT_DIR}/${script}" ]]; then
            log_error "脚本文件不存在: ${script}"
            exit 1
        else
            log_success "找到脚本文件: ${script}"
        fi
    done
    
    # 确保脚本有执行权限
    chmod +x "${SCRIPT_DIR}/ray_cluster_manager.sh"
    chmod +x "${SCRIPT_DIR}/setup_ssh_keys.sh"
    chmod +x "${SCRIPT_DIR}/setup_verl_env.sh"
    log_success "脚本执行权限设置完成"
}

# 显示服务器配置
show_server_config() {
    log_info "当前服务器配置:"
    echo ""
    echo "=========================================="
    echo "          H20 Ray 集群配置"
    echo "=========================================="
    echo "Head 节点:"
    echo "  123.206.111.143 (内网: 10.0.0.13)"
    echo ""
    echo "Worker 节点:"
    echo "  43.142.113.152 (内网: 10.0.0.38)"
    echo "  1.116.229.162 (内网: 10.0.0.6)"
    echo "  1.15.107.7 (内网: 10.0.0.25)"
    echo "  124.220.215.36 (内网: 10.0.0.43)"
    echo "  101.34.242.166 (内网: 10.0.0.20)"
    echo "  110.40.184.105 (内网: 10.0.0.12)"
    echo "  1.117.194.221 (内网: 10.0.0.29)"
    echo "=========================================="
    echo ""
}

# 配置SSH免密登录
setup_ssh() {
    log_info "=== 第1步: 配置SSH免密登录 ==="
    echo ""
    
    log_info "开始配置SSH免密登录，这可能需要您输入各服务器的密码..."
    
    if "${SCRIPT_DIR}/setup_ssh_keys.sh" setup-all; then
        log_success "SSH免密登录配置完成"
    else
        log_error "SSH免密登录配置失败"
        log_info "您可以手动运行: ./setup_ssh_keys.sh setup-all"
        exit 1
    fi
    
    echo ""
}

# 安装VERL环境
install_verl() {
    log_info "=== 第2步: 安装VERL环境 ==="
    echo ""
    
    read -p "是否需要在所有服务器上安装VERL环境? (y/n): " install_env
    
    if [[ "$install_env" == "y" || "$install_env" == "Y" ]]; then
        log_info "在所有服务器上安装VERL环境..."
        
        # 在所有服务器上执行VERL环境安装
        if "${SCRIPT_DIR}/ray_cluster_manager.sh" exec "cd /data/cloud_disk_1/home/wuyu/code2sql/model/rl && bash setup_verl_env.sh"; then
            log_success "VERL环境安装完成"
        else
            log_warning "VERL环境安装可能失败，请检查日志"
            log_info "您可以手动在各服务器上运行安装脚本"
        fi
    else
        log_info "跳过VERL环境安装"
    fi
    
    echo ""
}

# 启动Ray集群
start_cluster() {
    log_info "=== 第3步: 启动Ray集群 ==="
    echo ""
    
    # 检查连接
    log_info "检查所有服务器连接..."
    if "${SCRIPT_DIR}/ray_cluster_manager.sh" check; then
        log_success "所有服务器连接正常"
    else
        log_error "服务器连接检查失败"
        exit 1
    fi
    
    # 启动集群
    log_info "启动Ray集群..."
    if "${SCRIPT_DIR}/ray_cluster_manager.sh" start; then
        log_success "Ray集群启动成功"
    else
        log_error "Ray集群启动失败"
        exit 1
    fi
    
    # 检查集群状态
    echo ""
    log_info "检查集群状态..."
    "${SCRIPT_DIR}/ray_cluster_manager.sh" status
    
    echo ""
}

# 显示使用提示
show_usage_tips() {
    log_success "=== Ray集群部署完成！ ==="
    echo ""
    echo "==========================================="
    echo "           Ray 集群管理命令"
    echo "==========================================="
    echo ""
    echo "基本操作:"
    echo "  ./ray_cluster_manager.sh status   # 查看集群状态"
    echo "  ./ray_cluster_manager.sh stop     # 停止集群"
    echo "  ./ray_cluster_manager.sh restart  # 重启集群"
    echo ""
    echo "健康检查:"
    echo "  ./ray_cluster_manager.sh check    # 检查SSH连接"
    echo "  ./ray_cluster_manager.sh exec 'nvidia-smi'  # 查看GPU状态"
    echo ""
    echo "连接信息:"
    echo "  Head节点地址: 10.0.0.13:10001"
    echo "  Dashboard: http://123.206.111.143:8265"
    echo ""
    echo "Python连接示例:"
    echo "  import ray"
    echo "  ray.init(address='ray://10.0.0.13:10001')"
    echo ""
    echo "更多用法请查看: cat README_ray_cluster.md"
    echo "==========================================="
    echo ""
}

# 错误处理
handle_error() {
    log_error "部署过程中发生错误"
    log_info "您可以："
    log_info "1. 检查网络连接和SSH配置"
    log_info "2. 查看详细文档: cat README_ray_cluster.md"
    log_info "3. 手动执行各个步骤"
    exit 1
}

# 主菜单
show_menu() {
    echo ""
    echo "==========================================="
    echo "        Ray 集群一键部署工具"
    echo "==========================================="
    echo ""
    echo "请选择操作:"
    echo "  1) 完整部署 (SSH + 环境 + 集群)"
    echo "  2) 仅配置SSH免密登录"
    echo "  3) 仅安装VERL环境"
    echo "  4) 仅启动Ray集群"
    echo "  5) 显示服务器配置"
    echo "  6) 显示帮助信息"
    echo "  0) 退出"
    echo ""
    read -p "请输入选项 (0-6): " choice
    echo ""
}

# 显示帮助
show_help() {
    echo "Ray 集群一键部署工具"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  full      完整部署流程"
    echo "  ssh       仅配置SSH"
    echo "  env       仅安装环境"
    echo "  start     仅启动集群"
    echo "  config    显示配置"
    echo "  help      显示帮助"
    echo ""
    echo "示例:"
    echo "  $0 full     # 完整部署"
    echo "  $0 start    # 只启动集群"
    echo ""
}

# 完整部署流程
full_deploy() {
    log_info "开始Ray集群完整部署流程..."
    
    check_scripts
    show_server_config
    
    # 询问是否继续
    read -p "确认要继续部署吗? (y/n): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "部署已取消"
        exit 0
    fi
    
    setup_ssh
    install_verl
    start_cluster
    show_usage_tips
}

# 错误处理
trap handle_error ERR

# 主函数
main() {
    case "${1:-menu}" in
        "full")
            full_deploy
            ;;
        "ssh")
            check_scripts
            setup_ssh
            ;;
        "env")
            check_scripts
            install_verl
            ;;
        "start")
            check_scripts
            start_cluster
            ;;
        "config")
            show_server_config
            ;;
        "help")
            show_help
            ;;
        "menu")
            while true; do
                show_menu
                case $choice in
                    1)
                        full_deploy
                        break
                        ;;
                    2)
                        check_scripts
                        setup_ssh
                        ;;
                    3)
                        check_scripts
                        install_verl
                        ;;
                    4)
                        check_scripts
                        start_cluster
                        ;;
                    5)
                        show_server_config
                        ;;
                    6)
                        show_help
                        ;;
                    0)
                        log_info "退出部署工具"
                        exit 0
                        ;;
                    *)
                        log_error "无效选项，请重新选择"
                        ;;
                esac
                echo ""
                read -p "按Enter键继续..." dummy
            done
            ;;
        *)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@" 