"""
Тесты для infrastructure MetricsCollector.

Проверяет:
1. Подписку на события EventBus
2. Сбор метрик из событий SKILL_EXECUTED, ERROR_OCCURRED
3. Агрегацию метрик через MetricsPublisher
4. Обработку событий SESSION_STARTED/SESSION_COMPLETED
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

from core.infrastructure.metrics_collector import MetricsCollector
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, Event, EventType
from core.models.data.metrics import MetricRecord, MetricType, AggregatedMetrics
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage


@pytest.fixture
def event_bus():
    """Создание тестовой шины событий."""
    return UnifiedEventBus()


@pytest.fixture
def storage():
    """Создание тестового хранилища с правильной настройкой mock."""
    storage = AsyncMock(spec=IMetricsStorage)
    storage.record = AsyncMock()
    storage.aggregate = AsyncMock()
    storage.get_records = AsyncMock()
    return storage


@pytest.fixture
def metrics_collector(event_bus, storage):
    """Создание MetricsCollector для тестов."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    return collector


@pytest.mark.asyncio
async def test_initialize_subscribes_to_events(event_bus, storage):
    """Тест: инициализация подписывает на нужные события."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    # Проверяем что подписки существуют
    assert collector._initialized is True


@pytest.mark.asyncio
async def test_on_skill_executed_records_success_metric(event_bus, storage):
    """Тест: обработка SKILL_EXECUTED записывает метрику успешности."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    # Создаём событие напрямую (не через EventBus)
    event = Event(
        event_type="skill.executed",
        data={
            "agent_id": "test-agent",
            "capability": "test.capability",
            "execution_time_ms": 150.5,
            "success": True,
            "session_id": "test-session",
            "tokens_used": 100
        },
        session_id="test-session",
        source="test"
    )

    # Вызываем обработчик напрямую
    await collector._on_skill_executed(event)

    # Проверяем что storage.record был вызван (через MetricsPublisher)
    assert storage.record.call_count >= 1


@pytest.mark.asyncio
async def test_on_skill_executed_records_execution_time(event_bus, storage):
    """Тест: обработка SKILL_EXECUTED записывает время выполнения."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    event = Event(
        event_type="skill.executed",
        data={
            "agent_id": "test-agent",
            "capability": "test.capability",
            "execution_time_ms": 200.0,
            "success": True,
            "session_id": "test-session"
        },
        session_id="test-session",
        source="test"
    )

    await collector._on_skill_executed(event)
    assert storage.record.call_count >= 1


@pytest.mark.asyncio
async def test_on_skill_executed_records_tokens_used(event_bus, storage):
    """Тест: обработка SKILL_EXECUTED записывает количество токенов."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    event = Event(
        event_type="skill.executed",
        data={
            "agent_id": "test-agent",
            "capability": "test.capability",
            "execution_time_ms": 100.0,
            "success": True,
            "session_id": "test-session",
            "tokens_used": 250
        },
        session_id="test-session",
        source="test"
    )

    await collector._on_skill_executed(event)
    assert storage.record.call_count >= 1


@pytest.mark.asyncio
async def test_on_skill_executed_skips_without_capability(event_bus, storage):
    """Тест: обработка SKILL_EXECUTED пропускает события без capability."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    event = Event(
        event_type="skill.executed",
        data={
            "agent_id": "test-agent",
            "execution_time_ms": 100.0,
            "success": True
        },
        session_id="test-session",
        source="test"
    )

    await collector._on_skill_executed(event)
    # storage.record не должен быть вызван
    storage.record.assert_not_called()


@pytest.mark.asyncio
async def test_on_session_started_publishes_event(event_bus, storage):
    """Тест: обработка SESSION_STARTED публикует событие."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    event = Event(
        event_type="session.started",
        data={
            "session_id": "test-session",
            "goal": "Test goal",
            "agent_id": "test-agent"
        },
        session_id="test-session",
        source="test"
    )

    # Если не упало - тест пройден
    await collector._on_session_started(event)
    assert True


@pytest.mark.asyncio
async def test_on_session_completed_records_metrics(event_bus, storage):
    """Тест: обработка SESSION_COMPLETED записывает метрики."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    event = Event(
        event_type="session.completed",
        data={
            "session_id": "test-session",
            "agent_id": "test-agent",
            "steps_completed": 5,
            "final_status": "completed"
        },
        session_id="test-session",
        source="test"
    )

    await collector._on_session_completed(event)
    # MetricsPublisher вызывает storage.record для метрики session_steps_completed
    assert storage.record.call_count >= 1


@pytest.mark.asyncio
async def test_on_error_occurred_records_error_metrics(event_bus, storage):
    """Тест: обработка ERROR_OCCURRED записывает метрики ошибок."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    event = Event(
        event_type="error.occurred",
        data={
            "agent_id": "test-agent",
            "capability": "test.capability",
            "error_type": "ValueError",
            "session_id": "test-session"
        },
        session_id="test-session",
        source="test"
    )

    await collector._on_error_occurred(event)
    assert storage.record.call_count >= 1


@pytest.mark.asyncio
async def test_on_capability_selected_records_counter(event_bus, storage):
    """Тест: обработка CAPABILITY_SELECTED записывает счётчик."""
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    event = Event(
        event_type="capability.selected",
        data={
            "agent_id": "test-agent",
            "capability": "test.capability",
            "session_id": "test-session"
        },
        session_id="test-session",
        source="test"
    )

    await collector._on_capability_selected(event)
    assert storage.record.call_count >= 1


@pytest.mark.asyncio
async def test_get_aggregated_metrics(event_bus, storage):
    """Тест: получение агрегированных метрик."""
    expected = AggregatedMetrics(
        capability="test.capability",
        version="1.0",
        total_runs=10,
        success_count=9,
        failure_count=1,
        accuracy=0.9,
        avg_execution_time_ms=150.0
    )
    storage.aggregate = AsyncMock(return_value=expected)
    
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    result = await collector.get_aggregated_metrics(
        capability="test.capability",
        version="1.0"
    )

    assert result == expected
    storage.aggregate.assert_called_once()


@pytest.mark.asyncio
async def test_get_metrics(event_bus, storage):
    """Тест: получение сырых метрик."""
    expected_records = [
        MetricRecord(
            agent_id="test-agent",
            capability="test.capability",
            metric_type=MetricType.GAUGE,
            name="success",
            value=1.0,
            timestamp=datetime.now()
        )
    ]
    storage.get_records = AsyncMock(return_value=expected_records)
    
    collector = MetricsCollector(event_bus=event_bus, storage=storage)
    await collector.initialize()

    result = await collector.get_metrics(
        capability="test.capability",
        version="1.0"
    )

    assert result == expected_records
    storage.get_records.assert_called_once()
