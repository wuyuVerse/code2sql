# Code2SQL

基于大语言模型的代码到SQL转换与分析工具

## 项目简介

Code2SQL 是一个智能化的代码分析系统，专门用于将 ORM 代码转换为相应的 SQL 语句，并提供深度的代码分析能力。该项目集成了多种大语言模型服务，提供了完整的数据处理流水线和模型微调环境。

## 核心功能

- **数据清洗流水线**：自动化的五步数据处理工作流（数据加载→SQL清洗→关键词提取→特殊处理→数据合并）
- **智能SQL清洗**：识别并移除无效SQL，保留有效的固定SQL和参数依赖SQL变体
- **关键词提取**：基于GORM等ORM框架的智能关键词匹配和提取
- **批量重新分析**：高并发验证被标记为"<NO SQL GENERATE>"的记录
- **模型微调**：支持 Qwen3-14B 等模型的全量微调和LoRA微调
- **实验跟踪**：集成 SwanLab 进行训练过程监控

## 项目结构

```
code2sql/
├── config/                     # 配置文件
│   ├── llm/                   # LLM服务配置
│   │   ├── servers.yaml       # 服务器配置文件
│   │   └── prompts.py         # 提示词模板
│   ├── validation/            # 验证配置
│   │   ├── rerun_config.yaml  # 重新分析配置
│   │   └── validation_prompts.py # 验证提示词
│   └── training/              # 训练配置
│       └── qwen/             
│           ├── qwen3_14b_ft.yaml    # 全量微调配置
│           └── qwen3_14b_lora.yaml  # LoRA微调配置
├── data_processing/           # 数据处理核心模块
│   ├── cleaning/              # 数据清洗
│   │   └── sql_cleaner.py     # SQL清洗器
│   ├── workflow/              # 工作流管理
│   │   └── workflow_manager.py # 工作流管理器
│   ├── data_reader.py         # 数据读取器
│   ├── data_analyzer.py       # 数据分析器
│   └── validation.py          # 数据验证器
├── sql_generation/            # SQL生成模块
│   ├── optimization/          # SQL优化
│   └── validation/            # SQL验证
├── model/                     # 模型相关
│   ├── training/              # 训练脚本
│   │   └── train_qwen3_ft.py  # Qwen3全量微调脚本
│   └── LLaMA-Factory/         # 微调框架
├── utils/                     # 工具函数
│   └── llm_client.py          # LLM客户端
├── tests/                     # 测试文件
├── datasets/                  # 数据集目录
├── workflow_output/           # 工作流输出目录
├── rerun_outputs/            # 重新分析输出目录
├── sql_cleaning_demo.py      # 数据清洗演示脚本
├── rerun_analysis.py         # 批量重新分析脚本
└── docs/                     # 文档
```

## 快速开始

### 环境要求

- Python >= 3.13
- CUDA 12.x (用于GPU加速)
- 8GB+ GPU显存 (用于模型微调)

### 安装

1. 克隆项目
```bash
git clone <repository-url>
cd code2sql
```

2. 使用uv创建和管理环境（推荐）
```bash
# 安装uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 同步项目依赖
uv sync
```

或使用传统方式：
```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -e .
```

### 配置

1. **配置 LLM 服务器**
   
   编辑 `config/llm/servers.yaml` 文件：
```yaml
# LLM服务器配置文件
servers:
  v3:
    host: "43.143.249.90"
    port: 8081
    model_name: "v3"
    timeout: 45
    max_retries: 3
    api_key_env: "V3_API_KEY"
    default_api_key: "your-api-key-here"
    
  r1:
    host: "111.229.79.211"
    port: 8081
    model_name: "default"
    timeout: 45
    max_retries: 3
    api_key_env: "R1_API_KEY"
    default_api_key: "your-api-key-here"
```

2. **设置环境变量（可选）**
```bash
export V3_API_KEY="your-v3-api-key"
export R1_API_KEY="your-r1-api-key"
```

3. **准备数据集**
   
   将原始数据文件放置在 `datasets/claude_output/` 目录下。

## 使用方法

### 1. 数据清洗工作流演示

运行 `sql_cleaning_demo.py` 来体验完整的数据处理流水线：

```bash
# 运行交互式演示
python sql_cleaning_demo.py

# 或直接指定模式
python sql_cleaning_demo.py 1  # 完整新架构工作流
python sql_cleaning_demo.py 2  # 逐步演示
python sql_cleaning_demo.py 3  # 测试工作流（小样本）
```

**演示模式说明**：
- **模式1**: 完整新架构工作流 - 处理全部17,761条记录，运行五步完整流程
- **模式2**: 逐步演示 - 交互式展示各处理阶段，便于理解工作流程
- **模式3**: 测试工作流 - 使用前100条记录快速测试，适合调试

