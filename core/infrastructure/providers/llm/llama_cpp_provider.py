"""
Провайдер для Llama.cpp.
Использует llama-cpp-python для запуска LLM моделей локально.
"""
import asyncio
import time
import json
import re
from typing import Dict, Any, Optional, Type, List
from contextlib import asynccontextmanager

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.interfaces.llm import LLMInterface
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

    def __init__(self, config, model_name: str = None):
        """
        Инициализация Llama.cpp провайдера.
        :param config: Конфигурация подключения (LlamaCppConfig или dict)
        :param model_name: Имя модели (если передано отдельно)
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

        # event_bus_logger будет инициализирован в initialize()
        self.event_bus_logger = None

        # Контекст вызова теперь управляется в BaseLLMProvider
        # set_call_context() наследуется из базового класса

    async def initialize(self) -> bool:
        """
        Асинхронная инициализация LLM инстанса.
        """
        try:
            # Инициализация event_bus_logger если ещё не создан
            if self.event_bus_logger is None:
                from core.infrastructure.event_bus.unified_event_bus import get_event_bus
                from core.infrastructure.logging import EventBusLogger
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                try:
                    event_bus = get_event_bus()
                    self.event_bus_logger = EventBusLogger(event_bus, "system", "llm_provider", self.__class__.__name__)
                      # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                except:
                    self.event_bus_logger = type('obj', (object,), {
                        'info': lambda *args, **kwargs: None,
                        'debug': lambda *args, **kwargs: None,
                        'warning': lambda *args, **kwargs: None,
                        'error': lambda *args, **kwargs: None
                    })()

            await self.event_bus_logger.info(f"Загрузка модели из: {self.model_path}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
                await self.event_bus_logger.info(f"Llama.cpp провайдер успешно инициализирован за {init_time:.2f} секунд")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.info(f"Контекст: {self.n_ctx}, потоки: {self.n_threads}, executor workers: 2")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

                return True
            else:
                await self.event_bus_logger.error("Не удалось инициализировать LLM инстанс")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False

        except ImportError as e:
            await self.event_bus_logger.error(f"Ошибка импорта llama-cpp-python: {str(e)}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.event_bus_logger.error("Установите с помощью: pip install llama-cpp-python")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False
        except ValueError as e:
            if "not enough values to unpack" in str(e):
                await self.event_bus_logger.error(f"Проблема с установкой llama-cpp-python: {str(e)}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                await self.event_bus_logger.error("Возможно, требуется переустановка: pip uninstall llama-cpp-python && pip install llama-cpp-python")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
            else:
                await self.event_bus_logger.error(f"Ошибка инициализации Llama.cpp провайдера: {str(e)}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка инициализации Llama.cpp провайдера: {str(e)}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """
        Корректное завершение работы провайдера.
        """
        try:
            await self.event_bus_logger.info("Завершение работы Llama.cpp провайдера...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            # Остановка ThreadPoolExecutor
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
                await self.event_bus_logger.debug("ThreadPoolExecutor остановлен")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            # В llama-cpp-python нет явного метода для освобождения ресурсов
            # Но можно обнулить ссылку на модель
            self.llm = None
            self.is_initialized = False
            await self.event_bus_logger.info("Llama.cpp провайдер успешно завершен")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка при завершении работы Llama.cpp провайдера: {str(e)}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

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
            await self.event_bus_logger.error(f"Ошибка health check для Llama.cpp: {str(e)}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
        
        # Упрощаем схему — убираем лишние поля для экономии токенов
        simplified_schema = {
            "type": "object",
            "properties": {},
            "required": schema_def.get("required", [])
        }
        
        # Копируем только основные поля
        for prop_name, prop_def in schema_def.get("properties", {}).items():
            simplified_schema["properties"][prop_name] = {
                "type": prop_def.get("type", "string"),
                "description": prop_def.get("description", "")[:100]  # Обрезаем описание
            }
        
        schema_json = json.dumps(simplified_schema, indent=2, ensure_ascii=False)
        
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
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"🔵 [LLM] _generate_impl started: prompt_len={len(request.prompt)}, structured_output={hasattr(request, 'structured_output') and request.structured_output is not None}")

        if not self.is_initialized or not self.llm:
            await self.event_bus_logger.warning("LLM не инициализирован! Вызываем initialize()...")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            await self.initialize()

        start_time = time.time()

        # === ПОДГОТОВКА ПРОМПТА ===
        prompt = request.prompt
        system_prompt = request.system_prompt or ""

        # ✅ Если есть structured_output — добавляем схему в промпт
        if hasattr(request, 'structured_output') and request.structured_output:
            max_tokens = min(request.max_tokens, 4000)
            msg = f"🔵 [LLM] Structured output активирован: model={request.structured_output.output_model}"
            if self.event_bus_logger:
                await self.event_bus_logger.info(msg)

            schema_prompt = self._build_schema_prompt(request.structured_output.schema_def)
            system_prompt = system_prompt + "\n\n" + schema_prompt

            msg = f"🔵 [LLM] Схема добавлена в system_prompt (длина: {len(schema_prompt)} символов)"
            if self.event_bus_logger:
                await self.event_bus_logger.info(msg)
                await self.event_bus_logger.debug("\n" + "=" * 80)
                await self.event_bus_logger.debug("📋 PROMPT WITH JSON SCHEMA (LlamaCppProvider)")
                await self.event_bus_logger.debug("=" * 80)
                await self.event_bus_logger.debug("\n=== SYSTEM (со схемой) ===")
                await self.event_bus_logger.debug(system_prompt)
                await self.event_bus_logger.debug("\n=== USER ===")
                await self.event_bus_logger.debug(prompt)
                await self.event_bus_logger.debug("\n" + "=" * 80)
        else:
            max_tokens = request.max_tokens

        # Проверка что модель инициализирована
        if not self.llm:
            if self.event_bus_logger:
                await self.event_bus_logger.warning("⚠️ [LLM] Модель не инициализирована! Вызываем initialize()...")
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
            if self.event_bus_logger:
                await self.event_bus_logger.info(msg)

            if choices:
                generated_text = choices[0].get('text', '')
                finish_reason = choices[0].get('finish_reason', 'stop')

                if self.event_bus_logger:
                    await self.event_bus_logger.debug("\n" + "=" * 80)
                    await self.event_bus_logger.debug("💬 RESPONSE (LlamaCppProvider)")
                    await self.event_bus_logger.debug("=" * 80)
                    await self.event_bus_logger.debug(generated_text)
                    await self.event_bus_logger.debug("\n" + "=" * 80)
                    await self.event_bus_logger.info(f"🔵 [LLM] generated_text: {len(generated_text)} символов")
                    await self.event_bus_logger.info(f"🔵 [LLM] finish_reason: {finish_reason}")
            else:
                generated_text = ''
                finish_reason = 'error'
                if self.event_bus_logger:
                    await self.event_bus_logger.warning("⚠️ [LLM] choices пуст!")

            # === ОБРАБОТКА STRUCTURED OUTPUT ===
            if hasattr(request, 'structured_output') and request.structured_output:
                msg = f"🔵 Structured output запрошен: {request.structured_output.output_model}"
                if self.event_bus_logger:
                    await self.event_bus_logger.info(msg)
                
                # Логирование сырого ответа
                if self.event_bus_logger:
                    await self.event_bus_logger.info(f"🔵 [LLM] Raw response: {generated_text[:500]}...")

                try:
                    json_content = self._extract_json_from_response(generated_text)

                    if self.event_bus_logger:
                        await self.event_bus_logger.debug(f"🔵 JSON извлечён: {json_content[:80]}...")
                    parsed_json = json.loads(json_content)
                    if self.event_bus_logger:
                        await self.event_bus_logger.info(f"✅ JSON распарсен: ключи={list(parsed_json.keys())}")

                    # ✅ Сохраняем JSON в raw_response.content
                    # ✅ parsed_content=None — оркестратор создаст Pydantic модель
                    response = LLMResponse(
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

                    if self.event_bus_logger:
                        await self.event_bus_logger.info(f"✅ LLMResponse создан (JSON в raw_response.content)")

                    self._update_metrics(response.generation_time)

                    return response

                except json.JSONDecodeError as json_err:
                    # ❌ Ошибка парсинга JSON — возвращаем LLMResponse с ошибкой
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(f"❌ Structured output JSON parse error: {json_err}")
                    
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
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(f"❌ Structured output error: {struct_err}")
                    
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
            if self.event_bus_logger:
                await self.event_bus_logger.error("❌ [LLM] Structured output запрос, но не удалось сгенерировать ответ")
            
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
            await self.event_bus_logger.error(f"Ошибка в сессии Llama.cpp: {str(e)}")
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
            max_tokens=max_tokens or self.config.get('max_tokens', 512),
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