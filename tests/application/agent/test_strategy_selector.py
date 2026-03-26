"""
Тесты для StrategySelector.

Проверяет:
1. Базовый выбор паттерна
2. Выбор с учётом сложности задачи
3. Переключение при ошибках
4. Обновление scores
"""
import pytest
from core.agent.components.strategy_selector import StrategySelector
from core.agent.components.failure_memory import FailureMemory
from core.models.enums.common_enums import ErrorType


class TestStrategySelectorBasic:
    """Тесты базового выбора паттерна."""

    def test_select_best_pattern_default(self):
        """Тест: выбор паттерна по умолчанию."""
        selector = StrategySelector()
        
        best = selector.select_best_pattern(
            available_patterns=["react_pattern", "planning_pattern"]
        )
        
        # planning_pattern имеет базовый score 0.6 > react_pattern 0.5
        assert best == "planning_pattern"

    def test_select_best_pattern_with_fallback(self):
        """Тест: fallback на react_pattern если нет доступных."""
        selector = StrategySelector()
        
        best = selector.select_best_pattern(available_patterns=[])
        
        assert best == "react_pattern"

    def test_select_best_pattern_single_option(self):
        """Тест: выбор единственного доступного паттерна."""
        selector = StrategySelector()
        
        best = selector.select_best_pattern(available_patterns=["react_pattern"])
        
        assert best == "react_pattern"


class TestStrategySelectorContext:
    """Тесты выбора с учётом контекста."""

    def test_high_complexity_selects_planning(self):
        """Тест: сложные задачи → planning_pattern."""
        selector = StrategySelector()
        
        best = selector.select_best_pattern(
            available_patterns=["react_pattern", "planning_pattern"],
            context={"complexity": "high"}
        )
        
        assert best == "planning_pattern"

    def test_low_complexity_selects_react(self):
        """Тест: простые задачи → react_pattern."""
        selector = StrategySelector()
        
        best = selector.select_best_pattern(
            available_patterns=["react_pattern", "planning_pattern"],
            context={"complexity": "low"}
        )
        
        assert best == "react_pattern"

    def test_evaluation_needs_evaluation_context(self):
        """Тест: evaluation_pattern выбирается при needs_evaluation."""
        selector = StrategySelector()
        
        best = selector.select_best_pattern(
            available_patterns=["react_pattern", "evaluation_pattern"],
            context={"needs_evaluation": True}
        )
        
        assert best == "evaluation_pattern"


class TestStrategySelectorFailureMemory:
    """Тесты выбора с учётом FailureMemory."""

    def test_exclude_failed_patterns(self):
        """Тест: исключение паттернов с ошибками."""
        selector = StrategySelector()
        failure_memory = FailureMemory()
        
        # Записываем 2 ошибки для planning_pattern
        failure_memory.record("planning_pattern", ErrorType.LOGIC)
        failure_memory.record("planning_pattern", ErrorType.LOGIC)
        
        best = selector.select_best_pattern(
            available_patterns=["react_pattern", "planning_pattern"],
            failure_memory=failure_memory
        )
        
        # planning_pattern исключён → react_pattern
        assert best == "react_pattern"

    def test_all_patterns_failed_fallback(self):
        """Тест: если все паттерны проблемные → берём все."""
        selector = StrategySelector()
        failure_memory = FailureMemory()
        
        # Записываем ошибки для всех
        failure_memory.record("react_pattern", ErrorType.LOGIC)
        failure_memory.record("react_pattern", ErrorType.LOGIC)
        failure_memory.record("planning_pattern", ErrorType.LOGIC)
        failure_memory.record("planning_pattern", ErrorType.LOGIC)
        
        best = selector.select_best_pattern(
            available_patterns=["react_pattern", "planning_pattern"],
            failure_memory=failure_memory
        )
        
        # Все проблемные → выбираем по score
        assert best in ["react_pattern", "planning_pattern"]


