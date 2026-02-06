"""
Централизованный мок для LLM-провайдеров
"""
from typing import Dict, Any, Optional, List
from domain.value_objects.provider_type import LLMRequest, LLMResponse, LLMHealthStatus
from infrastructure.gateways.llm_providers.base_provider import BaseLLMProvider


class TestLLMProvider(BaseLLMProvider):
    """
    Централизованный мок для LLM-провайдеров
    - Поддерживает детерминированные ответы
    - Поддерживает сценарные ответы
    - Поддерживает симуляцию ошибок/таймаутов
    """
    
    def __init__(self, model_name: str = "test-model", config: Optional[Dict[str, Any]] = None):
        super().__init__(model_name, config or {})
        self.responses_map: Dict[str, str] = {}
        self.error_scenarios: Dict[str, Exception] = {}
        self.response_history: List[LLMRequest] = []
        self._is_initialized = True
        self.health_status = LLMHealthStatus.HEALTHY
    
    def add_response(self, prompt_key: str, response: str):
        """
        Добавить детерминированный ответ для определенного ключа промта
        """
        self.responses_map[prompt_key] = response
    
    def add_response_by_content(self, prompt_content: str, response: str):
        """
        Добавить детерминированный ответ для определенного содержимого промта
        """
        self.responses_map[prompt_content] = response
    
    def add_error_scenario(self, prompt_key: str, error: Exception):
        """
        Добавить сценарий ошибки для определенного ключа промта
        """
        self.error_scenarios[prompt_key] = error
    
    def add_error_by_content(self, prompt_content: str, error: Exception):
        """
        Добавить сценарий ошибки для определенного содержимого промта
        """
        self.error_scenarios[prompt_content] = error
    
    async def initialize(self) -> bool:
        """
        Инициализация провайдера
        """
        self._is_initialized = True
        self.health_status = LLMHealthStatus.HEALTHY
        return True
    
    async def shutdown(self) -> None:
        """
        Завершение работы провайдера
        """
        self._is_initialized = False
        self.health_status = LLMHealthStatus.UNKNOWN
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация текста с использованием мок-данных
        """
        if not self._is_initialized:
            raise RuntimeError("Provider not initialized")
        
        # Сохраняем запрос в историю
        self.response_history.append(request)
        self.request_count += 1
        
        # Проверяем наличие сценария ошибки
        if request.prompt in self.error_scenarios:
            error = self.error_scenarios[request.prompt]
            self.error_count += 1
            raise error
        
        # Формируем ключ для поиска ответа
        prompt_key = request.prompt
        if request.system_prompt:
            prompt_key = f"{request.system_prompt}::{request.prompt}"
        
        # Ищем ответ по ключу
        response_text = self.responses_map.get(prompt_key)
        if response_text is None:
            # Если не нашли по составному ключу, ищем просто по промту
            response_text = self.responses_map.get(request.prompt)
        
        # Если ответ не найден, возвращаем стандартный ответ
        if response_text is None:
            response_text = f"Test response for: {request.prompt[:50]}..."
        
        # Создаем ответ
        response = LLMResponse(
            raw_text=response_text,
            model=self.model_name,
            tokens_used=len(response_text.split()),
            generation_time=0.1,  # Симуляция времени генерации
            finish_reason="stop",
            metadata=request.metadata or {}
        )
        
        # Если в запросе была указана ожидаемая схема ответа, пытаемся сгенерировать структурированный ответ
        if request.expected_response_schema:
            # Для тестовых целей создаем простой структурированный ответ на основе схемы
            structured_response = self._generate_structured_response(request.expected_response_schema)
            response.parsed = structured_response
        
        return response
    
    def _generate_structured_response(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерация структурированного ответа на основе схемы
        """
        result = {}
        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                prop_type = prop_schema.get("type", "string")
                if prop_type == "string":
                    result[prop_name] = f"test_{prop_name}_value"
                elif prop_type == "integer":
                    result[prop_name] = 42
                elif prop_type == "number":
                    result[prop_name] = 3.14
                elif prop_type == "boolean":
                    result[prop_name] = True
                elif prop_type == "array":
                    result[prop_name] = []
                elif prop_type == "object":
                    result[prop_name] = {}
                else:
                    result[prop_name] = f"test_{prop_name}_value"
        return result
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности
        """
        return {
            "status": self.health_status.value,
            "model": self.model_name,
            "initialized": self._is_initialized,
            "request_count": self.request_count,
            "error_count": self.error_count
        }