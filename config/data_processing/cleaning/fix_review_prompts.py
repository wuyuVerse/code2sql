# 修复审核提示词模板

# 删除或错误SQL审查
REMOVAL_REVIEW_PROMPT = """
你是一名经验丰富的 Go + SQL 代码审查专家。

**上下文信息：**
- **ORM 代码片段：**
```go
{orm_code}

- **调用者 (caller)：**
   {caller}

**目标 SQL：**

```sql
{target_sql}
```

请判断此 SQL 是否合理删除（或认为是错误新增）。根据以下标准作出决策：

- **删除的原因**：如果该 SQL 确实不应该执行或有错误，确认其应被删除。例：重复的查询、无效的操作等。
- **保留的理由**：如果该 SQL 是必要的，或与现有逻辑一致，则不应删除，甚至可能需要调整。

请输出 JSON 格式，包含以下字段：

1. **accepted** – 布尔值，若该 SQL 应删除则为 `true`，否则为 `false`。
2. **replacement** – 当 `accepted` 为 `false` 时，提供应保留或替代的 SQL 语句（与原类型一致）；若 `accepted` 为 `true`，可返回空字符串 `""`。

**示例输出：**

```json
{ "accepted": true, "replacement": "" }
```

或

```json
{ "accepted": false, "replacement": "SELECT * FROM users WHERE id = ?" }
```

"""

# 缺失 SQL 增补审查


#### 2. 缺失 SQL 增补审查
ADDITION_REVIEW_PROMPT = """
你是一名经验丰富的 Go + SQL 代码审查专家。

**上下文信息：**
- **ORM 代码片段：**
```go
{orm_code}
```

- **调用者 (caller)：**
   {caller}

**系统建议新增以下 SQL：**

```sql
{target_sql}
```

请判断此 SQL 增补是否合理。根据以下标准作出决策：

- **合适的增补**：如果该 SQL 是合适且必要的，确认其应被添加。例：优化查询、缺少的查询条件等。
- **不合适的增补**：如果该 SQL 与业务逻辑不匹配，提出替代方案。

请输出 JSON 格式，包含以下字段：

1. **accepted** – 布尔值，若确认应新增此 SQL 则为 `true`，否则为 `false`。
2. **replacement** – 当 `accepted` 为 `false` 时，提供建议的替代 SQL 语句；若 `accepted` 为 `true`，返回原 SQL 或空字符串 `""`。

**示例输出：**

```json
{ "accepted": true, "replacement": "" }
```

或

```json
{ "accepted": false, "replacement": "INSERT INTO audit_log ..." }
```

"""