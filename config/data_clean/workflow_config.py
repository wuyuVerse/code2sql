"""
工作流配置加载器
从YAML文件加载数据清洗工作流的配置参数
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel


class ConcurrencyConfig(BaseModel):
    """并发配置"""
    sql_completeness_check: int = 50
    sql_correctness_check: int = 50
    redundant_sql_validation: int = 50
    keyword_data_processing: int = 50  # 新增关键词处理步骤的并发配置
    control_flow_validation: int = 20  # 新增控制流验证步骤的并发配置
    default: int = 50


class TimeoutConfig(BaseModel):
    """超时配置"""
    llm_request: int = 45
    session_timeout: int = 300


class RetryConfig(BaseModel):
    """重试配置"""
    max_retries: int = 1000
    retry_delay: float = 1.0


class LLMConfig(BaseModel):
    """LLM配置"""
    max_tokens: int = 300
    temperature: float = 0.0
    default_server: str = "v3"


class WorkflowConfig(BaseModel):
    """工作流配置"""
    concurrency: ConcurrencyConfig
    timeout: TimeoutConfig
    retry: RetryConfig
    llm: LLMConfig


class WorkflowConfigManager:
    """工作流配置管理器"""
    
    def __init__(self, config_file: str = "config/data_clean/workflow_config.yaml"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        # 如果是相对路径，则相对于项目根目录
        if not Path(config_file).is_absolute():
            # 获取项目根目录（从当前文件位置向上查找）
            current_dir = Path(__file__).parent.parent.parent
            self.config_file = current_dir / config_file
        else:
            self.config_file = Path(config_file)
        
        self._config: Optional[WorkflowConfig] = None
        self.load_config()
    
    def load_config(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            workflow_settings = config_data.get('workflow_settings', {})
            
            # 创建配置对象
            self._config = WorkflowConfig(
                concurrency=ConcurrencyConfig(**workflow_settings.get('concurrency', {})),
                timeout=TimeoutConfig(**workflow_settings.get('timeout', {})),
                retry=RetryConfig(**workflow_settings.get('retry', {})),
                llm=LLMConfig(**workflow_settings.get('llm', {}))
            )
            
        except FileNotFoundError:
            # 使用默认配置
            self._config = WorkflowConfig(
                concurrency=ConcurrencyConfig(),
                timeout=TimeoutConfig(),
                retry=RetryConfig(),
                llm=LLMConfig()
            )
        except Exception as e:
            raise ValueError(f"配置文件加载失败: {e}")
    
    @property
    def config(self) -> WorkflowConfig:
        """获取配置对象"""
        if self._config is None:
            self.load_config()
        # 确保配置已加载
        if self._config is None:
            raise RuntimeError("配置加载失败")
        return self._config
    
    def get_concurrency(self, step_type: str) -> int:
        """
        获取指定步骤的并发数
        
        Args:
            step_type: 步骤类型 (sql_completeness_check, sql_correctness_check, redundant_sql_validation, control_flow_validation)
            
        Returns:
            并发数
        """
        concurrency_map = {
            'sql_completeness_check': self.config.concurrency.sql_completeness_check,
            'sql_correctness_check': self.config.concurrency.sql_correctness_check,
            'redundant_sql_validation': self.config.concurrency.redundant_sql_validation,
            'keyword_data_processing': self.config.concurrency.keyword_data_processing,
            'control_flow_validation': self.config.concurrency.control_flow_validation,
        }
        return concurrency_map.get(step_type, self.config.concurrency.default)
    
    def reload_config(self) -> None:
        """重新加载配置文件"""
        self.load_config()


# 全局配置实例
_global_workflow_config = None


def get_workflow_config() -> WorkflowConfigManager:
    """获取全局工作流配置实例（单例模式）"""
    global _global_workflow_config
    if _global_workflow_config is None:
        _global_workflow_config = WorkflowConfigManager()
    return _global_workflow_config


def reload_workflow_config() -> WorkflowConfigManager:
    """重新加载全局工作流配置"""
    global _global_workflow_config
    _global_workflow_config = None
    return get_workflow_config() 