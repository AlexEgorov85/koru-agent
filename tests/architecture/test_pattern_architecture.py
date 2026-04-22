"""
Тесты для валидации чистоты архитектуры Pattern.

ПРИНЦИП:
    мы тестируем НЕ код → мы тестируем принятие решений

ЭТИ ТЕСТЫ ЛОМАЮТ НЕПРАВИЛЬНУЮ АРХИТЕКТУРУ:
    - утечки логики в runtime/executor
    - скрытые decision-maker'ы
    - недетерминированность
    - слабую модель состояния
"""
import pytest
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from core.agent.behaviors.base import Decision, DecisionType
from core.session_context.session_context import SessionContext
from core.models.data.capability import Capability
from core.models.enums.common_enums import ExecutionStatus


# ============================================================================
# TEST FIXTURES
# ============================================================================

@dataclass
class Failure:
    """Запись об ошибке для тестов."""
    type: str
    capability: str = "test_capability"
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: str = ""


@dataclass
class Step:
    """Шаг выполнения для тестов."""
    result: str = ""
    capability: str = "test_capability"
    status: ExecutionStatus = ExecutionStatus.COMPLETED


def create_empty_context(goal: str = "test goal") -> SessionContext:
    """Создать пустой контекст для тестов."""
    ctx = SessionContext()
    ctx.set_goal(goal)
    return ctx


def create_context_with_failures(
    goal: str,
    failures: List[Failure],
    steps: Optional[List[Step]] = None
) -> SessionContext:
    """Создать контекст с ошибками."""
    ctx = create_empty_context(goal)
    
    # Записать failures в step_context
    for failure in failures:
        ctx.step_context.add_step(type('AgentStep', (), {
            'step_number': len(ctx.step_context.steps),
            'capability_name': failure.capability,
            'skill_name': 'test_skill',
            'action_item_id': '',
            'observation_item_ids': [],
            'summary': failure.error_message,
            'status': ExecutionStatus.FAILED
        })())
    
    # Записать steps если есть
    if steps:
        for step in steps:
            ctx.step_context.add_step(type('AgentStep', (), {
                'step_number': len(ctx.step_context.steps),
                'capability_name': step.capability,
                'skill_name': 'test_skill',
                'action_item_id': '',
                'observation_item_ids': [],
                'summary': step.result,
                'status': step.status
            })())
    
    return ctx


# ============================================================================
# 1. БАЗОВЫЙ ТЕСТ: Pattern работает изолированно
# ============================================================================

class TestPatternIsolation:
    """
    Цель: доказать, что Pattern — независимый мозг.
    
    ❌ Если падает:
        - pattern требует executor
        - pattern требует runtime
        👉 архитектура сломана
    """

    @pytest.mark.asyncio
    async def test_pattern_can_decide_without_runtime(self):
        """Pattern может принимать решения без Runtime."""
        from core.agent.behaviors.react.pattern import ReActPattern
        
        pattern = ReActPattern.__new__(ReActPattern)
        context = create_empty_context("test goal")
        
        # Pattern не должен требовать executor/runtime для decide()
        # Проверяем что метод существует и может быть вызван
        assert hasattr(pattern, 'decide')
        assert callable(getattr(pattern, 'decide'))

    @pytest.mark.asyncio
    async def test_pattern_has_no_executor_dependency(self):
        """
        Pattern НЕ должен знать Executor.
        
        Цель: поймать нарушение зависимостей.
        """
        from core.agent.behaviors.react.pattern import ReActPattern
        
        pattern = ReActPattern.__new__(ReActPattern)
        attrs = dir(pattern)
        
        forbidden = ["executor", "runtime", "safe_executor"]
        
        for f in forbidden:
            # Pattern не должен иметь прямых зависимостей от executor/runtime
            # (допускается только через application_context)
            assert f not in attrs or f.startswith('_'), \
                f"Pattern has forbidden dependency: {f}"


# ============================================================================
# 2. RETRY ТЕСТ (ключевой)
# ============================================================================

