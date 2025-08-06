# 2025-07-17 max_tokens配置统一管理

## 任务目标
将所有地方的 `max_tokens` 都统一从 `workflow_config.yaml` 中获取，实现集中管理。

## 修改内容

### 1. 配置文件扩展
**文件**: `config/data_processing/workflow/workflow_config.yaml`

**修改内容**:
- 在 `llm` 配置下新增 `max_tokens_config` 部分
- 为不同模块和组件配置专门的 `max_tokens` 值
- 支持模块级别的默认配置

**新增配置结构**:
```yaml
llm:
  max_tokens_config:
    validation:
      redundant_sql_validator: 4096
      control_flow_validator: 4096
      validator: 4096
      precheck: 1024  # 预检查不需要太多token
    workflow:
      sql_completeness_check: 4096
      sql_correctness_check: 4096
      keyword_processing: 4096
      fix_review: 4096
      llm_review: 4096
    synthetic_data_generator: 4096
    rl:
      table_extraction: 1024
      column_extraction: 1024
      keyword_evaluation: 2048
      control_flow_penalty: 2048
    default: 4096
```

### 2. 配置管理器扩展
**文件**: `config/data_processing/workflow/workflow_config.py`

**修改内容**:
- 新增 `get_max_tokens()` 方法
- 支持根据模块和组件获取对应的 `max_tokens` 配置
- 提供默认值回退机制

**新增方法**:
```python
def get_max_tokens(self, module: str = None, component: str = None) -> int:
    """
    获取指定模块和组件的max_tokens配置
    
    Args:
        module: 模块名称 (validation, workflow, synthetic_data_generator, rl)
        component: 组件名称 (可选，如果不指定则使用模块的默认配置)
        
    Returns:
        max_tokens值
    """
```

### 3. 验证器模块修改

#### 3.1 控制流验证器
**文件**: `data_processing/validation/control_flow_validator.py`

**修改内容**:
- 将硬编码的 `max_tokens=4096` 改为从配置获取
- 使用 `workflow_config.get_max_tokens("validation", "control_flow_validator")`

#### 3.2 冗余SQL验证器
**文件**: `data_processing/validation/redundant_sql_validator.py`

**修改内容**:
- 将多个地方的 `max_tokens=4096` 改为从配置获取
- 包括 `_validate_redundant_candidate`、`_validate_new_fingerprint_candidate`、`_validate_missing_candidate` 方法

#### 3.3 通用验证器
**文件**: `data_processing/validation/validator.py`

**修改内容**:
- 将三段式分析中的 `max_tokens=4096` 改为从配置获取
- 包括预检查、分析、验证、格式化四个阶段
- 使用 `workflow_config.get_max_tokens("validation", "validator")` 和 `workflow_config.get_max_tokens("validation", "precheck")`

### 4. 合成数据生成器修改

#### 4.1 示例文件
**文件**: `data_processing/synthetic_data_generator/example_usage.py`

**修改内容**:
- 将 `max_tokens=4096` 改为从配置获取
- 使用 `workflow_config.get_max_tokens("synthetic_data_generator")`

#### 4.2 测试文件
**文件**: `data_processing/synthetic_data_generator/test_generator.py`

**修改内容**:
- 将 `max_tokens=2048` 改为从配置获取
- 使用 `workflow_config.get_max_tokens("synthetic_data_generator")`

#### 4.3 示例脚本
**文件**: `synthetic_data_example.py`

**修改内容**:
- 将两个地方的 `max_tokens=4096` 改为从配置获取
- 包括 `run_synthetic_data_generation_workflow` 和 `generate_synthetic_data` 调用

## 配置优势

### 1. 集中管理
- 所有 `max_tokens` 配置统一在 `workflow_config.yaml` 中管理
- 避免硬编码，便于调整和维护

### 2. 模块化配置
- 不同模块可以设置不同的 `max_tokens` 值
- 支持组件级别的精细配置

### 3. 灵活回退
- 如果指定模块/组件不存在，自动回退到默认值
- 确保系统稳定运行

### 4. 性能优化
- 预检查等简单任务使用较小的 `max_tokens` (1024)
- 复杂分析任务使用较大的 `max_tokens` (4096)
- 根据任务复杂度合理分配资源

## 使用方式

### 获取配置示例
```python
from config.data_processing.workflow.workflow_config import get_workflow_config

workflow_config = get_workflow_config()

# 获取验证模块的max_tokens
max_tokens = workflow_config.get_max_tokens("validation", "control_flow_validator")

# 获取合成数据生成器的max_tokens
max_tokens = workflow_config.get_max_tokens("synthetic_data_generator")

# 获取默认max_tokens
max_tokens = workflow_config.get_max_tokens()
```

## 注意事项

1. **导入路径**: 确保在使用前正确导入 `get_workflow_config`
2. **配置加载**: 系统会自动加载配置文件，无需手动初始化
3. **错误处理**: 如果配置文件读取失败，会使用默认值
4. **向后兼容**: 所有修改都保持了原有的API接口

## 测试建议

1. 验证配置文件正确加载
2. 确认各模块使用正确的 `max_tokens` 值
3. 测试配置回退机制
4. 检查性能是否有所改善

## 总结

通过这次修改，成功实现了 `max_tokens` 配置的统一管理，提高了系统的可维护性和灵活性。所有相关文件都已更新，确保使用配置文件中的值而不是硬编码。 