**输出示例**：
```
🎉 新架构工作流执行成功!
📁 工作流目录: workflow_output/workflow_20250703_155430
📄 最终数据: workflow_output/workflow_20250703_155430/final_processed_dataset.json
📊 工作流摘要: workflow_output/workflow_20250703_155430/workflow_summary.json

📈 SQL清洗统计:
   输入记录: 17,761
   移除无效SQL: 1,245
   修改记录: 3,456

🎯 关键词提取统计:
   输入记录: 17,761
   提取记录: 1,345
   提取率: 7.57%
```

### 2. 批量重新分析

运行 `rerun_analysis.py` 来验证被标记为"<NO SQL GENERATE>"的记录：

#### 准备配置文件

编辑 `config/validation/rerun_config.yaml`：
```yaml
input_file: /path/to/your/final_processed_dataset.json
output_dir: rerun_outputs
output_filename: rerun_analysis_results.jsonl
server: v3  # 或 r1
concurrency: 200
```

#### 运行重新分析

```bash
# 使用默认配置文件
python rerun_analysis.py

# 使用自定义配置文件
python rerun_analysis.py --config-file config/validation/custom_rerun_config.yaml
```

**输出示例**：
```
找到 456 条记录需要重新分析。
重新分析进度: 100%|██████████| 456/456 [02:15<00:00,  3.37it/s]

📊 重新分析完成!
✅ 成功分析: 398 条
❌ 分析失败: 58 条
🆕 新生成SQL: 123 条
📁 结果文件: rerun_outputs/rerun_analysis_results.jsonl
```

### 3. 编程方式使用

#### 数据清洗工作流

```python
from data_processing.workflow import run_complete_workflow_from_raw_data

# 运行完整工作流
result = run_complete_workflow_from_raw_data(
    data_dir="datasets/claude_output",
    keywords=None,  # 使用GORM预定义关键词
    base_output_dir="workflow_output"
)

print(f"工作流目录: {result['workflow_directory']}")
print(f"最终数据: {result['final_data_path']}")
```

#### 逐步工作流控制

```python
from data_processing.workflow.workflow_manager import WorkflowManager

# 创建工作流管理器
workflow = WorkflowManager("my_workflow")

# 步骤1: 加载数据
load_result = workflow.load_raw_dataset("datasets/claude_output")

# 步骤2: SQL清洗
cleaning_result = workflow.run_sql_cleaning("sql_cleaning_step1")

# 步骤3: 关键词提取
extraction_result = workflow.extract_keyword_data(None, "keyword_extraction_step2")

# 步骤4: 特殊处理
processing_result = workflow.process_extracted_data("special_processing_step3")

# 步骤5: 数据合并
merge_result = workflow.merge_processed_data_back("merge_back_step4")

# 导出最终数据
final_path = workflow.export_final_data("final_processed_dataset.json")
summary_path = workflow.save_workflow_summary()

# 打印摘要
workflow.print_workflow_summary()
```

#### SQL清洗器单独使用

```python
from data_processing.cleaning.sql_cleaner import SQLCleaner

# 创建清洗器
cleaner = SQLCleaner(output_dir="cleaned_data")

# 清洗数据集
result = cleaner.clean_dataset(data, step_name="my_cleaning")

# 获取清洗摘要
summary = cleaner.get_cleaning_summary()
print(f"移除无效SQL: {summary['statistics']['invalid_sql_removed']}")
```

### 4. 模型微调

#### 启动训练环境

```bash
# 进入模型目录
cd model

# 启动 SwanLab 服务器（可选，用于实验跟踪）
swanlab server start

# 运行 Qwen3 全量微调
./training/train_qwen3_ft.py
```

#### 训练配置

编辑 `config/training/qwen/qwen3_14b_ft.yaml`：
```yaml
# 模型基本配置
model_name: qwen3_14b
model_path: /data/local_disk0/wuyu/model/qwen/Qwen3-14B
template: qwen

# 全量微调配置
finetuning_type: full
rope_scaling: linear
flash_attn: fa2

# 训练参数
learning_rate: 5e-5
num_train_epochs: 3.0
per_device_train_batch_size: 2
gradient_accumulation_steps: 8
lr_scheduler_type: cosine
warmup_ratio: 0.1
bf16: true

# 实验跟踪
use_swanlab: true
```

## 主要功能详解

### 数据清洗系统

**五步处理流程**：
1. **数据加载**: 从datasets目录读取17,761条记录
2. **SQL清洗**: 移除无效SQL（中文描述、空字符串等），保留有效SQL
3. **关键词提取**: 提取包含GORM关键词的记录（约7.57%匹配率）
4. **特殊处理**: 预留接口，支持数据增强、自动标注等
5. **数据合并**: 将处理后的数据合并回原数据集

**SQL识别能力**：
- 有效固定SQL：`INSERT INTO users (name) VALUES (?);`
- 参数依赖SQL变体：结构化的条件SQL对象
- 无效SQL：中文描述文本、空字符串等

