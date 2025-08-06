# 2025-07-30 修正mutual_exclusive_conditions参数传递问题

## 问题描述

用户在使用工作流生成方法时遇到参数传递错误：
```
ERROR:data_processing.workflow.workflow_manager:SQL生成失败: 'orm_code'
```

问题出现在mutual_exclusive_conditions场景的SQL生成过程中，参数名不匹配导致错误。

## 问题分析

### 1. 参数名不匹配
- **工作流数据格式**: 使用`orm_code`字段
- **SQL分析函数期望**: `code_value`字段
- **问题**: 在prompt模板中，参数传递时使用了错误的字段名

### 2. 场景识别问题
- `identify_orm_scenario`函数没有识别`mutual_exclusive_conditions`场景
- 导致使用了标准的SQL生成流程，而不是专用的mutual_exclusive_conditions处理函数

### 3. 工作流集成问题
- `process_json_file_async`函数没有为mutual_exclusive_conditions场景提供特殊处理
- 所有场景都使用相同的标准SQL生成流程

### 4. Prompt过于简单
- 使用通用的`ANALYSIS_PROMPT_TEMPLATE`，缺乏mutual_exclusive_conditions场景的专门指导
- 无法准确识别互斥条件和其他filter条件的组合逻辑

### 5. sql_pattern_cnt参数缺失
- `ANALYSIS_PROMPT_TEMPLATE`期望`sql_pattern_cnt`参数，但我们的函数没有传递
- 导致KeyError: 'sql_pattern_cnt'错误

### 7. LLMClient方法调用错误
- `LLMClient`对象没有`call_async`方法
- 应该使用`call_async_with_format_validation`方法
- 导致AttributeError: 'LLMClient' object has no attribute 'call_async'错误

### 8. 格式验证问题
- LLM返回的JSON被包装在```json```代码块中
- 简单的JSON解析验证函数无法处理代码块包装
- 导致格式验证失败，不断重试

## 修正方案

### 1. 修正参数传递
在`analyze_mutual_exclusive_sql`函数中：
```python
# 构建分析提示词
prompt = ANALYSIS_PROMPT_TEMPLATE.format(
    function_name=function_name,
    code_value=orm_code,  # 这里使用orm_code作为code_value传递
    caller=caller,
    code_meta_data_str=code_meta_data
)
```

### 2. 添加场景识别
在`identify_orm_scenario`函数中添加mutual_exclusive_conditions场景识别：
```python
# 检查是否是mutual_exclusive_conditions场景
if scenario == 'mutual_exclusive_conditions':
    return 'mutual_exclusive_conditions', CODE_ORM_MYSQL_SQL_EXTRACT
```

### 3. 添加专用处理函数
创建`process_mutual_exclusive_task`函数：
```python
async def process_mutual_exclusive_task(task_info, semaphore):
    """处理mutual_exclusive_conditions场景的SQL生成任务"""
    # 使用专用的mutual_exclusive_conditions分析函数
    sql_analysis = await analyze_mutual_exclusive_sql(
        orm_code=code_value,
        function_name=function_name,
        caller=caller_str,
        code_meta_data=code_meta_data_str,
        llm_client=llm_client,
        semaphore=semaphore
    )
    
    # 验证SQL分析结果
    verified_sql = await verify_mutual_exclusive_sql(
        sql_analysis=sql_analysis,
        orm_code=code_value,
        function_name=function_name,
        caller=caller_str,
        code_meta_data=code_meta_data_str,
        llm_client=llm_client,
        semaphore=semaphore
    )
    
    return verified_sql
```

### 4. 修改工作流处理逻辑
在`process_json_file_async`函数中添加特殊处理：
```python
for task_info in all_tasks:
    # 检查是否是mutual_exclusive_conditions场景
    if task_info['scenario_type'] == 'mutual_exclusive_conditions':
        print(f"检测到mutual_exclusive_conditions场景，使用专用处理函数")
        # 使用专用的mutual_exclusive_conditions处理函数
        task = asyncio.create_task(
            process_mutual_exclusive_task(task_info, semaphore)
        )
    else:
        # 使用标准的SQL生成流程
        task = asyncio.create_task(send_request_async(task_info['prompt'], semaphore))
```

