"""
LLMCallLogger - логирование LLM вызовов с использованием LogManager.

FEATURES:
- Агрегация всех LLM вызовов сессии в один файл
- JSONL формат для парсинга
- Интеграция с LogManager

USAGE:
    from core.infrastructure.logging import get_llm_call_logger

    logger = get_llm_call_logger()
    await logger.log_prompt(session_id, component, phase, data)
    await logger.log_response(session_id, component, phase, data)
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from core.infrastructure.logging.log_manager import LogManager, get_log_manager


logger = logging.getLogger(__name__)


class LLMCallLogger:
    """
    Логгер LLM вызовов с использованием LogManager.

    FEATURES:
    - Все вызовы сессии в одном файле
    - JSONL формат
    - Интеграция с системой логирования
    """

    def __init__(self, log_manager: Optional[LogManager] = None):
        """
        Инициализация логгера.

        ARGS:
            log_manager: LogManager (опционально)
        """
        self._log_manager = log_manager or get_log_manager()
        self._call_count: int = 0

    async def log_prompt(self, session_id: str, component: str,
                          phase: str, data: Dict[str, Any]) -> None:
        """
        Логирование промпта.

        ARGS:
            session_id: ID сессии
            component: Компонент
            phase: Фаза (think/act/observe)
            data: Данные промпта
        """
        timestamp = datetime.now()

        event_data = {
            'type': 'llm_prompt',
            'session_id': session_id,
            'component': component,
            'phase': phase,
            'system_prompt': data.get('system_prompt', ''),
            'user_prompt': data.get('user_prompt', ''),
            'prompt_length': data.get('prompt_length', 0),
            'temperature': data.get('temperature', 0.7),
            'max_tokens': data.get('max_tokens', 1000),
            'goal': data.get('goal', 'unknown'),
            'timestamp': timestamp.isoformat() + 'Z',
        }

        self._log_manager.log_llm(session_id, event_data)

        self._call_count += 1
        self.event_bus_logger.debug(f"LLM промпт logged: {session_id}/{component}/{phase}")

    async def log_response(self, session_id: str, component: str,
                            phase: str, data: Dict[str, Any]) -> None:
        """
        Логирование ответа.

        ARGS:
            session_id: ID сессии
            component: Компонент
            phase: Фаза
            data: Данные ответа
        """
        timestamp = datetime.now()

        response = data.get('response', {})
        if isinstance(response, dict):
            response_str = json.dumps(response, ensure_ascii=False, default=str)
        else:
            response_str = str(response)

        event_data = {
            'type': 'llm_response',
            'session_id': session_id,
            'component': component,
            'phase': phase,
            'response': response_str,
            'response_format': data.get('response_format', type(response).__name__),
            'tokens': data.get('tokens'),
            'latency_ms': data.get('latency_ms'),
            'goal': data.get('goal', 'unknown'),
            'timestamp': timestamp.isoformat() + 'Z',
        }

        self._log_manager.log_llm(session_id, event_data)

        self.event_bus_logger.debug(f"LLM ответ logged: {session_id}/{component}/{phase}")

    def cleanup(self):
        """Очистка счётчиков."""
        self._call_count = 0

    @property
    def call_count(self) -> int:
        """Количество logged вызовов."""
        return self._call_count


# Глобальный экземпляр
_global_llm_logger: Optional[LLMCallLogger] = None


def get_llm_call_logger() -> LLMCallLogger:
    """
    Получение глобального логгера LLM вызовов.

    RETURNS:
        LLMCallLogger
    """
    global _global_llm_logger
    if _global_llm_logger is None:
        _global_llm_logger = LLMCallLogger()
    return _global_llm_logger


def init_llm_call_logger() -> LLMCallLogger:
    """
    Инициализация глобального логгера LLM вызовов.

    RETURNS:
        LLMCallLogger
    """
    global _global_llm_logger
    _global_llm_logger = LLMCallLogger()
    return _global_llm_logger
