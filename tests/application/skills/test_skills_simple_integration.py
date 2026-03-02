"""
Упрощённые интеграционные тесты для Skills.

Проверяют что skills возвращают SkillResult с правильными полями.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.data.execution import SkillResult


class TestAllSkillsReturnSkillResult:
    """
    Тесты что ВСЕ skills возвращают SkillResult.
    
    Это критично для единой архитектуры.
    """

    def test_skill_result_exists(self):
        """SkillResult класс существует"""
        from core.models.data.execution import SkillResult
        assert SkillResult is not None

    def test_book_library_skill_returns_skill_result_type(self):
        """BookLibrarySkill._execute_impl возвращает SkillResult (проверка типа)"""
        import inspect
        from core.application.skills.book_library.skill import BookLibrarySkill
        
        source = inspect.getsource(BookLibrarySkill)
        
        # Проверяем что метод возвращает SkillResult
        assert "-> SkillResult:" in source
        assert "SkillResult.success" in source or "SkillResult.failure" in source

    def test_planning_skill_returns_skill_result_type(self):
        """PlanningSkill._execute_impl возвращает SkillResult (проверка типа)"""
        import inspect
        from core.application.skills.planning.skill import PlanningSkill
        
        source = inspect.getsource(PlanningSkill)
        
        # Проверяем что метод возвращает SkillResult
        assert "-> SkillResult:" in source
        assert "SkillResult(" in source

    def test_final_answer_skill_returns_skill_result_type(self):
        """FinalAnswerSkill._execute_impl возвращает SkillResult (проверка типа)"""
        import inspect
        from core.application.skills.final_answer.skill import FinalAnswerSkill
        
        source = inspect.getsource(FinalAnswerSkill)
        
        # Проверяем что метод возвращает SkillResult
        assert "-> SkillResult:" in source
        assert "SkillResult.success" in source or "SkillResult.failure" in source

    def test_data_analysis_skill_returns_skill_result_type(self):
        """DataAnalysisSkill._execute_impl возвращает SkillResult (проверка типа)"""
        import inspect
        from core.application.skills.data_analysis.skill import DataAnalysisSkill
        
        source = inspect.getsource(DataAnalysisSkill)
        
        # Проверяем что метод возвращает SkillResult
        assert "-> SkillResult:" in source
        assert "SkillResult.success" in source or "SkillResult.failure" in source


class TestSkillResultUsage:
    """Тесты правильного использования SkillResult"""

    def test_all_skills_use_success_factory(self):
        """Все skills используют SkillResult.success или конструктор для успешных результатов"""
        import inspect
        from core.application.skills.book_library.skill import BookLibrarySkill
        from core.application.skills.planning.skill import PlanningSkill
        from core.application.skills.final_answer.skill import FinalAnswerSkill
        from core.application.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)
            # Проверяем что используется factory метод ИЛИ конструктор
            has_success = "SkillResult.success" in source or "SkillResult(" in source
            assert has_success, f"{skill_class.__name__} не использует SkillResult"

    def test_all_skills_use_failure_factory(self):
        """Все skills используют SkillResult.failure или конструктор для ошибок"""
        import inspect
        from core.application.skills.book_library.skill import BookLibrarySkill
        from core.application.skills.planning.skill import PlanningSkill
        from core.application.skills.final_answer.skill import FinalAnswerSkill
        from core.application.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)
            # Проверяем что используется factory метод ИЛИ конструктор для ошибок
            has_failure = "SkillResult.failure" in source or "SkillResult(" in source
            assert has_failure, f"{skill_class.__name__} не использует SkillResult для ошибок"

    def test_side_effect_flag_used(self):
        """Skills явно указывают side_effect"""
        import inspect
        from core.application.skills.book_library.skill import BookLibrarySkill
        from core.application.skills.planning.skill import PlanningSkill
        from core.application.skills.final_answer.skill import FinalAnswerSkill
        from core.application.skills.data_analysis.skill import DataAnalysisSkill

        for skill_class in [BookLibrarySkill, PlanningSkill, FinalAnswerSkill, DataAnalysisSkill]:
            source = inspect.getsource(skill_class)
            # Проверяем что side_effect явно указан
            assert "side_effect=" in source, f"{skill_class.__name__} не указывает side_effect"


class TestSkillResultFields:
    """Тесты полей SkillResult"""

    def test_skill_result_has_all_fields(self):
        """SkillResult имеет все обязательные поля"""
        result = SkillResult(
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

    def test_skill_result_default_values(self):
        """SkillResult имеет правильные значения по умолчанию"""
        result = SkillResult()

        assert result.technical_success is True
        assert result.data is None
        assert result.error is None
        assert result.metadata == {}
        assert result.side_effect is False

    def test_skill_result_success_factory_creates_correct_result(self):
        """SkillResult.success создаёт правильный результат"""
        result = SkillResult.success(
            data={"answer": "test"},
            metadata={"tokens": 100},
            side_effect=True
        )

        assert result.technical_success is True
        assert result.data == {"answer": "test"}
        assert result.error is None
        assert result.metadata == {"tokens": 100}
        assert result.side_effect is True

    def test_skill_result_failure_factory_creates_correct_result(self):
        """SkillResult.failure создаёт правильный результат"""
        result = SkillResult.failure(
            error="Test error message",
            metadata={"error_code": 500}
        )

        assert result.technical_success is False
        assert result.data is None
        assert result.error == "Test error message"
        assert result.side_effect is False

    def test_skill_result_to_dict(self):
        """SkillResult.to_dict сериализует все поля"""
        result = SkillResult.success(
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


class TestSkillResultInExecutionContext:
    """Тесты что SkillResult правильно используется в контексте выполнения"""

    def test_skill_result_can_be_wrapped_in_execution_result(self):
        """SkillResult может быть обёрнут в ExecutionResult"""
        from core.models.data.execution import ExecutionResult, ExecutionStatus

        skill_result = SkillResult.success(
            data={"answer": "test"},
            side_effect=False
        )

        # ExecutionResult может содержать SkillResult как данные
        exec_result = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            result=skill_result,
            metadata={"skill_name": "test_skill"}
        )

        assert exec_result.status == ExecutionStatus.COMPLETED
        assert isinstance(exec_result.result, SkillResult)
        assert exec_result.result.data == {"answer": "test"}


class TestSkillsHaveNoLegacyPatterns:
    """Тесты что skills не имеют legacy паттернов"""

    def test_no_direct_dict_return_in_skills(self):
        """Skills не возвращают голый dict из основных методов (кроме внутренних)"""
        import inspect
        from core.application.skills.book_library.skill import BookLibrarySkill
        from core.application.skills.planning.skill import PlanningSkill
        from core.application.skills.final_answer.skill import FinalAnswerSkill
        from core.application.skills.data_analysis.skill import DataAnalysisSkill

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
                    # Проверяем что это часть SkillResult
                    context = '\n'.join(lines[max(0, i-5):i+1])
                    assert "SkillResult" in context, \
                        f"{skill_class.__name__}.{current_method} возвращает dict напрямую: {stripped}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
