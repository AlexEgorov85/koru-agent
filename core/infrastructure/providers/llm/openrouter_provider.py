"""
Провайдер для OpenRouter API.
Использует OpenAI-совместимый REST API для вызова удалённых LLM моделей.

OpenRouter — агрегатор, предоставляющий единый API к множеству моделей
(OpenAI, Anthropic, Google, Meta и др.) через https://openrouter.ai/api/v1
"""
import asyncio
import time
import json
import re
from typing import Dict, Any, Optional, List

import aiohttp

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.interfaces.llm import LLMInterface
from core.models.types.llm_types import (
    LLMRequest,
    LLMResponse,
    LLMHealthStatus,
    StructuredOutputConfig,
    RawLLMResponse
)
from pydantic import BaseModel, Field


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterConfig(BaseModel):
    """Конфигурация для OpenRouter провайдера."""
    api_key: str = Field(..., description="API ключ OpenRouter")
    model_name: str = Field(default="openai/gpt-4o-mini", description="ID модели в формате openrouter (например openai/gpt-4o-mini)")
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=4096, description="Максимальное количество токенов")
    timeout_seconds: float = Field(default=120.0, ge=0.0, description="Таймаут HTTP запроса")
    base_url: str = Field(default=OPENROUTER_API_URL, description="Базовый URL API")
    extra_headers: Dict[str, str] = Field(default_factory=dict, description="Дополнительные HTTP заголовки")


