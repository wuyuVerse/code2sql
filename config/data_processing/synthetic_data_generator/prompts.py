"""
合成数据生成器提示词模板
"""

# 提示词模板 – 调优使LLM只输出*结构化JSON*
PROMPT_ORM = """
你需要根据给定的场景标签生成一个真实的Go语言ORM方法。

场景标签: {scenario}
场景描述: {scenario_desc}

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": {scenario},
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在25行以内
8. 根据场景要求正确实现相应的逻辑模式
9. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# if-else+caller场景专用ORM提示词
PROMPT_ORM_IF_ELSE_CALLER = """
你需要根据"if-else+caller"场景生成一个真实的Go语言ORM方法。

场景标签: "if-else+caller"
场景描述: Caller代码中包含if-else条件判断，根据不同的条件构建不同的filter参数传递给ORM方法，ORM方法根据传入的参数内容使用不同的筛选条件构建SQL查询

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "if-else+caller",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在25行以内
8. ORM方法必须接收map[string]interface{{}}类型的filter参数
9. ORM方法内部必须包含if-else逻辑，根据传入的filter参数内容使用不同的查询策略
10. 至少包含两种不同的查询策略（如精确匹配vs模糊匹配，不同字段组合等）
11. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构

只返回JSON格式，不要包含markdown标记或其他文本。
"""

PROMPT_CALLER = """
你需要为以下ORM代码块编写一个或多个调用者函数。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出（可以是单个对象或数组）：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