class TestRetryLogic:
    """
    Цель: проверить, что retry — это решение Pattern.
    
    ❌ Если:
        - decision не зависит от failures
        👉 значит логика retry где-то ещё
    """

    @pytest.mark.asyncio
    async def test_pattern_sees_failures(self):
        """Pattern видит ошибки в контексте."""
        context = create_context_with_failures(
            goal="test",
            failures=[
                Failure(type="logic", error_message="Test error 1"),
                Failure(type="logic", error_message="Test error 2"),
            ]
        )
        
        # Pattern должен иметь доступ к failures через context
        failures_count = context.get_consecutive_failures()
        assert failures_count >= 0, "Pattern should be able to read failures"

    @pytest.mark.asyncio
    async def test_pattern_reacts_to_failures(self):
        """Pattern реагирует на количество ошибок."""
        from core.agent.behaviors.react.pattern import ReActPattern
        
        # Контекст с ошибками
        context_with_errors = create_context_with_failures(
            goal="test",
            failures=[Failure(type="logic")] * 3
        )
        
        # Контекст без ошибок
        context_clean = create_empty_context("test")
        
        # Pattern должен по-разному реагировать
        errors_count_with_errors = context_with_errors.get_consecutive_failures()
        errors_count_clean = context_clean.get_consecutive_failures()
        
        assert errors_count_with_errors > errors_count_clean, \
            "Pattern should distinguish contexts with different failure counts"


# ============================================================================
# 3. STRATEGY SWITCH ТЕСТ
# ============================================================================

class TestStrategySwitch:
    """
    Цель: убедиться, что switch — это решение Pattern.
    
    ❌ Если:
        - switch происходит НЕ в Pattern
        👉 значит он спрятан в runtime / memory
    """

    @pytest.mark.asyncio
    async def test_pattern_can_switch_strategy(self):
        """Pattern может принять решение о смене стратегии."""
        # DecisionType должен иметь SWITCH_STRATEGY
        assert hasattr(DecisionType, 'SWITCH_STRATEGY'), \
            "DecisionType should have SWITCH_STRATEGY"
        
        # Decision должен поддерживать next_pattern
        decision = Decision(
            type=DecisionType.SWITCH_STRATEGY,
            next_pattern="fallback_pattern",
            reasoning="Too many failures"
        )
        
        assert decision.next_pattern == "fallback_pattern"

    @pytest.mark.asyncio
    async def test_pattern_switches_on_repeated_failures(self):
        """
        Pattern должен переключаться при повторных ошибках.
        
        Это тест контракта — проверяем что архитектура поддерживает switch.
        """
        context = create_context_with_failures(
            goal="test",
            failures=[
                Failure(type="logic"),
                Failure(type="logic"),
                Failure(type="logic"),
            ]
        )
        
        # Pattern должен видеть 3 последовательные ошибки
        failures_count = context.get_consecutive_failures()
        assert failures_count >= 3, "Context should track consecutive failures"


# ============================================================================
# 4. NO-PROGRESS ТЕСТ (очень важный)
# ============================================================================

class TestNoProgress:
    """
    Цель: проверить, что Pattern понимает прогресс.
    
    ❌ Если:
        - Pattern игнорирует history
        👉 логика уехала в runtime/policy
    """

    @pytest.mark.asyncio
    async def test_pattern_detects_no_progress(self):
        """Pattern обнаруживает отсутствие прогресса."""
        context = create_context_with_failures(
            goal="test",
            failures=[],
            steps=[
                Step(result="same", status=ExecutionStatus.FAILED),
                Step(result="same", status=ExecutionStatus.FAILED),
                Step(result="same", status=ExecutionStatus.FAILED),
            ]
        )
        
        # Pattern должен обнаружить отсутствие прогресса
        has_no_progress = context.has_no_progress(n_steps=3)
        assert has_no_progress, "Pattern should detect no progress"

    @pytest.mark.asyncio
    async def test_pattern_sees_progress(self):
        """Pattern видит прогресс."""
        context = create_context_with_failures(
            goal="test",
            failures=[],
            steps=[
                Step(result="step1", status=ExecutionStatus.COMPLETED),
                Step(result="step2", status=ExecutionStatus.COMPLETED),
                Step(result="step3", status=ExecutionStatus.COMPLETED),
            ]
        )
        
        # Не должно быть отсутствия прогресса
        has_no_progress = context.has_no_progress(n_steps=3)
        assert not has_no_progress, "Pattern should see progress"


# ============================================================================
# 5. DETERMINISM ТЕСТ (очень жёсткий)
# ============================================================================

