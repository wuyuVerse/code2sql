# 数据集对比评估脚本使用说明

## 概述

`run_dataset_comparison.py` 是一个用于直接对比两个数据集（基准数据集和生成数据集）的脚本，无需模型推理。该脚本使用 `source_file`、`code_line`、`function_name` 三元组进行样本匹配，并生成详细的对比报告。

## 功能特点

1. **三元组匹配**：使用 `source_file`、`code_line`、`function_name` 进行精确匹配
2. **SQL指纹对比**：对SQL语句进行指纹化处理，确保对比的准确性
3. **详细报告**：生成包含一致、缺失、多余SQL的详细JSON报告
4. **网站友好**：生成的JSON格式适合在网站上渲染显示
5. **灵活输入**：支持单个文件或目录作为输入

## 使用方法

### 基本用法

```bash
python run_dataset_comparison.py \
    --config configs/dataset_comparison_config.yaml \
    --output_dir results/dataset_comparison \
    --mode full
```

### 参数说明

- `--config`: 配置文件路径（必需）
- `--output_dir`: 结果输出目录（必需）
- `--mode`: 评估模式，可选 `test` 或 `full`（默认：`full`）

### 配置文件格式

```yaml
# 数据配置
data_config:
  # 基准数据集路径（可以是文件或目录）
  baseline_data_path: "path/to/baseline/dataset.json"
  # 生成数据集路径（可以是文件或目录）
  generated_data_path: "path/to/generated/dataset.json"

# 调试配置（仅在test模式下使用）
debug_config:
  # 测试模式下处理的样本数量
  test_samples: 5
```

## 数据格式要求

### 输入数据格式

每个样本应包含以下字段：

```json
{
  "id": "unique_id",
  "source_file": "path/to/source/file.py",
  "code_line": 123,
  "function_name": "function_name",
  "orm_code": "ORM code here",
  "caller": "caller info",
  "callee": "callee info",
  "code_meta_data": [...],
  "sql_statement_list": ["SQL1", "SQL2", ...],
  // 或者使用 "sql" 字段
  "sql": ["SQL1", "SQL2", ...]
}
```

### 输出报告格式

生成的报告包含以下结构：

```json
{
  "metadata": {
    "run_timestamp": "2024-01-01T12:00:00",
    "config_file": "config.yaml",
    "evaluation_mode": "full",
    "baseline_data_path": "path/to/baseline",
    "generated_data_path": "path/to/generated",
    "total_samples": 100
  },
  "results": [
    {
      "sample_id": "unique_id",
      "source_file": "path/to/source/file.py",
      "code_line": 123,
      "function_name": "function_name",
      "orm_code": "ORM code here",
      "caller": "caller info",
      "callee": "callee info",
      "code_meta_data": [...],
      "baseline_sql": ["SQL1", "SQL2"],
      "generated_sql": ["SQL1", "SQL3"],
      "metrics": {
        "baseline_fingerprint_count": 2,
        "generated_fingerprint_count": 2,
        "common_fingerprint_count": 1,
        "missing_fingerprint_count": 1,
        "extra_fingerprint_count": 1
      },
      "fingerprints": {
        "common": ["fingerprint1"],
        "missing": ["fingerprint2"],
        "extra": ["fingerprint3"]
      }
    }
  ]
}
```

## 匹配逻辑

1. **三元组匹配**：优先使用 `source_file`、`code_line`、`function_name` 进行精确匹配
2. **ID备选**：如果三元组匹配失败，尝试使用 `id` 字段匹配
3. **跳过处理**：如果无法找到匹配的样本，记录错误信息并继续处理下一个样本

## 网站渲染支持

生成的JSON报告包含以下特性，适合在网站上渲染：

1. **结构化数据**：清晰的层次结构，便于前端解析
2. **中文字符支持**：使用 `ensure_ascii=False` 确保中文正确显示
3. **详细元数据**：包含时间戳、配置信息等便于追踪
4. **错误处理**：包含错误信息，便于调试和问题定位

## 示例

### 测试模式运行

```bash
python run_dataset_comparison.py \
    --config configs/dataset_comparison_config.yaml \
    --output_dir results/test_comparison \
    --mode test
```

### 完整模式运行

```bash
python run_dataset_comparison.py \
    --config configs/dataset_comparison_config.yaml \
    --output_dir results/full_comparison \
    --mode full
```

## 注意事项

1. 确保两个数据集中的样本具有相同的 `source_file`、`code_line`、`function_name` 三元组
2. 如果数据集较大，建议先使用 `test` 模式验证配置
3. 生成的报告文件名为 `dataset_comparative_results.json`
4. 脚本会自动创建输出目录（如果不存在） 