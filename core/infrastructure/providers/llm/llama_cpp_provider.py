"""
Провайдер для Llama.cpp.
Использует llama-cpp-python для запуска LLM моделей локально.
"""
import asyncio
import time
import json
import re
import logging
from typing import Dict, Any, Optional, Type, List, TYPE_CHECKING
from contextlib import asynccontextmanager

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
from pydantic import BaseModel, Field, ValidationError, create_model


class StructuredOutputError(Exception):
    """
    Ошибка структурированного вывода.
    
    Возникает когда не удалось получить валидный JSON от LLM после всех попыток.
    
    ATTRIBUTES:
    - message: Сообщение об ошибке
    - model_name: Имя модели которая не смогла сгенерировать ответ
    - attempts: Количество попыток генерации
    - correlation_id: ID для трассировки запроса
    - validation_errors: Список ошибок валидации из всех попыток
    """
    
    def __init__(
        self, 
        message: str, 
        model_name: str, 
        attempts: int, 
        correlation_id: str = None,
        validation_errors: list = None
    ):
        super().__init__(message)
        self.model_name = model_name
        self.attempts = attempts
        self.correlation_id = correlation_id
        self.validation_errors = validation_errors or []
    
    def __str__(self):
        base = f"{self.model_name}: {self.message} (попыток: {self.attempts})"
        if self.correlation_id:
            base += f" [correlation_id: {self.correlation_id}]"
        return base


class LlamaCppConfig(BaseModel):
    """Конфигурация для LlamaCpp провайдера."""
    model_path: str = Field(default="models/default_model.gguf", description="Путь к модели GGUF")
    model_name: str = Field(default="llama-model", description="Имя модели")
    n_ctx: int = Field(default=2048, description="Размер контекста")
    n_threads: int = Field(default=4, description="Количество потоков CPU")
    n_gpu_layers: int = Field(default=0, description="Количество слоев для GPU")
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=512, description="Максимальное количество токенов")
    verbose: bool = Field(default=False, description="Подробный вывод")
    timeout_seconds: float = Field(default=600.0, ge=0.0, description="Таймаут ожидания ответа от LLM в секундах")


# Для обратной совместимости с существующим кодом
MockLlamaCppConfig = LlamaCppConfig


