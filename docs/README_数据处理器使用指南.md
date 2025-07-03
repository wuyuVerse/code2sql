# Code2SQL 数据处理器使用指南

## 📁 新的文件结构设计

### 输出目录结构
```
extracted_data/
└── gorm_keywords_20250703_120407/    # 步骤名_时间戳
    ├── keyword_matched_records.json  # 主数据文件 (14MB)
    ├── extraction_statistics.json    # 统计报告
    └── by_keyword/                   # 按关键词分类
        ├── save_records.json (7.7MB)
        ├── Association_records.json (6.1MB)
        ├── Preload_records.json (1.2MB)
        ├── Transaction_records.json (911KB)
        ├── Callbacks_records.json (1.5MB)
        └── ... (其他关键词文件)
```

## 🔧 使用方法

### 基本使用
```python
from data_processing.data_reader import DataReader

# 创建数据读取器
reader = DataReader("datasets/claude_output")

# 提取GORM关键词 (推荐方法)
stats = reader.extract_gorm_keywords()

# 自定义关键词提取
custom_keywords = ["SELECT", "INSERT", "UPDATE"]
stats = reader.extract_by_keywords(custom_keywords, step_name="sql_keywords")
```

### 文件组织优势

1. **时间追溯**: 每次运行都有时间戳，便于版本管理
2. **步骤分离**: 不同处理步骤有独立文件夹
3. **批量处理**: 支持多个中间步骤的workflow

## 📊 处理结果

### 最新提取结果 (2025-07-03 12:04:07)
- **处理文件**: 86个JSON文件
- **总记录数**: 17,761条
- **匹配记录**: 1,345条 (7.57%)
- **输出位置**: `extracted_data/gorm_keywords_20250703_120407/`

### 关键词命中统计
| 关键词 | 命中次数 | 主要来源 |
|--------|----------|----------|
| save | 616 | alanoluo__eb-api |
| Association | 336 | 5-28-cbs |
| Preload | 170 | STKE__jinzhu-gorm |
| Transaction | 150 | 各项目分布 |
| Scopes | 46 | IVC相关项目 |

## 🚀 下一步workflow

### 数据处理流水线
```
datasets/claude_output/        # 原始数据
    ↓
extracted_data/
├── gorm_keywords_YYYYMMDD_HHMMSS/    # 关键词提取
├── cleaned_data_YYYYMMDD_HHMMSS/     # 数据清洗 (下一步)
├── augmented_data_YYYYMMDD_HHMMSS/   # 数据增强 (后续)
└── training_data_YYYYMMDD_HHMMSS/    # 训练数据 (最终)
```

### 支持的处理步骤
1. **关键词提取** ✅ 已完成
2. **数据清洗** (使用LLM API)
3. **数据增强** (生成更多样本)
4. **质量验证** (最终检查)

## 💡 最佳实践

### 运行环境
```bash
# 使用uv环境运行
uv run python extract_demo.py

# 或者激活环境后运行
uv shell
python extract_demo.py
```

### 模块导入修复
- 修复了`__init__.py`导入问题
- 支持按需导入，避免依赖错误
- 核心功能独立，可靠性更高

### 自定义提取
```python
# 自定义关键词和步骤名
keywords = ["gorm.DB", "db.Exec", "migrations"]
stats = reader.extract_by_keywords(
    keywords, 
    output_dir="extracted_data",
    step_name="database_operations"
)
```

## 🔍 文件说明

- **keyword_matched_records.json**: 包含所有匹配记录的完整数据
- **extraction_statistics.json**: 详细统计报告，包含频率分析
- **by_keyword/*.json**: 按关键词分类的数据，便于单独分析

## 📝 技术细节

### 关键词匹配逻辑
1. 检查 `code_meta_data` 中的 `code_value` 字段
2. 补充检查 `orm_code` 字段
3. 记录所有匹配的关键词
4. 生成详细统计报告

### 性能优化
- 批量读取所有文件
- 进度显示 (每5000条记录)
- 内存友好的数据结构
- 增量处理支持

这个改进的数据处理器现在完全符合您的需求，支持多步骤workflow，并且运行稳定！ 