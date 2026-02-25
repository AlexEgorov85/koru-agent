"""
Подписчик на события LLM для логирования и аудита.

Использование:
```python
from core.infrastructure.event_bus.llm_event_subscriber import LLMEventSubscriber
from core.infrastructure.event_bus.event_bus import get_event_bus

subscriber = LLMEventSubscriber()
subscriber.subscribe(get_event_bus())
```
"""
import logging
import json
from typing import Optional
from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType


logger = logging.getLogger(__name__)


class LLMEventSubscriber:
    """
    Подписчик на события LLM для подробного логирования.

    ПУБЛИКУЕМЫЕ СОБЫТИЯ:
    - LLM_PROMPT_GENERATED: сгенерирован промпт для LLM
    - LLM_RESPONSE_RECEIVED: получен ответ от LLM
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

        logger.info("=" * 80)
        logger.info(f"=== LLM ПРОМПТ #{self._prompt_count} ({data.get('component', 'unknown')}) ===")
        logger.info("=" * 80)
        logger.info(f"Компонент: {data.get('component', 'unknown')}")
        logger.info(f"Фаза: {data.get('phase', 'unknown')}")
        logger.info(f"Session ID: {data.get('session_id', 'unknown')}")
        logger.info(f"Цель: {data.get('goal', 'unknown')}")
        logger.info("-" * 80)
        logger.info(f"System prompt ({len(data.get('system_prompt', ''))} символов):")
        logger.info(f"{data.get('system_prompt', '')[:500]}...")
        logger.info("-" * 80)

        if self.log_full_content:
            logger.info(f"User prompt (полный, {data.get('prompt_length', 0)} символов):")
            logger.info(f"{data.get('user_prompt', '')}")
        else:
            logger.info(f"User prompt (первые 2000 символов из {data.get('prompt_length', 0)}):")
            logger.info(f"{data.get('user_prompt', '')[:2000]}...")

        logger.info("-" * 80)
        logger.info(f"Temperature: {data.get('temperature', 0.0)}")
        logger.info(f"Max tokens: {data.get('max_tokens', 1000)}")
        logger.info("=" * 80)

    async def on_llm_response_received(self, event: Event):
        """
        Обработчик события LLM_RESPONSE_RECEIVED.

        ARGS:
        - event: событие с данными об ответе
        """
        self._response_count += 1
        data = event.data

        logger.info("=" * 80)
        logger.info(f"=== LLM ОТВЕТ #{self._response_count} ({data.get('component', 'unknown')}) ===")
        logger.info("=" * 80)
        logger.info(f"Компонент: {data.get('component', 'unknown')}")
        logger.info(f"Фаза: {data.get('phase', 'unknown')}")
        logger.info(f"Session ID: {data.get('session_id', 'unknown')}")
        logger.info(f"Формат ответа: {data.get('response_format', 'unknown')}")
        logger.info("-" * 80)

        response = data.get('response', {})
        if isinstance(response, dict):
            logger.info(f"Результат (JSON):")
            logger.info(f"{json.dumps(response, ensure_ascii=False, indent=2)[:3000]}...")
        else:
            logger.info(f"Результат ({type(response).__name__}):")
            logger.info(f"{str(response)[:3000]}...")

        logger.info("=" * 80)

    def subscribe(self, event_bus: EventBus):
        """
        Подписка на события LLM.

        ARGS:
        - event_bus: шина событий для подписки
        """
        event_bus.subscribe(EventType.LLM_PROMPT_GENERATED, self.on_llm_prompt_generated)
        event_bus.subscribe(EventType.LLM_RESPONSE_RECEIVED, self.on_llm_response_received)
        logger.info(f"LLMEventSubscriber подписан на события LLM (log_full_content={self.log_full_content})")

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
