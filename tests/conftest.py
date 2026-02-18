"""
Helper fixtures для тестирования.

ПРИМЕЧАНИЕ: Моки допускаются только для LLM и БД провайдеров.
Для остальных компонентов используются реальные объекты или fake-классы.
"""
import pytest
from pathlib import Path


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
    from core.application.context.application_context import ApplicationContext
    
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
    from core.application.behaviors.react_pattern import ReActPattern
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
        
        return ReActPattern(
            name="test_react_pattern",
            application_context=application_context,
            component_config=config
        )

    return _create


@pytest.fixture
def create_planning_pattern():
    """Factory fixture для создания PlanningPattern в тестах."""
    from core.application.behaviors.planning_pattern import PlanningPattern
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
        
        return PlanningPattern(
            name="test_planning_pattern",
            application_context=application_context,
            component_config=config
        )

    return _create


@pytest.fixture
def create_evaluation_pattern():
    """Factory fixture для создания EvaluationPattern в тестах."""
    from core.application.behaviors.evaluation.pattern import EvaluationPattern

    def _create():
        return EvaluationPattern(
            pattern_id="test_evaluation_pattern"
        )

    return _create


@pytest.fixture
def create_fallback_pattern():
    """Factory fixture для создания FallbackPattern в тестах."""
    from core.application.behaviors.fallback.pattern import FallbackPattern

    def _create():
        return FallbackPattern(
            pattern_id="test_fallback_pattern"
        )

    return _create
