"""
控制流验证和SQL重新生成提示词

用于检测包含switch、if等控制流语句的ORM代码，验证生成的SQL变体数量是否合理，
并根据验证结果重新生成正确的SQL变体
"""

CONTROL_FLOW_VALIDATION_PROMPT = """你是一个专业的代码分析专家，需要分析Go语言ORM代码中的控制流语句，并验证生成的SQL变体数量是否合理。

请分析以下ORM代码及其上下文：

**调用者信息：**
{caller}

**代码元数据：**
{code_meta_data}

**ORM代码：**
{orm_code}

**当前生成的SQL变体：**
{current_sql_variants}

**分析要求：**

1. **控制流识别**：识别代码中的switch、if、else if等控制流语句
2. **分支分析**：分析每个分支的执行条件和逻辑
3. **可达性分析**：结合调用者信息和代码元数据，分析哪些分支是可能被执行的
4. **SQL变体验证**：验证生成的SQL变体数量是否与实际的可达控制流分支数量匹配
5. **合理性判断**：判断是否有多余或缺失的SQL变体

**分析标准：**

- **switch语句**：每个可达的case分支通常对应一个SQL变体（除非多个case执行相同逻辑）
- **if-else语句**：每个可达的if分支通常对应一个SQL变体
- **嵌套控制流**：需要考虑嵌套的控制流结构
- **条件合并**：如果多个条件执行相同的SQL逻辑，应该合并为一个变体
- **默认分支**：需要考虑default分支或else分支
- **可达性判断**：
  - 结合调用者信息分析函数调用路径
  - 根据代码元数据中的参数类型、值范围等判断分支可达性
  - 排除明显无法到达的分支（如条件永远为false的分支）
  - 考虑参数约束对分支执行的影响

**输出格式：**

请以JSON格式输出分析结果：

```json
{{
    "control_flow_analysis": {{
        "switch_statements": [
            {{
                "line_range": "行号范围",
                "variable": "判断变量",
                "branches": [
                    {{
                        "condition": "条件值",
                        "logic": "执行逻辑描述",
                        "is_reachable": true/false,
                        "reachability_reason": "可达性分析原因",
                        "should_have_sql": true/false
                    }}
                ]
            }}
        ],
        "if_statements": [
            {{
                "line_range": "行号范围", 
                "condition": "条件描述",
                "logic": "执行逻辑描述",
                "is_reachable": true/false,
                "reachability_reason": "可达性分析原因",
                "should_have_sql": true/false
            }}
        ],
        "reachability_analysis": {{
            "caller_analysis": "基于调用者信息的可达性分析",
            "parameter_constraints": "基于代码元数据的参数约束分析",
            "unreachable_branches": [
                "无法到达的分支及原因"
            ]
        }}
    }},
    "sql_variants_analysis": {{
        "expected_count": "期望的SQL变体数量（仅考虑可达分支）",
        "actual_count": "实际的SQL变体数量",
        "is_reasonable": true/false,
        "issues": [
            "发现的问题描述"
        ],
        "recommendations": [
            "建议的改进措施"
        ]
    }},
    "final_judgment": {{
        "is_correct": true/false,
        "reason": "判断理由"
    }}
}}
```

请仔细分析代码结构，确保分析结果的准确性。"""


CONTROL_FLOW_SQL_REGENERATION_PROMPT = """你是一个专业的SQL生成专家，需要根据控制流验证结果重新生成正确的SQL变体。

**原始信息：**

**调用者信息：**
{caller}

**代码元数据：**
{code_meta_data}

**ORM代码：**
{orm_code}

**控制流验证结果：**
{validation_result}

**重新生成要求：**

1. **根据验证结果调整SQL变体**：
   - 如果验证发现SQL变体数量不合理，请根据控制流分析重新生成
   - 确保每个可达的控制流分支对应一个SQL变体（除非多个分支执行相同逻辑）
   - 移除多余的SQL变体，添加缺失的SQL变体
   - **重要**：只生成可达分支对应的SQL，排除无法到达的分支

2. **控制流分析指导**：
   - 严格按照控制流分析中的可达分支逻辑生成SQL
   - 每个可达的case分支通常对应一个SQL变体
   - 考虑可达的if-else分支的执行条件
   - 注意嵌套控制流的影响
   - 结合调用者信息和代码元数据，确保只生成可能执行的分支对应的SQL

3. **可达性分析指导**：
   - 基于调用者信息分析函数调用路径
   - 根据代码元数据中的参数类型、值范围等判断分支可达性
   - 排除明显无法到达的分支（如条件永远为false的分支）
   - 考虑参数约束对分支执行的影响

4. **SQL生成标准**：
   - 确保SQL完整可执行，参数用?占位
   - 每条SQL以分号结尾
   - 不含省略号或占位符
   - 只有SQL结构不同才视为不同变体

**输出格式要求：**
输出标准JSON数组，结构如下：
[
  "固定SQL语句;",
  {{
    "type": "param_dependent", 
    "variants": [
      {{"scenario": "条件描述", "sql": "完整SQL语句;"}},
      {{"scenario": "条件描述", "sql": "完整SQL语句;"}}
    ]
  }},
  "另一个固定SQL;"
]

**严格要求：**
- 仅输出纯JSON数组，无其他文字说明
- SQL语句必须完整可执行，以分号结尾
- 参数使用问号(?)表示
- 根据控制流分析结果，生成正确数量的SQL变体
- 确保每个变体对应实际的可达控制流分支
- **重要**：只生成可达分支对应的SQL，排除无法到达的分支

**注意**：严格遵循控制流验证结果，确保生成的SQL变体数量与实际的可达控制流分支逻辑相匹配。结合调用者信息和代码元数据，确保只生成可能执行的分支对应的SQL。"""


def get_control_flow_validation_prompt(orm_code: str, caller: str, code_meta_data: str, current_sql_variants: str) -> str:
    """
    生成控制流验证提示词
    
    Args:
        orm_code: ORM代码
        caller: 调用者信息
        code_meta_data: 代码元数据
        current_sql_variants: 当前生成的SQL变体
        
    Returns:
        格式化的提示词
    """
    return CONTROL_FLOW_VALIDATION_PROMPT.format(
        orm_code=orm_code,
        caller=caller,
        code_meta_data=code_meta_data,
        current_sql_variants=current_sql_variants
    )


def get_control_flow_sql_regeneration_prompt(orm_code: str, caller: str, code_meta_data: str, validation_result: str) -> str:
    """
    生成控制流SQL重新生成提示词
    
    Args:
        orm_code: ORM代码
        caller: 调用者信息
        code_meta_data: 代码元数据
        validation_result: 控制流验证结果
        
    Returns:
        格式化的提示词
    """
    return CONTROL_FLOW_SQL_REGENERATION_PROMPT.format(
        orm_code=orm_code,
        caller=caller,
        code_meta_data=code_meta_data,
        validation_result=validation_result
    ) 