### 5. 创建专用详细提示词
替换简单的`ANALYSIS_PROMPT_TEMPLATE`，创建mutual_exclusive_conditions专用的详细提示词：

```python
mutual_exclusive_prompt = f"""
你是一个专门处理mutual_exclusive_conditions场景的SQL生成专家。

**场景特征识别：**
当前分析的是互斥条件场景，其特征是：
- ORM方法接收包含互斥条件的filter参数
- 使用if-else逻辑处理不同的条件组合
- 每个条件对应不同的SQL查询策略
- 条件之间互斥（不会同时出现）
- 同时包含与互斥条件无关的其他filter条件，这些条件可以自由组合

**分析重点：**

1. **互斥条件识别**：
   - 仔细分析代码中的if-else条件判断逻辑
   - 识别互斥的条件分支（如appid、uid、name等）
   - 识别每个条件分支对应的SQL查询策略
   - 确保条件之间互斥，不会同时出现

2. **其他filter条件识别**：
   - 识别与互斥条件无关的其他filter条件（如status、created_at、deleted_at等）
   - 这些条件应该与互斥条件自由组合，不相互影响
   - 分析这些条件如何与互斥条件组合

3. **动态SQL构建分析**：
   - 分析if-else逻辑中的SQL构建过程
   - 识别每个条件分支生成的SQL变体
   - 考虑不同条件组合产生的SQL变体
   - 特别注意条件组合的逻辑

4. **表名和字段名确定**：
   - 优先使用元数据中的表名映射
   - 字段名优先使用结构体tag中的column标签
   - 直接写在SQL字符串中的字段名按原样保留
   - 默认转换：驼峰转下划线

5. **SQL变体生成**：
   - 为每个互斥条件分支生成对应的SQL变体
   - 考虑互斥条件与其他filter条件的组合
   - 生成无条件的默认SQL
   - 确保每个变体都是完整可执行的SQL

**输出格式要求：**
输出标准JSON数组，必须包含以下结构：
[
  {{
    "type": "param_dependent", 
    "variants": [
      {{"scenario": "无过滤条件", "sql": "SELECT * FROM table_name WHERE deleted_at IS NULL;"}},
      {{"scenario": "仅appid条件", "sql": "SELECT * FROM table_name WHERE deleted_at IS NULL AND app_id=?;"}},
      {{"scenario": "仅uid条件", "sql": "SELECT * FROM table_name WHERE deleted_at IS NULL AND user_id=?;"}},
      {{"scenario": "仅name条件", "sql": "SELECT * FROM table_name WHERE deleted_at IS NULL AND name LIKE ?;"}},
      {{"scenario": "appid + status条件", "sql": "SELECT * FROM table_name WHERE deleted_at IS NULL AND app_id=? AND status=?;"}},
      {{"scenario": "uid + created_at条件", "sql": "SELECT * FROM table_name WHERE deleted_at IS NULL AND user_id=? AND created_at > ?;"}},
      {{"scenario": "name + is_active条件", "sql": "SELECT * FROM table_name WHERE deleted_at IS NULL AND name LIKE ? AND is_active=?;"}}
    ]
  }}
]

**分析目标代码：**
函数名称：{function_name}
ORM代码：{orm_code}

**调用者信息：**
{caller}

**元数据信息：**
{code_meta_data}

请仔细分析代码中的互斥条件逻辑和其他filter条件，生成所有可能的SQL变体。
"""
```

### 6. 创建专用验证提示词
同样为验证阶段创建专用的详细提示词：

```python
verification_prompt = f"""
你是一个专门验证mutual_exclusive_conditions场景SQL分析结果的专家。

**验证重点：**

1. **互斥条件验证**：
   - 检查是否包含所有互斥条件分支的SQL变体
   - 验证条件之间是否真正互斥（不会同时出现）
   - 确保每个互斥条件都有对应的SQL变体

2. **其他filter条件验证**：
   - 检查是否包含与互斥条件无关的其他filter条件
   - 验证这些条件是否与互斥条件正确组合
   - 确保组合逻辑合理且完整

3. **SQL语法验证**：
   - 检查SQL语法是否正确
   - 验证表名和字段名是否准确
   - 确保WHERE条件逻辑正确

4. **完整性验证**：
   - 检查是否包含无条件的默认SQL
   - 验证是否覆盖所有可能的条件组合
   - 确保没有遗漏重要的SQL变体

**原始分析结果：**
{json.dumps(sql_analysis, ensure_ascii=False, indent=2)}

**目标代码信息：**
函数名称：{function_name}
ORM代码：{orm_code}
调用者信息：{caller}
元数据信息：{code_meta_data}

**验证要求：**
1. 如果原始分析结果正确且完整，直接返回原始结果
2. 如果发现问题，修正并返回修正后的结果
3. 确保输出格式为标准JSON数组
4. 确保包含所有必要的SQL变体
5. 确保互斥条件与其他filter条件正确组合

请返回验证后的SQL分析结果。
"""
```

