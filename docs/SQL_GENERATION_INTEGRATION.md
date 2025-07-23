# SQL生成功能集成说明

## 概述

本项目已将 `get_sql.py` 中的SQL生成功能集成到 `run_synthetic_data_generation_workflow` 工作流中，实现了从合成数据生成到SQL生成的完整流程。

## 功能特性

### 1. 完整的端到端流程
- **合成数据生成**: 根据指定场景生成ORM代码和调用者数据
- **SQL生成**: 基于生成的合成数据自动生成对应的SQL语句
- **验证和格式化**: 对生成的SQL进行验证和格式化处理

### 2. 灵活的配置选项
- 支持自定义场景列表
- 可配置并发数量
- 支持数据验证
- 可选的SQL生成步骤

### 3. 异步并发处理
- 合成数据生成支持并行处理
- SQL生成支持高并发请求
- 自动错误重试机制

## 使用方法

### 基本使用

```python
import asyncio
from data_processing.workflow.workflow_manager import run_synthetic_data_generation_workflow

async def main():
    result = await run_synthetic_data_generation_workflow(
        base_output_dir="workflow_output",
        scenarios=["单chunk", "caller+chunk"],
        count_per_scenario=2,
        llm_server="http://212.64.90.3:8081/v1",
        generate_sql=True,  # 启用SQL生成
        sql_concurrency=20  # SQL生成并发数
    )
    
    print(f"工作流完成: {result}")

asyncio.run(main())
```

### 高级配置

```python
result = await run_synthetic_data_generation_workflow(
    base_output_dir="custom_workflow",
    scenarios=None,  # 使用所有可用场景
    count_per_scenario=3,
    llm_server="http://212.64.90.3:8081/v1",
    temperature=0.8,
    max_tokens=4096,
    parallel=True,
    max_workers=8,
    validate=True,
    generate_sql=True,
    sql_concurrency=50
)
```

## 参数说明

### 合成数据生成参数
- `scenarios`: 要生成的场景列表，None表示使用所有场景
- `count_per_scenario`: 每个场景生成的数据包数量
- `llm_server`: LLM服务器地址
- `temperature`: LLM温度参数，控制创造性
- `max_tokens`: 最大token数
- `parallel`: 是否启用并行模式
- `max_workers`: 并行worker数量
- `validate`: 是否验证生成的数据

### SQL生成参数
- `generate_sql`: 是否启用SQL生成步骤
- `sql_concurrency`: SQL生成的并发数量

## 输出结构

工作流执行完成后，会在指定目录下生成以下文件：

```
workflow_output/
├── synthetic_data_generation/
│   ├── synthetic_data_generation_step.json    # 生成的合成数据
│   └── synthetic_data_generation_step_validation.json  # 验证结果
├── sql_generation/
│   └── sql_generation_step.json              # 生成的SQL数据
└── workflow_summary.json                     # 工作流摘要
```

## 返回结果

工作流返回的结果包含以下信息：

```python
{
    'workflow_completed': True,
    'workflow_directory': 'workflow_output',
    'summary_path': 'workflow_output/workflow_summary.json',
    'generation_result': {
        'total_packs_generated': 10,
        'valid_packs': 9,
        'invalid_packs': 1,
        'validation_rate': 90.0
    },
    'sql_generation_result': {
        'valid_count': 25,
        'invalid_count': 5,
        'total_count': 30,
        'success_rate': 83.3
    }
}
```

## 测试脚本

### 运行集成测试
```bash
python test_sql_generation_integration.py
```

### 运行使用示例
```bash
python example_sql_generation_workflow.py
```

## 错误处理

### 常见错误及解决方案

1. **导入错误**
   - 确保项目路径正确设置
   - 检查依赖模块是否正确安装

2. **LLM服务器连接失败**
   - 检查服务器地址是否正确
   - 确认网络连接正常

3. **文件路径错误**
   - 确保输出目录有写入权限
   - 检查输入文件是否存在

4. **并发限制**
   - 根据服务器性能调整并发数量
   - 避免过高的并发导致服务器过载

## 性能优化建议

1. **并发设置**
   - 合成数据生成: `max_workers=4-8`
   - SQL生成: `sql_concurrency=20-50`

2. **场景选择**
   - 测试时使用少量场景
   - 生产环境可使用所有场景

3. **验证设置**
   - 开发阶段启用验证
   - 生产环境可选择性禁用

## 扩展功能

### 自定义SQL生成逻辑
可以通过修改 `get_sql.py` 中的函数来自定义SQL生成逻辑：

```python
# 在workflow_manager.py中调用自定义函数
from data_processing.synthetic_data_generator.get_sql import process_json_file_async

# 自定义处理逻辑
result = await process_json_file_async(
    input_file="custom_input.json",
    output_file="custom_output.json",
    concurrency=30
)
```

### 添加新的验证规则
可以在 `get_sql.py` 中添加新的验证函数：

```python
def custom_sql_validator(sql_statement):
    # 自定义验证逻辑
    return True

# 在process_json_file_async中使用
```

## 注意事项

1. **资源使用**
   - SQL生成过程会消耗大量LLM API调用
   - 建议在非高峰期运行

2. **数据质量**
   - 生成的SQL需要人工验证
   - 建议对关键场景进行手动检查

3. **版本兼容性**
   - 确保所有依赖模块版本兼容
   - 定期更新依赖包

## 更新日志

- **v1.0.0**: 初始集成版本
  - 支持基本的合成数据生成 + SQL生成流程
  - 支持异步并发处理
  - 添加了完整的错误处理机制 