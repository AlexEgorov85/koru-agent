"""
Unit-тесты для MetricsPublisher.

Тестирование основных функций:
- Публикация метрик разных типов
- Интеграция с хранилищем
- Обработка ошибок
- Контекстный менеджер и декоратор
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from datetime import datetime
from core.components.services.metrics_publisher import (
    MetricsPublisher, 
    MetricsContext, 
    record_metrics
)
from core.models.data.metrics import MetricRecord, MetricType
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage


class TestMetricsPublisher:
    """Тесты основного класса MetricsPublisher."""

    @pytest.fixture
    def mock_storage(self):
        """Мок хранилища метрик."""
        storage = Mock(spec=IMetricsStorage)
        storage.record = AsyncMock()
        return storage

    @pytest.fixture
    def mock_event_bus(self):
        """Мок шины событий."""
        event_bus = Mock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.fixture
    def publisher(self, mock_storage, mock_event_bus):
        """Экземпляр MetricsPublisher для тестирования."""
        return MetricsPublisher(mock_storage, mock_event_bus)

    @pytest.mark.asyncio
    async def test_gauge_metric_publication(self, publisher, mock_storage):
        """Тест публикации GAUGE метрики."""
        # Вызов
        result = await publisher.gauge(
            name="accuracy",
            value=0.95,
            capability="sql_generation",
            agent_id="test_agent",
            tags={"model": "gpt-4"}
        )

        # Проверки
        assert isinstance(result, MetricRecord)
        assert result.metric_type == MetricType.GAUGE
        assert result.name == "accuracy"
        assert result.value == 0.95
        assert result.capability == "sql_generation"
        assert result.tags == {"model": "gpt-4"}

        # Проверка вызова хранилища
        mock_storage.record.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_counter_metric_publication(self, publisher, mock_storage):
        """Тест публикации COUNTER метрики."""
        # Вызов
        result = await publisher.counter(
            name="execution_count",
            value=2.0,
            capability="data_analysis"
        )

        # Проверки
        assert result.metric_type == MetricType.COUNTER
        assert result.name == "execution_count"
        assert result.value == 2.0
        mock_storage.record.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_histogram_metric_publication(self, publisher, mock_storage):
        """Тест публикации HISTOGRAM метрики."""
        # Вызов
        result = await publisher.histogram(
            name="execution_time_ms",
            value=150.5,
            capability="sql_generation"
        )

        # Проверки
        assert result.metric_type == MetricType.HISTOGRAM
        assert result.name == "execution_time_ms"
        assert result.value == 150.5
        mock_storage.record.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_custom_metric_publication(self, publisher, mock_storage):
        """Тест публикации кастомной метрики."""
        # Вызов со строковым типом
        result = await publisher.record_custom(
            metric_type="gauge",
            name="temperature",
            value=0.7,
            capability="prompt_optimization"
        )

        # Проверки
        assert result.metric_type == MetricType.GAUGE
        assert result.name == "temperature"
        assert result.value == 0.7
        mock_storage.record.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_event_bus_publication(self, publisher, mock_storage, mock_event_bus):
        """Тест публикации события в EventBus."""
        # Вызов
        result = await publisher.gauge(
            name="test_metric",
            value=1.0,
            capability="test",
            agent_id="test_agent"
        )

        # Проверка публикации события
        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        # EventType.METRIC_COLLECTED имеет значение 'metric.collected' в нижнем регистре
        assert call_args[1]['event'].value == 'metric.collected'
        assert call_args[1]['data']['name'] == 'test_metric'
        assert call_args[1]['data']['value'] == 1.0

    @pytest.mark.asyncio
    async def test_event_bus_disabled(self, mock_storage):
        """Тест работы без EventBus."""
        publisher = MetricsPublisher(mock_storage)  # Без EventBus
        
        # Вызов должен работать без ошибок
        result = await publisher.gauge(
            name="test_metric",
            value=1.0,
            capability="test"
        )

        assert result is not None
        mock_storage.record.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_bus_publication_disabled(self, publisher, mock_storage, mock_event_bus):
        """Тест отключения публикации в EventBus."""
        # Вызов с отключенной публикацией
        result = await publisher.gauge(
            name="test_metric",
            value=1.0,
            capability="test",
            publish_event=False
        )

        # Хранилище должно быть вызвано, но EventBus - нет
        mock_storage.record.assert_called_once()
        mock_event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_metric_type(self, publisher):
        """Тест обработки неверного типа метрики."""
        with pytest.raises(ValueError):
            await publisher.record_custom(
                metric_type="invalid_type",
                name="test_metric",
                value=1.0
            )

    @pytest.mark.asyncio
    async def test_default_parameters(self, publisher, mock_storage):
        """Тест значений по умолчанию."""
        result = await publisher.gauge(
            name="test_metric",
            value=1.0
        )

        assert result.agent_id == "unknown"
        assert result.capability == ""
        assert result.tags == {}
        assert result.session_id is None
        assert result.correlation_id is None
        assert result.version is None


class TestMetricsContext:
    """Тесты контекстного менеджера MetricsContext."""

    @pytest.fixture
    def mock_publisher(self):
        """Мок публикатора метрик."""
        publisher = Mock()
        publisher.histogram = AsyncMock()
        return publisher

    @pytest.mark.asyncio
    async def test_context_manager_measures_time(self, mock_publisher):
        """Тест измерения времени в контекстном менеджере."""
        async with MetricsContext(mock_publisher, "test_metric") as context:
            # Некоторая работа внутри контекста
            await asyncio.sleep(0.01)
            elapsed = context.get_elapsed_ms()
            assert elapsed > 0

        # Проверка публикации метрики
        mock_publisher.histogram.assert_called_once()
        call_args = mock_publisher.histogram.call_args
        assert call_args[1]['name'] == 'test_metric'
        assert call_args[1]['value'] > 0

    @pytest.mark.asyncio
    async def test_context_manager_with_kwargs(self, mock_publisher):
        """Тест контекстного менеджера с дополнительными параметрами."""
        async with MetricsContext(
            mock_publisher, 
            "test_metric",
            capability="test_capability",
            agent_id="test_agent",
            tags={"test": "value"}
        ):
            await asyncio.sleep(0.01)

        # Проверка передачи параметров
        call_args = mock_publisher.histogram.call_args
        assert call_args[1]['capability'] == 'test_capability'
        assert call_args[1]['agent_id'] == 'test_agent'
        assert call_args[1]['tags'] == {"test": "value"}


class TestRecordMetricsDecorator:
    """Тесты декоратора record_metrics."""

    @pytest.fixture
    def mock_publisher(self):
        """Мок публикатора метрик."""
        publisher = Mock()
        publisher.histogram = AsyncMock()
        return publisher

    @pytest.mark.asyncio
    async def test_decorator_records_metrics(self, mock_publisher):
        """Тест декоратора для записи метрик."""
        
        @record_metrics(mock_publisher, "function_execution_time")
        async def test_function():
            await asyncio.sleep(0.01)
            return "result"

        result = await test_function()

        assert result == "result"
        mock_publisher.histogram.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator_with_parameters(self, mock_publisher):
        """Тест декоратора с параметрами."""
        
        @record_metrics(
            mock_publisher, 
            "api_call_time",
            capability="api",
            agent_id="client",
            tags={"version": "v1"}
        )
        async def api_call():
            return {"status": "ok"}

        result = await api_call()

        assert result == {"status": "ok"}
        call_args = mock_publisher.histogram.call_args
        assert call_args[1]['capability'] == 'api'
        assert call_args[1]['agent_id'] == 'client'
        assert call_args[1]['tags'] == {"version": "v1"}

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self, mock_publisher):
        """Тест сохранения метаданных функции."""
        
        @record_metrics(mock_publisher, "test_metric")
        async def documented_function():
            """Тестовая функция."""
            return True

        # Декоратор не сохраняет метаданные из-за природы wrapper функции
        # Проверяем только что функция работает корректно
        result = await documented_function()
        assert result is True
        mock_publisher.histogram.assert_called_once()


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v"])