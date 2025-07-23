# LLM格式验证使用指南

## 概述

本项目提供了统一的LLM格式验证和重试机制，确保LLM返回的内容符合预期格式。当模型返回不符合要求的格式时，系统会自动重试并提示模型重新生成。

## 核心功能

### 1. 格式验证方法

LLMClient类新增了两个带格式验证的方法：

- `call_async_with_format_validation()`: 异步调用，带格式验证
- `call_openai_with_format_validation()`: 使用OpenAI库调用，带格式验证

### 2. 预定义验证器

在 `utils/format_validators.py` 中提供了多种预定义验证器：

- `validate_json_format()`: 验证JSON格式
- `validate_boolean_response()`: 验证布尔值响应
- `validate_structured_response()`: 验证结构化响应
- `validate_sql_completeness_response()`: 验证SQL完整性检查响应
- `validate_sql_correctness_response()`: 验证SQL正确性检查响应
- `validate_keyword_extraction_response()`: 验证关键词提取响应
- `validate_redundant_sql_validation_response()`: 验证冗余SQL验证响应
- `validate_control_flow_validation_response()`: 验证控制流验证响应
- `validate_synthetic_data_response()`: 验证合成数据生成响应

## 使用示例

### 1. 基本使用

```python
from utils.llm_client import LLMClient
from utils.format_validators import validate_json_format

# 创建客户端
llm_client = LLMClient("v3")

# 异步调用带格式验证
async def example_async():
    async with aiohttp.ClientSession() as session:
        response = await llm_client.call_async_with_format_validation(
            session=session,
            prompt="请返回一个JSON格式的用户信息",
            validator=validate_json_format,
            max_tokens=500,
            temperature=0.0,
            max_retries=3
        )
        print(response)

# 同步调用带格式验证
async def example_sync():
    async with aiohttp.ClientSession() as session:
        response = await llm_client.call_async_with_format_validation(
            session,
            "请返回一个JSON格式的用户信息",
            validator=validate_json_format,
            max_tokens=500,
            temperature=0.0,
            max_retries=3
        )
        print(response)
```

### 2. 自定义验证器

```python
def custom_validator(response: str) -> Union[bool, Dict[str, Any]]:
    """自定义验证器"""
    if not response:
        return {
            'valid': False,
            'error': '响应为空'
        }
    
    # 检查是否包含特定关键词
    if 'success' in response.lower():
        return True
    
    return {
        'valid': False,
        'error': '响应不包含期望的关键词',
        'response': response[:100]
    }

# 使用自定义验证器
response = await llm_client.call_async_with_format_validation(
    session=session,
    prompt="请确认操作是否成功",
    validator=custom_validator,
    max_tokens=100,
    temperature=0.0
)
```

### 3. 带参数的验证器

```python
from utils.format_validators import get_validator

# 获取带参数的验证器
validator = get_validator('structured', required_fields=['name', 'age'])

response = await llm_client.call_async_with_format_validation(
    session=session,
    prompt="请返回用户信息，包含姓名和年龄",
    validator=validator,
    max_tokens=200,
    temperature=0.0
)
```

### 4. 自定义重试提示

```python
custom_retry_prompt = """您的回答格式不正确，请严格按照JSON格式回答。

原始问题：
{prompt}

请确保：
1. 返回有效的JSON格式
2. 包含所有必需字段
3. 不要添加额外的说明

请重新回答："""

response = await llm_client.call_async_with_format_validation(
    session=session,
    prompt="请返回用户信息",
    validator=validate_json_format,
    format_retry_prompt=custom_retry_prompt,
    max_tokens=200,
    temperature=0.0
)
```

## 验证器返回值

验证器函数应返回以下格式之一：

### 1. 简单布尔值
```python
def simple_validator(response: str) -> bool:
    return 'success' in response.lower()
```

### 2. 详细验证结果
```python
def detailed_validator(response: str) -> Dict[str, Any]:
    if 'success' in response.lower():
        return {
            'valid': True,
            'content': response,
            'parsed_data': parse_data(response)
        }
    else:
        return {
            'valid': False,
            'error': '响应不包含成功标识',
            'response': response[:100]
        }
```

## 错误处理

### 1. 网络错误
- 系统会自动重试网络请求
- 使用指数退避策略
- 记录详细的错误日志

### 2. 格式错误
- 系统会提示模型重新生成
- 包含具体的错误信息
- 支持自定义重试提示

### 3. 验证失败
- 达到最大重试次数后返回最后一次响应
- 记录验证失败的原因
- 提供调试信息

## 最佳实践

### 1. 选择合适的验证器
- 对于JSON响应，使用 `validate_json_format`
- 对于布尔值响应，使用 `validate_boolean_response`
- 对于结构化数据，使用 `validate_structured_response`

### 2. 设置合理的重试次数
- 网络错误：5-10次
- 格式错误：3-5次
- 根据业务重要性调整

### 3. 提供清晰的提示词
- 明确说明期望的格式
- 提供示例
- 避免歧义

### 4. 监控和日志
- 记录验证失败的情况
- 分析失败原因
- 优化提示词

## 集成到现有代码

### 1. 替换现有的LLM调用

```python
# 原来的调用
response = await llm_client.call_async(session, prompt, max_tokens=500)

# 替换为带验证的调用
from utils.format_validators import validate_json_format
response = await llm_client.call_async_with_format_validation(
    session, prompt, validator=validate_json_format, max_tokens=500
)
```

### 2. 处理验证结果

```python
# 如果验证器返回字典格式
if isinstance(response, dict) and 'valid' in response:
    if response['valid']:
        content = response.get('content', '')
        # 处理成功的结果
    else:
        error = response.get('error', '未知错误')
        # 处理验证失败
else:
    # 处理简单字符串响应
    content = response
```

## 注意事项

1. **性能影响**: 格式验证会增加一些处理时间，但能显著提高响应质量
2. **重试成本**: 多次重试会增加API调用成本，需要平衡质量和成本
3. **提示词优化**: 良好的提示词可以减少格式错误的发生
4. **错误处理**: 确保代码能正确处理验证失败的情况
5. **日志记录**: 记录验证失败的情况，便于分析和优化 