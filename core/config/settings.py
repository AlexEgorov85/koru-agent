"""
Обратная совместимость для core.config.settings.

ПРИМЕЧАНИЕ: Этот файл устарел. Используйте:
- core.config.app_config.AppConfig — основная конфигурация
- core.config.logging_config.LoggingConfig — логирование
- core.config.paths.log_paths — пути

*Settings классы перемещены в core.config.app_config
"""
from core.config.app_config import (
    DatabaseSettings,
    LLMSettings,
    AgentSettings,
    AppConfig,
    get_config,
    get_database_config,
    get_llm_config,
    get_agent_config,
)

# Для обратной совместимости
__all__ = [
    'DatabaseSettings',
    'LLMSettings',
    'AgentSettings',
    'AppConfig',
    'get_config',
    'get_database_config',
    'get_llm_config',
    'get_agent_config',
]
