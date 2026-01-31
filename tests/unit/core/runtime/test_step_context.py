"""
Тесты для класса StepContext.
"""
import pytest
from core.session_context.step_context import StepContext
from core.session_context.model import AgentStep


class TestStepContext:
    """Тесты для StepContext."""
    
    def test_initialization(self):
        """Тест инициализации StepContext."""
        step_context = StepContext()
        
        assert step_context.steps == []
        assert isinstance(step_context.steps, list)
    
    def test_add_step(self):
        """Тест метода add_step."""
        step_context = StepContext()
        
        step = AgentStep(
            step_number=1,
            capability_name="test_capability",
            skill_name="test_skill",
            action_item_id="action_123",
            observation_item_ids=["obs_123"],
            summary="Test step summary"
        )
        
        step_context.add_step(step)
        
        assert len(step_context.steps) == 1
        assert step_context.steps[0] == step
        assert step_context.steps[0].step_number == 1
    
    def test_add_multiple_steps(self):
        """Тест добавления нескольких шагов."""
        step_context = StepContext()
        
        step1 = AgentStep(
            step_number=1,
            capability_name="test_capability_1",
            skill_name="test_skill_1",
            action_item_id="action_1",
            observation_item_ids=["obs_1"],
            summary="First step"
        )
        
        step2 = AgentStep(
            step_number=2,
            capability_name="test_capability_2",
            skill_name="test_skill_2",
            action_item_id="action_2",
            observation_item_ids=["obs_2"],
            summary="Second step"
        )
        
        step_context.add_step(step1)
        step_context.add_step(step2)
        
        assert len(step_context.steps) == 2
        assert step_context.steps[0].step_number == 1
        assert step_context.steps[1].step_number == 2
        assert step_context.steps[0] == step1
        assert step_context.steps[1] == step2
    
    def test_count_steps(self):
        """Тест метода count."""
        step_context = StepContext()
        
        # Добавляем несколько шагов
        step1 = AgentStep(
            step_number=1,
            capability_name="test_capability_1",
            skill_name="test_skill_1",
            action_item_id="action_1",
            observation_item_ids=["obs_1"],
            summary="First step"
        )
        
        step2 = AgentStep(
            step_number=2,
            capability_name="test_capability_2",
            skill_name="test_skill_2",
            action_item_id="action_2",
            observation_item_ids=["obs_2"],
            summary="Second step"
        )
        
        step_context.add_step(step1)
        step_context.add_step(step2)
        
        count = step_context.count()
        
        assert count == 2
    
    def test_count_empty_context(self):
        """Тест метода count для пустого контекста."""
        step_context = StepContext()
        
        count = step_context.count()
        
        assert count == 0
    
    def test_get_current_step_number_empty(self):
        """Тест метода get_current_step_number для пустого контекста."""
        step_context = StepContext()
        
        current_step = step_context.get_current_step_number()
        
        assert current_step == 0
    
    def test_get_current_step_number_with_steps(self):
        """Тест метода get_current_step_number с добавленными шагами."""
        step_context = StepContext()
        
        step1 = AgentStep(
            step_number=1,
            capability_name="test_capability_1",
            skill_name="test_skill_1",
            action_item_id="action_1",
            observation_item_ids=["obs_1"],
            summary="First step"
        )
        
        step2 = AgentStep(
            step_number=5,  # Проверим, что возвращается максимальный номер
            capability_name="test_capability_2",
            skill_name="test_skill_2",
            action_item_id="action_2",
            observation_item_ids=["obs_2"],
            summary="Fifth step"
        )
        
        step3 = AgentStep(
            step_number=3,  # Промежуточный шаг
            capability_name="test_capability_3",
            skill_name="test_skill_3",
            action_item_id="action_3",
            observation_item_ids=["obs_3"],
            summary="Third step"
        )
        
        step_context.add_step(step1)
        step_context.add_step(step2)
        step_context.add_step(step3)
        
        current_step = step_context.get_current_step_number()
        
        assert current_step == 5  # Должно вернуть максимальный номер шага
    
    def test_get_current_step_number_after_adding_steps_out_of_order(self):
        """Тест метода get_current_step_number при добавлении шагов не по порядку."""
        step_context = StepContext()
        
        step3 = AgentStep(
            step_number=3,
            capability_name="test_capability_3",
            skill_name="test_skill_3",
            action_item_id="action_3",
            observation_item_ids=["obs_3"],
            summary="Third step"
        )
        
        step1 = AgentStep(
            step_number=1,
            capability_name="test_capability_1",
            skill_name="test_skill_1",
            action_item_id="action_1",
            observation_item_ids=["obs_1"],
            summary="First step"
        )
        
        step5 = AgentStep(
            step_number=5,
            capability_name="test_capability_5",
            skill_name="test_skill_5",
            action_item_id="action_5",
            observation_item_ids=["obs_5"],
            summary="Fifth step"
        )
        
        step_context.add_step(step3)
        step_context.add_step(step1)
        step_context.add_step(step5)
        
        current_step = step_context.get_current_step_number()
        
        assert current_step == 5  # Должно вернуть максимальный номер шага
    
    def test_steps_list_maintains_order(self):
        """Тест, что список шагов сохраняет порядок добавления."""
        step_context = StepContext()
        
        step1 = AgentStep(
            step_number=1,
            capability_name="test_capability_1",
            skill_name="test_skill_1",
            action_item_id="action_1",
            observation_item_ids=["obs_1"],
            summary="First step"
        )
        
        step2 = AgentStep(
            step_number=2,
            capability_name="test_capability_2",
            skill_name="test_skill_2",
            action_item_id="action_2",
            observation_item_ids=["obs_2"],
            summary="Second step"
        )
        
        step_context.add_step(step1)
        step_context.add_step(step2)
        
        # Проверяем, что шаги находятся в том же порядке, в котором были добавлены
        assert step_context.steps[0] == step1
        assert step_context.steps[1] == step2
        assert len(step_context.steps) == 2