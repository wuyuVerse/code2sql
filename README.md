# Code2SQL

基于大语言模型的代码到SQL转换与分析工具

## 项目简介

Code2SQL 是一个智能化的代码分析系统，专门用于将 ORM 代码转换为相应的 SQL 语句，并提供深度的代码分析能力。该项目集成了多种大语言模型服务，提供了完整的数据处理流水线和模型微调环境。

## 核心功能

- **ORM 代码分析**：自动识别和解析各种 ORM 框架代码
- **SQL 生成**：将 ORM 代码转换为等价的 SQL 语句
- **智能验证**：多阶段验证确保转换结果的准确性
- **模型微调**：支持 Qwen3-14B 等模型的全量微调
- **数据清洗**：自动化的数据清洗和预处理流水线
- **实验跟踪**：集成 SwanLab 进行训练过程监控

## 项目结构

```
code2sql/
├── config/                     # 配置文件
│   ├── llm/                   # LLM服务配置
│   ├── validation/            # 验证配置
│   └── training/              # 训练配置
├── data_processing/           # 数据处理模块
│   ├── cleaning/              # 数据清洗
│   ├── workflow/              # 工作流管理
│   └── validation/            # 数据验证
├── sql_generation/            # SQL生成模块
│   ├── optimization/          # SQL优化
│   └── validation/            # SQL验证
├── model/                     # 模型相关
│   ├── training/              # 训练脚本
│   └── LLaMA-Factory/         # 微调框架
├── workflows/                 # 工作流定义
│   ├── ai_judgment/           # AI判断工作流
│   └── data_cleaning/         # 数据清洗工作流
├── utils/                     # 工具函数
├── tests/                     # 测试文件
├── datasets/                  # 数据集
└── docs/                      # 文档
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

2. 创建虚拟环境
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
uv sync
# 或
pip install -e .
```

### 配置

1. 配置 LLM 服务
```bash
cp config/llm/servers.yaml.example config/llm/servers.yaml
# 编辑配置文件，添加你的 API 密钥
```

2. 配置训练环境（可选）
```bash
# 如果需要进行模型微调
cd model/LLaMA-Factory
source .venv/bin/activate
```

## 使用方法

### 代码分析与 SQL 生成

```python
from data_processing import DataAnalyzer

# 初始化分析器
analyzer = DataAnalyzer()

# 分析代码文件
result = analyzer.analyze_code_file("path/to/orm_code.py")

# 获取生成的 SQL
sql_statements = result.get_sql_statements()
```

### 批量数据处理

```bash
# 运行数据清洗工作流
python workflows/data_cleaning/run_cleaning.py

# 运行重新分析流程
python rerun_analysis.py
```

### 模型微调

```bash
# 启动 SwanLab 服务器
swanlab server start

# 运行全量微调
cd model
./training/train_qwen3_ft.py
```

## 主要模块

### 数据处理 (data_processing)

- **DataReader**: 读取和解析各种格式的数据文件
- **DataAnalyzer**: 分析代码结构和生成 SQL
- **Validation**: 多阶段验证系统

### SQL 生成 (sql_generation)

- **优化模块**: SQL 语句优化和性能提升
- **验证模块**: SQL 语法和逻辑验证

### 模型训练 (model)

- **训练脚本**: 支持 Qwen3-14B 全量微调
- **配置管理**: YAML 格式的训练配置
- **实验跟踪**: SwanLab 集成

### 工作流 (workflows)

- **AI 判断**: 基于 LLM 的智能判断流程
- **数据清洗**: 自动化数据预处理

## 配置说明

### LLM 服务配置

```yaml
# config/llm/servers.yaml
servers:
  openai:
    base_url: "https://api.openai.com/v1"
    api_key: "your-api-key"
  
  custom:
    base_url: "http://localhost:8000/v1"
    api_key: "local-key"
```

### 训练配置

```yaml
# config/training/qwen/qwen3_14b_ft.yaml
model_name: qwen3_14b
model_path: /path/to/model
finetuning_type: full
learning_rate: 5e-5
num_train_epochs: 3.0
```

## 开发指南

### 添加新的 LLM 服务

1. 在 `config/llm/servers.yaml` 中添加服务配置
2. 在 `utils/llm_client.py` 中实现客户端逻辑
3. 更新相关的提示词模板

### 扩展数据处理流程

1. 在 `data_processing/` 下创建新的处理模块
2. 实现相应的接口和验证逻辑
3. 更新工作流配置

### 自定义验证规则

1. 编辑 `config/validation/validation_prompts.py`
2. 添加新的验证提示词
3. 在验证流程中集成新规则

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_data_processing.py

# 生成覆盖率报告
pytest --cov=data_processing
```

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/new-feature`)
3. 提交更改 (`git commit -am 'Add new feature'`)
4. 推送到分支 (`git push origin feature/new-feature`)
5. 创建 Pull Request

## 许可证

[MIT License](LICENSE)

## 更新日志

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
