# core/config/__init__.py
import os
from typing import Optional

from core.config.models import SystemConfig
from .config_loader import ConfigLoader


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
        # Логирование ошибки загрузки конфигурации
        import logging
        logger = logging.getLogger("config")
        logger.error(f"Ошибка загрузки конфигурации: {str(e)}")
        
        # Создание минимальной конфигурации для работы
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