"""
SessionLogger - логирование сессий с использованием LogManager.

FEATURES:
- JSONL формат для структурированности
- Автоматическая индексация
- Интеграция с LogManager

USAGE:
    from core.infrastructure.logging import get_session_logger

    logger = get_session_logger(session_id)
    await logger.start(goal="Найти книги Пушкина")
    await logger.log_llm_prompt(...)
    await logger.end(success=True)
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from core.infrastructure.logging.log_manager import LogManager, get_log_manager
from core.infrastructure.logging.log_indexer import LogIndexer


logger = logging.getLogger(__name__)


class SessionLogger:
    """
    Логгер сессии с использованием LogManager.

    FEATURES:
    - JSONL формат для всех записей
    - Автоматическая индексация
    - Интеграция с системой логирования
    """

    def __init__(self, session_id: str, agent_id: Optional[str] = None,
                 log_manager: Optional[LogManager] = None):
        """
        Инициализация логгера сессии.

        ARGS:
            session_id: ID сессии
            agent_id: ID агента (опционально)
            log_manager: LogManager (опционально)
        """
        self.session_id = session_id
        self.agent_id = agent_id or "unknown"
        self._log_manager = log_manager or get_log_manager()

        self._start_time: Optional[datetime] = None
        self._steps: int = 0
        self._llm_calls: List[Dict[str, Any]] = []
        self._active = False

    async def start(self, goal: str, **kwargs) -> None:
        """
        Начало сессии.

        ARGS:
            goal: Цель сессии
            **kwargs: Дополнительные данные
        """
        self._start_time = datetime.now()
        self._active = True

        event_data = {
            'type': 'session_started',
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'goal': goal,
            'timestamp': self._start_time.isoformat() + 'Z',
            **kwargs
        }

        self._log_manager.log_session(self.session_id, event_data)

        if self._log_manager._indexer:
            await self._log_manager._indexer.add_session(
                self.session_id,
                self.agent_id,
                goal
            )

        logger.info(f"Сессия начата: {self.session_id} (goal: {goal})")

    async def log_llm_prompt(self, component: str, phase: str,
                              system_prompt: str, user_prompt: str,
                              **kwargs) -> None:
        """
        Логирование LLM промпта.

        ARGS:
            component: Компонент
            phase: Фаза (think/act/observe)
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            **kwargs: Дополнительные данные
        """
        if not self._active:
            logger.warning("Сессия не активна")
            return

        timestamp = datetime.now()

        event_data = {
            'type': 'llm_prompt',
            'session_id': self.session_id,
            'component': component,
            'phase': phase,
            'system_prompt': system_prompt,
            'user_prompt': user_prompt,
            'prompt_length': len(system_prompt) + len(user_prompt),
            'timestamp': timestamp.isoformat() + 'Z',
            **kwargs
        }

        self._log_manager.log_session(self.session_id, event_data)
        self._log_manager.log_llm(self.session_id, event_data)
        self._llm_calls.append(event_data)
        
        logger.debug(f"LLM промпт logged: {component}/{phase}")

    async def log_llm_response(self, component: str, phase: str,
                                response: Any, tokens: Optional[int] = None,
                                latency_ms: Optional[float] = None,
                                **kwargs) -> None:
        """
        Логирование LLM ответа.

        ARGS:
            component: Компонент
            phase: Фаза
            response: Ответ LLM
            tokens: Количество токенов
            latency_ms: Задержка в мс
            **kwargs: Дополнительные данные
        """
        if not self._active:
            logger.warning("Сессия не активна")
            return

        timestamp = datetime.now()

        event_data = {
            'type': 'llm_response',
            'session_id': self.session_id,
            'component': component,
            'phase': phase,
            'response': response if isinstance(response, (str, int, float, bool, type(None))) else str(response),
            'tokens': tokens,
            'latency_ms': latency_ms,
            'timestamp': timestamp.isoformat() + 'Z',
            **kwargs
        }

        self._log_manager.log_session(self.session_id, event_data)
        self._log_manager.log_llm(self.session_id, event_data)
        self._llm_calls.append(event_data)
        
        logger.debug(f"LLM ответ logged: {component}/{phase}")

    async def log_step(self, step_number: int, capability: str,
                        success: bool, latency_ms: Optional[float] = None,
                        **kwargs) -> None:
        """
        Логирование шага выполнения.

        ARGS:
            step_number: Номер шага
            capability: Название способности
            success: Успешность
            latency_ms: Задержка в мс
            **kwargs: Дополнительные данные
        """
        if not self._active:
            logger.warning("Сессия не активна")
            return

        self._steps += 1

        event_data = {
            'type': 'step_executed',
            'session_id': self.session_id,
            'step_number': step_number,
            'capability': capability,
            'success': success,
            'latency_ms': latency_ms,
            'timestamp': datetime.now().isoformat() + 'Z',
            **kwargs
        }

        self._log_manager.log_session(self.session_id, event_data)
        logger.debug(f"Шаг {step_number} logged: {capability} (success={success})")

    async def log_error(self, error_type: str, error_message: str,
                         capability: Optional[str] = None,
                         **kwargs) -> None:
        """
        Логирование ошибки.

        ARGS:
            error_type: Тип ошибки
            error_message: Сообщение об ошибке
            capability: Способность (опционально)
            **kwargs: Дополнительные данные
        """
        if not self._active:
            logger.warning("Сессия не активна")
            return

        event_data = {
            'type': 'error',
            'session_id': self.session_id,
            'error_type': error_type,
            'error_message': error_message,
            'capability': capability,
            'timestamp': datetime.now().isoformat() + 'Z',
            **kwargs
        }

        self._log_manager.log_session(self.session_id, event_data)
        logger.error(f"Ошибка logged: {error_type} - {error_message}")

    async def end(self, success: bool = True, result: Optional[str] = None,
                   **kwargs) -> None:
        """
        Завершение сессии.

        ARGS:
            success: Успешность
            result: Результат
            **kwargs: Дополнительные данные
        """
        if not self._active:
            logger.warning("Сессия не активна")
            return

        self._active = False

        end_time = datetime.now()
        total_time_ms = (end_time - self._start_time).total_seconds() * 1000 if self._start_time else 0

        event_data = {
            'type': 'session_completed' if success else 'session_failed',
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'success': success,
            'result': result,
            'steps': self._steps,
            'total_time_ms': int(total_time_ms),
            'llm_calls_count': len(self._llm_calls),
            'timestamp': end_time.isoformat() + 'Z',
            **kwargs
        }

        self._log_manager.log_session(self.session_id, event_data)

        if self._log_manager._indexer:
            await self._log_manager._indexer.update_session_status(
                self.session_id,
                'completed' if success else 'failed',
                self._steps,
                int(total_time_ms)
            )

        logger.info(f"Сессия завершена: {self.session_id} (success={success}, steps={self._steps})")

    def info(self, message: str, **kwargs):
        """INFO сообщение."""
        event_data = {
            'type': 'log_info',
            'session_id': self.session_id,
            'message': message,
            'timestamp': datetime.now().isoformat() + 'Z',
            **kwargs
        }
        self._log_manager.log_session(self.session_id, event_data)

    def debug(self, message: str, **kwargs):
        """DEBUG сообщение."""
        event_data = {
            'type': 'log_debug',
            'session_id': self.session_id,
            'message': message,
            'timestamp': datetime.now().isoformat() + 'Z',
            **kwargs
        }
        self._log_manager.log_session(self.session_id, event_data)

    def warning(self, message: str, **kwargs):
        """WARNING сообщение."""
        event_data = {
            'type': 'log_warning',
            'session_id': self.session_id,
            'message': message,
            'timestamp': datetime.now().isoformat() + 'Z',
            **kwargs
        }
        self._log_manager.log_session(self.session_id, event_data)

    def error(self, message: str, **kwargs):
        """ERROR сообщение."""
        event_data = {
            'type': 'log_error',
            'session_id': self.session_id,
            'message': message,
            'timestamp': datetime.now().isoformat() + 'Z',
            **kwargs
        }
        self._log_manager.log_session(self.session_id, event_data)

    def log_event(self, event_type: str, message: str, **kwargs):
        """Произвольное событие."""
        event_data = {
            'type': event_type.lower(),
            'session_id': self.session_id,
            'message': message,
            'timestamp': datetime.now().isoformat() + 'Z',
            **kwargs
        }
        self._log_manager.log_session(self.session_id, event_data)

    def close(self):
        """Закрытие сессии."""
        if self._active:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.end(success=True))
            except RuntimeError:
                pass


# Глобальные активные сессии
_active_sessions: Dict[str, SessionLogger] = {}


def get_session_logger(session_id: str, agent_id: Optional[str] = None) -> SessionLogger:
    """
    Получение или создание логгера сессии.

    ARGS:
        session_id: ID сессии
        agent_id: ID агента (опционально)

    RETURNS:
        SessionLogger
    """
    if session_id not in _active_sessions:
        _active_sessions[session_id] = SessionLogger(session_id, agent_id)
    return _active_sessions[session_id]


def close_session_logger(session_id: str):
    """Закрытие логгера сессии."""
    if session_id in _active_sessions:
        _active_sessions[session_id].close()
        del _active_sessions[session_id]


def cleanup_old_sessions(max_sessions: int = 100, log_dir: str = "logs/sessions"):
    """
    Очистка старых сессий.
    
    NOTE: В новой системе логи хранятся в logs/archive/YYYY/MM/sessions/
    и управляются через LogRotator.
    
    Эта функция оставлена для обратной совместимости.
    
    ARGS:
        max_sessions: максимальное количество хранимых сессий
        log_dir: директория логов (не используется в новой системе)
    """
    # В новой системе очистка выполняется через LogRotator
    # Эта функция оставлена для совместимости
    pass
