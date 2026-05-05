"""
Провайдер для SGLang (Structured Generation Language).
Использует SGLang runtime для локального инференса с нативной поддержкой structured output.

SGLang — высокопроизводительный движок для инференса LLM с фокусом на:
- Эффективное управление памятью через RadixAttention
- Натуральная поддержка constrained decoding (JSON, regex, grammar)
- Оптимизированный scheduling через continuous batching
- Поддержка multimodal моделей

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    import sglang as sgl
    
    @sgl.function
    def text_completion(s, prompt):
        s += prompt
        s += sgl.gen("response", max_tokens=512)
    
    state = text_completion.run(prompt="Hello")
    print(state["response"])
"""
import time
import json
import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.interfaces.llm import LLMInterface
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.infrastructure.providers.llm.json_parser import extract_json_from_response

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


class SGLangConfig(BaseModel):
    """Конфигурация для SGLang провайдера."""
    model_path: str = Field(
        default="meta-llama/Llama-2-7b-chat-hf",
        description="Путь к модели (локальный или HuggingFace)"
    )
    model_name: str = Field(
        default="sglang-model",
        description="Имя модели для логирования"
    )
    tensor_parallel_size: int = Field(
        default=1,
        description="Количество GPU для tensor parallelism"
    )
    mem_fraction_static: float = Field(
        default=0.8,
        ge=0.1,
        le=1.0,
        description="Доля GPU памяти для статического выделения"
    )
    max_running_requests: int = Field(
        default=32,
        description="Максимальное количество параллельных запросов"
    )
    max_total_tokens: Optional[int] = Field(
        default=None,
        description="Максимальное количество токенов в памяти"
    )
    context_length: Optional[int] = Field(
        default=None,
        description="Длина контекста модели"
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
    use_mock: bool = Field(
        default=False,
        description="Использовать mock режим (для тестирования без SGLang)"
    )


class SGLangProvider(BaseLLMProvider, LLMInterface):
    """
    Провайдер для SGLang с локальным инференсом.

    Поддерживает:
    - Все модели, поддерживаемые SGLang
    - Native structured output через JSON schema (constrained decoding)
    - Regex и grammar-based generation
    - Multi-turn диалоги
    - Tool calling (function calling)
    
    ОСОБЕННОСТИ:
    - Использует SGLang runtime для offline inference
    - RadixAttention для эффективного KV cache management
    - Continuous batching для высокой пропускной способности
    - Native JSON schema validation на уровне декодера
    """

    def __init__(self, config, model_name: str = None, log_session: Optional['LoggingSession'] = None):
        if isinstance(config, dict):
            config_obj = SGLangConfig(**config)
        else:
            config_obj = config

        model_name = model_name or config_obj.model_name
        super().__init__(model_name=model_name, config=config_obj.model_dump())

        self.config_obj = config_obj
        self.runtime = None  # SGLang Runtime
        self._log_session = log_session
        self._use_mock = config_obj.use_mock

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
        """Инициализация SGLang runtime и загрузка модели."""
        logger = self._get_logger()

        if self._use_mock:
            logger.info("🔵 [SGLang] Mock режим - инициализация без реального runtime",
                       extra={"event_type": EventType.LLM_RESPONSE})
            self.is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            self.last_health_check = time.time()
            return True

        try:
            logger.info("Загрузка SGLang модели: %s | Путь: %s", 
                       self.model_name, 
                       self.config_obj.model_path,
                       extra={"event_type": EventType.LLM_CALL})

            model_path = self._resolve_model_path(self.config_obj.model_path)

            logger.debug("Параметры инициализации SGLang: tensor_parallel=%d, mem_fraction=%.2f, max_requests=%d, dtype=%s",
                        self.config_obj.tensor_parallel_size,
                        self.config_obj.mem_fraction_static,
                        self.config_obj.max_running_requests,
                        self.config_obj.dtype,
                        extra={"event_type": EventType.LLM_CALL})

            # Импорт SGLang
            import sglang as sgl
            
            # Инициализация runtime
            self.runtime = sgl.Runtime(
                model_path=model_path,
                tensor_parallel_size=self.config_obj.tensor_parallel_size,
                mem_fraction_static=self.config_obj.mem_fraction_static,
                max_running_requests=self.config_obj.max_running_requests,
                max_total_tokens=self.config_obj.max_total_tokens,
                context_length=self.config_obj.context_length,
                dtype=self.config_obj.dtype,
                trust_remote_code=self.config_obj.trust_remote_code,
            )

            # Установка runtime по умолчанию
            sgl.set_default_backend(self.runtime)

            self.is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            self.last_health_check = time.time()

            logger.info("✅ SGLang модель успешно загружена: %s", self.model_name,
                       extra={"event_type": EventType.LLM_RESPONSE})

            return True

        except ImportError as e:
            self.health_status = LLMHealthStatus.UNHEALTHY
            logger.error("❌ SGLang не установлен: %s | Требуется: pip install sglang", str(e),
                        extra={"event_type": EventType.LLM_ERROR})
            return False
        except Exception as e:
            self.health_status = LLMHealthStatus.UNHEALTHY
            logger.error("❌ Ошибка инициализации SGLang провайдера: %s", str(e),
                        extra={"event_type": EventType.LLM_ERROR}, exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Завершение работы SGLang провайдера."""
        logger = self._get_logger()
        try:
            logger.info("Завершение работы SGLang провайдера: %s", self.model_name,
                       extra={"event_type": EventType.LLM_RESPONSE})
            
            if self.runtime:
                self.runtime.shutdown()
            
            self.runtime = None
            self.is_initialized = False
        except Exception as e:
            logger.error("Ошибка при завершении SGLang провайдера: %s", str(e),
                        extra={"event_type": EventType.LLM_ERROR})

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья SGLang провайдера."""
        logger = self._get_logger()
        try:
            if not self.is_initialized:
                logger.warning("SGLang health check: провайдер не инициализирован",
                             extra={"event_type": EventType.WARNING})
                return {
                    "status": LLMHealthStatus.UNHEALTHY.value,
                    "error": "Not initialized",
                    "model": self.model_name,
                    "is_initialized": self.is_initialized
                }

            if self._use_mock:
                return {
                    "status": LLMHealthStatus.HEALTHY.value,
                    "model": self.model_name,
                    "is_initialized": self.is_initialized,
                    "mock_mode": True
                }

            start_time = time.time()

            logger.debug("Выполнение health check для SGLang: %s", self.model_name,
                        extra={"event_type": EventType.LLM_CALL})

            # Простой тестовый запрос
            import sglang as sgl
            
            @sgl.function
            def health_check_fn(s):
                s += "ОК"
                s += sgl.gen("response", max_tokens=5, temperature=0.1)

            result = health_check_fn.run()

            response_time = time.time() - start_time

            logger.info("✅ SGLang health check: OK | Время ответа: %.3fс", response_time,
                       extra={"event_type": EventType.LLM_RESPONSE})

            return {
                "status": LLMHealthStatus.HEALTHY.value,
                "model": self.model_name,
                "is_initialized": self.is_initialized,
                "response_time": response_time,
                "request_count": self.request_count,
                "error_count": self.error_count
            }

        except Exception as e:
            logger.error("❌ SGLang health check failed: %s", str(e),
                        extra={"event_type": EventType.LLM_ERROR})
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self.is_initialized
            }

    def _build_schema_prompt(self, schema_def: Dict[str, Any]) -> str:
        """Формирование промпта с JSON схемой для structured output."""
        schema_json = json.dumps(schema_def, indent=2, ensure_ascii=False)
        return (
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

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """Генерация текста через SGLang."""
        logger = self._get_logger()

        if not self.is_initialized:
            logger.warning("SGLang не инициализирован, выполняется автоматическая инициализация",
                          extra={"event_type": EventType.WARNING})
            await self.initialize()

        start_time = time.time()

        # Ограничение max_tokens для structured output
        if hasattr(request, 'structured_output') and request.structured_output:
            max_tokens = min(request.max_tokens, 4000)
        else:
            max_tokens = request.max_tokens

        # Формирование промпта
        parts = []

        system_prompt = request.system_prompt or ""
        user_prompt = request.prompt or ""

        if system_prompt:
            parts.append(f"<|system|>\n{system_prompt}")

        if user_prompt:
            parts.append(f"<|user|>\n{user_prompt}")

        parts.append("<|assistant|>")

        prompt = "\n".join(parts)

        logger.info("📝 SGLang вызов | Модель: %s | Промт: %d симв. | Max tokens: %d | Temperature: %s",
                    self.model_name, len(prompt), max_tokens, request.temperature,
                    extra={"event_type": EventType.LLM_CALL})

        logger.debug("Промпт SGLang (%d симв.): %s", len(prompt), prompt,
                    extra={"event_type": EventType.LLM_CALL})

        logger.debug("=== ПРОМПТ LLM (ПОЛНЫЙ, RAW) ===\n%s\n=== КОНЕЦ ПРОМПТА ===", prompt,
                    extra={"event_type": EventType.DEBUG})

        if self._use_mock:
            return await self._mock_generate(request, prompt, max_tokens, start_time)

        try:
            import sglang as sgl

            # Подготовка параметров генерации
            gen_params = {
                "temperature": request.temperature,
                "max_tokens": max_tokens,
                "top_p": request.top_p,
            }

            # Добавляем stop sequences если есть
            if request.stop_sequences:
                gen_params["stop"] = request.stop_sequences

            # Structured output через JSON schema
            use_constrained = False
            if hasattr(request, 'structured_output') and request.structured_output:
                # SGLang поддерживает native JSON schema constrained decoding
                try:
                    gen_params["json_schema"] = request.structured_output.schema_def
                    use_constrained = True
                    logger.info("🔵 [SGLang] Constrained decoding активирован: JSON schema",
                               extra={"event_type": EventType.LLM_RESPONSE})
                except Exception as e:
                    logger.warning("⚠️ Не удалось применить JSON schema: %s. Используем fallback.", str(e),
                                  extra={"event_type": EventType.WARNING})

            # Определение функции генерации
            @sgl.function
            def generate_fn(s):
                s += prompt
                if use_constrained:
                    s += sgl.gen("response", **gen_params)
                else:
                    s += sgl.gen("response", **gen_params)

            # Выполнение генерации
            state = generate_fn.run()
            generated_text = state.get("response", "")
            finish_reason = "stop"

            # Получение метаданных из состояния
            tokens_used = getattr(state, 'tokens_used', 0)
            if not tokens_used:
                # Приблизительный подсчёт
                tokens_used = len(generated_text) // 4

            generation_time = time.time() - start_time

            logger.debug("=== СЫРОЙ ОТВЕТ LLM (RAW) ===\n%s\n=== КОНЕЦ СЫРОГО ОТВЕТА ===", generated_text,
                        extra={"event_type": EventType.DEBUG})

            # Обработка structured output
            if hasattr(request, 'structured_output') and request.structured_output:
                if not generated_text or not generated_text.strip():
                    logger.warning("⚠️ SGLang вернул пустой ответ для structured output",
                                  extra={"event_type": EventType.WARNING})
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
                                "warning": "SGLang вернул пустой ответ для structured output запроса"
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

                # Извлечение JSON (на случай если модель добавила обёртку)
                json_content = extract_json_from_response(generated_text)

                try:
                    parsed_json = json.loads(json_content)

                    content_length = len(json_content)
                    logger.info("✅ SGLang structured output | Модель: %s | JSON: %d симв. | Токенов: %s | Время: %.2fс",
                               self.model_name, content_length, tokens_used, generation_time,
                               extra={"event_type": EventType.LLM_RESPONSE})

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
                    logger.error("❌ Ошибка парсинга JSON SGLang: %s", str(err),
                                extra={"event_type": EventType.LLM_ERROR})
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
            logger.info("✅ SGLang ответ | Модель: %s | Ответ: %d симв. | Токенов: %s | Время: %.2fс | Причина: %s",
                       self.model_name, content_length, tokens_used, generation_time, finish_reason,
                       extra={"event_type": EventType.LLM_RESPONSE})

            logger.debug("Ответ SGLang: %s", generated_text,
                        extra={"event_type": EventType.LLM_RESPONSE})

            return LLMResponse(
                content=generated_text,
                model=self.model_name,
                tokens_used=tokens_used,
                generation_time=generation_time,
                finish_reason=finish_reason
            )

        except Exception as e:
            self._update_metrics(time.time() - start_time, success=False)
            logger.error("❌ SGLang ошибка | Модель: %s | %s: %s | Время: %.2fс",
                        self.model_name, type(e).__name__, str(e), time.time() - start_time,
                        extra={"event_type": EventType.LLM_ERROR}, exc_info=True)
            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": str(e)}
            )

    async def _mock_generate(self, request: LLMRequest, prompt: str, max_tokens: int, start_time: float) -> LLMResponse:
        """Mock генерация для тестирования без реального SGLang runtime."""
        logger = self._get_logger()
        logger.info("🔵 [SGLang] Mock генерация", extra={"event_type": EventType.LLM_RESPONSE})

        generation_time = time.time() - start_time

        if hasattr(request, 'structured_output') and request.structured_output:
            # Возвращаем mock JSON согласно схеме
            schema = request.structured_output.schema_def
            mock_data = self._generate_mock_json(schema)
            json_content = json.dumps(mock_data, ensure_ascii=False)

            logger.info("✅ SGLang mock structured output | JSON: %d симв.", len(json_content),
                       extra={"event_type": EventType.LLM_RESPONSE})

            return LLMResponse(
                parsed_content=None,
                raw_response=RawLLMResponse(
                    content=json_content,
                    model=self.model_name,
                    tokens_used=len(json_content) // 4,
                    generation_time=generation_time,
                    finish_reason="stop",
                    metadata={"parsed_json": mock_data, "mock": True}
                ),
                model=self.model_name,
                tokens_used=len(json_content) // 4,
                generation_time=generation_time,
                parsing_attempts=1,
                validation_errors=[]
            )
        else:
            # Возвращаем mock текст
            mock_text = f"Mock response for prompt: {prompt[:50]}..."
            return LLMResponse(
                content=mock_text,
                model=self.model_name,
                tokens_used=len(mock_text) // 4,
                generation_time=generation_time,
                finish_reason="stop",
                metadata={"mock": True}
            )

    def _generate_mock_json(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Генерация mock JSON данных согласно схеме (рекурсивно)."""
        return self._generate_mock_value(schema)
    
    def _generate_mock_value(self, schema: Dict[str, Any], depth: int = 0) -> Any:
        """Рекурсивная генерация mock значения согласно схеме."""
        if depth > 5:  # Защита от бесконечной рекурсии
            return None
            
        field_type = schema.get("type", "string")
        
        if field_type == "string":
            return f"mock_string_{depth}"
        elif field_type == "integer":
            return depth * 10
        elif field_type == "number":
            return float(depth) * 0.5
        elif field_type == "boolean":
            return depth % 2 == 0
        elif field_type == "array":
            items_schema = schema.get("items", {"type": "string"})
            # Генерируем массив из 2 элементов
            return [self._generate_mock_value(items_schema, depth + 1) for _ in range(2)]
        elif field_type == "object":
            properties = schema.get("properties", {})
            result = {}
            for prop_name, prop_schema in properties.items():
                result[prop_name] = self._generate_mock_value(prop_schema, depth + 1)
            return result
        else:
            return None

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

        json_content = extract_json_from_response(response.content)
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
