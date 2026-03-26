"""
Упрощённые интеграционные тесты для Skills.

Проверяют что skills возвращают ExecutionResult с правильными полями.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.data.execution import ExecutionResult


class TestAllSkillsReturnExecutionResult:
    """
    Тесты что ВСЕ skills возвращают ExecutionResult.

    Это критично для единой архитектуры.
    """

    def test_execution_result_exists(self):
        """ExecutionResult класс существует"""
        from core.models.data.execution import ExecutionResult
        assert ExecutionResult is not None

    def test_book_library_skill_returns_execution_result_type(self):
        """BookLibrarySkill._execute_impl возвращает ExecutionResult (проверка типа)"""
        import inspect
        from core.services.skills.book_library.skill import BookLibrarySkill

        source = inspect.getsource(BookLibrarySkill)

        # Проверяем что метод возвращает ExecutionResult
        assert "-> ExecutionResult:" in source
        assert "ExecutionResult.success" in source or "ExecutionResult.failure" in source

    def test_planning_skill_returns_execution_result_type(self):
        """PlanningSkill._execute_impl возвращает ExecutionResult (проверка типа)"""
        import inspect
        from core.services.skills.planning.skill import PlanningSkill

        source = inspect.getsource(PlanningSkill)

        # Проверяем что метод возвращает ExecutionResult
        assert "-> ExecutionResult:" in source
        assert "ExecutionResult(" in source

    def test_final_answer_skill_returns_execution_result_type(self):
        """FinalAnswerSkill._execute_impl возвращает ExecutionResult (проверка типа)"""
        import inspect
        from core.services.skills.final_answer.skill import FinalAnswerSkill

        source = inspect.getsource(FinalAnswerSkill)

        # Проверяем что метод возвращает ExecutionResult
        assert "-> ExecutionResult:" in source
        assert "ExecutionResult.success" in source or "ExecutionResult.failure" in source

    def test_data_analysis_skill_returns_execution_result_type(self):
        """DataAnalysisSkill._execute_impl возвращает ExecutionResult (проверка типа)"""
        import inspect
        from core.services.skills.data_analysis.skill import DataAnalysisSkill

        source = inspect.getsource(DataAnalysisSkill)

        # Проверяем что метод возвращает ExecutionResult
        assert "-> ExecutionResult:" in source
        assert "ExecutionResult.success" in source or "ExecutionResult.failure" in source


class TestExecutionResultUsage:
    """Тесты правильного использования ExecutionResult"""

    def test_all_skills_use_success_factory(self):
        """Все skills используют ExecutionResult.success или конструктор для успешных результатов"""
        import inspect
        from core.services.skills.book_library.skill import BookLibrarySkill
        from core.services.skills.planning.skill import PlanningSkill
        from core.services.skills.final_answer.skill import FinalAnswerSkill
        from core.services.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)
            # Проверяем что используется factory метод ИЛИ конструктор
            has_success = "ExecutionResult.success" in source or "ExecutionResult(" in source
            assert has_success, f"{skill_class.__name__} не использует ExecutionResult"

    def test_all_skills_use_failure_factory(self):
        """Все skills используют ExecutionResult.failure или конструктор для ошибок"""
        import inspect
        from core.services.skills.book_library.skill import BookLibrarySkill
        from core.services.skills.planning.skill import PlanningSkill
        from core.services.skills.final_answer.skill import FinalAnswerSkill
        from core.services.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)
            # Проверяем что используется factory метод ИЛИ конструктор для ошибок
            has_failure = "ExecutionResult.failure" in source or "ExecutionResult(" in source
            assert has_failure, f"{skill_class.__name__} не использует ExecutionResult для ошибок"

    def test_side_effect_flag_used(self):
        """Skills явно указывают side_effect"""
        import inspect
        from core.services.skills.book_library.skill import BookLibrarySkill
        from core.services.skills.planning.skill import PlanningSkill
        from core.services.skills.final_answer.skill import FinalAnswerSkill
        from core.services.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)
            # Проверяем что side_effect явно указан
            assert "side_effect=" in source, f"{skill_class.__name__} не указывает side_effect"


class TestExecutionResultFields:
    """Тесты полей ExecutionResult"""

    def test_execution_result_has_all_fields(self):
        """ExecutionResult имеет все обязательные поля"""
        result = ExecutionResult(
            technical_success=True,
            data={"test": "data"},
            error=None,
            metadata={"key": "value"},
            side_effect=False
        )

        assert result.technical_success is True
        assert result.data == {"test": "data"}
        assert result.error is None
        assert result.metadata == {"key": "value"}
        assert result.side_effect is False

    def test_execution_result_default_values(self):
        """ExecutionResult имеет правильные значения по умолчанию"""
        result = ExecutionResult()

        assert result.technical_success is True
        assert result.data is None
        assert result.error is None
        assert result.metadata == {}
        assert result.side_effect is False

    def test_execution_result_success_factory_creates_correct_result(self):
        """ExecutionResult.success создаёт правильный результат"""
        result = ExecutionResult.success(
            data={"answer": "test"},
            metadata={"tokens": 100},
            side_effect=True
        )

        assert result.technical_success is True
        assert result.data == {"answer": "test"}
        assert result.error is None
        assert result.metadata == {"tokens": 100}
        assert result.side_effect is True

    def test_execution_result_failure_factory_creates_correct_result(self):
        """ExecutionResult.failure создаёт правильный результат"""
        result = ExecutionResult.failure(
            error="Test error message",
            metadata={"error_code": 500}
        )

        assert result.technical_success is False
        assert result.data is None
        assert result.error == "Test error message"
        assert result.side_effect is False

    def test_execution_result_to_dict(self):
        """ExecutionResult.to_dict сериализует все поля"""
        result = ExecutionResult.success(
            data={"key": "value"},
            metadata={"meta": "data"},
            side_effect=True
        )

        result_dict = result.to_dict()

        assert result_dict == {
            "technical_success": True,
            "data": {"key": "value"},
            "error": None,
            "metadata": {"meta": "data"},
            "side_effect": True
        }


class TestExecutionResultInExecutionContext:
    """Тесты что ExecutionResult правильно используется в контексте выполнения"""

    def test_execution_result_can_be_wrapped_in_execution_result(self):
        """ExecutionResult может быть обёрнут в ExecutionResult"""
        from core.models.data.execution import ExecutionResult, ExecutionStatus

        execution_result = ExecutionResult.success(
            data={"answer": "test"},
            side_effect=False
        )

        # ExecutionResult может содержать ExecutionResult как данные
        exec_result = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            result=execution_result,
            metadata={"skill_name": "test_skill"}
        )

        assert exec_result.status == ExecutionStatus.COMPLETED
        assert isinstance(exec_result.result, ExecutionResult)
        assert exec_result.result.data == {"answer": "test"}


class TestSkillsHaveNoLegacyPatterns:
    """Тесты что skills не имеют legacy паттернов"""

    def test_no_direct_dict_return_in_skills(self):
        """Skills не возвращают голый dict из основных методов (кроме внутренних)"""
        import inspect
        from core.services.skills.book_library.skill import BookLibrarySkill
        from core.services.skills.planning.skill import PlanningSkill
        from core.services.skills.final_answer.skill import FinalAnswerSkill
        from core.services.skills.data_analysis.skill import DataAnalysisSkill

        # Проверяем только основные методы (_execute_impl и публичные)
        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)
            lines = source.split('\n')
            
            # Находим текущий метод
            current_method = None
            
            for i, line in enumerate(lines):
                # Определяем текущий метод
                if line.strip().startswith('def '):
                    method_name = line.strip().split('def ')[1].split('(')[0]
                    current_method = method_name
                
                stripped = line.strip()
                # Проверяем что return { не используется напрямую в основных методах
                if stripped.startswith('return {'):
                    # Пропускаем внутренние методы (начинаются с _)
                    if current_method and current_method.startswith('_'):
                        continue
                    # Проверяем что это часть ExecutionResult
                    context = '\n'.join(lines[max(0, i-5):i+1])
                    assert "ExecutionResult" in context, \
                        f"{skill_class.__name__}.{current_method} возвращает dict напрямую: {stripped}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
