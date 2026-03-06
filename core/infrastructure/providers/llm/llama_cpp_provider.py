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
from core.interfaces.llm import LLMInterface
from core.models.types.llm_types import (
    LLMRequest, 
    LLMResponse, 
    LLMHealthStatus, 
    StructuredOutputConfig,
    StructuredLLMResponse,
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
                try:
                    event_bus = get_event_bus()
                    self.event_bus_logger = EventBusLogger(event_bus, "system", "llm_provider", self.__class__.__name__)
                except:
                    self.event_bus_logger = type('obj', (object,), {
                        'info': lambda *args, **kwargs: None,
                        'debug': lambda *args, **kwargs: None,
                        'warning': lambda *args, **kwargs: None,
                        'error': lambda *args, **kwargs: None
                    })()

            await self.event_bus_logger.info(f"Загрузка модели из: {self.model_path}")
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
                await self.event_bus_logger.info(f"Контекст: {self.n_ctx}, потоки: {self.n_threads}, executor workers: 2")

                return True
            else:
                await self.event_bus_logger.error("Не удалось инициализировать LLM инстанс")
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False

        except ImportError as e:
            await self.event_bus_logger.error(f"Ошибка импорта llama-cpp-python: {str(e)}")
            await self.event_bus_logger.error("Установите с помощью: pip install llama-cpp-python")
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False
        except ValueError as e:
            if "not enough values to unpack" in str(e):
                await self.event_bus_logger.error(f"Проблема с установкой llama-cpp-python: {str(e)}")
                await self.event_bus_logger.error("Возможно, требуется переустановка: pip uninstall llama-cpp-python && pip install llama-cpp-python")
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
            else:
                await self.event_bus_logger.error(f"Ошибка инициализации Llama.cpp провайдера: {str(e)}")
                self.health_status = LLMHealthStatus.UNHEALTHY
                return False
        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка инициализации Llama.cpp провайдера: {str(e)}")
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """
        Корректное завершение работы провайдера.
        """
        try:
            await self.event_bus_logger.info("Завершение работы Llama.cpp провайдера...")

            # Остановка ThreadPoolExecutor
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
                await self.event_bus_logger.debug("ThreadPoolExecutor остановлен")

            # В llama-cpp-python нет явного метода для освобождения ресурсов
            # Но можно обнулить ссылку на модель
            self.llm = None
            self.is_initialized = False
            await self.event_bus_logger.info("Llama.cpp провайдер успешно завершен")
        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка при завершении работы Llama.cpp провайдера: {str(e)}")

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
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self.is_initialized
            }

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Реализация генерации текста для Llama.cpp.

        АРХИТЕКТУРА:
        - ТОЛЬКО выполняет вызов модели
        - НЕ публикует события (это делает LLMOrchestrator)
        - НЕ логирует (это делает LLMOrchestrator через события)
        - Возвращает LLMResponse или бросает исключение
        """
        if not self.is_initialized or not self.llm:
            await self.event_bus_logger.warning("LLM не инициализирован! Вызываем initialize()...")
            await self.initialize()

        start_time = time.time()

        # Подготовим параметры для вызова модели
        max_tokens = request.max_tokens
        if hasattr(request, 'structured_output') and request.structured_output:
            max_tokens = min(max_tokens, 1000)

        # Проверка что модель инициализирована
        if not self.llm:
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
        from asyncio import wait_for, TimeoutError

        def _call_llm_sync():
            """Синхронный вызов модели."""
            if not self.llm:
                raise RuntimeError("LLM модель не загружена")

            return self.llm(
                request.prompt,
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
                # Не в потоке - используем run_in_executor
                response = await wait_for(
                    asyncio.get_event_loop().run_in_executor(self._executor, _call_llm_sync),
                    timeout=self.timeout_seconds
                )

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

        LLM часто добавляют текст до/после JSON.
        """
        # Пытаемся найти JSON по скобкам
        start = content.find('{')
        end = content.rfind('}') + 1

        if start != -1 and end > start:
            return content[start:end]

        # Если не найдено, возвращаем как есть (возможно, это чистый JSON)
        return content.strip()