### 批量验证系统

- **高并发处理**: 支持200并发量的异步分析
- **实时写入**: 每完成一个分析立即写入结果，避免数据丢失
- **三阶段提示词**: 分析→验证→格式化的完整流程
- **错误恢复**: 完善的异常处理和中断恢复机制

### 模型训练系统

- **全量微调**: 支持Qwen3-14B的完整参数微调
- **分布式训练**: 支持8卡GPU分布式训练
- **实验跟踪**: SwanLab集成，实时监控训练过程
- **混合精度**: bf16混合精度训练，提升训练效率

## 配置文件详解

### LLM服务器配置 (`config/llm/servers.yaml`)

```yaml
servers:
  v3:
    host: "43.143.249.90"
    port: 8081
    model_name: "v3"
    timeout: 45
    max_retries: 3
    api_key_env: "V3_API_KEY"
    default_api_key: "your-api-key-here"

defaults:
  timeout: 45
  max_retries: 3
  temperature: 0.0
  max_tokens: 2048
```

### 重新分析配置 (`config/validation/rerun_config.yaml`)

```yaml
input_file: /path/to/final_processed_dataset.json
output_dir: rerun_outputs
output_filename: rerun_analysis_results.jsonl
server: v3  # 使用的LLM服务器
concurrency: 200  # 并发数量
```

### 训练配置 (`config/training/qwen/qwen3_14b_ft.yaml`)

```yaml
# 模型基本配置
model_name: qwen3_14b
model_path: /data/local_disk0/wuyu/model/qwen/Qwen3-14B
template: qwen

# 全量微调配置
finetuning_type: full
rope_scaling: linear
flash_attn: fa2

# 训练参数
learning_rate: 5e-5
num_train_epochs: 3.0
per_device_train_batch_size: 2
gradient_accumulation_steps: 8
lr_scheduler_type: cosine
warmup_ratio: 0.1
bf16: true

# 实验跟踪
use_swanlab: true
```

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_keyword_extraction.py

# 生成覆盖率报告
pytest --cov=data_processing tests/
```

## 故障排除

### 常见问题

1. **导入错误**: `"RerunValidator" is unknown import symbol`
   ```bash
   # 确保项目根目录在Python路径中
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **文件路径错误**: 
   ```bash
   # 检查数据目录是否存在
   ls datasets/claude_output/
   ```

3. **配置文件缺失**:
   ```bash
   # 检查配置文件
   ls config/llm/servers.yaml
   ls config/validation/rerun_config.yaml
   ```

4. **内存不足**:
   ```python
   # 使用测试模式处理小样本
   python sql_cleaning_demo.py 3
   ```

### 调试技巧

- 使用测试工作流（模式3）进行快速调试
- 检查workflow_output目录下的详细日志
- 启用详细日志：`export PYTHONPATH="${PYTHONPATH}:$(pwd)"`

## 性能指标

- **数据处理能力**: 17,761条记录，处理速度1,000条/秒
- **清洗准确性**: 三种SQL类型准确识别，7.57%的GORM关键词匹配率
- **并发能力**: 支持200并发异步处理
- **训练支持**: 8卡分布式训练，bf16混合精度

## 开发指南

### 添加新的数据处理步骤

1. 在 `data_processing/workflow/workflow_manager.py` 中添加新方法
2. 在工作流中调用新步骤
3. 更新相关测试

### 扩展SQL清洗规则

1. 编辑 `data_processing/cleaning/sql_cleaner.py`
2. 修改 `sql_keywords` 或 `sql_patterns`
3. 添加自定义验证逻辑

### 自定义提示词模板

1. 编辑 `config/llm/prompts.py` 或 `config/validation/validation_prompts.py`
2. 更新相关的格式化函数
3. 测试新提示词的效果

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/new-feature`)
3. 提交更改 (`git commit -am 'Add new feature'`)
4. 推送到分支 (`git push origin feature/new-feature`)
5. 创建 Pull Request

## 许可证

[MIT License](LICENSE)

## 更新日志

### v1.0.0 (2025-07-03)
- ✅ 完整的五步数据清洗工作流
- ✅ 智能SQL清洗和中文字符检测
- ✅ 高并发批量重新分析功能
- ✅ Qwen3-14B全量微调环境
- ✅ SwanLab实验跟踪集成
- ✅ 完善的配置管理和错误处理

### v0.1.0
- 初始版本发布
- 基础的代码到SQL转换功能
- LLM服务集成
- 数据处理流水线

## 支持

如有问题或建议，请在 [Issues](issues) 中提出。

## 致谢

- [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) - 模型微调框架
- [SwanLab](https://swanlab.cn/) - 实验跟踪平台
- [uv](https://github.com/astral-sh/uv) - 现代Python包管理工具
