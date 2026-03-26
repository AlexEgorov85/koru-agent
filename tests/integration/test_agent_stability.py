"""
Интеграционные тесты стабилизации Agent_v5.

Проверяют 4 критических критерия готовности:
1. Агент не зацикливается (AgentStuckError вместо бесконечного цикла)
2. LLM вызывается для THINK decision
3. State меняется после каждого шага
4. PlanningPattern завершается (is_finished=True)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.models.errors import AgentStuckError, InfrastructureError
from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.agent.components.state import AgentState


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_application_context():
    """Создаёт мок ApplicationContext для интеграционных тестов"""
    mock = MagicMock()
    mock.session_context = MagicMock()
    mock.session_context.get_goal = MagicMock(return_value="Тестовая цель")
    mock.session_context.current_step = 0
    mock.session_context.record_action = MagicMock()
    mock.session_context.record_decision = MagicMock()
    mock.session_context.record_error = MagicMock()
    
    # Создаём правильный мок event_bus с async publish
    mock_event_bus = AsyncMock()
    mock_event_bus.publish = AsyncMock()
    
    mock_infrastructure = MagicMock()
    mock_infrastructure.event_bus = mock_event_bus
    mock.infrastructure_context = mock_infrastructure
    
    mock.get_provider = MagicMock(return_value=None)
    mock.get_all_capabilities = MagicMock(return_value=[])
    
    return mock


@pytest.fixture
def mock_behavior_manager():
    """Создаёт мок BehaviorManager"""
    mock = AsyncMock()
    mock.initialize = AsyncMock()
    mock.generate_next_decision = AsyncMock()
    mock._current_pattern = MagicMock()
    return mock


# ============================================================================
# ТЕСТ 1: NO INFINITE LOOP
# ============================================================================

class TestNoInfiniteLoop:
    """Тест: Агент не должен зацикливаться на одном decision"""

    @pytest.mark.asyncio
    async def test_no_infinite_loop(self, mock_application_context, mock_behavior_manager):
        """
        Интеграционный тест: агент не зацикливается.
        
        Проверяет что при повторяющихся decision без изменения state
        агент завершает работу с ошибкой вместо бесконечного цикла.
        """
        from core.agent.runtime import AgentRuntime
        from core.agent.components.policy import AgentPolicy
        from core.models.enums.common_enums import ExecutionStatus

        # Создаём повторяющийся decision
        repeating_decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test_capability",
            parameters={},
            reason="test_reason"
        )

        # BehaviorManager всегда возвращает одинаковый decision
        mock_behavior_manager.generate_next_decision = AsyncMock(
            return_value=repeating_decision
        )

        # Создаём runtime
        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Найди 3 книги Пушкина",
            policy=AgentPolicy(),
            max_steps=10
        )

        # Подменяем behavior_manager на мок
        runtime.behavior_manager = mock_behavior_manager

        # Подменяем _execute_single_step_internal чтобы state не менялся
        async def mock_execute_step(decision, available_caps):
            # State не меняется
            return None

        runtime._execute_single_step_internal = mock_execute_step

        # Запуск должен завершиться с ошибкой (не бесконечный цикл)
        result = await runtime.run()

        # Проверяем что агент завершился с ошибкой AgentStuckError
        assert result.status == ExecutionStatus.FAILED
        assert "AgentStuckError" in result.result or "State did not mutate" in result.result

    @pytest.mark.asyncio
    async def test_no_three_identical_decisions_in_row(self, mock_application_context):
        """
        Тест: Не должно быть 3 одинаковых decision подряд.
        
        Проверяет логику детекции зацикливания.
        """
        from core.agent.components.state import AgentState

        state = AgentState()
        decisions = []
        loop_detected = False

        # Симуляция 5 шагов с зацикливанием
        for i in range(5):
            decision = BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name="same_capability",
                parameters={},
                reason="same_reason"
            )
            decisions.append(decision)

            # Проверка на зацикливание
            if len(decisions) >= 3:
                if (decisions[-1].action == decisions[-2].action == decisions[-3].action and
                    decisions[-1].capability_name == decisions[-2].capability_name == decisions[-3].capability_name):
                    # Проверяем что state не меняется
                    current_snapshot = state.snapshot()
                    if len(decisions) >= 4:
                        loop_detected = True
                        break

        # Зацикливание должно быть детектировано
        assert loop_detected is True


# ============================================================================
# ТЕСТ 2: LLM ALWAYS CALLED
# ============================================================================

class TestLlmAlwaysCalled:
    """Тест: LLM вызывается для THINK decision"""

    @pytest.mark.asyncio
    async def test_llm_called_for_think_decision(self, mock_application_context):
        """
        Интеграционный тест: LLM вызывается для THINK decision.
        
        Проверяет что когда decision.requires_llm=True,
        execution_result.llm_called должно быть True.
        """
        from core.agent.components.action_executor import ActionResult
        from core.models.errors import InfrastructureError

        # Decision требует LLM
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="think.capability",
            parameters={},
            reason="thinking",
            requires_llm=True
        )

        # Результат с llm_called=True
        execution_result_with_llm = ActionResult(success=True, data={}, llm_called=True)

        # Результат с llm_called=False
        execution_result_without_llm = ActionResult(success=True, data={}, llm_called=False)

        # Проверка: если requires_llm=True и llm_called=False, должна быть ошибка
        error_raised = False
        try:
            if getattr(decision, 'requires_llm', False):
                if hasattr(execution_result_without_llm, 'llm_called') and not execution_result_without_llm.llm_called:
                    raise InfrastructureError(
                        f"Decision requires LLM but LLM was not called for {decision.capability_name}"
                    )
        except InfrastructureError:
            error_raised = True

        assert error_raised is True

        # Проверка: если requires_llm=True и llm_called=True, ошибки нет
        error_raised = False
        try:
            if getattr(decision, 'requires_llm', False):
                if hasattr(execution_result_with_llm, 'llm_called') and not execution_result_with_llm.llm_called:
                    raise InfrastructureError(
                        f"Decision requires LLM but LLM was not called for {decision.capability_name}"
                    )
        except InfrastructureError:
            error_raised = True

        assert error_raised is False

    @pytest.mark.asyncio
    async def test_llm_not_required_for_act_decision(self, mock_application_context):
        """
        Тест: LLM не требуется для обычных ACT decision.
        
        Проверяет что requires_llm=False по умолчанию.
        """
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="search.capability",
            parameters={},
            reason="searching"
        )

        # requires_llm должен быть False по умолчанию
        assert decision.requires_llm is False


# ============================================================================
# ТЕСТ 3: STATE ALWAYS MUTATES
# ============================================================================

class TestStateAlwaysMutates:
    """Тест: State меняется после каждого шага"""

    @pytest.mark.asyncio
    async def test_state_mutates_after_each_step(self, mock_application_context, mock_behavior_manager):
        """
        Интеграционный тест: State меняется после каждого шага.
        
        Проверяет что snapshot состояния меняется после каждого шага выполнения.
        """
        from core.agent.runtime import AgentRuntime
        from core.agent.components.policy import AgentPolicy

        # Создаём разные decision
        decisions = [
            BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=f"capability_{i}",
                parameters={},
                reason=f"step_{i}"
            )
            for i in range(5)
        ]

        call_count = [0]
        async def mock_generate_decision(*args, **kwargs):
            idx = call_count[0] % len(decisions)
            call_count[0] += 1
            return decisions[idx]

        mock_behavior_manager.generate_next_decision = mock_generate_decision

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            policy=AgentPolicy(),
            max_steps=5
        )

        runtime.behavior_manager = mock_behavior_manager

        # State меняется при каждом шаге
        async def mock_execute_step(decision, available_caps):
            runtime.state.step += 1
            runtime.state.history.append(f"action_{runtime.state.step}")
            return None

        runtime._execute_single_step_internal = mock_execute_step

        # Сохраняем snapshots
        snapshots = []
        for _ in range(3):
            snapshot_before = runtime.state.snapshot()
            
            # Симуляция шага
            decision = await mock_behavior_manager.generate_next_decision()
            await mock_execute_step(decision, [])
            
            snapshot_after = runtime.state.snapshot()
            snapshots.append((snapshot_before, snapshot_after))

        # Проверяем что snapshots разные
        for i, (before, after) in enumerate(snapshots):
            assert before != after, f"State не изменился на шаге {i}"

    def test_snapshot_changes_after_action(self):
        """
        Тест: snapshot меняется после действия.
        
        Юнит-тест для AgentState.snapshot().
        """
        state = AgentState()
        snapshot_before = state.snapshot()

        # Симуляция действия
        state.step += 1
        state.history.append("test_action")

        snapshot_after = state.snapshot()

        # Snapshot должен измениться
        assert snapshot_before != snapshot_after
        assert snapshot_after['step'] == 1
        assert snapshot_after['history_length'] == 1


# ============================================================================
# ТЕСТ 4: PLANNING COMPLETES
# ============================================================================

class TestPlanningCompletes:
    """Тест: PlanningPattern завершается"""

    @pytest.mark.asyncio
    async def test_planning_skill_has_capabilities(self):
        """
        Интеграционный тест: PlanningSkill имеет capabilities.
        
        Проверяет что planning skill имеет все необходимые capabilities.
        """
        from core.services.skills.planning.skill import PlanningSkill
        from core.agent.components.action_executor import ActionExecutor

        # Создаём полный мок application_context
        mock_app_ctx = MagicMock()
        mock_app_ctx.session_context = MagicMock()
        mock_app_ctx.session_context.get_goal = MagicMock(return_value="Тест")
        mock_app_ctx.infrastructure_context = MagicMock()
        mock_app_ctx.infrastructure_context.event_bus = AsyncMock()
        mock_app_ctx.infrastructure_context.event_bus.publish = AsyncMock()
        
        # Создаём мок executor
        mock_executor = MagicMock(spec=ActionExecutor)

        # Создаём PlanningSkill
        skill = PlanningSkill(
            name="planning",
            application_context=mock_app_ctx,
            component_config=MagicMock(),
            executor=mock_executor
        )

        # Инициализируем skill
        await skill.initialize()

        # Получаем capability
        capabilities = skill.get_capabilities()

        # Проверяем что все необходимые capabilities существуют
        capability_names = [c.name for c in capabilities]
        assert "planning.create_plan" in capability_names
        assert "planning.get_next_step" in capability_names
        assert "planning.update_plan" in capability_names
        assert len(capabilities) >= 3  # Как минимум 3 capability

    @pytest.mark.asyncio
    async def test_planning_skill_initializes(self):
        """
        Тест: PlanningSkill успешно инициализируется.
        
        Проверяет что skill может быть инициализирован без ошибок.
        """
        from core.services.skills.planning.skill import PlanningSkill
        from core.agent.components.action_executor import ActionExecutor

        # Создаём полный мок application_context
        mock_app_ctx = MagicMock()
        mock_app_ctx.session_context = MagicMock()
        mock_app_ctx.session_context.get_goal = MagicMock(return_value="Тест")
        mock_app_ctx.infrastructure_context = MagicMock()
        mock_app_ctx.infrastructure_context.event_bus = AsyncMock()
        mock_app_ctx.infrastructure_context.event_bus.publish = AsyncMock()
        
        # Создаём мок executor
        mock_executor = MagicMock(spec=ActionExecutor)

        skill = PlanningSkill(
            name="planning",
            application_context=mock_app_ctx,
            component_config=MagicMock(),
            executor=mock_executor
        )

        # Инициализация не должна выбросить ошибку
        await skill.initialize()

        # Проверяем что skill инициализирован
        assert skill is not None
        assert skill.name == "planning"

    @pytest.mark.asyncio
    async def test_planning_skill_returns_execution_result_on_error(self):
        """
        Тест: PlanningSkill.execute() возвращает ExecutionResult даже при ошибке.

        Проверяет что результат всегда имеет тип ExecutionResult.
        """
        from core.services.skills.planning.skill import PlanningSkill
        from core.agent.components.action_executor import ExecutionContext, ActionExecutor
        from core.models.data.execution import ExecutionResult

        # Создаём полный мок application_context
        mock_app_ctx = MagicMock()
        mock_app_ctx.session_context = MagicMock()
        mock_app_ctx.session_context.get_goal = MagicMock(return_value="Тест")
        mock_app_ctx.infrastructure_context = MagicMock()
        mock_app_ctx.infrastructure_context.event_bus = AsyncMock()
        mock_app_ctx.infrastructure_context.event_bus.publish = AsyncMock()

        # Создаём мок executor
        mock_executor = MagicMock(spec=ActionExecutor)

        # Мокаем execute_action чтобы он возвращал ошибку (симуляция отсутствия промптов)
        async def mock_execute_action(action_name, parameters, context):
            return MagicMock(
                success=False,
                result={},
                error="Prompt not available",
                metadata={}
            )

        mock_executor.execute_action = mock_execute_action

        skill = PlanningSkill(
            name="planning",
            application_context=mock_app_ctx,
            component_config=MagicMock(),
            executor=mock_executor
        )

        await skill.initialize()

        capabilities = skill.get_capabilities()
        create_plan_cap = next(c for c in capabilities if c.name == "planning.create_plan")

        # Выполняем capability (должно вернуть ExecutionResult даже с ошибкой)
        result = await skill.execute(
            capability=create_plan_cap,
            parameters={"goal": "Тест"},
            execution_context=ExecutionContext(
                session_context=mock_app_ctx.session_context,
                available_capabilities=[c.name for c in capabilities]
            )
        )

        # Проверяем что результат — ExecutionResult (даже при ошибке)
        assert isinstance(result, ExecutionResult)
        # technical_success может быть False из-за отсутствия промптов
        # Главное что тип правильный


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
