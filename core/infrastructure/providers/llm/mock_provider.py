"""
Mock LLM Provider для тестирования без реального LLM.
"""
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider, LLMRequest, LLMResponse
from models.execution import ExecutionStatus


logger = logging.getLogger(__name__)


class MockLLMConfig(BaseModel):
    """Конфигурация для mock LLM провайдера."""
    model_name: str = Field(default="mock-model", description="Имя модели (для mock-провайдера)")
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=512, description="Максимальное количество токенов")
    verbose: bool = Field(default=True, description="Подробный вывод")


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM провайдер для тестирования."""

    def __init__(self, config: MockLLMConfig, name: str = None):
        # Вызываем родительский конструктор с базовыми параметрами
        model_name = getattr(config, 'model_name', 'mock-model')
        super().__init__(config=config, model_name=model_name)
        self.config = config
        self.initialized = False
        logger.info(f"Создан MockLLMProvider для модели: {model_name}")
    
    async def health_check(self) -> bool:
        """Проверка работоспособности провайдера."""
        return True  # Mock всегда здоров

    async def initialize(self) -> bool:
        """Инициализация провайдера."""
        try:
            logger.info(f"Mock LLM провайдер инициализирован для модели: {self.config.model_name}")
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации MockLLMProvider: {str(e)}")
            return False

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Генерация ответа (заглушка)."""
        if not self.initialized:
            await self.initialize()

        logger.debug(f"Mock генерация для запроса: {request.user_prompt[:50]}...")

        # Создаем mock-ответ в зависимости от типа запроса
        user_prompt = request.user_prompt.lower()

        if "какие книги" in user_prompt or "автор" in user_prompt or "написал" in user_prompt:
            # Ответ на вопросы о книгах
            mock_response = {
                "choices": [{
                    "message": {
                        "content": '{"action_type": "execute_capability", "capability_name": "book_library.get_books_by_author", "parameters": {"author_name": "Александр Пушкин"}, "reasoning": "Поиск книг конкретного автора"}'
                    }
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60}
            }
        elif "финальный" in user_prompt or "итоговый" in user_prompt or "заключение" in user_prompt:
            # Ответ для генерации финального ответа
            mock_response = {
                "choices": [{
                    "message": {
                        "content": '{"final_answer": "Александр Пушкин написал такие книги: \'Евгений Онегин\', \'Капитанская дочка\', \'Руслан и Людмила\', \'Борис Годунов\'.", "confidence": 0.95, "sources": ["book_library.get_books_by_author"]}'
                    }
                }],
                "usage": {"prompt_tokens": 15, "completion_tokens": 80, "total_tokens": 95}
            }
        else:
            # Общий ответ
            mock_response = {
                "choices": [{
                    "message": {
                        "content": '{"action_type": "continue", "next_step": "Продолжить выполнение задачи", "confidence": 0.8}'
                    }
                }],
                "usage": {"prompt_tokens": 8, "completion_tokens": 30, "total_tokens": 38}
            }

        return LLMResponse(
            content=mock_response["choices"][0]["message"]["content"],
            model=self.config.model_name,
            tokens_used=mock_response["usage"]["total_tokens"],
            generation_time=0.01,
            finish_reason="stop",
            metadata={}
        )

    async def generate_structured(self, user_prompt: str, output_schema: Dict[str, Any], system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 512, **kwargs) -> LLMResponse:
        """Генерация структурированного ответа (заглушка)."""
        if not self.initialized:
            await self.initialize()

        logger.debug(f"Mock структурированная генерация для запроса: {user_prompt[:50]}...")
        
        # Возвращаем mock-ответ в соответствии со схемой
        mock_content = {
            "action_type": "execute_capability",
            "capability_name": "book_library.get_books_by_author",
            "parameters": {"author_name": "Александр Пушкин"},
            "reasoning": "Поиск книг конкретного автора"
        }
        
        # Если схема отличается, адаптируем ответ
        if output_schema and "final_answer" in str(output_schema):
            mock_content = {
                "final_answer": "Александр Пушкин написал такие книги: \'Евгений Онегин\', \'Капитанская дочка\', \'Руслан и Людмила\', \'Борис Годунов\'.",
                "confidence": 0.95,
                "sources": ["book_library.get_books_by_author"]
            }
        
        return LLMResponse(
            content=mock_content,  # Возвращаем структурированные данные
            model=self.config.model_name,
            tokens_used=60,
            generation_time=0.01,
            finish_reason="stop",
            metadata={}
        )

    async def shutdown(self):
        """Завершение работы провайдера."""
        logger.info("Mock LLM провайдер завершает работу")
        self.initialized = False