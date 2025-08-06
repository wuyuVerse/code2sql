#!/bin/bash

# Ray 集群批量管理脚本
# 用于在多台服务器上批量执行 Ray 命令

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

# 默认配置
DEFAULT_USER="root"
DEFAULT_ENV_NAME="verl"
DEFAULT_HEAD_PORT="6379"
DEFAULT_SSH_PORT="22"

# 创建默认配置文件
create_default_config() {
    log_info "创建默认配置文件: ${CONFIG_FILE}"
    cat > "${CONFIG_FILE}" << EOF
# Ray 集群服务器配置文件
# 格式: [head|worker]:外网IP:内网IP:ssh_port:username
# 第一行必须是 head 节点，其余为 worker 节点

# Head 节点 (必须放在第一行)
head:123.206.111.143:10.0.0.13:22:root

# Worker 节点
worker:43.142.113.152:10.0.0.38:22:root
worker:1.116.229.162:10.0.0.6:22:root
worker:1.15.107.7:10.0.0.25:22:root
worker:124.220.215.36:10.0.0.43:22:root
worker:101.34.242.166:10.0.0.20:22:root
worker:110.40.184.105:10.0.0.12:22:root
worker:1.117.194.221:10.0.0.29:22:root
EOF
    log_warning "请编辑配置文件 ${CONFIG_FILE} 填入您的服务器信息"
    exit 1
}

