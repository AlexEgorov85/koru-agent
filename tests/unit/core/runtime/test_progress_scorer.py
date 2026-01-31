"""
Тесты для модели ProgressScorer (ProgressScorer, ProgressStatus).
"""
import pytest
from unittest.mock import MagicMock
from core.agent_runtime.progress import ProgressScorer
from models.progress import ProgressStatus


class TestProgressScorerModel:
    """Тесты для модели ProgressScorer."""
    
    def test_progress_scorer_initialization(self):
        """Тест инициализации ProgressScorer."""
        scorer = ProgressScorer()
        
        assert scorer.last_summary is None
        assert scorer.threshold == 0.1  # значение по умолчанию
    
    def test_progress_scorer_custom_initialization(self):
        """Тест инициализации ProgressScorer с кастомными значениями."""
        scorer = ProgressScorer(threshold=0.2)
        
        assert scorer.threshold == 0.2
        assert scorer.last_summary is None
    
    def test_evaluate_first_call_returns_true(self):
        """Тест метода evaluate при первом вызове (всегда возвращает True)."""
        scorer = ProgressScorer()
        
        mock_session = MagicMock()
        mock_session.get_summary.return_value = {"step": 1, "status": "running"}
        
        result = scorer.evaluate(mock_session)
        
        assert result is True
        assert scorer.last_summary == {"step": 1, "status": "running"}
    
    def test_evaluate_same_summary_returns_false(self):
        """Тест метода evaluate при том же summary (возвращает False)."""
        scorer = ProgressScorer()
        
        mock_session = MagicMock()
        mock_session.get_summary.return_value = {"step": 1, "status": "running"}
        
        # Первый вызов - должен вернуть True
        result1 = scorer.evaluate(mock_session)
        assert result1 is True
        
        # Второй вызов с тем же summary - должен вернуть False
        result2 = scorer.evaluate(mock_session)
        assert result2 is False
        
        # last_summary не должен измениться
        assert scorer.last_summary == {"step": 1, "status": "running"}
    
    def test_evaluate_different_summary_returns_true(self):
        """Тест метода evaluate при изменении summary (возвращает True)."""
        scorer = ProgressScorer()
        
        mock_session = MagicMock()
        
        # Устанавливаем первый summary
        mock_session.get_summary.return_value = {"step": 1, "status": "running"}
        result1 = scorer.evaluate(mock_session)
        assert result1 is True
        assert scorer.last_summary == {"step": 1, "status": "running"}
        
        # Меняем summary
        mock_session.get_summary.return_value = {"step": 2, "status": "running", "progress": 0.5}
        result2 = scorer.evaluate(mock_session)
        assert result2 is True
        assert scorer.last_summary == {"step": 2, "status": "running", "progress": 0.5}
    
    def test_evaluate_with_progress_calculation(self):
        """Тест метода evaluate с вычислением прогресса."""
        scorer = ProgressScorer(threshold=0.2)  # порог 20%
        
        mock_session = MagicMock()
        
        # Устанавливаем первый summary
        mock_session.get_summary.return_value = {"progress": 0.2}  # 20%
        result1 = scorer.evaluate(mock_session)
        assert result1 is True
        assert scorer.last_summary == {"progress": 0.2}
        
        # Второй summary с небольшим прогрессом (меньше порога) - 25%, прирост 5% < 20%
        mock_session.get_summary.return_value = {"progress": 0.25}  # 25%
        result2 = scorer.evaluate(mock_session)
        assert result2 is False  # прогресс меньше порога
        
        # Третий summary с достаточным прогрессом - 45%, прирост 20% >= 20%
        mock_session.get_summary.return_value = {"progress": 0.45}  # 45%
        result3 = scorer.evaluate(mock_session)
        assert result3 is True  # прогресс больше или равен порогу
        assert scorer.last_summary == {"progress": 0.45}
    
    def test_evaluate_with_none_summary_first_call(self):
        """Тест метода evaluate с None в качестве первого summary."""
        scorer = ProgressScorer()
        
        mock_session = MagicMock()
        mock_session.get_summary.return_value = None
        
        result = scorer.evaluate(mock_session)
        
        assert result is True  # первый вызов всегда возвращает True
        assert scorer.last_summary is None
    
    def test_evaluate_with_none_summary_second_call(self):
        """Тест метода evaluate с None в качестве summary после первого вызова."""
        scorer = ProgressScorer()
        
        mock_session = MagicMock()
        
        # Первый вызов с None
        mock_session.get_summary.return_value = None
        result1 = scorer.evaluate(mock_session)
        assert result1 is True
        assert scorer.last_summary is None
        
        # Второй вызов с тем же None
        result2 = scorer.evaluate(mock_session)
        assert result2 is False  # тот же summary (None), прогресса нет
        assert scorer.last_summary is None  # Не изменилось
    
    def test_evaluate_complex_data(self):
        """Тест метода evaluate со сложными данными."""
        scorer = ProgressScorer()
        
        # Сложные структуры данных
        summary1 = {
            "step": 1,
            "actions": [{"name": "action1", "status": "pending"}],
            "context": {"var1": "value1"},
            "metrics": {"errors": 0, "success": 0}
        }
        
        summary2 = {
            "step": 1,
            "actions": [{"name": "action1", "status": "completed"}],  # Изменилось
            "context": {"var1": "value1"},
            "metrics": {"errors": 0, "success": 1}  # Изменилось
        }
        
        mock_session = MagicMock()
        mock_session.get_summary.return_value = summary1
        
        # Первый вызов
        result1 = scorer.evaluate(mock_session)
        assert result1 is True
        assert scorer.last_summary == summary1
        
        # Меняем возвращаемое значение на новое
        mock_session.get_summary.return_value = summary2
        
        # Второй вызов с измененным summary
        result2 = scorer.evaluate(mock_session)
        assert result2 is True  # данные изменились, есть прогресс
        assert scorer.last_summary == summary2


def test_progress_status_enum_values():
    """Тест значений ProgressStatus enum."""
    assert ProgressStatus.NO_PROGRESS.value == "no_progress"
    assert ProgressStatus.MINIMAL_PROGRESS.value == "minimal_progress"
    assert ProgressStatus.SOME_PROGRESS.value == "some_progress"
    assert ProgressStatus.GOOD_PROGRESS.value == "good_progress"
    assert ProgressStatus.EXCELLENT_PROGRESS.value == "excellent_progress"
    assert ProgressStatus.COMPLETED.value == "completed"
    
    # Проверяем все значения
    all_statuses = [status.value for status in ProgressStatus]
    expected_statuses = [
        "no_progress", "minimal_progress", "some_progress", 
        "good_progress", "excellent_progress", "completed"
    ]
    assert set(all_statuses) == set(expected_statuses)