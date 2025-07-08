# 修复审核提示词模板

# 删除或错误SQL审查
REMOVAL_REVIEW_PROMPT = """你是一名经验丰富的 Go + SQL 代码审查专家。

上下文信息：
- ORM 代码片段：
```go
{orm_code}
```
- 调用者 (caller)：{caller}

下面的 SQL 被系统标记为需要 **删除**（或认为是错误新增）。请判断删除此 SQL 是否安全、合理。

目标 SQL：
```sql
{target_sql}
```

请输出 JSON，仅包含两个字段：
1. accepted – 布尔值，如果确实应该删除则为 true，否则为 false。
2. replacement – 字符串或数组。当 accepted 为 false 时，请给出应该保留或替换成的 SQL（与原类型一致）；若 accepted 为 true，可返回空字符串 ""。

示例输出：
```json
{ "accepted": true, "replacement": "" }
```
或者
```json
{ "accepted": false, "replacement": "SELECT * FROM users WHERE id = ?" }
```"""

# 缺失 SQL 增补审查
ADDITION_REVIEW_PROMPT = """你是一名经验丰富的 Go + SQL 代码审查专家。

上下文信息：
- ORM 代码片段：
```go
{orm_code}
```
- 调用者 (caller)：{caller}

系统建议在当前调用者中 **新增** 以下 SQL：
```sql
{target_sql}
```

请判断此补充是否合适，如不合适请给出应使用的替代 SQL（可与原类型一致）。

输出 JSON，仅包含：
1. accepted – 布尔值，若确认应添加则 true，否则 false。
2. replacement – 当 accepted 为 false 时，给出建议替换 SQL；若 accepted 为 true，可返回原 SQL 或空字符串。

示例输出：
```json
{ "accepted": true, "replacement": "" }
```
或
```json
{ "accepted": false, "replacement": "INSERT INTO audit_log ..." }
```""" 