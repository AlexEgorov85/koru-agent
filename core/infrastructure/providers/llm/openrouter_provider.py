"""
Провайдер для OpenRouter API.
Использует OpenAI Python библиотеку для вызова удалённых LLM моделей.

OpenRouter — агрегатор, предоставляющий единый API к множеству моделей
(OpenAI, Anthropic, Google, Meta и др.) через https://openrouter.ai/api/v1

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    from openai import OpenAI
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-v1-..."
    )
    
    completion = client.chat.completions.create(
        model="qwen/qwen3.6-plus:free",
        messages=[...]
    )
"""
import asyncio
import time
import json
import logging
from typing import Dict, Any, Optional, List

from openai import OpenAI, AsyncOpenAI

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.interfaces.llm import LLMInterface
from core.infrastructure.logging.event_types import LogEventType
from core.models.types.llm_types import (
    LLMRequest,
    LLMResponse,
    LLMHealthStatus,
    StructuredOutputConfig,
    RawLLMResponse
)
from pydantic import BaseModel, Field


OPENROUTER_API_URL = "https://openrouter.ai/api/v1"

_logger = logging.getLogger(__name__)


class OpenRouterConfig(BaseModel):
    """Конфигурация для OpenRouter провайдера."""
    api_key: str = Field(..., description="API ключ OpenRouter")
    model_name: str = Field(default="qwen/qwen3.6-plus:free", description="ID модели в формате openrouter")
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=4096, description="Максимальное количество токенов")
    timeout_seconds: float = Field(default=180.0, ge=0.0, description="Таймаут HTTP запроса")
    base_url: str = Field(default=OPENROUTER_API_URL, description="Базовый URL API")


