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
SPECIAL_KEYWORD_PROMPT = """
严格按照以下指导判断SQL语句是否与下列特殊关键词相关。判断时，重点考虑关键词的功能和用法，不是单纯看关键词的出现，而是要根据其在代码中的作用来判定是否与生成的SQL语句有关：

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
    "Save",
    "CreateOrUpdate"
]

### 关键词详细解释和说明：

1. **Preload**：
    - **无Preload**：只执行主表的基本SELECT查询。
    - **有Preload**：会生成额外的JOIN查询或子查询来加载关联数据。
    - 示例：`Preload("Profile")` 会生成主查询和关联表查询来避免N+1查询问题。

2. **Transaction**：
    - **无Transaction**：每个数据库操作都是独立的事务。
    - **有Transaction**：会生成`BEGIN TRANSACTION`、`COMMIT`/`ROLLBACK`，确保操作作为一个原子操作执行。
    - 示例：`BEGIN; INSERT INTO users...; COMMIT;`

3. **Scopes**：
    - **无Scopes**：查询是直接的，不会自动应用任何过滤器。
    - **有Scopes**：多个查询条件通过`db.Scopes()`封装，生成更简洁、模块化的SQL。
    - 示例：`db.Scopes(activeUsers, withAge(30)).Find(&users);`

4. **FindInBatches**：
    - **无FindInBatches**：一次性加载所有记录，可能导致内存溢出。
    - **有FindInBatches**：数据按批次加载（例如每次查询100条），避免一次性加载所有数据。
    - 示例：`SELECT * FROM users LIMIT 100 OFFSET 0;`

5. **FirstOrInit**：
    - **无FirstOrInit**：查询不到结果时需要手动创建一个新对象。
    - **有FirstOrInit**：查询不到结果时，返回一个初始化对象，不立即执行插入。
    - 示例：`db.FirstOrInit(&user, "name = ?", "John");`

6. **Association**：
    - **无Association**：查询仅返回主表数据。
    - **有Association**：会自动处理关联模型的查询，生成JOIN或嵌套SELECT语句。
    - 示例：`db.Model(user).Association("Profile").Find(&profile);`

7. **Locking**：
    - **无Locking**：查询正常执行。
    - **有Locking**：生成带有`FOR UPDATE`的锁定查询，确保数据一致性。
    - 示例：`SELECT * FROM users WHERE id = 1 FOR UPDATE;`

8. **Pluck**：
    - **无Pluck**：查询所有字段，返回完整模型。
    - **有Pluck**：仅查询指定字段，减少数据量。
    - 示例：`db.Model(&users).Pluck("name", &names);`

9. **Callbacks**：
    - **无Callbacks**：直接执行SQL操作。
    - **有Callbacks**：执行SQL前后会触发钩子（如BeforeCreate、AfterUpdate）。
    - 示例：`db.Callback().Create().After("gorm:create").Register("after_create_hook", afterCreateHook);`

10. **AutoMigrate**：
    - **无AutoMigrate**：表结构需要手动同步。
    - **有AutoMigrate**：自动生成`CREATE TABLE`或`ALTER TABLE`等SQL语句。
    - 示例：`db.AutoMigrate(&User{});`

11. **ForeignKey**：
    - **无ForeignKey**：需要手动定义外键关系。
    - **有ForeignKey**：自动生成外键约束。
    - 示例：`CREATE TABLE profiles (user_id INT, FOREIGN KEY (user_id) REFERENCES users(id));`

12. **References**：
    - **无References**：外键关系手动定义。
    - **有References**：生成外键约束的SQL。
    - 示例：`CREATE TABLE orders (user_id INT REFERENCES users(id));`

13. **NamedQuery**：
    - **无NamedQuery**：查询是动态生成的。
    - **有NamedQuery**：可以为查询命名以便复用，避免重复编写SQL。
    - 示例：`db.NamedQuery("active_users", db.Where("active = ?", true));`

14. **Hooks**：
    - **无Hooks**：直接执行SQL操作。
    - **有Hooks**：执行SQL操作前后触发钩子方法。
    - 示例：`BeforeCreate`，`AfterUpdate`等钩子。

15. **NamedParameters**：
    - **无NamedParameters**：使用位置绑定传递参数。
    - **有NamedParameters**：使用命名参数传递SQL语句的参数。
    - 示例：`db.Where("name = :name", map[string]interface{}{"name": "John"}).Find(&users);`

16. **Save**：
    - **无Save**：手动判断是否进行`INSERT`或`UPDATE`。
    - **有Save**：根据对象状态自动选择`INSERT`或`UPDATE`。
    - 示例：`db.Save(&user);`

17. **CreateOrUpdate**：
    - **无CreateOrUpdate**：手动判断插入或更新。
    - **有CreateOrUpdate**：自动判断是插入新记录还是更新现有记录。
    - 示例：`db.CreateOrUpdate(&user);`

###
必须真的有该功能，不能进行随便判断推测

### 输出要求：
- 如果SQL语句与上述关键词有关，返回这些关键词的列表，格式为JSON，如：`["Preload", "Transaction"]`
- 如果SQL语句与上述关键词没有任何关系，仅输出：`"No"`

**分析材料：**
- 调用者：{caller}
- 元数据：{code_meta}
- GORM代码：{orm_code}
- 生成的SQL语句：{sql_statements}
"""