# 读取配置文件
read_config() {
    if [[ ! -f "${CONFIG_FILE}" ]]; then
        log_error "配置文件不存在: ${CONFIG_FILE}"
        create_default_config
    fi
    
    # 解析配置文件
    HEAD_NODES=()
    WORKER_NODES=()
    
    while IFS=':' read -r node_type external_ip internal_ip ssh_port username; do
        # 跳过注释和空行
        [[ "$node_type" =~ ^#.*$ ]] && continue
        [[ -z "$node_type" ]] && continue
        
        if [[ "$node_type" == "head" ]]; then
            HEAD_NODES+=("$external_ip:$internal_ip:$ssh_port:$username")
        elif [[ "$node_type" == "worker" ]]; then
            WORKER_NODES+=("$external_ip:$internal_ip:$ssh_port:$username")
        fi
    done < "${CONFIG_FILE}"
    
    if [[ ${#HEAD_NODES[@]} -eq 0 ]]; then
        log_error "未找到 head 节点配置"
        exit 1
    fi
    
    if [[ ${#HEAD_NODES[@]} -gt 1 ]]; then
        log_warning "检测到多个 head 节点，将使用第一个: ${HEAD_NODES[0]}"
    fi
    
    log_info "读取配置完成 - Head: ${#HEAD_NODES[@]}, Workers: ${#WORKER_NODES[@]}"
}

# 在远程服务器上执行命令
execute_remote_command() {
    local node_info="$1"
    local command="$2"
    local node_label="$3"
    
    IFS=':' read -r external_ip internal_ip ssh_port username <<< "$node_info"
    
    # 使用内网 IP 进行 SSH
    local ssh_ip="$internal_ip"
    log_info "[$node_label] 在 $ssh_ip 上执行: $command"
    
    # 执行远程命令
    if ssh -p "$ssh_port" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$username@$ssh_ip" "$command"; then
        log_success "[$node_label] $ssh_ip 执行成功"
        return 0
    else
        log_error "[$node_label] $ssh_ip 执行失败"
        return 1
    fi
}

# 检查SSH连接
check_ssh_connections() {
    log_info "检查SSH连接..."
    local failed=0
    
    # 检查 head 节点
    IFS=':' read -r external_ip internal_ip ssh_port username <<< "${HEAD_NODES[0]}"
    local ssh_ip="$internal_ip"
    if ! ssh -p "$ssh_port" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$username@$ssh_ip" "echo 'SSH OK'" &>/dev/null; then
        log_error "无法连接到 head 节点: $ssh_ip"
        ((failed++))
    else
        log_success "Head 节点连接正常: $ssh_ip"
    fi
    
    # 检查 worker 节点
    for i in "${!WORKER_NODES[@]}"; do
        IFS=':' read -r external_ip internal_ip ssh_port username <<< "${WORKER_NODES[$i]}"
        local ssh_ip="$internal_ip"
        if ! ssh -p "$ssh_port" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$username@$ssh_ip" "echo 'SSH OK'" &>/dev/null; then
            log_error "无法连接到 worker-$((i+1)): $ssh_ip"
            ((failed++))
        else
            log_success "Worker-$((i+1)) 连接正常: $ssh_ip"
        fi
    done
    
    if [[ $failed -gt 0 ]]; then
        log_error "有 $failed 台服务器连接失败，请检查SSH配置"
        log_info "提示: 请确保已配置SSH免密登录"
        exit 1
    fi
    
    log_success "所有服务器SSH连接正常"
}

# 启动 Ray 集群
start_ray_cluster() {
    log_info "启动 Ray 集群..."
    
    # 获取 head 节点信息
    IFS=':' read -r head_external_ip head_internal_ip head_ssh_port head_username <<< "${HEAD_NODES[0]}"
    
    # 启动 head 节点
    log_info "启动 Head 节点..."
    head_command="source ~/.bashrc && export GLOO_SOCKET_IFNAME=eth0 && export NCCL_SOCKET_IFNAME=eth0 && conda activate ${DEFAULT_ENV_NAME} && ray start --head --port=${DEFAULT_HEAD_PORT} --node-ip-address=${head_internal_ip} --dashboard-host=0.0.0.0"
    
    if execute_remote_command "${HEAD_NODES[0]}" "$head_command" "HEAD"; then
        log_success "Head 节点启动成功 (内网地址: ${head_internal_ip}:${DEFAULT_HEAD_PORT})"
        sleep 5  # 等待 head 节点完全启动
    else
        log_error "Head 节点启动失败"
        exit 1
    fi
    
    # 启动 worker 节点
    log_info "启动 Worker 节点..."
    for i in "${!WORKER_NODES[@]}"; do
        IFS=':' read -r worker_external_ip worker_internal_ip worker_ssh_port worker_username <<< "${WORKER_NODES[$i]}"
        worker_command="source ~/.bashrc && export GLOO_SOCKET_IFNAME=eth0 && export NCCL_SOCKET_IFNAME=eth0 && conda activate ${DEFAULT_ENV_NAME} && ray start --address=${head_internal_ip}:${DEFAULT_HEAD_PORT} --node-ip-address=${worker_internal_ip}"
        execute_remote_command "${WORKER_NODES[$i]}" "$worker_command" "WORKER-$((i+1))" &
    done
    
    # 等待所有 worker 节点启动完成
    wait
    log_success "Ray 集群启动完成"
    log_info "Head 节点地址: ${head_internal_ip}:${DEFAULT_HEAD_PORT}"
}

# 停止 Ray 集群
stop_ray_cluster() {
    log_info "停止 Ray 集群..."
    
    # 停止所有节点
    stop_command="source ~/.bashrc && export GLOO_SOCKET_IFNAME=eth0 && export NCCL_SOCKET_IFNAME=eth0 && conda activate ${DEFAULT_ENV_NAME} && ray stop"
    
    # 并行停止所有节点
    execute_remote_command "${HEAD_NODES[0]}" "$stop_command" "HEAD" &
    
    for i in "${!WORKER_NODES[@]}"; do
        execute_remote_command "${WORKER_NODES[$i]}" "$stop_command" "WORKER-$((i+1))" &
    done
    
    wait
    log_success "Ray 集群停止完成"
}

# 检查 Ray 集群状态
check_ray_status() {
    log_info "检查 Ray 集群状态..."
    
    # 检查 head 节点状态
    status_command="source ~/.bashrc && export GLOO_SOCKET_IFNAME=eth0 && export NCCL_SOCKET_IFNAME=eth0 && conda activate ${DEFAULT_ENV_NAME} && ray status"
    execute_remote_command "${HEAD_NODES[0]}" "$status_command" "HEAD"
}

# 在所有节点执行自定义命令
execute_on_all_nodes() {
    local custom_command="$1"
    log_info "在所有节点执行自定义命令: $custom_command"
    
    # 在 head 节点执行
    execute_remote_command "${HEAD_NODES[0]}" "$custom_command" "HEAD" &
    
    # 在 worker 节点执行
    for i in "${!WORKER_NODES[@]}"; do
        execute_remote_command "${WORKER_NODES[$i]}" "$custom_command" "WORKER-$((i+1))" &
    done
    
    wait
    log_success "自定义命令执行完成"
}

# 显示帮助信息
show_help() {
    echo "Ray 集群批量管理脚本"
    echo ""
    echo "用法: $0 [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  start         启动整个 Ray 集群"
    echo "  stop          停止整个 Ray 集群"
    echo "  restart       重启整个 Ray 集群"
    echo "  status        检查 Ray 集群状态"
    echo "  check         检查所有服务器的SSH连接"
    echo "  exec <cmd>    在所有节点执行自定义命令"
    echo "  config        显示配置文件路径"
    echo "  help          显示此帮助信息"
    echo ""
    echo "配置文件: ${CONFIG_FILE}"
    echo ""
    echo "示例:"
    echo "  $0 start                    # 启动集群"
    echo "  $0 status                   # 查看状态"
    echo "  $0 exec 'nvidia-smi'       # 在所有节点查看GPU状态"
    echo "  $0 exec 'ps aux | grep ray' # 查看Ray进程"
}

# 主函数
main() {
    case "${1:-help}" in
        "start")
            read_config
            check_ssh_connections
            start_ray_cluster
            ;;
        "stop")
            read_config
            stop_ray_cluster
            ;;
        "restart")
            read_config
            check_ssh_connections
            stop_ray_cluster
            sleep 3
            start_ray_cluster
            ;;
        "status")
            read_config
            check_ray_status
            ;;
        "check")
            read_config
            check_ssh_connections
            ;;
        "exec")
            if [[ -z "$2" ]]; then
                log_error "请提供要执行的命令"
                echo "用法: $0 exec '<command>'"
                exit 1
            fi
            read_config
            execute_on_all_nodes "$2"
            ;;
        "config")
            echo "配置文件路径: ${CONFIG_FILE}"
            if [[ -f "${CONFIG_FILE}" ]]; then
                echo "当前配置:"
                cat "${CONFIG_FILE}"
            else
                echo "配置文件不存在，运行脚本会自动创建"
            fi
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@" 