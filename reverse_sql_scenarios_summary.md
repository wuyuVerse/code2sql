# 反向SQL生成器 - 11种场景生成逻辑总结

## 场景概述

### ✅ **已有的场景（6种）**

1. **"if-else+caller"** ✅
   - **要求**：Caller代码中包含if-else条件判断，根据不同的条件构建不同的filter参数传递给ORM方法
   - **生成流程**：基础SQL → 基础ORM → if-else SQL变体 → if-else Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

2. **"if-else+orm"** ✅
   - **要求**：ORM方法内部包含if-else条件判断，根据不同的分支使用不同的筛选条件构建SQL查询
   - **生成流程**：基础SQL → 基础ORM → if-else SQL变体 → 重新生成包含if-else逻辑的ORM → 基本Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

3. **"switch"** ✅
   - **要求**：ORM方法使用switch条件语句来根据不同的参数值或状态构建不同的SQL查询条件
   - **生成流程**：基础SQL → 基础ORM → switch SQL变体 → switch Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

4. **"dynamic_query"** ✅
   - **要求**：处理动态传入的多个条件，生成多条条件结合的SQL查询
   - **生成流程**：基础SQL → 基础ORM → 动态SQL变体 → 动态Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

5. **"fixed_params"** ✅
   - **要求**：固定条件查询，包含固定参数和动态参数的不同组合
   - **生成流程**：基础SQL → 基础ORM → 固定参数SQL变体 → 固定参数Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

6. **"complex_control"** ✅
   - **要求**：复杂控制流，包含多层嵌套的if-else或switch结构
   - **生成流程**：基础SQL → 基础ORM → 复杂控制流SQL变体 → 复杂控制流Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

### ✅ **新增的场景（5种）**

7. **"if-else+switch_mixed"** ✅
   - **要求**：ORM方法同时使用if-else和switch-case混合控制流，根据多个条件参数选择不同的数据库操作策略
   - **生成流程**：基础SQL → 基础ORM → if-else+switch混合SQL变体 → if-else+switch混合Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

8. **"conditional_chain"** ✅
   - **要求**：ORM方法通过连续的if-else条件判断逐步构建查询条件，每个条件都可能影响最终的SQL语句
   - **生成流程**：基础SQL → 基础ORM → 条件链式SQL变体 → 条件链式Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

9. **"multi_branch_transaction"** ✅
   - **要求**：ORM方法使用复杂的条件分支控制事务处理流程，不同分支执行不同的数据库操作组合
   - **生成流程**：基础SQL → 基础ORM → 多分支事务处理SQL变体 → 多分支事务处理Caller
   - **输出格式**：`PARAM_DEPENDENT` 类型

10. **"state_machine_branch"** ✅
    - **要求**：ORM方法基于对象状态使用switch-case实现状态机逻辑，每个状态对应特定的数据库操作序列
    - **生成流程**：基础SQL → 基础ORM → 状态机式分支SQL变体 → 状态机式分支Caller
    - **输出格式**：`PARAM_DEPENDENT` 类型

11. **"conditional_meta"** ✅
    - **要求**：ORM方法使用if-else条件分支的同时依赖元数据配置，根据配置和条件双重判断执行不同操作
    - **生成流程**：基础SQL → 基础ORM → 条件分支+meta SQL变体 → 条件分支+meta Caller
    - **输出格式**：`PARAM_DEPENDENT` 类型

## 场景对比分析

### ✅ **完全覆盖的8种场景**

1. **"if-else条件查询"** ≈ **"if-else+orm"** ✅
2. **"switch-case分支"** ≈ **"switch"** ✅
3. **"嵌套if-else+chunk"** ≈ **"complex_control"** ✅
4. **"if-else+switch混合"** = **"if-else+switch_mixed"** ✅
5. **"条件链式查询"** = **"conditional_chain"** ✅
6. **"多分支事务处理"** = **"multi_branch_transaction"** ✅
7. **"状态机式分支"** = **"state_machine_branch"** ✅
8. **"条件分支+meta"** = **"conditional_meta"** ✅

### ✅ **额外支持的3种场景**

9. **"if-else+caller"** - Caller中的if-else条件判断
10. **"dynamic_query"** - 动态条件查询
11. **"fixed_params"** - 固定参数+动态参数组合

## 输出格式统一

所有11种场景都输出相同的格式：

```json
{
    "function_name": "方法名",
    "orm_code": "完整的Go ORM代码",
    "caller": "完整的Go调用者代码",
    "sql_statement_list": [
        {
            "type": "param_dependent",
            "variants": [
                {
                    "scenario": "分支描述",
                    "sql": "SQL查询语句"
                }
            ]
        }
    ],
    "sql_types": ["PARAM_DEPENDENT"],
    "sql_length_match": true,
    "code_meta_data": [...]
}
```

## 关键特性

### ✅ **并行处理**
- 支持并行生成多个案例
- 使用信号量控制并发数
- 包含重试机制

### ✅ **重试逻辑**
- 每个组件独立重试（最多3次）
- 重试间隔1-2秒
- 详细错误日志

### ✅ **格式验证**
- 所有输出都符合正向生成器格式
- 统一的SQL类型映射
- 完整的必需字段

### ✅ **场景覆盖**
- 11种场景全部支持
- 每种场景都有专门的提示词模板
- 支持不同复杂度级别

## 生成内容

### **SQL生成**
- 基础SQL：完整的"全条件查询"
- SQL变体：根据场景生成2-6个不同的变体
- 条件组合：不同的WHERE条件组合

### **ORM生成**
- 基础ORM：标准的GORM代码
- 特殊ORM：if-else+orm场景包含内部控制流
- 参数支持：动态参数传递

### **Caller生成**
- 基本Caller：简单的调用者代码
- 控制流Caller：包含if-else、switch、动态等逻辑
- 参数验证：适当的参数验证和错误处理

## 验证要点

1. **格式一致性**：输出格式与正向生成器完全一致
2. **场景完整性**：11种场景都能正确生成
3. **并行性能**：支持真正的并行处理
4. **错误恢复**：重试机制确保稳定性
5. **类型映射**：所有场景都映射到 `PARAM_DEPENDENT` 