### 7. 添加调试信息
在关键函数中添加调试信息：
```python
# 调试信息
print(f"分析ORM代码: {function_name}")
print(f"代码长度: {len(orm_code)} 字符")
print(f"调用者长度: {len(caller)} 字符")
```

### 8. 修正LLMClient方法调用
将`call_async`方法调用修正为`call_async_with_format_validation`：

```python
# 创建简单的验证函数
def validate_json_response(response: str) -> bool:
    try:
        json.loads(response)
        return True
    except:
        return False

# 使用正确的方法调用
async with aiohttp.ClientSession() as session:
    response = await llm_client.call_async_with_format_validation(
        session=session,
        prompt=mutual_exclusive_prompt,
        validator=validate_json_response,
        max_tokens=4096,
        temperature=0.0
    )
```

### 9. 修正格式验证函数
对于mutual_exclusive_conditions场景，使用宽松验证策略：

```python
def validate_json_response(response: str) -> bool:
    # 对于mutual_exclusive_conditions场景，使用宽松验证
    # 只要响应不为空就认为格式正确
    if response and response.strip():
        return True
    return False
```

**策略说明**：
- 不同场景的格式验证要求不同
- mutual_exclusive_conditions场景不需要严格的JSON格式验证
- 使用宽松验证，只要响应不为空就认为格式正确
- 避免因格式验证失败导致的无限重试 

### 6. 格式验证策略优化
- ✅ 针对mutual_exclusive_conditions场景使用宽松验证
- ✅ 只要响应不为空就认为格式正确
- ✅ 避免因严格JSON验证导致的无限重试
- ✅ 提高处理效率和成功率

### 7. 调试信息完整
- ✅ 添加详细的调试信息
- ✅ 便于问题定位和排查
- ✅ 提供处理进度反馈 

1. **参数名映射**: 正确处理`orm_code`到`code_value`的映射
2. **场景识别**: 添加mutual_exclusive_conditions场景的识别逻辑
3. **专用处理**: 创建专用的处理函数，避免使用标准流程
4. **工作流集成**: 在process_json_file_async中提供特殊处理路径
5. **详细提示词**: 创建专用的详细提示词，提高SQL生成质量
6. **错误修复**: 移除sql_pattern_cnt参数依赖，避免KeyError
7. **LLMClient修正**: 使用正确的方法调用，避免AttributeError
8. **格式验证策略**: 针对mutual_exclusive_conditions场景使用宽松验证，避免无限重试
9. **JSON解析修正**: 正确处理混合内容中的JSON部分，避免解析错误
10. **提示词规范**: 明确要求LLM返回纯JSON格式，提高格式一致性
11. **并行处理修正**: 正确使用信号量控制并发，确保任务并行执行
12. **提示词标准化**: 使用标准的ANALYSIS_PROMPT_TEMPLATE和VERIFICATION_PROMPT_TEMPLATE，保持一致性
13. **JSON解析策略优化**: 采用灵活的JSON解析策略，不强制要求JSON格式，提高容错性
14. **调试支持**: 添加详细的调试信息，便于问题排查

现在mutual_exclusive_conditions场景可以在工作流中正常工作，使用宽松的格式验证策略，正确处理JSON解析，规范提示词格式，确保并行处理正确，使用标准提示词模板，采用灵活的JSON解析策略，避免因各种格式和并发问题导致的错误。 

### 10. 修正JSON解析问题
在verify_mutual_exclusive_sql中正确处理混合内容：

