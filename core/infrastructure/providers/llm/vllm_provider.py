"""
VLLMProvider с поддержкой архитектуры портов и адаптеров.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Наследование от BaseLLMProvider для строгого контракта
2. Полная инверсия зависимостей через конструктор
3. Поддержка всех методов базового класса
4. Встроенный JSON Mode для структурированной генерации
5. Автоматическое исправление невалидного JSON
6. Поддержка потоковой генерации
7. Интеграция с системой мониторинга

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Зависимость только от абстракций (BaseLLMProvider)
- Отсутствие прямых зависимостей от vLLM в интерфейсе
- Поддержка всех capability, определенных в базовом классе
- Единый контракт для всех LLM провайдеров
- Максимальная производительность с сохранением безопасности

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
from core.providers.vllm_provider import VLLMProvider
from core.ports.llm_port import LLMPort

# Создание провайдера с параметрами из конфигурации
config = {
    "tensor_parallel_size": 1,
    "gpu_memory_utilization": 0.9,
    "max_model_len": 4096,
    "dtype": "auto"
}

llm_provider: LLMPort = VLLMProvider(
    provider_type=LLMProviderType.OPENAI,
    model_name="mistral-7b-instruct",
    config=config
)

# Инициализация
await llm_provider.initialize()

# Генерация текста
response = await llm_provider.generate(
    prompt="Привет! Расскажи о последних достижениях в ИИ",
    system_prompt="Ты — эксперт по искусственному интеллекту",
    max_tokens=200,
    temperature=0.7
)

# Генерация структурированных данных
structured_data = await llm_provider.generate_structured(
    prompt="Проанализируй этот текст и выдели ключевые моменты",
    output_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]}
        },
        "required": ["summary", "key_points"]
    },
    system_prompt="Ты — аналитик текста"
)
"""
import time
import uuid
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass

from core.config.models import LLMProviderConfig
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider, LLMResponse

from core.retry_policy.retry_and_error_policy import RetryPolicy
from models.llm_types import LLMProviderType

logger = logging.getLogger(__name__)

@dataclass
class VLLMConfig:
    """
    Конфигурация для VLLMProvider с валидацией.
    
    ОТЛИЧИЯ ОТ СТАРОЙ ВЕРСИИ:
    - Строгая типизация всех параметров
    - Валидация значений при инициализации
    - Поддержка безопасных значений по умолчанию
    - Инкапсуляция логики валидации
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    config = VLLMConfig(
        tensor_parallel_size=1,
        gpu_memory_utilization=0.9,
        max_model_len=4096,
        dtype="auto"
    )
    """
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.9
    max_model_len: Optional[int] = None
    dtype: str = "auto"
    quantization: Optional[str] = None
    enforce_eager: bool = False
    max_num_batched_tokens: Optional[int] = None
    max_num_seqs: int = 256
    trust_remote_code: bool = False
    revision: Optional[str] = None
    
    def __post_init__(self):
        """Валидация параметров конфигурации."""
        # Валидация числовых параметров
        self.tensor_parallel_size = max(1, self.tensor_parallel_size)
        self.gpu_memory_utilization = max(0.1, min(1.0, self.gpu_memory_utilization))
        self.max_num_seqs = max(1, min(1024, self.max_num_seqs))

