"""
This module contains the prompt template for processing keyword data with an LLM.
"""

KEYWORD_PROCESSING_PROMPT = """
请基于以下分析要求，直接输出GORM代码对应的SQL语句JSON格式结果：

**首要判断：SQL生成有效性**
在开始分析前，请判断给定的ORM代码是否真的会生成SQL语句：
- 代码必须包含实际的数据库操作方法（Find、Create、Update、Delete、Count、First等）
- 仅有查询构建方法（Where、Select、Join等）而没有执行方法的代码不会生成SQL
- 如果代码不会生成任何SQL，请返回空数组[]

**分析步骤：**
1. **识别表名和字段映射**：
   **表名优先级：**
   · 元数据中TableName()函数显式返回值（最高优先级）
   · 配置文件中的表名映射（const常量、type定义等）
   · 代码中直接写出的表名（如Table("user_info")）- 必须原样保留
   · 默认命名规则：驼峰转下划线，严禁自动复数化（UserInfo→user_info，不是user_infos）
   
   **字段名优先级：**
   · 结构体tag中的column标签（如gorm:"column:user_name"）
   · 配置文件中的字段映射
   · 代码中直接写出的字段名（如Where("user_id = ?")）- 必须原样保留
   · 默认转换：驼峰转下划线（UserName→user_name）

2. **处理JOIN操作和表别名**：
   · 主表使用简短别名，关联表使用有意义的别名
   · SELECT、WHERE、ORDER BY、GROUP BY、HAVING子句中的所有列名必须带表别名前缀
   · ON条件必须使用完整格式：ON t1.foreign_key = t2.primary_key
   · 确保避免列名歧义，保持表别名一致性

3. **枚举所有可能的SQL结构**：
   · **忽略注释代码**：完全忽略//和/* */注释中的所有代码
   · 分析所有可能的WHERE条件字段组合（单条件、多条件AND、OR组合）
   · 考虑动态条件构建（if判断、循环遍历、switch分支等）
   · 识别GORM特性影响（关联查询、作用域、事务、软删/硬删等）
   · DELETE操作需包含显式Where条件＋主键自动条件

4. **上下文约束分析**（根据提供的信息进行）：
   · 如果提供调用者信息：只分析当前调用者触发的执行路径，排除其他独立路径
   · 如果提供被调用者信息：考虑内部调用可能产生的额外SQL操作
   · 如果信息不完整：基于现有信息进行最佳推断，但不臆测缺失部分

5. **生成标准SQL语句**：
   · 确保SQL完整可执行，参数用?占位
   · 不含省略号或[其他字段]等占位符
   · 每条SQL以分号结尾
   · 同结构SQL仅保留一条代表性模板

**元数据信息：**
以下元数据可能包含表名和列名的关键信息，请根据实际提供的内容进行分析：

· **表结构信息**（如提供）：数据库表的定义、字段标签、主键信息等，用于确定准确的表名和字段名
· **调用者代码**（如提供）：上层函数的调用方式、传递参数、业务条件等，用于限定执行路径
· **被调用者代码**（如提供）：内部调用的函数、嵌套查询、回调方法等，可能产生额外SQL

**注意**：1.如果某类信息未提供，请基于ORM代码本身和已有信息进行分析，不要为缺失信息创造假设。
        2.充分考虑特殊格式关键词，包括且仅包括"Preload","Transaction","Scopes","FindInBatches","FirstOrInit","Association","Locking","Pluck","Callbacks","AutoMigrate","ForeignKey","References","NamedQuery","Hooks","NamedParameters","save","createorupdate")

特殊关键词的解释和说明：

1. Preload
没有使用Preload：只会执行基本的SELECT查询，查询主表的数据。

使用Preload：会在生成的SQL中添加额外的JOIN查询或子查询，以便一次性加载关联数据。

例如，假设有User与Profile的关联，Preload("Profile")会生成类似于：


SELECT * FROM users;
SELECT * FROM profiles WHERE user_id IN (1, 2, 3, ...);
这有助于解决N+1查询问题，一次性加载关联数据，避免多次查询。

2. Transaction
没有使用Transaction：每个数据库操作（如INSERT、UPDATE、DELETE）都是单独的事务。

使用Transaction：会生成**BEGIN TRANSACTION和COMMIT/ROLLBACK**语句，确保操作作为一个原子操作执行。

例如：


BEGIN;
INSERT INTO users (name, age) VALUES ('John', 30);
UPDATE accounts SET balance = balance - 100 WHERE user_id = 1;
COMMIT;
这种方式可以确保数据库操作的一致性，如果某个操作失败，可以回滚整个事务。

3. Scopes
没有使用Scopes：每次查询都是直接编写的SQL，通常包括基本的SELECT和WHERE。

使用Scopes：会将多个查询条件和逻辑封装成可重用的查询块。GORM将会在生成SQL时根据Scopes链式添加条件。

例如：
db.Scopes(activeUsers, withAge(30)).Find(&users);
生成的SQL可能是：


SELECT * FROM users WHERE active = TRUE AND age = 30;
Scopes使得代码更加简洁和模块化，避免重复编写相同的查询条件。

4. FindInBatches
没有使用FindInBatches：所有记录会一次性加载到内存中，可能会导致内存溢出或性能问题。

使用FindInBatches：生成多个SELECT查询，每次只加载一部分数据（如每次查询100条），避免一次性加载所有数据。

例如：


SELECT * FROM users LIMIT 100 OFFSET 0;
SELECT * FROM users LIMIT 100 OFFSET 100;
这种方式有助于节省内存并提升性能，特别是当数据量非常大时。

5. FirstOrInit
没有使用FirstOrInit：如果查询不到结果，可能需要手动创建一个新的对象。

使用FirstOrInit：生成一个SELECT查询，如果没有找到结果，则初始化一个新的对象，不会立即执行INSERT操作。

例如：


SELECT * FROM users WHERE name = 'John';
如果没有结果，它会返回一个空的用户对象，而不是执行插入操作。

6. Association
没有使用Association：基本的查询语句，只会返回主表的数据。

使用Association：会自动处理关联模型的数据查询，生成多表JOIN或嵌套的SELECT语句。

例如，在User和Profile模型之间有关联时，使用db.Model(user).Association("Profile").Find(&profiles)会生成：


SELECT * FROM profiles WHERE user_id = ?;
7. Locking
没有使用Locking：查询会正常执行，不涉及锁定。

使用Locking：生成带有FOR UPDATE或类似锁定语句的SQL，确保数据在事务中的一致性。

例如：


SELECT * FROM users WHERE id = 1 FOR UPDATE;
这可以防止并发事务对同一数据的操作产生冲突。

8. Pluck
没有使用Pluck：会查询整个模型的所有字段，并返回完整的对象。

使用Pluck：只会查询指定的字段，减少返回的数据量。

例如：


SELECT name FROM users;
9. Callbacks
没有使用Callbacks：每次操作都会直接生成和执行SQL。

使用Callbacks：在执行SQL之前或之后，会触发钩子函数（如BeforeCreate、AfterUpdate等），这些钩子不会直接改变SQL，但可以在应用层进行额外操作（如验证、日志记录等）。

10. AutoMigrate
没有使用AutoMigrate：需要手动编写CREATE TABLE或ALTER TABLE语句来同步数据库结构。

使用AutoMigrate：会自动生成CREATE TABLE、ALTER TABLE等SQL语句，确保数据库表结构与模型同步。

例如：


CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(255), age INT);
11. ForeignKey
没有使用ForeignKey：表的外键关系需要手动在SQL中定义。

使用ForeignKey：GORM会自动在生成的CREATE TABLE语句中包含外键约束。

例如：


CREATE TABLE profiles (
    id INT PRIMARY KEY,
    user_id INT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
12. References
没有使用References：外键关系手动定义。

使用References：生成的SQL会包含引用约束。

例如：

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT REFERENCES users(id)
);
13. NamedQuery
没有使用NamedQuery：所有查询是动态生成的，无法重用。

使用NamedQuery：可以为查询命名，从而使查询在不同地方复用，避免重复编写SQL。

14. Hooks
没有使用Hooks：只有直接的SQL操作。

使用Hooks：在执行SQL操作前后执行钩子方法，如BeforeCreate、AfterUpdate等。

15. NamedParameters
没有使用NamedParameters：SQL语句中的参数通常是通过位置绑定。

使用NamedParameters：SQL语句中的参数通过命名方式传递，增加了SQL的可读性和灵活性。

例如：


SELECT * FROM users WHERE name = :name;
16. Save
没有使用Save：根据是否存在判断进行INSERT或UPDATE。

使用Save：根据对象的状态自动选择是进行INSERT还是UPDATE，生成相应的SQL。

17. CreateOrUpdate
没有使用CreateOrUpdate：手动判断是否插入或更新。

使用CreateOrUpdate：GORM会自动判断是否插入新记录或更新现有记录。

例如，INSERT INTO users ... 或 UPDATE users SET ... WHERE id = ?.


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