"""
Базовый класс системного контекста (SystemContext).
"""

from typing import Any, Dict, List, Optional
from core.session_context.session_context import SessionContext
from core.system_context.resource_registry import ResourceInfo
from models.capability import Capability
from models.llm_types import LLMResponse
from models.resource import ResourceType


class BaseSystemContext:
    
    def _setup_logging(self):
        """
        Настройка логирования на основе конфигурации.
        """
        pass
    

    async def initialize(self) -> bool:
        """Инициализация системы."""
        pass
        
    async def shutdown(self) -> None:
        """
        Завершение работы системы.
        """
        pass
    
    async def _register_providers_from_config(self) -> None:
        """
        Автоматическая регистрация провайдеров из конфигурации.
        """
        pass
    
    def _get_resources_by_type(self, resource_type: ResourceType) -> Dict[str, ResourceInfo]:
        """
        Получение ресурсов заданного типа.
        """
        pass
    
    def get_resource(self, name: str) -> Optional[Any]:
        """
        Получение ресурса по имени.
        """
        pass
    
    def get_capability(self, name: str) -> Optional[Capability]:
        """
        Получение capability по имени.
        """
        pass
    
    def list_capabilities(self) -> List[str]:
        """
        Получение списка всех доступных capability.
        """
        pass
    
    async def call_llm(self, prompt: str) -> str:
        """
        Вызов LLM для генерации текста.
        """
        pass
    

    async def create_agent(self, **kwargs):
        """
        Асинхронное создание агента.
        """
        pass

    
    async def create_agent_for_question(self, question: str, **kwargs):
        """
        Создает агента, настроенного под конкретный вопрос.
        """
        pass
    
    async def execute_sql_query(self, query: str, params: dict = None, db_provider_name: str = "default_db"):
        """
        Выполняет SQL-запрос к базе данных.
        """
        pass
    
    async def call_llm_with_params(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        llm_provider_name: str = "default_llm",
        output_format: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Выполняет запрос к LLM с заданными параметрами.
        """
        pass

    async def run_skill(
        self, 
        skill_name: str, 
        capability_name: str, 
        parameters: dict,
        session_context: SessionContext = None
    ):
        """
        Выполняет конкретный навык с заданными параметрами.
        """
        pass
    
    async def _select_strategy_for_question(self, question: str) -> str:
        """
        Выбирает стратегию выполнения на основе типа вопроса.
        """
        pass