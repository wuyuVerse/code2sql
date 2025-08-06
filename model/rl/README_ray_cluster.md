# Ray 集群批量管理工具

本工具集提供了便捷的Ray集群批量管理功能，支持在多台服务器上一键启动、停止和管理Ray集群。

## 工具组成

- `ray_cluster_manager.sh` - Ray集群批量管理脚本
- `setup_ssh_keys.sh` - SSH免密登录配置脚本  
- `ray_cluster_config.txt` - 服务器配置文件
- `setup_verl_env.sh` - VERL环境安装脚本

## 服务器配置

当前配置的8台H20服务器：

| 编号 | 外网IP | 内网IP | 角色 |
|------|--------|---------|------|
| 1 | 123.206.111.143 | 10.0.0.13 | Head |
| 2 | 43.142.113.152 | 10.0.0.38 | Worker |
| 3 | 1.116.229.162 | 10.0.0.6 | Worker |
| 4 | 1.15.107.7 | 10.0.0.25 | Worker |
| 5 | 124.220.215.36 | 10.0.0.43 | Worker |
| 6 | 101.34.242.166 | 10.0.0.20 | Worker |
| 7 | 110.40.184.105 | 10.0.0.12 | Worker |
| 8 | 1.117.194.221 | 10.0.0.29 | Worker |

## 快速开始

### 1. 配置SSH免密登录（首次使用）

```bash
# 查看服务器列表
./setup_ssh_keys.sh list

# 配置所有服务器的免密登录（自动使用硬编码密码）
./setup_ssh_keys.sh setup-all

# 测试免密登录
./setup_ssh_keys.sh test
```

### 2. 安装VERL环境（如需要）

```bash
# 在本地运行环境安装脚本
./setup_verl_env.sh
```

### 3. 管理Ray集群

```bash
# 检查所有服务器连接
./ray_cluster_manager.sh check

# 启动Ray集群
./ray_cluster_manager.sh start

# 查看集群状态
./ray_cluster_manager.sh status

# 停止Ray集群
./ray_cluster_manager.sh stop

# 重启Ray集群
./ray_cluster_manager.sh restart
```

## 详细使用说明

### SSH免密登录配置

在首次使用前，需要配置到所有服务器的SSH免密登录：

```bash
# 1. 生成SSH密钥（如果没有）
./setup_ssh_keys.sh keygen

# 2. 查看服务器列表
./setup_ssh_keys.sh list

# 3. 配置所有服务器（自动使用硬编码密码）
./setup_ssh_keys.sh setup-all

# 4. 配置单台服务器
./setup_ssh_keys.sh setup-one 3

# 5. 测试连接
./setup_ssh_keys.sh test
```

**注意**：脚本已硬编码服务器密码，会自动安装并使用 `sshpass` 工具进行自动化配置。

### Ray集群管理

#### 启动集群

```bash
./ray_cluster_manager.sh start
```

脚本会自动：
- 设置网络环境变量（GLOO_SOCKET_IFNAME=eth0, NCCL_SOCKET_IFNAME=eth0）
- 在Head节点启动Ray head进程（端口10001）
- 在所有Worker节点连接到Head节点
- 使用内网IP进行集群通信

#### 检查状态

```bash
./ray_cluster_manager.sh status
```

#### 停止集群

```bash
./ray_cluster_manager.sh stop
```

#### 在所有节点执行命令

```bash
# 查看GPU状态
./ray_cluster_manager.sh exec 'nvidia-smi'

# 查看Ray进程
./ray_cluster_manager.sh exec 'ps aux | grep ray'

# 查看网络配置
./ray_cluster_manager.sh exec 'ip addr show eth0'

# 检查环境变量
./ray_cluster_manager.sh exec 'echo $GLOO_SOCKET_IFNAME $NCCL_SOCKET_IFNAME'
```

## 网络配置

### 环境变量
脚本会自动设置以下环境变量：
- `GLOO_SOCKET_IFNAME=eth0` - GLOO通信接口
- `NCCL_SOCKET_IFNAME=eth0` - NCCL通信接口

### IP地址使用
- **SSH连接**: 使用外网IP（如123.206.111.143）
- **Ray集群通信**: 使用内网IP（如10.0.0.13）
- **Head节点地址**: 10.0.0.13:10001

## 故障排除

### 1. SSH连接失败
```bash
# 检查连接
./setup_ssh_keys.sh test

# 重新配置有问题的服务器
./setup_ssh_keys.sh setup-one 3
```

### 2. Ray启动失败
```bash
# 检查Ray进程
./ray_cluster_manager.sh exec 'ps aux | grep ray'

# 检查端口占用
./ray_cluster_manager.sh exec 'netstat -tulpn | grep 10001'

# 停止所有Ray进程后重新启动
./ray_cluster_manager.sh stop
sleep 5
./ray_cluster_manager.sh start
```

### 3. 网络连通性问题
```bash
# 检查内网连通性（在Head节点）
./ray_cluster_manager.sh exec 'ping -c 3 10.0.0.38'

# 检查端口连通性
./ray_cluster_manager.sh exec 'telnet 10.0.0.13 10001'
```

### 4. 环境问题
```bash
# 检查conda环境
./ray_cluster_manager.sh exec 'conda env list'

# 检查Python包
./ray_cluster_manager.sh exec 'conda run -n verl pip list | grep ray'
```

## 配置文件

### ray_cluster_config.txt 格式
```
# 格式: [head|worker]:外网IP:内网IP:ssh_port:username
head:123.206.111.143:10.0.0.13:22:wuyu
worker:43.142.113.152:10.0.0.38:22:wuyu
```

### 修改配置
如需修改服务器配置，编辑 `ray_cluster_config.txt` 文件：
```bash
vim ray_cluster_config.txt
```

## 常用命令组合

### 完整集群重建
```bash
./ray_cluster_manager.sh stop
./ray_cluster_manager.sh check
./ray_cluster_manager.sh start
./ray_cluster_manager.sh status
```

### 集群健康检查
```bash
./ray_cluster_manager.sh check
./ray_cluster_manager.sh status
./ray_cluster_manager.sh exec 'nvidia-smi | head -10'
```

### 批量环境检查
```bash
./ray_cluster_manager.sh exec 'conda list | grep torch'
./ray_cluster_manager.sh exec 'python -c "import ray; print(ray.__version__)"'
```

## 注意事项

1. **首次使用**：必须先配置SSH免密登录（现已支持自动密码配置）
2. **密码安全**：脚本已硬编码密码，生产环境建议使用环境变量
3. **端口占用**：确保10001端口未被占用
4. **网络环境**：确保内网IP可互相访问
5. **conda环境**：确保所有服务器都有verl环境
6. **防火墙**：确保相关端口已开放
7. **sshpass工具**：脚本会自动安装sshpass（需要root权限）

## 技术支持

如遇问题，请检查：
1. SSH免密登录是否正常
2. 网络连通性
3. Ray和conda环境
4. 防火墙设置
5. 端口占用情况 