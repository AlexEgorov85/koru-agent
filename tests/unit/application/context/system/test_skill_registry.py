"""
Тесты реестра навыков
"""
import pytest
from application.context.system.system_context import SystemContext
from domain.abstractions.base_skill import BaseSkill
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus
from domain.models.capability import Capability


class MockSkill(BaseSkill):
    """Мок-навык для тестирования"""
    
    def __init__(self, name: str, description: str = "Mock skill for testing", 
                 category: str = "test", required_tools: list = None, 
                 optional_tools: list = None):
        self.name = name
        self._description = description
        self.category = category
        self.required_tools = required_tools or []
        self.optional_tools = optional_tools or []
    
    async def execute(self, capability, parameters: dict, context):
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"status": "success", "result": "mock_skill_result"},
            observation_item_id="mock_observation",
            summary="Mock skill executed successfully"
        )


def test_register_unique_named_skill_succeeds():
    """Регистрация навыка с уникальным именем проходит успешно"""
    system = SystemContext()
    skill = MockSkill(name="unique_skill")
    
    system.register_skill(skill)
    
    retrieved_skill = system.get_skill("unique_skill")
    assert retrieved_skill is not None
    assert retrieved_skill.name == "unique_skill"


def test_attempt_to_register_duplicate_named_skill_raises_exception():
    """Попытка регистрации навыка с дублирующим именем вызывает исключение"""
    system = SystemContext()
    skill1 = MockSkill(name="duplicate_skill")
    skill2 = MockSkill(name="duplicate_skill")
    
    system.register_skill(skill1)
    
    with pytest.raises(ValueError):
        system.register_skill(skill2)


def test_get_skill_by_name_returns_registered_instance():
    """Получение навыка по имени возвращает зарегистрированный экземпляр"""
    system = SystemContext()
    skill = MockSkill(name="test_skill", description="A test skill")
    
    system.register_skill(skill)
    
    retrieved_skill = system.get_skill("test_skill")
    assert retrieved_skill is not None
    assert retrieved_skill is skill  # Проверяем, что это тот же экземпляр
    assert retrieved_skill._description == "A test skill"


def test_get_nonexistent_skill_returns_none():
    """Получение несуществующего навыка возвращает None (не исключение)"""
    system = SystemContext()
    
    retrieved_skill = system.get_skill("nonexistent_skill")
    assert retrieved_skill is None


def test_get_all_skills_returns_dictionary_of_name_to_skill():
    """Получение всех навыков возвращает словарь {имя: навык}"""
    system = SystemContext()
    skill1 = MockSkill(name="skill1")
    skill2 = MockSkill(name="skill2")
    
    system.register_skill(skill1)
    system.register_skill(skill2)
    
    all_skills = system.get_all_skills()
    assert len(all_skills) == 2
    assert "skill1" in all_skills
    assert "skill2" in all_skills
    assert all_skills["skill1"] is skill1
    assert all_skills["skill2"] is skill2


def test_filter_skills_by_category_returns_matching_skills_only():
    """Фильтрация навыков по категориям возвращает только подходящие навыки"""
    system = SystemContext()
    skill_with_category = MockSkill(name="skill_with_category", category="data_processing")
    skill_with_different_category = MockSkill(name="skill_with_different_category", category="analysis")
    skill_without_category = MockSkill(name="skill_without_category", category="test")
    
    system.register_skill(skill_with_category)
    system.register_skill(skill_with_different_category)
    system.register_skill(skill_without_category)
    
    filtered_skills = system.filter_skills_by_category("data_processing")
    assert len(filtered_skills) == 1
    assert "skill_with_category" in filtered_skills


def test_get_skill_dependencies_returns_list_of_required_tools():
    """Получение зависимостей навыка возвращает список требуемых инструментов"""
    system = SystemContext()
    skill = MockSkill(name="skill_with_deps", required_tools=["tool1", "tool2"])
    
    system.register_skill(skill)
    
    dependencies = system.get_skill_dependencies("skill_with_deps")
    assert dependencies == ["tool1", "tool2"]


def test_check_skill_readiness_works_correctly_when_all_dependencies_registered():
    """Проверка готовности навыка (все зависимости зарегистрированы) работает корректно"""
    system = SystemContext()
    # Регистрируем требуемые инструменты
    from domain.abstractions.tools.base_tool import BaseTool, ToolInput, ToolOutput
    
    class MockToolInput(ToolInput):
        pass
    
    class MockToolOutput(ToolOutput):
        result: str
    
    class MockTool(BaseTool):
        def __init__(self, name: str = "mock_tool", description: str = "Mock tool for testing"):
            self.name = name
            self._description = description
        
        @property
        def description(self) -> str:
            return self._description
        
        async def initialize(self) -> bool:
            return True
        
        async def execute(self, input_data: ToolInput) -> ToolOutput:
            return MockToolOutput(result="mock_result")
        
        async def shutdown(self) -> None:
            pass
    
    tool1 = MockTool(name="tool1")
    tool2 = MockTool(name="tool2")
    
    system.register_tool(tool1)
    system.register_tool(tool2)
    
    # Регистрируем навык с этими зависимостями
    skill = MockSkill(name="ready_skill", required_tools=["tool1", "tool2"])
    system.register_skill(skill)
    
    # Проверяем готовность навыка
    is_ready = system.is_skill_ready("ready_skill")
    assert is_ready is True


def test_check_skill_readiness_fails_when_dependencies_not_registered():
    """Проверка готовности навыка не проходит, если зависимости не зарегистрированы"""
    system = SystemContext()
    # Регистрируем только один из двух требуемых инструментов
    from domain.abstractions.tools.base_tool import BaseTool, ToolInput, ToolOutput
    
    class MockToolInput(ToolInput):
        pass
    
    class MockToolOutput(ToolOutput):
        result: str
    
    class MockTool(BaseTool):
        def __init__(self, name: str = "mock_tool", description: str = "Mock tool for testing"):
            self.name = name
            self._description = description
        
        @property
        def description(self) -> str:
            return self._description
        
        async def initialize(self) -> bool:
            return True
        
        async def execute(self, input_data: ToolInput) -> ToolOutput:
            return MockToolOutput(result="mock_result")
        
        async def shutdown(self) -> None:
            pass
    
    tool1 = MockTool(name="tool1")
    system.register_tool(tool1)
    
    # Регистрируем навык с двумя зависимостями, но одна не зарегистрирована
    skill = MockSkill(name="unready_skill", required_tools=["tool1", "tool2"])
    system.register_skill(skill)
    
    # Проверяем готовность навыка
    is_ready = system.is_skill_ready("unready_skill")
    assert is_ready is False