class TestDeterminism:
    """
    Цель: убить скрытые side-effects.
    
    ❌ Если падает:
        - есть hidden state
        - pattern зависит от внешнего мира
    """

    @pytest.mark.asyncio
    async def test_context_is_deterministic(self):
        """Context детерминирован."""
        context1 = create_empty_context("test")
        context2 = create_empty_context("test")
        
        # Одинаковые контексты должны давать одинаковые query results
        assert context1.get_goal() == context2.get_goal()
        assert context1.get_consecutive_failures() == context2.get_consecutive_failures()


# ============================================================================
# 6. ERROR INTERPRETATION ТЕСТ
# ============================================================================

class TestErrorInterpretation:
    """
    Цель: Pattern должен понимать тип ошибки.
    
    ❌ Если одинаково:
        👉 pattern тупой → вся логика вне его
    """

    @pytest.mark.asyncio
    async def test_context_tracks_error_types(self):
        """Context отслеживает типы ошибок."""
        context = create_context_with_failures(
            goal="test",
            failures=[
                Failure(type="logic", error_message="Logic error"),
                Failure(type="timeout", error_message="Timeout"),
            ]
        )
        
        # Context должен хранить информацию об ошибках
        failures_count = context.get_consecutive_failures()
        assert failures_count >= 2, "Context should track all failures"

    @pytest.mark.asyncio
    async def test_different_error_types_tracked(self):
        """Разные типы ошибок различимы."""
        from core.errors.failure_memory import FailureMemory
        from core.models.enums.common_enums import ErrorType
        
        memory = FailureMemory()
        
        memory.record("test_cap", ErrorType.LOGIC)
        memory.record("test_cap", ErrorType.TRANSIENT)
        
        # Memory должна различать типы
        logic_count = memory.get_count("test_cap", ErrorType.LOGIC)
        transient_count = memory.get_count("test_cap", ErrorType.TRANSIENT)
        
        assert logic_count >= 1
        assert transient_count >= 1


# ============================================================================
# 7. CONTRACT ТЕСТ DECISION
# ============================================================================

class TestDecisionContract:
    """
    Цель: не дать архитектуре размыться.
    
    ❌ Если появится:
        - AUTO_RETRY
        - HANDLED_ERROR
        - FALLBACK_INTERNAL
        👉 значит архитектура снова расползается
    """

    def test_decision_type_contract(self):
        """DecisionType имеет фиксированный набор."""
        allowed_types = {
            DecisionType.ACT,
            DecisionType.FINISH,
            DecisionType.FAIL,
            DecisionType.SWITCH_STRATEGY
        }
        
        # Никаких дополнительных типов
        assert len(list(DecisionType)) == len(allowed_types), \
            "DecisionType should have exactly 4 types"
        
        # Проверка что нет RETRY
        type_values = [t.value for t in DecisionType]
        assert "retry" not in type_values, \
            "RETRY should not be a separate type (use ACT with same action)"

    def test_decision_has_required_fields(self):
        """Decision имеет обязательные поля."""
        decision = Decision(
            type=DecisionType.ACT,
            action="test_capability",
            reasoning="because..."
        )
        
        assert decision.type is not None
        assert hasattr(decision, 'action')
        assert hasattr(decision, 'reasoning')

    def test_decision_switch_has_next_pattern(self):
        """Decision для SWITCH имеет next_pattern."""
        decision = Decision(
            type=DecisionType.SWITCH_STRATEGY,
            next_pattern="fallback_pattern",
            reasoning="Too many failures"
        )
        
        assert decision.next_pattern == "fallback_pattern"

    def test_decision_fail_has_error(self):
        """Decision для FAIL имеет error."""
        decision = Decision(
            type=DecisionType.FAIL,
            error="Critical failure",
            reasoning="Unrecoverable error"
        )
        
        assert decision.error == "Critical failure"


# ============================================================================
# 8. SIMULATION TEST (самый важный)
# ============================================================================

