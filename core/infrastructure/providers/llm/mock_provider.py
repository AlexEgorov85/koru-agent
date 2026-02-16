"""
Mock LLM Provider для тестирования без реального LLM.
"""
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.models.types.llm_types import LLMRequest, LLMResponse
from core.models.enums.common_enums import ExecutionStatus


logger = logging.getLogger(__name__)


class MockLLMConfig(BaseModel):
    """Конфигурация для mock LLM провайдера."""
    model_name: str = Field(default="mock-model", description="Имя модели (для mock-провайдера)")
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=512, description="Максимальное количество токенов")
    verbose: bool = Field(default=True, description="Подробный вывод")


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM провайдер для тестирования."""

    def __init__(self, config: MockLLMConfig, model_name: str = None):
        # Вызываем родительский конструктор с базовыми параметрами
        model_name = model_name or getattr(config, 'model_name', 'mock-model')
        super().__init__(model_name=model_name, config=config.model_dump())
        self.config = config
        self.initialized = False
        logger.info(f"Создан MockLLMProvider для модели: {model_name}")

    async def initialize(self) -> bool:
        """Инициализация провайдера."""
        try:
            logger.info(f"Mock LLM провайдер инициализирован для модели: {self.model_name}")
            self.initialized = True
            self.is_initialized = True
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации MockLLMProvider: {str(e)}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Проверка работоспособности провайдера."""
        return {
            "status": "healthy",
            "model": self.model_name,
            "is_initialized": self.is_initialized
        }

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Выполнить запрос к LLM (заглушка)."""
        if not self.initialized:
            await self.initialize()

        logger.debug(f"Mock выполнение запроса: {request.prompt[:50]}...")

        # Создаем mock-ответ в зависимости от типа запроса
        user_prompt = request.prompt.lower()

        if "какие книги" in user_prompt or "автор" in user_prompt or "написал" in user_prompt:
            # Ответ на вопросы о книгах
            mock_response = {
                "choices": [{
                    "text": '{"action_type": "execute_capability", "capability_name": "book_library.get_books_by_author", "parameters": {"author_name": "Александр Пушкин"}, "reasoning": "Поиск книг конкретного автора"}'
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60}
            }
        elif "финальный" in user_prompt or "итоговый" in user_prompt or "заключение" in user_prompt:
            # Ответ для генерации финального ответа
            mock_response = {
                "choices": [{
                    "text": '{"final_answer": "Александр Пушкин написал такие книги: \'Евгений Онегин\', \'Капитанская дочка\', \'Руслан и Людмила\', \'Борис Годунов\'.", "confidence": 0.95, "sources": ["book_library.get_books_by_author"]}'
                }],
                "usage": {"prompt_tokens": 15, "completion_tokens": 80, "total_tokens": 95}
            }
        else:
            # Общий ответ
            mock_response = {
                "choices": [{
                    "text": '{"action_type": "continue", "next_step": "Продолжить выполнение задачи", "confidence": 0.8}'
                }],
                "usage": {"prompt_tokens": 8, "completion_tokens": 30, "total_tokens": 38}
            }

        return LLMResponse(
            text=mock_response["choices"][0]["text"],
            tokens_used=mock_response["usage"]["total_tokens"],
            generation_time=0.01,
            model_name=self.model_name,
            finish_reason="stop"
        )

    async def shutdown(self):
        """Завершение работы провайдера."""
        logger.info("Mock LLM провайдер завершает работу")
        self.initialized = False
        self.is_initialized = False

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Генерация текста (совместимость с базовым интерфейсом)."""
        return await self.execute(request)

    async def generate_structured(self, request: LLMRequest) -> Dict[str, Any]:
        """Генерация структурированных данных."""
        response = await self.execute(request)
        # Возвращаем структурированные данные
        return {"raw_response": response.text, "tokens_used": response.tokens_used}


# Alias для совместимости с фабрикой
MockProvider = MockLLMProvider