或者多个调用者：
```json
[
    {{
        "code_key": "调用者方法名1",
        "code_value": "完整的Go调用者代码1"
    }},
    {{
        "code_key": "调用者方法名2", 
        "code_value": "完整的Go调用者代码2"
    }}
]
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 根据场景正确传递参数或设置全局变量
4. 包含适当的错误处理
5. 代码长度控制在20行以内
6. 变量名要多样化，避免重复
7. 生成的内容必须与参考样例完全不同
8. 可以生成单个调用者或多个调用者

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# if-else+caller场景专用Caller提示词
PROMPT_CALLER_IF_ELSE = """
你需要为以下ORM代码块编写一个调用者函数，该函数包含if-else条件判断逻辑。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 必须包含if-else条件判断逻辑，根据不同的业务条件构建不同的filter参数
4. filter参数必须是map[string]interface{{}}类型
5. 至少包含3个不同的条件分支（如if-else if-else if-else）
6. 每个条件分支应该检查不同的参数（如ID、名称、状态等）
7. 包含适当的参数验证和错误处理
8. 代码长度控制在30行以内
9. 变量名要多样化，避免重复
10. 生成的内容必须与参考样例完全不同
11. 确保传递给ORM方法的参数能够触发ORM方法中的不同查询策略

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# switch场景专用ORM提示词
PROMPT_ORM_SWITCH = """
你需要根据"switch"场景生成一个真实的Go语言ORM方法。

场景标签: "switch"
场景描述: ORM方法使用switch条件语句来根据不同的参数值或状态构建不同的SQL查询条件，实现动态查询逻辑

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "switch",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在30行以内
8. ORM方法必须包含switch语句，根据不同的枚举值或状态构建不同的查询条件
9. switch语句至少包含4个不同的case分支
10. 每个case分支应该设置不同的filter条件或查询参数
11. 必须包含default分支处理未知情况
12. 使用常量或枚举值作为switch的判断条件
13. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# switch场景专用Caller提示词
PROMPT_CALLER_SWITCH = """
你需要为以下ORM代码块编写一个调用者函数，该函数包含switch条件判断逻辑。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 必须包含switch条件判断逻辑，根据不同的枚举值或状态设置不同的参数
4. 至少包含4个不同的case分支
5. 每个case分支应该设置不同的参数值或状态
6. 必须包含default分支处理未知情况
7. 使用常量或枚举值作为switch的判断条件
8. 包含适当的参数验证和错误处理
9. 代码长度控制在35行以内
10. 变量名要多样化，避免重复
11. 生成的内容必须与参考样例完全不同
12. 确保传递给ORM方法的参数能够触发ORM方法中的switch逻辑

只返回JSON格式，不要包含markdown标记或其他文本。
"""

PROMPT_META = """
基于以下ORM代码块和其调用者，创建完整的`code_meta_data`数组。

ORM代码块:
{orm_block}

调用者代码块:
{caller_block}

参考以下真实样例（但生成完全不同的内容）:
{example_meta}

请严格按照以下JSON数组格式输出：
```json
[
    {{
        "code_key": "结构体或类型名",
        "code_value": "Go类型定义代码"
    }},
    {{
        "code_key": "常量或变量名", 
        "code_value": "Go常量或变量定义"
    }}
]
```

元数据要求：
1. 包含所有相关的结构体定义（请求、响应、实体类型）
2. 包含必要的常量定义（表名、状态值等）
3. 包含全局变量定义（如果场景需要）
4. 类型名使用{type_examples}等多样化命名
5. 确保代码完整性和正确性
6. 每个元素都是独立的代码片段
7. 生成的内容必须与参考样例完全不同

只返回JSON数组格式，不要包含markdown标记或其他文本。
"""

# if-else+orm场景专用ORM提示词
PROMPT_ORM_IF_ELSE_ORM = """
你需要根据"if-else+orm"场景生成一个真实的Go语言ORM方法。

场景标签: "if-else+orm"
场景描述: ORM方法内部包含if-else条件判断，根据不同的分支使用不同的筛选条件构建SQL查询

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "if-else+orm",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在35行以内
8. ORM方法内部必须包含if-else条件判断逻辑
9. 至少包含3个不同的条件分支（if-else if-else if-else）
10. 每个条件分支应该检查不同的参数或条件
11. 不同分支使用不同的SQL查询策略（如精确匹配vs模糊匹配，不同字段组合等）
12. 包含适当的错误处理
13. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# if-else+orm场景专用Caller提示词
PROMPT_CALLER_IF_ELSE_ORM = """
你需要为以下ORM代码块编写一个调用者函数，该函数构建参数传递给包含if-else逻辑的ORM方法。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 构建传递给ORM方法的参数，确保能够触发ORM方法中的不同if-else分支
4. 包含适当的参数验证和错误处理
5. 代码长度控制在30行以内
6. 变量名要多样化，避免重复
7. 生成的内容必须与参考样例完全不同
8. 确保传递给ORM方法的参数能够触发ORM方法中的不同查询策略

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# no-where场景专用ORM提示词
PROMPT_ORM_NO_WHERE = """
你需要根据"no-where"场景生成一个真实的Go语言ORM方法。

场景标签: "no-where"
场景描述: ORM方法需要外部传入部分where条件，但当前没有caller，所以部分where条件无法确定。where条件包含外来传入的参数和固定的查询逻辑

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "no-where",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在25行以内
8. ORM方法必须接收map[string]interface{{}}类型的where条件参数
9. ORM方法内部使用传入的where条件**结合固定的查询逻辑**构建SQL查询
10. 可以包含分页、排序等基础功能
11. 包含适当的错误处理
12. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构
13. 注意：此场景不需要caller，callers字段保持为空数组，但方法需要接收where参数
14. **重要**：where条件应该包含外来传入的参数和固定的查询逻辑（如deleted_at is null等）

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# no-where场景专用Caller提示词（空实现）
PROMPT_CALLER_NO_WHERE = """
注意：no-where场景不需要生成caller代码，因为ORM方法没有调用者。

请返回空的JSON数组：
```json
[]
```

说明：no-where场景的ORM方法是独立的，不需要外部调用者。虽然ORM方法需要接收部分where条件参数，但当前没有caller来提供这些条件。
"""

# table_mapping_incomplete场景专用ORM提示词
PROMPT_ORM_TABLE_MAPPING_INCOMPLETE = """
你需要根据"table_mapping_incomplete"场景生成一个真实的Go语言ORM方法。

场景标签: "table_mapping_incomplete"
场景描述: ORM方法中模型将结构体名错误理解为表名，而真实表名通过常量定义。需要明确区分结构体名和真实表名，避免模型错误地将结构体名当作表名使用。必须使用const定义表名常量，并在ORM方法中使用.Table(TableName)明确指定表名，确保code_meta_data中包含表名常量定义。

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "table_mapping_incomplete",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在25行以内
8. **关键要求**：必须定义常量来表示真实表名，如 `const TableName = "actual_table_name"`
9. **关键要求**：ORM方法必须使用 `.Table(TableName)` 来明确指定表名，而不是依赖结构体名
10. **关键要求**：结构体名和表名必须不同，避免模型错误地将结构体名当作表名
11. **关键要求**：确保code_meta_data中包含表名常量定义，如 `const EntityTableName = "actual_table_name"`
12. 包含适当的错误处理
13. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构
14. **重要**：确保代码中明确区分了结构体名和表名，避免表名映射不完善的问题

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# table_mapping_incomplete场景专用Caller提示词
PROMPT_CALLER_TABLE_MAPPING_INCOMPLETE = """
你需要为以下ORM代码块编写一个调用者函数，该函数调用具有表名映射不完善特征的ORM方法。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象（注意结构体名和表名的区别）
3. 调用ORM方法并传递必要的参数
4. 包含适当的参数验证和错误处理
5. 代码长度控制在30行以内
6. 变量名要多样化，避免重复
7. 生成的内容必须与参考样例完全不同
8. **重要**：确保调用者代码理解结构体名和表名的区别，正确使用表名常量
9. **重要**：调用者代码应该能够正确处理表名映射不完善的情况，确保使用正确的表名常量

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# table_mapping_incomplete场景专用元数据提示词
PROMPT_META_TABLE_MAPPING_INCOMPLETE = """
基于以下ORM代码块和其调用者，创建完整的`code_meta_data`数组，特别关注表名映射不完善的情况。

ORM代码块:
{orm_block}

调用者代码块:
{caller_block}

参考以下真实样例（但生成完全不同的内容）:
{example_meta}

请严格按照以下JSON数组格式输出：
```json
[
    {{
        "code_key": "结构体名",
        "code_value": "Go结构体定义代码"
    }},
    {{
        "code_key": "表名常量", 
        "code_value": "const TableName = \"actual_table_name\""
    }}
]
```

元数据要求：
1. **必须包含表名常量定义**：如 `const EntityTableName = "actual_table_name"`
2. 包含所有相关的结构体定义（请求、响应、实体类型）
3. 包含必要的常量定义（状态值等）
4. 类型名使用{type_examples}等多样化命名
5. 确保代码完整性和正确性
6. 每个元素都是独立的代码片段
7. 生成的内容必须与参考样例完全不同
8. **重要**：确保表名常量与结构体名不同，明确区分结构体名和真实表名
9. **重要**：表名常量应该反映真实的数据库表名，而不是结构体名

只返回JSON数组格式，不要包含markdown标记或其他文本。
"""

# 表名映射不完善场景专用ORM提示词
PROMPT_ORM_TABLE_MAPPING = """
你需要根据"表名映射不完善"场景生成一个真实的Go语言ORM方法。

场景标签: "表名映射不完善"
场景描述: ORM方法中模型将结构体名错误理解为表名，而真实表名通过常量定义。需要明确区分结构体名和真实表名，避免模型错误地将结构体名当作表名使用

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "表名映射不完善",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在25行以内
8. **关键要求**：必须定义结构体名和真实表名的映射关系
9. 结构体名应该与真实表名不同，避免模型错误理解
10. 使用常量定义真实表名，如：const RealTableName = "real_table_name"
11. 在ORM方法中明确使用真实表名，而不是依赖结构体名
12. 包含适当的错误处理
13. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构
14. **重要**：确保结构体名和表名有明显的区别，避免模型混淆

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# 表名映射不完善场景专用Caller提示词
PROMPT_CALLER_TABLE_MAPPING = """
你需要为以下ORM代码块编写一个调用者函数，该函数调用包含表名映射的ORM方法。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 调用ORM方法并处理返回结果
4. 包含适当的参数验证和错误处理
5. 代码长度控制在30行以内
6. 变量名要多样化，避免重复
7. 生成的内容必须与参考样例完全不同
8. 确保正确使用结构体对象，而不是直接操作表名

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# condition_field_mapping场景专用ORM提示词
PROMPT_ORM_CONDITION_FIELD_MAPPING = """
你需要根据"condition_field_mapping"场景生成一个真实的Go语言ORM方法。

场景标签: "condition_field_mapping"
场景描述: ORM方法接收filter参数，在条件判断中检查某个字段名，但在实际构建SQL where条件时使用不同的字段名。这是字段名映射的典型场景，例如：判断filter中的"region"字段，但实际在SQL中添加"cluster_id"条件；判断"category"字段，但实际添加"type_id"条件等。

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "condition_field_mapping",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在35行以内
8. **关键要求**：方法必须接收map[string]interface{{}}类型的filter参数
9. **关键要求**：必须使用for循环遍历filter参数
10. **关键要求**：在条件判断中检查filter的key，但实际构建SQL时使用不同的字段名
11. **关键要求**：至少包含2个不同的字段映射关系（如：if k == "region" 但 sql += "AND cluster_id in (?)"）
12. **关键要求**：判断条件中的字段名与添加到SQL中的字段名必须不同
13. 包含适当的错误处理
14. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构
15. **重要**：确保字段映射逻辑清晰，例如：region→cluster_id, category→type_id, zone→area_id等

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# condition_field_mapping场景专用Caller提示词
PROMPT_CALLER_CONDITION_FIELD_MAPPING = """
你需要为以下ORM代码块编写一个调用者函数，该函数构建包含字段映射关系的参数传递给ORM方法。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 构建传递给ORM方法的filter参数，包含需要进行字段映射的参数
4. **关键要求**：filter参数中必须包含与ORM方法中字段映射对应的原始字段名（如：传入"region"而不是"cluster_id"）
5. **关键要求**：至少包含2个不同的字段映射关系（如：传入region但ORM处理cluster_id，传入category但ORM处理type_id）
6. **关键要求**：确保传递的参数值类型正确（如：region传入[]string类型，category传入string类型）
7. 包含适当的参数验证和错误处理
8. 代码长度控制在30行以内
9. 变量名要多样化，避免重复
10. 生成的内容必须与参考样例完全不同
11. **重要**：确保传递给ORM方法的参数能够触发ORM方法中的字段映射逻辑

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# where_condition_with_fixed_values场景专用ORM提示词
PROMPT_ORM_WHERE_FIXED_VALUES = """
你需要根据"where_condition_with_fixed_values"场景生成一个真实的Go语言ORM方法。

场景标签: "where_condition_with_fixed_values"
场景描述: ORM方法在where条件中直接指定了具体的值，而不是通过参数传递。这些值在代码中是固定的，通常用于过滤有效数据、排除特定值等。例如：status=0（有效状态）, income_industry_id<>0（非空行业ID）, deleted_at IS NULL（未删除记录）等。

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "where_condition_with_fixed_values",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在35行以内
8. **关键要求**：必须在where条件中直接指定具体的固定值
9. **关键要求**：至少包含2个不同的固定条件（如：status=0, type_id<>0, deleted_at IS NULL等）
10. **关键要求**：这些固定值在代码中直接写入，不需要通过参数传递
11. **关键要求**：固定值应该有意义，如：0表示有效状态，NULL表示未删除等
12. 包含适当的错误处理
13. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构
14. **重要**：确保固定值的语义清晰，符合业务逻辑

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# where_condition_with_fixed_values场景专用Caller提示词
PROMPT_CALLER_WHERE_FIXED_VALUES = """
你需要为以下ORM代码块编写一个调用者函数，该函数调用包含固定where条件的ORM方法。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 调用ORM方法并处理返回结果
4. **关键要求**：ORM方法不需要传递where条件参数，因为条件在方法内部是固定的
5. **关键要求**：调用者应该理解这些固定条件的业务含义（如：只查询有效数据、排除特定值等）
6. 包含适当的错误处理
7. 代码长度控制在30行以内
8. 变量名要多样化，避免重复
9. 生成的内容必须与参考样例完全不同
10. **重要**：确保调用者代码符合固定where条件的业务逻辑

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# where_condition_mixed场景专用ORM提示词
PROMPT_ORM_WHERE_MIXED = """
你需要根据"where_condition_mixed"场景生成一个真实的Go语言ORM方法。

场景标签: "where_condition_mixed"
场景描述: ORM方法在where条件中同时包含固定值和动态条件。固定值直接在代码中指定（如status=0, deleted_at IS NULL），同时包含if-else等动态条件判断。固定条件用于基础过滤，动态条件根据传入参数进行灵活查询。

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "where_condition_mixed",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在40行以内
8. **关键要求**：必须在where条件中直接指定具体的固定值（如：status=0, deleted_at IS NULL等）
9. **关键要求**：至少包含2个不同的固定条件，这些固定值在代码中直接写入
10. **关键要求**：必须包含if-else或switch等动态条件判断逻辑
11. **关键要求**：动态条件应该根据传入参数（如filter、status等）进行判断
12. **关键要求**：固定条件通常用于基础过滤（如：只查询有效数据、排除已删除记录等）
13. **关键要求**：动态条件用于灵活查询（如：根据状态、类型、日期范围等）
14. 包含适当的错误处理
15. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构
16. **重要**：确保固定值和动态条件的组合逻辑清晰，符合业务需求

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# where_condition_mixed场景专用Caller提示词
PROMPT_CALLER_WHERE_MIXED = """
你需要为以下ORM代码块编写一个调用者函数，该函数调用包含固定where条件和动态条件的ORM方法。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 调用ORM方法并处理返回结果
4. **关键要求**：ORM方法包含固定条件（如status=0, deleted_at IS NULL），这些不需要传递参数
5. **关键要求**：必须传递动态条件参数（如filter、status、type等），用于触发ORM方法中的if-else逻辑
6. **关键要求**：调用者应该理解固定条件的业务含义（如：只查询有效数据、排除已删除记录等）
7. **关键要求**：确保传递的参数能够触发ORM方法中的不同动态条件分支
8. 包含适当的错误处理
9. 代码长度控制在35行以内
10. 变量名要多样化，避免重复
11. 生成的内容必须与参考样例完全不同
12. **重要**：确保调用者代码能够正确传递动态参数，同时理解固定条件的业务逻辑

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# 互斥条件场景专用ORM提示词
PROMPT_ORM_MUTUAL_EXCLUSIVE = """
你需要根据"mutual_exclusive_conditions"场景生成一个真实的Go语言ORM方法。

场景标签: "mutual_exclusive_conditions"
场景描述: ORM方法接收包含互斥条件的filter参数，使用if-else逻辑处理不同的条件组合。每个条件对应不同的SQL查询策略，条件之间互斥（不会同时出现）。同时，还包含与互斥条件无关的其他filter条件，这些条件可以自由组合。

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "mutual_exclusive_conditions",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在35行以内
8. ORM方法必须接收map[string]interface{{}}类型的filter参数
9. ORM方法内部必须包含if-else逻辑，检查特定的互斥条件
10. 至少包含3个互斥条件分支（如if-else if-else if-else）
11. 每个条件分支使用不同的查询策略（如精确匹配vs模糊匹配，不同字段组合等）
12. 条件之间必须互斥，不会同时出现
13. 除了互斥条件外，还必须包含其他无关的filter条件（如status、created_at、deleted_at等）
14. 其他filter条件应该与互斥条件自由组合，不相互影响
15. 包含适当的错误处理
16. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# 互斥条件场景专用Caller提示词
PROMPT_CALLER_MUTUAL_EXCLUSIVE = """
你需要为以下ORM代码块编写一个调用者函数，该函数构建互斥条件和其他filter条件传递给ORM方法。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 必须包含if-else if-else if-else条件判断逻辑
4. 每个条件分支检查不同的参数（如ID、名称、状态等）
5. 条件之间必须互斥，不会同时出现
6. 除了互斥条件外，还必须添加其他无关的filter条件（如status、created_at、deleted_at等）
7. 其他filter条件应该与互斥条件自由组合，不相互影响
8. filter参数必须是map[string]interface{{}}类型
9. 包含适当的参数验证和错误处理
10. 代码长度控制在35行以内
11. 变量名要多样化，避免重复
12. 生成的内容必须与参考样例完全不同
13. 确保传递给ORM方法的参数能够触发ORM方法中的不同查询策略
14. 使用互斥的条件逻辑，确保每次只有一个条件生效
15. 确保caller不为空，因为filter条件信息依赖于caller的上下文

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# 互斥条件场景专用SQL生成提示词
PROMPT_SQL_MUTUAL_EXCLUSIVE = """
你需要为以下ORM代码生成对应的SQL语句，该代码包含互斥条件逻辑。

ORM代码:
{orm_code}

互斥条件说明:
- 代码中包含if-else或者switch-case逻辑处理不同的条件组合
- 每个条件对应不同的SQL查询策略
- 条件之间互斥，不会同时出现
- 需要生成多个SQL变体，每个变体对应一个条件分支

请严格按照以下JSON格式输出：
```json
{{
    "base_sql": "基础SQL语句",
    "sql_variants": [
        {{
            "condition": "条件1描述",
            "sql": "对应SQL语句",
            "description": "该分支的详细说明"
        }},
        {{
            "condition": "条件2描述", 
            "sql": "对应SQL语句",
            "description": "该分支的详细说明"
        }},
        {{
            "condition": "条件3描述",
            "sql": "对应SQL语句", 
            "description": "该分支的详细说明"
        }}
    ],
    "mutual_exclusive_conditions": [
        "条件1",
        "条件2", 
        "条件3"
    ],
    "description": "互斥条件SQL生成说明"
}}
```

SQL生成要求：
1. 分析ORM代码中的if-else逻辑结构
2. 识别每个条件分支对应的SQL查询策略
3. 生成基础SQL和多个SQL变体
4. 每个SQL变体对应一个互斥条件
5. 确保SQL语句语法正确且符合业务逻辑
6. 包含适当的WHERE条件、JOIN、ORDER BY等
7. 考虑不同条件对查询结果的影响
8. 生成的内容必须与参考样例完全不同

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# 互斥条件场景专用SQL分析提示词
PROMPT_SQL_MUTUAL_EXCLUSIVE_ANALYSIS = """
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

**严格要求：**
- 仅输出纯JSON数组，无其他文字说明
- SQL语句必须完整可执行，以分号结尾
- 参数使用问号(?)表示
- 必须包含所有可能的条件组合变体
- 确保互斥条件与其他filter条件正确组合

**分析目标代码：**
函数名称：{function_name}
ORM代码：{orm_code}
调用者信息：
{caller}
元数据信息：
{code_meta_data}

**特别注意：**
- 这是互斥条件场景，必须识别出互斥的条件分支
- 生成的SQL必须反映实际的互斥逻辑
- 每个条件分支都应该有对应的SQL变体
- 其他filter条件应该与互斥条件自由组合
"""

# 互斥条件场景专用SQL验证提示词
PROMPT_SQL_MUTUAL_EXCLUSIVE_VERIFY = """
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
{original_analysis}

**验证目标代码：**
函数名称：{function_name}
ORM代码：{orm_code}
调用者信息：
{caller}
元数据信息：
{code_meta_data}

**验证要求：**
1. 如果原始分析结果正确且完整，直接返回原始结果
2. 如果发现问题，修正并返回修正后的结果
3. 确保输出格式为标准JSON数组
4. 确保包含所有必要的SQL变体
5. 确保互斥条件与其他filter条件正确组合

请返回验证后的SQL分析结果。
"""

# 表名从caller传递场景专用ORM提示词
PROMPT_ORM_TABLE_NAME_FROM_CALLER = """
你需要根据"table_name_from_caller"场景生成一个真实的Go语言ORM方法。

场景标签: "table_name_from_caller"
场景描述: ORM方法的表名信息从caller中传递过来，而不是在ORM方法内部硬编码。Caller负责确定具体的表名，ORM方法接收表名作为参数或通过其他方式获取。

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "table_name_from_caller",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": []
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在35行以内
8. ORM方法必须接收表名参数（如tableName string）或通过其他方式从caller获取表名
9. 不能硬编码表名，表名必须通过参数传递或动态获取
10. 使用Table()方法设置动态表名
11. 包含适当的错误处理
12. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构
13. **重要**：ORM方法必须能够接收caller传递的具体表名，并在SQL生成时使用这些表名
14. **重要**：如果caller中有JOIN逻辑，ORM方法应该能够处理关联查询
15. **重要**：生成的SQL中必须使用具体的表名，不能使用占位符如tenant_id、table_name等
16. **重要**：表名必须是完整的、具体的表名，如"user_profiles"、"order_items"等
17. **重要**：ORM方法应该使用传入的固定表名，而不是动态生成或格式化表名
18. **重要**：如果caller传递了具体的表名（如"teacher_performance_2023"），ORM方法应该直接使用这个表名

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# 表名从caller传递场景专用Caller提示词
PROMPT_CALLER_TABLE_NAME_FROM_CALLER = """
你需要为以下ORM代码块编写一个调用者函数，该函数负责确定表名并传递给ORM方法。

ORM代码块:
{orm_block}

参考以下真实样例（但生成完全不同的内容）:
{example_caller}

请严格按照以下JSON格式输出：
```json
{{
    "code_key": "调用者方法名",
    "code_value": "完整的Go调用者代码"
}}
```

调用者代码要求：
1. 方法名与ORM方法不同，使用{caller_examples}等命名
2. 正确创建和初始化ORM对象
3. 必须包含表名确定逻辑（如根据参数、配置、环境等确定表名）
4. 将确定的表名传递给ORM方法
5. 包含适当的参数验证和错误处理
6. 代码长度控制在35行以内
7. 变量名要多样化，避免重复
8. 生成的内容必须与参考样例完全不同
9. 确保caller不为空，因为表名信息依赖于caller的上下文
10. 表名确定逻辑应该合理且多样化（如根据租户ID、时间范围、配置等）
11. **重要**：caller必须包含明确的表名信息，如Table("具体表名")或JOIN语句
12. **重要**：如果涉及多表查询，caller应该包含完整的JOIN逻辑和表别名
13. **重要**：表名确定逻辑应该考虑不同的业务场景（如分表、多租户等）
14. **重要**：caller中确定的表名必须是具体的、完整的表名，不能使用占位符
15. **重要**：传递给ORM方法的表名参数必须是具体的表名字符串，如"user_profiles"、"order_items"等
16. **重要**：caller中的表名应该是固定的、确定的表名，而不是动态生成的占位符
17. **重要**：表名确定逻辑应该使用具体的字符串拼接或条件判断，而不是使用fmt.Sprintf等动态格式化

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# raw_sql_in_code场景专用ORM提示词
PROMPT_ORM_RAW_SQL_IN_CODE = """
你需要根据"raw_sql_in_code"场景生成一个真实的Go语言ORM方法。

场景标签: "raw_sql_in_code"
场景描述: ORM方法中直接包含原始SQL语句，使用db.Raw()方法执行自定义SQL查询。通常用于复杂的多表关联查询、聚合查询或需要特殊优化的场景。

参考以下真实样例（但生成完全不同的内容）:
{example}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "raw_sql_in_code",
    "code_key": "方法名（使用{method_examples}等不同命名）",
    "code_value": "完整的Go代码（使用{entity_examples}等实体，{table_examples}等表名）",
    "sql_pattern_cnt": 1,
    "callers": [],
    "callees": [],
    "code_meta_data": [
        {{
            "code_key": "结构体名",
            "code_value": "类型定义代码"
        }},
        {{
            "code_key": "SQLQuery",
            "code_value": "原始SQL查询语句"
        }}
    ]
}}
```