class OpenRouterProvider(BaseLLMProvider, LLMInterface):
    """
    Провайдер для OpenRouter API.

    Поддерживает:
    - Все модели доступные через OpenRouter
    - Structured output через JSON schema в промпте
    - Streaming (через SSE)
    - Автоматический retry при ошибках сети

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    config = OpenRouterConfig(
        api_key="sk-or-v1-...",
        model_name="anthropic/claude-3.5-sonnet"
    )
    provider = OpenRouterProvider(config=config)
    await provider.initialize()
    response = await provider.generate(request)
    """

    def __init__(self, config, model_name: str = None):
        if isinstance(config, dict):
            config_obj = OpenRouterConfig(**config)
        else:
            config_obj = config

        model_name = model_name or config_obj.model_name
        super().__init__(model_name=model_name, config=config_obj.model_dump())

        self.config_obj = config_obj
        self._session: Optional[aiohttp.ClientSession] = None
        self.event_bus_logger = None

    async def initialize(self) -> bool:
        """Инициализация HTTP сессии и проверка конфигурации."""
        try:
            if self.event_bus_logger is None:
                from core.infrastructure.event_bus.unified_event_bus import get_event_bus
                from core.infrastructure.logging import EventBusLogger
                try:
                    event_bus = get_event_bus()
                    self.event_bus_logger = EventBusLogger(event_bus, "system", "llm_provider", self.__class__.__name__)
                except Exception:
                    self.event_bus_logger = type('obj', (object,), {
                        'info': lambda *args, **kwargs: None,
                        'debug': lambda *args, **kwargs: None,
                        'warning': lambda *args, **kwargs: None,
                        'error': lambda *args, **kwargs: None
                    })()

            await self.event_bus_logger.info(f"Инициализация OpenRouter провайдера: модель={self.model_name}")

            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config_obj.timeout_seconds),
                headers={
                    "Authorization": f"Bearer {self.config_obj.api_key}",
                    "HTTP-Referer": "https://agent-v5.local",
                    "X-Title": "Agent v5",
                    "Content-Type": "application/json",
                    **self.config_obj.extra_headers
                }
            )

            self.is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            self.last_health_check = time.time()

            await self.event_bus_logger.info(f"OpenRouter провайдер инициализирован: {self.model_name}")
            return True

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка инициализации OpenRouter провайдера: {str(e)}")
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """Закрытие HTTP сессии."""
        try:
            if self.event_bus_logger:
                await self.event_bus_logger.info("Завершение работы OpenRouter провайдера...")
            if self._session and not self._session.closed:
                await self._session.close()
            self._session = None
            self.is_initialized = False
            if self.event_bus_logger:
                await self.event_bus_logger.info("OpenRouter провайдер завершён")
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка при завершении OpenRouter провайдера: {str(e)}")

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья через тестовый запрос."""
        try:
            if not self.is_initialized or not self._session:
                return {
                    "status": LLMHealthStatus.UNHEALTHY.value,
                    "error": "Not initialized",
                    "model": self.model_name,
                    "is_initialized": self.is_initialized
                }

            start_time = time.time()
            async with self._session.post(
                self.config_obj.base_url,
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": "Скажи ОК"}],
                    "max_tokens": 5,
                    "temperature": 0.1
                }
            ) as response:
                response_time = time.time() - start_time
                if response.status == 200:
                    return {
                        "status": LLMHealthStatus.HEALTHY.value,
                        "model": self.model_name,
                        "is_initialized": self.is_initialized,
                        "response_time": response_time,
                        "request_count": self.request_count,
                        "error_count": self.error_count
                    }
                else:
                    body = await response.text()
                    return {
                        "status": LLMHealthStatus.UNHEALTHY.value,
                        "error": f"HTTP {response.status}: {body[:200]}",
                        "model": self.model_name,
                        "is_initialized": self.is_initialized
                    }

        except Exception as e:
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self.is_initialized
            }

    def _build_schema_prompt(self, schema_def: Dict[str, Any]) -> str:
        """Формирование промпта с JSON схемой для structured output."""
        simplified_schema = {
            "type": "object",
            "properties": {},
            "required": schema_def.get("required", [])
        }

        for prop_name, prop_def in schema_def.get("properties", {}).items():
            simplified_schema["properties"][prop_name] = {
                "type": prop_def.get("type", "string"),
                "description": prop_def.get("description", "")[:100]
            }

        schema_json = json.dumps(simplified_schema, indent=2, ensure_ascii=False)

        schema_prompt = (
            "\n=== JSON SCHEMA ===\n"
            f"{schema_json}\n"
            "\nКРИТИЧЕСКИ ВАЖНО:\n"
            "1. Верни ТОЛЬКО JSON согласно схеме выше. НИЧЕГО больше.\n"
            "2. НЕ добавляй пояснений, вступлений, заключений или markdown-обёрток.\n"
            "3. НЕ используй triple backticks (```).\n"
            "4. Все обязательные поля (required) должны присутствовать.\n"
            "5. Типы данных должны точно соответствовать схеме.\n"
            "6. Начни ответ с '{' и закончи '}'.\n"
            "\nПример правильного ответа:\n"
            '{"field1": "value1", "field2": 42}\n'
        )

        return schema_prompt

    def _extract_json_from_response(self, content: str) -> str:
        """Извлечь JSON из ответа LLM."""
        json_block_pattern = r'```json\s*\n?(.*?)\n?```'
        matches = re.findall(json_block_pattern, content, re.DOTALL)
        if matches:
            return matches[-1].strip()

        code_block_pattern = r'```\s*\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        if matches:
            for block in reversed(matches):
                block = block.strip()
                if block.startswith('{') and block.endswith('}'):
                    try:
                        json.loads(block)
                        return block
                    except json.JSONDecodeError:
                        continue

        start = content.find('{')
        end = content.rfind('}') + 1

        if start != -1 and end > start:
            candidate = content[start:end]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pos = start + 1
                while pos < len(content):
                    next_start = content.find('{', pos)
                    if next_start == -1:
                        break
                    next_end = content.rfind('}', pos) + 1
                    if next_end <= next_start:
                        break
                    candidate = content[next_start:next_end]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        pos = next_start + 1
                return candidate

        return content.strip()

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация текста через OpenRouter API.

        АРХИТЕКТУРА:
        - ТОЛЬКО выполняет HTTP вызов к API
        - НЕ публикует события (это делает LLMOrchestrator)
        - Возвращает LLMResponse или бросает исключение
        """
        if not self.is_initialized or not self._session:
            await self.initialize()

        start_time = time.time()

        messages = self._build_messages(request)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
        }

        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        if hasattr(request, 'structured_output') and request.structured_output is not None and isinstance(request.structured_output, StructuredOutputConfig):
            schema_prompt = self._build_schema_prompt(request.structured_output.schema_def)
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] += "\n\n" + schema_prompt
            else:
                messages.insert(0, {"role": "system", "content": schema_prompt})
            payload["messages"] = messages

        try:
            async with self._session.post(self.config_obj.base_url, json=payload) as response:
                if response.status != 200:
                    error_body = await response.text()
                    self._update_metrics(time.time() - start_time, success=False)
                    return LLMResponse(
                        content="",
                        model=self.model_name,
                        tokens_used=0,
                        generation_time=time.time() - start_time,
                        finish_reason="error",
                        metadata={
                            "error": f"HTTP {response.status}: {error_body[:500]}",
                            "status_code": response.status
                        }
                    )

                data = await response.json()

        except asyncio.TimeoutError:
            self._update_metrics(time.time() - start_time, success=False)
            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": "Request timeout"}
            )
        except Exception as e:
            self._update_metrics(time.time() - start_time, success=False)
            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": str(e)}
            )

        choices = data.get("choices", [])
        usage = data.get("usage", {})

        if not choices:
            self._update_metrics(time.time() - start_time, success=False)
            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": "No choices in response", "raw_response": str(data)[:500]}
            )

        message = choices[0].get("message", {})
        generated_text = message.get("content", "")
        finish_reason = choices[0].get("finish_reason", "stop")
        tokens_used = usage.get("total_tokens", 0)
        generation_time = time.time() - start_time

        if hasattr(request, 'structured_output') and request.structured_output is not None and isinstance(request.structured_output, StructuredOutputConfig):
            try:
                json_content = self._extract_json_from_response(generated_text)
                parsed_json = json.loads(json_content)

                return LLMResponse(
                    parsed_content=None,
                    raw_response=RawLLMResponse(
                        content=json_content,
                        model=self.model_name,
                        tokens_used=tokens_used,
                        generation_time=generation_time,
                        finish_reason=finish_reason,
                        metadata={"parsed_json": parsed_json}
                    ),
                    model=self.model_name,
                    tokens_used=tokens_used,
                    generation_time=generation_time,
                    parsing_attempts=1,
                    validation_errors=[]
                )
            except (json.JSONDecodeError, Exception) as err:
                return LLMResponse(
                    parsed_content=None,
                    raw_response=RawLLMResponse(
                        content=generated_text,
                        model=self.model_name,
                        tokens_used=tokens_used,
                        generation_time=generation_time,
                        finish_reason="error"
                    ),
                    model=self.model_name,
                    parsing_attempts=1,
                    validation_errors=[{
                        "error": "json_parse_error" if isinstance(err, json.JSONDecodeError) else "exception",
                        "message": str(err)
                    }]
                )

        self._update_metrics(generation_time)

        return LLMResponse(
            content=generated_text,
            model=self.model_name,
            tokens_used=tokens_used,
            generation_time=generation_time,
            finish_reason=finish_reason
        )

    def _build_messages(self, request: LLMRequest) -> List[Dict[str, str]]:
        """Построение списка сообщений из запроса."""
        messages = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        return messages

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """Генерация текста (для совместимости с LLMInterface)."""
        if not self.is_initialized:
            await self.initialize()

        system_prompt = ""
        user_prompt = ""

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_prompt = content
            elif role == "assistant":
                user_prompt += f"\n\nAssistant: {content}"

        request = LLMRequest(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens or self.config_obj.max_tokens,
            stop_sequences=stop_sequences
        )

        response = await self._generate_impl(request)
        return response.content

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Генерация структурированного ответа (для совместимости с LLMInterface)."""
        if not self.is_initialized:
            await self.initialize()

        schema_json = json.dumps(response_schema, ensure_ascii=False)
        system_message = {
            "role": "system",
            "content": f"Ответь ТОЛЬКО валидным JSON согласно этой схеме:\n{schema_json}"
        }

        all_messages = [system_message] + messages

        request = LLMRequest(
            prompt=all_messages[-1]["content"],
            system_prompt="\n".join([m["content"] for m in all_messages[:-1]]),
            temperature=temperature,
            max_tokens=4096
        )

        response = await self._generate_impl(request)

        json_content = self._extract_json_from_response(response.content)
        return json.loads(json_content)

    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Приблизительный подсчёт токенов."""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return total_chars // 4
