"""
Модуль конфигурации системы.

ЕДИНАЯ КОНФИГУРАЦИЯ - AppConfig:
- Объединяет все системы конфигурации (LLM, БД, логирование, компоненты)
- Авто-обнаружение через ResourceDiscovery (заменяет registry.yaml)
- Устраняет дублирование (5+ систем → 1)

УДАЛЕНО (заменено на AppConfig):
- ConfigLoader
- DynamicConfigManager
- RegistryLoader
- SystemConfig (устарел, используется AppConfig)
"""
import os
from typing import Optional
from pathlib import Path

from core.config.app_config import AppConfig, LLMProviderConfig, DBProviderConfig, LoggingConfig
from core.config.component_config import ComponentConfig
from core.config.agent_config import AgentConfig


def get_config(profile: Optional[str] = None, data_dir: str = "data") -> AppConfig:
    """
    Получение конфигурации приложения через авто-обнаружение.
    
    ЗАМЕНЯЕТ:
    - ConfigLoader.load()
    - registry.yaml парсинг
    
    ARGS:
    - profile: профиль (prod/sandbox/dev), по умолчанию из APP_PROFILE или 'prod'
    - data_dir: директория данных
    
    RETURNS:
    - AppConfig: единая конфигурация приложения
    """
    profile = profile or os.getenv("APP_PROFILE") or "prod"
    
    # Авто-обнаружение ресурсов через файловую систему
    return AppConfig.from_discovery(profile=profile, data_dir=data_dir)


def create_minimal_config(
    profile: str = "dev",
    model_path: Optional[str] = None,
    data_dir: str = "data"
) -> AppConfig:
    """
    Создание минимальной конфигурации для тестов/отладки.
    
    ARGS:
    - profile: профиль
    - model_path: путь к модели (опционально)
    - data_dir: директория данных
    
    RETURNS:
    - AppConfig: минимальная конфигурация
    """
    llm_params = {
        "model_path": model_path or "models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "n_ctx": 512
    }
    
    return AppConfig(
        config_id="minimal_config",
        profile=profile,
        debug=True,
        log_level="DEBUG",
        log_dir="logs/dev",
        data_dir=data_dir,
        llm_providers={
            "default": LLMProviderConfig(
                provider_type="llama_cpp",
                model_name="tinyllama",
                parameters=llm_params,
                enabled=True
            )
        },
        max_steps=10,
        max_retries=3,
        temperature=0.2,
    )


__all__ = [
    # Основная конфигурация
    'AppConfig',
    'get_config',
    'create_minimal_config',
    
    # Встроенные конфигурации
    'LLMProviderConfig',
    'DBProviderConfig',
    'LoggingConfig',
    
    # Конфигурация компонентов
    'ComponentConfig',
    
    # Конфигурация агента
    'AgentConfig',
]
