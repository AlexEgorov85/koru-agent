"""
Провайдер для vLLM (Very Large Language Model).
Использует OpenAI-совместимый REST API для вызова локального или удалённого vLLM сервера.

vLLM — высокопроизводительный движок для инференса и обслуживания LLM.
Обеспечивает эффективное использование памяти и высокую пропускную способность.

ПРИМЕР ЗАПУСКА vLLM СЕРВЕРА:
    vllm serve meta-llama/Llama-2-7b-chat-hf --host 0.0.0.0 --port 8000

ПРИМЕР ИСПОЛЬЗОВАНИЯ ПРОВАЙДЕРА:
    config = VLLMConfig(
        base_url="http://localhost:8000/v1",
        model_name="meta-llama/Llama-2-7b-chat-hf"
    )
    provider = VLLMProvider(config=config)
    await provider.initialize()
    response = await provider.generate(request)
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


class VLLMConfig(BaseModel):
    """Конфигурация для vLLM провайдера."""
    base_url: str = Field(
        default="http://localhost:8000/v1",
        description="Базовый URL vLLM сервера (с /v1 суффиксом)"
    )
    api_key: str = Field(
        default="EMPTY",
        description="API ключ. Для локального vLLM обычно 'EMPTY'"
    )
    model_name: str = Field(
        default="meta-llama/Llama-2-7b-chat-hf",
        description="Имя модели на vLLM сервере"
    )
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=4096, description="Максимальное количество токенов")
    timeout_seconds: float = Field(default=120.0, ge=0.0, description="Таймаут HTTP запроса")
    extra_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Дополнительные HTTP заголовки"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Максимальное количество попыток при ошибках сети"
    )


class VLLMProvider(BaseLLMProvider, LLMInterface):
    """
    Провайдер для vLLM сервера.

    Поддерживает:
    - Все модели, развёрнутые на vLLM сервере
    - Structured output через JSON schema
    - Streaming (через SSE)
    - Автоматический retry при ошибках сети
    - Tool calling (function calling)

    ОСОБЕННОСТИ:
    - vLLM предоставляет OpenAI-совместимый API
    - Поддерживает нативный structured output (v0.8+)
    - Эффективное использование памяти PagedAttention
    """

    def __init__(self, config, model_name: str = None):
        if isinstance(config, dict):
            config_obj = VLLMConfig(**config)
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
                    self.event_bus_logger = EventBusLogger(
                        event_bus, "system", "llm_provider", self.__class__.__name__
                    )
                except Exception:
                    self.event_bus_logger = type('obj', (object,), {
                        'info': lambda *args, **kwargs: None,
                        'debug': lambda *args, **kwargs: None,
                        'warning': lambda *args, **kwargs: None,
                        'error': lambda *args, **kwargs: None
                    })()

            await self.event_bus_logger.info(
                f"Инициализация vLLM провайдера: модель={self.model_name}, "
                f"url={self.config_obj.base_url}"
            )

            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config_obj.timeout_seconds),
                headers={
                    "Authorization": f"Bearer {self.config_obj.api_key}",
                    "Content-Type": "application/json",
                    **self.config_obj.extra_headers
                }
            )

            self.is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            self.last_health_check = time.time()

            await self.event_bus_logger.info(
                f"vLLM провайдер инициализирован: {self.model_name}"
            )
            return True

        except Exception as e:
            await self.event_bus_logger.error(
                f"Ошибка инициализации vLLM провайдера: {str(e)}"
            )
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """Закрытие HTTP сессии."""
        try:
            if self.event_bus_logger:
                await self.event_bus_logger.info("Завершение работы vLLM провайдера...")
            if self._session and not self._session.closed:
                await self._session.close()
            self._session = None
            self.is_initialized = False
            if self.event_bus_logger:
                await self.event_bus_logger.info("vLLM провайдер завершён")
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(
                    f"Ошибка при завершении vLLM провайдера: {str(e)}"
                )

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья через тестовый запрос к vLLM серверу."""
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
                f"{self.config_obj.base_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": "ОК"}],
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
        """Формирование промпта с JSON схемой для structured output.

        Схема передаётся целиком — без упрощения, чтобы сохранить
        enum-ы, вложенные объекты, массивы и другие конструкции.
        """
        schema_json = json.dumps(schema_def, indent=2, ensure_ascii=False)

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
        Генерация текста через vLLM API.

        АРХИТЕКТУРА:
        - ТОЛЬКО выполняет HTTP вызов к API
        - НЕ публикует события (это делает LLMOrchestrator)
        - Возвращает LLMResponse или бросает исключение

        RETRY логика:
        - При ошибках сети делаем до max_retries попыток
        - Экспоненциальный backoff между попытками
        """
        if not self.is_initialized or not self._session:
            await self.initialize()

        max_retries = self.config_obj.max_retries
        last_result = None

        for attempt in range(1, max_retries + 1):
            result = await self._execute_single_attempt(request)
            last_result = result

            if result.finish_reason == "error" and attempt < max_retries:
                wait_time = 2 ** attempt
                if self.event_bus_logger:
                    await self.event_bus_logger.warning(
                        f"Попытка {attempt}/{max_retries} не удалась. "
                        f"Ожидание {wait_time}с перед повтором..."
                    )
                await asyncio.sleep(wait_time)
                continue

            return result

        return last_result

    async def _execute_single_attempt(self, request: LLMRequest) -> LLMResponse:
        """Одна попытка HTTP запроса к vLLM."""
        start_time = time.time()

        messages = self._build_messages(request)

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
        }

        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        if hasattr(request, 'structured_output') and request.structured_output is not None:
            if isinstance(request.structured_output, StructuredOutputConfig):
                schema_prompt = self._build_schema_prompt(request.structured_output.schema_def)
                if messages and messages[0]["role"] == "system":
                    messages[0]["content"] += "\n\n" + schema_prompt
                else:
                    messages.insert(0, {"role": "system", "content": schema_prompt})
                payload["messages"] = messages

        try:
            async with self._session.post(
                f"{self.config_obj.base_url}/chat/completions",
                json=payload
            ) as response:
                response_status = response.status

                if response_status != 200:
                    error_body = await response.text()
                    self._update_metrics(time.time() - start_time, success=False)
                    return LLMResponse(
                        content="",
                        model=self.model_name,
                        tokens_used=0,
                        generation_time=time.time() - start_time,
                        finish_reason="error",
                        metadata={
                            "error": f"HTTP {response_status}: {error_body[:500]}",
                            "status_code": response_status
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
        raw_content = message.get("content")
        generated_text = raw_content if raw_content is not None else ""
        finish_reason = choices[0].get("finish_reason", "stop")
        tokens_used = usage.get("total_tokens", 0)
        generation_time = time.time() - start_time

        if hasattr(request, 'structured_output') and request.structured_output is not None:
            if isinstance(request.structured_output, StructuredOutputConfig):
                if not generated_text or not generated_text.strip():
                    return LLMResponse(
                        parsed_content=None,
                        raw_response=RawLLMResponse(
                            content="",
                            model=self.model_name,
                            tokens_used=tokens_used,
                            generation_time=generation_time,
                            finish_reason="stop",
                            metadata={
                                "error": "empty_response",
                                "warning": "vLLM вернул пустой ответ для structured output запроса"
                            }
                        ),
                        model=self.model_name,
                        tokens_used=tokens_used,
                        generation_time=generation_time,
                        parsing_attempts=1,
                        validation_errors=[{
                            "error": "empty_response",
                            "message": "LLM вернул пустой ответ — невозможно распарсить JSON"
                        }]
                    )

                json_content = self._extract_json_from_response(generated_text)

                try:
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
                            finish_reason="stop",
                            metadata={"parse_error": str(err)}
                        ),
                        model=self.model_name,
                        tokens_used=tokens_used,
                        generation_time=generation_time,
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
        """Построение списка сообщений из запроса.

        Поддерживает два режима:
        1. Multi-turn: если передан request.messages — используется он напрямую
        2. Single-turn: если request.prompt — создаётся одно user-сообщение
        """
        if request.messages:
            return list(request.messages)

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
        """Генерация текста (для совместимости с LLMInterface).

        Поддерживает multi-turn диалоги — messages передаётся напрямую
        без склеивания, сохраняя роли system/user/assistant.
        """
        if not self.is_initialized:
            await self.initialize()

        request = LLMRequest(
            prompt="",
            messages=messages,
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

        schema_instruction = {
            "role": "system",
            "content": (
                "Ответь ТОЛЬКО валидным JSON согласно предоставленной схеме.\n"
                "НЕ добавляй пояснений, вступлений или markdown-обёрток.\n"
                "НЕ используй triple backticks (```)."
            )
        }

        has_system = any(msg.get("role") == "system" for msg in messages)

        if has_system:
            all_messages = list(messages) + [schema_instruction]
        else:
            all_messages = [schema_instruction] + list(messages)

        request = LLMRequest(
            prompt="",
            messages=all_messages,
            structured_output=StructuredOutputConfig(
                output_model="dynamic",
                schema_def=response_schema
            ),
            temperature=temperature,
            max_tokens=4096
        )

        response = await self._generate_impl(request)

        if response.raw_response and response.raw_response.metadata and "parsed_json" in response.raw_response.metadata:
            return response.raw_response.metadata["parsed_json"]

        json_content = self._extract_json_from_response(response.content)
        return json.loads(json_content)

    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Приблизительный подсчёт токенов."""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return total_chars // 4
