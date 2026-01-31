"""
Тесты для базового класса навыка (BaseSkill).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.skills.base_skill import BaseSkill
from core.session_context.base_session_context import BaseSessionContext
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus


class ConcreteSkill(BaseSkill):
    """Конкретная реализация BaseSkill для тестов."""
    
    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        self.name = name
        self.executed = False
    
    def get_capabilities(self):
        return [
            Capability(
                name="test_capability",
                description="Тестовая возможность",
                parameters_schema={},
                skill_name=self.name
            )
        ]
    
    async def execute(self, capability, parameters, context):
        self.executed = True
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result={"test": "result"},
            observation_item_id="test_id",
            summary="Test execution completed",
            error=None
        )


class TestBaseSkill:
    """Тесты для BaseSkill."""
    
    def test_initialization(self):
        """Тест инициализации навыка."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        skill = ConcreteSkill("test_skill", mock_system_context, config_param="test_value")
        
        assert skill.name == "test_skill"
        assert skill.system_context == mock_system_context
        assert skill.config == {"config_param": "test_value"}
    
    def test_get_capability_by_name_found(self):
        """Тест метода get_capability_by_name - capability найдена."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        skill = ConcreteSkill("test_skill", mock_system_context)
        
        capability = skill.get_capability_by_name("test_capability")
        
        assert capability.name == "test_capability"
        assert capability.skill_name == "test_skill"
    
    def test_get_capability_by_name_not_found(self):
        """Тест метода get_capability_by_name - capability не найдена."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        skill = ConcreteSkill("test_skill", mock_system_context)
        
        with pytest.raises(ValueError, match="Capability 'nonexistent' не найдена в skill 'test_skill'"):
            skill.get_capability_by_name("nonexistent")
    
    def test_get_capability_by_name_case_insensitive(self):
        """Тест метода get_capability_by_name - регистронезависимый поиск."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        skill = ConcreteSkill("test_skill", mock_system_context)
        
        capability = skill.get_capability_by_name("TEST_CAPABILITY")
        
        assert capability.name == "test_capability"
        assert capability.skill_name == "test_skill"
    
    @pytest.mark.asyncio
    async def test_execute_method(self):
        """Тест метода execute."""
        mock_system_context = MagicMock(spec=BaseSystemContext)
        mock_session_context = MagicMock(spec=BaseSessionContext)
        skill = ConcreteSkill("test_skill", mock_system_context)
        
        # Создаем тестовую capability
        capability = Capability(
            name="test_capability",
            description="Тестовая возможность",
            parameters_schema={},
            skill_name="test_skill"
        )
        
        result = await skill.execute(capability, {}, mock_session_context)
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result == {"test": "result"}
        assert skill.executed is True


def test_base_skill_abstract_methods():
    """Тест, что BaseSkill нельзя инстанцировать без реализации абстрактных методов."""
    mock_system_context = MagicMock(spec=BaseSystemContext)
    
    with pytest.raises(TypeError):
        BaseSkill("test", mock_system_context)