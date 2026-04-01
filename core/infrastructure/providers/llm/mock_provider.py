"""
Mock LLM Provider для тестирования без реального LLM.

Поддерживает:
- Регистрацию ответов для конкретных промптов
- Историю вызовов для тестирования
- Детерминированные ответы
- Переключение между mock и real LLM
"""
import time
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Pattern, Union
from pydantic import BaseModel, Field
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.models.types.llm_types import (
    LLMRequest,
    LLMResponse,
    RawLLMResponse,
    StructuredOutputConfig
)
from pydantic import BaseModel, ValidationError, create_model, Field
from core.models.enums.common_enums import ExecutionStatus


class MockLLMConfig(BaseModel):
    """Конфигурация для mock LLM провайдера."""
    model_name: str = Field(default="mock-model", description="Имя модели (для mock-провайдера)")
    temperature: float = Field(default=0.0, description="Температура генерации (0.0 для детерминизма)")
    max_tokens: int = Field(default=1000, description="Максимальное количество токенов")
    verbose: bool = Field(default=False, description="Подробный вывод")
    default_response: str = Field(default='{"status": "ok"}', description="Ответ по умолчанию")


class MockLLMProvider(BaseLLMProvider):
    """
    Mock LLM провайдер для тестирования.
    
    Поддерживает регистрацию ответов для конкретных промптов и ведение истории вызовов.
    """

    def __init__(self, config: MockLLMConfig = None, model_name: str = None):
        # Вызываем родительский конструктор с базовыми параметрами
        config = config or MockLLMConfig()
        model_name = model_name or getattr(config, 'model_name', 'mock-model')
        super().__init__(model_name=model_name, config=config.model_dump())
        self.config = config
        self.initialized = False

        # Маппинг паттернов → ответы
        self._prompt_responses: Dict[Union[str, Pattern], str] = {}
        self._default_response = config.default_response
        self._call_history: List[Dict[str, Any]] = []

        # event_bus_logger инициализируется в BaseProvider.initialize()
    
    def register_response(self, prompt_pattern: str, response: str):
        """
        Регистрация ответа для конкретного паттерна промпта.
        
        Args:
            prompt_pattern: Строка или regex-паттерн для поиска в промпте
            response: Ответ, который будет возвращен при совпадении
        """
        self._prompt_responses[prompt_pattern] = response
        self.event_bus_logger.debug(f"Зарегистрирован ответ для паттерна: {prompt_pattern[:50]}...")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    
    def register_regex_response(self, pattern: str, response: str):
        """
        Регистрация ответа для regex-паттерна.
        
        Args:
            pattern: Regex-паттерн для поиска в промпте
            response: Ответ, который будет возвращен при совпадении
        """
        compiled_pattern = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        self._prompt_responses[compiled_pattern] = response
        self.event_bus_logger.debug(f"Зарегистрирован regex-ответ для паттерна: {pattern}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    
    def set_default_response(self, response: str):
        """
        Установка ответа по умолчанию для неизвестных промптов.
        
        Args:
            response: Ответ по умолчанию
        """
        self._default_response = response
        self.event_bus_logger.debug(f"Установлен ответ по умолчанию: {response[:50]}...")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    
    def get_call_history(self) -> List[Dict[str, Any]]:
        """
        Получение истории вызовов для тестов.
        
        Returns:
            Копия истории вызовов
        """
        return self._call_history.copy()
    
    def clear_history(self):
        """Очистка истории вызовов."""
        self._call_history.clear()
        self.event_bus_logger.debug("История вызовов очищена")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    
    def get_last_call(self) -> Optional[Dict[str, Any]]:
        """
        Получение последнего вызова.
        
        Returns:
            Последний вызов или None если история пуста
        """
        return self._call_history[-1] if self._call_history else None
    
    def assert_called_with(self, prompt_contains: str):
        """
        Проверка что LLM был вызван с промптом содержащим указанную строку.
        
        Args:
            prompt_contains: Строка которая должна содержаться в промпте
            
        Raises:
            AssertionError: Если вызов не найден
        """
        for call in self._call_history:
            if prompt_contains in call.get('prompt', ''):
                return
        raise AssertionError(
            f"Mock LLM не был вызван с промптом содержащим '{prompt_contains}'. "
            f"История вызовов: {[c.get('prompt', '')[:50] for c in self._call_history]}"
        )
    
    def assert_call_count(self, expected_count: int):
        """
        Проверка количества вызовов LLM.
        
        Args:
            expected_count: Ожидаемое количество вызовов
            
        Raises:
            AssertionError: Если количество вызовов не совпадает
        """
        actual_count = len(self._call_history)
        if actual_count != expected_count:
            raise AssertionError(
                f"Ожидалось {expected_count} вызовов LLM, но было {actual_count}. "
                f"История: {[c.get('prompt', '')[:30] for c in self._call_history]}"
            )

    async def initialize(self) -> bool:
        """Инициализация провайдера."""
        try:
            self.event_bus_logger.info(f"Mock LLM провайдер инициализирован для модели: {self.model_name}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self.initialized = True
            self.is_initialized = True
            self._set_healthy_status()
            return True
        except Exception as e:
            self.event_bus_logger.error(f"Ошибка инициализации MockLLMProvider: {str(e)}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Проверка работоспособности провайдера."""
        return {
            "status": "healthy",
            "model": self.model_name,
            "is_initialized": self.is_initialized,
            "call_count": len(self._call_history),
            "registered_patterns": len(self._prompt_responses)
        }

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Реализация генерации для Mock провайдера.
        
        Логирование выполняется в базовом классе BaseLLMProvider.
        """
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        # Логирование вызова
        self.event_bus_logger.debug(f"Mock выполнение запроса: {request.prompt[:100]}...")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Публикация события LLM_CALL_STARTED
        if hasattr(self, '_event_bus') and self._event_bus:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            await self._event_bus.publish(
                EventType.LLM_CALL_STARTED,
                data={
                    "agent_id": getattr(self, '_agent_id', 'mock'),
                    "session_id": getattr(self, '_session_id', 'mock'),
                    "component": getattr(self, '_component', 'mock_llm'),
                    "phase": getattr(self, '_phase', 'mock'),
                    "goal": getattr(self, '_goal', 'mock'),
                    "provider": "MockLLMProvider",
                    "model": self.model_name,
                    "prompt_length": len(request.prompt),
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                    "is_mock": True
                },
                source="mock_llm_provider"
            )

        # Поиск подходящего ответа
        # ❌ УДАЛЕНО: default_response для неизвестных промптов
        # ✅ ТЕПЕРЬ: Выбрасываем MockProviderError если паттерн не найден
        response = None
        matched_pattern = None

        for pattern, resp in self._prompt_responses.items():
            if isinstance(pattern, Pattern):
                # Regex паттерн
                if pattern.search(request.prompt):
                    response = resp
                    matched_pattern = pattern.pattern
                    break
            else:
                # Строковый паттерн
                if pattern in request.prompt:
                    response = resp
                    matched_pattern = pattern
                    break

        # Если ответ не найден - выбрасываем ошибку
        if response is None:
            from core.errors.exceptions import MockProviderError
            raise MockProviderError(
                f"Не зарегистрирован ответ для промпта: {request.prompt[:200]}. "
                f"Зарегистрируйте ответ через register_response() или register_regex_response().",
                prompt=request.prompt
            )

        # Логирование в историю
        self._call_history.append({
            'prompt': request.prompt,
            'prompt_truncated': request.prompt[:200],
            'response': response,
            'response_truncated': response[:200],
            'matched_pattern': matched_pattern,
            'timestamp': datetime.now().isoformat(),
            'temperature': request.temperature,
            'max_tokens': request.max_tokens
        })
        
        generation_time = time.time() - start_time

        # Публикация события LLM_CALL_COMPLETED
        if hasattr(self, '_event_bus') and self._event_bus:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            await self._event_bus.publish(
                EventType.LLM_CALL_COMPLETED,
                data={
                    "agent_id": getattr(self, '_agent_id', 'mock'),
                    "session_id": getattr(self, '_session_id', 'mock'),
                    "component": getattr(self, '_component', 'mock_llm'),
                    "phase": getattr(self, '_phase', 'mock'),
                    "provider": "MockLLMProvider",
                    "model": self.model_name,
                    "response_length": len(response),
                    "tokens_used": len(response.split()),
                    "generation_time": generation_time,
                    "is_mock": True
                },
                source="mock_llm_provider"
            )

        return LLMResponse(
            content=response,
            model=self.model_name,
            tokens_used=len(response.split()),
            generation_time=generation_time,
            finish_reason="stop",
            metadata={
                'matched_pattern': matched_pattern,
                'is_mock': True
            }
        )

    async def shutdown(self):
        """Завершение работы провайдера."""
        self.event_bus_logger.info("Mock LLM провайдер завершает работу")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        self.initialized = False
        self.is_initialized = False

    async def _generate_structured_impl(
        self,
        request: LLMRequest
    ) -> LLMResponse:
        """
        Генерация структурированных данных для тестирования.

        Логирование выполняется в базовом классе BaseLLMProvider.

        Поддерживает:
        - Регистрацию ответов для конкретных схем
        - Автоматическую валидацию
        - Историю вызовов
        - Retry логику при ошибках

        ARGS:
        - request: Запрос с configuration структурированного вывода

        RETURNS:
        - LLMResponse: Типизированный ответ

        RAISES:
        - StructuredOutputError: если не удалось получить валидный ответ
        """
        from core.infrastructure.providers.llm.llama_cpp_provider import StructuredOutputError
        import json
        
        if not request.structured_output:
            raise ValueError("structured_output не указан в запросе")
        
        config: StructuredOutputConfig = request.structured_output
        schema_def = config.schema_def
        
        start_time = time.time()
        
        # Если есть output_schema, добавляем его в промпт
        schema_prompt = f"\n\nExpected JSON schema: {json.dumps(schema_def, indent=2)}"
        enhanced_request = LLMRequest(
            prompt=request.prompt + schema_prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            structured_output=request.structured_output
        )
        
        validation_errors = []
        
        # Retry цикл
        for attempt in range(1, config.max_retries + 1):
            try:
                # Получаем ответ через generate (наследуется из BaseLLMProvider)
                raw_response = await self.generate(enhanced_request)
                
                # Пытаемся распарсить JSON ответ
                parsed_data = json.loads(raw_response.content)
                
                # Создаём Pydantic модель из схемы
                temp_model = self._create_pydantic_from_schema(
                    config.output_model,
                    schema_def
                )
                
                # Валидируем
                parsed_content = temp_model.model_validate(parsed_data)
                
                # Успех!
                return LLMResponse(
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
                    validation_errors=[]
                )
                
            except (json.JSONDecodeError, ValidationError) as e:
                error_info = {
                    "attempt": attempt,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "response_snippet": raw_response.content[:200] if 'raw_response' in locals() else "N/A"
                }
                validation_errors.append(error_info)
                
                self.event_bus_logger.warning(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Mock: Попытка {attempt}/{config.max_retries} не удалась: {e}"
                )
        
        # Все попытки исчерпаны
        # correlation_id больше не передаётся — он генерируется в базовом классе
        raise StructuredOutputError(
            message="Mock: Не удалось получить валидный структурированный ответ",
            model_name=self.model_name,
            attempts=config.max_retries,
            validation_errors=validation_errors
        )
    
    def _create_pydantic_from_schema(
        self, 
        model_name: str, 
        schema_def: Dict[str, Any]
    ) -> type[BaseModel]:
        """
        Создаёт Pydantic модель из JSON Schema.
        
        ARGS:
        - model_name: Имя создаваемой модели
        - schema_def: JSON Schema словарь
        
        RETURNS:
        - type[BaseModel]: Класс Pydantic модели
        """
        from typing import List, Optional, Any
        
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


# Alias для совместимости с фабрикой
MockProvider = MockLLMProvider