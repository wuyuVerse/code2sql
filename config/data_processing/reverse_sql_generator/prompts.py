"""
反向SQL生成器提示词模板
"""

# SQL生成提示词
SQL_GENERATION_PROMPTS = {
    "complete_sql": """
你需要为给定的场景生成一个完整的SQL查询。

场景: {scenario}
复杂度: {complexity}

要求：
1. 生成一个"全条件查询"，包含所有可能的字段和条件
2. 表名使用: {table_examples}
3. 字段名使用: {field_examples} 等多样化字段
4. SQL必须语法正确，可执行
5. 包含适当的WHERE条件、ORDER BY、LIMIT等

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
    ]
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "if_else_variants": """
基于以下基础SQL查询，生成if-else分支的SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，对应不同的if-else分支
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
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "if_else_orm_variants": """
基于以下基础SQL查询，生成if-else+orm分支的SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，对应不同的if-else+orm分支
2. 每个变体应该有不同的WHERE条件组合，模拟ORM内部的if-else逻辑
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段
6. 变体应该反映ORM方法内部的if-else条件判断

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "if-else+orm分支1的SQL查询",
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
        "branch": "if_else_orm_branch_1",
        "description": "if-else+orm分支1描述"
    }},
    {{
        "query": "if-else+orm分支2的SQL查询",
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
        "branch": "if_else_orm_branch_2",
        "description": "if-else+orm分支2描述"
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
1. 生成{variants_count}个不同的SQL变体，对应不同的switch分支
2. 每个变体应该有不同的WHERE条件组合
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "switch分支1的SQL查询",
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
        "variant": "switch_case_1",
        "description": "switch分支1描述"
    }},
    {{
        "query": "switch分支2的SQL查询",
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
        "variant": "switch_case_2",
        "description": "switch分支2描述"
    }},
    {{
        "query": "switch分支3的SQL查询",
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
        "variant": "switch_case_3",
        "description": "switch分支3描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "dynamic_variants": """
基于以下基础SQL查询，生成动态查询的SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，对应不同的动态条件组合
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
                "type": "条件类型"
            }}
        ],
        "variant": "dynamic_condition_1",
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
                "type": "条件类型"
            }}
        ],
        "variant": "dynamic_condition_2",
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
                "type": "条件类型"
            }}
        ],
        "variant": "dynamic_condition_3",
        "description": "动态条件3描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "complex_control_variants": """
