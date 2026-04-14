"""
Провайдер для vLLM (Very Large Language Model).
Использует локальный инференс через vLLM движок.

vLLM — высокопроизводительный движок для инференса и обслуживания LLM.
Обеспечивает эффективное использование памяти и высокую пропускную способность.
"""
import time
import json
import re
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.interfaces.llm import LLMInterface
from core.infrastructure.logging.event_types import LogEventType

if TYPE_CHECKING:
    from core.infrastructure.logging.session import LoggingSession

from core.models.types.llm_types import (
    LLMRequest,
    LLMResponse,
    LLMHealthStatus,
    StructuredOutputConfig,
    RawLLMResponse
)
from pydantic import BaseModel, Field

# from vllm import LLM, SamplingParams
# from vllm.sampling_params import StructuredOutputsParams


class VLLMConfig(BaseModel):
    """Конфигурация для vLLM провайдера."""
    model_name: str = Field(
        default="meta-llama/Llama-2-7b-chat-hf",
        description="Имя модели на HuggingFace или локальный путь"
    )
    model_path: Optional[str] = Field(
        default=None,
        description="Локальный путь к модели (если отличается от model_name)"
    )
    tensor_parallel_size: int = Field(
        default=1,
        description="Количество GPU для tensor parallelism"
    )
    gpu_memory_utilization: float = Field(
        default=0.9,
        ge=0.1,
        le=1.0,
        description="Доля GPU памяти для KV cache"
    )
    max_num_seqs: int = Field(
        default=256,
        description="Максимальное количество параллельных последовательностей"
    )
    max_model_len: Optional[int] = Field(
        default=None,
        description="Максимальная длина контекста"
    )
    enforce_eager: bool = Field(
        default=True,
        description="Использовать eager execution (без CUDA graphs)"
    )
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=4096, description="Максимальное количество токенов")
    dtype: str = Field(
        default="auto",
        description="Тип данных: auto, float16, bfloat16, float8"
    )
    trust_remote_code: bool = Field(
        default=True,
        description="Доверять remote code при загрузке модели"
    )


