"""Тесты для навыка планирования с интеграцией PromptRepository"""
import pytest
from unittest.mock import Mock, AsyncMock
from infrastructure.adapters.skills.planning.skill import PlanningSkill
from domain.models.capability import Capability
from domain.models.prompt.prompt_version import PromptVersion, PromptRole, VariableSchema
from application.services.prompt_renderer import PromptRenderer
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType


class TestPlanningSkillUpdated:
    """Тесты для навыка планирования с интеграцией PromptRepository"""
    
    def test_planning_skill_creation(self):
        """Тест создания навыка планирования"""
        skill = PlanningSkill()
        
        # Проверяем, что объект создался успешно
        assert skill is not None
        assert hasattr(skill, 'execute')
        assert skill.name == "planning"
    
    def test_planning_skill_execute_method_exists(self):
        """Тест что у навыка планирования есть метод execute"""
        skill = PlanningSkill()
        
        assert hasattr(skill, 'execute')
        assert callable(getattr(skill, 'execute'))
    
    def test_planning_skill_get_capabilities(self):
        """Тест метода получения возможностей навыка"""
        skill = PlanningSkill()
        
        capabilities = skill.get_capabilities()
        assert len(capabilities) >= 1  # Может быть больше одного capability
    
    def test_planning_skill_str_representation(self):
        """Тест строкового представления навыка планирования"""
        skill = PlanningSkill()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "PlanningSkill" in str(skill)
    
    def test_planning_skill_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        skill = PlanningSkill()
        
        repr_str = repr(skill)
        assert "PlanningSkill" in repr_str


@pytest.mark.asyncio
async def test_planning_skill_with_prompt_repository():
    """Тест навыка планирования с использованием PromptRepository"""
    # Создаем mock репозитория и добавляем версию для планирования
    repo = Mock()
    repo.get_version_by_id = AsyncMock()
    
    # Подготовка версии промта для планирования
    planning_version = PromptVersion(
        id="planning_version_123",
        semantic_version="1.0.0",
        domain=DomainType.PLANNING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="planning.skill",
        role=PromptRole.SYSTEM,
        content="Create a plan for: {{goal}}. Consider: {{constraints}}",
        variables_schema=[
            VariableSchema(name="goal", type="string", required=True),
            VariableSchema(name="constraints", type="string", required=False)
        ],
        status="active"
    )
    
    # Настройка mock
    repo.get_version_by_id.return_value = planning_version
    
    # Создаем capability для планирования
    capability = Capability(
        name="planning.skill",
        description="Planning Skill Capability",
        skill_name="planning_skill",
        prompt_versions={
            "openai:system": "planning_version_123"
        }
    )
    
    # Создаем рендерер
    renderer = PromptRenderer(repo)
    
    # Рендерим промт
    rendered_prompts, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "goal": "Complete the project",
            "constraints": "Limited resources, tight deadline"
        },
        session_id="test_session_123"
    )
    
    # Проверяем результат
    assert PromptRole.SYSTEM in rendered_prompts
    expected_content = "Create a plan for: Complete the project. Consider: Limited resources, tight deadline"
    assert rendered_prompts[PromptRole.SYSTEM] == expected_content
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_planning_skill_with_validation_errors():
    """Тест навыка планирования с ошибками валидации переменных"""
    # Создаем mock репозитория
    repo = Mock()
    repo.get_version_by_id = AsyncMock()
    
    # Подготовка версии промта для планирования с обязательной переменной
    planning_version = PromptVersion(
        id="planning_version_123",
        semantic_version="1.0.0",
        domain=DomainType.PLANNING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="planning.skill",
        role=PromptRole.SYSTEM,
        content="Create a plan for: {{goal}}",
        variables_schema=[
            VariableSchema(name="goal", type="string", required=True)
        ],
        status="active"
    )
    
    # Настройка mock
    repo.get_version_by_id.return_value = planning_version
    
    # Создаем capability для планирования
    capability = Capability(
        name="planning.skill",
        description="Planning Skill Capability",
        skill_name="planning_skill",
        prompt_versions={
            "openai:system": "planning_version_123"
        }
    )
    
    # Создаем рендерер
    renderer = PromptRenderer(repo)
    
    # Рендерим промт без обязательной переменной goal
    rendered_prompts, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            # goal отсутствует - обязательная переменная
        },
        session_id="test_session_123"
    )
    
    # Проверяем, что есть ошибки валидации
    assert len(errors) > 0
    assert "goal" in str(errors[0])  # Ошибка должна касаться отсутствующей переменной
    assert len(rendered_prompts) == 0  # Нет отрендеренного содержимого из-за ошибок


