"""
Интеграционные тесты для Этапа 7.

ТЕСТЫ:
- test_data_repository_version_methods: методы управления версиями
- test_base_skill_publish_metrics: публикация метрик
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.data.prompt import Prompt, PromptStatus
from core.models.data.contract import Contract, ContractDirection
from core.models.enums.common_enums import ComponentType


class TestDataRepositoryVersionMethods:
    """Тесты методов управления версиями в DataRepository"""

    @pytest.fixture
    def mock_data_source(self):
        """Моковый DataSource"""
        data_source = MagicMock()
        data_source.load_all_prompts = MagicMock(return_value=[])
        data_source.load_all_contracts = MagicMock(return_value=[])
        return data_source

    @pytest.fixture
    def data_repository(self, mock_data_source):
        """DataRepository для тестов"""
        from core.components.services.data_repository import DataRepository
        
        repo = DataRepository(data_source=mock_data_source, profile='sandbox')
        repo._initialized = True  # Пропускаем инициализацию для тестов
        return repo

    def test_get_prompt_versions(self, data_repository):
        """Тест получения всех версий промпта"""
        # Добавляем тестовые промпты
        prompt_v1 = Prompt(
            capability='test.capability',
            version='v1.0.0',
            content='Version 1 content with enough characters',
            status='active',
            component_type=ComponentType.SKILL
        )
        prompt_v2 = Prompt(
            capability='test.capability',
            version='v2.0.0',
            content='Version 2 content with enough characters',
            status='draft',
            component_type=ComponentType.SKILL
        )
        prompt_other = Prompt(
            capability='other.capability',
            version='v1.0.0',
            content='Other capability content with enough chars',
            status='active',
            component_type=ComponentType.SKILL
        )

        data_repository._prompts_index = {
            ('test.capability', 'v1.0.0'): prompt_v1,
            ('test.capability', 'v2.0.0'): prompt_v2,
            ('other.capability', 'v1.0.0'): prompt_other,
        }

        # Получение версий
        versions = data_repository.get_prompt_versions('test.capability')

        assert len(versions) == 2
        assert versions[0].version == 'v1.0.0'
        assert versions[1].version == 'v2.0.0'

    def test_get_active_version(self, data_repository):
        """Тест получения активной версии"""
        prompt_active = Prompt(
            capability='test.capability',
            version='v1.0.0',
            content='Active version content with enough chars',
            status='active',
            component_type=ComponentType.SKILL
        )
        prompt_draft = Prompt(
            capability='test.capability',
            version='v2.0.0',
            content='Draft version content with enough chars',
            status='draft',
            component_type=ComponentType.SKILL
        )

        data_repository._prompts_index = {
            ('test.capability', 'v1.0.0'): prompt_active,
            ('test.capability', 'v2.0.0'): prompt_draft,
        }

        # Получение активной версии
        active_version = data_repository.get_active_version('test.capability')

        assert active_version == 'v1.0.0'

    def test_get_active_version_not_found(self, data_repository):
        """Тест когда активная версия не найдена"""
        prompt_draft = Prompt(
            capability='test.capability',
            version='v1.0.0',
            content='Draft version content with enough chars',
            status='draft',
            component_type=ComponentType.SKILL
        )

        data_repository._prompts_index = {
            ('test.capability', 'v1.0.0'): prompt_draft,
        }

        active_version = data_repository.get_active_version('test.capability')

        assert active_version is None

    def test_get_draft_versions(self, data_repository):
        """Тест получения draft версий"""
        prompt_active = Prompt(
            capability='test.capability',
            version='v1.0.0',
            content='Active version content with enough chars',
            status='active',
            component_type=ComponentType.SKILL
        )
        prompt_draft1 = Prompt(
            capability='test.capability',
            version='v2.0.0',
            content='Draft 1 content with enough characters',
            status='draft',
            component_type=ComponentType.SKILL
        )
        prompt_draft2 = Prompt(
            capability='test.capability',
            version='v3.0.0',
            content='Draft 2 content with enough characters',
            status='draft',
            component_type=ComponentType.SKILL
        )

        data_repository._prompts_index = {
            ('test.capability', 'v1.0.0'): prompt_active,
            ('test.capability', 'v2.0.0'): prompt_draft1,
            ('test.capability', 'v3.0.0'): prompt_draft2,
        }

        drafts = data_repository.get_draft_versions('test.capability')

        assert len(drafts) == 2
        assert 'v2.0.0' in drafts
        assert 'v3.0.0' in drafts

    def test_update_prompt_status(self, data_repository):
        """Тест обновления статуса промпта"""
        prompt = Prompt(
            capability='test.capability',
            version='v1.0.0',
            content='Original content with enough characters',
            status='draft',
            component_type=ComponentType.SKILL
        )

        data_repository._prompts_index = {
            ('test.capability', 'v1.0.0'): prompt,
        }

        # Обновление статуса (через model_copy т.к. Prompt - frozen модель)
        result = data_repository.update_prompt_status(
            'test.capability',
            'v1.0.0',
            PromptStatus.ACTIVE
        )

        assert result is True
        # Проверяем что статус обновлён в индексе
        updated_prompt = data_repository._prompts_index[('test.capability', 'v1.0.0')]
        assert updated_prompt.status == PromptStatus.ACTIVE
        # Оригинальный объект не изменился (frozen)
        assert prompt.status == PromptStatus.DRAFT

    def test_update_prompt_status_not_found(self, data_repository):
        """Тест обновления несуществующего промпта"""
        result = data_repository.update_prompt_status(
            'nonexistent.capability',
            'v1.0.0',
            PromptStatus.ACTIVE
        )

        assert result is False

    def test_add_prompt(self, data_repository):
        """Тест добавления нового промпта"""
        new_prompt = Prompt(
            capability='new.capability',
            version='v1.0.0',
            content='New prompt content with enough characters',
            status='draft',
            component_type=ComponentType.SKILL
        )

        result = data_repository.add_prompt(new_prompt)

        assert result is True
        assert ('new.capability', 'v1.0.0') in data_repository._prompts_index

    def test_add_prompt_duplicate(self, data_repository):
        """Тест добавления дубликата"""
        existing_prompt = Prompt(
            capability='test.capability',
            version='v1.0.0',
            content='Existing content with enough characters',
            status='active',
            component_type=ComponentType.SKILL
        )

        data_repository._prompts_index = {
            ('test.capability', 'v1.0.0'): existing_prompt,
        }

        duplicate_prompt = Prompt(
            capability='test.capability',
            version='v1.0.0',
            content='Duplicate content with enough characters',
            status='draft',
            component_type=ComponentType.SKILL
        )

        result = data_repository.add_prompt(duplicate_prompt)

        assert result is False

    def test_add_contract(self, data_repository):
        """Тест добавления контракта"""
        new_contract = Contract(
            capability='test.capability',
            version='v1.0.0',
            input_schema={'type': 'object'},
            status='active',
            component_type=ComponentType.SKILL,
            direction=ContractDirection.INPUT,
            schema_data={'type': 'object'}
        )

        result = data_repository.add_contract(new_contract)

        assert result is True
        key = ('test.capability', 'v1.0.0', 'input')
        assert key in data_repository._contracts_index

    def test_get_contract_versions(self, data_repository):
        """Тест получения версий контрактов"""
        contract_v1 = Contract(
            capability='test.capability',
            version='v1.0.0',
            input_schema={'type': 'object'},
            status='active',
            component_type=ComponentType.SKILL,
            direction=ContractDirection.INPUT,
            schema_data={'type': 'object'}
        )
        contract_v2 = Contract(
            capability='test.capability',
            version='v2.0.0',
            input_schema={'type': 'object'},
            status='draft',
            component_type=ComponentType.SKILL,
            direction=ContractDirection.INPUT,
            schema_data={'type': 'object'}
        )

        data_repository._contracts_index = {
            ('test.capability', 'v1.0.0', 'input'): contract_v1,
            ('test.capability', 'v2.0.0', 'input'): contract_v2,
        }

        versions = data_repository.get_contract_versions('test.capability', 'input')

        assert len(versions) == 2

    def test_update_contract_status(self, data_repository):
        """Тест обновления статуса контракта"""
        contract = Contract(
            capability='test.capability',
            version='v1.0.0',
            input_schema={'type': 'object'},
            status='draft',
            component_type=ComponentType.SKILL,
            direction=ContractDirection.INPUT,
            schema_data={'type': 'object'}
        )

        data_repository._contracts_index = {
            ('test.capability', 'v1.0.0', 'input'): contract,
        }

        # Обновление статуса (через model_copy т.к. Contract - frozen модель)
        result = data_repository.update_contract_status(
            'test.capability',
            'v1.0.0',
            'input',
            PromptStatus.ACTIVE  # Меняем статус на active
        )

        assert result is True
        # Проверяем что статус обновлён в индексе
        updated_contract = data_repository._contracts_index[('test.capability', 'v1.0.0', 'input')]
        assert updated_contract.status == PromptStatus.ACTIVE
        # Оригинальный объект не изменился (frozen)
        assert contract.status == 'draft'


class TestBaseSkillPublishMetrics:
    """Тесты публикации метрик в BaseSkill"""

    @pytest.fixture
    def mock_infrastructure_context(self):
        """Моковый InfrastructureContext"""
        infra_ctx = MagicMock()
        infra_ctx.event_bus = AsyncMock()
        infra_ctx.event_bus.publish = AsyncMock()
        return infra_ctx

    @pytest.fixture
    def mock_application_context(self, mock_infrastructure_context):
        """Моковый ApplicationContext"""
        app_ctx = MagicMock()
        app_ctx.infrastructure_context = mock_infrastructure_context
        app_ctx.agent_id = 'test_agent_123'
        return app_ctx

    @pytest.fixture
    def mock_config(self):
        """Моковая конфигурация"""
        config = MagicMock()
        return config

    @pytest.fixture
    def base_skill(self, mock_application_context, mock_config):
        """BaseSkill для тестов"""
        from core.components.skills.base_skill import BaseSkill
        from core.models.data.capability import Capability
        from core.models.data.execution import ExecutionResult

        class TestSkill(BaseSkill):
            name = 'test_skill'

            def get_capabilities(self):
                return [Capability(
                    name='test_capability',
                    description='Test capability',
                    skill_name='test_skill'
                )]

            async def execute(self, capability, parameters, context):
                """Реализация абстрактного метода"""
                return ExecutionResult(
                    capability=capability.name,
                    success=True,
                    content={'result': 'test'}
                )

        skill = TestSkill(
            name='test_skill',
            application_context=mock_application_context,
            app_config=mock_config
        )
        return skill

    @pytest.mark.asyncio
    async def test_publish_metrics_success(self, base_skill, mock_infrastructure_context):
        """Тест успешной публикации метрик"""
        from core.infrastructure.event_bus import EventType

        await base_skill._publish_metrics(
            event_type=EventType.SKILL_EXECUTED,
            capability_name='test_capability',
            success=True,
            execution_time_ms=150.5,
            tokens_used=500,
            version='v1.0.0',
            session_id='session_123'
        )

        # Проверка что publish был вызван
        assert mock_infrastructure_context.event_bus.publish.called

        # Проверка аргументов
        call_args = mock_infrastructure_context.event_bus.publish.call_args
        assert call_args is not None

        # Проверка типа события
        event_type = call_args[0][0]
        assert event_type.value == 'skill.executed'

        # Проверка данных
        data = call_args[1]['data']
        assert data['capability'] == 'test_capability'
        assert data['success'] is True
        assert data['execution_time_ms'] == 150.5
        assert data['tokens_used'] == 500
        assert data['version'] == 'v1.0.0'
        assert data['session_id'] == 'session_123'
        assert data['agent_id'] == 'test_agent_123'

    @pytest.mark.asyncio
    async def test_publish_metrics_failure(self, base_skill, mock_infrastructure_context):
        """Тест публикации метрик неудачи"""
        from core.infrastructure.event_bus import EventType

        await base_skill._publish_metrics(
            event_type=EventType.SKILL_EXECUTED,
            capability_name='test_capability',
            success=False,
            execution_time_ms=200.0,
            tokens_used=0,
            version='v1.0.0'
        )

        call_args = mock_infrastructure_context.event_bus.publish.call_args
        data = call_args[1]['data']

        assert data['success'] is False
        assert data['tokens_used'] == 0

    @pytest.mark.asyncio
    async def test_publish_metrics_default_values(self, base_skill, mock_infrastructure_context):
        """Тест публикации с значениями по умолчанию"""
        from core.infrastructure.event_bus import EventType

        await base_skill._publish_metrics(
            event_type=EventType.SKILL_EXECUTED,
            capability_name='test_capability',
            success=True,
            execution_time_ms=100.0
        )

        call_args = mock_infrastructure_context.event_bus.publish.call_args
        data = call_args[1]['data']

        # Проверяем значения по умолчанию
        assert data['tokens_used'] == 0
        # version и session_id могут отсутствовать если не переданы
        assert 'version' not in data or data['version'] is None
        assert 'session_id' not in data or data['session_id'] is None

    @pytest.mark.asyncio
    async def test_publish_metrics_no_infrastructure_context(self, base_skill):
        """Тест когда infrastructure_context отсутствует"""
        from core.infrastructure.event_bus import EventType

        # Удаляем infrastructure_context
        del base_skill.application_context.infrastructure_context

        # Не должно вызвать ошибку (метод должен корректно обработать отсутствие infrastructure_context)
        await base_skill._publish_metrics(
            event_type=EventType.SKILL_EXECUTED,
            capability_name='test_capability',
            success=True,
            execution_time_ms=100.0
        )

        # Проверяем что метод выполнился без ошибок
        # (если бы была ошибка, тест упал бы выше)
        assert base_skill.application_context is not None