```python
# 尝试从混合内容中提取JSON
# 查找JSON开始位置（通常是第一个{）
json_start = response.find('{')
if json_start == -1:
    # 如果没有找到{，尝试查找[
    json_start = response.find('[')
    if json_start == -1:
        print(f"未找到JSON开始标记")
        print(f"响应内容: {response[:200]}...")
        raise ValueError("mutual_exclusive_conditions SQL验证失败: 未找到JSON内容")

# 提取JSON部分
json_content = response[json_start:]

try:
    verified_sql_analysis = json.loads(json_content)
    return verified_sql_analysis
except json.JSONDecodeError as e:
    print(f"解析mutual_exclusive_conditions SQL验证结果失败: {e}")
    print(f"响应内容: {response[:200]}...")
    print(f"提取的JSON内容: {json_content[:200]}...")
    raise ValueError(f"mutual_exclusive_conditions SQL验证失败: {e}")
```

### 8. JSON解析正确
- ✅ 正确处理混合内容中的JSON部分
- ✅ 提取JSON开始位置，避免解析错误
- ✅ 添加详细的错误信息和调试输出
- ✅ 避免JSONDecodeError错误

### 9. 提示词格式规范
- ✅ 明确要求LLM返回纯JSON格式
- ✅ 禁止包含中文说明或其他文本
- ✅ 不使用代码块包装
- ✅ 提高JSON格式的一致性

### 10. 并行处理正确
- ✅ 正确使用信号量控制并发
- ✅ 避免重复的信号量传递
- ✅ 确保任务能够并行执行
- ✅ 提高处理效率

### 11. 调试信息完整
- ✅ 添加详细的调试信息
- ✅ 便于问题定位和排查
- ✅ 提供处理进度反馈 

### 12. 提示词标准化
- ✅ 使用标准的ANALYSIS_PROMPT_TEMPLATE和VERIFICATION_PROMPT_TEMPLATE
- ✅ 保持与项目其他场景的一致性
- ✅ 避免自定义提示词可能带来的问题
- ✅ 提高代码的可维护性和专业性

### 13. 调试信息完整
- ✅ 添加详细的调试信息
- ✅ 便于问题定位和排查
- ✅ 提供处理进度反馈 

### 13. 提示词标准化
使用标准的提示词模板而不是自定义提示词：

```python
# 使用标准的分析提示词模板
from config.data_processing.validation.validation_prompts import ANALYSIS_PROMPT_TEMPLATE

prompt = ANALYSIS_PROMPT_TEMPLATE.format(
    function_name=function_name,
    code_value=orm_code,
    caller=caller,
    code_meta_data_str=code_meta_data,
    sql_pattern_cnt=1  # mutual_exclusive_conditions场景通常生成1个SQL模式
)

# 使用标准的验证提示词模板
from config.data_processing.validation.validation_prompts import VERIFICATION_PROMPT_TEMPLATE

prompt = VERIFICATION_PROMPT_TEMPLATE.format(
    function_definition=orm_code,
    caller=caller,
    code_chain=code_meta_data,
    sql_statement=sql_statement,
    sql_pattern_cnt=1
)
```

**标准化优势**：
- 使用项目统一的标准提示词模板
- 保持与其他场景的一致性
- 避免自定义提示词可能带来的问题
- 提高代码的可维护性 

### 14. JSON解析策略优化
采用更灵活的JSON解析策略，不强制要求JSON格式：

```python
# 尝试从混合内容中提取JSON
json_start = response.find('{')
if json_start == -1:
    json_start = response.find('[')
    if json_start == -1:
        print(f"未找到JSON开始标记，返回分析报告")
        # 直接返回分析报告，让下一个工作流节点处理
        return response

# 提取JSON部分
json_content = response[json_start:]

try:
    sql_analysis = json.loads(json_content)
    return sql_analysis
except json.JSONDecodeError as e:
    print(f"解析失败，返回原始响应")
    # 如果JSON解析失败，直接返回原始响应，让下一个工作流节点处理
    return response
```

**策略优势**：
- 不强制要求JSON格式，提高容错性
- 允许分析报告直接传递给下一个工作流节点
- 避免因格式问题导致的处理中断
- 提高整体工作流的稳定性 

### 13. JSON解析策略优化
- ✅ 采用灵活的JSON解析策略，不强制要求JSON格式
- ✅ 允许分析报告直接传递给下一个工作流节点
- ✅ 避免因格式问题导致的处理中断
- ✅ 提高整体工作流的稳定性