@pytest.mark.asyncio
async def test_planning_skill_execution_integration():
    """Тест интеграции навыка планирования с выполнением"""
    from application.gateways.execution.execution_gateway import ExecutionGateway
    
    # Создаем mock системного контекста
    mock_system_context = Mock()
    mock_skill = Mock()
    mock_skill.execute = AsyncMock(return_value="Plan created successfully")
    mock_system_context.get_resource.return_value = mock_skill
    
    # Создаем mock репозитория промтов
    mock_repo = Mock()
    mock_repo.get_version_by_id = AsyncMock()
    
    # Подготовка версии промта для планирования
    planning_version = PromptVersion(
        id="planning_version_123",
        semantic_version="1.0.0",
        domain=DomainType.PLANNING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="planning.skill",
        role=PromptRole.SYSTEM,
        content="Create a plan for: {{goal}}. Constraints: {{constraints}}",
        variables_schema=[
            VariableSchema(name="goal", type="string", required=True),
            VariableSchema(name="constraints", type="string", required=True)
        ],
        status="active"
    )
    
    mock_repo.get_version_by_id.return_value = planning_version
    
    # Создаем capability для планирования
    capability = Capability(
        name="planning.skill",
        description="Planning Skill Capability",
        skill_name="planning_skill",
        prompt_versions={
            "openai:system": "planning_version_123"
        }
    )
    
    # Создаем ExecutionGateway с репозиторием
    gateway = ExecutionGateway(mock_system_context, prompt_repository=mock_repo)
    
    # Создаем mock сессии
    mock_session = Mock()
    mock_session.get_goal = Mock(return_value="Test goal")
    mock_session.get_last_steps = Mock(return_value=["Previous step"])
    
    # Выполняем capability с навыком планирования
    result = await gateway.execute_capability(
        capability=capability,
        parameters={
            "goal": "Develop new feature",
            "constraints": "Must be completed in 2 weeks"
        },
        session=mock_session
    )
    
    # Проверяем результат
    assert result.status.name == "SUCCESS"
    assert "executed successfully" in result.summary


@pytest.mark.asyncio
async def test_planning_skill_with_multiple_prompt_roles():
    """Тест навыка планирования с несколькими ролями промтов"""
    # Создаем mock репозитория
    repo = Mock()
    repo.get_version_by_id = AsyncMock()
    
    # Подготовка версий промтов для разных ролей
    system_version = PromptVersion(
        id="system_version_123",
        semantic_version="1.0.0",
        domain=DomainType.PLANNING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="planning.skill",
        role=PromptRole.SYSTEM,
        content="You are a planning assistant for: {{goal}}",
        variables_schema=[
            VariableSchema(name="goal", type="string", required=True)
        ],
        status="active"
    )
    
    user_version = PromptVersion(
        id="user_version_456",
        semantic_version="1.0.0",
        domain=DomainType.PLANNING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="planning.skill",
        role=PromptRole.USER,
        content="Generate detailed plan for: {{details}}",
        variables_schema=[
            VariableSchema(name="details", type="string", required=True)
        ],
        status="active"
    )
    
    # Настройка mock для возврата разных версий
    async def mock_get_version_by_id(version_id):
        if version_id == "system_version_123":
            return system_version
        elif version_id == "user_version_456":
            return user_version
        return None
    
    repo.get_version_by_id.side_effect = mock_get_version_by_id
    
    # Создаем capability с несколькими версиями промтов
    capability = Capability(
        name="planning.skill",
        description="Planning Skill Capability",
        skill_name="planning_skill",
        prompt_versions={
            "openai:system": "system_version_123",
            "openai:user": "user_version_456"
        }
    )
    
    # Создаем рендерер
    renderer = PromptRenderer(repo)
    
    # Рендерим промты для обоих ролей
    rendered_prompts, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "goal": "Project planning",
            "details": "Develop new user interface"
        },
        session_id="test_session_123"
    )
    
    # Проверяем результаты для обеих ролей
    assert PromptRole.SYSTEM in rendered_prompts
    assert PromptRole.USER in rendered_prompts
    assert len(errors) == 0
    
    expected_system_content = "You are a planning assistant for: Project planning"
    expected_user_content = "Generate detailed plan for: Develop new user interface"
    
    assert rendered_prompts[PromptRole.SYSTEM] == expected_system_content
    assert rendered_prompts[PromptRole.USER] == expected_user_content