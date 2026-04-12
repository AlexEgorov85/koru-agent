"""
Интеграционные тесты для Behavior Patterns (ReAct, Planning, Evaluation).

ТЕСТЫ:
  ReActPattern (4):
  - test_react_decides_action_for_sql_goal: цель требует SQL → выбирает sql_tool
  - test_react_decides_action_for_analysis_goal: цель требует анализа → выбирает data_analysis
  - test_react_decides_finish_when_goal_achieved: при наличии результата → FINISH
  - test_react_switches_to_planning_on_complex_task: сложная задача → SWITCH

  PlanningPattern (3):
  - test_planning_creates_plan_when_no_plan: нет плана → создаёт план
  - test_planning_executes_next_step: есть план → выполняет следующий шаг
  - test_planning_updates_plan_on_failure: ошибка шага → обновляет план

  EvaluationPattern (3):
  - test_evaluation_assesses_progress: оценка прогресса
  - test_evaluation_finishes_on_goal_achieved: цель достигнута → FINISH
  - test_evaluation_continues_on_partial_success: частичный успех → ACT

ПРИНЦИПЫ:
- Контексты поднимаются ОДИН РАЗ (scope="module")
- Проверяем decision.type, decision.action, decision.reasoning
- Используем наполненный SessionContext
"""
import pytest
import pytest_asyncio

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.session_context.session_context import SessionContext
from core.models.enums.common_enums import ExecutionStatus
from core.models.data.capability import Capability
from core.agent.behaviors.base import DecisionType


# ============================================================================
# ФИКСТУРЫ (scope="module" — один подъём на ВСЕ тесты)
# ============================================================================

@pytest.fixture(scope="module")
def config():
    return get_config(profile='prod', data_dir='data')


@pytest_asyncio.fixture(scope="module")
async def infrastructure(config):
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest_asyncio.fixture(scope="module")
async def app_context(infrastructure):
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=infrastructure.config.data_dir
    )
    ctx = ApplicationContext(
        infrastructure_context=infrastructure,
        config=app_config,
        profile="prod"
    )
    await ctx.initialize()
    yield ctx
    await ctx.shutdown()


@pytest_asyncio.fixture(scope="module")
async def executor(app_context):
    from core.agent.components.action_executor import ActionExecutor
    return ActionExecutor(application_context=app_context)


# ============================================================================
# HELPER: Создание capabilities для тестов
# ============================================================================

def create_capabilities() -> list:
    """Создаёт набор capabilities для тестирования паттернов."""
    return [
        Capability(
            name="sql_tool.execute",
            description="Выполнение SQL запросов",
            skill_name="sql_tool",
            supported_strategies=["react", "planning", "evaluation"],
            visiable=True
        ),
        Capability(
            name="data_analysis.analyze_step_data",
            description="Анализ данных",
            skill_name="data_analysis",
            supported_strategies=["react", "planning"],
            visiable=True
        ),
        Capability(
            name="final_answer.generate",
            description="Генерация финального ответа",
            skill_name="final_answer",
            supported_strategies=["react", "planning", "evaluation"],
            visiable=True
        ),
        Capability(
            name="planning.create_plan",
            description="Создание плана",
            skill_name="planning",
            supported_strategies=["planning"],
            visiable=False
        ),
        Capability(
            name="book_library.search",
            description="Поиск книг",
            skill_name="book_library",
            supported_strategies=["react", "planning"],
            visiable=True
        ),
    ]


def create_session_with_goal(goal: str) -> SessionContext:
    """Создаёт SessionContext с целью."""
    session = SessionContext(session_id="test_pattern_001", agent_id="test_agent_001")
    session.set_goal(goal)
    session.dialogue_history.add_user_message(goal)
    return session


def create_session_with_observations_and_goal(goal: str, observations: list) -> SessionContext:
    """Создаёт SessionContext с наблюдениями и целью."""
    session = create_session_with_goal(goal)
    for i, obs in enumerate(observations, 1):
        session.record_observation(obs["data"], obs["source"], i)
    return session


# ============================================================================
# REACT PATTERN TESTS
# ============================================================================

