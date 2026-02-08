"""
BaseLLMProvider - базовая абстракция для LLM-провайдеров.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from domain.value_objects.provider_type import LLMHealthStatus, LLMRequest, LLMResponse



class BaseLLMProvider(ABC):
    """
    Базовая абстракция для LLM-провайдеров.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (шлюз)
    - Ответственность: предоставление интерфейса для работы с LLM
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    def __init__(self, model_name: str, config: Dict[str, Any]):
        """
        Инициализация провайдера.
        
        Args:
            model_name: Название модели
            config: Конфигурация провайдера
        """
        self.model_name = model_name
        self.config = config
        self.health_status = LLMHealthStatus.UNKNOWN
        self.request_count = 0
        self.error_count = 0
        self.avg_response_time = 0.0
        self._is_initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Инициализация провайдера.
        
        Returns:
            bool: Успешность инициализации
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """
        Завершение работы провайдера.
        """
        pass
    
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация текста.
        
        Args:
            request: Запрос к LLM
            
        Returns:
            LLMResponse: Ответ от LLM
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности.
        
        Returns:
            Dict[str, Any]: Статус работоспособности
        """
        pass
    
    async def generate_structured(self, request: LLMRequest, output_schema: Dict[str, Any]) -> LLMResponse:
        """
        Генерация структурированных данных в формате JSON.
        
        Args:
            request: Запрос к LLM
            output_schema: Схема вывода в формате JSON Schema
            
        Returns:
            LLMResponse: Ответ от LLM
        """
        # По умолчанию реализация делегируется обычной генерации
        response = await self.generate(request)
        
        # Проверяем, является ли ответ валидным JSON
        import json
        try:
            json_content = json.loads(response.raw_text)
            # Проверяем соответствие схеме
            validated_content = await self.validate_output(json_content, output_schema)
            # Обновляем parsed данные в ответе
            response.parsed = validated_content
        except json.JSONDecodeError:
            # Если не удалось распознать JSON, сохраняем информацию об ошибке
            response.validation_error = f"Failed to parse JSON from response: {response.raw_text}"
        except Exception as e:
            # Если ошибка валидации, сохраняем информацию об ошибке
            response.validation_error = f"Schema validation error: {str(e)}"
        
        return response
    
    async def validate_output(self, content: Dict[str, Any], schema: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        """
        Валидация выходных данных по JSON Schema.
        
        Args:
            content: Содержимое для валидации
            schema: Схема валидации в формате JSON Schema
            max_retries: Максимальное количество попыток исправления
            
        Returns:
            Dict[str, Any]: Валидное содержимое
        """
        if max_retries <= 0:
            return content
        
        # Валидация с использованием jsonschema
        try:
            from jsonschema import validate, ValidationError
            
            validate(instance=content, schema=schema)
            return content
        except ImportError:
            # Если jsonschema не установлен, возвращаем без валидации
            return content
        except ValidationError as e:
            # Пытаемся исправить ошибку
            fixed_content = await self._fix_validation_error(content, schema, e, max_retries - 1)
            return fixed_content
    
    async def _fix_validation_error(self, content: Dict[str, Any], schema: Dict[str, Any], 
                                   error: Exception, max_retries: int) -> Dict[str, Any]:
        """
        Исправление ошибки валидации.
        
        Args:
            content: Содержимое с ошибкой
            schema: Схема валидации
            error: Ошибка валидации
            max_retries: Оставшееся количество попыток
            
        Returns:
            Dict[str, Any]: Исправленное содержимое
        """
        # По умолчанию возвращаем оригинальное содержимое
        # Реальная реализация будет зависеть от конкретного провайдера
        return content
    
    def _update_metrics(self, generation_time: float, success: bool = True):
        """
        Обновление метрик работы.
        
        Args:
            generation_time: Время генерации
            success: Успешность операции
        """
        self.request_count += 1
        if not success:
            self.error_count += 1
        
        # Обновляем среднее время ответа
        total_time = self.avg_response_time * (self.request_count - 1)
        total_time += generation_time
        self.avg_response_time = total_time / self.request_count