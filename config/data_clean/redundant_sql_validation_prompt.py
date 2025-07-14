# 分步骤冗余SQL验证提示词模板

# Step 1: 语法级等价检测
SYNTAX_EQUIVALENCE_PROMPT = """你是SQL分析专家，需要判断目标SQL是否与参考SQL在语法上等价。

目标SQL:
```sql
{target_sql}
```

参考SQL集合:
{reference_sqls}

任务：判断目标SQL是否与参考SQL集合中的任何一个在语法上等价（忽略空白、大小写、注释差异）。

请回答：
- 如果等价，回答"是"
- 如果不等价，回答"否"

只需要简单回答"是"或"否"，不需要解释。"""

# Step 2: 冗余SQL业务合理性检测
REDUNDANT_BUSINESS_VALIDATION_PROMPT = """<ROLE>
你是一位资深的Go语言代码审计专家，专注于识别并优化代码中的数据库操作。你的任务是精确、严谨地判断一个SQL查询在特定业务场景下是否属于不必要的冗余。
</ROLE>

<CONTEXT>
系统通过SQL指纹对比，发现了一个潜在的冗余数据库操作。

- **调用者 (Target Caller)**: `{caller}`
- **参考标准 (Reference Caller)**: `{reference_caller}`

**Go 代码上下文:**
```go
{orm_code}
```

**待验证的 SQL (由 Target Caller 生成):**
```sql
{target_sql}
```

**参考 SQL (由 Reference Caller 生成):**
```sql
{reference_sql_json}
```
</CONTEXT>

<ANALYSIS_TASK>
**系统发现**: '调用者 (Target Caller)' 产生了一个或多个 '参考标准 (Reference Caller)' 中不存在的 SQL。

**你的核心任务**: 判断这个新增的 `{target_sql}` 是否真的多余。

请遵循以下步骤进行思考：
1.  **理解业务逻辑**: 仔细阅读 Go 代码，理解 `{caller}` 函数的核心业务目标。
2.  **对比 SQL**: 对比 "待验证的 SQL" 和 "参考 SQL"。它们的功能是否重叠？`{target_sql}` 是否只是在做 "参考 SQL" 已经做过或应该做的事情？
3.  **考虑执行路径**: 这个 `{target_sql}` 是否位于一个不同于 "参考 SQL" 的、有必要的代码分支中（例如，不同的 if/else 逻辑）？或者它是否在一个循环内，造成了不必要的重复查询？
4.  **得出结论**: 综合以上分析，该 SQL 是否可以被安全地移除而不影响任何业务功能？

**重要原则**: 宁缺毋滥。只有在你 **100% 确定**该 SQL 是多余的、可以安全删除时，才将其判断为冗余。任何不确定性都应标记为“非冗余”。
</ANALYSIS_TASK>

<OUTPUT_FORMAT>
请严格按照以下 JSON 格式返回你的分析结果，不要添加任何额外的解释或说明。

```json
{{
  "is_redundant": boolean,
  "reasoning": "在这里用一句话简要说明你的判断依据。例如：该查询结果已被外部缓存，此处为重复获取。"
}}
```
</OUTPUT_FORMAT>
"""

# Step 3: 新增指纹合理性检测
NEW_FINGERPRINT_VALIDATION_PROMPT = """<ROLE>
你是一位资深的Go语言代码审计专家，负责评估新出现的数据库查询模式是否符合业务逻辑和最佳实践。你的任务是判断一个全新的SQL指纹是合理的业务演进还是潜在的代码错误。
</ROLE>

<CONTEXT>
系统在项目中发现了一个全新的、从未出现过的SQL查询指纹。

- **调用者 (Target Caller)**: `{caller}`
- **参考标准 (Reference Caller)**: `{reference_caller}` (一个功能相似的参考函数)

**Go 代码上下文:**
```go
{orm_code}
```

**待验证的新 SQL (由 Target Caller 生成):**
```sql
{new_sql}
```

**参考 SQL (由 Reference Caller 生成，用于对比):**
```sql
{reference_sql_json}
```
</CONTEXT>

<ANALYSIS_TASK>
**系统发现**: '{caller}' 产生了一个在整个项目中都未曾见过的全新SQL查询。

**你的核心任务**: 判断这个新SQL `{new_sql}` 是否合理。

请遵循以下步骤进行思考：
1.  **理解业务逻辑**: 仔细阅读 Go 代码，理解 `{caller}` 函数的业务目的，以及它与 `{reference_caller}` 的异同。
2.  **评估新颖性**: 这个新SQL实现的功能，是现有业务逻辑的合理扩展吗？（例如，查询了新的字段，或增加了新的过滤条件）。
3.  **检查潜在错误**: 这个新SQL有没有可能是因错误的ORM用法（如错误的链式调用）而意外产生的？
4.  **得出结论**: 综合分析，这个新SQL是应该被接受的合理新增，还是应该被拒绝的潜在错误？

**重要原则**: 审慎评估。只有在明确确认该SQL是符合预期的业务新增时，才判断为合理。
</ANALYSIS_TASK>

<OUTPUT_FORMAT>
请严格按照以下 JSON 格式返回你的分析结果，不要添加任何额外的解释或说明。

```json
{{
  "is_valid_new": boolean,
  "reasoning": "在这里用一句话简要说明你的判断依据。例如：该查询为新业务增加了必要的字段过滤，是合理的。"
}}
```
</OUTPUT_FORMAT>
"""

