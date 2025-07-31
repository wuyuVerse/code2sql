# 合成数据整合脚本使用说明

## 概述

该脚本用于将 `synthetic_output` 文件夹中所有不是 `workflow_年份` 的文件夹中的 `sql_generation` 文件夹的所有 JSON 文件中的数据整合起来，加入到 `workflow_output/workflow_v{version}` 这个文件夹的 `final_processed_dataset.json` 中。

## 功能特点

- **自动版本检测**: 自动检测下一个可用的版本号
- **智能文件过滤**: 自动跳过 `workflow_年份` 格式的文件夹
- **数据合并**: 将所有符合条件的 JSON 文件数据合并到一个文件中
- **错误处理**: 完善的错误处理和日志记录
- **干运行模式**: 可以预览将要处理的文件而不实际执行

## 文件结构

```
scripts/
├── merge_synthetic_data.py      # Python主脚本
├── merge_synthetic_data.sh      # Shell包装器
└── README_merge_synthetic_data.md  # 使用说明
```

## 使用方法

### 1. 使用Shell脚本（推荐）

```bash
# 自动检测版本号
bash scripts/merge_synthetic_data.sh

# 指定版本号
bash scripts/merge_synthetic_data.sh --version 7

# 干运行模式（仅显示将要处理的文件）
bash scripts/merge_synthetic_data.sh --dry-run

# 指定输入输出目录
bash scripts/merge_synthetic_data.sh --input-dir custom_input --output-dir custom_output

# 查看帮助
bash scripts/merge_synthetic_data.sh --help
```

### 2. 直接使用Python脚本

```bash
# 自动检测版本号
python3 scripts/merge_synthetic_data.py

# 指定版本号
python3 scripts/merge_synthetic_data.py --version 7

# 干运行模式
python3 scripts/merge_synthetic_data.py --dry-run

# 指定输入输出目录
python3 scripts/merge_synthetic_data.py --input-dir custom_input --output-dir custom_output
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--version` | int | 自动检测 | 工作流版本号 |
| `--input-dir` | string | `synthetic_output` | 输入目录 |
| `--output-dir` | string | `workflow_output` | 输出目录 |
| `--dry-run` | flag | False | 仅显示将要处理的文件，不实际合并 |

## 工作流程

1. **扫描输入目录**: 遍历 `synthetic_output` 目录下的所有文件夹
2. **过滤文件夹**: 跳过 `workflow_年份` 格式的文件夹（如 `workflow_2024`）
3. **查找JSON文件**: 在每个符合条件的文件夹的 `sql_generation` 子目录中查找所有 `.json` 文件
4. **版本检测**: 自动检测 `workflow_output` 目录中现有的版本号，生成下一个版本号
5. **数据合并**: 读取所有找到的 JSON 文件，合并数据
6. **保存结果**: 将合并后的数据保存到 `workflow_output/workflow_v{version}/final_processed_dataset.json`

## 示例

### 目录结构示例

```
synthetic_output/
├── workflow_2024/                    # 会被跳过
│   └── sql_generation/
│       └── data.json
├── workflow_mutual_exclusive_conditions/  # 会被处理
│   └── sql_generation/
│       ├── output1.json
│       └── output2.json
├── workflow_if_else_callers/         # 会被处理
│   └── sql_generation/
│       └── output3.json
└── workflow_2023/                    # 会被跳过
    └── sql_generation/
        └── data.json

workflow_output/
├── workflow_v1/
│   └── final_processed_dataset.json
├── workflow_v2/
│   └── final_processed_dataset.json
└── workflow_v3/
    └── final_processed_dataset.json
```

### 执行示例

