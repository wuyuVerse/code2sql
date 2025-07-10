"""
GORM特殊关键字检测的配置文件
包含17个特殊关键字及对应的LLM提示模板
"""

# 17个特殊GORM关键字及其说明
SPECIAL_KEYWORDS = [
    "Preload",
    "Transaction",
    "Scopes",
    "FindInBatches",
    "FirstOrInit",
    "Association",
    "Locking",
    "Pluck",
    "Callbacks",
    "AutoMigrate",
    "ForeignKey",
    "References",
    "NamedQuery",
    "Hooks",
    "NamedParameters",
    "save",
    "createorupdate"
]

# LLM判断提示模板
SPECIAL_KEYWORD_PROMPT = """严格按照请判断SQL语句不完善的原因是否与下列特殊关键词有关，不是说关键词出现了就一定有关，要根据关键词的用法去判断：

[
    "Preload",
    "Transaction",
    "Scopes",
    "FindInBatches",
    "FirstOrInit",
    "Association",
    "Locking",
    "Pluck",
    "Callbacks",
    "AutoMigrate",
    "ForeignKey",
    "References",
    "NamedQuery",
    "Hooks",
    "NamedParameters",
    "save",
    "createorupdate"
]

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


输出要求
- 如果SQL语句与一个或几个上述关键词有关，返回这些关键词的列表的json格式，如["Preload","Transaction"]
- 不要输出分析结果，仅输出关键词列表
- 如果SQL语句与上述关键词没有任何关系，仅输出"No"

**分析材料：**
调用者：{caller}
元数据：{code_meta}
GORM代码：{orm_code}
生成的SQL语句：{sql_statements}""" 