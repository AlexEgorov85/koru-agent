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
from core.infrastructure.event_bus.unified_event_bus import EventType
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
    strict_mode: bool = Field(default=False, description="Если True, выбрасывать ошибку при отсутствии зарегистрированного ответа")


class MockLLMProvider(BaseLLMProvider):
    """
    Mock LLM провайдер для тестирования.

    Поддерживает регистрацию ответов для конкретных промптов и ведение истории вызовов.
    
    КАК ИСПОЛЬЗОВАТЬ:
    
    1. Базовое использование:
        mock_llm = MockLLMProvider()
        mock_llm.register_response("привет", "Привет! Как дела?")
        response = await mock_llm.generate(LLMRequest(prompt="привет"))
    
    2. Строгий режим (ошибка если ответ не найден):
        config = MockLLMConfig(strict_mode=True)
        mock_llm = MockLLMProvider(config=config)
    
    3. Ответ по умолчанию для всех незаregistered запросов:
        config = MockLLMConfig(default_response="Стандартный ответ")
        mock_llm = MockLLMProvider(config=config)
    
    4. Regex паттерны для гибкого匹配:
        mock_llm.register_regex_response(r"\\d+", "Вы ввели число")
    
    5. Проверка истории вызовов:
        history = mock_llm.get_call_history()
        assert len(history) == 1
    """

    def __init__(self, config: MockLLMConfig = None, model_name: str = None):
        config = config or MockLLMConfig()
        model_name = model_name or getattr(config, 'model_name', 'mock-model')
        super().__init__(model_name=model_name, config=config.model_dump())
        self.config = config
        self.initialized = False

        self._prompt_responses: Dict[Union[str, Pattern], str] = {}
        self._default_response = config.default_response
        self._strict_mode = config.strict_mode
        self._call_history: List[Dict[str, Any]] = []

    def register_response(self, prompt_pattern: str, response: str, use_exact_match: bool = False):
        """
        Регистрация ответа для конкретного паттерна промпта.
        
        ARGS:
        - prompt_pattern: Строка или паттерн для поиска в промпте
        - response: Ответ который вернуть при совпадении
        - use_exact_match: Если True, точное совпадение (по умолчанию substring поиск)
        
        EXAMPLES:
        >>> mock_llm.register_response("привет", "Привет! Как дела?")
        >>> mock_llm.register_response("как дела", "Отлично!", use_exact_match=True)
        """
        if use_exact_match:
            self._prompt_responses[f"exact:{prompt_pattern}"] = response
        else:
            # Для обычного substring поиска добавляем маркер чтобы отличать от regex
            self._prompt_responses[f"substring:{prompt_pattern}"] = response
        self.log.debug("Зарегистрирован ответ для паттерна: %s...",
                       prompt_pattern[:50],
                       extra={"event_type": EventType.DEBUG})

    def register_exact_response(self, prompt: str, response: str):
        """Регистрация ответа для точного совпадения промпта."""
        return self.register_response(prompt, response, use_exact_match=True)
    
    def register_responses_batch(self, responses: Dict[str, str]):
        """
        Массовая регистрация ответов.
        
        ARGS:
        - responses: Словарь {паттерн: ответ}
        
        EXAMPLE:
        >>> mock_llm.register_responses_batch({
        ...     "привет": "Привет!",
        ...     "пока": "До свидания!",
        ...     r"\\d+": "Число найдено"
        ... })
        """
        for pattern, response in responses.items():
            self.register_response(pattern, response)
        self.log.info("Зарегистрировано %d ответов批量", len(responses),
                     extra={"event_type": EventType.DEBUG})

    def register_regex_response(self, pattern: str, response: str):
        """Регистрация ответа для regex-паттерна."""
        compiled_pattern = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        self._prompt_responses[compiled_pattern] = response
        self.log.debug("Зарегистрирован regex-ответ для паттерна: %s",
                       pattern,
                       extra={"event_type": EventType.DEBUG})

    def set_default_response(self, response: str):
        """Установка ответа по умолчанию."""
        self._default_response = response
        self.log.debug("Установлен ответ по умолчанию: %s...",
                       response[:50],
                       extra={"event_type": EventType.DEBUG})

    def get_call_history(self) -> List[Dict[str, Any]]:
        """Получение истории вызовов для тестов."""
        return self._call_history.copy()

    def clear_history(self):
        """Очистка истории вызовов."""
        self._call_history.clear()
        self.log.debug("История вызовов очищена",
                       extra={"event_type": EventType.DEBUG})

    def get_last_call(self) -> Optional[Dict[str, Any]]:
        """Получение последнего вызова."""
        return self._call_history[-1] if self._call_history else None

    def assert_called_with(self, prompt_contains: str):
        """Проверка что LLM был вызван с промптом содержащим указанную строку."""
        for call in self._call_history:
            if prompt_contains in call.get('prompt', ''):
                return
        raise AssertionError(
            f"Mock LLM не был вызван с промптом содержащим '{prompt_contains}'. "
            f"История вызовов: {[c.get('prompt', '')[:50] for c in self._call_history]}"
        )

    def assert_call_count(self, expected_count: int):
        """Проверка количества вызовов LLM."""
        actual_count = len(self._call_history)
        if actual_count != expected_count:
            raise AssertionError(
                f"Ожидалось {expected_count} вызовов LLM, но было {actual_count}. "
                f"История: {[c.get('prompt', '')[:30] for c in self._call_history]}"
            )

    async def initialize(self) -> bool:
        """Инициализация провайдера."""
        try:
            self.log.info("Mock LLM провайдер инициализирован для модели: %s",
                          self.model_name,
                          extra={"event_type": EventType.SYSTEM_INIT})
            self.initialized = True
            self.is_initialized = True
            self._set_healthy_status()
            return True
        except Exception as e:
            self.log.error("Ошибка инициализации MockLLMProvider: %s", str(e),
                           extra={"event_type": EventType.LLM_ERROR})
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
        """Реализация генерации для Mock провайдера."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        self.log.debug("=== ПРОМПТ LLM (ПОЛНЫЙ, RAW) ===\n%s\n=== КОНЕЦ ПРОМПТА ===", request.prompt,
                      extra={"event_type": EventType.DEBUG})

        self.log.debug("Mock выполнение запроса: %s",
                       request.prompt,
                       extra={"event_type": EventType.LLM_CALL})

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
        response = None
        matched_pattern = None

        # Сначала проверяем точные совпадения
        for pattern, resp in self._prompt_responses.items():
            if isinstance(pattern, str) and pattern.startswith("exact:"):
                exact_prompt = pattern[6:]  # Убираем префикс "exact:"
                if exact_prompt == request.prompt:
                    response = resp
                    matched_pattern = f"exact:{exact_prompt}"
                    break
        
        # Если не найдено точное совпадение, ищем по substring или regex
        if response is None:
            for pattern, resp in self._prompt_responses.items():
                if isinstance(pattern, Pattern):
                    if pattern.search(request.prompt):
                        response = resp
                        matched_pattern = pattern.pattern
                        break
                elif isinstance(pattern, str) and pattern.startswith("substring:"):
                    search_text = pattern[10:]  # Убираем префикс "substring:"
                    if search_text in request.prompt:
                        response = resp
                        matched_pattern = f"substring:{search_text}"
                        break

        if response is None:
            if self._strict_mode:
                from core.errors.exceptions import MockProviderError
                raise MockProviderError(
                    f"Не зарегистрирован ответ для промпта: {request.prompt[:200]}. "
                    f"Зарегистрируйте ответ через register_response() или register_regex_response().",
                    prompt=request.prompt
                )
            else:
                # В не-strict режиме используем ответ по умолчанию
                response = self._default_response
                matched_pattern = "default"

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

        self.log.debug("=== СЫРОЙ ОТВЕТ LLM (RAW) ===\n%s\n=== КОНЕЦ СЫРОГО ОТВЕТА ===", response,
                      extra={"event_type": EventType.DEBUG})

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
        self.log.info("Mock LLM провайдер завершает работу",
                      extra={"event_type": EventType.SYSTEM_SHUTDOWN})
        self.initialized = False
        self.is_initialized = False

    async def _generate_structured_impl(self, request: LLMRequest) -> LLMResponse:
        """Генерация структурированных данных для тестирования."""
        from core.infrastructure.providers.llm.llama_cpp_provider import StructuredOutputError
        import json

        if not request.structured_output:
            raise ValueError("structured_output не указан в запросе")

        config: StructuredOutputConfig = request.structured_output
        schema_def = config.schema_def

        start_time = time.time()

        schema_prompt = f"\n\nExpected JSON schema: {json.dumps(schema_def, indent=2)}"
        enhanced_request = LLMRequest(
            prompt=request.prompt + schema_prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            structured_output=request.structured_output
        )

        validation_errors = []

        for attempt in range(1, config.max_retries + 1):
            try:
                raw_response = await self.generate(enhanced_request)
                parsed_data = json.loads(raw_response.content)

                temp_model = self._create_pydantic_from_schema(
                    config.output_model,
                    schema_def
                )

                parsed_content = temp_model.model_validate(parsed_data)

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

                self.log.warning("Mock: Попытка %d/%d не удалась: %s",
                                 attempt, config.max_retries, e,
                                 extra={"event_type": EventType.WARNING})

        raise StructuredOutputError(
            message="Mock: Не удалось получить валидный структурированный ответ",
            model_name=self.model_name,
            attempts=config.max_retries,
            validation_errors=validation_errors
        )

    def _create_pydantic_from_schema(self, model_name: str, schema_def: Dict[str, Any]) -> type[BaseModel]:
        """Создаёт Pydantic модель из JSON Schema."""
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
                field_type, field_info = build_field(field_schema)
                fields[field_name] = (Optional[field_type], field_info)

        return create_model(model_name, **fields)


# Alias для совместимости с фабрикой
MockProvider = MockLLMProvider
