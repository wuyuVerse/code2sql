# 2025-07-16 SQL Pattern Count 错误分析

## 问题描述

用户报告了在RL数据转换过程中出现的大量错误：

```
ERROR:data_processing.rl_data_converter:处理第 17165 条记录时出错: 'sql_pattern_cnt'
ERROR:data_processing.rl_data_converter:处理第 17166 条记录时出错: 'sql_pattern_cnt'
...
```

## 错误分析

### 错误类型
- **错误**: `KeyError: 'sql_pattern_cnt'`
- **位置**: `data_processing/rl_data_converter.py` 第143行
- **原因**: 模板格式化时缺少必需的参数

### 根本原因

在 `PROMPT_TEMPLATE` 模板中包含了以下占位符：
1. `{sql_pattern_cnt}` - 缺失
2. `{function_name}` - 已提供
3. `{code_value}` - 缺失（应该是 `orm_code`）
4. `{caller}` - 已提供
5. `{code_meta_data_str}` - 已提供

**注意**: 模板中**没有** `{callee}` 占位符，所以不需要提供 `callee` 参数

### 当前代码问题

```python
# 当前代码（有问题的）
user_content = PROMPT_TEMPLATE.format(
    function_name=function_name,
    orm_code=orm_code,  # 参数名不匹配
    caller=caller,
    code_meta_data_str=code_meta_data_str
    # 缺少 sql_pattern_cnt 和 code_value
)
```

### 解决方案

需要在 `create_rl_prompt` 方法中修正参数映射：

```python
# 修正后的代码
user_content = PROMPT_TEMPLATE.format(
    function_name=function_name,
    code_value=orm_code,  # 修正参数名
    caller=caller,
    code_meta_data_str=code_meta_data_str,
    sql_pattern_cnt=record.get('sql_pattern_cnt', 0)  # 添加缺失参数
)
```

**注意**: 不需要添加 `callee` 参数，因为模板中没有对应的占位符

## 影响范围

- 从第17165条记录开始的所有数据处理都失败
- 影响了RL训练数据的生成
- 需要修复后重新运行数据转换流程

## 修复建议

1. 修正 `data_processing/rl_data_converter.py` 中的 `create_rl_prompt` 方法
2. 确保所有模板占位符都有对应的参数
3. 添加参数验证，避免类似错误再次发生
4. 重新运行数据转换流程

## 相关文件

- `data_processing/rl_data_converter.py` - 主要错误文件
- `config/rl/data_conversion/orm2sql_prompt_template.py` - 模板定义文件
- `model/rl/training_output.txt` - 错误日志文件 