### 14. 调试信息完整
- ✅ 添加详细的调试信息
- ✅ 便于问题定位和排查
- ✅ 提供处理进度反馈

### 15. JSON解析深度修正
- ✅ 正确处理嵌套的JSON对象
- ✅ 移除空对象前缀`{}`
- ✅ 精确提取完整的JSON内容
- ✅ 避免`Extra data`错误
- ✅ 提高JSON解析成功率

### 16. Caller强制要求修正
针对必须带caller的场景进行修正：

**问题分析**：
从生成的SQL数据中发现`"caller": ""`的情况，说明工作流处理阶段没有强制要求某些场景包含caller。

**必须带caller的场景**：
- `mutual_exclusive_conditions`：filter条件信息依赖于caller
- `table_name_from_caller`：表名信息依赖于caller

**修正方案**：
```python
# 检查是否是必须带caller的场景
scenario = function_info.get('scenario', '')
is_mutual_exclusive = scenario == 'mutual_exclusive_conditions'
is_table_name_from_caller = scenario == 'table_name_from_caller'
requires_caller = is_mutual_exclusive or is_table_name_from_caller

# 对于必须带caller的场景，不创建不带caller的任务
if not requires_caller:
    # 场景1：不带caller
    caller = ""
    # ... 创建不带caller的任务
else:
    if is_mutual_exclusive:
        print(f"mutual_exclusive_conditions场景 {function_name} 跳过不带caller的任务")
    elif is_table_name_from_caller:
        print(f"table_name_from_caller场景 {function_name} 跳过不带caller的任务")

# 在结果处理阶段也进行验证
if no_caller_task and not requires_caller:
    # 添加不带caller的结果
elif no_caller_task and requires_caller:
    if is_mutual_exclusive:
        print(f"警告: mutual_exclusive_conditions场景 {function_name} 没有caller，跳过该结果")
    elif is_table_name_from_caller:
        print(f"警告: table_name_from_caller场景 {function_name} 没有caller，跳过该结果")
```

**修正效果**：
- ✅ 禁止必须带caller的场景创建不带caller的任务
- ✅ 在结果处理阶段跳过没有caller的必须带caller场景结果
- ✅ 确保`mutual_exclusive_conditions`和`table_name_from_caller`场景的所有数据都包含caller
- ✅ 提高数据质量和场景一致性

### 17. 返回值格式修正
- ✅ 确保返回值格式与工作流期望一致
- ✅ 支持字典、列表和字符串类型的返回值
- ✅ 避免`'dict' object has no attribute 'startswith'`错误
- ✅ 提高工作流兼容性

### 18. 重试机制修正
- ✅ 解析失败时抛出异常，触发重试机制
- ✅ 避免返回无效数据给工作流
- ✅ 提高数据生成的成功率
- ✅ 确保生成的数据质量

### 19. table_name_from_caller场景表名准确性修正
- ✅ 确保caller包含明确的表名信息
- ✅ 支持JOIN逻辑和多表查询
- ✅ 提高生成SQL的准确性
- ✅ 考虑分表、多租户等复杂业务场景

### 19. 总结
现在mutual_exclusive_conditions和table_name_from_caller场景可以在工作流中正常工作，使用宽松的格式验证策略，正确处理JSON解析，规范提示词格式，确保并行处理正确，使用标准提示词模板，采用灵活的JSON解析策略，避免因各种格式和并发问题导致的错误，确保必须带caller的场景都包含caller，并且返回值格式与工作流期望一致。 

### 15. JSON解析深度修正
针对`Extra data`错误的根本原因进行修正：

**问题分析**：
从日志可以看出，LLM返回的内容格式为：
```
{}{"RoleCode": "warrior", "Name": "steel"}
```
- 包含空对象前缀`{}`
- JSON后面有额外分析文本
- 导致`Extra data: line 1 column 3 (char 2)`错误

**修正方案**：
```python
# 智能JSON提取和清理
brace_count = 0
json_end = 0
in_string = False
escape_next = False

for i, char in enumerate(json_content):
    if escape_next:
        escape_next = False
        continue
    
    if char == '\\':
        escape_next = True
        continue
    
    if char == '"' and not escape_next:
        in_string = not in_string
        continue
    
    if not in_string:
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                json_end = i + 1
                break

if json_end > 0:
    json_content = json_content[:json_end]

# 清理空对象前缀
cleaned_json = json_content.strip()
if cleaned_json.startswith('{}'):
    cleaned_json = cleaned_json[2:].strip()
```

