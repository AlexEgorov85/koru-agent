"""
Модуль метрик для BookLibrarySkill.

КОМПОНЕНТЫ:
- publish_metrics: функция публикации метрик выполнения
"""
from typing import Optional

from core.infrastructure.event_bus.unified_event_bus import EventType


async def publish_book_library_metrics(
    logger,
    capability_name: str,
    success: bool,
    execution_time_ms: float,
    execution_type: Optional[str] = None,
    rows_returned: int = 0,
    script_name: Optional[str] = None,
    error: Optional[str] = None,
    event_type=None
) -> None:
    """
    Публикация метрик выполнения BookLibrarySkill через стандартный logging.

    ARGS:
    - logger: логгер для публикации событий
    - capability_name: имя capability
    - success: флаг успеха выполнения
    - execution_time_ms: время выполнения в миллисекундах
    - execution_type: тип выполнения (static/dynamic/vector)
    - rows_returned: количество возвращённых строк
    - script_name: имя выполненного скрипта (для static)
    - error: сообщение об ошибке (при неудаче)

    NOTE:
    - Метрики не должны влиять на основную логику
    - Ошибки логируются на уровне debug
    """
    try:
        if logger:
            # Основное сообщение метрик
            await logger.info(
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Метрика: {capability_name} | execution_type={execution_type} | "
                f"execution_time={execution_time_ms:.2f}ms | rows={rows_returned} | "
                f"success={success} | script={script_name}"
            )

            # Детализация по типу выполнения
            if execution_type == "static" and script_name:
                await logger.info(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Static скрипт выполнен: {script_name} | "
                    f"status={'success' if success else 'failed'}"
                )
            elif execution_type == "dynamic":
                await logger.info(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Dynamic поиск выполнен | status={'success' if success else 'failed'}"
                )
            elif execution_type == "vector":
                await logger.info(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Vector поиск выполнен | status={'success' if success else 'failed'}"
                )
    except Exception as e:
        # Метрики не должны ломать основную логику
        if logger:
            await logger.debug(f"Ошибка публикации метрик: {e}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
