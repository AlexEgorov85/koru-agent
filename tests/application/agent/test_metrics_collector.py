"""
Тесты для MetricsCollector.

Проверяет:
1. Сбор метрик шагов
2. Агрегацию статистики сессии
3. Переключение паттернов
4. Публикацию событий через EventBus
"""
import pytest
from unittest.mock import MagicMock
from core.application.agent.components.metrics_collector import (
    MetricsCollector, StepMetrics, SessionMetrics
)


class TestStepMetrics:
    """Тесты StepMetrics."""

    def test_create_step_metrics(self):
        """Тест: создание метрик шага."""
        step = StepMetrics(
            step_number=1,
            capability="test.capability",
            status="completed",
            execution_time_ms=150.5
        )
        
        assert step.step_number == 1
        assert step.capability == "test.capability"
        assert step.status == "completed"
        assert step.execution_time_ms == 150.5
        assert step.error_type is None
        assert step.retry_count == 0

    def test_create_step_metrics_with_error(self):
        """Тест: создание метрик шага с ошибкой."""
        step = StepMetrics(
            step_number=2,
            capability="test.capability",
            status="failed",
            execution_time_ms=50.0,
            error_type="ValueError",
            retry_count=2
        )
        
        assert step.status == "failed"
        assert step.error_type == "ValueError"
        assert step.retry_count == 2


class TestSessionMetrics:
    """Тесты SessionMetrics."""

    def test_create_session_metrics(self):
        """Тест: создание метрик сессии."""
        metrics = SessionMetrics(
            session_id="test-session-123",
            goal="Test goal"
        )
        
        assert metrics.session_id == "test-session-123"
        assert metrics.goal == "Test goal"
        assert metrics.total_steps == 0
        assert metrics.successful_steps == 0
        assert metrics.failed_steps == 0

    def test_add_successful_step(self):
        """Тест: добавление успешного шага."""
        metrics = SessionMetrics(session_id="test", goal="test")
        
        step = StepMetrics(
            step_number=1,
            capability="test.capability",
            status="completed",
            execution_time_ms=100.0
        )
        metrics.add_step(step)
        
        assert metrics.total_steps == 1
        assert metrics.successful_steps == 1
        assert metrics.failed_steps == 0
        assert metrics.get_success_rate() == 1.0

    def test_add_failed_step(self):
        """Тест: добавление неудачного шага."""
        metrics = SessionMetrics(session_id="test", goal="test")
        
        step = StepMetrics(
            step_number=1,
            capability="test.capability",
            status="failed",
            execution_time_ms=50.0,
            error_type="ValueError"
        )
        metrics.add_step(step)
        
        assert metrics.total_steps == 1
        assert metrics.failed_steps == 1
        assert metrics.errors_by_type.get("ValueError") == 1

    def test_add_multiple_steps(self):
        """Тест: добавление нескольких шагов."""
        metrics = SessionMetrics(session_id="test", goal="test")
        
        for i in range(5):
            status = "completed" if i % 2 == 0 else "failed"
            step = StepMetrics(
                step_number=i+1,
                capability=f"test.capability.{i}",
                status=status,
                execution_time_ms=100.0
            )
            metrics.add_step(step)
        
        assert metrics.total_steps == 5
        assert metrics.successful_steps == 3  # 0, 2, 4
        assert metrics.failed_steps == 2  # 1, 3
        assert metrics.get_success_rate() == 0.6  # 3/5

    def test_add_pattern_switch(self):
        """Тест: запись переключения паттерна."""
        metrics = SessionMetrics(session_id="test", goal="test")
        
        metrics.add_pattern_switch()
        assert metrics.pattern_switches == 1
        
        metrics.add_pattern_switch()
        assert metrics.pattern_switches == 2

    def test_finalize(self):
        """Тест: завершение сессии."""
        metrics = SessionMetrics(session_id="test", goal="test")
        
        assert metrics.end_time is None
        
        metrics.finalize()
        
        assert metrics.end_time is not None

    def test_to_dict(self):
        """Тест: конвертация в словарь."""
        metrics = SessionMetrics(session_id="test", goal="test")
        
        step = StepMetrics(
            step_number=1,
            capability="test.capability",
            status="completed",
            execution_time_ms=100.0
        )
        metrics.add_step(step)
        metrics.finalize()
        
        data = metrics.to_dict()
        
        assert data["session_id"] == "test"
        assert data["goal"] == "test"
        assert data["total_steps"] == 1
        assert data["success_rate"] == 1.0
        assert "start_time" in data
        assert "end_time" in data