class TestStrategySelectorRecommendation:
    """Тесты рекомендаций переключения."""

    def test_recommend_switch_on_failure(self):
        """Тест: рекомендация переключения при ошибках."""
        selector = StrategySelector()
        failure_memory = FailureMemory()
        
        # Записываем 2 ошибки
        failure_memory.record("planning_pattern", ErrorType.LOGIC)
        failure_memory.record("planning_pattern", ErrorType.LOGIC)
        
        should_switch, target = selector.recommend_switch(
            current_pattern="planning_pattern",
            failure_memory=failure_memory
        )
        
        assert should_switch is True
        assert target == "react_pattern"

    def test_no_switch_on_transient_error(self):
        """Тест: нет переключения при TRANSIENT ошибке."""
        selector = StrategySelector()
        failure_memory = FailureMemory()
        
        # TRANSIENT ошибка → retry, не switch
        failure_memory.record("planning_pattern", ErrorType.TRANSIENT)
        
        should_switch, target = selector.recommend_switch(
            current_pattern="planning_pattern",
            failure_memory=failure_memory
        )
        
        assert should_switch is False

    def test_no_switch_without_failures(self):
        """Тест: нет переключения без ошибок."""
        selector = StrategySelector()
        failure_memory = FailureMemory()
        
        should_switch, target = selector.recommend_switch(
            current_pattern="planning_pattern",
            failure_memory=failure_memory
        )
        
        assert should_switch is False


class TestStrategySelectorScoreUpdates:
    """Тесты обновления scores."""

    def test_update_score_on_success(self):
        """Тест: успех увеличивает score."""
        selector = StrategySelector()
        initial_score = selector.BASE_SCORES.get("react_pattern", 0.5)
        
        selector._update_score("react_pattern", success=True)
        
        new_score = selector.BASE_SCORES.get("react_pattern", 0.5)
        assert new_score > initial_score
        assert new_score <= 1.0  # Не больше 1.0

    def test_update_score_on_failure(self):
        """Тест: неудача уменьшает score."""
        selector = StrategySelector()
        initial_score = selector.BASE_SCORES.get("react_pattern", 0.5)
        
        selector._update_score("react_pattern", success=False)
        
        new_score = selector.BASE_SCORES.get("react_pattern", 0.5)
        assert new_score < initial_score
        assert new_score >= 0.0  # Не меньше 0.0

    def test_get_pattern_scores(self):
        """Тест: получение копий scores."""
        selector = StrategySelector()
        
        scores = selector.get_pattern_scores()
        
        assert isinstance(scores, dict)
        assert "react_pattern" in scores
        assert "planning_pattern" in scores
        # Копия, не оригинал
        assert scores is not selector.BASE_SCORES


class TestStrategySelectorIntegration:
    """Интеграционные тесты."""

    def test_full_selection_workflow(self):
        """Тест: полный цикл выбора паттерна."""
        selector = StrategySelector()
        failure_memory = FailureMemory()
        
        # 1. Начальный выбор
        best = selector.select_best_pattern(
            available_patterns=["react_pattern", "planning_pattern"],
            context={"complexity": "high"},
            failure_memory=failure_memory
        )
        assert best == "planning_pattern"
        
        # 2. Обновление score после успеха
        selector._update_score("planning_pattern", success=True)
        
        # 3. Запись ошибок
        failure_memory.record("planning_pattern", ErrorType.LOGIC)
        failure_memory.record("planning_pattern", ErrorType.LOGIC)
        
        # 4. Выбор после ошибок
        best = selector.select_best_pattern(
            available_patterns=["react_pattern", "planning_pattern"],
            failure_memory=failure_memory
        )
        assert best == "react_pattern"

    def test_switch_penalty(self):
        """Тест: штраф за частые переключения."""
        selector = StrategySelector()
        
        # Выбор с current_pattern
        best_with_current = selector.select_best_pattern(
            available_patterns=["react_pattern", "planning_pattern"],
            current_pattern="react_pattern"
        )
        
        # planning_pattern должен быть выбран несмотря на штраф
        # (0.6 - 0.05 = 0.55 > 0.5)
        assert best_with_current == "planning_pattern"
