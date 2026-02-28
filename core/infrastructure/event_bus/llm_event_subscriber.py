"""
Подписчик на события LLM для логирования и аудита.

Использование:
```python
from core.infrastructure.event_bus.llm_event_subscriber import LLMEventSubscriber
from core.infrastructure.event_bus.event_bus import get_event_bus

subscriber = LLMEventSubscriber()
subscriber.subscribe(get_event_bus())
```

ВАЖНО: Технические логи (промпты, ответы) пишутся в файл сессии:
logs/sessions/{session_id}.log
"""
import logging
import json
from typing import Optional
from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType
from core.infrastructure.logging.session_logger import get_session_logger


logger = logging.getLogger(__name__)


class LLMEventSubscriber:
    """
    Подписчик на события LLM для подробного логирования.

    ПУБЛИКУЕМЫЕ СОБЫТИЯ:
    - LLM_PROMPT_GENERATED: сгенерирован промпт для LLM
    - LLM_RESPONSE_RECEIVED: получен ответ от LLM
    
    ВАЖНО: Технические логи (промпты, ответы) выводятся на уровне DEBUG,
    чтобы не засорять консоль. Полные промпты/ответы пишутся в отдельные файлы:
    logs/llm_calls/{session_id}_{timestamp}_{component}_{phase}.log
    """

    def __init__(self, log_full_content: bool = False):
        """
        Инициализация подписчика.

        ARGS:
        - log_full_content: логировать полный контент промптов/ответов (полезно для отладки)
        """
        self.log_full_content = log_full_content
        self._prompt_count = 0
        self._response_count = 0

    async def on_llm_prompt_generated(self, event: Event):
        """
        Обработчик события LLM_PROMPT_GENERATED.

        ARGS:
        - event: событие с данными о промпте
        """
        self._prompt_count += 1
        data = event.data
        session_id = data.get('session_id', 'unknown')
        component = data.get('component', 'unknown')
        phase = data.get('phase', 'unknown')

        # Пишем в лог сессии
        session_logger = get_session_logger(session_id)
        await session_logger.log_llm_prompt(
            component=component,
            phase=phase,
            system_prompt=data.get('system_prompt', ''),
            user_prompt=data.get('user_prompt', '')
        )

        # Краткое уведомление в лог (DEBUG → только файл)
        logger.debug(f"LLM Prompt #{self._prompt_count} | {component}/{phase} | Session: {session_id}")
        logger.debug(f"Prompt length: {data.get('prompt_length', len(data.get('user_prompt', '')))} chars")

        # Пользователь видит только факт (INFO)
        logger.info(f"📝 Промпт #{self._prompt_count} ({data.get('prompt_length', 0)} символов)")

    async def on_llm_response_received(self, event: Event):
        """
        Обработчик события LLM_RESPONSE_RECEIVED.

        ARGS:
        - event: событие с данными об ответе
        """
        self._response_count += 1
        data = event.data
        session_id = data.get('session_id', 'unknown')
        component = data.get('component', 'unknown')
        phase = data.get('phase', 'unknown')

        # Пишем в лог сессии
        session_logger = get_session_logger(session_id)
        await session_logger.log_llm_response(component, phase, data)

        # Краткое уведомление в лог (DEBUG → только файл)
        response = data.get('response', {})
        if isinstance(response, dict):
            response_str = json.dumps(response, ensure_ascii=False)[:200]
        else:
            response_str = str(response)[:200]
        logger.debug(f"LLM Response #{self._response_count} | {component}/{phase} | {response_str}...")

        # Пользователь видит только факт (INFO)
        logger.info(f"✅ Ответ #{self._response_count} получен")

    def subscribe(self, event_bus: EventBus):
        """
        Подписка на события LLM.

        ARGS:
        - event_bus: шина событий для подписки
        """
        event_bus.subscribe(EventType.LLM_PROMPT_GENERATED, self.on_llm_prompt_generated)
        event_bus.subscribe(EventType.LLM_RESPONSE_RECEIVED, self.on_llm_response_received)
        logger.info(f"LLMEventSubscriber подписан (log_full={self.log_full_content})")

    def get_stats(self) -> dict:
        """
        Получение статистики обработанных событий.

        RETURNS:
        - словарь со статистикой
        """
        return {
            "prompt_count": self._prompt_count,
            "response_count": self._response_count
        }
