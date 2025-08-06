# 反向SQL生成器if-else+orm场景修复

## 问题描述

用户发现反向SQL生成器在处理"if-else+orm"场景时存在问题：

1. **错误处理逻辑**：系统错误地重新生成ORM代码，而不是生成if-else+orm Caller
2. **缺少提示词模板**：SQL生成器缺少`if_else_orm_variants`模板
3. **流程混乱**：if-else+orm场景被错误地当作普通if-else场景处理

## 问题分析

### 1. 逻辑错误
在`data_processing/reverse_sql_generator/generator.py`中，存在一个通用的"if-else"处理逻辑（第85-95行），它会检查场景名称中是否包含"orm"，如果是，就会重新生成ORM代码。这个逻辑在"if-else+orm"场景的专门处理逻辑之前执行，导致覆盖了正确的处理流程。

### 2. 缺少模板
SQL生成器在尝试生成if-else+orm变体时，找不到对应的提示词模板`if_else_orm_variants`，导致抛出错误：
```
ValueError: 不支持的变体类型: if_else_orm，模板键: if_else_orm_variants
```

## 修复方案

### 1. 修复逻辑顺序
将"if-else+orm"场景的处理逻辑移到"if-else"通用逻辑之前，确保正确的处理流程：

```python
# 修复前
if "if-else" in scenario:
    if "orm" in scenario:
        # 错误的处理逻辑
        ...

elif "if-else+orm" in scenario:
    # 正确的处理逻辑（永远不会执行）
    ...

# 修复后
if "if-else+orm" in scenario:
    # 正确的处理逻辑
    ...

elif "if-else" in scenario:
    # 通用if-else处理逻辑
    ...
```

### 2. 添加缺失的提示词模板
在`config/data_processing/reverse_sql_generator/prompts.py`中添加`if_else_orm_variants`模板：

```python
"if_else_orm_variants": """
基于以下基础SQL查询，生成if-else+orm分支的SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成2-3个不同的SQL变体，对应不同的if-else+orm分支
2. 每个变体应该有不同的WHERE条件组合，模拟ORM内部的if-else逻辑
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段
6. 变体应该反映ORM方法内部的if-else条件判断

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {
        "query": "if-else+orm分支1的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {
                "field": "字段名",
                "operator": "操作符", 
                "value": "值",
                "type": "条件类型"
            }
        ],
        "branch": "if_else_orm_branch_1",
        "description": "if-else+orm分支1描述"
    },
    {
        "query": "if-else+orm分支2的SQL查询",
        "table": "表名", 
        "fields": ["字段1", "字段2"],
        "conditions": [
            {
                "field": "字段名",
                "operator": "操作符",
                "value": "值", 
                "type": "条件类型"
            }
        ],
        "branch": "if_else_orm_branch_2",
        "description": "if-else+orm分支2描述"
    }
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",
```

### 3. 添加缺失的Caller生成方法
在`data_processing/reverse_sql_generator/caller_generator.py`中添加`generate_if_else_orm_caller`方法：

```python
async def generate_if_else_orm_caller(self, orm_code: Dict, if_else_orm_sqls: List[Dict], scenario: str) -> Dict:
    """生成if-else+orm调用者代码
    
    Args:
        orm_code: ORM代码数据
        if_else_orm_sqls: if-else+orm SQL变体列表
        scenario: 场景类型
        
    Returns:
        if-else+orm调用者代码数据
    """
    # 实现细节...
```

## 修复结果

### 修复前的问题流程：
1. 生成if-else变体 ✅
2. 重新生成包含if-else逻辑的ORM ❌
3. 生成基本Caller ❌

### 修复后的正确流程：
1. 生成if-else+orm变体 ✅
2. 生成if-else+orm Caller ✅
3. 数据验证通过 ✅

### 测试结果：
- ✅ if-else+orm变体生成成功（2-3个变体）
- ✅ if-else+orm Caller生成成功
- ✅ 数据验证通过
- ✅ 流程正确，不再重新生成ORM代码

## 相关文件修改

1. **data_processing/reverse_sql_generator/generator.py**
   - 修复了场景处理逻辑的顺序
   - 确保"if-else+orm"场景使用正确的处理流程

2. **config/data_processing/reverse_sql_generator/prompts.py**
   - 添加了`if_else_orm_variants`提示词模板

3. **data_processing/reverse_sql_generator/caller_generator.py**
   - 添加了`generate_if_else_orm_caller`方法

## 总结

这次修复解决了反向SQL生成器中"if-else+orm"场景的处理问题，确保了：

1. **正确的处理流程**：不再错误地重新生成ORM代码
2. **完整的模板支持**：添加了缺失的提示词模板
3. **专门的Caller生成**：为if-else+orm场景提供了专门的Caller生成方法

修复后的系统能够正确生成if-else+orm场景的数据，包括SQL变体、ORM代码和Caller代码，符合预期的数据格式和内容要求。 