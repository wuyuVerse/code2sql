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