class OpenRouterProvider(BaseLLMProvider, LLMInterface):
    """
    Провайдер для OpenRouter API.
    Использует OpenAI Python библиотеку (AsyncOpenAI).
    """

    def __init__(self, config, model_name: str = None):
        if isinstance(config, dict):
            config_obj = OpenRouterConfig(**config)
        else:
            config_obj = config

        model_name = model_name or config_obj.model_name
        super().__init__(model_name=model_name, config=config_obj.model_dump())

        self.config_obj = config_obj
        self._client: Optional[AsyncOpenAI] = None
        self._last_request_time = 0.0

    async def initialize(self) -> bool:
        """Инициализация OpenAI клиента."""
        try:
            import httpx
            timeout = httpx.Timeout(self.config_obj.timeout_seconds, connect=30.0)

            self._client = AsyncOpenAI(
                api_key=self.config_obj.api_key,
                base_url=self.config_obj.base_url,
                timeout=timeout,
                max_retries=0,  # Retry обрабатываем вручную
                default_headers={
                    "HTTP-Referer": "https://agent-v5.local",
                    "X-Title": "Agent v5",
                }
            )

            self.is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            self.last_health_check = time.time()

            _logger.info("OpenRouter провайдер инициализирован: %s", self.model_name, extra={"event_type": LogEventType.LLM_RESPONSE})
            return True

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            _logger.error("Ошибка инициализации OpenRouter провайдера: %s\n%s", str(e), tb, extra={"event_type": LogEventType.LLM_ERROR})
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """Закрытие клиента."""
        try:
            if self._client:
                await self._client.close()
            self._client = None
            self.is_initialized = False
        except Exception as e:
            _logger.error("Ошибка при завершении OpenRouter провайдера: %s", str(e), extra={"event_type": LogEventType.LLM_ERROR})

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья через тестовый запрос."""
        try:
            if not self.is_initialized or not self._client:
                return {
                    "status": LLMHealthStatus.UNHEALTHY.value,
                    "error": "Not initialized",
                    "model": self.model_name,
                    "is_initialized": self.is_initialized
                }

            start_time = time.time()
            response = await self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "ОК"}],
                max_tokens=5,
                temperature=0.1
            )
            response_time = time.time() - start_time

            if response.choices and response.choices[0].message.content:
                self.health_status = LLMHealthStatus.HEALTHY
                return {
                    "status": LLMHealthStatus.HEALTHY.value,
                    "model": self.model_name,
                    "response_time_ms": int(response_time * 1000),
                    "is_initialized": self.is_initialized
                }
            else:
                return {
                    "status": LLMHealthStatus.DEGRADED.value,
                    "model": self.model_name,
                    "error": "Empty response",
                    "is_initialized": self.is_initialized
                }

        except Exception as e:
            self.health_status = LLMHealthStatus.UNHEALTHY
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "model": self.model_name,
                "error": str(e),
                "is_initialized": self.is_initialized
            }

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация текста через OpenRouter API.
        Использует OpenAI AsyncOpenAI клиент.
        """
        if not self.is_initialized or not self._client:
            await self.initialize()

        start_time = time.time()
        messages = self._build_messages(request)

        max_retries = 3
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                # Задержка между попытками
                if attempt > 1:
                    wait_time = 5 * attempt
                    _logger.info("⏳ [OPENROUTER] Retry %d/%d, жду %ds...", attempt, max_retries, wait_time, extra={"event_type": LogEventType.LLM_RESPONSE})
                    await asyncio.sleep(wait_time)

                # Вызов через OpenAI клиент — ТОЧНО как в примере пользователя
                response = await self._client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=request.temperature if hasattr(request, 'temperature') and request.temperature else self.config_obj.temperature,
                    max_tokens=request.max_tokens if hasattr(request, 'max_tokens') and request.max_tokens else self.config_obj.max_tokens,
                    extra_body={}  # Как в рабочем примере
                )

                duration_ms = (time.time() - start_time) * 1000

                # Проверяем ответ
                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content or ""
                    finish_reason = response.choices[0].finish_reason or "stop"
                    tokens_used = response.usage.total_tokens if response.usage else 0

                    # Если контент пустой — это ошибка free-модели
                    if not content or not content.strip():
                        if attempt < max_retries:
                            _logger.warning("⚠️ [OPENROUTER] Empty response (attempt %d/%d)", attempt, max_retries, extra={"event_type": LogEventType.WARNING})
                            continue
                        else:
                            return LLMResponse(
                                content="",
                                model=self.model_name,
                                tokens_used=0,
                                generation_time=duration_ms,
                                finish_reason="empty",
                                metadata={"error": "empty_response", "attempts": attempt}
                            )

                    # Успешный ответ
                    if attempt > 1:
                        _logger.info("✅ [OPENROUTER] Успешный ответ с попытки %d", attempt, extra={"event_type": LogEventType.LLM_RESPONSE})

                    return LLMResponse(
                        content=content,
                        model=self.model_name,
                        tokens_used=tokens_used,
                        generation_time=duration_ms,
                        finish_reason=finish_reason,
                        raw_response=RawLLMResponse(
                            content=content,
                            model=self.model_name,
                            tokens_used=tokens_used,
                            generation_time=duration_ms,
                            finish_reason=finish_reason
                        )
                    )
                else:
                    last_error = "No choices in response"
                    continue

            except Exception as e:
                last_error = str(e)
                _logger.error("❌ [OPENROUTER] Ошибка: %s", last_error, extra={"event_type": LogEventType.LLM_ERROR})
                
                if attempt < max_retries:
                    wait_time = 10 * attempt
                    await asyncio.sleep(wait_time)
                continue

        # Все попытки неудачны
        return LLMResponse(
            content="",
            model=self.model_name,
            tokens_used=0,
            generation_time=(time.time() - start_time) * 1000,
            finish_reason="error",
            metadata={"error": last_error, "attempts": max_retries}
        )

    def _build_messages(self, request: LLMRequest) -> List[Dict[str, str]]:
        """Построение списка сообщений из запроса."""
        if request.messages:
            return list(request.messages)

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        return messages

    async def generate_sync(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Синхронная генерация для совместимости."""
        request = LLMRequest(
            messages=messages,
            temperature=kwargs.get("temperature", self.config_obj.temperature),
            max_tokens=kwargs.get("max_tokens", self.config_obj.max_tokens)
        )
        response = await self.generate(request)
        return response.content

    @property
    def is_available(self) -> bool:
        return self.is_initialized and self.health_status == LLMHealthStatus.HEALTHY

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """Реализация генерации для BaseLLMProvider."""
        return await self.generate(request)
