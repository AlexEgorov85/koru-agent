"""
Тесты для Component Discovery.

TESTS:
- test_discovery_creation: Создание обнаружителя
- test_discover_components: Обнаружение компонентов
- test_get_component: Получение компонента
- test_get_by_type: Фильтрация по типу
- test_validate_dependencies: Валидация зависимостей
- test_component_info: Информация о компоненте
- test_stats: Статистика обнаружения
"""
import asyncio
import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from core.components import (
    ComponentDiscovery,
    ComponentInfo,
    ComponentStatus,
    ComponentNotFoundError,
    ComponentLoadError,
    get_component_discovery,
    create_component_discovery,
    reset_component_discovery,
)
from core.models.enums.common_enums import ComponentType


@pytest.fixture
def temp_manifests_dir():
    """Фикстура: временная директория с манифестами."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Создание тестового манифеста skill
        skill_manifest = {
            "component": {
                "id": "test_skill",
                "name": "Test Skill",
                "type": "skill",
                "version": "1.0.0",
                "status": "active"
            },
            "dependencies": ["dependency1", "dependency2"],
            "capabilities": ["capability1", "capability2"],
            "metadata": {"author": "test"},
            "config": {"param1": "value1"}
        }
        
        skill_dir = tmpdir / "skills" / "test_skill"
        skill_dir.mkdir(parents=True)
        
        with open(skill_dir / "manifest.yaml", 'w') as f:
            yaml.dump(skill_manifest, f)
        
        # Создание тестового манифеста tool
        tool_manifest = {
            "component": {
                "id": "test_tool",
                "name": "Test Tool",
                "type": "tool",
                "version": "2.0.0",
                "status": "active"
            },
            "dependencies": [],
            "capabilities": ["tool_capability"],
        }
        
        tool_dir = tmpdir / "tools" / "test_tool"
        tool_dir.mkdir(parents=True)
        
        with open(tool_dir / "manifest.yaml", 'w') as f:
            yaml.dump(tool_manifest, f)
        
        # Создание тестового манифеста service
        service_manifest = {
            "component": {
                "id": "test_service",
                "name": "Test Service",
                "type": "service",
                "version": "1.5.0",
                "status": "experimental"
            },
            "requires": ["dep1"],
            "provides": ["svc_cap"],
        }
        
        service_dir = tmpdir / "services" / "test_service"
        service_dir.mkdir(parents=True)
        
        with open(service_dir / "manifest.yaml", 'w') as f:
            yaml.dump(service_manifest, f)
        
        yield tmpdir


@pytest.fixture
def component_discovery(temp_manifests_dir):
    """Фикстура: обнаружитель компонентов."""
    reset_component_discovery()
    
    discovery = ComponentDiscovery(
        search_paths=[temp_manifests_dir]
    )
    
    yield discovery
    
    reset_component_discovery()


class TestComponentDiscoveryCreation:
    """Тесты создания обнаружителя."""

    def test_create_component_discovery(self, temp_manifests_dir):
        """Создание обнаружителя компонентов."""
        discovery = ComponentDiscovery(
            search_paths=[temp_manifests_dir]
        )
        
        assert discovery is not None
        assert len(discovery._search_paths) == 1
        assert discovery._manifest_filename == "manifest.yaml"

    def test_get_component_discovery_singleton(self):
        """get_component_discovery возвращает singleton."""
        reset_component_discovery()
        
        discovery1 = get_component_discovery()
        discovery2 = get_component_discovery()
        
        assert discovery1 is discovery2

    def test_reset_component_discovery(self):
        """Сброс singleton."""
        reset_component_discovery()
        discovery1 = get_component_discovery()
        
        reset_component_discovery()
        discovery2 = get_component_discovery()
        
        assert discovery1 is not discovery2


class TestDiscoverComponents:
    """Тесты обнаружения компонентов."""

    @pytest.mark.asyncio
    async def test_discover_components(self, component_discovery):
        """Обнаружение компонентов."""
        components = await component_discovery.discover()
        
        assert len(components) == 3
        assert "test_skill" in components
        assert "test_tool" in components
        assert "test_service" in components

    @pytest.mark.asyncio
    async def test_discover_with_nonexistent_path(self):
        """Обнаружение с несуществующим путем."""
        discovery = ComponentDiscovery(
            search_paths=[Path("/nonexistent/path")]
        )
        
        components = await discovery.discover()
        
        assert len(components) == 0

    @pytest.mark.asyncio
    async def test_refresh_components(self, component_discovery):
        """Пересканирование компонентов."""
        await component_discovery.discover()
        
        # Добавление нового манифеста
        new_manifest = {
            "component": {
                "id": "new_component",
                "name": "New Component",
                "type": "skill",
                "version": "1.0.0",
            }
        }
        
        new_dir = Path(component_discovery._search_paths[0]) / "skills" / "new_component"
        new_dir.mkdir(parents=True)
        
        with open(new_dir / "manifest.yaml", 'w') as f:
            yaml.dump(new_manifest, f)
        
        # Пересканирование
        await component_discovery.refresh()
        
        components = component_discovery.get_all_components()
        assert "new_component" in components


class TestGetComponent:
    """Тесты получения компонентов."""

    @pytest.mark.asyncio
    async def test_get_component(self, component_discovery):
        """Получение компонента по ID."""
        await component_discovery.discover()
        
        component = component_discovery.get_component("test_skill")
        
        assert component is not None
        assert component.id == "test_skill"
        assert component.name == "Test Skill"
        assert component.component_type == ComponentType.SKILL

    @pytest.mark.asyncio
    async def test_get_nonexistent_component(self, component_discovery):
        """Получение несуществующего компонента."""
        await component_discovery.discover()
        
        component = component_discovery.get_component("nonexistent")
        
        assert component is None

    @pytest.mark.asyncio
    async def test_has_component(self, component_discovery):
        """Проверка наличия компонента."""
        await component_discovery.discover()
        
        assert component_discovery.has_component("test_skill") is True
        assert component_discovery.has_component("nonexistent") is False


class TestGetByType:
    """Тесты фильтрации по типу."""

    @pytest.mark.asyncio
    async def test_get_by_type(self, component_discovery):
        """Получение компонентов по типу."""
        await component_discovery.discover()
        
        skills = component_discovery.get_by_type(ComponentType.SKILL)
        tools = component_discovery.get_by_type(ComponentType.TOOL)
        services = component_discovery.get_by_type(ComponentType.SERVICE)
        
        assert len(skills) == 1
        assert skills[0].id == "test_skill"
        
        assert len(tools) == 1
        assert tools[0].id == "test_tool"
        
        assert len(services) == 1
        assert services[0].id == "test_service"

    @pytest.mark.asyncio
    async def test_get_by_status(self, component_discovery):
        """Получение компонентов по статусу."""
        await component_discovery.discover()
        
        active = component_discovery.get_by_status(ComponentStatus.ACTIVE)
        experimental = component_discovery.get_by_status(ComponentStatus.EXPERIMENTAL)
        
        assert len(active) == 2  # test_skill и test_tool
        assert len(experimental) == 1  # test_service


class TestComponentInfo:
    """Тесты ComponentInfo."""

    def test_component_info_from_manifest(self, temp_manifests_dir):
        """Создание ComponentInfo из манифеста."""
        manifest_path = temp_manifests_dir / "skills" / "test_skill" / "manifest.yaml"
        
        with open(manifest_path, 'r') as f:
            manifest_data = yaml.safe_load(f)
        
        component_info = ComponentInfo.from_manifest(manifest_path, manifest_data)
        
        assert component_info.id == "test_skill"
        assert component_info.name == "Test Skill"
        assert component_info.component_type == ComponentType.SKILL
        assert component_info.version == "1.0.0"
        assert component_info.status == ComponentStatus.ACTIVE
        assert "dependency1" in component_info.dependencies
        assert "capability1" in component_info.capabilities

    def test_component_info_to_dict(self, component_discovery):
        """Конвертация ComponentInfo в dict."""
        info = ComponentInfo(
            id="test",
            name="Test",
            component_type=ComponentType.SKILL,
            version="1.0.0",
        )
        
        data = info.to_dict()
        
        assert data["id"] == "test"
        assert data["component_type"] == "skill"
        assert "discovered_at" in data

    def test_component_info_default_values(self):
        """Значения по умолчанию."""
        manifest_data = {
            "component": {
                "id": "minimal",
                "name": "Minimal Component",
            }
        }
        
        info = ComponentInfo.from_manifest(Path("test.yaml"), manifest_data)
        
        assert info.version == "1.0.0"
        assert info.status == ComponentStatus.ACTIVE
        assert info.component_type == ComponentType.SKILL


class TestValidateDependencies:
    """Тесты валидации зависимостей."""

    @pytest.mark.asyncio
    async def test_validate_dependencies_missing(self, component_discovery):
        """Валидация с отсутствующими зависимостями."""
        await component_discovery.discover()
        
        missing = component_discovery.validate_dependencies("test_skill")
        
        assert "dependency1" in missing
        assert "dependency2" in missing

    @pytest.mark.asyncio
    async def test_validate_dependencies_ok(self, component_discovery):
        """Валидация с существующими зависимостями."""
        await component_discovery.discover()
        
        # Tool не имеет зависимостей
        missing = component_discovery.validate_dependencies("test_tool")
        
        assert len(missing) == 0


class TestComponentStats:
    """Тесты статистики."""

    @pytest.mark.asyncio
    async def test_get_discovery_stats(self, component_discovery):
        """Получение статистики обнаружения."""
        await component_discovery.discover()
        
        stats = component_discovery.get_discovery_stats()
        
        assert stats["total_components"] == 3
        assert stats["by_type"]["skill"] == 1
        assert stats["by_type"]["tool"] == 1
        assert stats["by_type"]["service"] == 1
        assert stats["by_status"]["active"] == 2
        assert stats["by_status"]["experimental"] == 1


class TestComponentClassRegistration:
    """Тесты регистрации классов компонентов."""

    @pytest.mark.asyncio
    async def test_register_component_class(self, component_discovery):
        """Регистрация класса компонента."""
        class MockComponent:
            pass
        
        component_discovery.register_component_class("test_component", MockComponent)
        
        assert component_discovery.has_component_class("test_component")

    @pytest.mark.asyncio
    async def test_load_component(self, component_discovery, temp_manifests_dir):
        """Загрузка компонента."""
        class MockComponent:
            def __init__(self, **kwargs):
                pass
        
        # Добавляем компонент в обнаружитель
        component_discovery._components["mock"] = ComponentInfo(
            id="mock",
            name="Mock",
            component_type=ComponentType.SKILL,
        )
        
        component_discovery.register_component_class("mock", MockComponent)
        
        component = await component_discovery.load_component("mock")
        
        assert component is not None
        assert isinstance(component, MockComponent)

    @pytest.mark.asyncio
    async def test_load_nonexistent_component(self, component_discovery):
        """Загрузка несуществующего компонента."""
        with pytest.raises(ComponentNotFoundError):
            await component_discovery.load_component("nonexistent")


class TestSingleton:
    """Тесты singleton паттерна."""

    def test_create_component_discovery_singleton(self, temp_manifests_dir):
        """create_component_discovery создает singleton."""
        reset_component_discovery()
        
        discovery1 = create_component_discovery(search_paths=[temp_manifests_dir])
        discovery2 = get_component_discovery()
        
        assert discovery1 is discovery2

    def test_reset_component_discovery(self, temp_manifests_dir):
        """Сброс singleton."""
        reset_component_discovery()
        discovery1 = create_component_discovery(search_paths=[temp_manifests_dir])
        
        reset_component_discovery()
        
        with pytest.raises(AssertionError):
            assert discovery1 is get_component_discovery()
