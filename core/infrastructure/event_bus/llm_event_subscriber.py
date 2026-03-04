"""
Подписчик на события LLM для логирования и аудита.
"""
import json
from typing import Optional
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, Event, EventType
from core.infrastructure.logging import EventBusLogger


class LLMEventSubscriber:
    """Подписчик на события LLM для подробного логирования."""

    def __init__(self, event_bus: UnifiedEventBus, log_full_content: bool = False):
        self.event_bus = event_bus
        self.log_full_content = log_full_content
        self.event_bus_logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="LLMEventSubscriber")
        self._prompt_count = 0
        self._response_count = 0

    async def on_llm_prompt_generated(self, event: Event):
        """Обработчик события LLM_PROMPT_GENERATED."""
        self._prompt_count += 1
        data = event.data
        session_id = data.get('session_id', event.session_id or 'unknown')
        component = data.get('component', 'unknown')
        phase = data.get('phase', 'unknown')

        # Логируем через EventBusLogger
        prompt_length = data.get('prompt_length', len(data.get('user_prompt', '')))
        await self.event_bus_logger.info(f"[LLM] Prompt #{self._prompt_count} | {component}/{phase} | {prompt_length} симв.")

        if self.log_full_content:
            await self.event_bus_logger.debug(f"System prompt: {data.get('system_prompt', '')[:500]}")
            await self.event_bus_logger.debug(f"User prompt: {data.get('user_prompt', '')[:500]}")

    async def on_llm_response_received(self, event: Event):
        """Обработчик события LLM_RESPONSE_RECEIVED."""
        self._response_count += 1
        data = event.data
        session_id = data.get('session_id', event.session_id or 'unknown')
        component = data.get('component', 'unknown')
        phase = data.get('phase', 'unknown')

        response = data.get('response', {})
        if isinstance(response, dict):
            response_str = json.dumps(response, ensure_ascii=False)[:200]
        else:
            response_str = str(response)[:200]

        await self.event_bus_logger.info(f"[LLM] Response #{self._response_count} | {component}/{phase}")

        if self.log_full_content:
            await self.event_bus_logger.debug(f"Response: {response_str}")

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