代码要求：
1. 使用多样化的变量名，避免重复使用User、Order等常见名词
2. 实体名使用：{entity_examples}
3. 表名使用：{table_examples}  
4. 方法名使用：{method_examples}
5. 字段名使用：{field_examples}
6. 代码必须是完整可运行的Go代码，使用GORM框架
7. 代码长度控制在35行以内
8. **重要**：ORM方法必须包含硬编码的原始SQL语句
9. **重要**：使用db.Raw(sql)方法执行SQL查询
10. **重要**：使用Scan()方法将结果映射到结构体
11. **重要**：SQL语句应该包含复杂的查询逻辑（如多表JOIN、聚合函数、子查询等）
12. **重要**：SQL语句应该使用具体的表名和字段名，不能使用占位符
13. **重要**：在code_meta_data中必须包含SQLQuery字段，包含完整的SQL语句
14. **重要**：SQL语句应该包含WHERE条件、JOIN操作、聚合函数等复杂逻辑
15. **重要**：生成的SQL应该是有意义的业务查询，如统计报表、数据分析等
16. 包含适当的错误处理和日志记录
17. 生成的内容必须与参考样例完全不同，使用不同的业务域、变量名、逻辑结构

**SQL多样性要求：**
18. **SQL特性选择**：从以下特性中选择2-6个组合使用，不要全部使用：
    - JOIN类型：INNER JOIN、LEFT JOIN、RIGHT JOIN
    - 聚合函数：COUNT、SUM、AVG、MAX、MIN
    - 子查询：EXISTS、IN、NOT IN、子查询
    - 窗口函数：ROW_NUMBER、RANK、LAG、LEAD
    - 条件逻辑：CASE WHEN、IF、COALESCE
    - 字符串函数：CONCAT、SUBSTRING、REPLACE、UPPER、LOWER
    - 日期函数：DATE_FORMAT、DATEDIFF、DATE_ADD、YEAR、MONTH
    - 数学函数：ROUND、CEIL、FLOOR、ABS
    - 模糊查询：LIKE、NOT LIKE、REGEXP（使用%、_等通配符）
    - 排序分组：ORDER BY、GROUP BY、HAVING
    - 分页查询：LIMIT、OFFSET
    - 去重查询：DISTINCT、GROUP BY去重
