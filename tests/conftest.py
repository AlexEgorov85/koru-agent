"""
Helper fixtures для тестирования.

ПРИМЕЧАНИЕ: Моки допускаются только для LLM и БД провайдеров.
Для остальных компонентов используются реальные объекты или fake-классы.
"""
import os
import pytest
from pathlib import Path


# ============================================================================
# Фикстуры для Mock LLM
# ============================================================================

@pytest.fixture
def mock_llm_provider():
    """
    Mock LLM с предзаготовленными ответами.
    
    Используется для интеграционных тестов workflow.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    
    config = MockLLMConfig(
        model_name="test-mock",
        temperature=0.0,  # Детерминированные ответы
        max_tokens=1000,
        verbose=False
    )
    provider = MockLLMProvider(config=config)
    
    # Регистрируем ответы для типовых сценариев
    provider.register_response(
        "planning.create_plan",
        '{"steps": [{"action": "search_books", "parameters": {"query": "test"}}]}'
    )
    
    provider.register_response(
        "book_library.search_books",
        '{"rows": [{"title": "Test Book", "author": "Test Author"}], "rowcount": 1}'
    )
    
    provider.register_response(
        "final_answer.generate",
        '{"final_answer": "Test answer", "confidence": 0.95}'
    )

    # Регистрируем ответы для основных промптов вместо default_response
    provider.register_response("status", '{"status": "ok"}')
    provider.register_response("ping", '{"status": "ok"}')

    return provider


@pytest.fixture
def infrastructure_with_mock_llm(mock_llm_provider):
    """
    InfrastructureContext с mock LLM.
    
    Используется для интеграционных тестов с mock LLM.
    """
    from core.config.models import SystemConfig
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.models.data.resource import ResourceInfo
    from core.models.enums.common_enums import ResourceType
    from core.infrastructure_context.resource_registry import ResourceRegistry
    
    config = SystemConfig(
        llm_providers={},  # Не используем стандартную регистрацию
        db_providers={},
        data_dir='data'
    )
    
    infra = InfrastructureContext(config)
    # Создаем resource registry вручную
    infra.resource_registry = ResourceRegistry()
    infra._initialized = True
    
    # Регистрируем mock LLM
    infra.resource_registry.register_resource(
        ResourceInfo(
            name='mock_llm',
            resource_type=ResourceType.LLM,
            instance=mock_llm_provider
        )
    )
    
    return infra


@pytest.fixture
def llm_provider_type():
    """
    Определяет тип LLM для тестов из переменной окружения.
    
    Использование:
        TEST_LLM_TYPE=mock pytest tests/
        TEST_LLM_TYPE=real pytest tests/  # Для финальной валидации
    """
    return os.getenv('TEST_LLM_TYPE', 'mock')


@pytest.fixture
def llm_provider(llm_provider_type, mock_llm_provider):
    """
    Factory для создания LLM провайдера.
    
    Переключается между mock и real LLM через переменную окружения TEST_LLM_TYPE.
    """
    if llm_provider_type == 'mock':
        return mock_llm_provider
    elif llm_provider_type == 'real':
        # Для real LLM требуется реальная конфигурация
        # Возвращаем None, тесты должны сами создать провайдер
        pytest.skip("Real LLM tests require actual LLM configuration")
    else:
        raise ValueError(f"Unknown LLM type: {llm_provider_type}")


# ============================================================================
# Оригинальные фикстуры
# ============================================================================

class FakeInfraContext:
    """Fake InfrastructureContext для юнит-тестов."""
    def __init__(self, data_dir='data'):
        from core.config.models import SystemConfig
        self.config = SystemConfig(
            llm_providers={},
            db_providers={},
            data_dir=data_dir
        )
        self.id = "fake_infra_001"

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_prompt_storage(self):
        from unittest.mock import Mock
        return Mock()

    def get_contract_storage(self):
        from unittest.mock import Mock
        return Mock()

    def get_provider(self, name):
        return None


@pytest.fixture
def fake_infra_context():
    """Создает FakeInfraContext для тестов."""
    return FakeInfraContext()


@pytest.fixture
def real_component_config():
    """Создает реальный ComponentConfig для тестов."""
    from core.config.component_config import ComponentConfig
    return ComponentConfig(
        variant_id="test_component_default",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={},
        side_effects_enabled=True,
        detailed_metrics=False,
        parameters={},
        dependencies=[]
    )


@pytest.fixture
def real_application_context(fake_infra_context):
    """Создает минимальный реальный ApplicationContext для тестов."""
    from core.config.app_config import AppConfig
    from core.application_context.application_context import ApplicationContext

    app_config = AppConfig(
        config_id="test_config",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={},
        side_effects_enabled=True,
        detailed_metrics=False
    )

    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="test"
    )
    return app_context


@pytest.fixture
def create_react_pattern():
    """Factory fixture для создания ReActPattern в тестах.

    Тесты с этим фикстурой должны создавать собственный ApplicationContext.
    """
    from core.agent.behaviors.base import ReActInput, ReActOutput
    from core.config.component_config import ComponentConfig

    def _create(application_context=None):
        if application_context is None:
            # Создаем минимальный mock context только для тестов структуры
            from unittest.mock import Mock
            application_context = Mock()
            application_context.get_service = Mock(return_value=None)

        config = ComponentConfig(
            variant_id="test_react_default",
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False,
            parameters={},
            dependencies=[]
        )

        # Возвращаем класс для совместимости
        return type('ReActPatternMock', (), {
            'ReActInput': ReActInput,
            'ReActOutput': ReActOutput
        })

    return _create


@pytest.fixture
def create_planning_pattern():
    """Factory fixture для создания PlanningPattern в тестах."""
    from core.agent.behaviors.base import PlanningInput, PlanningOutput
    from core.config.component_config import ComponentConfig

    def _create(application_context=None):
        if application_context is None:
            from unittest.mock import Mock
            application_context = Mock()
            application_context.get_service = Mock(return_value=None)

        config = ComponentConfig(
            variant_id="test_planning_default",
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False,
            parameters={},
            dependencies=[]
        )

        # Возвращаем класс для совместимости
        return type('PlanningPatternMock', (), {
            'PlanningInput': PlanningInput,
            'PlanningOutput': PlanningOutput
        })

    return _create


@pytest.fixture
def create_evaluation_pattern():
    """Factory fixture для создания EvaluationPattern в тестах."""
    from core.agent.behaviors.evaluation.pattern import EvaluationPattern
    from core.config.component_config import ComponentConfig

    def _create():
        config = ComponentConfig(variant_id="test_evaluation")
        return EvaluationPattern(
            component_name="test_evaluation_pattern",
            component_config=config
        )

    return _create


@pytest.fixture
def create_fallback_pattern():
    """Factory fixture для создания FallbackPattern в тестах."""
    from core.agent.behaviors.fallback.pattern import FallbackPattern
    from core.config.component_config import ComponentConfig

    def _create():
        config = ComponentConfig(variant_id="test_fallback")
        return FallbackPattern(
            component_name="test_fallback_pattern",
            component_config=config
        )

    return _create