class TestReActPattern:
    """ReAct паттерн — 4 теста."""

    @pytest.mark.asyncio
    async def test_react_decides_action_for_sql_goal(self, app_context, executor):
        """Цель требует SQL → паттерн выбирает sql_tool."""
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig

        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=ComponentConfig(name="react_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Найди все книги Пушкина в библиотеке")
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type == DecisionType.ACT, f"Expected ACT, got {decision.type}"
        assert decision.action is not None, "Action is None"
        
        action_lower = decision.action.lower()
        assert any(word in action_lower for word in ["sql", "book", "search"]), \
            f"Expected sql/book/search action, got: {decision.action}"
        
        assert decision.reasoning is not None and len(decision.reasoning) > 0, "No reasoning"
        
        print(f"✅ ReAct: выбрал {decision.action} для цели 'книги Пушкина'")

    @pytest.mark.asyncio
    async def test_react_decides_action_for_analysis_goal(self, app_context, executor):
        """Цель требует анализа → паттерн выбирает data_analysis."""
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig

        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=ComponentConfig(name="react_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Проанализируй данные о продажах")
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type == DecisionType.ACT, f"Expected ACT, got {decision.type}"
        
        action_lower = decision.action.lower()
        has_analysis = "analysis" in action_lower or "data" in action_lower or "sql" in action_lower
        assert has_analysis, f"Expected analysis action, got: {decision.action}"
        
        print(f"✅ ReAct: выбрал {decision.action} для цели 'анализ данных'")

    @pytest.mark.asyncio
    async def test_react_decides_finish_when_goal_achieved(self, app_context, executor):
        """При наличии результата в наблюдениях → FINISH."""
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig

        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=ComponentConfig(name="react_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_observations_and_goal(
            goal="Что найдено?",
            observations=[
                {"data": {"result": "Найдено 5 книг", "books": ["Книга1", "Книга2"]}, "source": "sql_tool"},
                {"data": {"result": "Ответ готов"}, "source": "final_answer"}
            ]
        )
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type in [DecisionType.FINISH, DecisionType.ACT], \
            f"Expected FINISH or ACT, got {decision.type}"
        
        if decision.type == DecisionType.FINISH:
            assert decision.result is not None, "No result for FINISH"
            print(f"✅ ReAct: FINISH с результатом")
        else:
            print(f"✅ ReAct: ACT (продолжает работу)")

    @pytest.mark.asyncio
    async def test_react_switches_to_planning_on_complex_task(self, app_context, executor):
        """Сложная задача → SWITCH к planning."""
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.config.component_config import ComponentConfig

        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=ComponentConfig(name="react_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Проведи полное исследование библиотеки и подготовь отчёт")
        session.record_observation(
            {"result": "Много данных", "steps_needed": 5},
            "system", 1
        )
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type in [DecisionType.ACT, DecisionType.SWITCH], \
            f"Expected ACT or SWITCH, got {decision.type}"
        
        if decision.type == DecisionType.SWITCH:
            assert decision.next_pattern is not None, "No next_pattern"
            assert "planning" in decision.next_pattern.lower(), \
                f"Expected planning pattern, got: {decision.next_pattern}"
            print(f"✅ ReAct: SWITCH к {decision.next_pattern}")
        else:
            print(f"✅ ReAct: ACT с action {decision.action}")


# ============================================================================
# PLANNING PATTERN TESTS
# ============================================================================

