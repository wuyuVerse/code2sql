# 合成数据生成器

用于自动生成**合成ORM数据包**的工具，这些数据包镜像真实提取样本的结构（如`full_scenario.json`中的样本）。

## 功能特点

- 🔄 **完全重构**：使用您的项目架构（LLMClient、config等）
- 🚀 **并行处理**：支持多线程并行生成，提高效率
- 🎯 **场景支持**：支持13种不同的ORM场景模式
- 📊 **统计监控**：实时显示生成进度和统计信息
- ✅ **数据验证**：自动验证生成数据的格式正确性

## 模块结构

```
data_processing/synthetic_data_generator/
├── __init__.py          # 模块初始化
├── config.py            # 配置管理
├── prompts.py           # 提示词模板
├── generator.py         # 核心生成逻辑
├── cli.py              # 命令行接口
├── test_generator.py   # 测试脚本
└── README.md           # 说明文档
```

## 使用方法

### 1. 基本使用

```bash
# 生成所有场景的数据（每个场景1个包）
python -m data_processing.synthetic_data_generator.cli

# 生成指定场景的数据
python -m data_processing.synthetic_data_generator.cli --scenario "单chunk" --count 5

# 并行模式生成
python -m data_processing.synthetic_data_generator.cli --parallel --workers 8 --count 10
```

### 2. 查看支持的场景

```bash
python -m data_processing.synthetic_data_generator.cli --list-scenarios
```

### 3. 验证生成的数据

```bash
python -m data_processing.synthetic_data_generator.cli --validate --count 3
```

### 4. 自定义配置

```bash
python -m data_processing.synthetic_data_generator.cli \
    --llm-server v3 \
    --temperature 0.8 \
    --max-tokens 4096 \
    --parallel \
    --workers 4 \
    --count 20 \
    --out my_synthetic_data.json
```

## 支持的场景

1. **对象var+chunk** - ORM方法仅依赖接收者对象的成员变量
2. **caller+global variable** - 依赖外部全局常量或变量
3. **caller+chunk** - 需要调用者传递的参数chunks
4. **caller的callee+caller** - 形成调用链的ORM方法
5. **单chunk** - 最基础的CRUD操作
6. **单chunk+meta(global var)** - 使用单一数据块和全局变量
7. **preload特殊函数** - 使用预加载功能优化关联查询
8. **association特殊函数** - 处理关联关系操作
9. **单chunk+meta(local var)** - 依赖方法内部的局部变量
10. **单chunk+meta(对象var)** - 依赖对象成员变量
11. **一度caller+chunk** - 一层调用关系
12. **二度caller+chunk** - 两层调用关系
13. **对象const+chunk** - 依赖对象常量成员变量

## 配置说明

### LLM服务器配置

使用您的 `config/llm/servers.yaml` 配置文件：

```yaml
servers:
  v3:
    host: "212.64.90.3"
    port: 8081
    model_name: "v3"
    timeout: 45
    max_retries: 3
    api_key_env: "V3_API_KEY"
```

### 环境变量

```bash
export V3_API_KEY="your-api-key-here"
export R1_API_KEY="your-api-key-here"
```

## 输出格式

生成的数据包格式与 `full_scenario.json` 完全一致：

```json
{
  "synthetic_scenario_method_name": {
    "scenario": "场景标签",
    "code_key": "方法名",
    "code_value": "完整的Go代码",
    "sql_pattern_cnt": 1,
    "callers": [
      {
        "code_key": "调用者方法名",
        "code_value": "调用者代码"
      }
    ],
    "callees": [],
    "code_meta_data": [
      {
        "code_key": "结构体名",
        "code_value": "类型定义代码"
      }
    ]
  }
}
```

## 性能优化

### 并行模式

- 使用 `--parallel` 启用并行模式
- 使用 `--workers N` 设置worker数量（建议4-8个）
- 并行模式下自动禁用请求间延迟

### 内存优化

- 生成大量数据时建议分批处理
- 使用 `--count` 控制每批生成的数量

## 错误处理

- 自动重试失败的LLM请求
- 详细的错误日志和统计信息
- 数据验证确保输出格式正确

## 与原有代码的区别

### 架构改进

1. **使用您的LLMClient**：替代直接的OpenAI调用
2. **使用您的配置系统**：替代硬编码配置
3. **模块化设计**：分离配置、提示词、生成逻辑
4. **类型安全**：修复了原有的linter错误

### 功能保持

- ✅ 完全相同的生成逻辑
- ✅ 相同的提示词模板
- ✅ 相同的并行处理机制
- ✅ 相同的数据验证逻辑

## 测试

运行测试脚本验证模块功能：

```bash
python data_processing/synthetic_data_generator/test_generator.py
```

## 迁移指南

如果您之前使用 `make_data.py`，现在可以这样迁移：

```bash
# 旧方式
python data_processing/make_data.py --scenario "单chunk" --count 5

# 新方式
python -m data_processing.synthetic_data_generator.cli --scenario "单chunk" --count 5
```

所有参数和功能都保持一致，只是模块结构更加清晰和可维护。 