# Step 4: 缺失SQL必要性检测
MISSING_SQL_VALIDATION_PROMPT = """<ROLE>
你是一位资深的Go语言代码审计专家，擅长通过对比分析来发现代码中缺失的数据库操作。你的任务是判断一个函数是否遗漏了必要的SQL查询。
</ROLE>

<CONTEXT>
系统通过SQL指纹对比，发现了一个潜在的缺失数据库操作。

- **调用者 (Target Caller)**: `{caller}`
- **参考标准 (Reference Caller)**: `{reference_caller}`

**Go 代码上下文:**
```go
{orm_code}
```

**疑似缺失的SQL (由 Reference Caller 生成):**
```sql
{missing_sql}
```

**调用者已生成的SQL (由 Target Caller 生成，用于对比):**
```sql
{target_sql_json}
```
</CONTEXT>

<ANALYSIS_TASK>
**系统发现**: '{caller}' 未能生成 '{reference_caller}' 中存在的 SQL 查询 `{missing_sql}`。

**你的核心任务**: 判断这次缺失是合理的业务差异，还是一个应该被修复的遗漏？

请遵循以下步骤进行思考：
1.  **理解业务逻辑**: 仔细阅读 Go 代码，理解 `{caller}` 和 `{reference_caller}` 的业务目标和功能差异。
2.  **评估必要性**: 基于 `{caller}` 的业务逻辑，执行 `{missing_sql}` 这个操作是否是必需的？如果不执行，会否导致功能不完整或数据错误？
3.  **检查是否被替代**: `{caller}` 已生成的SQL中，是否有其他查询已经等效地完成了 `{missing_sql}` 的任务？
4.  **得出结论**: 综合分析，这个SQL是确实遗漏了，还是在当前上下文中本就不需要？

**重要原则**: 只有在明确确认业务逻辑要求必须有此查询时，才判断为“确实缺失”。
</ANALYSIS_TASK>

<OUTPUT_FORMAT>
请严格按照以下 JSON 格式返回你的分析结果，不要添加任何额外的解释或说明。

```json
{{
  "is_truly_missing": boolean,
  "reasoning": "在这里用一句话简要说明你的判断依据。例如：缺少了对关联表的必要查询，导致数据不完整。"
}}
```
</OUTPUT_FORMAT>
"""

# Step 0: 规则预过滤（简单差异检测）
RULE_BASED_FILTER_PROMPT = """你是SQL预处理专家，判断以下SQL差异是否为简单的格式差异。

SQL1:
```sql
{sql1}
```

SQL2:
```sql
{sql2}
```

请判断这两个SQL是否仅存在以下简单差异：
- 空白字符、换行符差异
- 大小写差异  
- 注释差异
- 表名/字段名的引号差异（如`table`与table）

如果仅存在上述简单差异，回答"格式差异"；
如果存在实质性语义差异，回答"语义差异"。

只需要简单回答，不需要详细解释。"""

# 保留原有的提示词作为备用
REDUNDANT_SQL_VALIDATION_PROMPT = """请判断以下SQL语句在给定的代码上下文中是否真的冗余。

SQL语句:
```sql
{clean_sql}
```

代码上下文信息:
- 函数名: {function_name}
- 调用者: {caller}
- ORM代码: {orm_code}

系统检测到此SQL的指纹在同一调用者中出现了多次，因此标记为可能冗余。

请分析：
1. 考虑到代码执行流程和业务逻辑，这个SQL是否确实是多余的重复？
2. 还是虽然SQL文本相同，但在不同的业务场景或代码分支中都有其必要性？

如果确实冗余可以安全删除，请回答"是，冗余"；如果不是冗余或不确定，请回答"否，保留"并简要说明原因。

注意：只有在明确确认SQL完全多余且删除不会影响业务逻辑时，才应该判断为冗余。"""

# 保留原有的解析验证提示词作为备用
REDUNDANT_SQL_PARSING_VALIDATION_PROMPT = """请验证以下SQL解析信息是否正确。

SQL语句:
```sql
{clean_sql}
```

系统解析结果:
- 语句类型: {stmt_type}
- WHERE子句涉及的列: {where_columns}

请判断系统解析结果是否准确。如果准确，请回答"是"；如果有错误，请回答"否，应该是..."并说明正确的解析结果。

注意：只需要验证语句类型和WHERE列的识别是否正确，不需要验证SQL语法正确性。""" 