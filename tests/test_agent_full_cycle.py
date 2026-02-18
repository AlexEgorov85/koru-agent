"""
Тесты для полного цикла работы агента с новой архитектурой.

ПРИМЕЧАНИЕ: Тесты используют реальные объекты вместо моков для ApplicationContext и компонентов.
Моки допускаются только для LLM и БД провайдеров.
"""
import pytest
from core.application.agent.components.policy import AgentPolicy
from core.application.agent.components.state import AgentState
from core.application.agent.components.progress import ProgressScorer
from core.application.agent.components.action_executor import ActionExecutor
from core.application.agent.components.behavior_manager import BehaviorManager


class TestAgentState:
    """Тесты компонента AgentState."""

    def test_agent_state_initialization(self):
        """Тест инициализации состояния агента."""
        state = AgentState()

        assert state.step == 0
        assert state.error_count == 0
        assert state.consecutive_errors == 0
        assert state.no_progress_steps == 0
        assert state.finished is False
        assert state.history == []

    def test_agent_state_register_error(self):
        """Тест регистрации ошибки."""
        state = AgentState()

        state.register_error()

        assert state.error_count == 1
        assert state.consecutive_errors == 1

    def test_agent_state_register_multiple_errors(self):
        """Тест регистрации нескольких ошибок."""
        state = AgentState()

        state.register_error()
        state.register_error()
        state.register_error()

        assert state.error_count == 3
        assert state.consecutive_errors == 3

    def test_agent_state_reset_consecutive_errors(self):
        """Тест сброса последовательных ошибок."""
        state = AgentState()

        state.register_error()
        state.register_error()
        state.reset_consecutive_errors()

        assert state.error_count == 2
        assert state.consecutive_errors == 0

    def test_agent_state_register_progress(self):
        """Тест регистрации прогресса."""
        state = AgentState()

        state.register_progress(progressed=True)

        assert state.no_progress_steps == 0

    def test_agent_state_register_no_progress(self):
        """Тест регистрации отсутствия прогресса."""
        state = AgentState()

        state.register_progress(progressed=False)

        assert state.no_progress_steps == 1

    def test_agent_state_register_multiple_no_progress(self):
        """Тест регистрации нескольких шагов без прогресса."""
        state = AgentState()

        state.register_progress(progressed=False)
        state.register_progress(progressed=False)
        state.register_progress(progressed=False)

        assert state.no_progress_steps == 3


class TestAgentPolicy:
    """Тесты компонента AgentPolicy."""

    def test_agent_policy_default_values(self):
        """Тест значений политики по умолчанию."""
        policy = AgentPolicy()

        assert policy.max_errors == 2
        assert policy.max_no_progress_steps == 3

    def test_agent_policy_custom_values(self):
        """Тест custom значений политики."""
        policy = AgentPolicy(max_errors=5, max_no_progress_steps=10)

        assert policy.max_errors == 5
        assert policy.max_no_progress_steps == 10

    def test_agent_policy_should_fallback(self):
        """Тест проверки необходимости fallback."""
        policy = AgentPolicy(max_errors=2)
        state = AgentState()

        # Пока ошибок меньше порога
        assert policy.should_fallback(state) is False

        # Достигаем порога
        state.register_error()
        state.register_error()
        assert policy.should_fallback(state) is True

    def test_agent_policy_should_stop_no_progress(self):
        """Тест проверки остановки при отсутствии прогресса."""
        policy = AgentPolicy(max_no_progress_steps=3)
        state = AgentState()

        # Пока нет прогресса меньше порога
        assert policy.should_stop_no_progress(state) is False

        # Достигаем порога
        for _ in range(3):
            state.register_progress(progressed=False)
        assert policy.should_stop_no_progress(state) is True


