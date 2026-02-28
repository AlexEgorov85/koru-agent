"""
Провайдер для Llama.cpp.
Использует llama-cpp-python для запуска LLM моделей локально.
"""
import logging
import time
import json
import re
from typing import Dict, Any, Optional, Type
from contextlib import asynccontextmanager

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.models.types.llm_types import (
    LLMRequest, 
    LLMResponse, 
    LLMHealthStatus, 
    StructuredOutputConfig,
    StructuredLLMResponse,
    RawLLMResponse
)
from pydantic import BaseModel, Field, ValidationError, create_model


logger = logging.getLogger(__name__)


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


class LlamaCppProvider(BaseLLMProvider):
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
        logger.info(f"Инициализация Llama.cpp провайдера для модели: {model_name}")

        # Контекст вызова для логирования
        self._event_bus = None
        self._session_id = None
        self._agent_id = None
        self._component = None
        self._phase = None
        self._goal = None

    def set_call_context(self, event_bus, session_id: str, agent_id: str = None, 
                         component: str = None, phase: str = None, goal: str = None):
        """
        Установка контекста вызова для логирования событий.
        
        ПАРАМЕТРЫ:
        - event_bus: EventBus для публикации событий
        - session_id: ID сессии
        - agent_id: ID агента
        - component: компонент вызывающий LLM
        - phase: фаза выполнения (think/act)
        - goal: цель выполнения
        """
        self._event_bus = event_bus
        self._session_id = session_id
        self._agent_id = agent_id
        self._component = component
        self._phase = phase
        self._goal = goal

    async def initialize(self) -> bool:
        """
        Асинхронная инициализация LLM инстанса.
        """
        try:
            logger.info(f"Загрузка модели из: {self.model_path}")
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
                logger.info(f"Llama.cpp провайдер успешно инициализирован за {init_time:.2f} секунд")
                logger.info(f"Контекст: {self.n_ctx}, потоки: {self.n_threads}, executor workers: 2")

                return True
            else:
                logger.error("Не удалось инициализировать LLM инстанс")
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
                
        except ImportError as e:
            logger.error(f"Ошибка импорта llama-cpp-python: {str(e)}")
            logger.error("Установите с помощью: pip install llama-cpp-python")
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False
        except ValueError as e:
            if "not enough values to unpack" in str(e):
                logger.error(f"Проблема с установкой llama-cpp-python: {str(e)}")
                logger.error("Возможно, требуется переустановка: pip uninstall llama-cpp-python && pip install llama-cpp-python")
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
            else:
                logger.exception(f"Ошибка инициализации Llama.cpp провайдера: {str(e)}")
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
        except Exception as e:
            logger.exception(f"Ошибка инициализации Llama.cpp провайдера: {str(e)}")
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """
        Корректное завершение работы провайдера.
        """
        try:
            logger.info("Завершение работы Llama.cpp провайдера...")
            
            # Остановка ThreadPoolExecutor
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
                logger.debug("ThreadPoolExecutor остановлен")
            
            # В llama-cpp-python нет явного метода для освобождения ресурсов
            # Но можно обнулить ссылку на модель
            self.llm = None
            self.is_initialized = False
            logger.info("Llama.cpp провайдер успешно завершен")
        except Exception as e:
            logger.error(f"Ошибка при завершении работы Llama.cpp провайдера: {str(e)}")

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
            logger.error(f"Ошибка health check для Llama.cpp: {str(e)}")
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self.is_initialized
            }

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Реализация генерации текста для Llama.cpp.
        
        Логирование выполняется в базовом классе BaseLLMProvider.
        """
        if not self.is_initialized or not self.llm:
            logger.warning("LLM не инициализирован! Вызываем initialize()...")
            await self.initialize()

        start_time = time.time()

        try:
            # === ПУБЛИКАЦИЯ СОБЫТИЯ: НАЧАЛО LLM ВЫЗОВА ===
            # Публикуем событие с полной информацией для логирования в сессию
            if hasattr(self, '_event_bus') and self._event_bus:
                from core.infrastructure.event_bus.event_bus import EventType
                await self._event_bus.publish(
                    event=EventType.LLM_CALL_STARTED,
                    data={
                        "agent_id": getattr(self, '_agent_id', 'unknown'),
                        "session_id": getattr(self, '_session_id', 'unknown'),
                        "component": getattr(self, '_component', 'llama_cpp'),
                        "phase": getattr(self, '_phase', 'generation'),
                        "goal": getattr(self, '_goal', 'unknown'),
                        "provider": type(self).__name__,
                        "model": self.model_name,
                        "is_initialized": self.is_initialized,
                        "prompt_length": len(request.prompt),
                        "max_tokens": request.max_tokens,
                        "temperature": request.temperature,
                        "top_p": request.top_p,
                        "frequency_penalty": request.frequency_penalty,
                        "presence_penalty": request.presence_penalty,
                        "stop_sequences": request.stop_sequences,
                        "structured_output": hasattr(request, 'structured_output') and request.structured_output,
                        "timeout_seconds": self.timeout_seconds
                    },
                    source="llama_cpp_provider.execute",
                    correlation_id=getattr(self, '_session_id', '')
                )

            # Подготовим параметры для вызова модели
            max_tokens = request.max_tokens
            if hasattr(request, 'structured_output') and request.structured_output:
                # Если запрошена структурированная генерация
                max_tokens = min(max_tokens, 1000)  # ограничим для структурированного вывода

            # Проверка что модель инициализирована
            if not self.llm:
                # Публикуем событие о проблеме инициализации
                if hasattr(self, '_event_bus') and self._event_bus:
                    from core.infrastructure.event_bus.event_bus import EventType
                    await self._event_bus.publish(
                        event=EventType.ERROR_OCCURRED,
                        data={
                            "agent_id": getattr(self, '_agent_id', 'unknown'),
                            "session_id": getattr(self, '_session_id', 'unknown'),
                            "component": getattr(self, '_component', 'llama_cpp'),
                            "error_type": "initialization_error",
                            "error_message": "LLM не инициализирован, вызываем initialize()",
                        },
                        source="llama_cpp_provider.execute",
                        correlation_id=getattr(self, '_session_id', '')
                    )
                await self.initialize()

            # Выполняем запрос к модели (в отдельном потоке чтобы не блокировать event loop)
            import asyncio
            from asyncio import wait_for, TimeoutError
            import threading

            # Используем существующий ThreadPoolExecutor
            if not self._executor:
                from concurrent.futures import ThreadPoolExecutor
                self._executor = ThreadPoolExecutor(
                    max_workers=2,
                    thread_name_prefix='llm_worker'
                )
                logger.warning("ThreadPoolExecutor не был создан при инициализации, создан сейчас")

            # Флаг для отслеживания завершения вызова
            call_completed = {'done': False, 'error': None}

            def _call_llm_sync():
                try:
                    if not self.llm:
                        raise RuntimeError("LLM модель не загружена")
                    
                    result = self.llm(
                        request.prompt,
                        max_tokens=max_tokens,
                        temperature=request.temperature,
                        top_p=request.top_p,
                        frequency_penalty=request.frequency_penalty,
                        presence_penalty=request.presence_penalty,
                        echo=False,
                        stop=request.stop_sequences or None
                    )

                    call_completed['done'] = True
                    return result
                except Exception as e:
                    call_completed['error'] = str(e)
                    logger.error(f"Ошибка в _call_llm_sync: {e}")
                    raise  # Пробрасываем ошибку дальше

            try:
                logger.info(f"Запуск LLM вызова: prompt_length={len(request.prompt)}, max_tokens={max_tokens}, timeout={self.timeout_seconds}с")
                logger.debug(f"Executor: {self._executor}, llm loaded: {self.llm is not None}")
                
                response = await wait_for(
                    asyncio.get_event_loop().run_in_executor(self._executor, _call_llm_sync),
                    timeout=self.timeout_seconds
                )
                
                logger.info(f"LLM вызов завершён успешно за {time.time() - start_time:.2f}с")

                elapsed_time = time.time() - start_time

                # === ПУБЛИКАЦИЯ СОБЫТИЯ: LLM ВЫЗОВ ЗАВЕРШЁН ===
                if hasattr(self, '_event_bus') and self._event_bus:
                    from core.infrastructure.event_bus.event_bus import EventType
                    await self._event_bus.publish(
                        event=EventType.LLM_CALL_COMPLETED,
                        data={
                            "agent_id": getattr(self, '_agent_id', 'unknown'),
                            "session_id": getattr(self, '_session_id', 'unknown'),
                            "component": getattr(self, '_component', 'llama_cpp'),
                            "phase": getattr(self, '_phase', 'generation'),
                            "goal": getattr(self, '_goal', 'unknown'),
                            "provider": type(self).__name__,
                            "model": self.model_name,
                            "success": True,
                            "elapsed_time": elapsed_time,
                            "result_length": len(response.get('choices', [{}])[0].get('text', '')) if response.get('choices') else 0
                        },
                        source="llama_cpp_provider.execute",
                        correlation_id=getattr(self, '_session_id', '')
                    )

            except TimeoutError as e:
                elapsed = time.time() - start_time
                logger.error(f"⏰ LLM TIMEOUT после {elapsed:.2f}с (timeout={self.timeout_seconds}с)")
                logger.error(f"  - prompt_length: {len(request.prompt)}")
                logger.error(f"  - max_tokens: {max_tokens}")
                logger.error(f"  - executor: {self._executor}")
                logger.error(f"  - llm loaded: {self.llm is not None}")
                logger.error(f"  - call_completed: {call_completed}")
                logger.error(f"  - active_threads: {threading.active_count()}")
                
                # === ПУБЛИКАЦИЯ СОБЫТИЯ: ТАЙМАУТ LLM ===
                if hasattr(self, '_event_bus') and self._event_bus:
                    from core.infrastructure.event_bus.event_bus import EventType
                    await self._event_bus.publish(
                        event=EventType.LLM_CALL_FAILED,
                        data={
                            "agent_id": getattr(self, '_agent_id', 'unknown'),
                            "session_id": getattr(self, '_session_id', 'unknown'),
                            "component": getattr(self, '_component', 'llama_cpp'),
                            "phase": getattr(self, '_phase', 'generation'),
                            "goal": getattr(self, '_goal', 'unknown'),
                            "provider": type(self).__name__,
                            "model": self.model_name,
                            "success": False,
                            "error_type": "timeout",
                            "error_message": f"Превышено время ожидания ответа от LLM ({self.timeout_seconds} секунд)",
                            "timeout_seconds": self.timeout_seconds,
                            "elapsed_seconds": elapsed,
                            "call_completed": call_completed['done'],
                            "active_threads": threading.active_count()
                        },
                        source="llama_cpp_provider.execute",
                        correlation_id=getattr(self, '_session_id', '')
                    )

                raise TimeoutError(f"Превышено время ожидания ответа от LLM ({self.timeout_seconds} секунд)") from e

            # Обрабатываем результат
            choices = response.get('choices', [])
            usage = response.get('usage', {})
            
            if choices:
                generated_text = choices[0].get('text', '')
                finish_reason = choices[0].get('finish_reason', 'stop')
            else:
                generated_text = ''
                finish_reason = 'error'

            # Создаем результат
            llm_response = LLMResponse(
                content=generated_text,
                model=self.model_name,
                tokens_used=usage.get('total_tokens', 0),
                generation_time=time.time() - start_time,
                finish_reason=finish_reason
            )

            # Обновляем метрики
            self._update_metrics(llm_response.generation_time)

            return llm_response

        except TimeoutError as e:
            # Re-raise timeout without wrapping in generic error
            raise
        
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ LLM вызов failed после {elapsed:.2f}с: {type(e).__name__}: {str(e)}")
            logger.error(f"  - prompt_length: {len(request.prompt)}")
            logger.error(f"  - max_tokens: {max_tokens}")
            logger.error(f"  - executor: {self._executor}")
            logger.error(f"  - llm loaded: {self.llm is not None}")
            
            # Публикуем событие об ошибке
            if hasattr(self, '_event_bus') and self._event_bus:
                from core.infrastructure.event_bus.event_bus import EventType
                await self._event_bus.publish(
                    event=EventType.ERROR_OCCURRED,
                    data={
                        "agent_id": getattr(self, '_agent_id', 'unknown'),
                        "session_id": getattr(self, '_session_id', 'unknown'),
                        "component": getattr(self, '_component', 'llama_cpp'),
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "elapsed_seconds": elapsed
                    },
                    source="llama_cpp_provider.execute",
                    correlation_id=getattr(self, '_session_id', '')
                )

            self._update_metrics(time.time() - start_time, success=False)

            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": str(e)}
            )

    async def _generate_structured_impl(
        self,
        request: LLMRequest
    ) -> StructuredLLMResponse:
        """
        Генерация с гарантированным структурным выводом.
        
        Логирование выполняется в базовом классе BaseLLMProvider.

        АЛГОРИТМ:
        1. Проверяем наличие structured_output в запросе
        2. Добавляем схему в промпт
        3. Генерируем с retry (до max_retries)
        4. Парсим JSON и валидируем против схемы
        5. Возвращаем StructuredLLMResponse с валидной моделью
        
        RAISES:
        - StructuredOutputError: если все попытки исчерпаны
        - ValueError: если structured_output не указан
        """
        if not request.structured_output:
            raise ValueError("structured_output не указан в запросе")
        
        config: StructuredOutputConfig = request.structured_output
        schema_def = config.schema_def
        
        # Логирование начала структурированной генерации
        self.logger.info(
            f"Запуск structured output для {config.output_model} "
            f"(max_retries={config.max_retries}, strict_mode={config.strict_mode})"
        )
        
        # 1. Добавляем схему в промпт
        enhanced_prompt = self._add_schema_to_prompt(
            request.prompt,
            schema_def
        )
        
        # Создаем новый запрос с улучшенным промптом
        structured_request = LLMRequest(
            prompt=enhanced_prompt,
            system_prompt=request.system_prompt,
            temperature=0.1,  # Низкая температура для точности
            max_tokens=min(request.max_tokens, 1500),  # Ограничение для JSON
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            stop_sequences=request.stop_sequences,
            metadata=request.metadata,
            correlation_id=request.correlation_id,
            capability_name=request.capability_name
        )
        
        validation_errors = []
        last_raw_response = None
        last_json_content = None
        
        # 2. Retry цикл
        for attempt in range(1, config.max_retries + 1):
            try:
                self.logger.debug(f"Попытка {attempt}/{config.max_retries}: генерация...")
                
                # 3. Генерация
                raw_response = await self.execute(structured_request)
                last_raw_response = raw_response
                
                self.logger.debug(f"Попытка {attempt}/{config.max_retries}: ответ получен ({len(raw_response.content)} символов)")
                
                # 4. Извлечение JSON из ответа
                json_content = self._extract_json_from_response(raw_response.content)
                last_json_content = json_content
                
                self.logger.debug(f"Попытка {attempt}/{config.max_retries}: JSON извлечён ({len(json_content)} ключей)")
                
                # 5. Валидация против схемы
                temp_model = self._create_pydantic_from_schema(
                    config.output_model,
                    schema_def
                )
                
                # Валидируем
                parsed_content = temp_model.model_validate(json_content)
                
                # 6. Успех!
                self.logger.info(
                    f"Structured output успешен с попытки {attempt}/{config.max_retries} "
                    f"для {config.output_model}"
                )
                
                return StructuredLLMResponse(
                    parsed_content=parsed_content,
                    raw_response=RawLLMResponse(
                        content=raw_response.content,
                        model=raw_response.model,
                        tokens_used=raw_response.tokens_used,
                        generation_time=raw_response.generation_time,
                        finish_reason=raw_response.finish_reason,
                        metadata=raw_response.metadata
                    ),
                    parsing_attempts=attempt,
                    validation_errors=[],
                    provider_native_validation=False
                )
                
            except json.JSONDecodeError as e:
                error_info = {
                    "attempt": attempt,
                    "error_type": "JSONDecodeError",
                    "error_message": f"Не удалось распарсить JSON: {str(e)}",
                    "response_snippet": raw_response.content[:200] if raw_response else "N/A"
                }
                validation_errors.append(error_info)
                
                self.logger.warning(
                    f"Попытка {attempt}/{config.max_retries} не удалась (JSON): {e}"
                )
                
                if attempt < config.max_retries:
                    # Добавляем ошибку в промпт для следующей попытки
                    structured_request = self._add_error_to_prompt(
                        structured_request,
                        last_json_content if last_json_content else raw_response.content,
                        str(e)
                    )
                    continue
                    
            except ValidationError as e:
                error_info = {
                    "attempt": attempt,
                    "error_type": "ValidationError",
                    "error_message": f"Валидация схемы не пройдена: {str(e)}",
                    "response_snippet": raw_response.content[:200] if raw_response else "N/A"
                }
                validation_errors.append(error_info)
                
                self.logger.warning(
                    f"Попытка {attempt}/{config.max_retries} не удалась (валидация): {e}"
                )
                
                if attempt < config.max_retries:
                    # Добавляем ошибку в промпт для следующей попытки
                    structured_request = self._add_error_to_prompt(
                        structured_request,
                        last_json_content if last_json_content else raw_response.content,
                        str(e)
                    )
                    continue
        
        # 7. Все попытки исчерпаны
        self.logger.error(
            f"Все {config.max_retries} попыток структурированного вывода не удались "
            f"для {config.output_model}. Ошибок валидации: {len(validation_errors)}"
        )
        
        raise StructuredOutputError(
            message="Не удалось получить валидный структурированный ответ",
            model_name=self.model_name,
            attempts=config.max_retries,
            correlation_id=request.correlation_id,
            validation_errors=validation_errors
        )
    
    def _add_schema_to_prompt(
        self, 
        prompt: str, 
        schema_def: Dict[str, Any]
    ) -> str:
        """
        Добавляет JSON схему в промпт.
        
        ARGS:
        - prompt: Исходный текст промпта
        - schema_def: JSON Schema словарь
        
        RETURNS:
        - str: Промпт с добавленной схемой
        """
        schema_section = f"""

