"""
This module contains the prompt template for processing keyword data with an LLM.
"""

KEYWORD_PROCESSING_PROMPT = """
请基于以下分析要求，直接输出GORM代码对应的SQL语句JSON格式结果：

**首要判断：SQL生成有效性**
在开始分析前，请判断给定的ORM代码是否真的会生成SQL语句：
- 代码必须包含实际的数据库操作方法（Find、Create、Update、Delete、Count、First等）。
- 仅有查询构建方法（Where、Select、Join等）而没有执行方法的代码不会生成SQL。
- 如果代码不会生成任何SQL，请返回空数组[]。

**分析步骤：**

1. **识别表名和字段映射：**
   **表名优先级：**
   · **最高优先级**：元数据中`TableName()`函数显式返回的表名。
   · **次优先级**：配置文件中的表名映射（常量、type定义等）。
   · **低优先级**：代码中直接写出的表名（如`Table("user_info")`）- 必须原样保留。
   · **默认规则**：驼峰转下划线（UserInfo → user_info），严禁自动复数化。

   **字段名优先级：**
   · **最高优先级**：结构体tag中的`column`标签（如`gorm:"column:user_name"`）。
   · **次优先级**：配置文件中的字段映射。
   · **低优先级**：代码中直接写出的字段名（如`Where("user_id = ?")`）- 必须原样保留。
   · **默认规则**：驼峰转下划线（UserName → user_name）。

2. **处理JOIN操作和表别名：**
   - 主表使用简短别名，关联表使用有意义的别名。
   - SELECT、WHERE、ORDER BY、GROUP BY、HAVING子句中的所有列名必须带表别名前缀。
   - ON条件必须使用完整格式：`ON t1.foreign_key = t2.primary_key`。
   - 确保避免列名歧义，保持表别名一致性。

3. **枚举所有可能的SQL结构：**
   - **忽略注释代码**：完全忽略`//`和`/* */`注释中的所有代码。
   - 分析所有可能的WHERE条件字段组合（单条件、多条件AND、OR组合）。
   - 考虑动态条件构建（if判断、循环遍历、switch分支等）。
   - 识别GORM特性影响（关联查询、作用域、事务、软删/硬删等）。
   - DELETE操作需包含显式WHERE条件和主键自动条件。

4. **上下文约束分析（根据提供的信息进行）**：
   - 如果提供调用者信息：只分析当前调用者触发的执行路径，排除其他独立路径。
   - 如果提供被调用者信息：考虑内部调用可能产生的额外SQL操作。
   - 如果信息不完整：基于现有信息进行最佳推断，但不臆测缺失部分。

5. **生成标准SQL语句：**
   - 确保SQL完整可执行，参数用`?`占位。
   - 不含省略号或[其他字段]等占位符。
   - 每条SQL以分号结尾。
   - 同结构SQL仅保留一条代表性模板。

**元数据信息：**
以下元数据可能包含表名和列名的关键信息，请根据实际提供的内容进行分析：
- **表结构信息**（如提供）：数据库表的定义、字段标签、主键信息等，用于确定准确的表名和字段名。
- **调用者代码**（如提供）：上层函数的调用方式、传递参数、业务条件等，用于限定执行路径。
- **被调用者代码**（如提供）：内部调用的函数、嵌套查询、回调方法等，可能产生额外SQL。

**注意**：
1.如果某类信息未提供，请基于ORM代码本身和已有信息进行分析，不要为缺失信息创造假设。
2.充分考虑特殊格式关键词，包括且仅包括"Preload","Transaction","Scopes","FindInBatches","FirstOrInit","Association","Locking","Pluck","Callbacks","AutoMigrate","ForeignKey","References","NamedQuery","Hooks","NamedParameters","Save","CreateOrUpdate"。

### 特殊关键词的解释和说明：
1. **Preload**：
   - **无Preload**：只会执行基本的SELECT查询，查询主表数据。
   - **有Preload**：生成额外的JOIN查询或子查询来加载关联数据。
   - 示例SQL：`SELECT * FROM users; SELECT * FROM profiles WHERE user_id IN (1, 2, 3, ...);`

2. **Transaction**：
   - **无Transaction**：每个操作独立执行。
   - **有Transaction**：生成`BEGIN TRANSACTION`、`COMMIT`或`ROLLBACK`语句，确保原子操作。
   - 示例SQL：`BEGIN; INSERT INTO users ... COMMIT;`

3. **Scopes**：
   - **无Scopes**：直接编写SQL查询。
   - **有Scopes**：多个查询条件链式封装成模块，生成简洁的SQL。
   - 示例SQL：`SELECT * FROM users WHERE active = TRUE AND age = 30;`

4. **FindInBatches**：
   - **无FindInBatches**：一次性加载所有记录。
   - **有FindInBatches**：数据分批加载，减少内存使用。
   - 示例SQL：`SELECT * FROM users LIMIT 100 OFFSET 0;`

5. **FirstOrInit**：
   - **无FirstOrInit**：查询不到结果时，需要手动创建对象。
   - **有FirstOrInit**：查询不到结果时，返回初始化对象，不执行插入。
   - 示例SQL：`SELECT * FROM users WHERE name = 'John';`

6. **Association**：
   - **无Association**：只查询主表数据。
   - **有Association**：生成多表JOIN查询，自动加载关联模型数据。
   - 示例SQL：`SELECT * FROM profiles WHERE user_id = ?;`

7. **Locking**：
   - **无Locking**：查询正常执行。
   - **有Locking**：生成带有`FOR UPDATE`的锁定查询，确保数据一致性。
   - 示例SQL：`SELECT * FROM users WHERE id = 1 FOR UPDATE;`

8. **Pluck**：
   - **无Pluck**：查询所有字段，返回完整对象。
   - **有Pluck**：仅查询指定字段，减少返回的数据量。
   - 示例SQL：`SELECT name FROM users;`

9. **Callbacks**：
   - **无Callbacks**：直接执行SQL操作。
   - **有Callbacks**：在执行SQL前后触发钩子方法（如`BeforeCreate`、`AfterUpdate`）。
   - 示例SQL：无SQL变动，钩子方法在应用层触发。

10. **AutoMigrate**：
   - **无AutoMigrate**：表结构需要手动同步。
   - **有AutoMigrate**：自动生成表结构同步的SQL。
   - 示例SQL：`CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(255), age INT);`

11. **ForeignKey**：
   - **无ForeignKey**：外键关系需手动定义。
   - **有ForeignKey**：自动生成外键约束SQL。
   - 示例SQL：`CREATE TABLE profiles (id INT PRIMARY KEY, user_id INT, FOREIGN KEY (user_id) REFERENCES users(id));`

12. **References**：
   - **无References**：外键关系手动定义。
   - **有References**：生成外键引用约束SQL。
   - 示例SQL：`CREATE TABLE orders (id INT PRIMARY KEY, user_id INT REFERENCES users(id));`

13. **NamedQuery**：
   - **无NamedQuery**：查询为动态生成。
   - **有NamedQuery**：为查询命名，以便复用。
   - 示例SQL：`SELECT * FROM users WHERE active = TRUE;`

14. **Hooks**：
   - **无Hooks**：直接执行SQL操作。
   - **有Hooks**：执行SQL前后触发钩子方法。
   - 示例SQL：无SQL变动，钩子方法在应用层触发。

15. **NamedParameters**：
   - **无NamedParameters**：参数位置绑定。
   - **有NamedParameters**：使用命名参数提高SQL可读性。
   - 示例SQL：`SELECT * FROM users WHERE name = :name;`

16. **Save**：
   - **无Save**：手动判断进行`INSERT`或`UPDATE`。
   - **有Save**：自动选择`INSERT`或`UPDATE`。
   - 示例SQL：`INSERT INTO users ...` 或 `UPDATE users SET ... WHERE id = ?;`

17. **CreateOrUpdate**：
   - **无CreateOrUpdate**：手动判断插入或更新。
   - **有CreateOrUpdate**：自动判断插入新记录或更新现有记录。
   - 示例SQL：`INSERT INTO users ...` 或 `UPDATE users SET ... WHERE id = ?;`

**输出格式要求：**
输出标准JSON数组，结构如下：
[
  "固定SQL语句;",
  {
    "type": "param_dependent",
    "variants": [
      {"scenario": "条件描述", "sql": "完整SQL语句;"},
      {"scenario": "条件描述", "sql": "完整SQL语句;"}
    ]
  },
  "另一个固定SQL;"
]

**严格要求：**
- 仅输出纯JSON数组，无其他文字说明
- SQL语句必须完整可执行，以分号结尾
- 不含省略号、占位符或解释性文本
- 参数使用问号(?)表示
- 只有SQL结构不同才视为不同变体

**分析目标代码：**
函数名称：{function_name}
{orm_code}

关键词：{keyword}

调用者：{caller}
元数据：{code_meta}
**最终要求：仅输出纯JSON数组，无其他文字说明。**
"""