class TestMetricsCollector:
    """Тесты MetricsCollector."""

    def test_create_collector(self):
        """Тест: создание сборщика метрик."""
        collector = MetricsCollector(session_id="test-123")
        
        assert collector.session_id == "test-123"
        assert collector.event_bus is None
        assert collector.session_metrics is None

    def test_start_session(self):
        """Тест: начало сессии."""
        collector = MetricsCollector(session_id="test-123")
        
        collector.start_session(goal="Test goal")
        
        assert collector.session_metrics is not None
        assert collector.session_metrics.goal == "Test goal"
        assert len(collector.step_history) == 0

    def test_record_step(self):
        """Тест: запись шага."""
        collector = MetricsCollector(session_id="test-123")
        collector.start_session(goal="Test goal")
        
        collector.record_step(
            step_number=1,
            capability="test.capability",
            status="completed",
            execution_time_ms=150.5
        )
        
        assert len(collector.step_history) == 1
        assert collector.session_metrics.total_steps == 1

    def test_record_step_with_error(self):
        """Тест: запись шага с ошибкой."""
        collector = MetricsCollector(session_id="test-123")
        collector.start_session(goal="Test goal")
        
        collector.record_step(
            step_number=1,
            capability="test.capability",
            status="failed",
            execution_time_ms=50.0,
            error_type="ValueError",
            retry_count=2
        )
        
        step = collector.step_history[0]
        assert step.error_type == "ValueError"
        assert step.retry_count == 2
        assert collector.session_metrics.failed_steps == 1

    def test_record_pattern_switch(self):
        """Тест: запись переключения паттерна."""
        collector = MetricsCollector(session_id="test-123")
        collector.start_session(goal="Test goal")
        
        collector.record_pattern_switch(
            from_pattern="planning_pattern",
            to_pattern="react_pattern",
            reason="failure_memory_recommendation"
        )
        
        assert collector.session_metrics.pattern_switches == 1

    def test_end_session(self):
        """Тест: завершение сессии."""
        collector = MetricsCollector(session_id="test-123")
        collector.start_session(goal="Test goal")
        
        collector.end_session(final_status="completed")
        
        assert collector.session_metrics.end_time is not None

    def test_get_session_metrics(self):
        """Тест: получение метрик сессии."""
        collector = MetricsCollector(session_id="test-123")
        
        # До начала сессии
        assert collector.get_session_metrics() is None
        
        collector.start_session(goal="Test goal")
        metrics = collector.get_session_metrics()
        
        assert metrics is not None
        assert metrics.session_id == "test-123"

    def test_get_step_history(self):
        """Тест: получение истории шагов."""
        collector = MetricsCollector(session_id="test-123")
        collector.start_session(goal="Test goal")
        
        collector.record_step(1, "cap1", "completed", 100.0)
        collector.record_step(2, "cap2", "failed", 50.0)
        
        history = collector.get_step_history()
        
        assert len(history) == 2
        assert history[0].capability == "cap1"
        assert history[1].capability == "cap2"

    def test_get_summary(self):
        """Тест: получение сводки."""
        collector = MetricsCollector(session_id="test-123")
        
        # Пустая сводка
        assert collector.get_summary() == {}
        
        collector.start_session(goal="Test goal")
        collector.record_step(1, "cap1", "completed", 100.0)
        collector.record_step(2, "cap2", "completed", 100.0)
        
        summary = collector.get_summary()
        
        assert summary["total_steps"] == 2
        assert summary["success_rate"] == 1.0