### ТРЕБУЕМЫЙ ФОРМАТ ОТВЕТА (JSON Schema) ###
Твой ответ ДОЛЖЕН быть валидным JSON, соответствующим этой схеме:

```json
{json.dumps(schema_def, indent=2, ensure_ascii=False)}
```

⚠️ **ВАЖНО:**
- ОТВЕТЬ ТОЛЬКО JSON
- Не добавляй никаких объяснений
- Не используй markdown кроме ```json ... ```
- Все поля из "required" обязательны
"""
        return prompt + schema_section
    
    def _extract_json_from_response(self, content: str) -> Dict[str, Any]:
        """
        Извлекает JSON из ответа LLM.
        
        LLM может вернуть:
        - Чистый JSON: {"key": "value"}
        - JSON в markdown: ```json {...} ```
        - JSON с текстом: Вот ответ: {...}
        
        ARGS:
        - content: Ответ от LLM
        
        RETURNS:
        - Dict[str, Any]: Распарсенный JSON
        
        RAISES:
        - json.JSONDecodeError: если не удалось извлечь JSON
        """
        content = content.strip()
        
        # Попытка 1: Чистый JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Попытка 2: JSON в markdown блоке
        markdown_pattern = r'```(?:json)?\s*({.*?})\s*```'
        match = re.search(markdown_pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Попытка 3: Поиск первой { и последней }
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # Попытка 4: Возвращаем ошибку
        raise json.JSONDecodeError(
            "Не удалось извлечь JSON из ответа",
            content,
            0
        )
    
    def _create_pydantic_from_schema(
        self, 
        model_name: str, 
        schema_def: Dict[str, Any]
    ) -> Type[BaseModel]:
        """
        Создаёт Pydantic модель из JSON Schema.
        
        ARGS:
        - model_name: Имя создаваемой модели
        - schema_def: JSON Schema словарь
        
        RETURNS:
        - Type[BaseModel]: Класс Pydantic модели
        """
        from typing import List, Optional, Union
        
        def build_field(field_schema: Dict) -> tuple:
            field_type = field_schema.get('type', 'string')
            description = field_schema.get('description', '')
            default = field_schema.get('default', ...)
            
            type_mapping = {
                'string': str,
                'integer': int,
                'number': float,
                'boolean': bool,
                'array': List[Any],
                'object': Dict[str, Any]
            }
            
            python_type = type_mapping.get(field_type, Any)
            
            if description:
                field_info = Field(default=default, description=description) if default is not ... else Field(description=description)
            else:
                field_info = Field(default=default) if default is not ... else Field()
            
            return (python_type, field_info)
        
        fields = {}
        properties = schema_def.get('properties', {})
        required = schema_def.get('required', [])
        
        for field_name, field_schema in properties.items():
            if field_name in required:
                fields[field_name] = build_field(field_schema)
            else:
                # Необязательное поле
                field_type, field_info = build_field(field_schema)
                fields[field_name] = (Optional[field_type], field_info)
        
        return create_model(model_name, **fields)
    
    def _add_error_to_prompt(
        self, 
        request: LLMRequest, 
        invalid_json: Any, 
        error_message: str
    ) -> LLMRequest:
        """
        Добавляет информацию об ошибке в промпт для retry.
        
        ARGS:
        - request: Текущий запрос
        - invalid_json: Невалидный JSON который вернул LLM
        - error_message: Сообщение об ошибке валидации
        
        RETURNS:
        - LLMRequest: Новый запрос с обновлённым промптом
        """
        # Преобразуем JSON в строку если нужно
        if isinstance(invalid_json, dict):
            invalid_json_str = json.dumps(invalid_json, ensure_ascii=False)[:500]
        else:
            invalid_json_str = str(invalid_json)[:500]
        
        error_section = f"""

### ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ ###
Твой предыдущий ответ не прошёл валидацию:

```json
{invalid_json_str}...
```

Ошибка: {error_message}

ПОПРОБУЙ ЕЩЁ РАЗ. Убедись что:
1. JSON синтаксически корректен (проверь запятые, кавычки, скобки)
2. Все required поля присутствуют
3. Типы данных соответствуют схеме (string, integer, number, boolean)
4. Не добавляй никаких объяснений, только JSON
"""
        
        return LLMRequest(
            prompt=request.prompt + error_section,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            stop_sequences=request.stop_sequences,
            metadata=request.metadata,
            correlation_id=request.correlation_id,
            capability_name=request.capability_name,
            structured_output=request.structured_output
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
            logger.error(f"Ошибка в сессии Llama.cpp: {str(e)}")
            raise