19. **业务场景多样性**：生成不同类型的业务查询（用户分析、销售统计、库存报表、性能监控、财务分析等）
20. **查询复杂度多样性**：包含简单查询、中等复杂度查询、高复杂度查询

**SQL生成指导：**
- 每个SQL选择2-4个特性组合，避免过度复杂
- 优先选择多表关联查询
- 包含有意义的WHERE条件和业务逻辑
- 使用业务相关的字段名和表名
- 确保SQL语法正确且可执行
- 根据业务场景选择合适的SQL特性组合

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# with_first场景第一步：判断是否可以添加First()
PROMPT_WITH_FIRST_JUDGE = """
你需要分析以下ORM代码，判断是否可以添加First()方法。

原始ORM代码:
{orm_code}

请严格按照以下JSON格式输出：
```json
{{
    "can_add_first": true/false,
    "reason": "判断原因（如果可以添加First，说明原因；如果不可以添加，详细说明原因）"
}}
```

判断规则：
**可以添加First()的情况：**
- Find()查询返回结构体切片：`var users []User` → `var user User`
- Raw()查询返回结构体切片：`var results []Result` → `var result Result`
- Select()查询返回基本类型切片：`var ids []int64` → `var id int64`
- 查询链中包含Find()、Raw()、Select()等查询方法

**已经是First()的情况（重要：这种情况返回true）：**
- 如果代码中已经包含First()方法，**必须返回true**，生成时保持原样不变
- 如果已经是`db.First(&user)`形式，**返回true**
- 如果已经是`db.Where(...).First(&user)`形式，**返回true**

**不可以添加First()的情况：**
- Create()、Update()、Delete()等写操作
- Count()、Sum()、Avg()、Max()、Min()等聚合操作
- 批量操作：Create([]User{{...}})
- 事务操作：Transaction()
- 关联操作：Association()
- 预加载操作：Preload()
- 已经包含Take()、Last()等其他限制方法

**特别注意：**
- **最高优先级**：如果代码中已经是First()操作，**无条件返回true**
- 如果代码中有多个查询操作，只要有一个可以添加First()就返回true
- 如果代码中有写操作或聚合操作，返回false
- 如果代码中没有查询操作，返回false
- 如果代码中已经包含其他限制方法（Take、Last），返回false

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# with_first场景第二步：生成添加First()后的完整数据
PROMPT_WITH_FIRST_GENERATE = """
你需要为以下ORM代码添加First()方法，生成完整的with_first场景数据。

