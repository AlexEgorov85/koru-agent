"""
Система логирования koru-agent.

КОМПОНЕНТЫ:
- LogManager: единая точка управления логами
- LogIndexer: индексация для быстрого поиска
- LogRotator: ротация и очистка
- LogSearch: поиск по логам
- SessionLogger: логирование сессий
- LLMCallLogger: логирование LLM вызовов

USAGE:
    from core.infrastructure.logging import init_logging_system

    # Инициализация
    await init_logging_system()

    # Использование
    from core.infrastructure.logging import get_log_manager, get_session_logger

    log_manager = get_log_manager()
    log_manager.log_agent("Agent started")

    session_logger = get_session_logger(session_id)
    await session_logger.start(goal="Find books")
"""

from core.infrastructure.logging.log_config import (
    LoggingConfig,
    LogFormat,
    RetentionConfig,
    IndexingConfig,
    SymlinksConfig,
    get_logging_config,
    configure_logging,
    load_config_from_yaml,
    save_config_to_yaml,
)

from core.infrastructure.logging.log_manager import (
    LogManager,
    get_log_manager,
    init_log_manager,
)

from core.infrastructure.logging.log_indexer import (
    LogIndexer,
    SessionIndexEntry,
    AgentIndexEntry,
    get_log_indexer,
    init_log_indexer,
)

from core.infrastructure.logging.log_rotator import (
    LogRotator,
    get_log_rotator,
    init_log_rotator,
)

from core.infrastructure.logging.log_search import (
    LogSearch,
    get_log_search,
    init_log_search,
    get_latest_session,
    find_session,
    get_session_llm_calls,
    get_last_llm_call,
)

from core.infrastructure.logging.session_logger import (
    SessionLogger,
    get_session_logger,
    close_session_logger,
    _active_sessions,
)

from core.infrastructure.logging.llm_call_logger import (
    LLMCallLogger,
    get_llm_call_logger,
    init_llm_call_logger,
)

# Для обратной совместимости
from core.infrastructure.logging.log_formatter import (
    LogFormatter,
    setup_logging,
)


__all__ = [
    # Config
    'LoggingConfig',
    'LogFormat',
    'RetentionConfig',
    'IndexingConfig',
    'SymlinksConfig',
    'get_logging_config',
    'configure_logging',
    'load_config_from_yaml',
    'save_config_to_yaml',

    # Manager
    'LogManager',
    'get_log_manager',
    'init_log_manager',

    # Indexer
    'LogIndexer',
    'SessionIndexEntry',
    'AgentIndexEntry',
    'get_log_indexer',
    'init_log_indexer',

    # Rotator
    'LogRotator',
    'get_log_rotator',
    'init_log_rotator',

    # Search
    'LogSearch',
    'get_log_search',
    'init_log_search',
    'get_latest_session',
    'find_session',
    'get_session_llm_calls',
    'get_last_llm_call',

    # Session Logger
    'SessionLogger',
    'get_session_logger',
    'close_session_logger',
    '_active_sessions',

    # LLM Call Logger
    'LLMCallLogger',
    'get_llm_call_logger',
    'init_llm_call_logger',

    # Backward compatibility
    'LogFormatter',
    'setup_logging',
]


async def init_logging_system(config: LoggingConfig = None) -> dict:
    """
    Инициализация всей системы логирования.

    ARGS:
        config: Конфигурация (опционально)

    RETURNS:
        Dict с инициализированными компонентами
    """
    log_manager = await init_log_manager(config)
    log_indexer = await init_log_indexer(config)
    log_rotator = await init_log_rotator(config)
    log_search = await init_log_search(config, log_indexer)

    log_manager.set_indexer(log_indexer)
    log_manager.set_rotator(log_rotator)

    return {
        'manager': log_manager,
        'indexer': log_indexer,
        'rotator': log_rotator,
        'search': log_search,
    }


async def shutdown_logging_system():
    """Завершение работы системы логирования."""
    log_manager = get_log_manager()
    if log_manager.is_initialized:
        await log_manager.shutdown()

    log_indexer = get_log_indexer()
    if log_indexer.is_initialized:
        await log_indexer.shutdown()

    log_rotator = get_log_rotator()
    if log_rotator.is_initialized:
        await log_rotator.shutdown()

    log_search = get_log_search()
    if log_search.is_initialized:
        await log_search.shutdown()