```bash
# 执行整合（自动检测到下一个版本为 v4）
bash scripts/merge_synthetic_data.sh

# 输出示例
==================================================================
合成数据整合脚本
==================================================================
项目根目录: /data/cloud_disk_1/home/wuyu/code2sql
Python脚本: /data/cloud_disk_1/home/wuyu/code2sql/scripts/merge_synthetic_data.py
输入目录: synthetic_output
输出目录: workflow_output
版本号: 自动检测
==================================================================
开始执行数据整合...
2024-07-30 21:45:23,456 - INFO - 自动检测到下一个版本号: 4
2024-07-30 21:45:23,457 - INFO - 输出目录: workflow_output/workflow_v4
2024-07-30 21:45:23,457 - INFO - 输出文件: workflow_output/workflow_v4/final_processed_dataset.json
2024-07-30 21:45:23,458 - INFO - 在 workflow_mutual_exclusive_conditions 中找到 2 个json文件
2024-07-30 21:45:23,459 - INFO - 在 workflow_if_else_callers 中找到 1 个json文件
2024-07-30 21:45:23,460 - INFO - 找到 3 个JSON文件需要处理:
2024-07-30 21:45:23,460 - INFO -   - synthetic_output/workflow_mutual_exclusive_conditions/sql_generation/output1.json
2024-07-30 21:45:23,460 - INFO -   - synthetic_output/workflow_mutual_exclusive_conditions/sql_generation/output2.json
2024-07-30 21:45:23,460 - INFO -   - synthetic_output/workflow_if_else_callers/sql_generation/output3.json
2024-07-30 21:45:23,461 - INFO - 开始处理 3 个JSON文件...
2024-07-30 21:45:23,462 - INFO - 处理文件 1/3: output1.json
2024-07-30 21:45:23,463 - INFO - 从 synthetic_output/workflow_mutual_exclusive_conditions/sql_generation/output1.json 加载了 100 条记录
2024-07-30 21:45:23,464 - INFO - 处理文件 2/3: output2.json
2024-07-30 21:45:23,465 - INFO - 从 synthetic_output/workflow_mutual_exclusive_conditions/sql_generation/output2.json 加载了 150 条记录
2024-07-30 21:45:23,466 - INFO - 处理文件 3/3: output3.json
2024-07-30 21:45:23,467 - INFO - 从 synthetic_output/workflow_if_else_callers/sql_generation/output3.json 加载了 75 条记录
2024-07-30 21:45:23,468 - INFO - 总共合并了 325 条记录
2024-07-30 21:45:23,469 - INFO - 数据已保存到: workflow_output/workflow_v4/final_processed_dataset.json
2024-07-30 21:45:23,470 - INFO - 总共保存了 325 条记录
2024-07-30 21:45:23,471 - INFO - 数据整合完成！
==================================================================
数据整合完成！
==================================================================
```

## 注意事项

1. **文件格式**: 脚本会处理 JSON 文件，支持单个对象或对象数组格式
2. **编码**: 使用 UTF-8 编码读写文件
3. **错误处理**: 如果某个文件读取失败，会记录错误但继续处理其他文件
4. **目录创建**: 如果输出目录不存在，会自动创建
5. **版本冲突**: 如果指定的版本号已存在，会覆盖现有文件

## 故障排除

### 常见问题

1. **找不到输入目录**
   ```
   错误: 输入目录不存在: synthetic_output
   ```
   解决: 确保 `synthetic_output` 目录存在

2. **没有找到JSON文件**
   ```
   未找到任何需要处理的JSON文件
   ```
   解决: 检查目录结构，确保有符合条件的文件夹和JSON文件

3. **权限错误**
   ```
   保存文件时出错: [Errno 13] Permission denied
   ```
   解决: 检查输出目录的写入权限

4. **JSON格式错误**
   ```
   加载文件 xxx.json 时出错: Expecting value: line 1 column 1 (char 0)
   ```
   解决: 检查JSON文件格式是否正确

### 调试模式

使用 `--dry-run` 参数可以预览将要处理的文件而不实际执行：

```bash
bash scripts/merge_synthetic_data.sh --dry-run
```

这将显示所有将要处理的文件列表，帮助您确认脚本的行为是否符合预期。 