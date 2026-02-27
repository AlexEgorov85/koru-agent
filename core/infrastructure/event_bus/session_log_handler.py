"""
Обработчик событий для логирования в сессию.

Подписывается на события EventBus и записывает их в лог сессии.
"""
import logging
from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType
from core.infrastructure.logging.session_logger import get_session_logger


logger = logging.getLogger(__name__)


class SessionLogHandler:
    """
    Обработчик событий для логирования в сессию.
    
    Подписывается на:
    - AGENT_STARTED, AGENT_COMPLETED, AGENT_FAILED
    - SKILL_EXECUTED, ACTION_PERFORMED
    - LLM_CALL_STARTED, LLM_CALL_COMPLETED
    - и другие события
    """

    def __init__(self):
        """Инициализация обработчика."""
        self._current_session_id: str = None

    def set_session_id(self, session_id: str):
        """Установка ID текущей сессии."""
        self._current_session_id = session_id

    def _get_logger(self):
        """Получение логгера сессии."""
        if self._current_session_id:
            return get_session_logger(self._current_session_id)
        return None

    async def on_agent_started(self, event: Event):
        """Обработка события запуска агента."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.log_event("AGENT_STARTED", f"Goal: {data.get('goal', 'unknown')}")

    async def on_agent_completed(self, event: Event):
        """Обработка события завершения агента."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.log_event("AGENT_COMPLETED", f"Result: {data.get('result', 'unknown')[:500]}")

    async def on_skill_executed(self, event: Event):
        """Обработка выполнения навыка."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.log_event(
                "SKILL_EXECUTED",
                f"Skill: {data.get('skill', 'unknown')}",
                result=str(data.get('result', ''))[:300]
            )

    async def on_action_performed(self, event: Event):
        """Обработка действия."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.log_action(
                data.get('action', 'unknown'),
                data.get('parameters', {})
            )

    async def on_observation(self, event: Event):
        """Обработка наблюдения."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.log_observation(
                data.get('observation', 'unknown'),
                **{k: v for k, v in data.items() if k != 'observation'}
            )

    async def on_llm_call_started(self, event: Event):
        """Обработка начала LLM вызова."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.log_event(
                "LLM_CALL_STARTED",
                f"Component: {data.get('component', 'unknown')} | Phase: {data.get('phase', 'unknown')}"
            )

    async def on_llm_call_completed(self, event: Event):
        """Обработка завершения LLM вызова."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.log_event(
                "LLM_CALL_COMPLETED",
                f"Component: {data.get('component', 'unknown')} | Phase: {data.get('phase', 'unknown')}"
            )

    async def on_component_initialized(self, event: Event):
        """Обработка инициализации компонента."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.log_component_init(
                data.get('component_type', 'unknown'),
                data.get('component_name', 'unknown')
            )

    async def on_error(self, event: Event):
        """Обработка ошибки."""
        session_logger = self._get_logger()
        if session_logger:
            data = event.data
            session_logger.error(
                f"Error: {data.get('error', 'unknown')}",
                exc_info=data.get('exc_info', False)
            )

    def subscribe(self, event_bus: EventBus):
        """
        Подписка на события.

        ARGS:
            event_bus: шина событий
        """
        event_bus.subscribe(EventType.AGENT_STARTED, self.on_agent_started)
        event_bus.subscribe(EventType.AGENT_COMPLETED, self.on_agent_completed)
        event_bus.subscribe(EventType.AGENT_FAILED, self.on_agent_completed)  # Используем тот же обработчик
        event_bus.subscribe(EventType.SKILL_EXECUTED, self.on_skill_executed)
        event_bus.subscribe(EventType.ACTION_PERFORMED, self.on_action_performed)
        event_bus.subscribe(EventType.LLM_CALL_STARTED, self.on_llm_call_started)
        event_bus.subscribe(EventType.LLM_CALL_COMPLETED, self.on_llm_call_completed)
        event_bus.subscribe(EventType.COMPONENT_INITIALIZED, self.on_component_initialized)
        event_bus.subscribe(EventType.ERROR_OCCURRED, self.on_error)
        
        logger.info("SessionLogHandler подписан на события")


# Глобальный обработчик
_global_session_handler: SessionLogHandler = None


def get_session_log_handler() -> SessionLogHandler:
    """Получение глобального обработчика сессии."""
    global _global_session_handler
    if _global_session_handler is None:
        _global_session_handler = SessionLogHandler()
    return _global_session_handler


def init_session_logging(event_bus: EventBus, session_id: str):
    """
    Инициализация логирования сессии.

    ARGS:
        event_bus: шина событий
        session_id: ID сессии
    """
    handler = get_session_log_handler()
    handler.set_session_id(session_id)
    handler.subscribe(event_bus)