class VLLMProvider(BaseLLMProvider, LLMInterface):
    """
    Провайдер для vLLM с локальным инференсом.

    Поддерживает:
    - Все модели, поддерживаемые vLLM
    - Structured output через JSON schema
    - Parallel generation
    - Tool calling (function calling)
    
    ОСОБЕННОСТИ:
    - Использует vLLM LLM class для offline inference
    - Эффективное использование памяти PagedAttention
    - Загружает модель в GPU напрямую
    """

    def __init__(self, config, model_name: str = None, log_session: Optional['LoggingSession'] = None):
        if isinstance(config, dict):
            config_obj = VLLMConfig(**config)
        else:
            config_obj = config

        model_name = model_name or config_obj.model_name
        super().__init__(model_name=model_name, config=config_obj.model_dump())

        self.config_obj = config_obj
        self.llm = None
        self._log_session = log_session

    def _get_logger(self) -> logging.Logger:
        """Получение логгера из log_session или fallback."""
        if self._log_session and self._log_session.infra_logger:
            return self._log_session.infra_logger
        return logging.getLogger(__name__)

    def _resolve_model_path(self, model_path: str) -> str:
        """Разрешение пути к модели."""
        from pathlib import Path

        path = Path(model_path)
        if path.is_absolute():
            return model_path

        project_root = Path(__file__).parent.parent.parent.parent.parent
        resolved = project_root / model_path

        if resolved.exists():
            return str(resolved)

        return model_path

    async def initialize(self) -> bool:
        """Инициализация vLLM движка и загрузка модели."""
        logger = self._get_logger()

        try:
            logger.info("Загрузка vLLM модели: %s | Путь: %s", 
                       self.model_name, 
                       self.config_obj.model_path or self.config_obj.model_name,
                       extra={"event_type": LogEventType.LLM_CALL})

            model_path = self.config_obj.model_path or self.config_obj.model_name
            model_path = self._resolve_model_path(model_path)

            logger.debug("Параметры инициализации vLLM: tensor_parallel=%d, gpu_memory=%.2f, max_num_seqs=%d, dtype=%s",
                        self.config_obj.tensor_parallel_size,
                        self.config_obj.gpu_memory_utilization,
                        self.config_obj.max_num_seqs,
                        self.config_obj.dtype,
                        extra={"event_type": LogEventType.LLM_CALL})

            self.llm = LLM(
                model=model_path,
                tensor_parallel_size=self.config_obj.tensor_parallel_size,
                gpu_memory_utilization=self.config_obj.gpu_memory_utilization,
                max_num_seqs=self.config_obj.max_num_seqs,
                max_model_len=self.config_obj.max_model_len,
                enforce_eager=self.config_obj.enforce_eager,
                dtype=self.config_obj.dtype,
                trust_remote_code=self.config_obj.trust_remote_code,
            )

            self.is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            self.last_health_check = time.time()

            logger.info("✅ vLLM модель успешно загружена: %s", self.model_name,
                       extra={"event_type": LogEventType.LLM_RESPONSE})

            return True

        except ImportError as e:
            self.health_status = LLMHealthStatus.UNHEALTHY
            logger.error("❌ vLLM не установлен: %s | Требуется: pip install vllm", str(e),
                        extra={"event_type": LogEventType.LLM_ERROR})
            return False
        except Exception as e:
            self.health_status = LLMHealthStatus.UNHEALTHY
            logger.error("❌ Ошибка инициализации vLLM провайдера: %s", str(e),
                        extra={"event_type": LogEventType.LLM_ERROR}, exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Завершение работы vLLM провайдера."""
        logger = self._get_logger()
        try:
            logger.info("Завершение работы vLLM провайдера: %s", self.model_name,
                       extra={"event_type": LogEventType.LLM_RESPONSE})
            self.llm = None
            self.is_initialized = False
        except Exception as e:
            logger.error("Ошибка при завершении vLLM провайдера: %s", str(e),
                        extra={"event_type": LogEventType.LLM_ERROR})

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья vLLM провайдера."""
        logger = self._get_logger()
        try:
            if not self.is_initialized or not self.llm:
                logger.warning("vLLM health check: провайдер не инициализирован",
                             extra={"event_type": LogEventType.WARNING})
                return {
                    "status": LLMHealthStatus.UNHEALTHY.value,
                    "error": "Not initialized",
                    "model": self.model_name,
                    "is_initialized": self.is_initialized
                }

            start_time = time.time()

            logger.debug("Выполнение health check для vLLM: %s", self.model_name,
                        extra={"event_type": LogEventType.LLM_CALL})

            result = await self.llm.generate(
                "ОК",
                SamplingParams(temperature=0.1, max_tokens=5)
            )

            response_time = time.time() - start_time

            logger.info("✅ vLLM health check: OK | Время ответа: %.3fс", response_time,
                       extra={"event_type": LogEventType.LLM_RESPONSE})

            return {
                "status": LLMHealthStatus.HEALTHY.value,
                "model": self.model_name,
                "is_initialized": self.is_initialized,
                "response_time": response_time,
                "request_count": self.request_count,
                "error_count": self.error_count
            }

        except Exception as e:
            logger.error("❌ vLLM health check failed: %s", str(e),
                        extra={"event_type": LogEventType.LLM_ERROR})
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self.is_initialized
            }

    def _extract_json_from_response(self, content: str) -> str:
        """Извлечь JSON из ответа LLM."""
        from core.infrastructure.providers.llm.json_parser import extract_json_from_response
        return extract_json_from_response(content)

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """Генерация текста через vLLM."""
        logger = self._get_logger()

        if not self.is_initialized or not self.llm:
            logger.warning("vLLM не инициализирован, выполняется автоматическая инициализация",
                          extra={"event_type": LogEventType.WARNING})
            await self.initialize()

        start_time = time.time()

        if hasattr(request, 'structured_output') and request.structured_output:
            max_tokens = min(request.max_tokens, 4000)
        else:
            max_tokens = request.max_tokens

        # ──────────────────────────────────────────────
        # Явное формирование одного промпта
        # ──────────────────────────────────────────────
        # Архитектура: LLMRequest создаётся с prompt + system_prompt.
        # messages НЕ используется — это legacy от chat-формата.
        # Все вызовы в проекте передают готовый prompt (рендер из YAML).
        #
        # Формат:
        #   <|system|>
        #   {system_prompt}
        #   <|user|>
        #   {prompt}
        #   <|assistant|>
        # ──────────────────────────────────────────────
        parts = []

        system_prompt = request.system_prompt or ""
        user_prompt = request.prompt or ""

        if system_prompt:
            parts.append(f"<|system|>\n{system_prompt}")

        if user_prompt:
            parts.append(f"<|user|>\n{user_prompt}")

        parts.append("<|assistant|>")

        prompt = "\n".join(parts)

        logger.info("📝 vLLM вызов | Модель: %s | Промт: %d симв. | Max tokens: %d | Temperature: %s",
                    self.model_name, len(prompt), max_tokens, request.temperature,
                    extra={"event_type": LogEventType.LLM_CALL})

        logger.debug("Промпт vLLM (%d симв.): %s", len(prompt), prompt,
                    extra={"event_type": LogEventType.LLM_CALL})

        logger.debug("=== ПРОМПТ LLM (ПОЛНЫЙ, RAW) ===\n%s\n=== КОНЕЦ ПРОМПТА ===", prompt,
                    extra={"event_type": LogEventType.DEBUG})

        structured_outputs = None
        if hasattr(request, 'structured_output') and request.structured_output:
            structured_outputs = StructuredOutputsParams(
                json=request.structured_output.schema_def
            )

        sampling_params = SamplingParams(
            temperature=request.temperature,
            max_tokens=max_tokens,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            stop=request.stop_sequences or None,
            structured_outputs=structured_outputs
        )

        try:
            response = self.llm.generate(prompt, sampling_params)

            if response[0].outputs:
                generated_text = response[0].outputs[0].text
                finish_reason = response[0].outputs[0].finish_reason or "stop"
            else:
                generated_text = ''
                finish_reason = 'error'

            tokens_used = len(response[0].promt_token_ids)
            generation_time = time.time() - start_time

            logger.debug("=== СЫРОЙ ОТВЕТ LLM (RAW) ===\n%s\n=== КОНЕЦ СЫРОГО ОТВЕТА ===", generated_text,
                        extra={"event_type": LogEventType.DEBUG})

            if hasattr(request, 'structured_output') and request.structured_output:
                if not generated_text or not generated_text.strip():
                    logger.warning("⚠️ vLLM вернул пустой ответ для structured output",
                                  extra={"event_type": LogEventType.WARNING})
                    return LLMResponse(
                        parsed_content=None,
                        raw_response=RawLLMResponse(
                            content="",
                            model=self.model_name,
                            tokens_used=tokens_used,
                            generation_time=generation_time,
                            finish_reason="empty",
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

                    content_length = len(json_content)
                    logger.info("✅ vLLM structured output | Модель: %s | JSON: %d симв. | Токенов: %s | Время: %.2fс",
                               self.model_name, content_length, tokens_used, generation_time,
                               extra={"event_type": LogEventType.LLM_RESPONSE})

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
                    logger.error("❌ Ошибка парсинга JSON vLLM: %s", str(err),
                                extra={"event_type": LogEventType.LLM_ERROR})
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

            # Проверка на пустой ответ для не-structured режима
            if not generated_text or not generated_text.strip():
                return LLMResponse(
                    content="",
                    model=self.model_name,
                    tokens_used=tokens_used,
                    generation_time=generation_time,
                    finish_reason="empty",
                    metadata={"error": "empty_response"}
                )

            self._update_metrics(generation_time)

            content_length = len(generated_text) if generated_text else 0
            logger.info("✅ vLLM ответ | Модель: %s | Ответ: %d симв. | Токенов: %s | Время: %.2fс | Причина: %s",
                       self.model_name, content_length, tokens_used, generation_time, finish_reason,
                       extra={"event_type": LogEventType.LLM_RESPONSE})

            logger.debug("Ответ vLLM: %s", generated_text,
                        extra={"event_type": LogEventType.LLM_RESPONSE})

            return LLMResponse(
                content=generated_text,
                model=self.model_name,
                tokens_used=tokens_used,
                generation_time=generation_time,
                finish_reason=finish_reason
            )

        except Exception as e:
            self._update_metrics(time.time() - start_time, success=False)
            logger.error("❌ vLLM ошибка | Модель: %s | %s: %s | Время: %.2fс",
                        self.model_name, type(e).__name__, str(e), time.time() - start_time,
                        extra={"event_type": LogEventType.LLM_ERROR}, exc_info=True)
            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": str(e)}
            )

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
        """Подсчёт токенов (приблизительный, без tokenizer)."""
        # Формируем промпт как в _generate_impl
        parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                parts.append(f"<|system|>\n{content}")
            elif role == 'user':
                parts.append(f"<|user|>\n{content}")
            elif role == 'assistant':
                parts.append(f"<|assistant|>\n{content}")
        parts.append("<|assistant|>")
        prompt = "\n".join(parts)

        # Приблизительный подсчёт: ~4 символа на токен для большинства моделей
        return len(prompt) // 4
