"""
Провайдер для Llama.cpp.
Использует llama-cpp-python для запуска LLM моделей локально.
"""
import logging
import time
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.models.types.llm_types import LLMRequest, LLMResponse, LLMHealthStatus, StructuredOutputConfig
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


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
        
        self.llm = None
        logger.info(f"Инициализация Llama.cpp провайдера для модели: {model_name}")

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
            
            # Проверка загрузки модели
            if self.llm:
                self.is_initialized = True
                self.health_status = LLMHealthStatus.HEALTHY
                self.last_health_check = time.time()
                
                init_time = time.time() - start_time
                logger.info(f"Llama.cpp провайдер успешно инициализирован за {init_time:.2f} секунд")
                logger.info(f"Контекст: {self.n_ctx}, потоки: {self.n_threads}")
                
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

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """
        Выполнение запроса к LLM.
        """
        if not self.is_initialized or not self.llm:
            await self.initialize()

        start_time = time.time()

        try:
            # Логируем запрос при необходимости
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Выполнение запроса к Llama.cpp: {request.prompt[:50]}...")

            # Подготовим параметры для вызова модели
            max_tokens = request.max_tokens
            if hasattr(request, 'structured_output') and request.structured_output:
                # Если запрошена структурированная генерация
                max_tokens = min(max_tokens, 1000)  # ограничим для структурированного вывода

            # Выполняем запрос к модели (в отдельном потоке чтобы не блокировать event loop)
            # Используем run_in_executor для совместимости
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            # Создаём executor если нет
            if not hasattr(self, '_executor'):
                self._executor = ThreadPoolExecutor(max_workers=2)
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self._executor,
                lambda: self.llm(
                    request.prompt,
                    max_tokens=max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty,
                    echo=False,
                    stop=request.stop_sequences or None
                )
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

        except Exception as e:
            logger.error(f"Ошибка выполнения запроса к Llama.cpp: {str(e)}")
            logger.error(f"Запрос был: {request.prompt[:100]}...")

            self._update_metrics(time.time() - start_time, success=False)

            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": str(e)}
            )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация текста (совместимость с базовым интерфейсом).
        """
        return await self.execute(request)

    async def generate_structured(self, request: LLMRequest) -> Dict[str, Any]:
        """
        Генерация структурированных данных.
        """
        response = await self.execute(request)
        # В реальной реализации здесь будет парсинг структурированного ответа
        return {"raw_response": response.content, "tokens_used": response.tokens_used}

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