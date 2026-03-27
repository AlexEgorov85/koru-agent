"""
Подписчик на события LLM для логирования и аудита.
"""
import json
from typing import Optional
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, Event, EventType
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()


class LLMEventSubscriber:
    """Подписчик на события LLM для подробного логирования."""

    def __init__(self, event_bus: UnifiedEventBus, log_full_content: bool = False):
        self.event_bus = event_bus
        self.log_full_content = log_full_content
        self.event_bus_logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="LLMEventSubscriber")
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        self._prompt_count = 0
        self._response_count = 0

    async def on_llm_prompt_generated(self, event: Event):
        """Обработчик события LLM_PROMPT_GENERATED."""
        self._prompt_count += 1
        data = event.data
        session_id = data.get('session_id', event.session_id or 'unknown')
        # Поддержка обоих форматов: от LLMOrchestrator и BaseLLMProvider
        component = data.get('capability_name', data.get('component', 'unknown'))
        phase = data.get('phase', 'unknown')

        # Логируем через EventBusLogger
        prompt_length = data.get('prompt_length', len(data.get('user_prompt', '')))
        await self.event_bus_logger.info(f"[LLM] Prompt #{self._prompt_count} | {component}/{phase} | {prompt_length} симв.")
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        if self.log_full_content:
            system_prompt = data.get('system_prompt', '')
            user_prompt = data.get('user_prompt', '')
            if system_prompt:
                await self.event_bus_logger.debug(f"System prompt: {system_prompt[:500]}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            if user_prompt:
                await self.event_bus_logger.debug(f"User prompt: {user_prompt[:500]}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    async def on_llm_response_received(self, event: Event):
        """Обработчик события LLM_RESPONSE_RECEIVED."""
        self._response_count += 1
        data = event.data
        session_id = data.get('session_id', event.session_id or 'unknown')
        # Поддержка обоих форматов: от LLMOrchestrator и BaseLLMProvider
        component = data.get('capability_name', data.get('component', 'unknown'))
        phase = data.get('phase', 'unknown')

        # Получаем ответ - поддержка обоих форматов
        # Приоритет: parsed_response → raw_response → response
        parsed_response = data.get('parsed_response')
        raw_response = data.get('raw_response', data.get('response', ''))
        
        # Форматируем ответ для логирования
        if parsed_response:
            # Распарсенный JSON - форматируем красиво
            response_str = json.dumps(parsed_response, ensure_ascii=False, indent=2)[:800]
        elif isinstance(raw_response, dict):
            response_str = json.dumps(raw_response, ensure_ascii=False, indent=2)[:800]
        elif isinstance(raw_response, str):
            response_str = raw_response[:800]  # Увеличено до 800 символов
        else:
            response_str = str(raw_response)[:800]

        # Добавляем метрики если доступны
        success = data.get('success', 'unknown')
        duration_ms = data.get('duration_ms', 0)
        tokens = data.get('tokens_used', 0)
        
        await self.event_bus_logger.info(
          # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            f"[LLM] Response #{self._response_count} | {component}/{phase} | "
            f"success={success} | duration={duration_ms:.1f}ms | tokens={tokens}"
        )

        if self.log_full_content and response_str:
            await self.event_bus_logger.debug(f"Response: {response_str}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    def subscribe(self, event_bus: UnifiedEventBus):
        """Подписка на события LLM."""
        event_bus.subscribe(EventType.LLM_PROMPT_GENERATED, self.on_llm_prompt_generated)
        event_bus.subscribe(EventType.LLM_RESPONSE_RECEIVED, self.on_llm_response_received)
        # Логирование при подписке не требуется — это внутренний метод

    def get_stats(self) -> dict:
        return {
            "prompt_count": self._prompt_count,
            "response_count": self._response_count
        }