class TestProgressScorer:
    """Тесты компонента ProgressScorer."""

    def test_progress_scorer_initialization(self):
        """Тест инициализации оценщика прогресса."""
        scorer = ProgressScorer()

        assert scorer.last_summary is None

    def test_progress_scorer_evaluate_no_progress(self):
        """Тест оценки без прогресса."""
        scorer = ProgressScorer()

        # Создаем mock сессии с одинаковым summary
        class MockSession:
            def get_summary(self):
                return "same summary"

        session = MockSession()

        # Первая оценка
        result1 = scorer.evaluate(session)
        assert result1 is True  # Первый вызов всегда True
        assert scorer.last_summary == "same summary"

        # Вторая оценка (без изменений)
        result2 = scorer.evaluate(session)
        assert result2 is False

    def test_progress_scorer_evaluate_with_progress(self):
        """Тест оценки с прогрессом."""
        scorer = ProgressScorer()

        class MockSession:
            def __init__(self, summaries):
                self.summaries = summaries
                self.index = 0

            def get_summary(self):
                result = self.summaries[self.index]
                self.index += 1
                return result

        session = MockSession(["summary 1", "summary 2", "summary 3"])

        # Первая оценка
        assert scorer.evaluate(session) is True

        # Вторая оценка (изменился summary)
        assert scorer.evaluate(session) is True

        # Третья оценка (изменился summary)
        assert scorer.evaluate(session) is True


class TestActionExecutor:
    """Тесты компонента ActionExecutor."""

    def test_action_executor_initialization(self):
        """Тест инициализации ActionExecutor."""
        # Создаем минимальный mock ApplicationContext
        class MockApplicationContext:
            def get_service(self, name):
                return None

            def get_tool(self, name):
                return None

            def get_skill(self, name):
                return None

        app_ctx = MockApplicationContext()
        executor = ActionExecutor(app_ctx)

        assert executor.application_context is app_ctx


class TestBehaviorManagerStructure:
    """Тесты структуры BehaviorManager."""

    def test_behavior_manager_initialization(self):
        """Тест инициализации BehaviorManager."""
        # Создаем минимальный mock ApplicationContext
        class MockApplicationContext:
            def get_service(self, name):
                return None

        app_ctx = MockApplicationContext()
        manager = BehaviorManager(app_ctx)

        assert manager._app_ctx is app_ctx
        assert manager._current_pattern is None
        assert manager._pattern_history == []
        assert manager._behavior_storage is None

    def test_behavior_manager_get_current_pattern_id_none(self):
        """Тест получения ID паттерна когда паттерн не установлен."""
        class MockApplicationContext:
            def get_service(self, name):
                return None

        app_ctx = MockApplicationContext()
        manager = BehaviorManager(app_ctx)

        assert manager.get_current_pattern_id() is None

    def test_behavior_manager_get_pattern_history_empty(self):
        """Тест получения истории паттернов когда она пуста."""
        class MockApplicationContext:
            def get_service(self, name):
                return None

        app_ctx = MockApplicationContext()
        manager = BehaviorManager(app_ctx)

        history = manager.get_pattern_history()
        assert history == []


class TestAgentRuntimeComponents:
    """Тесты компонентов AgentRuntime."""

    def test_agent_policy_integration_with_state(self):
        """Тест интеграции политики с состоянием."""
        policy = AgentPolicy(max_errors=2, max_no_progress_steps=3)
        state = AgentState()

        # Симуляция цикла выполнения с ошибками
        for _ in range(2):
            state.register_error()

        # Политика должна требовать fallback
        assert policy.should_fallback(state) is True

    def test_progress_tracking_integration(self):
        """Тест интеграции отслеживания прогресса."""
        scorer = ProgressScorer()
        state = AgentState()
        policy = AgentPolicy(max_no_progress_steps=2)

        class MockSession:
            def __init__(self):
                self.summary = "initial"
                self.first_call = True

            def get_summary(self):
                # Первый вызов возвращает "initial", последующие тоже
                # ProgressScorer сравнивает с last_summary который изначально None
                # Поэтому первый вызов всегда возвращает True (прогресс есть)
                # А последующие вызовы с тем же summary возвращают False
                if self.first_call:
                    self.first_call = False
                    return "initial"  # Первый вызов: last_summary=None, вернёт True
                return "initial"  # Последующие: last_summary="initial", вернёт False

        session = MockSession()

        # Первый шаг — всегда есть прогресс (last_summary=None)
        has_progress = scorer.evaluate(session)
        state.register_progress(progressed=has_progress)
        # has_progress=True, no_progress_steps=0

        # Второй шаг — нет прогресса (summary не изменился)
        has_progress = scorer.evaluate(session)
        state.register_progress(progressed=has_progress)
        # has_progress=False, no_progress_steps=1

        # Третий шаг — нет прогресса
        has_progress = scorer.evaluate(session)
        state.register_progress(progressed=has_progress)
        # has_progress=False, no_progress_steps=2

        # Должно сработать условие остановки
        assert policy.should_stop_no_progress(state) is True