基于以下基础SQL查询，生成复杂控制流的SQL变体（多层嵌套的if-else或switch结构）：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，对应复杂控制流的不同分支
2. 每个变体应该有不同的WHERE条件组合
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段
6. 变体应该体现多层嵌套的控制流逻辑

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "复杂控制流分支1的SQL查询",
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
        "variant": "complex_branch_1",
        "description": "复杂控制流分支1描述"
    }},
    {{
        "query": "复杂控制流分支2的SQL查询",
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
        "variant": "complex_branch_2",
        "description": "复杂控制流分支2描述"
    }},
    {{
        "query": "复杂控制流分支3的SQL查询",
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
        "variant": "complex_branch_3",
        "description": "复杂控制流分支3描述"
    }},
    {{
        "query": "复杂控制流分支4的SQL查询",
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
        "variant": "complex_branch_4",
        "description": "复杂控制流分支4描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "fixed_params_variants": """
基于以下基础SQL查询，生成固定参数SQL变体（包含固定参数和动态参数的不同组合）：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，体现固定参数和动态参数的不同组合
2. 每个变体应该有不同的参数组合方式
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段
6. 变体应该体现固定参数和动态参数的混合使用

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "包含所有固定和动态参数的SQL查询",
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
        "variant": "all_params",
        "description": "包含所有参数的完整查询"
    }},
    {{
        "query": "仅包含固定参数的SQL查询",
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
        "variant": "fixed_only",
        "description": "仅使用固定参数的查询"
    }},
    {{
        "query": "固定参数+部分动态参数的SQL查询",
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
        "variant": "mixed_params",
        "description": "固定参数和部分动态参数的混合查询"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "if_else_switch_mixed_variants": """
基于以下基础SQL查询，生成if-else+switch混合SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，对应if-else和switch混合控制流的不同分支
2. 每个变体应该有不同的WHERE条件组合
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段
6. 变体应该体现if-else和switch混合的逻辑

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "if-else+switch混合分支1的SQL查询",
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
        "variant": "mixed_branch_1",
        "description": "if-else+switch混合分支1描述"
    }},
    {{
        "query": "if-else+switch混合分支2的SQL查询",
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
        "variant": "mixed_branch_2",
        "description": "if-else+switch混合分支2描述"
    }},
    {{
        "query": "if-else+switch混合分支3的SQL查询",
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
        "variant": "mixed_branch_3",
        "description": "if-else+switch混合分支3描述"
    }},
    {{
        "query": "if-else+switch混合分支4的SQL查询",
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
        "variant": "mixed_branch_4",
        "description": "if-else+switch混合分支4描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "conditional_chain_variants": """
基于以下基础SQL查询，生成条件链式查询SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，对应条件链式查询的不同步骤
2. 每个变体应该体现逐步构建查询条件的逻辑
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段
6. 变体应该体现条件链式构建的过程

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "条件链式查询步骤1的SQL查询",
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
        "variant": "chain_step_1",
        "description": "条件链式查询步骤1描述"
    }},
    {{
        "query": "条件链式查询步骤2的SQL查询",
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
        "variant": "chain_step_2",
        "description": "条件链式查询步骤2描述"
    }},
    {{
        "query": "条件链式查询步骤3的SQL查询",
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
        "variant": "chain_step_3",
        "description": "条件链式查询步骤3描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "multi_branch_transaction_variants": """
基于以下基础SQL查询，生成多分支事务处理SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体
2. 每个变体对应不同的业务分支和条件
3. 表名使用: {table_name}
4. 字段名使用: {field_examples}

请严格按照以下JSON格式输出：
```json
[
    {{
        "query": "分支1的SQL查询",
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
        "variant": "branch_1",
        "description": "分支1描述"
    }},
    {{
        "query": "分支2的SQL查询",
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
        "variant": "branch_2",
        "description": "分支2描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "state_machine_branch_variants": """
基于以下基础SQL查询，生成状态机式分支SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，对应状态机不同状态的数据库操作
2. 每个变体应该对应不同的对象状态
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段
6. 变体应该体现状态机逻辑的不同状态

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "状态机状态1的SQL查询",
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
        "variant": "state_1",
        "description": "状态机状态1描述"
    }},
    {{
        "query": "状态机状态2的SQL查询",
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
        "variant": "state_2",
        "description": "状态机状态2描述"
    }},
    {{
        "query": "状态机状态3的SQL查询",
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
        "variant": "state_3",
        "description": "状态机状态3描述"
    }},
    {{
        "query": "状态机状态4的SQL查询",
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
        "variant": "state_4",
        "description": "状态机状态4描述"
    }}
]
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "conditional_meta_variants": """
基于以下基础SQL查询，生成条件分支+meta SQL变体：

基础SQL:
{base_sql}

要求：
1. 生成{variants_count}个不同的SQL变体，对应条件分支+meta配置的不同组合
2. 每个变体应该体现配置和条件的双重判断
3. 保持相同的表结构和基本查询逻辑
4. 表名使用: {table_name}
5. 字段名使用: {field_examples} 等多样化字段
6. 变体应该体现元数据配置的影响

请严格按照以下JSON格式输出（数组格式）：
```json
[
    {{
        "query": "条件分支+meta配置1的SQL查询",
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
        "variant": "meta_config_1",
        "description": "条件分支+meta配置1描述"
    }},
    {{
        "query": "条件分支+meta配置2的SQL查询",
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
        "variant": "meta_config_2",
        "description": "条件分支+meta配置2描述"
    }},
    {{
        "query": "条件分支+meta配置3的SQL查询",
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
        "variant": "meta_config_3",
        "description": "条件分支+meta配置3描述"
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
6. 只生成函数定义，不包含package、import和结构体定义
7. 包含适当的错误处理
8. 支持动态参数传递

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "方法名",
    "code": "只包含函数定义的Go ORM代码（不包含package、import、结构体定义）",
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
""",

    "sql_to_orm_with_if_else": """
你需要将以下SQL查询转换为包含if-else逻辑的Go语言ORM代码：

基础SQL查询:
{sql_data}

if-else SQL变体:
{if_else_sqls}

要求：
1. 使用GORM框架
2. 方法名使用: {method_examples}
3. 实体名使用: {entity_examples}
4. 表名使用: {table_examples}
5. 字段名使用: {field_examples}
6. 在ORM方法内部添加if-else条件判断逻辑
7. 根据不同的条件分支使用不同的SQL查询条件
8. 代码必须完整可运行
9. 包含适当的错误处理

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "方法名",
    "code": "包含if-else逻辑的完整Go ORM代码",
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
""",

    "sql_to_orm_multi_branch_transaction": """
你需要将以下SQL查询转换为多分支事务处理的Go语言ORM代码：

SQL查询:
{sql_data}

要求：
1. 使用GORM框架
2. 方法名使用: {method_examples}
3. 实体名使用: {entity_examples}
4. 表名使用: {table_examples}
5. 字段名使用: {field_examples}
6. 实现多分支事务处理逻辑，包含多个业务分支
7. 每个分支对应不同的数据库操作（查询、更新、删除等）
8. 包含事务管理和错误回滚
9. 代码必须完整可运行
10. 包含适当的错误处理

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "方法名",
    "code": "包含多分支事务处理逻辑的完整Go ORM代码",
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
5. 只生成函数定义，不包含package、import和结构体定义
6. 包含if-else条件判断逻辑
7. 根据不同的条件调用不同的ORM方法
8. 包含适当的参数验证和错误处理

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "if-else调用者方法名",
    "code": "只包含函数定义的Go调用者代码（不包含package、import、结构体定义）",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "if-else方法描述"
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
5. 代码必须完整可运行
6. 包含switch条件判断逻辑
7. 根据不同的参数值调用不同的ORM方法
8. 包含适当的参数验证和错误处理

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "switch调用者方法名",
    "code": "包含switch逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "switch方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "dynamic_caller": """
你需要为以下ORM代码生成包含动态查询逻辑的调用者代码：

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
5. 代码必须完整可运行
6. 包含动态条件处理逻辑
7. 根据不同的动态参数调用不同的ORM方法
8. 包含适当的参数验证和错误处理

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "动态查询调用者方法名",
    "code": "包含动态查询逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "动态查询方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "complex_control_caller": """
你需要为以下ORM代码生成包含复杂控制流逻辑的调用者代码：

ORM代码:
{orm_data}

复杂控制流SQL变体:
{complex_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 代码必须完整可运行
6. 包含多层嵌套的if-else或switch逻辑
7. 根据不同的条件组合调用不同的ORM方法
8. 包含适当的参数验证和错误处理
9. 体现复杂控制流的业务逻辑

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "复杂控制流调用者方法名",
    "code": "包含复杂控制流逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "复杂控制流方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "fixed_params_caller": """
你需要为以下ORM代码生成包含固定参数逻辑的调用者代码：

ORM代码:
{orm_data}

固定参数SQL变体:
{fixed_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 代码必须完整可运行
6. 包含固定参数和动态参数的混合处理逻辑
7. 根据不同的参数组合调用不同的ORM方法
8. 包含适当的参数验证和错误处理
9. 体现固定参数和动态参数的混合使用场景

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "固定参数调用者方法名",
    "code": "包含固定参数逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "固定参数方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "if_else_switch_mixed_caller": """
你需要为以下ORM代码生成包含if-else+switch混合逻辑的调用者代码：

ORM代码:
{orm_data}

if-else+switch混合SQL变体:
{mixed_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 代码必须完整可运行
6. 包含if-else和switch-case混合控制流逻辑
7. 根据多个条件参数选择不同的数据库操作策略
8. 包含适当的参数验证和错误处理
9. 体现if-else和switch混合的复杂控制流

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "if-else+switch混合调用者方法名",
    "code": "包含if-else+switch混合逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "if-else+switch混合方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "conditional_chain_caller": """
你需要为以下ORM代码生成包含条件链式查询逻辑的调用者代码：

ORM代码:
{orm_data}

条件链式查询SQL变体:
{chain_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 代码必须完整可运行
6. 包含连续的if-else条件判断逻辑
7. 通过逐步构建查询条件影响最终的SQL语句
8. 包含适当的参数验证和错误处理
9. 体现条件链式构建的查询逻辑

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "条件链式查询调用者方法名",
    "code": "包含条件链式查询逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "条件链式查询方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "multi_branch_transaction_caller": """
你需要为以下ORM代码生成包含多分支事务处理逻辑的调用者代码：

ORM代码:
{orm_data}

多分支事务处理SQL变体:
{transaction_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 代码必须完整可运行
6. 包含复杂的条件分支控制事务处理流程
7. 不同分支执行不同的数据库操作组合
8. 包含适当的参数验证和错误处理
9. 体现多分支事务处理的业务逻辑

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "多分支事务处理调用者方法名",
    "code": "包含多分支事务处理逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "多分支事务处理方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "state_machine_branch_caller": """
你需要为以下ORM代码生成包含状态机式分支逻辑的调用者代码：

ORM代码:
{orm_data}

状态机式分支SQL变体:
{state_machine_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 代码必须完整可运行
6. 基于对象状态使用switch-case实现状态机逻辑
7. 每个状态对应特定的数据库操作序列
8. 包含适当的参数验证和错误处理
9. 体现状态机式的分支控制逻辑

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "状态机式分支调用者方法名",
    "code": "包含状态机式分支逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "状态机式分支方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
""",

    "conditional_meta_caller": """
你需要为以下ORM代码生成包含条件分支+meta逻辑的调用者代码：

ORM代码:
{orm_data}

条件分支+meta SQL变体:
{meta_sqls}

场景: {scenario}

要求：
1. 方法名使用: {method_examples}
2. 实体名使用: {entity_examples}
3. 表名使用: {table_examples}
4. 字段名使用: {field_examples}
5. 代码必须完整可运行
6. 使用if-else条件分支的同时依赖元数据配置
7. 根据配置和条件双重判断执行不同操作
8. 包含适当的参数验证和错误处理
9. 体现元数据配置对业务逻辑的影响

请严格按照以下JSON格式输出：
```json
{{
    "method_name": "条件分支+meta调用者方法名",
    "code": "包含条件分支+meta逻辑的完整Go调用者代码",
    "parameters": [
        {{
            "name": "参数名",
            "type": "参数类型",
            "description": "参数描述"
        }}
    ],
    "return_type": "返回类型",
    "orm_method": "调用的ORM方法名",
    "description": "条件分支+meta方法描述"
}}
```

只返回JSON格式，不要包含markdown标记或其他文本。
"""
} 