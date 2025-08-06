#!/bin/bash

# SSH 免密登录配置脚本
# 用于配置到 Ray 集群所有服务器的免密登录

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

# 配置文件路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/ray_cluster_config.txt"

# 硬编码服务器密码（所有服务器统一密码）
SERVER_PASSWORD="AI2DB%@!$no=_NO-SQL@?$#db4ai"

# 生成 SSH 密钥对
generate_ssh_key() {
    local ssh_key_path="$HOME/.ssh/id_rsa"
    
    if [[ -f "$ssh_key_path" ]]; then
        log_info "SSH 密钥已存在: $ssh_key_path"
        return 0
    fi
    
    log_info "生成 SSH 密钥对..."
    ssh-keygen -t rsa -b 4096 -f "$ssh_key_path" -N "" -q
    
    if [[ -f "$ssh_key_path" ]]; then
        log_success "SSH 密钥生成成功: $ssh_key_path"
    else
        log_error "SSH 密钥生成失败"
        exit 1
    fi
}

# 检查配置文件
check_config_file() {
    if [[ ! -f "${CONFIG_FILE}" ]]; then
        log_error "配置文件不存在: ${CONFIG_FILE}"
        log_info "请先运行 ray_cluster_manager.sh 生成配置文件"
        exit 1
    fi
}

# 读取服务器列表
read_server_list() {
    SERVERS=()
    
    while IFS=':' read -r node_type external_ip internal_ip ssh_port username; do
        # 跳过注释和空行
        [[ "$node_type" =~ ^#.*$ ]] && continue
        [[ -z "$node_type" ]] && continue
        
        if [[ "$node_type" == "head" ]] || [[ "$node_type" == "worker" ]]; then
            SERVERS+=("$external_ip:$internal_ip:$ssh_port:$username")
        fi
    done < "${CONFIG_FILE}"
    
    log_info "读取到 ${#SERVERS[@]} 台服务器配置"
}

# 复制公钥到远程服务器
copy_public_key() {
    local server_info="$1"
    local server_index="$2"
    
    IFS=':' read -r external_ip internal_ip ssh_port username <<< "$server_info"
    
    log_info "[$server_index] 配置免密登录到 $username@$external_ip:$ssh_port (内网: $internal_ip)"
    
    # 检查是否已经可以免密登录
    if ssh -p "$ssh_port" -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o PasswordAuthentication=no "$username@$external_ip" "echo 'SSH OK'" &>/dev/null; then
        log_success "[$server_index] $external_ip 已配置免密登录"
        return 0
    fi
    
    # 使用 sshpass 自动输入密码
    log_info "[$server_index] 使用硬编码密码复制公钥到 $external_ip"
    
    if SSHPASS="$SERVER_PASSWORD" sshpass -e ssh-copy-id -p "$ssh_port" -o StrictHostKeyChecking=no "$username@$external_ip" &>/dev/null; then
        log_success "[$server_index] $external_ip 免密登录配置成功"
        
        # 验证免密登录
        if ssh -p "$ssh_port" -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o PasswordAuthentication=no "$username@$external_ip" "echo 'SSH OK'" &>/dev/null; then
            log_success "[$server_index] $external_ip 免密登录验证通过"
            return 0
        else
            log_error "[$server_index] $external_ip 免密登录验证失败"
            return 1
        fi
    else
        log_error "[$server_index] $external_ip 免密登录配置失败"
        return 1
    fi
}

# 测试所有服务器的连接
test_all_connections() {
    log_info "测试所有服务器的免密登录..."
    local success_count=0
    local total_count=${#SERVERS[@]}
    
    for i in "${!SERVERS[@]}"; do
        IFS=':' read -r external_ip internal_ip ssh_port username <<< "${SERVERS[$i]}"
        
        if ssh -p "$ssh_port" -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o PasswordAuthentication=no "$username@$external_ip" "echo 'Connection test successful'" 2>/dev/null; then
            log_success "[$((i+1))] $external_ip 连接测试成功"
            ((success_count++))
        else
            log_error "[$((i+1))] $external_ip 连接测试失败"
        fi
    done
    
    echo ""
    echo "连接测试结果: $success_count/$total_count"
    
    if [[ $success_count -eq $total_count ]]; then
        log_success "所有服务器免密登录配置成功！"
        return 0
    else
        log_error "有 $((total_count - success_count)) 台服务器免密登录配置失败"
        return 1
    fi
}

# 批量配置所有服务器
setup_all_servers() {
    log_info "开始批量配置免密登录..."
    
    for i in "${!SERVERS[@]}"; do
        copy_public_key "${SERVERS[$i]}" "$((i+1))"
        echo ""  # 空行分隔
    done
    
    echo ""
    test_all_connections
}

# 显示服务器列表
show_server_list() {
    echo "服务器列表："
    echo "============="
    
    for i in "${!SERVERS[@]}"; do
        IFS=':' read -r external_ip internal_ip ssh_port username <<< "${SERVERS[$i]}"
        echo "$((i+1)). $username@$external_ip:$ssh_port (内网: $internal_ip)"
    done
    echo ""
}

# 单独配置某台服务器
setup_single_server() {
    local server_num="$1"
    
    if [[ -z "$server_num" ]] || [[ ! "$server_num" =~ ^[0-9]+$ ]]; then
        log_error "请提供有效的服务器编号"
        show_server_list
        exit 1
    fi
    
    local index=$((server_num - 1))
    
    if [[ $index -lt 0 ]] || [[ $index -ge ${#SERVERS[@]} ]]; then
        log_error "服务器编号超出范围 (1-${#SERVERS[@]})"
        show_server_list
        exit 1
    fi
    
    copy_public_key "${SERVERS[$index]}" "$server_num"
}

# 显示帮助信息
show_help() {
    echo "SSH 免密登录配置脚本"
    echo ""
    echo "用法: $0 [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  setup-all     配置所有服务器的免密登录"
    echo "  setup-one <N> 配置指定编号的服务器 (N=1,2,3...)"
    echo "  test          测试所有服务器的免密登录"
    echo "  list          显示服务器列表"
    echo "  keygen        生成 SSH 密钥对"
    echo "  help          显示此帮助信息"
    echo ""
    echo "配置文件: ${CONFIG_FILE}"
    echo ""
    echo "示例:"
    echo "  $0 setup-all     # 配置所有服务器"
    echo "  $0 setup-one 3   # 只配置第3台服务器"
    echo "  $0 test          # 测试连接"
    echo ""
    echo "注意:"
    echo "  - 使用硬编码密码自动配置，无需手动输入"
    echo "  - 请确保所有服务器都已启动 SSH 服务"
    echo "  - 建议先运行 'list' 命令查看服务器列表"
    echo "  - 会自动安装 sshpass 工具（如果未安装）"
}

# 主函数
main() {
    case "${1:-help}" in
        "setup-all")
            check_config_file
            generate_ssh_key
            read_server_list
            show_server_list
            setup_all_servers
            ;;
        "setup-one")
            check_config_file
            generate_ssh_key
            read_server_list
            show_server_list
            setup_single_server "$2"
            ;;
        "test")
            check_config_file
            read_server_list
            test_all_connections
            ;;
        "list")
            check_config_file
            read_server_list
            show_server_list
            ;;
        "keygen")
            generate_ssh_key
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@" 