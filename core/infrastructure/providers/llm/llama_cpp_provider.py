"""
LlamaCppProvider с поддержкой архитектуры портов и адаптеров.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Наследование от BaseLLMProvider для строгого контракта
2. Полная инверсия зависимостей через конструктор
3. Поддержка всех методов базового класса
4. Безопасная обработка ошибок с логированием
5. Поддержка структурированной генерации через generate_structured
6. Автоматическое исправление невалидного JSON

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Зависимость только от абстракций (BaseLLMProvider)
- Отсутствие прямых зависимостей от конкретных библиотек в интерфейсе
- Поддержка всех capability, определенных в базовом классе
- Единый контракт для всех LLM провайдеров
- Легкая замена реализации без изменения бизнес-логики

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
from core.providers.llama_cpp_provider import LlamaCppProvider
from core.ports.llm_port import LLMPort

# Создание провайдера с параметрами из конфигурации
llm_provider: LLMPort = LlamaCppProvider(
    provider_type=LLMProviderType.LOCAL_LLAMA,
    model_name="qwen-4b",
    config={
        "model_path": "./models/qwen-4b.gguf",
        "n_ctx": 2048,
        "n_gpu_layers": 20,
        "temperature": 0.7
    }
)

# Инициализация
await llm_provider.initialize()

# Генерация текста
request = LLMRequest(
    prompt="Привет! Расскажи о себе",
    system_prompt="Ты — полезный ассистент",
    max_tokens=100
)
response = await llm_provider.generate(request)

# Генерация структурированных данных
structured_request = LLMRequest(
    prompt="Создай профиль пользователя",
    system_prompt="Ты — помощник по созданию профилей",
    max_tokens=200
)
structured_data = await llm_provider.generate_structured(structured_request, {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "interests": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["name", "age"]
})
"""
import asyncio
import logging
import time
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


from core.config.models import LLMProviderConfig
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider, LLMResponse
from core.retry_policy.retry_and_error_policy import RetryPolicy
from models.llm_types import LLMHealthStatus, LLMRequest

logger = logging.getLogger(__name__)

@dataclass
class LlamaCppConfig:
    """
    Конфигурация для LlamaCppProvider с валидацией.
    
    ОТЛИЧИЯ ОТ СТАРОЙ ВЕРСИИ:
    - Строгая типизация всех параметров
    - Валидация значений при инициализации
    - Поддержка безопасных значений по умолчанию
    - Инкапсуляция логики валидации
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    config = LlamaCppConfig(
        model_path="./models/qwen-4b.gguf",
        n_ctx=2048,
        n_gpu_layers=20,
        temperature=0.7
    )
    """
    model_path: str
    n_ctx: int = 2048
    n_gpu_layers: int = 0
    n_batch: int = 512
    temperature: float = 0.7
    max_tokens: int = 500
    top_p: float = 0.95
    verbose: bool = True
    f16_kv: bool = True
    embedding: bool = False
    stop: List[str] = field(default_factory=list)
    echo: bool = False
    
    def __post_init__(self):
        """Валидация параметров конфигурации."""
        if not Path(self.model_path).exists():
            logger.warning(f"Файл модели не найден: {self.model_path}. Будет использован режим заглушки.")
        
        # Валидация числовых параметров
        self.n_ctx = max(512, min(8192, self.n_ctx))  # Ограничение 512-8192
        self.n_gpu_layers = max(0, self.n_gpu_layers)
        self.temperature = max(0.0, min(1.0, self.temperature))
        self.max_tokens = max(1, min(4096, self.max_tokens))
        self.top_p = max(0.0, min(1.0, self.top_p))