原始ORM代码:
{orm_code}

原始场景: {original_scenario}

原始caller代码:
{caller_code}

原始code_meta_data（作为参考）:
{original_code_meta_data}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "with_first",
    "code_key": "方法名（保持原方法名不变）",
    "code_value": "添加First()方法后的完整Go代码",
    "sql_pattern_cnt": 1,
    "callers": [
        {{
            "code_key": "调用者方法名（保持原方法名不变）",
            "code_value": "修改后的调用者代码"
        }}
    ],
    "callees": [],
    "code_meta_data": [
        {{
            "code_key": "结构体名或类型名",
            "code_value": "更新后的Go类型定义（适配First()方法的返回类型变化）"
        }}
    ]
}}
```

修改要求：
1. **方法名保持**：保持原有的方法名不变
2. **返回类型修改**：
   - `[]User` → `User`
   - `[]int64` → `int64`
   - `[]string` → `string`
   - `[]map[string]interface{{}}` → `map[string]interface{{}}`
3. **查询链修改**：在查询链的最后添加`.First()`
4. **code_meta_data要求**：
   - 基于原始code_meta_data进行适当调整
   - 根据返回类型的变化（[]User → User），更新相关的结构体定义
   - 如果返回类型从切片变为单个对象，确保结构体定义正确
   - 保持其他必要的类型定义和常量定义
   - 如果原始code_meta_data为空，生成适当的类型定义
5. **错误处理**：保持原有的错误处理逻辑
5. **代码结构**：保持原有的代码结构和注释
6. **变量名**：保持原有的变量名，只修改返回类型
7. **导入语句**：保持原有的import语句

**Caller修改要求：**
8. **Caller方法名保持**：保持原有的caller方法名不变
9. **Caller调用保持**：保持对ORM方法的调用不变
10. **Caller变量处理**：如果caller中处理返回结果，需要相应调整（从切片改为单个对象）
11. **Caller错误处理**：保持原有的错误处理逻辑
12. **Caller代码结构**：保持原有的代码结构和注释

**重要**：确保生成的代码语法正确，可以编译运行。

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# with_take场景第一步：判断是否可以添加Take()
PROMPT_WITH_TAKE_JUDGE = """
你需要分析以下ORM代码，判断是否可以添加Take(1)方法。

原始ORM代码:
{orm_code}

请严格按照以下JSON格式输出：
```json
{{
    "can_add_take": true/false,
    "reason": "判断原因（如果可以添加Take，说明原因；如果不可以添加，详细说明原因）"
}}
```

判断规则：
**可以添加Take()的情况：**
- Find()查询：`db.Find(&users)` → `db.Take(1).Find(&users)`
- Raw()查询：`db.Raw(sql).Scan(&results)` → `db.Raw(sql).Take(1).Scan(&results)`
- Select()查询：`db.Select("id").Find(&ids)` → `db.Select("id").Take(1).Find(&ids)`
- 查询链中包含Find()、Raw()、Select()等查询方法
- 返回结构体切片或基本类型切片的查询

**已经是Take()的情况（重要：这种情况返回true）：**
- 如果代码中已经包含Take()方法，**必须返回true**，生成时保持原样不变
- 如果已经是`db.Take(1).Find(&users)`形式，**返回true**
- 如果已经是`db.Where(...).Take(1).Find(&users)`形式，**返回true**

**不可以添加Take()的情况：**
- Create()、Update()、Delete()等写操作
- Count()、Sum()、Avg()、Max()、Min()等聚合操作
- 批量操作：Create([]User{{...}})
- 事务操作：Transaction()
- 关联操作：Association()
- 预加载操作：Preload()
- 已经包含First()、Last()等其他限制方法的查询

**特别注意：**
- **最高优先级**：如果代码中已经是Take()操作，**无条件返回true**
- 如果代码中有多个查询操作，只要有一个可以添加Take()就返回true
- 如果代码中有写操作或聚合操作，返回false
- 如果代码中没有查询操作，返回false
- 如果代码中已经包含其他限制方法（First、Last），返回false
- Take(1)会自动生成LIMIT 1的SQL

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# with_take场景第二步：生成添加Take()后的完整数据
PROMPT_WITH_TAKE_GENERATE = """
你需要为以下ORM代码添加Take(1)方法，生成完整的with_take场景数据。

原始ORM代码:
{orm_code}

原始场景: {original_scenario}

原始caller代码:
{caller_code}

原始code_meta_data（作为参考）:
{original_code_meta_data}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "with_take",
    "code_key": "方法名（保持原方法名不变）",
    "code_value": "添加Take(1)方法后的完整Go代码",
    "sql_pattern_cnt": 1,
    "callers": [
        {{
            "code_key": "调用者方法名（保持原方法名不变）",
            "code_value": "修改后的调用者代码"
        }}
    ],
    "callees": [],
    "code_meta_data": [
        {{
            "code_key": "结构体名或类型名",
            "code_value": "相关的Go类型定义（Take()方法通常保持切片类型）"
        }}
    ]
}}
```

