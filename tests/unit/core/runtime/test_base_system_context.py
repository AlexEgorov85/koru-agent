"""
Тесты для базового класса системного контекста (BaseSystemContext).
"""
import pytest
from unittest.mock import MagicMock
from core.session_context.session_context import SessionContext
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from core.system_context.resource_registry import ResourceInfo
from models.resource import ResourceType
from models.llm_types import LLMResponse


class ConcreteSystemContext(BaseSystemContext):
    """Конкретная реализация BaseSystemContext для тестов."""
    
    async def initialize(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    async def _register_providers_from_config(self) -> None:
        pass

    def _get_resources_by_type(self, resource_type: ResourceType) -> dict:
        return {}

    def get_resource(self, name: str):
        return None

    def get_capability(self, name: str) -> Capability:
        return None

    def list_capabilities(self) -> list:
        return []

    async def call_llm(self, prompt: str) -> str:
        return "test response"

    async def create_agent(self, **kwargs):
        pass

    async def create_agent_for_question(self, question: str, **kwargs):
        pass

    async def execute_sql_query(self, query: str, params: dict = None, db_provider_name: str = "default_db"):
        pass

    async def call_llm_with_params(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        llm_provider_name: str = "default_llm",
        output_format: str = None,
        output_schema: dict = None,
        **kwargs
    ) -> LLMResponse:
        return LLMResponse(content="test", model="test_model", tokens_used=10, generation_time=0.1)

    async def run_capability(
        self, 
        capability_name: str, 
        parameters: dict,
        session_context: 'SessionContext' = None
    ):
        pass
    
    async def _select_strategy_for_question(self, question: str) -> str:
        return "default"


class TestBaseSystemContext:
    """Тесты для BaseSystemContext."""
    
    def test_initialization(self):
        """Тест инициализации системного контекста."""
        system_context = ConcreteSystemContext()
        
        # Проверяем, что объект создан без ошибок
        assert system_context is not None
    
    @pytest.mark.asyncio
    async def test_initialize_method(self):
        """Тест метода инициализации."""
        system_context = ConcreteSystemContext()
        
        result = await system_context.initialize()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_shutdown_method(self):
        """Тест метода завершения работы."""
        system_context = ConcreteSystemContext()
        
        # Просто проверяем, что метод не вызывает исключений
        await system_context.shutdown()
    
    def test_get_resources_by_type(self):
        """Тест метода получения ресурсов по типу."""
        system_context = ConcreteSystemContext()
        
        resources = system_context._get_resources_by_type(ResourceType.LLM_PROVIDER)
        
        assert resources == {}
    
    def test_get_resource(self):
        """Тест метода получения ресурса."""
        system_context = ConcreteSystemContext()
        
        resource = system_context.get_resource("nonexistent_resource")
        
        assert resource is None
    
    def test_get_capability(self):
        """Тест метода получения capability."""
        system_context = ConcreteSystemContext()
        
        capability = system_context.get_capability("nonexistent_capability")
        
        assert capability is None
    
    def test_list_capabilities(self):
        """Тест метода получения списка capability."""
        system_context = ConcreteSystemContext()
        
        capabilities = system_context.list_capabilities()
        
        assert capabilities == []
    
    @pytest.mark.asyncio
    async def test_call_llm(self):
        """Тест метода вызова LLM."""
        system_context = ConcreteSystemContext()
        
        response = await system_context.call_llm("test prompt")
        
        assert response == "test response"
    
    @pytest.mark.asyncio
    async def test_create_agent(self):
        """Тест метода создания агента."""
        system_context = ConcreteSystemContext()
        
        # Просто проверяем, что метод не вызывает исключений
        await system_context.create_agent(test_param="value")
    
    @pytest.mark.asyncio
    async def test_create_agent_for_question(self):
        """Тест метода создания агента для вопроса."""
        system_context = ConcreteSystemContext()
        
        # Просто проверяем, что метод не вызывает исключений
        await system_context.create_agent_for_question("test question")
    
    @pytest.mark.asyncio
    async def test_execute_sql_query(self):
        """Тест метода выполнения SQL-запроса."""
        system_context = ConcreteSystemContext()
        
        # Просто проверяем, что метод не вызывает исключений
        await system_context.execute_sql_query("SELECT 1")
    
    @pytest.mark.asyncio
    async def test_call_llm_with_params(self):
        """Тест метода вызова LLM с параметрами."""
        system_context = ConcreteSystemContext()
        
        response = await system_context.call_llm_with_params("test prompt")
        
        assert isinstance(response, LLMResponse)
        assert response.content == "test"
    
    @pytest.mark.asyncio
    async def test_run_capability(self):
        """Тест метода выполнения capability."""
        system_context = ConcreteSystemContext()
        
        # Просто проверяем, что метод не вызывает исключений
        await system_context.run_capability("test_capability", {"param": "value"})
    
    @pytest.mark.asyncio
    async def test_select_strategy_for_question(self):
        """Тест метода выбора стратегии для вопроса."""
        system_context = ConcreteSystemContext()
        
        strategy = await system_context._select_strategy_for_question("test question")
        
        assert strategy == "default"


def test_base_system_context_abstract_methods():
    """Тест, что BaseSystemContext нельзя инстанцировать без реализации абстрактных методов."""
    
    with pytest.raises(TypeError):
        BaseSystemContext()