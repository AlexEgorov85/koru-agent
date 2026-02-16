"""
Модели конфигурации для системы агента.
СООТВЕТСТВУЕТ Pydantic V2 и современным стандартам.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum
import yaml


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
        # Преобразуем пути в абсолютные
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


class LLMProviderConfig(BaseModel):
    """Конфигурация LLM провайдера"""
    model_config = ConfigDict(validate_assignment=True)

    provider_type: str = Field(default="llama_cpp", description="Тип провайдера (vllm, llama_cpp, openai)")
    model_name: str = Field(default="qwen-4b", description="Название модели")
    parameters: Dict[str, Any] = Field(default={}, description="Параметры провайдера")
    enabled: bool = Field(default=True, description="Включен ли провайдер")
    fallback_providers: List[str] = Field(default_factory=list, description="Резервные провайдеры")
    # Поддержка обратной совместимости
    type_provider: Optional[str] = Field(default=None, description="Устаревшее поле, используйте provider_type")

    def __init__(self, **data):
        # Обратная совместимость: если type_provider задан, но provider_type нет, используем type_provider
        if 'type_provider' in data and 'provider_type' not in data:
            data['provider_type'] = data['type_provider']
        super().__init__(**data)

    @field_validator('provider_type')
    @classmethod
    def validate_provider_type(cls, v):
        valid_types = ['vllm', 'llama_cpp', 'openai', 'anthropic', 'gemini']
        if v.lower() not in valid_types:
            raise ValueError(f"Неподдерживаемый тип LLM провайдера: {v}. Допустимые значения: {valid_types}")
        return v.lower()

    def get_full_model_path(self) -> str:
        """Получение полного пути к модели из параметров конфигурации"""
        model_path = self.parameters.get("model_path", "")
        if model_path and not os.path.isabs(model_path):
            return os.path.join(os.getcwd(), model_path)
        return model_path


class DBProviderConfig(BaseModel):
    """Конфигурация базы данных"""
    model_config = ConfigDict(validate_assignment=True)

    provider_type: str = Field(default="postgres", description="Тип провайдера")
    enabled: bool = Field(default=True, description="Включена ли база данных")
    parameters: Dict[str, Any] = Field(default={}, description="Параметры провайдера")
    # Поддержка обратной совместимости
    type_provider: Optional[str] = Field(default=None, description="Устаревшее поле, используйте provider_type")

    def __init__(self, **data):
        # Обратная совместимость: если type_provider задан, но provider_type нет, используем type_provider
        if 'type_provider' in data and 'provider_type' not in data:
            data['provider_type'] = data['type_provider']
        super().__init__(**data)


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
    """Конфигурация реестра с явным объявлением типов компонентов"""
    model_config = ConfigDict(validate_assignment=True, extra='allow')

    profile: str = Field(..., description="Имя профиля (prod, dev, sandbox)")

    # НОВАЯ СЕКЦИЯ: Явное объявление типов компонентов
    capability_types: Dict[str, ComponentType] = Field(
        default_factory=dict,
        description="Явное маппирование capability → тип компонента"
    )

    active_prompts: Dict[str, str] = Field(
        default_factory=dict,
        description="capability → версия"
    )

    active_contracts: Dict[str, Any] = Field(
        default_factory=dict,
        description="capability.direction → версия или сложная структура"
    )

    # Конфигурации компонентов
    services: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации сервисов")
    skills: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации навыков")
    tools: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации инструментов")
    strategies: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации стратегий")
    behaviors: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации поведений")

    @field_validator('capability_types')
    @classmethod
    def validate_capability_format(cls, v):
        """Проверяем формат capability: должен содержать точку"""
        for cap in v.keys():
            # Теперь разрешаем capability без точки для обратной совместимости
            # Но рекомендуем использовать формат с точкой
            pass
        return v


from .agent_config import AgentConfig

class SystemConfig(BaseModelConfig):
    """Корневая конфигурация системы"""
    # Конфигурация LLM провайдеров
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict, description="LLM провайдеры")

    # Конфигурация БД
    db_providers: Dict[str, DBProviderConfig] = Field(default_factory=dict, description="Базы данных")

    # Конфигурация навыков
    skills: Dict[str, SkillConfig] = Field(default_factory=dict, description="Навыки системы")

    # Конфигурация инструментов
    tools: Dict[str, ToolConfig] = Field(default_factory=dict, description="Инструменты системы")

    # Параметры агента
    agent: Dict[str, Any] = Field(
        default={
            "max_steps": 10,
            "max_retries": 3,
            "temperature": 0.2,
            "default_strategy": "react"
        },
        description="Параметры агента"
    )

    # Агентная конфигурация (для предзагрузки промптов и контрактов)
    agent_config: Optional[AgentConfig] = Field(default=None, description="Конфигурация агента для предзагрузки ресурсов")

    # Безопасность
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Параметры безопасности")

    # Дополнительные настройки
    providers: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные провайдеры")

    @property
    def primary_llm(self) -> Optional[LLMProviderConfig]:
        """Получение основного LLM провайдера"""
        for name, provider in self.llm_providers.items():
            if provider.enabled:
                return provider
        return None

    @property
    def default_db(self) -> Optional[DBProviderConfig]:
        """Получение основной базы данных"""
        for name, db in self.db_providers.items():
            if db.enabled:
                return db
        return None

    @field_validator('agent')
    @classmethod
    def validate_agent_params(cls, v):
        """Валидация параметров агента"""
        if 'max_steps' in v and v['max_steps'] < 1:
            raise ValueError("max_steps должен быть больше 0")
        if 'max_retries' in v and v['max_retries'] < 0:
            raise ValueError("max_retries не может быть отрицательным")
        if 'temperature' in v and not (0.0 <= v['temperature'] <= 1.0):
            raise ValueError("temperature должно быть в диапазоне 0.0-1.0")
        return v