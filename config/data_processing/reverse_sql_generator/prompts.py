"""
反向SQL生成器提示词模板
"""

# SQL生成提示词
SQL_GENERATION_PROMPTS = {
    "complete_sql": """
你需要为给定的场景生成一个完整的SQL查询。

场景: {scenario}
场景描述: {scenario_desc}
复杂度: {complexity} - {complexity_desc}

要求：
1. 生成一个"全条件查询"，包含所有可能的字段和条件
2. 表名使用: {table_name}
3. 字段名使用: {field_examples} 等多样化字段
4. 条件数量: {min_conditions}-{max_conditions} 个
5. 实体名使用: {entity_examples}
6. SQL必须语法正确，可执行
7. 包含适当的WHERE条件、ORDER BY、LIMIT等

请严格按照以下JSON格式输出：
```json
{{
    "query": "完整的SQL查询语句",
    "table": "表名",
    "fields": ["字段1", "字段2", "字段3"],
    "conditions": [
        {{
            "field": "字段名",
            "operator": "操作符",
            "value": "值或参数",
            "type": "条件类型"
        }}
    ],
    "joins": [
        {{
            "table": "关联表",
            "type": "JOIN类型",
            "condition": "关联条件"
        }}
    ],
    "group_by": ["分组字段1", "分组字段2"],
    "order_by": [
        {{
            "field": "排序字段",
            "direction": "ASC/DESC"
        }}
    ],
    "limit": 数量,
    "offset": 偏移量
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "if_else_variants": """
基于以下基础SQL查询，生成if-else分支的SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成2-3个不同的SQL变体，对应不同的if-else分支
2. 每个变体应该有不同的WHERE条件组合
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "if分支1的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符", 
                "value": "值",
                "type": "条件类型"
            }}
        ],
        "branch": "if_branch_1",
        "description": "分支1描述"
    }},
    {{
        "query": "if分支2的SQL查询",
        "table": "表名", 
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值", 
                "type": "条件类型"
            }}
        ],
        "branch": "if_branch_2",
        "description": "分支2描述"
    }},
    {{
        "query": "else分支的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值",
                "type": "条件类型"
            }}
        ],
        "branch": "else_branch",
        "description": "else分支描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "switch_variants": """
基于以下基础SQL查询，生成switch分支的SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成4-6个不同的SQL变体，对应不同的switch case分支
2. 每个变体应该有不同的WHERE条件组合
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "case 1的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值",
                "type": "条件类型"
            }}
        ],
        "branch": "case_1",
        "description": "case 1描述"
    }},
    {{
        "query": "case 2的SQL查询", 
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值",
                "type": "条件类型"
            }}
        ],
        "branch": "case_2",
        "description": "case 2描述"
    }},
    {{
        "query": "case 3的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值",
                "type": "条件类型"
            }}
        ],
        "branch": "case_3", 
        "description": "case 3描述"
    }},
    {{
        "query": "default的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值",
                "type": "条件类型"
            }}
        ],
        "branch": "default",
        "description": "default分支描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "dynamic_variants": """
基于以下基础SQL查询，生成动态条件查询的SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成3-5个不同的SQL变体，对应不同的动态条件组合
2. 每个变体应该有不同的WHERE条件组合
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "动态条件1的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值",
                "type": "动态条件"
            }}
        ],
        "variant": "dynamic_1",
        "description": "动态条件1描述"
    }},
    {{
        "query": "动态条件2的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值",
                "type": "动态条件"
            }}
        ],
        "variant": "dynamic_2",
        "description": "动态条件2描述"
    }},
    {{
        "query": "动态条件3的SQL查询",
        "table": "表名",
        "fields": ["字段1", "字段2"],
        "conditions": [
            {{
                "field": "字段名",
                "operator": "操作符",
                "value": "值",
                "type": "动态条件"
            }}
        ],
        "variant": "dynamic_3",
        "description": "动态条件3描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
"""
}

# ORM映射提示词
ORM_MAPPING_PROMPTS = {
    "sql_to_orm": """
你需要将以下SQL查询转换为Go语言的ORM代码：

SQL查询:
{sql_data}

要求：
1. 使用GORM框架
2. 方法名使用: {method_examples}
3. 实体名使用: {entity_examples}
4. 表名使用: {table_examples}
5. 字段名使用: {field_examples}
6. 代码必须完整可运行
7. 包含适当的错误处理
8. 支持动态参数传递

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "方法名",
    "code": "完整的Go ORM代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "table": "表名",
    "fields": ["字段1", "字段2"],
    "conditions": [
        {{
            "field": "字段名",
            "operator": "操作符",
            "value": "值或参数",
            "type": "条件类型"
        }}
    ]
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
"""
}

# Caller生成提示词
CALLER_GENERATION_PROMPTS = {
    "basic_caller": """
你需要为以下ORM代码生成调用者代码：

ORM代码:
{orm_data}

场景: {scenario}
场景描述: {scenario_desc}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 代码必须完整可运行
6. 包含适当的参数验证和错误处理
7. 正确调用ORM方法并传递参数

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "调用者方法名",
    "code": "完整的Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "if_else_caller": """
你需要为以下ORM代码生成包含if-else逻辑的调用者代码：

ORM代码:
{orm_data}

if-else SQL变体:
{if_else_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 必须包含if-else条件判断逻辑
6. 根据不同的条件构建不同的filter参数
7. 每个if分支对应一个SQL变体
8. 包含适当的参数验证和错误处理
9. 代码必须完整可运行

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "调用者方法名",
    "code": "完整的Go调用者代码（包含if-else逻辑）",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "branches": [
        {{
            "condition": "if条件",
            "description": "分支描述",
            "sql_variant": "对应的SQL变体"
        }}
    ],
    "description": "方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "switch_caller": """
你需要为以下ORM代码生成包含switch逻辑的调用者代码：

ORM代码:
{orm_data}

switch SQL变体:
{switch_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 必须包含switch条件判断逻辑
6. 根据不同的case构建不同的filter参数
7. 每个case分支对应一个SQL变体
8. 包含default分支处理未知情况
9. 包含适当的参数验证和错误处理
10. 代码必须完整可运行

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "调用者方法名",
    "code": "完整的Go调用者代码（包含switch逻辑）",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "cases": [
        {{
            "case_value": "case值",
            "description": "case描述",
            "sql_variant": "对应的SQL变体"
        }}
    ],
    "default_case": {{
        "description": "default分支描述",
        "sql_variant": "对应的SQL变体"
    }},
    "description": "方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "dynamic_caller": """
你需要为以下ORM代码生成动态条件查询的调用者代码：

ORM代码:
{orm_data}

动态SQL变体:
{dynamic_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 支持动态参数传递和条件组合
6. 根据传入的参数动态构建filter
7. 每个参数组合对应一个SQL变体
8. 包含适当的参数验证和错误处理
9. 代码必须完整可运行

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "调用者方法名",
    "code": "完整的Go调用者代码（支持动态条件）",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "dynamic_combinations": [
        {{
            "combination": "参数组合描述",
            "description": "组合描述",
            "sql_variant": "对应的SQL变体"
        }}
    ],
    "description": "方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
"""
} 