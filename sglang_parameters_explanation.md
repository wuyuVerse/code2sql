# SGLang启动参数详细说明

## 基于当前运行服务的配置参数分析

### 核心参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--model-path` | `/data/local_disk0/wuyu/save_model/saves/qwen3-14b-ft-20250710_154849` | 模型路径 |
| `--host` | `0.0.0.0` | 服务监听地址 |
| `--port` | `8001` | 服务端口 |
| `--tp-size` | `2` | Tensor Parallel大小，使用2张GPU |

### 内存和性能参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--mem-fraction-static` | `0.864` | 静态内存分配比例，占用86.4%的GPU内存 |
| `--chunked-prefill-size` | `8192` | 分块预填充大小 |
| `--max-prefill-tokens` | `16384` | 最大预填充token数 |
| `--cpu-offload-gb` | `0` | CPU卸载内存大小（GB） |

### 调度参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--schedule-policy` | `fcfs` | 调度策略：先到先服务 |
| `--schedule-conservativeness` | `1.0` | 调度保守程度 |
| `--page-size` | `1` | 页面大小 |

### 后端配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `--sampling-backend` | `flashinfer` | 采样后端：使用flashinfer |
| `--grammar-backend` | `xgrammar` | 语法后端：使用xgrammar |
| `--lora-backend` | `triton` | LoRA后端：使用triton |

### 优化参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--disable-radix-cache` | `true` | 禁用radix缓存 |
| `--disable-cuda-graph` | `true` | 禁用CUDA图优化 |
| `--stream-interval` | `1` | 流式输出间隔 |
| `--stream-output` | `false` | 禁用流式输出 |

### 监控和日志参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--log-level` | `info` | 日志级别 |
| `--log-requests` | `false` | 不记录请求日志 |
| `--enable-metrics` | `false` | 不启用指标监控 |
| `--show-time-cost` | `false` | 不显示时间成本 |

### 并行配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `--tp-size` | `2` | Tensor Parallel大小 |
| `--pp-size` | `1` | Pipeline Parallel大小 |
| `--dp-size` | `1` | Data Parallel大小 |
| `--ep-size` | `1` | Expert Parallel大小 |

### 高级参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `--random-seed` | `80244742` | 随机种子 |
| `--watchdog-timeout` | `300` | 看门狗超时时间（秒） |
| `--decode-log-interval` | `40` | 解码日志间隔 |
| `--num-reserved-decode-tokens` | `512` | 保留的解码token数 |

## 启动命令对比

### 完整版启动命令
```bash
nohup env CUDA_VISIBLE_DEVICES=0,1 python -m sglang.launch_server \
  --model-path /data/local_disk0/wuyu/save_model/saves/qwen3-14b-ft-20250710_154849 \
  --host 0.0.0.0 --port 8001 --tp-size 2 \
  --mem-fraction-static 0.864 --chunked-prefill-size 8192 \
  --max-prefill-tokens 16384 --sampling-backend flashinfer \
  --grammar-backend xgrammar --disable-radix-cache \
  --disable-cuda-graph > code2sql_sglang_8001.log 2>&1 &
```

### 简化版启动命令
```bash
nohup env CUDA_VISIBLE_DEVICES=0,1 python -m sglang.launch_server \
  --model-path /data/local_disk0/wuyu/save_model/saves/qwen3-14b-ft-20250710_154849 \
  --host 0.0.0.0 --port 8001 --tp-size 2 \
  > code2sql_sglang_8001.log 2>&1 &
```

## 性能分析

### 当前配置特点
1. **内存使用**: 每个GPU占用约85GB内存（85700MiB）
2. **并行策略**: 使用2张GPU进行tensor parallel
3. **优化设置**: 禁用了radix缓存和CUDA图优化
4. **调度策略**: 采用先到先服务的调度策略

### 建议优化
1. **启用监控**: 添加 `--enable-metrics` 和 `--log-requests`
2. **增加并发**: 调整 `--max-running-requests` 和 `--max-total-tokens`
3. **性能监控**: 启用 `--show-time-cost` 查看性能指标

## 使用说明

### 启动服务
```bash
chmod +x sglang_start_simple.sh
./sglang_start_simple.sh
```

### 查看状态
```bash
# 查看进程
ps aux | grep sglang

# 查看GPU使用
nvidia-smi

# 查看日志
tail -f code2sql_sglang_8001.log
```

### 测试服务
```bash
# 健康检查
curl http://localhost:8001/health

# 测试API
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-14b-ft-20250710_154849","messages":[{"role":"user","content":"你好"}]}'
``` 