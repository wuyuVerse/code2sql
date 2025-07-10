# 模型评估系统使用说明

## 概述

本评估系统用于对训练好的ORM到SQL转换模型进行全面评估，包括推理质量、SQL有效性、指纹匹配等多个维度的分析。

## 文件结构

```
model/evaluation/
├── README.md                           # 使用说明文档
└── fingerprint_eval/                   # 指纹评估模块
    ├── data/                           # 评估数据
    │   ├── eval_data.json              # 验证集数据
    │   └── cbs_528_final.pkl           # 官方指纹库
    ├── scripts/                        # 评估脚本
    │   ├── run_evaluation.py           # 主要评估脚本
    │   ├── evaluation_report_generator.py # 评估报告生成器
    │   ├── model_evaluator.py          # 模型评估器
    │   └── run_quick_evaluation.sh     # 快速评估脚本
    └── results/                        # 评估结果目录
        └── YYYYMMDD_HHMMSS_evaluation/ # 按时间戳组织的结果
            ├── evaluation_results_*.json    # 详细结果
            ├── evaluation_summary_*.json    # 统计摘要
            └── reports/                     # 可视化报告
                ├── evaluation_report_*.html # HTML报告
                └── detailed_analysis_*.json # 详细分析

config/evaluation/
└── model_evaluation_config.yaml       # 评估配置文件

# 根目录脚本
run_fingerprint_evaluation.sh          # 指纹评估启动脚本（推荐使用）
```

## 快速开始

### 🚀 推荐使用方式：根目录脚本

**从项目根目录运行**，使用新的指纹评估脚本：

```bash
# 快速测试评估（10个样本）
./run_fingerprint_evaluation.sh

# 指定模型路径
./run_fingerprint_evaluation.sh --model saves/your-model-path

# 完整评估（所有样本）
./run_fingerprint_evaluation.sh --mode full

# 自定义配置文件
./run_fingerprint_evaluation.sh --config config/evaluation/custom_config.yaml
```

**特性:**
- ✅ 自动创建带时间戳的结果目录
- ✅ 从项目根目录运行，路径简单
- ✅ 自动生成评估报告
- ✅ 支持测试模式和完整模式

### 1. 基本使用示例

```bash
# 测试模式评估（推荐开始）
./run_fingerprint_evaluation.sh --mode test

# 完整模式评估
./run_fingerprint_evaluation.sh --mode full --model saves/qwen3-14b-ft-20250709_171410
```

### 2. 高级使用

#### 直接使用Python脚本

```bash
# 自定义配置评估
python3 model/evaluation/fingerprint_eval/scripts/run_evaluation.py \
    --config config/evaluation/model_evaluation_config.yaml

# 单独生成报告
python3 model/evaluation/fingerprint_eval/scripts/evaluation_report_generator.py \
    --results model/evaluation/fingerprint_eval/results/20250710_123456_evaluation/evaluation_results_*.json \
    --output_dir model/evaluation/fingerprint_eval/results/20250710_123456_evaluation/reports
```

## 配置说明

### 评估配置文件 (`config/evaluation/model_evaluation_config.yaml`)

```yaml
# 模型配置
model_config:
  model_path: "saves/qwen3-14b-ft-20250709_171410"  # 您的模型路径
  template: "qwen"
  finetuning_type: "full"

# 数据配置
data_config:
  eval_data_path: "model/evaluation/fingerprint_eval/data/eval_data.json"
  fingerprint_cache_path: "model/evaluation/fingerprint_eval/data/cbs_528_final.pkl"
  max_samples: null  # null=全部样本，数字=限制样本数

# 推理配置
inference_config:
  batch_size: 1
  cutoff_len: 2048
  generate_config:
    max_new_tokens: 512
    temperature: 0.1
    top_p: 0.9
    do_sample: false

# 输出配置
output_config:
  output_dir: "model/evaluation/fingerprint_eval/results"  # 自动创建时间戳子目录
  result_prefix: "qwen3_evaluation"

# 调试配置
debug_config:
  test_mode: false      # true=测试模式（10个样本）
  test_samples: 10
```

## 评估指标说明

### 主要指标