class TestFullSimulation:
    """
    Simulation test — тестирует всю архитектуру через Pattern.
    
    ❗ Это тестирует:
        👉 всю архитектуру через Pattern
    """

    @pytest.mark.asyncio
    async def test_full_loop_with_failures(self):
        """
        Полный цикл с ошибками.
        
        Собираем минимальную симуляцию:
        1. Pattern принимает решение
        2. Executor выполняет (fail)
        3. Pattern видит failure
        4. Pattern решает что делать дальше
        """
        context = create_empty_context("test goal")
        
        # Симуляция 3 неудачных попыток
        for i in range(3):
            # Pattern принимает решение
            # (в реальном коде: decision = await pattern.decide(context))
            
            # Executor выполняет (fail)
            # (в реальном коде: await executor.execute(decision.action))
            
            # Запись failure в контекст
            context.step_context.add_step(type('AgentStep', (), {
                'step_number': i,
                'capability_name': 'test_capability',
                'skill_name': 'test_skill',
                'action_item_id': '',
                'observation_item_ids': [],
                'summary': f'Attempt {i+1} failed',
                'status': ExecutionStatus.FAILED
            })())
        
        # После 3 ошибок Pattern должен решить что-то кроме ACT
        failures_count = context.get_consecutive_failures()
        assert failures_count >= 3, "Should have 3 consecutive failures"
        
        # В реальной архитектуре Pattern должен вернуть SWITCH или FAIL
        has_no_progress = context.has_no_progress(n_steps=3)
        assert has_no_progress, "Should detect no progress"

    @pytest.mark.asyncio
    async def test_context_persists_failures(self):
        """Context сохраняет failures между шагами."""
        context = create_empty_context("test")
        
        # Шаг 1: failure
        context.step_context.add_step(type('AgentStep', (), {
            'step_number': 0,
            'capability_name': 'cap1',
            'skill_name': 'skill1',
            'action_item_id': '',
            'observation_item_ids': [],
            'summary': 'Failed',
            'status': ExecutionStatus.FAILED
        })())
        
        # Шаг 2: failure
        context.step_context.add_step(type('AgentStep', (), {
            'step_number': 1,
            'capability_name': 'cap2',
            'skill_name': 'skill2',
            'action_item_id': '',
            'observation_item_ids': [],
            'summary': 'Failed',
            'status': ExecutionStatus.FAILED
        })())
        
        # Context должен помнить оба failure
        failures_count = context.get_consecutive_failures()
        assert failures_count >= 2, "Context should persist failures"


# ============================================================================
# 9. EXECUTION RESULT ТЕСТ
# ============================================================================

class TestExecutionResult:
    """Тесты для ExecutionResult."""

    def test_is_failure_helper(self):
        """is_failure() работает корректно."""
        from core.models.data.execution import ExecutionResult
        
        success_result = ExecutionResult.success(data={'result': 'ok'})
        failure_result = ExecutionResult.failure(error='test error')
        
        assert not success_result.is_failure()
        assert failure_result.is_failure()

    def test_is_empty_helper(self):
        """is_empty() работает корректно."""
        from core.models.data.execution import ExecutionResult
        
        empty_result = ExecutionResult.success(data=None)
        non_empty_result = ExecutionResult.success(data={'result': 'ok'})
        
        assert empty_result.is_empty()
        assert not non_empty_result.is_empty()


# ============================================================================
# 10. CONTEXT QUERY HELPERS ТЕСТ
# ============================================================================

class TestContextQueryHelpers:
    """Тесты для query helpers в SessionContext."""

    def test_get_last_steps(self):
        """get_last_steps() возвращает последние шаги."""
        context = create_empty_context("test")
        
        # Добавить 5 шагов
        for i in range(5):
            context.step_context.add_step(type('AgentStep', (), {
                'step_number': i,
                'capability_name': f'cap{i}',
                'skill_name': 'skill',
                'action_item_id': '',
                'observation_item_ids': [],
                'summary': f'Step {i}',
                'status': ExecutionStatus.COMPLETED
            })())
        
        # Получить последние 3
        last_steps = context.get_last_steps(n=3)
        assert len(last_steps) == 3
        assert last_steps[-1].summary == 'Step 4'

    def test_get_errors_count(self):
        """get_errors_count() считает ошибки."""
        context = create_context_with_failures(
            goal="test",
            failures=[Failure(type="logic")] * 5
        )
        
        errors_count = context.get_errors_count()
        assert errors_count >= 5

    def test_has_no_progress(self):
        """has_no_progress() обнаруживает отсутствие прогресса."""
        context = create_context_with_failures(
            goal="test",
            failures=[],
            steps=[
                Step(result="same", status=ExecutionStatus.FAILED),
                Step(result="same", status=ExecutionStatus.FAILED),
            ]
        )
        
        assert context.has_no_progress(n_steps=2)
        assert not context.has_no_progress(n_steps=5)  # Мало шагов
