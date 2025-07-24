# 数据集查看器

一个基于FastAPI的Web应用，用于直观展示和搜索数据集内容。现已集成到主Web服务器中，与模型评估报告查看功能统一部署。

## 功能特性

- **多格式支持**: 支持多种JSON格式的数据文件
- **智能搜索**: 根据文件名和ORM代码内容进行搜索
- **数据过滤**: 按SQL类型、控制流等条件过滤记录
- **统计摘要**: 自动生成数据集统计信息
- **导出功能**: 支持导出HTML和JSON格式的报告
- **响应式设计**: 美观的Bootstrap界面，支持移动端

## 快速开始

### 1. 启动集成Web服务器

```bash
python run_dataset_viewer.py
```

或者直接启动主服务器：

```bash
python web_server/main.py
```

### 2. 访问应用

- **主仪表盘**: http://localhost:8000/
- **数据集查看器**: http://localhost:8000/dataset_viewer
- **API文档**: http://localhost:8000/docs

### 3. 使用数据集查看器

1. 在主页点击"数据集查看器"卡片
2. 默认会读取 `datasets/claude_output` 路径下的JSON文件
3. 可以通过URL参数指定其他路径：`/dataset_viewer?path=your/data/path`

## 支持的JSON格式

应用支持以下JSON格式：

1. **记录列表格式**:
```json
[
  {"orm_code": "...", "sql_statement_list": [...]},
  {"orm_code": "...", "sql_statement_list": [...]}
]
```

2. **包装格式**:
```json
{
  "records": [
    {"orm_code": "...", "sql_statement_list": [...]}
  ]
}
```

3. **数据格式**:
```json
{
  "data": [
    {"orm_code": "...", "sql_statement_list": [...]}
  ]
}
```

4. **单记录格式**:
```json
{
  "orm_code": "...",
  "sql_statement_list": [...]
}
```

## 主要功能

### 数据摘要
- 文件数量和总记录数
- 包含SQL的记录数量
- 参数依赖和控制流统计
- 平均SQL变体数量

### 搜索和过滤
- **文件名搜索**: 根据JSON文件名搜索
- **内容搜索**: 在ORM代码中搜索关键词
- **SQL类型过滤**: 筛选包含特定SQL类型的记录
- **控制流过滤**: 筛选包含switch/if等控制流的记录

### 数据展示
- **文件列表**: 显示所有JSON文件及其统计信息
- **详细记录**: 展示每条记录的完整信息
- **代码元数据**: 格式化显示代码位置和属性信息
- **SQL变体**: 展示参数依赖SQL的所有变体

### 导出功能
- **HTML导出**: 生成包含样式的HTML报告
- **JSON导出**: 导出过滤后的JSON数据

## API接口

### 获取数据集信息
```
GET /api/dataset_info?path=datasets/claude_output
```

返回数据集的基本信息，包括文件列表和统计信息。

## 技术架构

- **后端**: FastAPI (集成到main.py)
- **模板引擎**: Jinja2
- **前端**: Bootstrap 5 + JavaScript
- **数据格式**: JSON
- **编码**: UTF-8

## 文件结构

```
web_server/
├── main.py                 # 集成Web服务器主文件
├── templates/
│   ├── dashboard.html      # 主仪表盘
│   ├── dataset_viewer.html # 数据集查看器页面
│   ├── error.html         # 错误页面
│   └── ...               # 其他模板文件
├── static/                # 静态文件目录
└── ...

run_dataset_viewer.py      # 启动脚本
README_dataset_viewer.md   # 本文档
```

## 开发说明

### 添加新的数据格式支持

在 `main.py` 的 `dataset_viewer` 函数中添加新的数据格式解析逻辑：

```python
# 在数据格式检测部分添加新格式
elif isinstance(file_data, dict) and 'new_format' in file_data:
    records = file_data['new_format']
```

### 自定义过滤器

在模板中添加新的Jinja2过滤器：

```python
def custom_filter(value):
    # 自定义处理逻辑
    return processed_value

templates.env.filters["custom"] = custom_filter
```

## 故障排除

### 常见问题

1. **数据路径不存在**
   - 确保指定的数据目录存在
   - 检查路径权限

2. **JSON解析错误**
   - 确保JSON文件格式正确
   - 检查文件编码是否为UTF-8

3. **模板渲染错误**
   - 确保所有模板文件存在
   - 检查模板语法

### 日志查看

应用会输出详细的日志信息，包括：
- 文件读取状态
- 数据解析过程
- 错误信息

## 更新日志

### v1.0.0 (当前版本)
- ✅ 集成到主Web服务器
- ✅ 支持多种JSON格式
- ✅ 完整的搜索和过滤功能
- ✅ 响应式Web界面
- ✅ API接口支持
- ✅ 导出功能

## 贡献

欢迎提交Issue和Pull Request来改进这个工具！ 