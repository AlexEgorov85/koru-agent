"""Тесты для паттерна ReAct с интеграцией PromptRepository"""
import pytest
from unittest.mock import Mock, AsyncMock
from domain.models.capability import Capability
from domain.models.prompt.prompt_version import PromptVersion, PromptRole, VariableSchema
from application.orchestration.patterns.patterns import ReActPattern
from application.services.prompt_renderer import PromptRenderer
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType


class TestReActPatternUpdated:
    """Тесты для паттерна ReAct с интеграцией PromptRepository"""
    
    def test_react_pattern_creation(self):
        """Тест создания паттерна ReAct"""
        pattern = ReActPattern()
        
        # Проверяем, что объект создался успешно
        assert pattern is not None
        assert isinstance(pattern, ReActPattern)
    
    def test_react_pattern_str_representation(self):
        """Тест строкового представления паттерна ReAct"""
        pattern = ReActPattern()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "ReActPattern" in str(pattern)
    
    def test_react_pattern_attributes(self):
        """Тест атрибутов паттерна ReAct"""
        pattern = ReActPattern()
        
        # Проверяем, что паттерн имеет ожидаемые характеристики
        assert hasattr(pattern, '__class__')
        assert pattern.__class__.__name__ == 'ReActPattern'


@pytest.mark.asyncio
async def test_react_pattern_with_prompt_repository():
    """Тест паттерна ReAct с использованием PromptRepository"""
    # Создаем репозиторий и добавляем версию для ReAct
    repo = Mock()
    repo.get_version_by_id = AsyncMock()
    
    # Подготовка версии промта для ReAct
    react_version = PromptVersion(
        id="react_pattern_version",
        semantic_version="1.0.0",
    domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="thinking.react",
        role=PromptRole.SYSTEM,
        content="You are implementing ReAct pattern. Task: {{task}}, Context: {{context}}, Tools: {{available_tools}}",
        variables_schema=[
            VariableSchema(name="task", type="string", required=True),
            VariableSchema(name="context", type="string", required=False),
            VariableSchema(name="available_tools", type="string", required=False)
        ],
        status="active"
    )
    
    # Настройка mock
    repo.get_version_by_id.return_value = react_version
    
    # Создаем capability для ReAct
    capability = Capability(
        name="thinking.react",
        description="ReAct Pattern (Reasoning and Acting)",
        skill_name="reasoning_skill",
        prompt_versions={
            "openai:system": "react_pattern_version"
        }
    )
    
    # Создаем рендерер
    renderer = PromptRenderer(repo)
    
    # Рендерим промт
    rendered_prompts, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            "task": "Solve the math problem",
            "context": "Using calculator tool",
            "available_tools": "calculator, search"
        },
        session_id="test_session_123"
    )
    
    # Проверяем результат
    assert PromptRole.SYSTEM in rendered_prompts
    expected_content = "You are implementing ReAct pattern. Task: Solve the math problem, Context: Using calculator tool, Tools: calculator, search"
    assert rendered_prompts[PromptRole.SYSTEM] == expected_content
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_react_pattern_with_validation_errors():
    """Тест паттерна ReAct с ошибками валидации переменных"""
    # Создаем mock репозитория
    repo = Mock()
    repo.get_version_by_id = AsyncMock()
    
    # Подготовка версии промта для ReAct с обязательной переменной
    react_version = PromptVersion(
        id="react_pattern_version",
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="thinking.react",
        role=PromptRole.SYSTEM,
        content="You are implementing ReAct pattern. Task: {{task}}, Context: {{context}}",
        variables_schema=[
            VariableSchema(name="task", type="string", required=True),
            VariableSchema(name="context", type="string", required=False)
        ],
        status="active"
    )
    
    # Настройка mock
    repo.get_version_by_id.return_value = react_version
    
    # Создаем capability для ReAct
    capability = Capability(
        name="thinking.react",
        description="ReAct Pattern (Reasoning and Acting)",
        skill_name="reasoning_skill",
        prompt_versions={
            "openai:system": "react_pattern_version"
        }
    )
    
    # Создаем рендерер
    renderer = PromptRenderer(repo)
    
    # Рендерим промт без обязательной переменной task
    rendered_prompts, errors = await renderer.render_for_request(
        capability=capability,
        provider_type=LLMProviderType.OPENAI,
        template_context={
            # task отсутствует - обязательная переменная
            "context": "Using calculator tool"
        },
        session_id="test_session_123"
    )
    
    # Проверяем, что есть ошибки валидации
    assert len(errors) > 0
    assert "task" in str(errors[0])  # Ошибка должна касаться отсутствующей переменной
    assert len(rendered_prompts) == 0  # Нет отрендеренного содержимого из-за ошибок


@pytest.mark.asyncio
async def test_react_pattern_integration_with_execution():
    """Тест интеграции паттерна ReAct с выполнением через ExecutionGateway"""
    # Этот тест проверяет, как паттерн ReAct будет интегрироваться с ExecutionGateway
    from application.gateways.execution.execution_gateway import ExecutionGateway
    
    # Создаем mock системного контекста
    mock_system_context = Mock()
    mock_skill = Mock()
    mock_skill.execute = AsyncMock(return_value="ReAct pattern executed successfully")
    mock_system_context.get_resource.return_value = mock_skill
    
    # Создаем mock репозитория промтов
    mock_repo = Mock()
    mock_repo.get_version_by_id = AsyncMock()
    
    # Подготовка версии промта для ReAct
    react_version = PromptVersion(
        id="react_pattern_version",
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="thinking.react",
        role=PromptRole.SYSTEM,
        content="Implement ReAct: {{task}} with {{tools}}",
        variables_schema=[
            VariableSchema(name="task", type="string", required=True),
            VariableSchema(name="tools", type="string", required=True)
        ],
        status="active"
    )
    
    mock_repo.get_version_by_id.return_value = react_version
    
    # Создаем capability для ReAct
    capability = Capability(
        name="thinking.react",
        description="ReAct Pattern (Reasoning and Acting)",
        skill_name="reasoning_skill",
        prompt_versions={
            "openai:system": "react_pattern_version"
        }
    )
    
    # Создаем ExecutionGateway с репозиторием
    gateway = ExecutionGateway(mock_system_context, prompt_repository=mock_repo)
    
    # Создаем mock сессии
    mock_session = Mock()
    mock_session.get_goal = Mock(return_value="Test goal")
    mock_session.get_last_steps = Mock(return_value=["Previous step"])
    
    # Выполняем capability с паттерном ReAct
    result = await gateway.execute_capability(
        capability=capability,
        parameters={
            "task": "Solve equation",
            "tools": "calculator"
        },
        session=mock_session
    )
    
    # Проверяем результат
    assert result.status.name == "SUCCESS"
    assert "executed successfully" in result.summary