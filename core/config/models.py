"""
Модели конфигурации для системы агента.
СООТВЕТСТВУЕТ Pydantic V2 и современным стандартам.

ОБРАТНАЯ СОВМЕСТИМОСТЬ:
- LLMProviderConfig, DBProviderConfig импортируются из app_config.py
- LoggingConfig импортируется из logging_config.py
- AppConfig импортируется из app_config.py
- SystemConfig сохранён для обратной совместимости (устарел, используйте AppConfig)
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
import yaml

# Импортируем из новой единой конфигурации для обратной совместимости
from core.config.app_config import LLMProviderConfig, DBProviderConfig, AppConfig
from core.config.logging_config import LoggingConfig


class BaseModelConfig(BaseModel):
    """Базовая модель для всех конфигураций"""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    profile: str = Field(default="dev", description="Имя профиля конфигурации")
    debug: bool = Field(default=False, description="Включить режим отладки")
    log_level: str = Field(default="INFO", description="Уровень логирования")
    log_dir: str = Field(default="logs", description="Директория для логов")
    data_dir: str = Field(default="data", description="Директория для данных")

    def model_dump(self, **kwargs):
        """Дополнительная обработка для экспорта в словарь"""
        d = super().model_dump(**kwargs)
        if "log_dir" in d:
            d["log_dir"] = os.path.abspath(d["log_dir"])
        if "data_dir" in d:
            d["data_dir"] = os.path.abspath(d["data_dir"])
        return d

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Некорректный уровень логирования: {v}. Допустимые значения: {valid_levels}")
        return v.upper()


# === Классы для обратной совместимости ===
# LLMProviderConfig и DBProviderConfig теперь импортируются из app_config.py
# Здесь оставлены только классы, которые ещё используются в SystemConfig

class SkillConfig(BaseModel):
    """Конфигурация навыка"""
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Включен ли навык")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры навыка")
    priority: int = Field(default=1, description="Приоритет навыка")


class ToolConfig(BaseModel):
    """Конфигурация инструмента"""
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = Field(default=True, description="Включен ли инструмент")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры инструмента")
    dependencies: List[str] = Field(default_factory=list, description="Зависимости инструмента")


class SecurityConfig(BaseModel):
    """Конфигурация безопасности"""
    model_config = ConfigDict(validate_assignment=True)

    secrets_path: Optional[str] = Field(None, description="Путь к файлу с секретами")
    encryption_key: Optional[str] = Field(None, description="Ключ шифрования", repr=False)
    token_expiry_minutes: int = Field(default=60, description="Время жизни токена в минутах")

    def get_secrets(self) -> Dict[str, Any]:
        """Загрузка секретов из файла"""
        if not self.secrets_path:
            return {}
        try:
            with open(self.secrets_path, 'r', encoding='utf-8') as f:
                if self.secrets_path.endswith('.yaml'):
                    return yaml.safe_load(f) or {}
                elif self.secrets_path.endswith('.json'):
                    return json.load(f)
                else:
                    raise ValueError(f"Неподдерживаемый формат файла секретов: {self.secrets_path}")
        except Exception as e:
            raise ValueError(f"Ошибка загрузки секретов из {self.secrets_path}: {str(e)}")


from core.models.enums.common_enums import ComponentType


class RegistryConfig(BaseModel):
    """Конфигурация реестра с явным объявлением типов компонентов (устарел)"""
    model_config = ConfigDict(validate_assignment=True, extra='allow')

    profile: str = Field(..., description="Имя профиля (prod, dev, sandbox)")
    capability_types: Dict[str, ComponentType] = Field(default_factory=dict)
    active_prompts: Dict[str, str] = Field(default_factory=dict)
    active_contracts: Dict[str, Any] = Field(default_factory=dict)
    services: Dict[str, Any] = Field(default_factory=dict)
    skills: Dict[str, Any] = Field(default_factory=dict)
    tools: Dict[str, Any] = Field(default_factory=dict)
    strategies: Dict[str, Any] = Field(default_factory=dict)
    behaviors: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('capability_types')
    @classmethod
    def validate_capability_format(cls, v):
        for cap in v.keys():
            pass  # Разрешаем любой формат для обратной совместимости
        return v


from .agent_config import AgentConfig
from .vector_config import VectorSearchConfig


class SystemConfig(BaseModelConfig):
    """
    Корневая конфигурация системы (УСТАРЕЛА).
    
    DEPRECATED: Используйте AppConfig вместо SystemConfig.
    Сохранена для обратной совместимости со старым кодом.
    """
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)
    db_providers: Dict[str, DBProviderConfig] = Field(default_factory=dict)
    vector_search: Optional[VectorSearchConfig] = Field(default=None)
    skills: Dict[str, SkillConfig] = Field(default_factory=dict)
    tools: Dict[str, ToolConfig] = Field(default_factory=dict)
    agent: Dict[str, Any] = Field(default={"max_steps": 10, "max_retries": 3, "temperature": 0.2})
    agent_config: Optional[AgentConfig] = Field(default=None)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    providers: Dict[str, Any] = Field(default_factory=dict)
    use_unified_event_bus: bool = Field(default=False)

    @field_validator('vector_search', mode='before')
    @classmethod
    def set_default_vector_config(cls, v):
        if v is None:
            return VectorSearchConfig()
        return v

    @property
    def primary_llm(self) -> Optional[LLMProviderConfig]:
        for provider in self.llm_providers.values():
            if provider.enabled:
                return provider
        return None

    @property
    def default_db(self) -> Optional[DBProviderConfig]:
        for db in self.db_providers.values():
            if db.enabled:
                return db
        return None

    @field_validator('agent')
    @classmethod
    def validate_agent_params(cls, v):
        if 'max_steps' in v and v['max_steps'] < 1:
            raise ValueError("max_steps должен быть больше 0")
        if 'max_retries' in v and v['max_retries'] < 0:
            raise ValueError("max_retries не может быть отрицательным")
        if 'temperature' in v and not (0.0 <= v['temperature'] <= 1.0):
            raise ValueError("temperature должно быть в диапазоне 0.0-1.0")
        return v


# === Экспорт для обратной совместимости ===
__all__ = [
    'BaseModelConfig',
    'LLMProviderConfig',      # из app_config.py
    'DBProviderConfig',       # из app_config.py
    'LoggingConfig',          # из app_config.py
    'AppConfig',              # из app_config.py
    'SkillConfig',
    'ToolConfig',
    'SecurityConfig',
    'RegistryConfig',
    'SystemConfig',           # устарел
    'AgentConfig',
    'VectorSearchConfig',
]
