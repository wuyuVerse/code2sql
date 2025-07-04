"""
SQL完整性检查提示词配置
"""

SQL_COMPLETENESS_CHECK_PROMPT = """请判断根据以下GORM代码和上下文信息生成的SQL语句是否完善：

**判断标准：**
SQL语句被认为完善当且仅当满足以下所有条件：

1. **SQL生成完整性**：
   - 包含了ORM代码中所有会执行的数据库操作（Find、Create、Update、Delete等）
   - 覆盖了所有可能的执行路径和条件分支
   - 没有遗漏任何会生成SQL的代码行

2. **表名和字段名准确性**：
   - 表名遵循正确的优先级规则（TableName()函数 > 配置映射 > 直接显式 > 默认转换）
   - 字段名遵循正确的映射规则（column标签 > 配置映射 > 直接显式 > 默认转换）
   - 直接写出的表名/字段名完全按原样保留，无格式转换
   - 正确应用了表前缀/后缀（如有配置）

3. **SQL语法正确性**：
   - JOIN操作中所有列名都带有表别名前缀
   - ON条件使用完整的表别名.列名格式
   - DELETE操作包含了显式WHERE条件和主键自动条件
   - SQL语句完整可执行，无省略号或占位符

4. **条件组合完整性**：
   - 枚举了所有可能的WHERE条件字段组合
   - 考虑了动态条件构建（if判断、循环、switch等）
   - 区分了SQL结构不同的变体（不仅是参数值不同）

5. **上下文一致性**：
   - 如果提供调用者信息，只包含当前调用者会触发的执行路径
   - 如果提供被调用者信息，包含了内部调用可能产生的SQL
   - 正确忽略了注释代码，不基于注释生成SQL

6. **数量准确性**：
   - 生成的SQL语句数量符合代码逻辑
   - 没有重复的SQL模板
   - 没有无效或虚假的SQL语句

**检查项目：**
- [ ] 是否遗漏了某些数据库操作？
- [ ] 表名是否按正确优先级确定？
- [ ] 字段名映射是否准确？
- [ ] JOIN操作的表别名是否正确？
- [ ] WHERE条件组合是否完整？
- [ ] 是否错误包含了注释代码的影响？
- [ ] 调用者上下文是否被正确限制？
- [ ] SQL语法是否完整无误？
- [ ] 是否存在无效的虚假SQL？

**输出要求：**
- 如果SQL语句完善：仅输出"是"
- 如果SQL语句不完善：输出"否"，并说明原因,20字以内。

**分析材料：**
调用者：{caller}
元数据：{code_meta}
GORM代码：{orm_code}
生成的SQL语句：{sql_statements}
"""


def get_sql_completeness_check_prompt(caller: str, code_meta: str, orm_code: str, sql_statements: str) -> str:
    """
    生成SQL完整性检查提示词
    
    Args:
        caller: 调用者信息
        code_meta: 元数据信息
        orm_code: GORM代码
        sql_statements: 生成的SQL语句
        
    Returns:
        格式化的提示词
    """
    return SQL_COMPLETENESS_CHECK_PROMPT.format(
        caller=caller,
        code_meta=code_meta,
        orm_code=orm_code,
        sql_statements=sql_statements
    ) 