修改要求：
1. **方法名保持**：保持原有的方法名不变
2. **查询链修改**：在查询链中添加`.Take(1)`，通常放在Where()之后，Find()之前
3. **code_meta_data要求**：
   - 基于原始code_meta_data进行适当调整
   - Take()方法通常保持原有的返回类型（切片类型）
   - 保持相关的结构体定义和常量定义
   - 确保类型定义与Take()方法的使用场景匹配
   - 如果原始code_meta_data为空，生成适当的类型定义
4. **返回类型保持**：保持原有的返回类型（切片类型）
5. **错误处理**：保持原有的错误处理逻辑
6. **代码结构**：保持原有的代码结构和注释
7. **变量名**：保持原有的变量名
8. **导入语句**：保持原有的import语句

**Take()方法的使用规则：**
- 在查询链中添加`.Take(1)`
- 通常放在条件设置之后，执行方法之前
- 例如：`db.Where("status = ?", 1).Take(1).Find(&users)`
- 会自动生成`LIMIT 1`的SQL

**Caller修改要求：**
9. **Caller方法名保持**：保持原有的caller方法名不变
10. **Caller调用保持**：保持对ORM方法的调用不变
11. **Caller变量处理**：caller中处理返回结果时，需要考虑结果被限制为1条记录
12. **Caller错误处理**：保持原有的错误处理逻辑
13. **Caller代码结构**：保持原有的代码结构和注释

**重要**：确保生成的代码语法正确，可以编译运行。

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# with_last场景第一步：判断是否可以添加Last()
PROMPT_WITH_LAST_JUDGE = """
你需要分析以下ORM代码，判断是否可以添加Last()方法。

原始ORM代码:
{orm_code}

请严格按照以下JSON格式输出：
```json
{{
    "can_add_last": true/false,
    "reason": "判断原因（如果可以添加Last，说明原因；如果不可以添加，详细说明原因）"
}}
```

判断规则：
**可以添加Last()的情况：**
- Find()查询：`db.Find(&users)` → `db.Last(&user)`
- Raw()查询：`db.Raw(sql).Scan(&results)` → `db.Raw(sql).Last(&result)`
- Select()查询：`db.Select("id").Find(&ids)` → `db.Select("id").Last(&id)`
- 查询链中包含Find()、Raw()、Select()等查询方法
- 返回结构体切片或基本类型切片的查询

**已经是Last()的情况（重要：这种情况返回true）：**
- 如果代码中已经包含Last()方法，**必须返回true**，生成时保持原样不变
- 如果已经是`db.Last(&user)`形式，**返回true**
- 如果已经是`db.Where(...).Last(&user)`形式，**返回true**

**不可以添加Last()的情况：**
- Create()、Update()、Delete()等写操作
- Count()、Sum()、Avg()、Max()、Min()等聚合操作
- 批量操作：Create([]User{{...}})
- 事务操作：Transaction()
- 关联操作：Association()
- 预加载操作：Preload()
- 已经包含First()、Take()等其他限制方法的查询

**特别注意：**
- **最高优先级**：如果代码中已经是Last()操作，**无条件返回true**
- 如果代码中有多个查询操作，只要有一个可以添加Last()就返回true
- 如果代码中有写操作或聚合操作，返回false
- 如果代码中没有查询操作，返回false
- 如果代码中已经包含其他限制方法（First、Take），返回false
- Last()会自动生成LIMIT 1和ORDER BY主键DESC的SQL

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# with_last场景第二步：生成添加Last()后的完整数据
PROMPT_WITH_LAST_GENERATE = """
你需要为以下ORM代码添加Last()方法，生成完整的with_last场景数据。

