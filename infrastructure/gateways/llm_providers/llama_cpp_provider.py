"""
LlamaCppProvider - реализация LLM-провайдера с использованием llama-cpp-python.
"""
import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from domain.abstractions.event_system import EventType
from infrastructure.gateways.llm_providers.base_provider import BaseLLMProvider, LLMRequest, LLMResponse, LLMHealthStatus, LLMDecisionType


class LlamaCppProvider(BaseLLMProvider):
    """
    Реализация LLM-провайдера с использованием llama-cpp-python.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (шлюз)
    - Зависимости: от базового класса BaseLLMProvider
    - Ответственность: интеграция с локальной LLM-моделью через llama-cpp
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    def __init__(self, model_name: str, config: Dict[str, Any]):
        """
        Инициализация LlamaCpp провайдера.
        
        Args:
            model_name: Название модели (путь к файлу модели)
            config: Конфигурация провайдера
        """
        super().__init__(model_name, config)
        self._engine = None
        self._is_initialized = False
        
        # Извлекаем параметры из конфигурации
        self.model_path = config.get("model_path", model_name)
        self.n_ctx = config.get("n_ctx", 2048)
        self.n_gpu_layers = config.get("n_gpu_layers", 0)
        self.n_batch = config.get("n_batch", 512)
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 500)
        self.top_p = config.get("top_p", 0.95)
        self.verbose = config.get("verbose", True)
        self.f16_kv = config.get("f16_kv", True)
        self.embedding = config.get("embedding", False)
        self.stop = config.get("stop", [])
        self.echo = config.get("echo", False)
    
    async def initialize(self) -> bool:
        """
        Инициализация Llama.cpp движка.
        
        Returns:
            bool: Успешность инициализации
        """
        if self._is_initialized:
            return True
        
        try:
            # Импортируем llama_cpp только при необходимости
            from llama_cpp import Llama
            
            # Проверяем существование файла модели
            if not Path(self.model_path).exists():
                raise FileNotFoundError(f"Файл модели не найден: {self.model_path}")
            
            # Создаем движок
            self._engine = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_batch=self.n_batch,
                verbose=self.verbose,
                f16_kv=self.f16_kv,
                embedding=self.embedding
            )
            
            # Выполняем тестовый запрос для проверки работоспособности
            test_request = LLMRequest(prompt="Привет", max_tokens=5)
            await self.generate(test_request)
            
            self._is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            
            return True
        except Exception as e:
            if hasattr(self, 'event_publisher') and self.event_publisher:
                await self.event_publisher.publish(
                    EventType.ERROR,
                    "LlamaCppProvider",
                    {
                        "message": f"Ошибка инициализации LlamaCppProvider: {str(e)}",
                        "error": str(e),
                        "context": "initialization_error"
                    }
                )
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False
    
    async def shutdown(self) -> None:
        """
        Завершение работы провайдера.
        """
        self._engine = None
        self._is_initialized = False
        self.health_status = LLMHealthStatus.UNKNOWN
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация текста с использованием Llama.cpp.
        
        Args:
            request: Запрос к LLM
            
        Returns:
            LLMResponse: Ответ от LLM
        """
        if not self._is_initialized:
            if not await self.initialize():
                raise RuntimeError("LlamaCppProvider не инициализирован")
        
        start_time = time.time()
        
        try:
            # Формируем полный промпт
            full_prompt = self._format_prompt(request)
            
            # Подготавливаем параметры для генерации
            gen_kwargs = {
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "frequency_penalty": request.frequency_penalty,
                "presence_penalty": request.presence_penalty,
                "echo": self.echo,
                "stop": request.stop_sequences or self.stop
            }
            
            # Выполняем генерацию в отдельном потоке
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._engine(
                    full_prompt,
                    **gen_kwargs
                )
            )
            
            # Извлекаем результат
            content = response["choices"][0]["text"].strip()
            usage = response["usage"]
            
            # Проверяем, был ли ответ обрезан
            is_truncated = response["choices"][0].get("finish_reason", "") == "length"
            
            # Создаем ответ
            llm_response = LLMResponse(
                raw_text=content,
                model=self.model_name,
                tokens_used=usage["total_tokens"],
                generation_time=time.time() - start_time,
                parsed=None,  # Будет заполнено валидатором
                validation_error=None,  # Будет заполнено валидатором
                validation_attempts=0,  # Будет обновлено валидатором
                validation_chain=[],  # Будет обновлено валидатором
                finish_reason=response["choices"][0].get("finish_reason", "stop"),
                is_truncated=is_truncated,
                metadata={
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"]
                }
            )
            
            # Обновляем метрики
            self._update_metrics(llm_response.generation_time)
            
            return llm_response
        except Exception as e:
            # Обновляем метрики ошибки
            self._update_metrics(time.time() - start_time, success=False)
            raise e
    
    def _format_prompt(self, request: LLMRequest) -> str:
        """
        Форматирование промпта для модели.
        
        Args:
            request: Запрос к LLM
            
        Returns:
            str: Отформатированный промпт
        """
        if request.system_prompt:
            # Для моделей, поддерживающих системный промпт
            return f"### Instruction:\n{request.system_prompt}\n\n### Input:\n{request.prompt}\n\n### Response:"
        else:
            # Просто промпт
            return f"### Input:\n{request.prompt}\n\n### Response:"
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности провайдера.
        
        Returns:
            Dict[str, Any]: Статус работоспособности
        """
        if not self._is_initialized:
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": "Provider not initialized",
                "model": self.model_name
            }
        
        try:
            # Выполняем тестовый запрос
            start_time = time.time()
            test_request = LLMRequest(prompt="health check", max_tokens=5, temperature=0.1)
            response = await self.generate(test_request)
            response_time = time.time() - start_time
            
            return {
                "status": LLMHealthStatus.HEALTHY.value,
                "model": self.model_name,
                "response_time_ms": response_time * 1000,
                "is_initialized": self._is_initialized,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "avg_response_time_ms": self.avg_response_time * 1000
            }
        except Exception as e:
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self._is_initialized
            }
    
    async def _fix_validation_error(self, content: Dict[str, Any], schema: Dict[str, Any], 
                                   error: Exception, max_retries: int) -> Dict[str, Any]:
        """
        Исправление ошибки валидации через LLM.
        
        Args:
            content: Содержимое с ошибкой
            schema: Схема валидации
            error: Ошибка валидации
            max_retries: Оставшееся количество попыток
            
        Returns:
            Dict[str, Any]: Исправленное содержимое
        """
        if max_retries <= 0:
            return content
        
        try:
            # Создаем промпт для исправления ошибки
            fix_prompt = f"""
            Исправь следующий JSON, чтобы он соответствовал схеме:
            
            Схема: {json.dumps(schema)}
            
            JSON: {json.dumps(content)}
            
            Ошибка: {str(error)}
            
            Верни ИСКЛЮЧИТЕЛЬНО валидный JSON без дополнительных объяснений:
            """
            
            fix_request = LLMRequest(
                prompt=fix_prompt,
                system_prompt="Ты — помощник по исправлению JSON. Возвращай только исправленный JSON.",
                max_tokens=2000,
                temperature=0.1
            )
            
            fix_response = await self.generate(fix_request)
            
            # Пытаемся распарсить результат
            fixed_content = json.loads(fix_response.content)
            
            # Рекурсивно валидируем исправленный контент
            return await self.validate_output(fixed_content, schema, max_retries - 1)
        except Exception:
            # Если не удалось исправить, возвращаем оригинальное содержимое
            return content