1. **推理成功率** (`inference_success_rate`)
   - 模型成功生成响应的样本比例
   - 衡量模型基本推理能力

2. **有效SQL生成率** (`valid_sql_rate`)
   - 生成有效SQL语句的样本比例
   - 衡量模型SQL生成质量

3. **指纹匹配率** (`fingerprint_match_rate`)
   - SQL指纹匹配已知模式的样本比例
   - 衡量生成SQL的实用性

### 详细指标

- **SQL有效性比率** (`sql_validity_rate`): SQL语句级别的有效性
- **SQL匹配比率** (`sql_match_rate`): SQL语句级别的指纹匹配率
- **解析错误率** (`parse_error_rate`): 响应解析失败的比例

## 输出文件说明

### 🗂️ 结果目录结构

每次评估都会创建独立的时间戳目录：
```
model/evaluation/fingerprint_eval/results/
└── 20250710_143022_evaluation/         # 时间戳_evaluation
    ├── evaluation_results_*.json       # 详细评估结果
    ├── evaluation_summary_*.json       # 统计摘要
    └── reports/                        # 可视化报告
        ├── evaluation_report_*.html    # HTML交互式报告
        └── detailed_analysis_*.json    # 详细分析数据
```

### 📊 报告文件说明

- **HTML报告**: 包含可视化图表、统计分析、代表性示例
- **JSON详细分析**: 机器可读的完整分析数据
- **评估结果**: 每个样本的详细推理和验证结果
- **统计摘要**: 核心指标的汇总统计

## 使用示例

### 示例1: 第一次使用（推荐）

```bash
# 从项目根目录运行，使用测试模式快速验证
cd /path/to/your/code2sql/project
./run_fingerprint_evaluation.sh --mode test

# 查看结果
ls -la model/evaluation/fingerprint_eval/results/*/reports/
```

### 示例2: 完整评估

```bash
# 对指定模型进行完整评估
./run_fingerprint_evaluation.sh \
    --model saves/qwen3-14b-ft-20250709_171410 \
    --mode full
```

### 示例3: 批量测试不同模型

```bash
# 测试多个模型
for model in saves/model_v1 saves/model_v2 saves/model_v3; do
    echo "评估模型: $model"
    ./run_fingerprint_evaluation.sh --model $model --mode test
done
```

### 示例4: 查看和比较结果

```bash
# 列出所有评估结果
ls -la model/evaluation/fingerprint_eval/results/

# 查看最新的HTML报告
latest_dir=$(ls -t model/evaluation/fingerprint_eval/results/*/reports/ | head -1 | cut -d'/' -f1-6)
echo "最新报告目录: $latest_dir"
ls -la "$latest_dir"/*.html
```

## 故障排除

### 常见问题

1. **脚本权限问题**
   ```bash
   chmod +x run_fingerprint_evaluation.sh
   ```

2. **路径错误**
   - 确保在项目根目录运行脚本
   - 检查模型路径是否相对于根目录

3. **模型加载失败**
   - 检查模型路径是否正确
   - 确认模型文件完整性
   - 检查GPU内存是否足够

4. **指纹文件不存在**
   - 新的指纹文件位于: `model/evaluation/fingerprint_eval/data/cbs_528_final.pkl`
   - 如果缺失，请检查文件是否正确移动

### 调试技巧

1. **启用测试模式进行快速验证**
   ```bash
   ./run_fingerprint_evaluation.sh --mode test
   ```

2. **查看配置文件验证路径**
   ```bash
   cat config/evaluation/model_evaluation_config.yaml
   ```

3. **手动检查关键文件**
   ```bash
   ls -la model/evaluation/fingerprint_eval/data/
   ls -la model/evaluation/fingerprint_eval/scripts/
   ls -la config/evaluation/
   ```

## 版本说明

- **v2.0**: 重构目录结构，支持多种评估方法，改进用户体验
- **v1.0**: 初始版本，基础指纹评估功能

## 下一步计划

- 添加更多评估维度（语义相似度、业务逻辑正确性等）
- 支持模型对比评估
- 集成到CI/CD流程
- 添加评估结果的趋势分析