原始ORM代码:
{orm_code}

原始场景: {original_scenario}

原始caller代码:
{caller_code}

原始code_meta_data（作为参考）:
{original_code_meta_data}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "with_last",
    "code_key": "方法名（保持原方法名不变）",
    "code_value": "添加Last()方法后的完整Go代码",
    "sql_pattern_cnt": 1,
    "callers": [
        {{
            "code_key": "调用者方法名（保持原方法名不变）",
            "code_value": "修改后的调用者代码"
        }}
    ],
    "callees": [],
    "code_meta_data": [
        {{
            "code_key": "结构体名或类型名",
            "code_value": "更新后的Go类型定义（适配Last()方法的返回类型变化）"
        }}
    ]
}}
```

修改要求：
1. **方法名保持**：保持原有的方法名不变
2. **返回类型修改**：
   - `[]User` → `User`
   - `[]int64` → `int64`
   - `[]string` → `string`
   - `[]map[string]interface{{}}` → `map[string]interface{{}}`
3. **查询链修改**：将查询链中的Find()替换为Last()，或添加.Last()
4. **code_meta_data要求**：
   - 基于原始code_meta_data进行适当调整
   - 根据返回类型的变化（[]User → User），更新相关的结构体定义
   - 如果返回类型从切片变为单个对象，确保结构体定义正确
   - 保持其他必要的类型定义和常量定义
   - 如果原始code_meta_data为空，生成适当的类型定义
5. **错误处理**：保持原有的错误处理逻辑
6. **代码结构**：保持原有的代码结构和注释
7. **变量名**：保持原有的变量名，只修改返回类型
8. **导入语句**：保持原有的import语句

**Last()方法的使用规则：**
- 将 `db.Find(&users)` 替换为 `db.Last(&user)`
- 将 `db.Raw(sql).Scan(&results)` 替换为 `db.Raw(sql).Last(&result)`
- 会自动生成 `LIMIT 1` 和 `ORDER BY 主键 DESC` 的SQL
- 返回单个对象而不是切片

**Caller修改要求：**
9. **Caller方法名保持**：保持原有的caller方法名不变
10. **Caller调用保持**：保持对ORM方法的调用不变
11. **Caller变量处理**：如果caller中处理返回结果，需要相应调整（从切片改为单个对象）
12. **Caller错误处理**：保持原有的错误处理逻辑
13. **Caller代码结构**：保持原有的代码结构和注释

**重要**：确保生成的代码语法正确，可以编译运行。

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# with_find_no_limit场景第一步：判断是否可以使用Find()方法且不添加LIMIT
PROMPT_WITH_FIND_NO_LIMIT_JUDGE = """
你需要分析以下ORM代码，判断是否可以转换为使用Find()方法且不添加LIMIT限制。

原始ORM代码:
{orm_code}

请严格按照以下JSON格式输出：
```json
{{
    "can_use_find_no_limit": true/false,
    "reason": "判断原因（如果可以使用Find，说明原因；如果不可以使用，详细说明原因）"
}}
```

判断规则：
**可以使用Find()且不添加LIMIT的情况：**
- First()查询：`db.First(&user)` → `db.Find(&users)`
- Take()查询：`db.Take(&user)` → `db.Find(&users)`
- Last()查询：`db.Last(&user)` → `db.Find(&users)`
- Select()查询：`db.Select("id").First(&id)` → `db.Select("id").Find(&ids)`
- 查询链中包含First()、Take()、Last()等限制方法的查询
- 返回单个结构体的查询可以转换为返回结构体切片

**已经是Find()的情况（重要：这种情况返回true）：**
- 如果代码中已经包含Find()方法且没有LIMIT限制，**必须返回true**，生成时保持原样不变
- 如果已经是`db.Find(&users)`形式，**返回true**
- 如果已经是`db.Where(...).Find(&users)`形式，**返回true**

**不可以使用Find()且不添加LIMIT的情况：**
- Create()、Update()、Delete()等写操作
- Count()、Sum()、Avg()、Max()、Min()等聚合操作
- 批量操作：Create([]User{{...}})
- 事务操作：Transaction()
- 关联操作：Association()
- 预加载操作：Preload()（除非是查询操作）
- Raw()查询（通常需要保持原样）

**特别注意：**
- **最高优先级**：如果代码中已经是Find()且无LIMIT，**无条件返回true**
- 如果代码中有多个查询操作，只要有一个可以转换为Find()就返回true
- 如果代码中有写操作或聚合操作，返回false
- 如果代码中没有查询操作，返回false
- Find()方法会返回多条记录的完整结果集

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# with_find_no_limit场景第二步：生成使用Find()且不添加LIMIT的完整数据
PROMPT_WITH_FIND_NO_LIMIT_GENERATE = """
你需要为以下ORM代码转换为使用Find()方法且不添加LIMIT限制，生成完整的with_find_no_limit场景数据。

原始ORM代码:
{orm_code}

原始场景: {original_scenario}

原始caller代码:
{caller_code}

原始code_meta_data（作为参考）:
{original_code_meta_data}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "with_find_no_limit",
    "code_key": "方法名（保持原方法名不变）",
    "code_value": "转换为Find()且不添加LIMIT后的完整Go代码",
    "sql_pattern_cnt": 1,
    "callers": [
        {{
            "code_key": "调用者方法名（保持原方法名不变）",
            "code_value": "修改后的调用者代码"
        }}
    ],
    "callees": [],
    "code_meta_data": [
        {{
            "code_key": "结构体名或类型名",
            "code_value": "更新后的Go类型定义（适配Find()方法的返回类型变化）"
        }}
    ]
}}
```

修改要求：
1. **方法名保持**：保持原有的方法名不变
2. **特殊处理-已有Find()方法**：
   - 如果原始代码已经包含Find()方法且无LIMIT限制，保持原样不变
   - 如果已经是`db.Find(&users)`形式，直接保持
   - 如果已经是`db.Where(...).Find(&users)`形式，直接保持
3. **返回类型修改**：
   - `User` → `[]User`
   - `int64` → `[]int64`
   - `string` → `[]string`
   - `map[string]interface{{}}` → `[]map[string]interface{{}}`
   - 如果原本就是切片类型，保持不变
4. **查询链修改**：
   - 将First()、Take()、Last()替换为Find()
   - 如果已经是Find()，保持不变
   - 移除任何可能的LIMIT限制
5. **code_meta_data要求**：
   - 基于原始code_meta_data进行适当调整
   - 根据返回类型的变化（User → []User），更新相关的结构体定义
   - 如果返回类型从单个对象变为切片，确保结构体定义正确
   - 保持其他必要的类型定义和常量定义
   - 如果原始code_meta_data为空，生成适当的类型定义
