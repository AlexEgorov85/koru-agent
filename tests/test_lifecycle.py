"""
Тесты для системы управления жизненным циклом компонентов.

Проверяет:
- ComponentState enum
- LifecycleMixin
- Интеграцию в BaseComponent
- Проверки готовности в AgentRuntime
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.agent.components.lifecycle import ComponentState, LifecycleMixin
from core.agent.components.base_component import BaseComponent


class TestComponentState:
    """Тесты для enum состояний."""
    
    def test_component_state_values(self):
        """Проверка значений enum."""
        assert ComponentState.CREATED.value == "created"
        assert ComponentState.INITIALIZING.value == "initializing"
        assert ComponentState.READY.value == "ready"
        assert ComponentState.FAILED.value == "failed"
        assert ComponentState.SHUTDOWN.value == "shutdown"


class TestLifecycleMixin:
    """Тесты для LifecycleMixin."""
    
    @pytest.fixture
    def component(self):
        """Создание тестового компонента."""
        return LifecycleMixin("test_component")
    
    def test_initial_state(self, component):
        """Проверка начального состояния."""
        assert component.state == ComponentState.CREATED
        assert not component.is_ready
        assert not component.is_initialized
        assert not component.is_failed
    
    def test_ensure_ready_before_init(self, component):
        """Проверка ошибки при вызове ensure_ready до инициализации."""
        with pytest.raises(RuntimeError) as exc_info:
            component.ensure_ready()
        
        assert "not ready" in str(exc_info.value).lower()
        assert "test_component" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_transition_to_ready(self, component):
        """Проверка перехода в состояние READY."""
        await component._transition_to(ComponentState.READY)
        
        assert component.state == ComponentState.READY
        assert component.is_ready
        assert component.is_initialized
    
    @pytest.mark.asyncio
    async def test_transition_to_failed(self, component):
        """Проверка перехода в состояние FAILED."""
        await component._transition_to(ComponentState.FAILED)
        
        assert component.state == ComponentState.FAILED
        assert component.is_failed
        assert not component.is_ready
    
    @pytest.mark.asyncio
    async def test_transition_to_shutdown(self, component):
        """Проверка перехода в состояние SHUTDOWN."""
        await component._transition_to(ComponentState.SHUTDOWN)
        
        assert component.state == ComponentState.SHUTDOWN
        assert component.is_initialized
        assert not component.is_ready
    
    def test_name_property(self, component):
        """Проверка имени компонента."""
        assert component.name == "test_component"
    
    def test_repr(self, component):
        """Проверка строкового представления."""
        repr_str = repr(component)
        assert "LifecycleMixin" in repr_str
        assert "test_component" in repr_str
        assert "created" in repr_str


class MockApplicationContext:
    """Мокированный ApplicationContext для тестов."""
    
    def __init__(self):
        self.infrastructure_context = MagicMock()
        self.infrastructure_context.event_bus = None


class TestBaseComponentLifecycle:
    """Тесты для интеграции LifecycleMixin в BaseComponent."""
    
    @pytest.fixture
    def mock_context(self):
        """Создание мокированного контекста."""
        return MockApplicationContext()
    
    @pytest.fixture
    def mock_config(self):
        """Создание мокированной конфигурации."""
        config = MagicMock()
        config.variant_id = "test_variant"
        config.prompt_versions = {}
        config.input_contract_versions = {}
        config.output_contract_versions = {}
        config.critical_resources = {'prompts': False}
        return config
    
    @pytest.fixture
    def mock_executor(self):
        """Создание мокированного executor."""
        return MagicMock()
    
    @pytest.fixture
    def component(self, mock_context, mock_config, mock_executor):
        """Создание тестового компонента."""
        class TestComponent(BaseComponent):
            def _get_component_type(self):
                return "test"
        
        return TestComponent(
            name="test_component",
            application_context=mock_context,
            component_config=mock_config,
            executor=mock_executor
        )
    
    def test_initial_state(self, component):
        """Проверка начального состояния BaseComponent."""
        assert component.state == ComponentState.CREATED
        assert not component.is_ready
    
    def test_ensure_ready_before_init(self, component):
        """Проверка ошибки при использовании до инициализации."""
        with pytest.raises(RuntimeError):
            component.ensure_ready()
    
    @pytest.mark.asyncio
    async def test_state_after_successful_init(self, component):
        """Проверка состояния после успешной инициализации."""
        # Мокируем методы валидации
        with patch.object(component, '_validate_manifest', return_value=True):
            with patch.object(component, '_preload_resources', return_value=True):
                with patch.object(component, '_validate_loaded_resources', return_value=True):
                    result = await component.initialize()
                    
                    assert result is True
                    assert component.state == ComponentState.READY
                    assert component.is_ready
    
    @pytest.mark.asyncio
    async def test_state_after_failed_init(self, component):
        """Проверка состояния после ошибки инициализации."""
        # Мокируем ошибку валидации
        with patch.object(component, '_validate_manifest', return_value=False):
            result = await component.initialize()
            
            assert result is False
            assert component.state == ComponentState.FAILED
            assert component.is_failed
    
    @pytest.mark.asyncio
    async def test_reinit_when_already_ready(self, component):
        """Проверка повторной инициализации."""
        # Сначала успешно инициализируем
        with patch.object(component, '_validate_manifest', return_value=True):
            with patch.object(component, '_preload_resources', return_value=True):
                with patch.object(component, '_validate_loaded_resources', return_value=True):
                    await component.initialize()
                    assert component.state == ComponentState.READY
        
        # Повторная инициализация должна вернуть True без изменений
        with patch.object(component, '_validate_manifest', return_value=True):
            result = await component.initialize()
            assert result is True
            assert component.state == ComponentState.READY  # Состояние не изменилось


class TestAgentRuntimeChecks:
    """Тесты для проверок готовности в AgentRuntime."""
    
    def test_runtime_requires_ready_context(self):
        """Проверка что AgentRuntime требует готовый контекст."""
        from core.agent.runtime import AgentRuntime
        
        # Создаём мокированный неготовый контекст
        mock_context = MagicMock()
        mock_context.is_ready = False
        mock_context.infrastructure_context = MagicMock()
        mock_context.infrastructure_context.is_ready = True
        
        with pytest.raises(RuntimeError) as exc_info:
            AgentRuntime(
                application_context=mock_context,
                goal="Test goal"
            )
        
        assert "not initialized" in str(exc_info.value).lower()
    
    def test_runtime_requires_ready_infra_context(self):
        """Проверка что AgentRuntime требует готовый инфраструктурный контекст."""
        from core.agent.runtime import AgentRuntime
        
        # Создаём мокированный готовый app контекст
        mock_context = MagicMock()
        mock_context.is_ready = True
        mock_context.infrastructure_context = MagicMock()
        mock_context.infrastructure_context.is_ready = False
        
        with pytest.raises(RuntimeError) as exc_info:
            AgentRuntime(
                application_context=mock_context,
                goal="Test goal"
            )
        
        assert "not initialized" in str(exc_info.value).lower()
    
    def test_runtime_with_ready_contexts(self):
        """Проверка создания AgentRuntime с готовыми контекстами."""
        from core.agent.runtime import AgentRuntime
        
        # Создаём мокированные готовые контексты
        mock_context = MagicMock()
        mock_context.is_ready = True
        mock_context.session_context = None  # Будет создан автоматически
        mock_context.infrastructure_context = MagicMock()
        mock_context.infrastructure_context.is_ready = True
        mock_context.infrastructure_context.id = "test_id"
        mock_context.infrastructure_context.config = MagicMock()
        mock_context.infrastructure_context.config.data_dir = "data"
        
        # Должно работать без ошибок
        agent = AgentRuntime(
            application_context=mock_context,
            goal="Test goal"
        )
        
        assert agent is not None
        assert agent.goal == "Test goal"


class TestBehaviorManagerChecks:
    """Тесты для проверок в BehaviorManager."""
    
    @pytest.mark.asyncio
    async def test_generate_decision_requires_init(self):
        """Проверка что generate_next_decision требует инициализации."""
        from core.agent.components.behavior_manager import BehaviorManager
        from core.models.data.capability import Capability
        
        # Создаём мокированный контекст
        mock_context = MagicMock()
        
        manager = BehaviorManager(application_context=mock_context)
        
        # Попытка генерации решения до инициализации
        with pytest.raises(RuntimeError) as exc_info:
            await manager.generate_next_decision(
                session_context=MagicMock(),
                available_capabilities=[]
            )
        
        assert "not initialized" in str(exc_info.value).lower()


class TestErrorHandlerDecorator:
    """Тесты для декоратора handle_errors."""
    
    def test_sync_function_raises_typeerror(self):
        """Проверка что синхронные функции выбрасывают TypeError."""
        from core.errors.error_handler import ErrorHandler, get_error_handler
        
        error_handler = get_error_handler()
        
        def sync_func():
            return "result"
        
        with pytest.raises(TypeError) as exc_info:
            error_handler.handle_errors(component="test")(sync_func)
        
        assert "must be async" in str(exc_info.value).lower()
        assert "sync" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_async_function_works(self):
        """Проверка что асинхронные функции работают."""
        from core.errors.error_handler import ErrorHandler, get_error_handler
        
        error_handler = get_error_handler()
        
        @error_handler.handle_errors(component="test", reraise=False)
        async def async_func():
            return "result"
        
        result = await async_func()
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_async_function_with_error(self):
        """Проверка обработки ошибок в асинхронных функциях."""
        from core.errors.error_handler import ErrorHandler, get_error_handler
        
        error_handler = get_error_handler()
        error_handler.reset_stats()
        
        @error_handler.handle_errors(component="test", reraise=False)
        async def async_func_with_error():
            raise ValueError("Test error")
        
        result = await async_func_with_error()
        assert result is None
        
        # Проверка статистики
        stats = error_handler.get_stats()
        assert stats["total_errors"] >= 1