# 2025-07-30 新增table_name_from_caller场景

## 任务概述

用户要求新增一个场景，其中表名从caller中传递过来，而不是在ORM方法内部硬编码。这个场景的特点是：

1. **必须有caller**（不能为空）
2. **表名信息在caller中定义**
3. **不需要修改现有的get_sql提示词**
4. **在生成时确保callers不为空**

## 实现方案

### 1. 场景定义

在 `config/data_processing/synthetic_data_generator/config.py` 中添加新场景：

```python
"table_name_from_caller": "ORM方法的表名信息从caller中传递过来，而不是在ORM方法内部硬编码。Caller负责确定具体的表名，ORM方法接收表名作为参数或通过其他方式获取。这种模式适用于需要动态切换表名的场景，如多租户系统、分表查询等。必须确保callers不为空，因为表名信息依赖于caller的上下文。"
```

### 2. 专用提示词设计

在 `config/data_processing/synthetic_data_generator/prompts.py` 中添加：

#### ORM提示词 (PROMPT_ORM_TABLE_NAME_FROM_CALLER)
- 生成接收表名参数的ORM方法
- 不能硬编码表名，表名必须通过参数传递或动态获取
- 使用Table()方法设置动态表名
- 包含适当的错误处理

#### Caller提示词 (PROMPT_CALLER_TABLE_NAME_FROM_CALLER)
- 生成确定表名并传递给ORM的调用者
- 必须包含表名确定逻辑（如根据参数、配置、环境等确定表名）
- 将确定的表名传递给ORM方法
- 确保caller不为空，因为表名信息依赖于caller的上下文

### 3. 生成器集成

在 `data_processing/synthetic_data_generator/generator.py` 中：

#### 场景选择逻辑
```python
elif scenario == "table_name_from_caller":
    from config.data_processing.synthetic_data_generator.prompts import PROMPT_ORM_TABLE_NAME_FROM_CALLER
    orm_prompt = PROMPT_ORM_TABLE_NAME_FROM_CALLER.format(
        example=example_str,
        **var_names
    )
```

#### 强制Caller生成
```python
elif scenario == "table_name_from_caller":
    # table_name_from_caller场景必须生成caller，因为表名信息依赖于caller
    self._thread_safe_print("  - table_name_from_caller场景必须生成caller...")
    # ... 生成逻辑 ...
    # 确保callers不为空
    if not caller_blocks:
        raise ValueError("table_name_from_caller场景必须生成caller，但生成的callers为空")
```

### 4. 测试验证

创建 `data_processing/synthetic_data_generator/test_table_name_from_caller.py` 测试脚本：

#### 验证要点
- ✅ ORM代码包含Table()方法调用
- ✅ Caller包含表名确定逻辑
- ✅ Callers不为空（符合要求）
- ✅ 使用标准SQL分析函数进行SQL生成验证

## 核心特点

### 1. 表名动态化
- ORM方法接收表名参数而不是硬编码
- 支持多租户、分表等动态表名场景

### 2. Caller依赖
- 必须生成caller，因为表名信息依赖于caller的上下文
- Caller负责确定具体的表名并传递给ORM

### 3. 标准SQL分析
- 不需要重新设计get_sql的提示词
- 使用现有的标准SQL分析函数
- 保持与现有系统的一致性

### 4. 强制验证
- 在生成时确保callers不为空
- 验证ORM代码包含Table()方法调用
- 验证Caller包含表名确定逻辑

## 使用方式

```bash
# 生成table_name_from_caller场景数据
python -m data_processing.synthetic_data_generator.cli --scenario "table_name_from_caller" --count 5

# 测试新场景
python data_processing/synthetic_data_generator/test_table_name_from_caller.py
```

## 与现有场景的区别

| 场景 | 特点 | 表名来源 | Caller要求 | SQL分析 |
|------|------|----------|------------|---------|
| mutual_exclusive_conditions | 互斥条件处理 | 硬编码或元数据 | 必须包含if-else逻辑 | 专用提示词 |
| table_name_from_caller | 动态表名 | 从caller传递 | 必须包含表名确定逻辑 | 标准分析函数 |

## 总结

成功实现了table_name_from_caller场景，该场景：

1. **满足用户需求**：表名从caller中传递，确保callers不为空
2. **保持系统一致性**：使用标准SQL分析函数，无需修改get_sql.py
3. **提供专业实现**：包含完整的生成、验证和测试流程
4. **支持动态场景**：适用于多租户、分表等需要动态表名的业务场景

这个新场景为处理动态表名需求提供了专门的支持，确保生成的代码能够正确处理表名从caller传递的场景。 