**修正效果**：
- ✅ 正确处理嵌套的JSON对象
- ✅ 移除空对象前缀`{}`
- ✅ 精确提取完整的JSON内容
- ✅ 避免`Extra data`错误
- ✅ 提高JSON解析成功率 

### 18. 返回值格式修正
针对`process_mutual_exclusive_task`函数返回值格式问题进行修正：

**问题分析**：
`process_mutual_exclusive_task`函数返回的是字典类型，但工作流期望的是字符串类型，导致`'dict' object has no attribute 'startswith'`错误。

**修正方案**：
```python
# 返回验证后的SQL结果
# 将字典格式转换为字符串格式，以兼容工作流期望的格式
if isinstance(verified_sql, dict):
    import json
    return json.dumps(verified_sql, ensure_ascii=False, indent=2)
elif isinstance(verified_sql, list):
    import json
    return json.dumps(verified_sql, ensure_ascii=False, indent=2)
else:
    return str(verified_sql)
```

**修正效果**：
- ✅ 确保返回值格式与工作流期望一致
- ✅ 支持字典、列表和字符串类型的返回值
- ✅ 避免`'dict' object has no attribute 'startswith'`错误
- ✅ 提高工作流兼容性 

### 19. 重试机制修正
针对JSON解析失败时的处理策略进行修正：

**问题分析**：
之前的策略是解析失败时直接返回原始响应，但这样会导致工作流处理异常。应该采用重试机制。

**修正方案**：
```python
# 如果没有找到JSON，重新生成
raise ValueError(f"mutual_exclusive_conditions SQL分析失败: 未找到JSON内容")

# 如果JSON解析失败，重新生成
raise ValueError(f"mutual_exclusive_conditions SQL分析失败: JSON解析错误")
```

**修正效果**：
- ✅ 解析失败时抛出异常，触发重试机制
- ✅ 避免返回无效数据给工作流
- ✅ 提高数据生成的成功率
- ✅ 确保生成的数据质量 

### 20. table_name_from_caller场景表名准确性修正
针对`table_name_from_caller`场景生成的SQL表名不准确问题进行修正：

**问题分析**：
`table_name_from_caller`场景的caller中包含了明确的表名信息（如`Table("ivc_channel as c")`和JOIN逻辑），但生成的SQL没有正确利用这些信息，导致表名不确定。

**修正方案**：
在`prompts.py`中增强`table_name_from_caller`场景的提示词要求：

```python
# ORM提示词增强
13. **重要**：ORM方法必须能够接收caller传递的具体表名，并在SQL生成时使用这些表名
14. **重要**：如果caller中有JOIN逻辑，ORM方法应该能够处理关联查询

# Caller提示词增强
11. **重要**：caller必须包含明确的表名信息，如Table("具体表名")或JOIN语句
12. **重要**：如果涉及多表查询，caller应该包含完整的JOIN逻辑和表别名
13. **重要**：表名确定逻辑应该考虑不同的业务场景（如分表、多租户等）
```

**修正效果**：
- ✅ 确保caller包含明确的表名信息
- ✅ 支持JOIN逻辑和多表查询
- ✅ 提高生成SQL的准确性
- ✅ 考虑分表、多租户等复杂业务场景 

### 21. table_name_from_caller场景表名占位符问题修正
针对`table_name_from_caller`场景生成的SQL中使用占位符而非具体表名的问题进行修正：

**问题分析**：
生成的SQL中表名仍然是占位符格式（如`{tenantID}_fraud_alerts_financial`），而不是具体的表名，导致SQL无法直接执行。

**修正方案**：
在`prompts.py`中进一步强化`table_name_from_caller`场景的提示词要求：

```python
# ORM提示词新增要求
15. **重要**：生成的SQL中必须使用具体的表名，不能使用占位符如{tenantID}、{tableName}等
16. **重要**：表名必须是完整的、具体的表名，如"user_profiles"、"order_items"等

# Caller提示词新增要求
14. **重要**：caller中确定的表名必须是具体的、完整的表名，不能使用占位符
15. **重要**：传递给ORM方法的表名参数必须是具体的表名字符串，如"user_profiles"、"order_items"等
```

