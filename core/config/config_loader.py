# core/config/config_loader.py
import os
import json
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from core.config.models import SystemConfig

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Управление конфигурацией системы"""
    
    DEFAULT_CONFIG_DIR = "core/config/defaults"
    DEFAULT_PROFILES = ["dev", "staging", "prod", "test"]
    DEFAULT_CONFIG_FILES = {
        "base": "base.yaml",
        "profiles": "{profile}.yaml",
        "secrets": "secrets.yaml"
    }
    
    def __init__(
        self,
        config_dir: Optional[str] = None,
        profile: Optional[str] = None,
        config_files: Optional[Dict[str, str]] = None
    ):
        """
        Инициализация загрузчика конфигурации
        :param config_dir: Директория с конфигурационными файлами
        :param profile: Профиль конфигурации (dev/staging/prod)
        :param config_files: Словарь с путями к конфигурационным файлам
        """
        self.config_dir = config_dir or os.getenv("CONFIG_DIR") or self.DEFAULT_CONFIG_DIR
        self.profile = profile or os.getenv("APP_PROFILE") or "dev"
        self.config_files = config_files or self.DEFAULT_CONFIG_FILES
        
        # Проверка существования директории
        if not Path(self.config_dir).exists():
            raise FileNotFoundError(f"Директория конфигурации не найдена: {self.config_dir}")
    
    def load(self) -> SystemConfig:
        """Загрузка конфигурации с объединением всех источников"""
        # 1. Загрузка базовой конфигурации
        base_config = self._load_base_config()
        
        # 2. Загрузка конфигурации профиля
        profile_config = self._load_profile_config()
        
        # 3. Объединение конфигураций с приоритетом профиля
        merged_config = self._merge_configs(base_config, profile_config)
        
        # 4. Загрузка и объединение секретов
        secrets_config = self._load_secrets_config()
        merged_config = self._merge_configs(merged_config, secrets_config)
        
        # 5. Переопределение из переменных окружения
        env_config = self._load_env_config()
        merged_config = self._merge_configs(merged_config, env_config)
        
        # 6. Создание и валидация итоговой конфигурации
        return SystemConfig(**merged_config)
    
    def _load_base_config(self) -> Dict[str, Any]:
        """Загрузка базовой конфигурации"""
        base_file = Path(self.config_dir) / self.config_files["base"]
        if not base_file.exists():
            # Создаем базовую конфигурацию по умолчанию
            return self._create_default_config()
        
        return self._load_yaml_file(base_file)
    
    def _load_profile_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации профиля"""
        profile_file = Path(self.config_dir) / self.config_files["profiles"].format(profile=self.profile)
        if not profile_file.exists():
            return {}
        
        return self._load_yaml_file(profile_file)
    
    def _load_secrets_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации секретов"""
        secrets_file = Path(self.config_dir) / self.config_files["secrets"]
        if not secrets_file.exists():
            return {}
        
        # Загружаем секреты в безопасном режиме
        secrets = self._load_yaml_file(secrets_file)
        return {"security": {"secrets": secrets}}
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из переменных окружения"""
        env_config = {}
        
        # Обработка переменных окружения с префиксом APP_
        for key, value in os.environ.items():
            if key.startswith("APP_"):
                # Преобразуем APP_DB_HOST в путь db.host
                path = key[4:].lower().replace('_', '.').split('.')
                self._set_nested_value(env_config, path, value)
        
        return env_config
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Загрузка YAML файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"Ошибка загрузки конфигурации из {file_path}: {str(e)}")
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Рекурсивное объединение конфигураций"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        # Нормализуем конфигурацию провайдеров после объединения
        result = self._normalize_provider_config(result)
        
        return result
    
    def _set_nested_value(self, config: Dict[str, Any], path: List[str], value: str):
        """Установка вложенного значения в конфигурацию"""
        current = config
        
        for i, key in enumerate(path):
            if i == len(path) - 1:
                # Последний ключ - устанавливаем значение
                try:
                    # Пытаемся преобразовать тип
                    if value.lower() in ['true', 'false']:
                        current[key] = value.lower() == 'true'
                    elif value.isdigit():
                        current[key] = int(value)
                    elif '.' in value and value.replace('.', '', 1).isdigit():
                        current[key] = float(value)
                    else:
                        current[key] = value
                except (ValueError, TypeError):
                    current[key] = value
            else:
                # Создаем вложенные словари при необходимости
                if key not in current or not isinstance(current[key], dict):
                    current[key] = {}
                current = current[key]
    
    def _normalize_provider_config(self, config_dict: Dict) -> Dict:
        """Нормализация конфигурации провайдеров (поддержка обратной совместимости)"""
        if isinstance(config_dict, dict):
            # Обработка llm_providers
            if "llm_providers" in config_dict:
                for provider_name, provider_config in config_dict["llm_providers"].items():
                    if isinstance(provider_config, dict):
                        if "type_provider" in provider_config and "provider_type" not in provider_config:
                            provider_config["provider_type"] = provider_config.pop("type_provider")
                            logger.warning(
                                f"Устаревшее поле 'type_provider' заменено на 'provider_type' для провайдера {provider_name}. "
                                f"Обновите конфигурацию."
                            )

            # Обработка db_providers
            if "db_providers" in config_dict:
                for provider_name, provider_config in config_dict["db_providers"].items():
                    if isinstance(provider_config, dict):
                        if "type_provider" in provider_config and "provider_type" not in provider_config:
                            provider_config["provider_type"] = provider_config.pop("type_provider")
                            logger.warning(
                                f"Устаревшее поле 'type_provider' заменено на 'provider_type' для провайдера {provider_name}. "
                                f"Обновите конфигурацию."
                            )
        
        return config_dict

    def _create_default_config(self) -> Dict[str, Any]:
        """Создание конфигурации по умолчанию"""
        return {
            "profile": self.profile,
            "debug": self.profile == "dev",
            "log_level": "DEBUG" if self.profile == "dev" else "INFO",
            "log_dir": f"logs/{self.profile}",
            "data_dir": f"data/{self.profile}",
            "llm_providers": {
                "default_llm": {
                    "provider_type": "llama_cpp",  # Исправлено на provider_type
                    "model_name": "qwen-4b",
                    "enabled": True,
                    "parameters": {
                        "model_path": "./models/qwen-4b.gguf",
                        "n_ctx": 2048,
                        "n_gpu_layers": 0,
                        "temperature": 0.7,
                        "max_tokens": 512
                    }
                }
            },
            "db_providers": {
                "default_db": {
                    "provider_type": "postgres",  # Исправлено на provider_type
                    "host": "localhost",
                    "port": 5432,
                    "database": "agent_db",
                    "username": "user",
                    "password": "password",  # Будет переопределен секретами
                    "enabled": True
                }
            },
            "skills": {
                "planning": {"enabled": True},
                "book_library": {"enabled": True}
            },
            "tools": {
                "SQLTool": {"enabled": True},
                "file_tool": {"enabled": True}
            },
            "agent": {
                "max_steps": 10,
                "max_retries": 3,
                "temperature": 0.7
            },
            "security": {
                "secrets_path": f"config/secrets_{self.profile}.yaml"
            }
        }