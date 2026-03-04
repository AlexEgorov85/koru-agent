# core/config/__init__.py
"""
Модуль конфигурации системы.

КОМПОНЕНТЫ:
- config_loader: загрузчик конфигурации из файлов
- dynamic_config: менеджер динамической конфигурации с hot-reload
- agent_config: конфигурация агента
- app_config: конфигурация приложения
- models: модели данных конфигурации
"""
import os
from typing import Optional

from core.config.models import SystemConfig
from .config_loader import ConfigLoader
from .agent_config import AgentConfig
from .dynamic_config import (
    DynamicConfigManager,
    ConfigChangeEvent,
    ConfigSnapshot,
    get_config_manager,
    create_config_manager,
    reset_config_manager,
)


def get_config(profile: Optional[str] = None, config_dir: Optional[str] = None) -> SystemConfig:
    """
    Получение конфигурации приложения

    :param profile: Профиль конфигурации (dev/staging/prod)
    :param config_dir: Директория с конфигурационными файлами
    :return: Валидированная конфигурация системы
    """
    try:
        loader = ConfigLoader(
            profile=profile or os.getenv("APP_PROFILE"),
            config_dir=config_dir or os.getenv("CONFIG_DIR")
        )
        return loader.load()
    except Exception as e:
        # Создание минимальной конфигурации для работы при ошибке загрузки
        default_config = {
            "profile": profile or "dev",
            "debug": True,
            "log_level": "DEBUG",
            "log_dir": "logs/dev",
            "data_dir": "data/dev",
            "llm_providers": {
                "fallback": {
                    "type_provider": "llama_cpp",
                    "model_name": "tinyllama",
                    "enabled": True,
                    "parameters": {
                        "model_path": "models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
                        "n_ctx": 512
                    }
                }
            }
        }
        return SystemConfig(**default_config)


__all__ = [
    # Config loader
    'ConfigLoader',
    'get_config',
    
    # Dynamic config (hot-reload)
    'DynamicConfigManager',
    'ConfigChangeEvent',
    'ConfigSnapshot',
    'get_config_manager',
    'create_config_manager',
    'reset_config_manager',
    
    # Models
    'SystemConfig',
    'AgentConfig',
]