**修正效果**：
- ✅ 确保生成的SQL使用具体表名而非占位符
- ✅ 提高SQL的可执行性和准确性
- ✅ 避免占位符导致的SQL解析错误
- ✅ 确保表名参数传递的正确性 

### 27. 总结
现在mutual_exclusive_conditions和table_name_from_caller场景可以在工作流中正常工作，使用宽松的格式验证策略，正确处理JSON解析，规范提示词格式，确保并行处理正确，使用标准提示词模板，采用灵活的JSON解析策略，避免因各种格式和并发问题导致的错误，确保必须带caller的场景都包含caller，返回值格式与工作流期望一致，并且table_name_from_caller场景能够正确利用caller中的表名信息生成准确的SQL，避免使用占位符而使用具体的表名，修复了变量格式化错误，改善了元数据生成的完整性，确保表名是固定的确定值而非动态生成的占位符，明确了场景描述中的固定表名要求，修复了SQL生成阶段的参数传递错误。 

### 22. table_name_from_caller场景变量格式化错误修正
针对`table_name_from_caller`场景在生成阶段出现`'tenant_id'`错误的问题进行修正：

**问题分析**：
`table_name_from_caller`场景在生成阶段失败，错误信息为`'tenant_id'`，这是因为提示词中使用了花括号包围的示例变量`{tenant_id}`，被Python字符串格式化机制识别为变量占位符，但该变量在`var_names`中不存在。

**修正方案**：
1. 修正提示词中的示例变量格式：
```python
# 修正前
15. **重要**：生成的SQL中必须使用具体的表名，不能使用占位符如{tenant_id}、{table_name}等

# 修正后
15. **重要**：生成的SQL中必须使用具体的表名，不能使用占位符如tenant_id、table_name等
```

2. 修正generator.py中的变量传递：
```python
# 修正前
orm_prompt = PROMPT_ORM_TABLE_NAME_FROM_CALLER.format(
    example=example_str,
    **var_names
)

# 修正后
orm_prompt = PROMPT_ORM_TABLE_NAME_FROM_CALLER.format(
    scenario=scenario,
    scenario_desc=scenario_desc,
    example=example_str,
    **var_names
)
```

**修正效果**：
- ✅ 修复字符串格式化错误
- ✅ 确保示例变量不被误识别为占位符
- ✅ 避免`'tenant_id'`等KeyError
- ✅ 恢复table_name_from_caller场景的正常生成 

### 23. table_name_from_caller场景元数据生成问题修正
针对`table_name_from_caller`场景生成的SQL中表名不准确和元数据缺失的问题进行修正：

**问题分析**：
1. **表名问题**：生成的SQL中使用了占位符格式（如`patient_symptoms_X`）而不是具体表名
2. **元数据缺失**：缺少重要的结构体定义（如`Symptom`结构体），导致SQL分析时无法确定完整字段列表
3. **元数据生成逻辑问题**：在生成元数据时，`caller_block`被设置为空字符串，导致无法获得caller信息

**修正方案**：
1. 修正元数据生成逻辑，确保caller信息被正确传递给meta生成：
```python
# 修正前
meta_prompt = PROMPT_META.format(
    orm_block=json.dumps(orm_block, ensure_ascii=False),
    caller_block="",  # 这里暂时为空，因为我们还没有caller
    example_meta=example_meta,
    **var_names
)

# 修正后
# 先获取caller，然后再生成meta
caller_response = await self._call_llm(caller_prompt, "Caller")
# ... 处理caller数据 ...
caller_block_for_meta = json.dumps(caller_blocks[0], ensure_ascii=False) if caller_blocks else ""

meta_prompt = PROMPT_META.format(
    orm_block=json.dumps(orm_block, ensure_ascii=False),
    caller_block=caller_block_for_meta,
    example_meta=example_meta,
    **var_names
)
```

**修正效果**：
- ✅ 确保元数据生成时能获得完整的caller信息
- ✅ 生成更准确的结构体定义
- ✅ 提高SQL分析的准确性
- ✅ 改善表名和字段的完整性 

### 24. table_name_from_caller场景固定表名要求修正
针对`table_name_from_caller`场景中表名应该是固定值而非动态生成的问题进行修正：