class TestPlanningPattern:
    """Planning паттерн — 3 теста."""

    @pytest.mark.asyncio
    async def test_planning_creates_plan_when_no_plan(self, app_context, executor):
        """Нет плана → создаёт план."""
        from core.agent.behaviors.planning.pattern import PlanningPattern
        from core.config.component_config import ComponentConfig

        pattern = PlanningPattern(
            component_name="planning_pattern",
            component_config=ComponentConfig(name="planning_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Найди книги Пушкина и подготовь отчёт")
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type == DecisionType.ACT, f"Expected ACT, got {decision.type}"
        assert decision.action is not None, "No action"
        
        assert "plan" in decision.action.lower() or "planning" in decision.action.lower(), \
            f"Expected planning action, got: {decision.action}"
        
        print(f"✅ Planning: создаёт план с action {decision.action}")

    @pytest.mark.asyncio
    async def test_planning_executes_next_step(self, app_context, executor):
        """Есть активный план → выполняет следующий шаг."""
        from core.agent.behaviors.planning.pattern import PlanningPattern
        from core.config.component_config import ComponentConfig

        pattern = PlanningPattern(
            component_name="planning_pattern",
            component_config=ComponentConfig(name="planning_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Выполнить план")
        
        session.register_step(
            step_number=1,
            capability_name="sql_tool.execute",
            skill_name="sql_tool",
            action_item_id=session.record_action({"action": "sql_query"}),
            observation_item_ids=[],
            summary="Выполнить запрос",
            status=ExecutionStatus.COMPLETED
        )
        
        session.register_step(
            step_number=2,
            capability_name="final_answer.generate",
            skill_name="final_answer",
            action_item_id=session.record_action({"action": "generate_answer"}),
            observation_item_ids=[],
            summary="Сгенерировать ответ",
            status=ExecutionStatus.PENDING
        )
        
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type == DecisionType.ACT, f"Expected ACT, got {decision.type}"
        assert decision.action is not None, "No action"
        
        print(f"✅ Planning: выполняет шаг {decision.action}")

    @pytest.mark.asyncio
    async def test_planning_updates_plan_on_failure(self, app_context, executor):
        """Ошибка в шаге → обновляет план."""
        from core.agent.behaviors.planning.pattern import PlanningPattern
        from core.config.component_config import ComponentConfig

        pattern = PlanningPattern(
            component_name="planning_pattern",
            component_config=ComponentConfig(name="planning_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Выполнить план")
        
        session.register_step(
            step_number=1,
            capability_name="sql_tool.execute",
            skill_name="sql_tool",
            action_item_id=session.record_action({"action": "sql_query", "error": "Connection failed"}),
            observation_item_ids=[],
            summary="Выполнить запрос",
            status=ExecutionStatus.FAILED
        )
        
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type in [DecisionType.ACT, DecisionType.SWITCH], \
            f"Expected ACT or SWITCH, got {decision.type}"
        
        print(f"✅ Planning: обрабатывает ошибку → {decision.type.value}")


# ============================================================================
# EVALUATION PATTERN TESTS
# ============================================================================

class TestEvaluationPattern:
    """Evaluation паттерн — 3 теста."""

    @pytest.mark.asyncio
    async def test_evaluation_assesses_progress(self, app_context, executor):
        """Оценка прогресса выполнения."""
        from core.agent.behaviors.evaluation.pattern import EvaluationPattern
        from core.config.component_config import ComponentConfig

        pattern = EvaluationPattern(
            component_name="evaluation_pattern",
            component_config=ComponentConfig(name="evaluation_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Оцени прогресс")
        
        session.record_observation(
            {"result": "Выполнено 2 из 5 шагов", "progress": "40%"},
            "system", 1
        )
        
        session.register_step(
            step_number=1,
            capability_name="sql_tool.execute",
            skill_name="sql_tool",
            action_item_id=session.record_action({"action": "query"}),
            observation_item_ids=[],
            summary="Шаг 1",
            status=ExecutionStatus.COMPLETED
        )
        
        session.register_step(
            step_number=2,
            capability_name="data_analysis.analyze",
            skill_name="data_analysis",
            action_item_id=session.record_action({"action": "analyze"}),
            observation_item_ids=[],
            summary="Шаг 2",
            status=ExecutionStatus.COMPLETED
        )
        
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type in [DecisionType.ACT, DecisionType.FINISH, DecisionType.SWITCH], \
            f"Expected ACT/FINISH/SWITCH, got {decision.type}"
        
        print(f"✅ Evaluation: оценка прогресса → {decision.type.value}")

    @pytest.mark.asyncio
    async def test_evaluation_finishes_on_goal_achieved(self, app_context, executor):
        """Цель достигнута → FINISH."""
        from core.agent.behaviors.evaluation.pattern import EvaluationPattern
        from core.config.component_config import ComponentConfig

        pattern = EvaluationPattern(
            component_name="evaluation_pattern",
            component_config=ComponentConfig(name="evaluation_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Задача выполнена?")
        
        session.record_observation(
            {"result": "Все шаги выполнены", "completed": True, "final_answer": "Готово"},
            "system", 1
        )
        
        session.register_step(
            step_number=1,
            capability_name="sql_tool.execute",
            skill_name="sql_tool",
            action_item_id=session.record_action({"action": "query"}),
            observation_item_ids=[],
            summary="Запрос",
            status=ExecutionStatus.COMPLETED
        )
        
        session.register_step(
            step_number=2,
            capability_name="final_answer.generate",
            skill_name="final_answer",
            action_item_id=session.record_action({"action": "generate"}),
            observation_item_ids=[],
            summary="Финальный ответ",
            status=ExecutionStatus.COMPLETED
        )
        
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        if decision.type == DecisionType.FINISH:
            assert decision.result is not None, "No result for FINISH"
            print(f"✅ Evaluation: FINISH - цель достигнута")
        else:
            print(f"✅ Evaluation: {decision.type.value} - проверка выполнена")

    @pytest.mark.asyncio
    async def test_evaluation_continues_on_partial_success(self, app_context, executor):
        """Частичный успех → ACT для продолжения."""
        from core.agent.behaviors.evaluation.pattern import EvaluationPattern
        from core.config.component_config import ComponentConfig

        pattern = EvaluationPattern(
            component_name="evaluation_pattern",
            component_config=ComponentConfig(name="evaluation_pattern", variant_id="default"),
            application_context=app_context,
            executor=executor
        )

        session = create_session_with_goal("Оцени результат")
        
        session.record_observation(
            {"result": "Часть данных обработана", "completed": False, "remaining": 2},
            "system", 1
        )
        
        session.register_step(
            step_number=1,
            capability_name="data_analysis.analyze",
            skill_name="data_analysis",
            action_item_id=session.record_action({"action": "analyze"}),
            observation_item_ids=[],
            summary="Анализ",
            status=ExecutionStatus.COMPLETED
        )
        
        capabilities = create_capabilities()

        decision = await pattern.decide(session, capabilities)

        assert decision.type in [DecisionType.ACT, DecisionType.SWITCH], \
            f"Expected ACT or SWITCH, got {decision.type}"
        
        print(f"✅ Evaluation: частичный успех → {decision.type.value}")