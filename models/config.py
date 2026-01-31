from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ConfigType(str, Enum):
    """Типы конфигураций системы."""
    SYSTEM = "system"
    LLM_PROVIDER = "llm_provider"
    DB_PROVIDER = "db_provider"
    TOOL = "tool"
    SKILL = "skill"


class Config(BaseModel):
    """Основная модель конфигурации."""
    profile: str = Field(default="dev", description="Профиль конфигурации")
    log_level: str = Field(default="INFO", description="Уровень логирования")
    log_dir: str = Field(default="logs", description="Директория для логов")
    agent: Dict[str, Any] = Field(
        default={"max_steps": 10, "default_strategy": "react_composable"},
        description="Параметры агента"
    )
    llm_providers: Dict[str, Any] = Field(default_factory=dict, description="LLM провайдеры")
    db_providers: Dict[str, Any] = Field(default_factory=dict, description="DB провайдеры")
    custom_settings: Dict[str, Any] = Field(default_factory=dict, description="Пользовательские настройки")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Метаданные конфигурации")


class LLMProviderConfig(BaseModel):
    """Конфигурация LLM провайдера."""
    type: str
    model_path: str = ""
    enabled: bool = True
    parameters: Dict[str, Any] = Field(default_factory=dict)
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DBProviderConfig(BaseModel):
    """Конфигурация DB провайдера."""
    type: str
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = ""
    database: str
    enabled: bool = True
    parameters: Dict[str, Any] = Field(default_factory=dict)
    connection_string: Optional[str] = None
    ssl_enabled: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)