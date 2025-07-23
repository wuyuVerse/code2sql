# -*- coding: utf-8 -*-
"""ORM → SQL 提示词模板 - 优化版本"""

PROMPT_TEMPLATE =     """
请基于以下分析要求，直接输出GORM代码对应的SQL语句JSON格式结果：

**首要判断：SQL生成有效性**
在开始分析前，请判断给定的ORM代码是否真的会生成SQL语句：
- 代码必须包含实际的数据库操作方法（Find、Create、Update、Delete、Count、First等）
- 仅有查询构建方法（Where、Select、Join等）而没有执行方法的代码不会生成SQL
- 被完全注释掉的代码不会生成SQL
- 如果代码不会生成任何SQL，请返回：`NO_SQL_GENERATE: 具体原因`，格式要求见下
- 如果信息不完整但可推测，请返回：`LACK_INFORMATION: 缺失描述，推测SQL，`，格式要求见下
- 如果代码中没有传入任何筛选条件，即 `filter` 为空，没有caller，或者 `Where` 条件没有被动态构建（没有筛选条件），即没有任何过滤条件的查询。这种情况下SQL的WHERE子句应该为 `WHERE ?``

**分析步骤：**

1. **识别表名和字段映射**：
   **表名获取路径：**
   · 元数据中TableName()函数显式返回值
   · 配置文件中的表名映射（const常量、type定义等）
   · 代码中直接写出的表名（如Table("user_info")）- 必须原样保留
   · 默认命名规则：驼峰转下划线，严禁自动复数化（UserInfo→user_info，不是user_infos）
   
   **字段名获取路径：**
   · 结构体tag中的column标签（如gorm:"column:user_name"）
   · 配置文件中的字段映射
   · 代码中直接写出的字段名（如Where("user_id = ?")）- 必须原样保留
   · 默认转换：驼峰转下划线（UserName→user_name）

2. **处理JOIN操作和表别名**：
   · 主表使用简短别名，关联表使用有意义的别名
   · SELECT、WHERE、ORDER BY、GROUP BY、HAVING子句中的所有列名必须带表别名前缀
   · ON条件必须使用完整格式：`ON t1.foreign_key = t2.primary_key`
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

边界条件格式：
- 信息缺失：[{{"type": "LACK_INFORMATION", "variants": [{{"scenario": "缺失描述", "sql": "推测SQL"}}]}}]
- 缺少筛选条件的情况：[{{"type": "LACK_INFORMATION", "variants": [{{"scenario": "缺少筛选条件", "sql": "WHERE子句为WHERE ？的sql语句"}}]}}]
- 无法生成：[{{"type": "NO_SQL_GENERATE", "variants": [{{"scenario": "原因", "sql": ""}}]}}]

**严格要求：**
- 仅输出纯JSON数组，无其他文字说明
- SQL语句必须完整可执行，以分号结尾
- 不含省略号、占位符或解释性文本
- 参数使用问号(?)表示
- 只有SQL结构不同才视为不同变体

**分析目标代码：**
函数名称：{function_name}
ORM代码：{code_value}
调用者：{caller}
元数据：{code_meta_data_str}

**注意**：严格遵循高级工程师规范，仅基于实际代码进行分析，不添加推测性内容。

**特别强调：**
- 在`LACK_INFORMATION`的场景中，请尽可能生成多个SQL变体。对于缺失信息的场景，`scenario`字段应该详细描述缺失的具体内容（如表名、字段名等）。如果能推测出不同的SQL结构变体（例如，表名推测、字段映射推测），请尽量生成多个变体。
"""