class LlamaCppProvider(BaseLLMProvider, LLMInterface):
    """
    Провайдер для Llama.cpp с использованием llama-cpp-python.
    Обеспечивает локальный запуск LLM моделей.
    """

    def __init__(self, config, model_name: str = None, log_session: Optional['LoggingSession'] = None):
        """
        Инициализация Llama.cpp провайдера.
        :param config: Конфигурация подключения (LlamaCppConfig или dict)
        :param model_name: Имя модели (если передано отдельно)
        :param log_session: Сессия логирования для получения логгера
        """
        # Если передан словарь, создаем конфигурацию
        if isinstance(config, dict):
            config_obj = LlamaCppConfig(**config)
        else:
            config_obj = config

        model_name = model_name or config_obj.model_name
        super().__init__(model_name=model_name, config=config_obj.model_dump())

        self.config_obj = config_obj
        self.model_path = config_obj.model_path
        self.n_ctx = config_obj.n_ctx
        self.n_threads = config_obj.n_threads
        self.n_gpu_layers = config_obj.n_gpu_layers
        self.verbose = config_obj.verbose
        self.temperature = config_obj.temperature
        self.timeout_seconds = config_obj.timeout_seconds

        self.llm = None
        self._executor = None  # ThreadPoolExecutor для LLM вызовов
        self._log_session = log_session

        # Контекст вызова теперь управляется в BaseLLMProvider
        # set_call_context() наследуется из базового класса

    def _get_logger(self) -> logging.Logger:
        """Получение логгера из log_session или fallback."""
        if self._log_session and self._log_session.infra_logger:
            return self._log_session.infra_logger
        return logging.getLogger(__name__)

    async def initialize(self) -> bool:
        """
        Асинхронная инициализация LLM инстанса.
        """
        try:
            self._get_logger().info("Загрузка модели из: %s", self.model_path, extra={"event_type": LogEventType.LLM_RESPONSE})
            start_time = time.time()

            # Инициализация Llama.cpp инстанса
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose
            )

            # Создание ThreadPoolExecutor для LLM вызовов
            from concurrent.futures import ThreadPoolExecutor
            self._executor = ThreadPoolExecutor(
                max_workers=2,  # 2 worker для предотвращения блокировок
                thread_name_prefix='llm_worker'
            )

            # Проверка загрузки модели
            if self.llm:
                self.is_initialized = True
                self.health_status = LLMHealthStatus.HEALTHY
                self.last_health_check = time.time()

                init_time = time.time() - start_time
                self._get_logger().info("Llama.cpp провайдер успешно инициализирован за %.2f секунд", init_time, extra={"event_type": LogEventType.LLM_RESPONSE})
                self._get_logger().info("Контекст: %d, потоки: %d, executor workers: 2", self.n_ctx, self.n_threads, extra={"event_type": LogEventType.LLM_RESPONSE})

                return True
            else:
                self._get_logger().error("Не удалось инициализировать LLM инстанс", extra={"event_type": LogEventType.LLM_ERROR})
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False

        except ImportError as e:
            self._get_logger().error("Ошибка импорта llama-cpp-python: %s", str(e), extra={"event_type": LogEventType.LLM_ERROR})
            self._get_logger().error("Установите с помощью: pip install llama-cpp-python", extra={"event_type": LogEventType.LLM_ERROR})
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False
        except ValueError as e:
            if "not enough values to unpack" in str(e):
                self._get_logger().error("Проблема с установкой llama-cpp-python: %s", str(e), extra={"event_type": LogEventType.LLM_ERROR})
                self._get_logger().error("Возможно, требуется переустановка: pip uninstall llama-cpp-python && pip install llama-cpp-python", extra={"event_type": LogEventType.LLM_ERROR})
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
            else:
                self._get_logger().error("Ошибка инициализации Llama.cpp провайдера: %s", str(e), extra={"event_type": LogEventType.LLM_ERROR})
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
        except Exception as e:
            self._get_logger().error("Ошибка инициализации Llama.cpp провайдера: %s", str(e), extra={"event_type": LogEventType.LLM_ERROR})
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """
        Корректное завершение работы провайдера.
        """
        try:
            self._get_logger().info("Завершение работы Llama.cpp провайдера...", extra={"event_type": LogEventType.LLM_RESPONSE})

            # Остановка ThreadPoolExecutor
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
                self._get_logger().debug("ThreadPoolExecutor остановлен", extra={"event_type": LogEventType.DEBUG})

            # В llama-cpp-python нет явного метода для освобождения ресурсов
            # Но можно обнулить ссылку на модель
            self.llm = None
            self.is_initialized = False
            self._get_logger().info("Llama.cpp провайдер успешно завершен", extra={"event_type": LogEventType.LLM_RESPONSE})
        except Exception as e:
            self._get_logger().error("Ошибка при завершении работы Llama.cpp провайдера: %s", str(e), extra={"event_type": LogEventType.LLM_ERROR})

    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья Llama.cpp провайдера.
        """
        try:
            if not self.is_initialized or not self.llm:
                return {
                    "status": LLMHealthStatus.UNHEALTHY.value,
                    "error": "Model not initialized",
                    "model": self.model_name,
                    "is_initialized": self.is_initialized
                }

            # Выполняем короткий тестовый запрос для проверки работоспособности
            start_time = time.time()
            test_response = self.llm(
                "Привет. Кратко скажи 'ОК'.",
                max_tokens=5,
                temperature=0.1,
                echo=False
            )
            
            response_time = time.time() - start_time
            
            return {
                "status": LLMHealthStatus.HEALTHY.value,
                "model": self.model_name,
                "is_initialized": self.is_initialized,
                "response_time": response_time,
                "test_output_length": len(test_response.get('choices', [])),
                "request_count": self.request_count,
                "error_count": self.error_count
            }

        except Exception as e:
            self._get_logger().error("Ошибка health check для Llama.cpp: %s", str(e), extra={"event_type": LogEventType.LLM_ERROR})
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self.is_initialized
            }

    def _build_schema_prompt(self, schema_def: Dict[str, Any]) -> str:
        """
        Формирование промпта с JSON схемой для structured output.

        АРХИТЕКТУРА:
        - Provider сам решает как добавить схему в промпт
        - Схема добавляется в system_prompt или user prompt
        - Формат зависит от возможностей модели

        ПАРАМЕТРЫ:
        - schema_def: JSON Schema определения ответа

        ВОЗВРАЩАЕТ:
        - str: Текст промпта с инструкцией и схемой
        """
        import json
        
        schema_json = json.dumps(schema_def, indent=2, ensure_ascii=False)
        
        # Формируем строгую инструкцию с акцентом на JSON-only вывод
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

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Реализация генерации текста для Llama.cpp.

        АРХИТЕКТУРА:
        - ТОЛЬКО выполняет вызов модели
        - НЕ публикует события (это делает LLMOrchestrator)
        - НЕ логирует (это делает LLMOrchestrator через события)
        - Возвращает LLMResponse или бросает исключение

        STRUCTURED OUTPUT:
        - Если request.structured_output — добавляет схему в промпт
        - Схема добавляется в system_prompt или user prompt
        - Provider сам решает формат промпта
        """
        self._get_logger().info("🔵 [LLM] _generate_impl started: prompt_len=%d, structured_output=%s", len(request.prompt), hasattr(request, 'structured_output') and request.structured_output is not None, extra={"event_type": LogEventType.LLM_RESPONSE})

        if not self.is_initialized or not self.llm:
            self._get_logger().warning("LLM не инициализирован! Вызываем initialize()...", extra={"event_type": LogEventType.WARNING})
            await self.initialize()

        start_time = time.time()

        # === ПОДГОТОВКА ПРОМПТА ===
        prompt = request.prompt
        system_prompt = request.system_prompt or ""

        # ✅ Если есть structured_output — добавляем схему в промпт
        if hasattr(request, 'structured_output') and request.structured_output:
            max_tokens = min(request.max_tokens, 4000)
            self._get_logger().info("🔵 [LLM] Structured output активирован: model=%s", request.structured_output.output_model, extra={"event_type": LogEventType.LLM_RESPONSE})

            schema_prompt = self._build_schema_prompt(request.structured_output.schema_def)
            system_prompt = system_prompt + "\n\n" + schema_prompt

            self._get_logger().info("🔵 [LLM] Схема добавлена в system_prompt (длина: %d символов)", len(schema_prompt), extra={"event_type": LogEventType.LLM_RESPONSE})
            self._get_logger().debug("\n" + "=" * 80, extra={"event_type": LogEventType.DEBUG})
            self._get_logger().debug("📋 PROMPT WITH JSON SCHEMA (LlamaCppProvider)", extra={"event_type": LogEventType.DEBUG})
            self._get_logger().debug("=" * 80, extra={"event_type": LogEventType.DEBUG})
            self._get_logger().debug("\n=== SYSTEM (со схемой) ===", extra={"event_type": LogEventType.DEBUG})
            self._get_logger().debug(system_prompt, extra={"event_type": LogEventType.DEBUG})
            self._get_logger().debug("\n=== USER ===", extra={"event_type": LogEventType.DEBUG})
            self._get_logger().debug(prompt, extra={"event_type": LogEventType.DEBUG})
            self._get_logger().debug("\n" + "=" * 80, extra={"event_type": LogEventType.DEBUG})
        else:
            max_tokens = request.max_tokens

        # Проверка что модель инициализирована
        if not self.llm:
            self._get_logger().warning("⚠️ [LLM] Модель не инициализирована! Вызываем initialize()...", extra={"event_type": LogEventType.WARNING})
            await self.initialize()

        # Создаем executor если не создан
        if not self._executor:
            from concurrent.futures import ThreadPoolExecutor
            self._executor = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix='llm_worker'
            )

        # Выполняем вызов модели в потоке
        import threading
        import asyncio

        def _call_llm_sync():
            """Синхронный вызов модели."""
            if not self.llm:
                raise RuntimeError("LLM модель не загружена")

            # ✅ llama-cpp-python НЕ поддерживает system_prompt отдельным параметром
            # Объединяем system_prompt + prompt в один текст
            full_prompt = prompt
            if system_prompt:
                full_prompt = system_prompt + "\n\n" + prompt

            return self.llm(
                full_prompt,  # ← system_prompt уже в prompt
                max_tokens=max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                frequency_penalty=request.frequency_penalty,
                presence_penalty=request.presence_penalty,
                echo=False,
                stop=request.stop_sequences or None
            )

        try:
            # Проверяем, выполняемся ли мы уже в потоке executor'а
            current_thread = threading.current_thread()
            is_executor_thread = current_thread.name.startswith('llm_worker') or \
                                 current_thread.name.startswith('llm_orchestrator')

            # Логируем полный промпт перед вызовом
            full_prompt_for_log = prompt
            if system_prompt:
                full_prompt_for_log = system_prompt + "\n\n" + prompt
            
            self._get_logger().debug("=== ПРОМПТ LLM (ПОЛНЫЙ, RAW) ===\n%s\n=== КОНЕЦ ПРОМПТА ===", full_prompt_for_log,
                                    extra={"event_type": LogEventType.DEBUG})

            if is_executor_thread:
                # Уже в потоке - вызываем напрямую
                response = _call_llm_sync()
            else:
                # Не в потоке - используем run_in_executor (без таймаута)
                response = await asyncio.get_event_loop().run_in_executor(
                    self._executor, _call_llm_sync
                )

            # Обрабатываем результат
            choices = response.get('choices', [])
            usage = response.get('usage', {})

            msg = f"🔵 [LLM] Получен ответ: choices={len(choices)}"
            self._get_logger().info(msg, extra={"event_type": LogEventType.LLM_RESPONSE})

            if choices:
                generated_text = choices[0].get('text', '')
                finish_reason = choices[0].get('finish_reason', 'stop')

                self._get_logger().debug("=== СЫРОЙ ОТВЕТ LLM (RAW) ===\n%s\n=== КОНЕЦ СЫРОГО ОТВЕТА ===", generated_text,
                                        extra={"event_type": LogEventType.DEBUG})

                self._get_logger().info("🔵 [LLM] generated_text: %d символов", len(generated_text), extra={"event_type": LogEventType.LLM_RESPONSE})
                self._get_logger().info("🔵 [LLM] finish_reason: %s", finish_reason, extra={"event_type": LogEventType.LLM_RESPONSE})
            else:
                generated_text = ''
                finish_reason = 'error'
                self._get_logger().warning("⚠️ [LLM] choices пуст!", extra={"event_type": LogEventType.WARNING})

            # Проверка на пустой ответ (для structured output и обычного режима)
            if not generated_text or not generated_text.strip():
                self._get_logger().warning("⚠️ [LLM] generated_text пустой или содержит только пробелы", extra={"event_type": LogEventType.WARNING})
                return LLMResponse(
                    content="",
                    model=self.model_name,
                    tokens_used=usage.get('total_tokens', 0),
                    generation_time=time.time() - start_time,
                    finish_reason="empty",
                    metadata={"error": "empty_response"}
                )

            # === ОБРАБОТКА STRUCTURED OUTPUT ===
            if hasattr(request, 'structured_output') and request.structured_output:
                self._get_logger().info("🔵 Structured output запрошен: %s", request.structured_output.output_model, extra={"event_type": LogEventType.LLM_RESPONSE})

                # Логирование сырого ответа
                self._get_logger().info("🔵 [LLM] Raw response: %s...", generated_text[:100], extra={"event_type": LogEventType.LLM_RESPONSE})

                try:
                    json_content = self._extract_json_from_response(generated_text)

                    self._get_logger().debug("🔵 JSON извлечён: %s...", json_content[:100], extra={"event_type": LogEventType.DEBUG})
                    parsed_json = json.loads(json_content)
                    self._get_logger().info("✅ JSON распарсен: ключи=%s", list(parsed_json.keys()), extra={"event_type": LogEventType.LLM_RESPONSE})

                    # ✅ Сохраняем JSON в raw_response.content И в content для совместимости
                    # ✅ parsed_content=None — оркестратор создаст Pydantic модель
                    response = LLMResponse(
                        content=json_content,  # ← ВАЖНО: для fallback чтения!
                        parsed_content=None,  # ← Оркестратор заполнит
                        raw_response=RawLLMResponse(
                            content=json_content,  # ← JSON строка для валидации
                            model=self.model_name,
                            tokens_used=usage.get('total_tokens', 0),
                            generation_time=time.time() - start_time,
                            finish_reason=finish_reason,
                            metadata={"parsed_json": parsed_json}  # ← dict для отладки
                        ),
                        model=self.model_name,
                        tokens_used=usage.get('total_tokens', 0),
                        generation_time=time.time() - start_time,
                        parsing_attempts=1,
                        validation_errors=[]
                    )

                    self._get_logger().info("✅ LLMResponse создан (JSON в raw_response.content)", extra={"event_type": LogEventType.LLM_RESPONSE})

                    self._update_metrics(response.generation_time)

                    return response

                except json.JSONDecodeError as json_err:
                    # ❌ Ошибка парсинга JSON — возвращаем LLMResponse с ошибкой
                    self._get_logger().error("❌ Structured output JSON parse error: %s", json_err, extra={"event_type": LogEventType.LLM_ERROR})
                    
                    return LLMResponse(
                        parsed_content=None,
                        raw_response=RawLLMResponse(
                            content=generated_text,  # ← Сырой текст
                            model=self.model_name,
                            tokens_used=usage.get('total_tokens', 0),
                            generation_time=time.time() - start_time,
                            finish_reason="error"
                        ),
                        model=self.model_name,
                        parsing_attempts=1,
                        validation_errors=[{
                            "error": "json_parse_error",
                            "message": str(json_err)
                        }]
                    )
                    
                except Exception as struct_err:
                    # ❌ Другая ошибка — возвращаем LLMResponse с ошибкой
                    self._get_logger().error("❌ Structured output error: %s", struct_err, extra={"event_type": LogEventType.LLM_ERROR})
                    
                    return LLMResponse(
                        parsed_content=None,
                        raw_response=RawLLMResponse(
                            content=generated_text,
                            model=self.model_name,
                            tokens_used=usage.get('total_tokens', 0),
                            generation_time=time.time() - start_time,
                            finish_reason="error"
                        ),
                        model=self.model_name,
                        parsing_attempts=1,
                        validation_errors=[{
                            "error": "exception",
                            "message": str(struct_err)
                        }]
                    )

            # ❌ УДАЛЕНО: Возврат LLMResponse для structured output
            # ТЕПЕРЬ: Всегда возвращаем LLMResponse для структурированных запросов
            self._get_logger().error("❌ [LLM] Structured output запрос, но не удалось сгенерировать ответ", extra={"event_type": LogEventType.LLM_ERROR})
            
            return LLMResponse(
                parsed_content=None,
                raw_response=RawLLMResponse(
                    content=generated_text,
                    model=self.model_name,
                    tokens_used=usage.get('total_tokens', 0),
                    generation_time=time.time() - start_time,
                    finish_reason="error"
                ),
                parsing_attempts=1,
                validation_errors=[{
                    "error": "unknown",
                    "message": "Не удалось получить структурированный ответ"
                }]
            )

        except Exception as e:
            # Возвращаем ошибку без логирования (это делает LLMOrchestrator)
            self._update_metrics(time.time() - start_time, success=False)

            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": str(e)}
            )

    @asynccontextmanager
    async def session(self):
        """
        Контекстный менеджер для сессии работы с LLM.
        """
        if not self.is_initialized or not self.llm:
            await self.initialize()

        try:
            yield self
        except Exception as e:
            self._get_logger().error("Ошибка в сессии Llama.cpp: %s", str(e), extra={"event_type": LogEventType.LLM_ERROR})
            raise

    # Методы для совместимости с LLMInterface
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """
        Сгенерировать текстовый ответ (для совместимости с LLMInterface).
        """
        if not self.is_initialized or not self.llm:
            await self.initialize()

        # Форматируем сообщения в промт
        prompt = self._format_messages_to_prompt(messages)

        # Создаём запрос
        request = LLMRequest(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens or self.config_obj.max_tokens,
            stop_sequences=stop_sequences
        )

        # Выполняем генерацию
        response = await self._generate_impl(request)
        return response.content

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Сгенерировать структурированный ответ (для совместимости с LLMInterface).
        """
        if not self.is_initialized or not self.llm:
            await self.initialize()

        # Добавляем инструкцию для JSON вывода
        schema_json = json.dumps(response_schema, ensure_ascii=False)
        system_message = {
            "role": "system",
            "content": f"Ответь ТОЛЬКО валидным JSON согласно этой схеме:\n{schema_json}"
        }

        # Объединяем сообщения
        all_messages = [system_message] + messages

        # Форматируем в промт
        prompt = self._format_messages_to_prompt(all_messages)

        # Создаём запрос
        request = LLMRequest(
            prompt=prompt,
            temperature=temperature,
            max_tokens=1000  # Увеличиваем для JSON
        )

        # Выполняем генерацию
        response = await self._generate_impl(request)

        # Извлекаем и парсим JSON
        content = response.content

        # Пытаемся найти JSON в ответе
        json_content = self._extract_json_from_response(content)

        return json.loads(json_content)

    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Подсчитать количество токенов в сообщениях (для совместимости с LLMInterface).
        """
        if not self.is_initialized or not self.llm:
            await self.initialize()

        prompt = self._format_messages_to_prompt(messages)

        # LlamaCpp имеет метод для токенизации
        if hasattr(self.llm, 'tokenize'):
            tokens = self.llm.tokenize(prompt.encode())
            return len(tokens)

        # Fallback: приблизительный подсчёт
        return len(prompt.split()) // 4

    def _format_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Форматировать сообщения в промт для LlamaCpp.

        Использует ChatML формат или формат конкретной модели.
        """
        prompt_parts = []

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if role == 'system':
                prompt_parts.append(f"<|system|>\n{content}</s>")
            elif role == 'user':
                prompt_parts.append(f"<|user|>\n{content}</s>")
            elif role == 'assistant':
                prompt_parts.append(f"<|assistant|>\n{content}</s>")
            else:
                prompt_parts.append(content)

        # Добавляем префикс для ответа ассистента
        prompt_parts.append("<|assistant|>")

        return "\n".join(prompt_parts)

    def _extract_json_from_response(self, content: str) -> str:
        """
        Извлечь JSON из ответа LLM.

        LLM часто добавляют текст до/после JSON или оборачивают в markdown блоки.
        """
        import re
        
        # 1. Сначала ищем JSON внутри markdown блока ```json ... ```
        json_block_pattern = r'```json\s*\n?(.*?)\n?```'
        matches = re.findall(json_block_pattern, content, re.DOTALL)
        if matches:
            # Берём последний блок (обычно там самый полный JSON)
            return matches[-1].strip()
        
        # 2. Ищем JSON внутри обычного markdown блока ``` ... ```
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
        
        # 3. Ищем JSON по скобкам
        start = content.find('{')
        end = content.rfind('}') + 1

        if start != -1 and end > start:
            candidate = content[start:end]
            # Проверяем что это валидный JSON
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                # Ищем следующий JSON объект
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
                # Если ничего не найдено, возвращаем первый кандидат
                return candidate

        # 4. Если не найдено, возвращаем как есть
        return content.strip()