class TestMetricsCollectorWithEventBus:
    """Тесты MetricsCollector с EventBus."""

    def test_publish_events(self):
        """Тест: публикация событий через EventBus."""
        event_bus = MagicMock()
        collector = MetricsCollector(session_id="test-123", event_bus=event_bus)
        
        collector.start_session(goal="Test goal")
        
        # Проверка вызова publish
        assert event_bus.publish.called
        call_args = event_bus.publish.call_args
        assert call_args[1]["event_type"] == "metrics.session_started"

    def test_publish_step_event(self):
        """Тест: публикация события шага."""
        event_bus = MagicMock()
        collector = MetricsCollector(session_id="test-123", event_bus=event_bus)
        collector.start_session(goal="Test goal")
        
        collector.record_step(1, "test.capability", "completed", 100.0)
        
        # Проверка вызова publish для шага
        assert event_bus.publish.call_count >= 2  # session_started + step_completed

    def test_publish_pattern_switch_event(self):
        """Тест: публикация события переключения паттерна."""
        event_bus = MagicMock()
        collector = MetricsCollector(session_id="test-123", event_bus=event_bus)
        collector.start_session(goal="Test goal")
        
        collector.record_pattern_switch("planning", "react", "test")
        
        # Проверка вызова publish
        publish_calls = [call for call in event_bus.publish.call_args_list 
                        if call[1]["event_type"] == "metrics.pattern_switched"]
        assert len(publish_calls) == 1

    def test_publish_session_end_event(self):
        """Тест: публикация события завершения сессии."""
        event_bus = MagicMock()
        collector = MetricsCollector(session_id="test-123", event_bus=event_bus)
        collector.start_session(goal="Test goal")
        collector.end_session(final_status="completed")
        
        # Проверка вызова publish для завершения
        publish_calls = [call for call in event_bus.publish.call_args_list 
                        if call[1]["event_type"] == "metrics.session_completed"]
        assert len(publish_calls) == 1

    def test_ignore_event_bus_errors(self):
        """Тест: игнорирование ошибок EventBus."""
        event_bus = MagicMock()
        event_bus.publish.side_effect = Exception("EventBus error")
        
        collector = MetricsCollector(session_id="test-123", event_bus=event_bus)
        
        # Не должно выбрасывать исключение
        collector.start_session(goal="Test goal")
        collector.record_step(1, "test.capability", "completed", 100.0)
        collector.end_session(final_status="completed")


class TestMetricsCollectorIntegration:
    """Интеграционные тесты."""

    def test_full_session_workflow(self):
        """Тест: полный цикл сессии."""
        collector = MetricsCollector(session_id="integration-test")
        
        # 1. Начало сессии
        collector.start_session(goal="Найти книги Пушкина")
        
        # 2. Запись шагов
        collector.record_step(1, "book_library.execute_script", "completed", 150.5)
        collector.record_step(2, "final_answer.generate", "completed", 200.0)
        
        # 3. Завершение сессии
        collector.end_session(final_status="completed")
        
        # 4. Проверка метрик
        metrics = collector.get_session_metrics()
        assert metrics.total_steps == 2
        assert metrics.successful_steps == 2
        assert metrics.get_success_rate() == 1.0
        
        summary = collector.get_summary()
        assert summary["total_steps"] == 2
        assert summary["success_rate"] == 1.0

    def test_session_with_errors(self):
        """Тест: сессия с ошибками."""
        collector = MetricsCollector(session_id="error-test")
        collector.start_session(goal="Test with errors")
        
        collector.record_step(1, "cap1", "completed", 100.0)
        collector.record_step(2, "cap2", "failed", 50.0, error_type="ValueError")
        collector.record_step(3, "cap3", "failed", 30.0, error_type="TimeoutError")
        collector.record_step(4, "cap4", "completed", 120.0)
        
        collector.end_session(final_status="completed")
        
        metrics = collector.get_session_metrics()
        assert metrics.total_steps == 4
        assert metrics.successful_steps == 2
        assert metrics.failed_steps == 2
        assert metrics.errors_by_type.get("ValueError") == 1
        assert metrics.errors_by_type.get("TimeoutError") == 1
        assert metrics.get_success_rate() == 0.5

    def test_session_with_pattern_switches(self):
        """Тест: сессия с переключениями паттернов."""
        collector = MetricsCollector(session_id="switch-test")
        collector.start_session(goal="Test with switches")
        
        collector.record_step(1, "cap1", "completed", 100.0)
        collector.record_pattern_switch("planning", "react", "failure")
        collector.record_step(2, "cap2", "completed", 150.0)
        collector.record_pattern_switch("react", "evaluation", "request")
        
        collector.end_session(final_status="completed")
        
        metrics = collector.get_session_metrics()
        assert metrics.pattern_switches == 2