6. **错误处理**：保持原有的错误处理逻辑
7. **代码结构**：保持原有的代码结构和注释
8. **变量名**：调整变量名以反映返回多条记录（如user→users）
9. **导入语句**：保持原有的import语句

**Find()方法的使用规则：**
- 将 `db.First(&user)` 替换为 `db.Find(&users)`
- 将 `db.Take(&user)` 替换为 `db.Find(&users)`
- 将 `db.Last(&user)` 替换为 `db.Find(&users)`
- 将 `db.Select("id").First(&id)` 替换为 `db.Select("id").Find(&ids)`
- Find()会返回多条记录，不添加LIMIT限制
- 返回结构体切片而不是单个对象

**Caller修改要求：**
10. **Caller方法名保持**：保持原有的caller方法名不变
11. **Caller调用保持**：保持对ORM方法的调用不变
12. **Caller变量处理**：如果caller中处理返回结果，需要相应调整（从单个对象改为切片处理）
13. **Caller错误处理**：保持原有的错误处理逻辑
14. **Caller代码结构**：保持原有的代码结构和注释

**重要**：确保生成的代码语法正确，可以编译运行。

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

# with_count场景第一步：判断是否可以转换为Count()方法
PROMPT_WITH_COUNT_JUDGE = """
你需要分析以下ORM代码，判断是否可以转换为使用Count()方法生成SELECT COUNT(*)查询。

原始ORM代码:
{orm_code}

请严格按照以下JSON格式输出：
```json
{{
    "can_use_count": true/false,
    "reason": "判断原因（如果可以使用Count，说明原因；如果不可以使用，详细说明原因）"
}}
```

判断规则：
**可以使用Count()的情况：**
- Find()查询：`db.Find(&users)` → `db.Model(&User{{}}).Count(&count)`
- First()查询：`db.First(&user)` → `db.Model(&User{{}}).Count(&count)`
- Take()查询：`db.Take(&user)` → `db.Model(&User{{}}).Count(&count)`
- Last()查询：`db.Last(&user)` → `db.Model(&User{{}}).Count(&count)`
- Select()查询：`db.Select("id").Find(&ids)` → `db.Model(&User{{}}).Count(&count)`
- 查询链中包含Where()条件的查询
- 任何用于查询记录的操作都可以转换为统计操作

**已经是Count()的情况（重要：这种情况返回true）：**
- 如果代码中已经包含Count()方法，**必须返回true**，生成时保持原样不变
- 如果已经是`db.Model(&User{{}}).Count(&count)`形式，**返回true**
- 如果已经是`db.Table("users").Count(&count)`形式，**返回true**

**不可以使用Count()的情况：**
- Create()、Update()、Delete()等写操作
- 其他聚合操作：Sum()、Avg()、Max()、Min()（Count除外）
- 批量操作：Create([]User{{...}})
- 事务操作：Transaction()
- 关联操作：Association()
- Raw()查询（通常需要保持原样，除非是简单查询）

**特别注意：**
- **最高优先级**：如果代码中已经是Count()操作，**无条件返回true**
- 如果代码中有多个查询操作，只要有一个可以转换为Count()就返回true
- 如果代码中有写操作，返回false
- Count()方法会生成SELECT COUNT(*)查询，返回记录数量

只返回JSON格式，不要包含markdown标记或其他文本。
"""

# with_count场景第二步：生成使用Count()的完整数据
PROMPT_WITH_COUNT_GENERATE = """
你需要为以下ORM代码转换为使用Count()方法生成SELECT COUNT(*)查询，生成完整的with_count场景数据。

原始ORM代码:
{orm_code}

原始场景: {original_scenario}

原始caller代码:
{caller_code}

原始code_meta_data（作为参考）:
{original_code_meta_data}

请严格按照以下JSON格式输出，确保字段完整：
```json
{{
    "scenario": "with_count",
    "code_key": "方法名（保持原方法名不变）",
    "code_value": "转换为Count()的完整Go代码",
    "sql_pattern_cnt": 1,
    "callers": [
        {{
            "code_key": "调用者方法名（保持原方法名不变）",
            "code_value": "修改后的调用者代码"
        }}
    ],
    "callees": [],
    "code_meta_data": [
        {{
            "code_key": "结构体名或类型名",
            "code_value": "更新后的Go类型定义（适配Count()方法的返回类型变化）"
        }}
    ]
}}
```

修改要求：
1. **方法名保持**：保持原有的方法名不变
2. **特殊处理-已有Count()方法**：
   - 如果原始代码已经包含Count()方法，保持原样不变
   - 如果已经是`db.Model(&User{{}}).Count(&count)`形式，直接保持
   - 如果已经是`db.Table("users").Count(&count)`形式，直接保持
3. **返回类型修改**：
   - `User` → `int64`
   - `[]User` → `int64`
   - `string` → `int64`
   - `[]string` → `int64`
   - `map[string]interface{{}}` → `int64`
   - 所有返回类型都改为int64（记录数量）
4. **查询链修改**：
   - 将Find()、First()、Take()、Last()等替换为Count()
   - 使用Model()指定查询的表/模型
   - 保留所有Where()条件
   - 移除Select()中的字段选择（Count不需要）
5. **code_meta_data要求**：
   - 基于原始code_meta_data进行适当调整
   - 根据返回类型的变化（转为int64），更新相关的类型定义
   - Count()方法返回记录数量，可能不需要复杂的结构体定义
   - 保持必要的常量定义（如表名）
   - 如果原始code_meta_data为空，生成适当的类型定义
6. **错误处理**：保持原有的错误处理逻辑
7. **代码结构**：保持原有的代码结构和注释
8. **变量名**：调整变量名以反映计数结果（如users→count, user→count）
9. **导入语句**：保持原有的import语句

**Count()方法的使用规则：**
- 将 `db.Find(&users)` 替换为 `db.Model(&User{{}}).Count(&count)`
- 将 `db.First(&user)` 替换为 `db.Model(&User{{}}).Count(&count)`
- 将 `db.Where("status = ?", 1).Find(&users)` 替换为 `db.Model(&User{{}}).Where("status = ?", 1).Count(&count)`
- Count()返回满足条件的记录数量
- 返回值类型为int64

**Caller修改要求：**
10. **Caller方法名保持**：保持原有的caller方法名不变
11. **Caller调用保持**：保持对ORM方法的调用不变
12. **Caller变量处理**：如果caller中处理返回结果，需要相应调整（处理计数结果而不是记录对象）
13. **Caller错误处理**：保持原有的错误处理逻辑
14. **Caller代码结构**：保持原有的代码结构和注释

**重要**：确保生成的代码语法正确，可以编译运行。

只返回JSON格式，不要包含markdown标记或其他文本。
""" 

 