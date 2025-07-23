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


class FormatValidationModuleConfig(BaseModel):
    """格式验证模块配置"""
    max_retries: int = 3
    retry_delay: float = 1.0


class FormatValidationConfig(BaseModel):
    """格式验证配置"""
    max_retries: int
    retry_delay: float
    enabled: bool
    modules: Dict[str, dict] = {}


class LLMServerConfig(BaseModel):
    """LLM服务器配置"""
    redundant_sql_validator: str = "v3"
    control_flow_validator: str = "v3"
    validator: str = "v3"
    sql_completeness_check: str = "v3"
    sql_correctness_check: str = "v3"
    keyword_processing: str = "v3"
    fix_review: str = "v3"
    llm_review: str = "v3"
    synthetic_data_generator: str = "v3"
    default: str = "v3"


class LLMConfig(BaseModel):
    """LLM配置"""
    max_tokens: int = 300
    temperature: float = 0.0
    default_server: str = "v3"
    servers: Optional[LLMServerConfig] = None


class WorkflowConfig(BaseModel):
    """工作流配置"""
    concurrency: ConcurrencyConfig
    timeout: TimeoutConfig
    retry: RetryConfig
    format_validation: FormatValidationConfig
    llm: LLMConfig


class WorkflowConfigManager:
    """工作流配置管理器"""
    
    def __init__(self, config_file: str = "config/data_processing/workflow/workflow_config.yaml"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        # 如果是相对路径，则相对于项目根目录
        if not Path(config_file).is_absolute():
            # 获取项目根目录（从当前文件位置向上查找）
            current_dir = Path(__file__).parent.parent.parent.parent
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
            
            # 处理LLM配置
            llm_settings = workflow_settings.get('llm', {})
            servers_config = llm_settings.get('servers', {})
            
            # 处理格式验证配置
            format_validation_settings = dict(workflow_settings.get('format_validation', {}))
            modules = format_validation_settings.pop('modules', {})
            format_validation_config = FormatValidationConfig(**format_validation_settings)
            format_validation_config.modules = modules
            
            # 创建配置对象
            self._config = WorkflowConfig(
                concurrency=ConcurrencyConfig(**workflow_settings.get('concurrency', {})),
                timeout=TimeoutConfig(**workflow_settings.get('timeout', {})),
                retry=RetryConfig(**workflow_settings.get('retry', {})),
                format_validation=format_validation_config,
                llm=LLMConfig(
                    max_tokens=llm_settings.get('max_tokens', 300),
                    temperature=llm_settings.get('temperature', 0.0),
                    default_server=llm_settings.get('default_server', 'v3'),
                    servers=LLMServerConfig(**servers_config) if servers_config else None
                )
            )
            
        except FileNotFoundError as e:
            # 使用默认配置
            self._config = WorkflowConfig(
                concurrency=ConcurrencyConfig(),
                timeout=TimeoutConfig(),
                retry=RetryConfig(),
                format_validation=FormatValidationConfig(
                    max_retries=3,
                    retry_delay=1.0,
                    enabled=True
                ),
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
    
    def get_llm_server(self, module: str, component: str = None) -> str:
        """
        获取指定模块和组件的LLM服务器
        
        Args:
            module: 模块名称 (validation, workflow, synthetic_data_generator)
            component: 组件名称 (可选，如果不指定则使用模块的默认配置)
            
        Returns:
            LLM服务器名称
        """
        if self.config.llm.servers is None:
            return self.config.llm.default_server
        
        # 根据模块和组件获取服务器配置
        if module == "validation":
            if component == "redundant_sql_validator":
                return self.config.llm.servers.redundant_sql_validator
            elif component == "control_flow_validator":
                return self.config.llm.servers.control_flow_validator
            elif component == "validator":
                return self.config.llm.servers.validator
            else:
                return self.config.llm.servers.default
        elif module == "workflow":
            if component == "sql_completeness_check":
                return self.config.llm.servers.sql_completeness_check
            elif component == "sql_correctness_check":
                return self.config.llm.servers.sql_correctness_check
            elif component == "keyword_processing":
                return self.config.llm.servers.keyword_processing
            elif component == "fix_review":
                return self.config.llm.servers.fix_review
            elif component == "llm_review":
                return self.config.llm.servers.llm_review
            else:
                return self.config.llm.servers.default
        elif module == "synthetic_data_generator":
            return self.config.llm.servers.synthetic_data_generator
        else:
            return self.config.llm.servers.default
    
    def get_format_validation_config(self, module: str = None, component: str = None) -> Dict[str, Any]:
        """
        获取格式验证配置
        
        Args:
            module: 模块名称 (validation, workflow, synthetic_data_generator)
            component: 组件名称
            
        Returns:
            格式验证配置字典
        """
        if not self.config.format_validation.enabled:
            return {
                'enabled': False,
                'max_retries': 0,
                'retry_delay': 0.0
            }
        
        # 获取默认配置
        config = {
            'enabled': True,
            'max_retries': self.config.format_validation.max_retries,
            'retry_delay': self.config.format_validation.retry_delay
        }
        
        # 如果指定了模块和组件，尝试获取特定配置
        if module and component and self.config.format_validation.modules:
            module_config = self.config.format_validation.modules.get(module, {})
            if isinstance(module_config, dict):
                component_config = module_config.get(component, {})
                if isinstance(component_config, dict):
                    config.update({
                        'max_retries': component_config.get('max_retries', config['max_retries']),
                        'retry_delay': component_config.get('retry_delay', config['retry_delay'])
                    })
        
        return config
    
    def get_llm_config(self) -> Dict[str, Any]:
        """
        获取LLM配置参数
        
        Returns:
            LLM配置字典
        """
        return {
            'max_tokens': self.config.llm.max_tokens,
            'temperature': self.config.llm.temperature,
            'default_server': self.config.llm.default_server
        }
    
    def get_max_tokens(self, module: str = None, component: str = None) -> int:
        """
        获取指定模块和组件的max_tokens配置
        
        Args:
            module: 模块名称 (validation, workflow, synthetic_data_generator, rl)
            component: 组件名称 (可选，如果不指定则使用模块的默认配置)
            
        Returns:
            max_tokens值
        """
        # 从配置文件中读取max_tokens_config
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            workflow_settings = config_data.get('workflow_settings', {})
            llm_settings = workflow_settings.get('llm', {})
            max_tokens_config = llm_settings.get('max_tokens_config', {})
            
            # 根据模块和组件获取max_tokens
            if module and component:
                module_config = max_tokens_config.get(module, {})
                return module_config.get(component, max_tokens_config.get('default', 4096))
            elif module:
                module_config = max_tokens_config.get(module, {})
                return module_config.get('default', max_tokens_config.get('default', 4096))
            else:
                return max_tokens_config.get('default', 4096)
                
        except Exception as e:
            # 如果读取失败，返回默认值
            return self.config.llm.max_tokens
    
    def get_max_retries(self, module: str = None, component: str = None) -> int:
        """
        获取指定模块和组件的最大重试次数
        
        Args:
            module: 模块名称 (validation, workflow, synthetic_data_generator)
            component: 组件名称 (可选，如果不指定则使用模块的默认配置)
            
        Returns:
            最大重试次数
        """
        return self.config.retry.max_retries
    
    def get_retry_delay(self, module: str = None, component: str = None) -> float:
        """
        获取指定模块和组件的重试延迟
        
        Args:
            module: 模块名称 (validation, workflow, synthetic_data_generator)
            component: 组件名称 (可选，如果不指定则使用模块的默认配置)
            
        Returns:
            重试延迟（秒）
        """
        return self.config.retry.retry_delay
    
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