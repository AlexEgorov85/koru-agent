"""
Тесты для ReAct паттерна мышления.
"""
import pytest
from unittest.mock import Mock
from application.agent.thinking_patterns.react_pattern import ReActPattern
from domain.models.agent.agent_state import AgentState
from domain.models.react_state import ReActState, ActionType


@pytest.fixture
def mock_llm_provider():
    """Создает mock LLM провайдер"""
    provider = Mock()
    provider.generate_response.return_value = '{"action": "TEST_ACTION", "thought": "Test thought"}'
    return provider


@pytest.fixture
def mock_prompt_renderer():
    """Создает mock рендерера промтов"""
    renderer = Mock()
    renderer.render.return_value = "Тестовый промт для ReAct"
    return renderer


@pytest.fixture
def react_thinking_pattern(mock_llm_provider, mock_prompt_renderer):
    """Создает экземпляр ReAct паттерна мышления с моками"""
    return ReActPattern(
        llm_provider=mock_llm_provider,
        prompt_renderer=mock_prompt_renderer,
        max_iterations=5
    )


class TestReActThinkingPattern:
    """Тесты для ReAct паттерна мышления"""

    def test_react_pattern_initialization(self, react_thinking_pattern):
        """Тест: инициализация ReAct паттерна мышления с параметрами"""
        assert react_thinking_pattern.name == "react"
        assert react_thinking_pattern.max_iterations == 5
        assert react_thinking_pattern.current_state is None

    @pytest.mark.asyncio
    async def test_react_pattern_execute_with_llm(self, react_thinking_pattern, mock_llm_provider):
        """Тест: выполнение ReAct паттерна мышления с LLM"""
        # Подготовим контекст для выполнения
        state = AgentState()
        class Context:
            goal = "Тестовая задача"
        context = Context()
        available_capabilities = ["test_capability"]

        result = await react_thinking_pattern.execute(state, context, available_capabilities)

        # Проверяем, что был вызван LLM
        mock_llm_provider.generate_response.assert_called()
        assert "action" in result
        assert "thought" in result
        assert react_thinking_pattern.current_state is not None
        assert react_thinking_pattern.current_state.goal == "Тестовая задача"

    @pytest.mark.asyncio
    async def test_react_pattern_execute_without_llm(self):
        """Тест: выполнение ReAct паттерна мышления без LLM (запасная логика)"""
        pattern = ReActPattern(max_iterations=5)

        # Подготовим контекст для выполнения
        state = AgentState()
        class Context:
            goal = "Тестовая задача"
        context = Context()
        available_capabilities = ["test_capability"]

        result = await pattern.execute(state, context, available_capabilities)

        assert "action" in result
        assert "thought" in result
        assert "Нет доступа к LLM" in result["thought"]

    @pytest.mark.asyncio
    async def test_adapt_to_task(self, react_thinking_pattern):
        """Тест: адаптация паттерна к задаче"""
        task_description = "Анализировать код на Python"

        result = await react_thinking_pattern.adapt_to_task(task_description)

        assert result["domain"] == "code_analysis"
        assert result["confidence"] == 0.9
        assert "parameters" in result
        assert result["parameters"]["max_iterations"] == 5

    @pytest.mark.asyncio
    async def test_process_observation(self, react_thinking_pattern):
        """Тест: обработка наблюдения"""
        # Подготовим контекст для выполнения
        state = AgentState()
        class Context:
            goal = "Тестовая задача"
        context = Context()
        available_capabilities = ["test_capability"]

        # Сначала выполним один шаг, чтобы создать состояние
        await react_thinking_pattern.execute(state, context, available_capabilities)

        # Теперь обработаем наблюдение
        observation = {"result": "Тестовый результат выполнения действия"}
        result = react_thinking_pattern.process_observation(observation, context)

        assert result is not None
        assert "thought" in result
        assert "continue" in result
        assert "Тестовый результат" in result["thought"]

        # Проверим, что наблюдение добавилось в состояние
        current_state = react_thinking_pattern.get_state()
        assert len(current_state.steps) > 1  # Должно быть больше одного шага
        assert any(step.action_type == ActionType.OBSERVATION for step in current_state.steps)

    @pytest.mark.asyncio
    async def test_get_and_restore_state(self, react_thinking_pattern):
        """Тест: получение и восстановление состояния"""
        # Подготовим контекст для выполнения
        state = AgentState()
        class Context:
            goal = "Тестовая задача"
        context = Context()
        available_capabilities = ["test_capability"]

        # Выполним несколько шагов
        await react_thinking_pattern.execute(state, context, available_capabilities)
        await react_thinking_pattern.execute(state, context, available_capabilities)

        # Получим текущее состояние
        current_state = react_thinking_pattern.get_state()
        assert current_state is not None
        assert len(current_state.steps) >= 2

        # Создадим новое состояние для восстановления
        new_state = ReActState(
            goal="Новая цель",
            steps=[]
        )

        # Восстановим состояние
        success = react_thinking_pattern.restore_state(new_state)
        assert success is True

        # Проверим, что состояние изменилось
        restored_state = react_thinking_pattern.get_state()
        assert restored_state.goal == "Новая цель"
        assert len(restored_state.steps) == 0

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self, react_thinking_pattern):
        """Тест: ограничение по максимальному количеству итераций"""
        # Подготовим контекст для выполнения
        state = AgentState()
        class Context:
            goal = "Тестовая задача"
        context = Context()
        available_capabilities = ["test_capability"]

        # Выполняем больше итераций, чем разрешено
        for i in range(react_thinking_pattern.max_iterations + 1):
            result = await react_thinking_pattern.execute(state, context, available_capabilities)
            if result["action"] == "STOP":
                assert "максимальное количество итераций" in result["thought"]
                break

    @pytest.mark.asyncio
    async def test_recovery_manager_integration(self, react_thinking_pattern):
        """Тест: интеграция с менеджером восстановления"""
        # Проверяем, что паттерн имеет доступ к менеджеру восстановления
        assert hasattr(react_thinking_pattern, 'recovery_manager')
        assert react_thinking_pattern.recovery_manager is not None
        
        # Проверяем, что используется общий PatternRecoveryManager, а не специализированный
        from application.agent.recovery.pattern_recovery_manager import PatternRecoveryManager
        assert isinstance(react_thinking_pattern.recovery_manager, PatternRecoveryManager)
    
    @pytest.mark.asyncio
    async def test_atomic_actions_integration(self, react_thinking_pattern):
        """Тест: интеграция с атомарными действиями"""
        # Проверяем, что паттерн использует атомарные действия
        assert hasattr(react_thinking_pattern, 'think_action')
        assert hasattr(react_thinking_pattern, 'act_action')
        assert hasattr(react_thinking_pattern, 'observe_action')
        assert react_thinking_pattern.think_action is not None
        assert react_thinking_pattern.act_action is not None
        assert react_thinking_pattern.observe_action is not None
        
        # Проверяем, что атомарные действия получили LLM провайдер и рендерер промтов
        assert react_thinking_pattern.think_action.llm_provider is not None
        assert react_thinking_pattern.think_action.prompt_renderer is not None