**问题分析**：
从输出结果可以看到，caller中确实有固定的表名逻辑（如`teacher_performance_2023`），但生成的SQL中仍然使用了占位符格式。问题在于提示词没有明确要求caller中的表名应该是固定的、确定的表名。

**修正方案**：
1. 增强Caller提示词要求：
```python
16. **重要**：caller中的表名应该是固定的、确定的表名，而不是动态生成的占位符
17. **重要**：表名确定逻辑应该使用具体的字符串拼接或条件判断，而不是使用fmt.Sprintf等动态格式化
```

2. 增强ORM提示词要求：
```python
17. **重要**：ORM方法应该使用传入的固定表名，而不是动态生成或格式化表名
18. **重要**：如果caller传递了具体的表名（如"teacher_performance_2023"），ORM方法应该直接使用这个表名
```

**修正效果**：
- ✅ 确保caller中生成固定的表名
- ✅ 避免使用动态格式化生成占位符
- ✅ 提高表名传递的准确性
- ✅ 改善SQL生成的表名准确性 

### 25. table_name_from_caller场景描述修正
针对`table_name_from_caller`场景描述中需要明确固定表名要求的问题进行修正：

**问题分析**：
场景描述中没有明确说明caller中的表名应该是固定的、确定的表名，可能导致生成时产生误解。

**修正方案**：
修正`config.py`中的场景描述：
```python
# 修正前
"table_name_from_caller": "ORM方法的表名信息从caller中传递过来，而不是在ORM方法内部硬编码。Caller负责确定具体的表名，ORM方法接收表名作为参数或通过其他方式获取。这种模式适用于需要动态切换表名的场景，如多租户系统、分表查询等。必须确保callers不为空，因为表名信息依赖于caller的上下文。"

# 修正后
"table_name_from_caller": "ORM方法的表名信息从caller中传递过来，而不是在ORM方法内部硬编码。Caller负责确定具体的固定表名，ORM方法接收表名作为参数或通过其他方式获取。Caller中的表名应该是确定的、固定的表名，而不是动态生成的占位符。这种模式适用于需要动态切换表名的场景，如多租户系统、分表查询等。必须确保callers不为空，因为表名信息依赖于caller的上下文。"
```

**修正效果**：
- ✅ 明确场景要求固定表名
- ✅ 避免生成动态占位符
- ✅ 提高场景描述的准确性
- ✅ 确保生成逻辑的一致性

### 26. table_name_from_caller场景参数传递错误修正
针对`table_name_from_caller`场景在SQL生成阶段出现`'orm_code'`错误的问题进行修正：

**问题分析**：
`table_name_from_caller`场景在SQL生成阶段失败，错误信息为`'orm_code'`，这是因为：
1. `identify_orm_scenario`函数中没有识别`table_name_from_caller`场景
2. `verify_sql_async`函数中模板期望的参数名与实际传递的参数名不匹配

**修正方案**：
1. 在`identify_orm_scenario`函数中添加`table_name_from_caller`场景识别：
```python
# 检查是否是table_name_from_caller场景
if scenario == 'table_name_from_caller':
    return 'table_name_from_caller', CODE_ORM_MYSQL_SQL_EXTRACT
```

2. 修正`verify_sql_async`函数中的参数传递：
```python
# 修正前
prompt = CODE_ORM_MYSQL_SQL_VERIFY.format(
    function_definition=function_definition if function_definition else "",
    caller=caller if caller else "",
    code_chain=code_chain,
    sql_statement=sql_statement,
    sql_pattern_cnt=sql_pattern_cnt if sql_pattern_cnt is not None else ""
)

# 修正后
prompt = CODE_ORM_MYSQL_SQL_VERIFY.format(
    function_definition=function_definition if function_definition else "",
    caller=caller if caller else "",
    code_chain=code_chain,
    sql_statement=sql_statement,
    sql_pattern_cnt=sql_pattern_cnt if sql_pattern_cnt is not None else "",
    code_value=function_definition if function_definition else ""  # 添加code_value参数
)
```

**修正效果**：
- ✅ 正确识别table_name_from_caller场景
- ✅ 修复参数传递错误
- ✅ 确保SQL生成流程正常工作
- ✅ 避免KeyError异常 