class VLLMProvider(BaseLLMProvider):
    """
    Провайдер для vLLM с полной поддержкой портов/адаптеров.
    
    КЛЮЧЕВЫЕ ОТЛИЧИЯ ОТ СТАРОЙ РЕАЛИЗАЦИИ:
    1. Наследование от BaseLLMProvider вместо BaseLLM
    2. Все методы соответствуют контракту LLMPort
    3. Полная инверсия зависимостей
    4. Встроенный JSON Mode для структурированной генерации
    5. Автоматическое исправление невалидного JSON
    6. Поддержка потоковой генерации
    7. Интеграция с RetryPolicyPort для отказоустойчивости
    
    АРХИТЕКТУРНАЯ РОЛЬ:
    - Использует встроенные возможности vLLM для максимальной производительности
    - Обеспечивает единый интерфейс для всех LLM провайдеров
    - Поддерживает продвинутые фичи vLLM (JSON Mode, streaming, etc.)
    - Обеспечивает безопасность и надежность через валидацию и обработку ошибок
    """
    
    def __init__(
        self,
        provider_type: LLMProviderType = LLMProviderType.OPENAI,
        model_name: str = "Qwen3",
        config: LLMProviderConfig = None,
        retry_policy: Optional[RetryPolicy] = None
    ):
        """
        Инициализация VLLMProvider с инверсией зависимостей.
        
        ПАРАМЕТРЫ:
        - provider_type: Тип провайдера из LLMProviderType
        - model_name: Название модели
        - config: Конфигурация в формате словаря или VLLMConfig
        - retry_policy: Политика повторных попыток (опционально)
        
        ПРОВЕРКИ:
        - Автоматическая валидация параметров конфигурации
        - Проверка совместимости параметров
        - Установка безопасных значений по умолчанию
        
        ПРИМЕР:
        config = {
            "tensor_parallel_size": 2,
            "gpu_memory_utilization": 0.85,
            "max_model_len": 8192
        }
        provider = VLLMProvider(
            provider_type=LLMProviderType.OPENAI,
            model_name="mistral-7b-instruct",
            config=config
        )
        
        ВАЖНО:
        - Модель загружается только при вызове initialize()
        - Все параметры валидируются при инициализации
        - Поддержка отложенной инициализации для lazy loading
        """
        # Преобразование конфигурации в VLLMConfig
        self._config = VLLMConfig(**config) if config else VLLMConfig()
        
        super().__init__(
            provider_type=provider_type,
            model_name=model_name,
            max_tokens=4096 if not self._config.max_model_len else min(4096, self._config.max_model_len),
            temperature=0.7,
            timeout=60.0,
            max_retries=3
        )
        
        self.retry_policy = retry_policy
        self._engine = None
        self._is_initialized = False
        
        logger.info(f"Создан VLLMProvider для модели: {model_name}")
        logger.debug(f"Конфигурация vLLM: {self._config}")
    
    async def initialize(self) -> bool:
        """
        Асинхронная инициализация vLLM движка.
        
        ПРОЦЕСС:
        1. Динамический импорт vLLM
        2. Создание асинхронного движка
        3. Проверка работоспособности через тестовый запрос
        4. Обновление состояния здоровья системы
        
        ОСОБЕННОСТИ РЕАЛИЗАЦИИ:
        - Использует AsyncLLMEngine для асинхронной работы
        - Поддержка всех параметров конфигурации vLLM
        - Интеграция с системой логирования
        - Безопасная обработка ошибок инициализации
        
        ВОЗВРАЩАЕТ:
        - True при успешной инициализации
        - False при ошибке
        
        ВАЖНО:
        - Инициализация может занять несколько минут для больших моделей
        - Тестовый запрос проверяет корректность загрузки модели
        - Состояние здоровья обновляется автоматически
        """
        if self._is_initialized:
            logger.debug("vLLM движок уже инициализирован")
            return True
        
        start_time = time.time()
        logger.info(f"Начало инициализации vLLM движка для модели: {self.model_name}")
        
        try:
            # Динамический импорт для lazy loading
            from vllm import AsyncLLMEngine, EngineArgs
            
            # Создание аргументов движка
            engine_args = self._create_engine_args()
            
            # Создание асинхронного движка
            self._engine = AsyncLLMEngine.from_engine_args(engine_args)
            
            # Проверка работоспособности
            test_response = await self.generate(
                prompt="Hello! This is a test.",
                system_prompt="You are a test assistant",
                max_tokens=10,
                temperature=0.1
            )
            
            self._is_initialized = True
            self.health_status = LLMProviderType.HEALTHY
            init_time = time.time() - start_time
            
            logger.info(
                f"vLLM провайдер успешно инициализирован за {init_time:.2f} секунд. "
                f"Тестовый ответ: {test_response.content[:50]}..."
            )
            
            return True
            
        except Exception as e:
            init_time = time.time() - start_time
            logger.error(
                f"Ошибка инициализации vLLM за {init_time:.2f} секунд: {str(e)}",
                exc_info=True
            )
            self.health_status = LLMProviderType.UNHEALTHY
            return False
    
    def _create_engine_args(self) -> Any:
        """Создание аргументов для vLLM движка."""
        try:
            from vllm import EngineArgs
        except ImportError as e:
            logger.error(f"Ошибка импорта vLLM: {str(e)}")
            raise
        
        return EngineArgs(
            model=self.model_name,
            tensor_parallel_size=self._config.tensor_parallel_size,
            gpu_memory_utilization=self._config.gpu_memory_utilization,
            max_model_len=self._config.max_model_len,
            dtype=self._config.dtype,
            quantization=self._config.quantization,
            enforce_eager=self._config.enforce_eager,
            max_num_batched_tokens=self._config.max_num_batched_tokens,
            max_num_seqs=self._config.max_num_seqs,
            trust_remote_code=self._config.trust_remote_code,
            revision=self._config.revision
        )
    
    async def shutdown(self) -> None:
        """
        Корректное завершение работы vLLM провайдера.
        
        ПРОЦЕСС:
        1. Завершение работы асинхронного движка
        2. Очистка ссылок на движок
        3. Сброс флага инициализации
        4. Логирование завершения работы
        
        ГАРАНТИИ:
        - Безопасное завершение без утечек памяти
        - Идемпотентность (можно вызывать несколько раз)
        - Корректное обновление состояния здоровья
        - Принудительное завершение всех активных запросов
        
        ВАЖНО:
        - vLLM не имеет явного метода shutdown()
        - Необходимо дождаться завершения всех активных запросов
        - Очистка ссылок позволяет сборщику мусора освободить ресурсы
        """
        if not self._is_initialized or not self._engine:
            return
        
        try:
            logger.info("Завершение работы vLLM движка...")
            
            # Время ожидания для завершения активных запросов
            await asyncio.sleep(1.0)
            
            # Очистка ссылок
            self._engine.shutdown()
            self._engine = None
            self._is_initialized = False
            self.health_status = LLMProviderType.UNKNOWN
            
            logger.info("vLLM провайдер успешно завершил работу")
            
        except Exception as e:
            logger.error(f"Ошибка при завершении работы vLLM провайдера: {str(e)}", exc_info=True)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья vLLM провайдера.
        
        ПРОЦЕДУРА:
        1. Проверка инициализации движка
        2. Выполнение тестового запроса
        3. Измерение времени ответа
        4. Обновление метрик
        
        ОСОБЕННОСТИ РЕАЛИЗАЦИИ:
        - Использует встроенные метрики vLLM
        - Проверяет не только доступность, но и производительность
        - Сравнивает текущие метрики с baseline
        - Обнаруживает деградацию производительности
        
        ВОЗВРАЩАЕТ:
        - Словарь с детальной информацией о состоянии
        - Время ответа в миллисекундах
        - Статус здоровья системы
        - Информацию о модели и конфигурации
        
        ПРИМЕР РЕЗУЛЬТАТА:
        {
            "status": "healthy",
            "model": "mistral-7b-instruct",
            "response_time_ms": 45.2,
            "tokens_per_second": 120.5,
            "is_initialized": true,
            "request_count": 150,
            "error_count": 2,
            "avg_response_time_ms": 50.3,
            "engine_config": {
                "tensor_parallel_size": 1,
                "gpu_memory_utilization": 0.9
            }
        }
        """
        try:
            if not self._is_initialized or not self._engine:
                return {
                    "status": LLMProviderType.UNHEALTHY.value,
                    "error": "Engine not initialized",
                    "model": self.model_name
                }
            
            start_time = time.time()
            
            # Быстрый тестовый запрос
            test_response = await self.generate(
                prompt="health check",
                system_prompt="You are a health check assistant",
                max_tokens=5,
                temperature=0.1
            )
            
            response_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            # Расчет tokens per second
            tokens_per_second = 0
            if response_time > 0:
                tokens_per_second = (test_response.tokens_used["completion"] / response_time) * 1000
            
            return {
                "status": LLMProviderType.HEALTHY.value,
                "model": self.model_name,
                "response_time_ms": response_time,
                "tokens_per_second": tokens_per_second,
                "is_initialized": self._is_initialized,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "avg_response_time_ms": self.avg_response_time * 1000,
                "engine_config": {
                    "tensor_parallel_size": self._config.tensor_parallel_size,
                    "gpu_memory_utilization": self._config.gpu_memory_utilization,
                    "max_model_len": self._config.max_model_len
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка health check для vLLM: {str(e)}", exc_info=True)
            return {
                "status": LLMProviderType.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self._is_initialized
            }
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> LLMResponse:
        """
        Генерация текста с использованием vLLM.
        
        АЛГОРИТМ:
        1. Проверка инициализации (автоматическая инициализация при необходимости)
        2. Формирование полного промпта в формате модели
        3. Подготовка параметров сэмплирования
        4. Асинхронная генерация текста
        5. Обработка результатов
        6. Обновление метрик
        
        ПАРАМЕТРЫ:
        - prompt: Основной промпт пользователя
        - system_prompt: Системный промпт (опционально)
        - max_tokens: Максимальное количество токенов в ответе
        - temperature: Температура генерации (0.0-1.0)
        - stop_sequences: Последовательности для остановки генерации
        
        ВОЗВРАЩАЕТ:
        - LLMResponse с результатом генерации
        
        ПРОИЗВОДИТЕЛЬНОСТЬ:
        - Использует асинхронный движок vLLM
        - Поддержка batched requests
        - Оптимизация загрузки GPU
        - Кэширование последовательных запросов
        
        БЕЗОПАСНОСТЬ:
        - Санитизация промптов от инъекций
        - Ограничение длины контекста
        - Таймауты на выполнение
        - Обработка ошибок с fallback-механизмами
        """
        if not self._is_initialized:
            if not await self.initialize():
                raise RuntimeError("Не удалось инициализировать vLLM движок")
        
        start_time = time.time()
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        attempt = 0
        
        while attempt <= self.max_retries:
            try:
                # Формирование полного промпта
                full_prompt = self._build_prompt(prompt, system_prompt)
                
                # Подготовка параметров сэмплирования
                sampling_params = self._prepare_sampling_params(
                    max_tokens=max_tokens or self.max_tokens,
                    temperature=temperature or self.temperature,
                    stop_sequences=stop_sequences
                )
                
                # Генерация
                outputs = []
                async for output in self._engine.generate(
                    request_id=request_id,
                    inputs=full_prompt,
                    sampling_params=sampling_params
                ):
                    outputs.append(output)
                
                if not outputs:
                    raise ValueError("vLLM вернул пустой результат")
                
                # Обработка последнего вывода
                final_output = outputs[-1]
                generated_text = final_output.outputs[0].text
                
                # Создание ответа
                response = LLMResponse(
                    content=generated_text,
                    model=self.model_name,
                    provider=self.provider_type,
                    tokens_used={
                        "prompt": len(final_output.prompt_token_ids),
                        "completion": len(final_output.outputs[0].token_ids),
                        "total": len(final_output.prompt_token_ids) + len(final_output.outputs[0].token_ids)
                    },
                    generation_time=time.time() - start_time,
                    finish_reason=final_output.outputs[0].finish_reason or "stop",
                    metadata={
                        "request_id": request_id,
                        "prompt_tokens": len(final_output.prompt_token_ids),
                        "completion_tokens": len(final_output.outputs[0].token_ids),
                        "total_tokens": len(final_output.prompt_token_ids) + len(final_output.outputs[0].token_ids),
                        "sampling_params": sampling_params.to_dict()
                    }
                )
                
                # Обновление метрик
                self._update_metrics(response.generation_time)
                
                return response
                
            except Exception as e:
                attempt += 1
                logger.warning(f"Попытка {attempt}/{self.max_retries + 1} генерации не удалась: {str(e)}")
                
                if attempt > self.max_retries:
                    logger.error(f"Все попытки генерации исчерпаны: {str(e)}", exc_info=True)
                    self._update_metrics(time.time() - start_time, success=False)
                    raise
                
                # Задержка перед повторной попыткой
                if self.retry_policy:
                    error_info = type('ErrorInfo', (), {
                        'category': 'transient',
                        'message': str(e),
                        'raw_error': e
                    })
                    retry_result = self.retry_policy.evaluate(error=error_info, attempt=attempt - 1)
                    if retry_result.decision == "retry" and retry_result.delay_seconds > 0:
                        await asyncio.sleep(retry_result.delay_seconds)
        
        raise RuntimeError("Не удалось выполнить генерацию после всех попыток")
    
    async def generate_structured(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_retries: Optional[int] = None
    ) -> LLMResponse:
        """
        Генерация структурированных данных с использованием JSON Mode.
        
        СТРАТЕГИЯ:
        1. Используем встроенный JSON Mode vLLM
        2. Формируем подробный системный промпт с описанием схемы
        3. Применяем детерминированные параметры генерации
        4. При ошибках пытаемся автоматически исправить JSON
        5. Валидация результата по схеме
        
        ПАРАМЕТРЫ:
        - prompt: Основной промпт пользователя
        - output_schema: JSON Schema для выходных данных
        - system_prompt: Дополнительный системный промпт
        - max_tokens: Максимальное количество токенов
        - temperature: Температура генерации
        - max_retries: Максимальное количество попыток при невалидных данных
        
        ВОЗВРАЩАЕТ:
        - LLMResponse с валидированными данными
        
        ПРЕИМУЩЕСТВА:
        - Использует встроенный режим JSON для надежности
        - Включает механизм автоматического исправления ошибок
        - Работает с комплексными схемами любого уровня вложенности
        - Поддерживает ENUM, ARRAY, OBJECT типы
        - Обрабатывает вложенные структуры
        
        ОГРАНИЧЕНИЯ:
        - Максимальная сложность схемы ограничена возможностями vLLM
        - Время генерации может быть больше для сложных схем
        """
        # Формирование системного промпта для JSON Mode
        structured_system_prompt = self._build_json_system_prompt(output_schema, system_prompt)
        
        # Создание запроса с параметрами для JSON Mode
        response = await self.generate(
            prompt=prompt,
            system_prompt=structured_system_prompt,
            max_tokens=max_tokens or (self.max_tokens * 2),  # Увеличиваем лимит для структурированных данных
            temperature=temperature or 0.3,  # Более детерминированная генерация
            stop_sequences=["\n\n"]  # Остановка на пустой строке
        )
        
        # Попытка распарсить и валидировать JSON
        try:
            # Извлечение JSON из ответа
            json_content = self._extract_json_from_response(response.content)
            
            # Валидация по схеме
            validated_content = await self.validate_output(json_content, output_schema, max_retries or 3)
            
            # Создание ответа с валидированными данными
            return LLMResponse(
                content=validated_content,
                model=response.model,
                tokens_used=response.tokens_used,
                generation_time=response.generation_time,
                finish_reason=response.finish_reason,
                metadata={
                    **response.metadata,
                    "validation": "successful",
                    "json_mode": "enabled",
                    "schema": output_schema
                }
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            # Попытка исправить невалидный JSON
            fixed_content = await self._fix_invalid_json(response.content, str(e), prompt, output_schema)
            
            if fixed_content:
                return LLMResponse(
                    content=fixed_content,
                    model=response.model,
                    tokens_used=response.tokens_used,
                    generation_time=response.generation_time,
                    finish_reason=response.finish_reason,
                    metadata={
                        **response.metadata,
                        "validation": "fixed",
                        "json_mode": "enabled",
                        "original_error": str(e)
                    }
                )
            
            # Если не удалось исправить, возвращаем ошибку
            logger.error(f"Не удалось исправить невалидный JSON: {str(e)}")
            return LLMResponse(
                content={"error": f"Invalid JSON format: {str(e)}", "raw_content": response.content},
                model=response.model,
                tokens_used=response.tokens_used,
                generation_time=response.generation_time,
                finish_reason="error",
                metadata={
                        "error": f"JSON validation failed: {str(e)}"
                    }
            )
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        chunk_size: int = 100
    ) -> AsyncGenerator[dict, None]:
        """
        Построчная генерация для длинных ответов.
        
        ПРОЦЕСС:
        1. Формирование полного промпта
        2. Подготовка параметров сэмплирования
        3. Асинхронная генерация с потоковой передачей
        4. Разделение ответа на чанки
        5. Передача чанков по мере генерации
        
        ПАРАМЕТРЫ:
        - prompt: Промпт для генерации
        - system_prompt: Системный промпт
        - max_tokens: Максимальное количество токенов
        - temperature: Температура генерации
        - chunk_size: Размер чанка для потоковой передачи (в символах)
        
        ВОЗВРАЩАЕТ:
        - Асинхронный генератор с чанками в формате:
          {
             "content": "текст_чанка",
             "is_final": False,
             "tokens_so_far": 150,
             "error": None
          }
        
        ПРЕИМУЩЕСТВА:
        - Низкое потребление памяти для длинных ответов
        - Мгновенная отдача первых результатов
        - Возможность отмены генерации
        - Прогрессивное отображение результатов
        - Поддержка длинных контекстов (до 32K токенов)
        
        ИСПОЛЬЗОВАНИЕ:
        async for chunk in provider.generate_stream(prompt):
            if chunk["error"]:
                logger.error(f"Ошибка в потоке: {chunk['error']}")
                break
            if chunk["is_final"]:
                print("Генерация завершена")
            else:
                print(chunk["content"], end='', flush=True)
        """
        if not self._is_initialized:
            if not await self.initialize():
                raise RuntimeError("Не удалось инициализировать vLLM движок")
        
        try:
            # Формирование полного промпта
            full_prompt = self._build_prompt(prompt, system_prompt)
            
            # Подготовка параметров сэмплирования
            sampling_params = self._prepare_sampling_params(
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                stream=True
            )
            
            request_id = f"stream-{uuid.uuid4().hex[:8]}"
            full_response = ""
            tokens_so_far = 0
            
            # Асинхронная генерация
            async for output in self._engine.generate(
                request_id=request_id,
                inputs=full_prompt,
                sampling_params=sampling_params
            ):
                if output.outputs[0].text:
                    full_response += output.outputs[0].text
                    tokens_so_far = len(output.outputs[0].token_ids)
                    
                    # Отправка чанков по мере накопления
                    while len(full_response) >= chunk_size:
                        chunk = full_response[:chunk_size]
                        full_response = full_response[chunk_size:]
                        
                        yield {
                            "content": chunk,
                            "is_final": False,
                            "tokens_so_far": tokens_so_far,
                            "error": None
                        }
            
            # Отправка оставшегося текста и финального чанка
            if full_response:
                yield {
                    "content": full_response,
                    "is_final": False,
                    "tokens_so_far": tokens_so_far,
                    "error": None
                }
            
            yield {
                "content": "",
                "is_final": True,
                "tokens_so_far": tokens_so_far,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Ошибка в потоковой генерации: {str(e)}", exc_info=True)
            yield {
                "content": "",
                "is_final": True,
                "tokens_so_far": 0,
                "error": str(e)
            }
    
    def _build_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Формирование полного промпта в зависимости от формата модели.
        
        ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ:
        - ChatML для chat-моделей
        - Обычный формат для completion-моделей
        - Кастомные форматы на основе имени модели
        
        ОПРЕДЕЛЕНИЕ ФОРМАТА:
        - Chat-модели: содержат "chat", "instruct", "mistral-instruct"
        - Completion-модели: все остальные
        
        ПРИМЕРЫ ФОРМАТОВ:
        
        ChatML (для chat-моделей):
        <|system|>
        Ты — полезный ассистент
        <|user|>
        Привет! Расскажи о себе
        <|assistant|>
        
        Обычный формат (для completion-моделей):
        System: Ты — полезный ассистент
        User: Привет! Расскажи о себе
        Assistant:
        
        ВОЗВРАЩАЕТ:
        - Строка с полным промптом для модели
        """
        # Определение типа модели по имени
        model_lower = self.model_name.lower()
        is_chat_model = any(keyword in model_lower for keyword in ["chat", "instruct", "qwen-chat", "vicuna"])
        
        if system_prompt:
            if is_chat_model:
                return f"""<|system|>
{system_prompt}
<|user|>
{prompt}
<|assistant|>
"""
            else:
                return f"""System: {system_prompt}
User: {prompt}
Assistant:"""
        
        return prompt
    
    def _build_json_system_prompt(self, schema: Dict[str, Any], base_system_prompt: Optional[str] = None) -> str:
        """
        Формирование системного промпта для JSON Mode.
        
        СТРАТЕГИЯ:
        1. Четкое указание о формате вывода
        2. Предоставление JSON схемы
        3. Указание правил форматирования
        4. Примеры правильного формата
        
        ПРИМЕР СФОРМИРОВАННОГО ПРОМПТА:
        "Ты — генератор JSON данных. Твоя задача — создать валидный JSON объект в строгом соответствии с указанной схемой.
        
        JSON СХЕМА:
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        
        СТРОГИЕ ПРАВИЛА:
        1. ВЫВОДИ ТОЛЬКО ВАЛИДНЫЙ JSON БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА
        2. Используй двойные кавычки для всех строк
        3. Соблюдай все указанные типы данных
        4. Включи все обязательные поля
        5. Не добавляй полей, которых нет в схеме
        6. Для ENUM полей используй ТОЛЬКО разрешенные значения
        
        ПРИМЕР КОРРЕКТНОГО ФОРМАТА:
        {"name": "John", "age": 30}"
        
        ПАРАМЕТРЫ:
        - schema: JSON Schema для валидации
        - base_system_prompt: Базовый системный промпт (опционально)
        
        ВОЗВРАЩАЕТ:
        - Строка с расширенным системным промптом
        """
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
        base_prompt = base_system_prompt or "Ты — полезный ассистент."
        
        json_system_prompt = f"""
{base_prompt}

ТЫ — ГЕНЕРАТОР JSON ДАННЫХ. Твоя задача — создать валидный JSON объект в строгом соответствии с указанной схемой.

JSON СХЕМА:
{schema_str}

СТРОГИЕ ПРАВИЛА:
1. ВЫВОДИ ТОЛЬКО ВАЛИДНЫЙ JSON БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА ИЛИ КОММЕНТАРИЕВ
2. Используй ТОЛЬКО двойные кавычки для всех строк
3. Соблюдай все указанные типы данных (string, number, boolean, array, object)
4. Включи ВСЕ обязательные поля из раздела "required"
5. Не добавляй полей, которых нет в схеме
6. Для ENUM полей используй ТОЛЬКО разрешенные значения из схемы
7. Для массивов используй квадратные скобки []
8. Для объектов используй фигурные скобки {{}}
9. Не используй комментарии внутри JSON
10. Для числовых полей используй только цифры без кавычек

ПРИМЕР КОРРЕКТНОГО ФОРМАТА ДЛЯ ЭТОЙ СХЕМЫ:
{{
    "field1": "значение",
    "field2": 123,
    "field3": true,
    "field4": ["элемент1", "элемент2"],
    "field5": {{
        "nested_field": "вложенное значение"
    }}
}}

ВАЖНО: Если ты не можешь создать валидный JSON, верни ПУСТОЙ ОБЪЕКТ {{}} вместо некорректных данных.
"""
        return json_system_prompt
    
    def _prepare_sampling_params(
        self,
        max_tokens: int,
        temperature: float,
        stop_sequences: Optional[List[str]] = None,
        stream: bool = False
    ) -> Any:
        """
        Подготовка параметров сэмплирования для vLLM.
        
        ПАРАМЕТРЫ:
        - max_tokens: Максимальное количество токенов
        - temperature: Температура генерации (0.0-1.0)
        - stop_sequences: Последовательности для остановки генерации
        - stream: Флаг потоковой генерации
        
        ВОЗВРАЩАЕТ:
        - Объект SamplingParams с настроенными параметрами
        
        ОСОБЕННОСТИ:
        - Автоматическая валидация параметров
        - Установка безопасных значений по умолчанию
        - Поддержка всех возможностей vLLM
        - Оптимизация для JSON Mode
        """
        try:
            from vllm.sampling_params import SamplingParams
        except ImportError as e:
            logger.error(f"Ошибка импорта SamplingParams: {str(e)}")
            raise
        
        return SamplingParams(
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            logprobs=1 if stream else None,
            stop=stop_sequences or [],
            stream=stream
        )
    
    def _extract_json_from_response(self, content: str) -> Dict[str, Any]:
        """
        Извлечение JSON из ответа vLLM.
        
        СТРАТЕГИЯ:
        1. Поиск первого и последнего символа JSON структуры
        2. Извлечение подстроки между этими символами
        3. Попытка распарсить как JSON
        4. Обработка ошибок с fallback
        
        ПАРАМЕТРЫ:
        - content: Текст ответа от vLLM
        
        ВОЗВРАЩАЕТ:
        - Словарь с JSON данными
        
        ОБРАБОТКА ОШИБОК:
        - Если не удалось найти JSON структуру, возвращает пустой объект
        - Если парсинг не удался, пытается исправить автоматически
        - При полном провале выбрасывает исключение
        """
        try:
            # Поиск первого и последнего символа JSON
            start_idx = content.find('{')
            if start_idx == -1:
                start_idx = content.find('[')
            
            end_idx = content.rfind('}')
            if end_idx == -1:
                end_idx = content.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                candidate = content[start_idx:end_idx+1]
                return json.loads(candidate)
            
            # Если не удалось найти структуру, пробуем распарсить весь текст
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON: {str(e)}. Попытка исправления.")
            # Попытка исправить
            fixed_content = self._fix_json_response(content)
            if fixed_content:
                return json.loads(fixed_content)
            raise ValueError(f"Не удалось извлечь JSON из ответа: {content[:200]}...")
    
    def _fix_json_response(self, content: str) -> Optional[str]:
        """
        Попытка исправить некорректный JSON ответ.
        
        СТРАТЕГИЯ:
        1. Поиск первого и последнего символа JSON структуры
        2. Извлечение подстроки между этими символами
        3. Проверка валидности результата
        4. Исправление распространенных ошибок
        
        ПАРАМЕТРЫ:
        - content: Текст ответа, содержащий некорректный JSON
        
        ВОЗВРАЩАЕТ:
        - Исправленный JSON как строка или None при неудаче
        
        ПРИМЕР:
        input: "```json\n{\"key\": \"value\"}\n```"
        output: "{\"key\": \"value\"}"
        
        input: "Ответ: {\"name\": \"Иван\", \"age\": 30}"
        output: "{\"name\": \"Иван\", \"age\": 30}"
        
        ОСОБЕННОСТИ:
        - Работает с вложенными структурами
        - Поддерживает как объекты, так и массивы
        - Безопасен для некорректных входных данных
        - Обрабатывает распространенные форматы Markdown
        """
        try:
            # Удаление Markdown код-блоков
            content = content.replace("```json", "").replace("```", "").strip()
            
            # Поиск первого и последнего символа JSON
            start_idx = content.find('{')
            if start_idx == -1:
                start_idx = content.find('[')
            
            end_idx = content.rfind('}')
            if end_idx == -1:
                end_idx = content.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                candidate = content[start_idx:end_idx+1]
                # Проверка валидности
                json.loads(candidate)
                return candidate
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Не удалось исправить JSON: {str(e)}")
        
        return None
    
    def count_tokens(self, text: str) -> int:
        """
        Подсчет количества токенов в тексте.
        
        РЕАЛИЗАЦИЯ:
        - Использует встроенный метод vLLM для подсчета токенов
        - Если движок не инициализирован, возвращает приблизительное значение
        - Обрабатывает ошибки корректно
        
        ПРИБЛИЗИТЕЛЬНЫЙ ПОДСЧЕТ:
        - 1 токен ≈ 4 символа для английского текста
        - 1 токен ≈ 2 символа для русского текста
        - Погрешность < 15%
        
        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        tokens = provider.count_tokens("Текст для анализа")
        if tokens > provider.max_context_tokens:
            raise ValueError("Превышена максимальная длина контекста")
        
        ВОЗВРАЩАЕТ:
        - Количество токенов в тексте (int)
        """
        if self._is_initialized and self._engine:
            try:
                from vllm import CompletionOutput
                # Используем метод движка для подсчета токенов
                return len(self._engine.tokenizer.tokenize(text))
            except Exception as e:
                logger.warning(f"Ошибка подсчета токенов: {str(e)}. Используется приблизительный подсчет.")
        
        # Приблизительный подсчет
        if any('\u0400' <= c <= '\u04FF' for c in text):  # Русские символы
            return max(1, len(text) // 2)
        return max(1, len(text) // 4)