"""
Mock LLM Provider для тестирования без реального LLM.

Поддерживает:
- Регистрацию ответов для конкретных промптов
- Историю вызовов для тестирования
- Детерминированные ответы
- Переключение между mock и real LLM
"""
import logging
import time
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Pattern, Union
from pydantic import BaseModel, Field
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.models.types.llm_types import LLMRequest, LLMResponse
from core.models.enums.common_enums import ExecutionStatus


logger = logging.getLogger(__name__)


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
        
        logger.info(f"Создан MockLLMProvider для модели: {model_name}")
    
    def register_response(self, prompt_pattern: str, response: str):
        """
        Регистрация ответа для конкретного паттерна промпта.
        
        Args:
            prompt_pattern: Строка или regex-паттерн для поиска в промпте
            response: Ответ, который будет возвращен при совпадении
        """
        self._prompt_responses[prompt_pattern] = response
        logger.debug(f"Зарегистрирован ответ для паттерна: {prompt_pattern[:50]}...")
    
    def register_regex_response(self, pattern: str, response: str):
        """
        Регистрация ответа для regex-паттерна.
        
        Args:
            pattern: Regex-паттерн для поиска в промпте
            response: Ответ, который будет возвращен при совпадении
        """
        compiled_pattern = re.compile(pattern, re.IGNORECASE | re.DOTALL)
        self._prompt_responses[compiled_pattern] = response
        logger.debug(f"Зарегистрирован regex-ответ для паттерна: {pattern}")
    
    def set_default_response(self, response: str):
        """
        Установка ответа по умолчанию для неизвестных промптов.
        
        Args:
            response: Ответ по умолчанию
        """
        self._default_response = response
        logger.debug(f"Установлен ответ по умолчанию: {response[:50]}...")
    
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
        logger.debug("История вызовов очищена")
    
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
            logger.info(f"Mock LLM провайдер инициализирован для модели: {self.model_name}")
            self.initialized = True
            self.is_initialized = True
            self._set_healthy_status()
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации MockLLMProvider: {str(e)}")
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

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """
        Выполнить запрос к LLM.
        
        Ищет подходящий ответ среди зарегистрированных паттернов.
        """
        if not self.initialized:
            await self.initialize()

        start_time = time.time()
        
        # Логирование вызова
        logger.debug(f"Mock выполнение запроса: {request.prompt[:100]}...")

        # Поиск подходящего ответа
        response = self._default_response
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
        logger.info("Mock LLM провайдер завершает работу")
        self.initialized = False
        self.is_initialized = False

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Генерация текста (совместимость с базовым интерфейсом)."""
        return await self.execute(request)

    async def generate_structured(self, request: LLMRequest, output_schema: Dict = None, system_prompt: str = None) -> Dict[str, Any]:
        """
        Генерация структурированных данных.
        
        Args:
            request: Запрос к LLM
            output_schema: JSON схема для валидации (опционально)
            system_prompt: Системный промпт (опционально)
            
        Returns:
            Словарь с распарсенными данными
        """
        # Если есть output_schema, добавляем его в промпт
        if output_schema:
            schema_prompt = f"\n\nExpected JSON schema: {output_schema}"
            if isinstance(request, LLMRequest):
                request = LLMRequest(
                    prompt=request.prompt + schema_prompt,
                    system_prompt=system_prompt or request.system_prompt,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens
                )
        
        response = await self.execute(request)
        
        # Пытаемся распарсить JSON ответ
        try:
            import json
            parsed = json.loads(response.content)
            return {
                "parsed": parsed,
                "raw_response": response.content,
                "tokens_used": response.tokens_used,
                "is_valid": True
            }
        except (json.JSONDecodeError, AttributeError):
            return {
                "parsed": None,
                "raw_response": response.content,
                "tokens_used": response.tokens_used,
                "is_valid": False,
                "error": "Failed to parse JSON response"
            }


# Alias для совместимости с фабрикой
MockProvider = MockLLMProvider