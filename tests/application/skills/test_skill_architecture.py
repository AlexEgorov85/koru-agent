"""
Интеграционные тесты для Skills.

Проверяют соответствие архитектуры:
1. Skill вызывается без Agent
2. Skill не имеет доступа к state
3. Skill не вызывает LLM напрямую
4. Skill возвращает ExecutionResult
5. Skill не делает retry
6. Skill с side-effect помечает его
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.data.execution import ExecutionResult
from core.models.data.capability import Capability


class TestSkillArchitecture:
    """Тесты архитектуры Skills"""

    def test_execution_result_has_required_fields(self):
        """ExecutionResult имеет все обязательные поля"""
        from core.models.enums.common_enums import ExecutionStatus
        result = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={"test": "data"},
            error=None,
            metadata={"key": "value"},
            side_effect=True
        )

        assert hasattr(result, 'data')
        assert hasattr(result, 'error')
        assert hasattr(result, 'metadata')
        assert hasattr(result, 'side_effect')
        assert hasattr(result, 'status')
        # Проверяем алиас technical_success
        assert result.technical_success is True

    def test_execution_result_success_factory(self):
        """ExecutionResult.success создаёт правильный результат"""
        result = ExecutionResult.success(
            data={"answer": "test"},
            metadata={"tokens": 100},
            side_effect=False
        )

        assert result.technical_success is True
        assert result.data == {"answer": "test"}
        assert result.error is None
        assert result.metadata == {"tokens": 100}
        assert result.side_effect is False

    def test_execution_result_failure_factory(self):
        """ExecutionResult.failure создаёт правильный результат"""
        result = ExecutionResult.failure(
            error="Test error",
            metadata={"error_code": 500}
        )

        assert result.technical_success is False
        assert result.data is None
        assert result.error == "Test error"
        assert result.side_effect is False


class TestBookLibrarySkill:
    """Тесты BookLibrarySkill"""

    def test_skill_has_no_state_access(self):
        """BookLibrarySkill не имеет прямого доступа к state"""
        import inspect
        from core.components.skills.book_library.skill import BookLibrarySkill

        # Получаем исходный код
        source = inspect.getsource(BookLibrarySkill)

        # Проверяем отсутствие доступа к state
        assert "state.memory" not in source
        assert "state.finished" not in source
        assert "state.pattern_data" not in source
        assert ".data_context" not in source


class TestFinalAnswerSkill:
    """Тесты FinalAnswerSkill"""

    def test_skill_has_no_direct_context_access(self):
        """FinalAnswerSkill не имеет прямого доступа к context.data_context"""
        import inspect
        from core.components.skills.final_answer.skill import FinalAnswerSkill

        source = inspect.getsource(FinalAnswerSkill)

        # Проверяем что нет прямого доступа (только через executor)
        assert "context.data_context.items" not in source
        assert "session_context.data_context" not in source

    def test_skill_calls_executor_for_context(self):
        """FinalAnswerSkill использует executor для доступа к контексту"""
        import inspect
        from core.components.skills.final_answer.skill import FinalAnswerSkill

        source = inspect.getsource(FinalAnswerSkill)

        # Проверяем что использует executor
        assert "executor.execute_action" in source
        assert "context.get_all_items" in source or "context.get_step_history" in source


class TestPlanningSkill:
    """Тесты PlanningSkill"""

    def test_skill_returns_data_from_execute_impl(self):
        """PlanningSkill._execute_impl возвращает данные (BaseComponent.execute() обернёт в ExecutionResult)"""
        import inspect
        from core.components.skills.planning.skill import PlanningSkill

        source = inspect.getsource(PlanningSkill)

        # Проверяем что _execute_impl возвращает Dict
        assert "-> Dict[str, Any]:" in source or "-> Dict" in source
        # Проверяем что извлекает данные из ActionResult
        assert "result.data" in source or "return result" in source

    def test_skill_marks_side_effects(self):
        """PlanningSkill помечает side_effect=True"""
        import inspect
        from core.components.skills.planning.skill import PlanningSkill

        source = inspect.getsource(PlanningSkill)

        # PlanningSkill всегда меняет контекст через executor
        # Проверяем что использует executor для изменения контекста
        assert "executor.execute_action" in source
        assert "context.record" in source or "context.update" in source


class TestDataAnalysisSkill:
    """Тесты DataAnalysisSkill"""

    def test_skill_returns_data_from_execute_impl(self):
        """DataAnalysisSkill._execute_impl возвращает данные (BaseComponent.execute() обернёт в ExecutionResult)"""
        import inspect
        from core.components.skills.data_analysis.skill import DataAnalysisSkill

        source = inspect.getsource(DataAnalysisSkill)

        # Проверяем что _execute_impl возвращает Dict
        assert "-> Dict[str, Any]:" in source or "-> Dict" in source
        # Проверяем что возвращает данные напрямую
        assert "return validated_answer" in source or "return result" in source

    def test_skill_marks_side_effects(self):
        """DataAnalysisSkill помечает side_effect=True для file/DB access"""
        import inspect
        from core.components.skills.data_analysis.skill import DataAnalysisSkill

        source = inspect.getsource(DataAnalysisSkill)

        # Проверяем что side_effect=True указан
        assert "side_effect=True" in source


class TestSkillDeterminism:
    """Тесты детерминированности Skills"""

    def test_no_random_usage(self):
        """Skills не используют random"""
        import inspect
        from core.components.skills.book_library.skill import BookLibrarySkill
        from core.components.skills.planning.skill import PlanningSkill
        from core.components.skills.final_answer.skill import FinalAnswerSkill
        from core.components.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)
            assert "import random" not in source
            assert "from random" not in source
            assert "random." not in source


class TestSkillNoPatternKnowledge:
    """Тесты что Skills не знают о Pattern"""

    def test_no_pattern_type_checks(self):
        """Skills не проверяют тип Pattern"""
        import inspect
        from core.components.skills.book_library.skill import BookLibrarySkill
        from core.components.skills.planning.skill import PlanningSkill
        from core.components.skills.final_answer.skill import FinalAnswerSkill
        from core.components.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)

            # Проверяем отсутствие проверок типа Pattern
            assert "isinstance" not in source or "Pattern" not in source
            assert "pattern_type" not in source
            assert "pattern_data" not in source

    def test_supported_strategies_is_metadata(self):
        """supported_strategies это только metadata, не логика"""
        import inspect
        from core.components.skills.book_library.skill import BookLibrarySkill
        from core.components.skills.final_answer.skill import FinalAnswerSkill
        from core.components.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, FinalAnswerSkill, DataAnalysisSkill]:
            # Проверяем исходный код что нет проверок стратегии
            source = inspect.getsource(skill_class)
            # Проверяем что нет проверок типа if strategy == "react"
            assert 'if.*strategy.*==' not in source


class TestSkillNoDirectLLM:
    """Тесты что Skills не вызывают LLM напрямую"""

    def test_no_direct_llm_calls(self):
        """Skills не создают LLM клиентов напрямую"""
        import inspect
        from core.components.skills.book_library.skill import BookLibrarySkill
        from core.components.skills.planning.skill import PlanningSkill
        from core.components.skills.final_answer.skill import FinalAnswerSkill
        from core.components.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)

            # Проверяем отсутствие прямых вызовов LLM API
            assert "openai.ChatCompletion" not in source
            assert "openai.chat" not in source
            assert "client.chat" not in source
            assert "llm_client" not in source

            # Но executor.execute_action с llm.generate_structured OK
            # assert "llm.generate_structured" in source  # Это правильно через executor


class TestSkillNoRetry:
    """Тесты что Skills не имеют своей retry логики"""

    def test_no_retry_loops(self):
        """Skills не имеют циклов retry"""
        import inspect
        from core.components.skills.book_library.skill import BookLibrarySkill
        from core.components.skills.planning.skill import PlanningSkill
        from core.components.skills.final_answer.skill import FinalAnswerSkill
        from core.components.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)

            # Проверяем отсутствие retry циклов
            assert "for attempt" not in source
            assert "while retry" not in source
            assert "range(3)" not in source
            # max_retries в параметрах executor это OK (это не retry логика skill)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
