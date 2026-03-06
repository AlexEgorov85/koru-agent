"""
Юнит-тесты для ResourcePreloader.

ЗАПУСК:
```bash
pytest tests/unit/preloading/test_resource_preloader.py -v
```
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from core.application.preloading.resource_preloader import ResourcePreloader


class MockDataRepository:
    """Mock DataRepository для тестов."""
    
    def __init__(self, prompts=None, contracts=None):
        self._prompts = prompts or {}
        self._contracts = contracts or {}
        self._get_prompt_calls = []
        self._get_contract_calls = []
    
    @property
    def prompts(self):
        return self._prompts
    
    @property
    def contracts(self):
        return self._contracts
    
    async def get_prompt(self, capability: str, version: str):
        self._get_prompt_calls.append((capability, version))
        return self._prompts.get((capability, version))
    
    async def get_contract(self, capability: str, direction: str, version: str):
        self._get_contract_calls.append((capability, direction, version))
        return self._contracts.get((capability, direction, version))


class MockConfig:
    """Mock AppConfig для тестов."""
    
    def __init__(
        self,
        prompt_versions=None,
        input_contract_versions=None,
        output_contract_versions=None
    ):
        self.prompt_versions = prompt_versions or {}
        self.input_contract_versions = input_contract_versions or {}
        self.output_contract_versions = output_contract_versions or {}


class TestResourcePreloader:
    """Тесты ResourcePreloader."""
    
    @pytest.fixture
    def mock_repository(self):
        """Создать mock DataRepository."""
        return MockDataRepository()
    
    @pytest.fixture
    def mock_event_bus(self):
        """Создать mock EventBus."""
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus
    
    @pytest.fixture
    def preloader(self, mock_repository, mock_event_bus):
        """Создать ResourcePreloader."""
        return ResourcePreloader(mock_repository, mock_event_bus)
    
    @pytest.mark.asyncio
    async def test_preload_all(self, preloader, mock_repository, mock_event_bus):
        """Тест: предзагрузка всех ресурсов."""
        # Setup
        mock_repository._prompts = {
            ("cap1", "v1"): "Prompt 1",
            ("cap2", "v1"): "Prompt 2"
        }
        mock_repository._contracts = {
            ("cap1", "input", "v1"): {"type": "object"},
            ("cap1", "output", "v1"): {"type": "object"}
        }
        
        config = MockConfig()
        
        # Execute
        prompts, contracts = await preloader.preload_all(config)
        
        # Assert
        assert len(prompts) == 2
        assert len(contracts) == 2
    
    @pytest.mark.asyncio
    async def test_preload_for_component(self, preloader, mock_repository):
        """Тест: предзагрузка для компонента."""
        # Setup
        mock_repository._prompts = {
            ("search", "v1"): "Search prompt"
        }
        mock_repository._contracts = {
            ("search", "input", "v1"): {"query": "string"},
            ("search", "output", "v1"): {"results": "array"}
        }
        
        config = MockConfig(
            prompt_versions={"search": "v1"},
            input_contract_versions={"search": "v1"},
            output_contract_versions={"search": "v1"}
        )
        
        # Execute
        resources = await preloader.preload_for_component(
            "skill", "search_skill", config
        )
        
        # Assert
        assert "prompts" in resources
        assert "input_contracts" in resources
        assert "output_contracts" in resources
        assert "search" in resources["prompts"]
    
    @pytest.mark.asyncio
    async def test_preload_all_empty_repository(self, preloader):
        """Тест: предзагрузка из пустого репозитория."""
        config = MockConfig()
        
        prompts, contracts = await preloader.preload_all(config)
        
        assert prompts == {}
        assert contracts == {}
    
    @pytest.mark.asyncio
    async def test_load_prompt(self, preloader, mock_repository):
        """Тест: загрузка промпта."""
        # Setup
        mock_repository._prompts = {("test_cap", "v1"): "Test prompt"}
        
        # Execute
        prompt = await preloader._load_prompt("test_cap", "v1")
        
        # Assert
        assert prompt == "Test prompt"
        assert len(mock_repository._get_prompt_calls) == 1
    
    @pytest.mark.asyncio
    async def test_load_contract(self, preloader, mock_repository):
        """Тест: загрузка контракта."""
        # Setup
        mock_repository._contracts = {
            ("test_cap", "input", "v1"): {"type": "object"}
        }
        
        # Execute
        contract = await preloader._load_contract("test_cap", "input", "v1")
        
        # Assert
        assert contract == {"type": "object"}
        assert len(mock_repository._get_contract_calls) == 1
    
    @pytest.mark.asyncio
    async def test_get_prompt_versions_for_component(self, preloader):
        """Тест: получение версий промптов."""
        config = MockConfig(prompt_versions={"cap1": "v1", "cap2": "v2"})
        
        versions = preloader._get_prompt_versions_for_component(
            "skill", "test_skill", config
        )
        
        assert versions == {"cap1": "v1", "cap2": "v2"}
    
    @pytest.mark.asyncio
    async def test_get_input_contract_versions(self, preloader):
        """Тест: получение версий input контрактов."""
        config = MockConfig(input_contract_versions={"cap1": "v1"})
        
        versions = preloader._get_input_contract_versions_for_component(
            "skill", "test_skill", config
        )
        
        assert versions == {"cap1": "v1"}
    
    @pytest.mark.asyncio
    async def test_get_output_contract_versions(self, preloader):
        """Тест: получение версий output контрактов."""
        config = MockConfig(output_contract_versions={"cap1": "v1"})
        
        versions = preloader._get_output_contract_versions_for_component(
            "skill", "test_skill", config
        )
        
        assert versions == {"cap1": "v1"}
    
    @pytest.mark.asyncio
    async def test_preload_component_prompts(self, preloader, mock_repository):
        """Тест: предзагрузка промптов компонента."""
        # Setup
        mock_repository._prompts = {
            ("search", "v1"): "Search prompt"
        }
        
        config = MockConfig(prompt_versions={"search": "v1"})
        
        # Execute
        prompts = await preloader._preload_component_prompts(
            "skill", "search_skill", config
        )
        
        # Assert
        assert len(prompts) == 1
        assert "search" in prompts
    
    @pytest.mark.asyncio
    async def test_preload_component_contracts(self, preloader, mock_repository):
        """Тест: предзагрузка контрактов компонента."""
        # Setup
        mock_repository._contracts = {
            ("search", "input", "v1"): {"query": "string"},
            ("search", "output", "v1"): {"results": "array"}
        }
        
        config = MockConfig(
            input_contract_versions={"search": "v1"},
            output_contract_versions={"search": "v1"}
        )
        
        # Execute
        contracts = await preloader._preload_component_contracts(
            "skill", "search_skill", config
        )
        
        # Assert
        assert "input" in contracts
        assert "output" in contracts
        assert "search" in contracts["input"]
        assert "search" in contracts["output"]
    
    @pytest.mark.asyncio
    async def test_repr(self, preloader):
        """Тест: строковое представление."""
        repr_str = repr(preloader)
        
        assert "ResourcePreloader" in repr_str
        assert "connected" in repr_str
    
    @pytest.mark.asyncio
    async def test_preload_with_no_repository(self, mock_event_bus):
        """Тест: предзагрузка без репозитория."""
        preloader = ResourcePreloader(None, mock_event_bus)
        config = MockConfig()
        
        prompts, contracts = await preloader.preload_all(config)
        
        assert prompts == {}
        assert contracts == {}
    
    @pytest.mark.asyncio
    async def test_load_prompt_no_repository(self, mock_event_bus):
        """Тест: загрузка промпта без репозитория."""
        preloader = ResourcePreloader(None, mock_event_bus)
        
        prompt = await preloader._load_prompt("cap", "v1")
        
        assert prompt is None
    
    @pytest.mark.asyncio
    async def test_load_contract_no_repository(self, mock_event_bus):
        """Тест: загрузка контракта без репозитория."""
        preloader = ResourcePreloader(None, mock_event_bus)
        
        contract = await preloader._load_contract("cap", "input", "v1")
        
        assert contract is None


class TestResourcePreloaderEdgeCases:
    """Тесты граничных случаев ResourcePreloader."""
    
    @pytest.fixture
    def mock_repository(self):
        return MockDataRepository()
    
    @pytest.fixture
    def mock_event_bus(self):
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus
    
    @pytest.mark.asyncio
    async def test_empty_versions(self, mock_repository, mock_event_bus):
        """Тест: пустые версии в конфиге."""
        preloader = ResourcePreloader(mock_repository, mock_event_bus)
        config = MockConfig()  # Пустые версии
        
        prompts = await preloader._preload_component_prompts(
            "skill", "test", config
        )
        
        assert prompts == {}
    
    @pytest.mark.asyncio
    async def test_nonexistent_prompt(self, mock_repository, mock_event_bus):
        """Тест: несуществующий промпт."""
        preloader = ResourcePreloader(mock_repository, mock_event_bus)
        config = MockConfig(prompt_versions={"nonexistent": "v1"})
        
        prompts = await preloader._preload_component_prompts(
            "skill", "test", config
        )
        
        assert prompts == {}
    
    @pytest.mark.asyncio
    async def test_partial_contracts(self, mock_repository, mock_event_bus):
        """Тест: только input контракты."""
        mock_repository._contracts = {
            ("cap", "input", "v1"): {"type": "object"}
        }
        
        preloader = ResourcePreloader(mock_repository, mock_event_bus)
        config = MockConfig(
            input_contract_versions={"cap": "v1"},
            output_contract_versions={"cap": "v1"}  # Нет в репозитории
        )
        
        contracts = await preloader._preload_component_contracts(
            "skill", "test", config
        )
        
        assert "cap" in contracts["input"]
        assert "cap" not in contracts["output"]
