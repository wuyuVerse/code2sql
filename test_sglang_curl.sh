#!/bin/bash

# 测试sglang API访问的bash脚本

echo "=== 测试sglang API访问 ==="

# 服务地址
BASE_URL="http://localhost:8001"

# 1. 测试服务状态
echo "1. 测试服务状态..."
curl -s "$BASE_URL/health" || echo "服务未启动"

# 2. 获取模型信息
echo -e "\n2. 获取模型信息..."
curl -s "$BASE_URL/v1/models" | jq '.' 2>/dev/null || curl -s "$BASE_URL/v1/models"

# 3. 测试聊天API
echo -e "\n3. 测试聊天API..."
curl -X POST "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-14b-ft-20250710_154849",
    "messages": [
      {
        "role": "system",
        "content": "你是一个有用的助手。"
      },
      {
        "role": "user",
        "content": "你好，请用SQL查询所有年龄大于20岁的用户"
      }
    ],
    "temperature": 0.1,
    "max_tokens": 256
  }' | jq '.' 2>/dev/null || curl -X POST "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-14b-ft-20250710_154849",
    "messages": [
      {
        "role": "system",
        "content": "你是一个有用的助手。"
      },
      {
        "role": "user",
        "content": "你好，请用SQL查询所有年龄大于20岁的用户"
      }
    ],
    "temperature": 0.1,
    "max_tokens": 256
  }'

echo -e "\n=== 测试完成 ===" 