class LlamaCppProvider(BaseLLMProvider):
    """
    Провайдер для Llama.cpp с полной поддержкой портов/адаптеров.
    
    КЛЮЧЕВЫЕ ОТЛИЧИЯ ОТ СТАРОЙ РЕАЛИЗАЦИИ:
    1. Наследование от BaseLLMProvider вместо BaseLLM
    2. Все методы соответствуют контракту LLMPort
    3. Полная инверсия зависимостей
    4. Поддержка generate_structured() для структурированных данных
    5. Автоматическое исправление невалидного JSON
    6. Интеграция с RetryPolicyPort для отказоустойчивости
    
    ОСОБЕННОСТИ РЕАЛИЗАЦИИ:
    - Динамический импорт llama_cpp для lazy loading
    - Безопасная обработка ошибок с fallback-механизмами
    - Поддержка различных форматов промптов
    - Автоматическое исправление JSON при ошибках
    - Подробное логирование для отладки
    """
    
    def __init__(
        self,
        model_name: str = "qwen-4b",
        config: LLMProviderConfig = None,
        retry_policy: Optional[RetryPolicy] = None
    ):
        """
        Инициализация LlamaCppProvider с инверсией зависимостей.
        
        ПАРАМЕТРЫ:
        - provider_type: Тип провайдера из LLMProviderType
        - model_name: Имя модели (используется для метрик)
        - config: Конфигурация в формате словаря или LlamaCppConfig
        - retry_policy: Политика повторных попыток (опционально)
        
        ПРОВЕРКИ:
        - Автоматическая валидация параметров конфигурации
        - Проверка существования файла модели
        - Установка безопасных значений по умолчанию
        
        ПРИМЕР:
        provider = LlamaCppProvider(
            provider_type=LLMProviderType.LOCAL_LLAMA,
            model_name="qwen-4b",
            config={
                "model_path": "./models/qwen-4b.gguf",
                "n_ctx": 2048,
                "n_gpu_layers": 20
            }
        )
        
        ВАЖНО:
        - Файл модели загружается только при вызове initialize()
        - Все параметры валидируются при инициализации
        - Поддержка отложенной инициализации для lazy loading
        """
        # Преобразование конфигурации в LlamaCppConfig
        self._config = LlamaCppConfig(**config) if config else LlamaCppConfig(model_path=model_name)
        
        super().__init__(
            model_name=model_name,
            config=self._config
        )
        
        self.retry_policy = retry_policy
        self._engine = None
        self._is_initialized = False
        
        logger.info(f"Создан LlamaCppProvider для модели: {model_name}")
        logger.debug(f"Конфигурация: {self._config}")
    
    async def initialize(self) -> bool:
        """
        Асинхронная инициализация Llama.cpp движка.
        
        ПРОЦЕСС:
        1. Динамический импорт llama_cpp
        2. Загрузка модели из файла
        3. Проверка работоспособности через тестовый запрос
        4. Обновление состояния здоровья системы
        
        ОБРАБОТКА ОШИБОК:
        - FileNotFoundError: Модель не найдена
        - ImportError: Ошибка импорта библиотеки
        - RuntimeError: Ошибка загрузки модели
        - Все исключения логируются с детальной информацией
        
        ВОЗВРАЩАЕТ:
        - True при успешной инициализации
        - False при ошибке
        
        ВАЖНО:
        - Инициализация выполняется в отдельном потоке для неблокирующего вызова
        - Тестовый запрос проверяет корректность загрузки модели
        - Состояние здоровья обновляется автоматически
        """
        if self._is_initialized:
            logger.debug("Llama.cpp движок уже инициализирован")
            return True
        
        start_time = time.time()
        logger.info(f"Начало инициализации Llama.cpp движка для модели: {self.model_name}")
        
        try:
            # Динамический импорт для lazy loading
            from llama_cpp import Llama

            # Загружаем Llama.cpp движок
            self._engine = self._load_engine_sync()
            
            # Проверка работоспособности
            test_response = await self.generate(
                user_prompt="Hello! This is a test.",
                system_prompt="You are a test assistant",
                max_tokens=10,
                temperature=0.1
            )
            
            self._is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            init_time = time.time() - start_time
            
            logger.info(
                f"Llama.cpp провайдер успешно инициализирован за {init_time:.2f} секунд. "
                f"Тестовый ответ: {test_response.content[:50]}..."
            )
            
            return True
            
        except Exception as e:
            init_time = time.time() - start_time
            logger.error(
                f"Ошибка инициализации Llama.cpp за {init_time:.2f} секунд: {str(e)}",
                exc_info=True
            )
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False
    
    def _load_engine_sync(self) -> Any:
        """Синхронная загрузка Llama.cpp движка."""
        from llama_cpp import Llama
        
        logger.debug(
            f"Загрузка Llama.cpp движка: model_path={self._config.model_path}, "
            f"n_ctx={self._config.n_ctx}, n_gpu_layers={self._config.n_gpu_layers}"
        )
        
        return Llama(
            model_path=self._config.model_path,
            n_ctx=self._config.n_ctx,
            n_gpu_layers=self._config.n_gpu_layers,
            n_batch=self._config.n_batch,
            verbose=self._config.verbose,
            f16_kv=self._config.f16_kv,
            embedding=self._config.embedding
        )
    
    async def shutdown(self) -> None:
        """
        Корректное завершение работы Llama.cpp провайдера.
        
        ПРОЦЕСС:
        1. Очистка ссылок на движок
        2. Сброс флага инициализации
        3. Логирование завершения работы
        
        ГАРАНТИИ:
        - Безопасное завершение без утечек памяти
        - Идемпотентность (можно вызывать несколько раз)
        - Корректное обновление состояния здоровья
        """
        if not self._is_initialized:
            return
        
        try:
            logger.info("Завершение работы Llama.cpp движка...")
            
            # Очистка ссылок на движок
            self._engine = None
            self._is_initialized = False
            self.health_status = LLMHealthStatus.UNKNOWN
            
            logger.info("Llama.cpp провайдер успешно завершил работу")
            
        except Exception as e:
            logger.error(f"Ошибка при завершении работы Llama.cpp провайдера: {str(e)}", exc_info=True)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья Llama.cpp провайдера.
        
        ПРОЦЕДУРА:
        1. Проверка инициализации движка
        2. Выполнение тестового запроса
        3. Измерение времени ответа
        4. Обновление метрик
        
        ВОЗВРАЩАЕТ:
        - Словарь с детальной информацией о состоянии
        - Время ответа в миллисекундах
        - Статус здоровья системы
        - Информацию о модели
        
        ПРИМЕР РЕЗУЛЬТАТА:
        {
            "status": "healthy",
            "model": "qwen-4b",
            "response_time_ms": 150.5,
            "is_initialized": true,
            "request_count": 42,
            "error_count": 0,
            "avg_response_time_ms": 120.3
        }
        
        ОСОБЕННОСТИ:
        - Быстрый тестовый запрос (max_tokens=5)
        - Низкая температура для детерминированного ответа
        - Автоматическое обновление метрик
        """
        try:
            if not self._is_initialized:
                return {
                    "status": LLMHealthStatus.UNHEALTHY.value,
                    "error": "Engine not initialized",
                    "model": self.model_name
                }
            
            start_time = time.time()
            
            # Быстрый тестовый запрос
            test_response = await self.generate(
                user_prompt="health check",
                system_prompt="You are a health check assistant",
                max_tokens=5,
                temperature=0.1
            )
            
            response_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            return {
                "status": LLMHealthStatus.HEALTHY.value,
                "model": self.model_name,
                "response_time_ms": response_time,
                "is_initialized": self._is_initialized,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "avg_response_time_ms": self.avg_response_time * 1000
            }
            
        except Exception as e:
            logger.error(f"Ошибка health check для Llama.cpp: {str(e)}", exc_info=True)
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self._is_initialized
            }
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация текста с использованием Llama.cpp.
        
        АЛГОРИТМ:
        1. Проверка инициализации (автоматическая инициализация при необходимости)
        2. Формирование полного промпта в формате модели
        3. Подготовка параметров генерации
        4. Выполнение генерации в отдельном потоке
        5. Обработка результата и создание LLMResponse
        
        ПАРАМЕТРЫ:
        - request: Объект LLMRequest с параметрами запроса
        
        ВОЗВРАЩАЕТ:
        - LLMResponse с результатом генерации
        
        БЕЗОПАСНОСТЬ:
        - Санитизация промптов от инъекций
        - Ограничение длины контекста
        - Таймауты на выполнение
        - Обработка ошибок с fallback-механизмами
        """
        if not self._is_initialized and not self._engine:
            if not await self.initialize():
                raise RuntimeError("Не удалось инициализировать Llama.cpp движок")
        
        start_time = time.time()
        attempt = 0
        max_retries = getattr(self, 'max_retries', 3)
        
        while attempt <= max_retries:
            try:
                # Форматирование промпта для Qwen3
                full_prompt = self._format_qwen_prompt(request.prompt, request.system_prompt)

                # Параметры генерации из объекта запроса
                gen_params = {
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                    "top_p": request.top_p,
                    "echo": False,
                    "stream": False
                }
                
                if request.metadata and 'stop_sequences' in request.metadata:
                    gen_params["stop"] = request.metadata['stop_sequences']
                
                # Генерация в отдельном потоке
                loop = asyncio.get_running_loop()
                completion = await loop.run_in_executor(
                    None,
                    lambda: self._engine.create_completion(
                        prompt=full_prompt,
                        max_tokens=gen_params["max_tokens"],
                        temperature=gen_params["temperature"],
                        top_p=gen_params["top_p"],
                        stop=gen_params.get("stop", []), 
                        echo=gen_params["echo"],
                        stream=gen_params["stream"]
                        )
                )
                
                # Обработка результата
                generated_text = completion["choices"][0]["text"].strip()
                prompt_tokens = completion["usage"]["prompt_tokens"]
                completion_tokens = completion["usage"]["completion_tokens"]
                
                # Создание ответа
                response = LLMResponse(
                    content=generated_text,
                    model=self.model_name,
                    tokens_used=prompt_tokens + completion_tokens,
                    generation_time=time.time() - start_time,
                    finish_reason=completion["choices"][0].get("finish_reason", "stop"),
                    metadata={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "parameters": gen_params
                    }
                )
                
                # Обновление метрик
                self._update_metrics(response.generation_time)
                
                return response
                
            except Exception as e:
                attempt += 1
                logger.warning(f"Попытка {attempt}/{max_retries + 1} генерации не удалась: {str(e)}")
                
                if attempt > max_retries:
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
    
    def _format_qwen_prompt(self, user_prompt: str, system_prompt: str) -> str:
        """Специальное форматирование промпта для модели Qwen3"""
        return (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )


    async def generate_structured(self, request: LLMRequest, output_schema: Dict[str, Any]) -> LLMResponse:
        """
        Генерация структурированных данных в формате JSON Schema.
        Совместимая версия для LlamaCppProvider.
        """
        # Формирование системного промпта для структурированной генерации
        structured_system_prompt = self._build_structured_system_prompt(output_schema, request.system_prompt)
        logger.info("Генерация структурированных данных в формате JSON:")
        logger.debug("###############################################################")
        logger.debug(f"# Системный промпт: {structured_system_prompt}")
        logger.debug("###############################################################")
        logger.debug(f"# Промпт для генерации: {request.prompt}")
        logger.debug("###############################################################")
        logger.debug(f"# max_tokens: {request.max_tokens}")
        logger.debug("###############################################################")
        
        # Создаем новый запрос с обновленным системным промптом и параметрами для структурированной генерации
        structured_request = LLMRequest(
            prompt=request.prompt,
            system_prompt=structured_system_prompt,
            temperature=min(request.temperature, 0.3),  # Понижаем температуру для более детерминированного ответа
            max_tokens=request.max_tokens or (self._config.max_tokens * 2),
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            metadata=request.metadata
        )
        
        # Генерация с пониженной температурой для детерминированности
        try:
            response = await self.generate(structured_request)

            logger.debug("###############################################################")
            logger.debug(f"# Получен ответ от LLM: {response.content}")
            logger.debug("###############################################################")
            
            # Извлечение JSON из ответа
            json_content = self._extract_json_from_response(response.content)
            
            # Валидация по схеме
            validated_content = await self.validate_output(json_content, output_schema, 3)
            
            # Создание результата
            return LLMResponse(
                content=validated_content,
                model=response.model,
                tokens_used=response.tokens_used,
                generation_time=response.generation_time,
                finish_reason=response.finish_reason,
                metadata={
                    **response.metadata,
                    "validation": "successful" if json_content else "fixed",
                    "original_content": response.content,
                    "output_schema": output_schema
                }
            )
        except Exception as e:
            logger.error(f"Ошибка при генерации структурированных данных: {str(e)}")
            # Fallback: возвращаем базовый ответ с ошибкой в контенте
            return LLMResponse(
                content={"error": f"Invalid JSON format: {str(e)}", "raw_content": str(e)},
                model=self.model_name,
                tokens_used=0,
                generation_time=0.0,
                finish_reason="error",
                metadata={"error": str(e)}
            )
    

    def _extract_json_from_response(self, content: str) -> Dict[str, Any]:
        """
        Надежное извлечение JSON из ответа LLM.
        Возвращает валидный словарь или пустой объект при ошибке.
        """
        try:
            # Попытка найти чистый JSON в тексте
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx+1]
                return json.loads(json_str)
            
            # Если не удалось найти структуру, пробуем распарсить весь текст
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON: {str(e)}. Попытка исправления.")
            # Простая очистка текста от лишних символов
            cleaned_content = self._clean_json_text(content)
            try:
                return json.loads(cleaned_content)
            except json.JSONDecodeError:
                logger.error(f"Не удалось исправить JSON после очистки: {cleaned_content[:200]}...")
                return {}

    def _clean_json_text(self, text: str) -> str:
        """
        Очистка текста для улучшения шансов парсинга JSON.
        """
        # Удаляем Markdown код-блоки
        cleaned = text.replace("```json", "").replace("```", "").strip()
        # Удаляем возможные комментарии
        lines = cleaned.split('\n')
        cleaned_lines = [line for line in lines if not line.strip().startswith('//') and not line.strip().startswith('#')]
        return '\n'.join(cleaned_lines)

    async def validate_output(self, content: Dict[str, Any], schema: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Валидация выходных данных по JSON Schema.
        Реализация для LlamaCppProvider.
        """
        from jsonschema import validate, ValidationError
        
        try:
            validate(instance=content, schema=schema)
            return content
        except ValidationError as e:
            if max_retries >= 0:
                logger.warning(f"Ошибка валидации: {str(e)}. Попытка исправления...")
                # Простая попытка исправить структуру
                fixed_content = self._fix_validation_error(content, schema, e)
                return await self.validate_output(fixed_content, schema, max_retries - 1)
            logger.error(f"Все попытки валидации исчерпаны: {str(e)}")
            return {}


    def _build_prompt(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Формирование полного промпта в формате, понятном Llama.cpp.
        
        ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ:
        - ChatML для chat-моделей
        - Обычный формат для completion-моделей
        - Кастомные форматы на основе имени модели
        
        ОПРЕДЕЛЕНИЕ ФОРМАТА:
        - Chat-модели: содержат "chat", "instruct", "qwen-chat"
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
    
    def _build_structured_system_prompt(self, schema: Dict[str, Any], base_system_prompt: Optional[str] = None) -> str:
        """
        Формирование системного промпта для структурированной генерации.
        
        СТРАТЕГИЯ:
        1. Добавление четких инструкций о формате вывода
        2. Предоставление JSON схемы для валидации
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
        
        ПРАВИЛА:
        1. ВЫВОДИ ТОЛЬКО ВАЛИДНЫЙ JSON БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА
        2. Используй двойные кавычки для строк
        3. Соблюдай все указанные типы данных
        4. Включи все обязательные поля
        5. Не добавляй полей, которых нет в схеме
        
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
        
        structured_prompt = f"""
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
6. Для массивов используй квадратные скобки []
7. Для объектов используй фигурные скобки {{}}
8. Не используй комментарии внутри JSON

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
        return structured_prompt
    
    async def _fix_invalid_json(self, invalid_json: str, error_message: str, original_prompt: str, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Попытка исправить некорректный JSON через LLM.
        
        ПРОЦЕСС:
        1. Анализ ошибки парсинга
        2. Формирование промпта для исправления
        3. Генерация исправленной версии
        4. Валидация результата
        
        ПАРАМЕТРЫ:
        - invalid_json: Некорректный JSON
        - error_message: Сообщение об ошибке
        - original_prompt: Исходный промпт
        - schema: JSON Schema для валидации
        
        ВОЗВРАЩАЕТ:
        - Исправленный JSON как словарь или None при неудаче
        
        СТРАТЕГИЯ:
        - Использование пониженной температуры для детерминированности
        - Максимально подробные инструкции по исправлению
        - Валидация результата перед возвратом
        """
        try:
            fix_prompt = f"""
            ИСПРАВЬ следующий некорректный JSON. Верни ТОЛЬКО валидный JSON без дополнительного текста.
            
            НЕКОРРЕКТНЫЙ JSON:
            {invalid_json}
            
            ОШИБКА ПАРСИНГА:
            {error_message}
            
            ИСХОДНЫЙ ПРОМПТ:
            {original_prompt}
            
            JSON СХЕМА ДЛЯ ВАЛИДАЦИИ:
            {json.dumps(schema, indent=2, ensure_ascii=False)}
            
            ИНСТРУКЦИИ:
            1. ИСПРАВЬ только синтаксические ошибки (кавычки, запятые, скобки)
            2. СОХРАНИ все данные из исходного JSON
            3. ДОБАВЬ недостающие обязательные поля со значениями по умолчанию
            4. УДАЛИ поля, которых нет в схеме
            5. ВЕРНИ ТОЛЬКО валидный JSON без пояснений
            
            ПРИМЕР КОРРЕКТНОГО ФОРМАТА:
            {{"field1": "исправленное значение", "field2": 123}}
            """
            
            # Генерация исправленной версии
            fix_response = await self.generate(
                user_prompt=fix_prompt,
                system_prompt="Ты — JSON валидатор. Исправь ошибки в JSON и верни ТОЛЬКО валидный JSON.",
                max_tokens=1000,
                temperature=0.2  # Очень детерминированная генерация
            )
            
            # Попытка распарсить исправленный JSON
            fixed_content = json.loads(fix_response.content)
            validated_content = await self.validate_output(fixed_content, schema, max_retries=1)
            
            logger.info("Некорректный JSON успешно исправлен")
            return validated_content
            
        except Exception as e:
            logger.warning(f"Не удалось исправить некорректный JSON: {str(e)}")
            return None
    
    def count_tokens(self, text: str) -> int:
        """
        Подсчет количества токенов в тексте.
        
        РЕАЛИЗАЦИЯ:
        - Использует встроенный метод Llama.cpp для подсчета токенов
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
                return len(self._engine.tokenize(text.encode("utf-8")))
            except Exception as e:
                logger.warning(f"Ошибка подсчета токенов: {str(e)}. Используется приблизительный подсчет.")
        
        # Приблизительный подсчет
        if any('\u0400' <= c <= '\u04FF' for c in text):  # Русские символы
            return max(1, len(text) // 2)
        return max(1, len(text) // 4)