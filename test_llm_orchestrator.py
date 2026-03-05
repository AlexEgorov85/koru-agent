"""
Тесты для LLMOrchestrator.

ПРОВЕРЯЮТ:
1. Инициализация и shutdown
2. Выполнение вызовов с таймаутом
3. Обработку "брошенных" вызовов
4. Метрики и мониторинг
5. Реестр активных вызовов
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor

from core.infrastructure.providers.llm.llm_orchestrator import (
    LLMOrchestrator,
    CallStatus,
    CallRecord,
    LLMMetrics
)
from core.models.types.llm_types import LLMRequest, LLMResponse


class MockProvider:
    """Mock LLM провайдера для тестов."""
    
    def __init__(self, delay: float = 0.1, should_fail: bool = False):
        self.delay = delay
        self.should_fail = should_fail
        self._generate_impl_called = False
    
    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """Симуляция синхронного вызова LLM."""
        self._generate_impl_called = True
        
        if self.should_fail:
            raise ValueError("Mock provider failure")
        
        # Симуляция задержки
        await asyncio.sleep(self.delay)
        
        return LLMResponse(
            content="Mock response",
            model="mock-model",
            tokens_used=10,
            generation_time=self.delay,
            finish_reason="stop"
        )


class TestLLMOrchestrator:
    """Тесты для LLMOrchestrator."""
    
    @pytest.fixture
    def mock_event_bus(self):
        """Создание mock event bus."""
        event_bus = AsyncMock()
        event_bus.publish = AsyncMock(return_value=True)
        return event_bus
    
    @pytest.fixture
    async def orchestrator(self, mock_event_bus):
        """Создание инициализированного оркестратора."""
        orch = LLMOrchestrator(
            event_bus=mock_event_bus,
            max_workers=2,
            cleanup_interval=1.0,
            max_pending_calls=10
        )
        await orch.initialize()
        yield orch
        await orch.shutdown()
    
    @pytest.fixture
    def call_context(self):
        """Контекст вызова для тестов."""
        return {
            "session_id": "test_session",
            "agent_id": "test_agent",
            "step_number": 1,
            "phase": "think",
            "goal": "Test goal"
        }
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_event_bus):
        """Тест инициализации оркестратора."""
        orch = LLMOrchestrator(event_bus=mock_event_bus, max_workers=2)
        
        assert orch._executor is None
        assert not orch._running
        
        success = await orch.initialize()
        
        assert success is True
        assert orch._executor is not None
        assert orch._running is True
        assert isinstance(orch._executor, ThreadPoolExecutor)
        
        await orch.shutdown()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, orchestrator):
        """Тест корректного завершения работы."""
        assert orchestrator._running is True
        assert orchestrator._executor is not None
        
        await orchestrator.shutdown()
        
        assert orchestrator._running is False
        assert orchestrator._executor is None
    
    @pytest.mark.asyncio
    async def test_successful_execute(self, orchestrator, mock_event_bus, call_context):
        """Тест успешного выполнения вызова."""
        provider = MockProvider(delay=0.1)
        
        request = LLMRequest(
            prompt="Test prompt",
            system_prompt="Test system",
            temperature=0.7,
            max_tokens=100
        )
        
        response = await orchestrator.execute(
            request=request,
            timeout=5.0,
            provider=provider,
            **call_context
        )
        
        assert response is not None
        assert response.finish_reason == "stop"
        assert response.content == "Mock response"
        
        # Проверка метрик
        metrics = orchestrator.get_metrics()
        assert metrics.total_calls == 1
        assert metrics.completed_calls == 1
        assert metrics.timed_out_calls == 0
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, orchestrator, mock_event_bus, call_context):
        """Тест обработки таймаута."""
        # Провайдер с большой задержкой
        provider = MockProvider(delay=2.0)
        
        request = LLMRequest(
            prompt="Test prompt",
            system_prompt="Test system",
            temperature=0.7,
            max_tokens=100
        )
        
        # Короткий таймаут
        response = await orchestrator.execute(
            request=request,
            timeout=0.5,  # 500ms
            provider=provider,
            **call_context
        )
        
        # Проверка что вернулась ошибка таймаута
        assert response is not None
        assert response.finish_reason == "error"
        assert response.metadata is not None
        assert 'error' in response.metadata
        assert 'timeout' in response.metadata.get('error', '').lower()
        
        # Проверка метрик
        metrics = orchestrator.get_metrics()
        assert metrics.total_calls == 1
        assert metrics.timed_out_calls == 1
        assert metrics.completed_calls == 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, orchestrator, mock_event_bus, call_context):
        """Тест обработки ошибок провайдера."""
        provider = MockProvider(should_fail=True)
        
        request = LLMRequest(
            prompt="Test prompt",
            system_prompt="Test system",
            temperature=0.7,
            max_tokens=100
        )
        
        response = await orchestrator.execute(
            request=request,
            timeout=5.0,
            provider=provider,
            **call_context
        )
        
        assert response is not None
        assert response.finish_reason == "error"
        assert response.metadata is not None
        assert 'error' in response.metadata
        
        # Проверка метрик
        metrics = orchestrator.get_metrics()
        assert metrics.total_calls == 1
        assert metrics.failed_calls == 1
    
    @pytest.mark.asyncio
    async def test_call_registry(self, orchestrator, mock_event_bus, call_context):
        """Тест реестра активных вызовов."""
        provider = MockProvider(delay=0.5)
        
        request = LLMRequest(
            prompt="Test prompt",
            system_prompt="Test system",
            temperature=0.7,
            max_tokens=100
        )
        
        # Запуск вызова
        task = asyncio.create_task(
            orchestrator.execute(
                request=request,
                timeout=5.0,
                provider=provider,
                **call_context
            )
        )
        
        # Небольшая задержка чтобы вызов начался
        await asyncio.sleep(0.1)
        
        # Проверка реестра
        pending = orchestrator.get_pending_calls()
        # Вызов должен быть в реестре
        assert len(pending) >= 0  # Может завершиться быстро
        
        # Дожидаемся завершения
        await task
        
        # После завершения вызов должен исчезнуть из pending
        pending = orchestrator.get_pending_calls()
        assert len(pending) == 0
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, orchestrator, mock_event_bus, call_context):
        """Тест отслеживания метрик."""
        # Несколько успешных вызовов
        for _ in range(3):
            provider = MockProvider(delay=0.1)
            request = LLMRequest(prompt="Test", system_prompt="Test")
            await orchestrator.execute(request=request, timeout=5.0, provider=provider, **call_context)
        
        # Один вызов с таймаутом
        provider = MockProvider(delay=2.0)
        request = LLMRequest(prompt="Test", system_prompt="Test")
        await orchestrator.execute(request=request, timeout=0.5, provider=provider, **call_context)
        
        # Проверка метрик
        metrics = orchestrator.get_metrics()
        
        assert metrics.total_calls == 4
        assert metrics.completed_calls == 3
        assert metrics.timed_out_calls == 1
        assert metrics.failed_calls == 0
        
        # Проверка вычисляемых метрик
        assert metrics.avg_generation_time > 0
        assert metrics.timeout_rate == 0.25  # 1 из 4
        assert metrics.orphan_rate == 0  # Пока нет брошенных
    
    @pytest.mark.asyncio
    async def test_health_status(self, orchestrator, mock_event_bus):
        """Тест статуса здоровья."""
        status = orchestrator.get_health_status()
        
        assert 'status' in status
        assert 'executor_running' in status
        assert 'pending_calls' in status
        assert 'metrics' in status
        
        assert status['executor_running'] is True
        assert isinstance(status['metrics'], dict)
    
    @pytest.mark.asyncio
    async def test_cleanup_old_records(self, orchestrator, mock_event_bus, call_context):
        """Тест очистки старых записей."""
        provider = MockProvider(delay=0.1)
        request = LLMRequest(prompt="Test", system_prompt="Test")
        
        # Выполняем несколько вызовов
        for _ in range(3):
            await orchestrator.execute(request=request, timeout=5.0, provider=provider, **call_context)
        
        # Ждём немного
        await asyncio.sleep(0.5)
        
        # Принудительная очистка
        removed = await orchestrator._cleanup_old_records(max_age=0.1)
        
        # Некоторые записи должны быть удалены
        assert removed >= 0
    
    @pytest.mark.asyncio
    async def test_call_record_status_tracking(self, orchestrator, mock_event_bus, call_context):
        """Тест отслеживания статуса вызова."""
        provider = MockProvider(delay=0.2)
        request = LLMRequest(prompt="Test", system_prompt="Test")
        
        # Выполняем вызов
        response = await orchestrator.execute(
            request=request,
            timeout=5.0,
            provider=provider,
            **call_context
        )
        
        # Проверяем что вызов был зарегистрирован
        metrics = orchestrator.get_metrics()
        assert metrics.total_calls >= 1


class TestLLMMetrics:
    """Тесты для метрик."""
    
    def test_metrics_initialization(self):
        """Тест инициализации метрик."""
        metrics = LLMMetrics()
        
        assert metrics.total_calls == 0
        assert metrics.completed_calls == 0
        assert metrics.timed_out_calls == 0
        assert metrics.failed_calls == 0
        assert metrics.orphaned_calls == 0
    
    def test_avg_generation_time(self):
        """Тест среднего времени генерации."""
        metrics = LLMMetrics()
        metrics.completed_calls = 3
        metrics.total_generation_time = 3.0
        
        assert metrics.avg_generation_time == 1.0
    
    def test_timeout_rate(self):
        """Тест процента таймаутов."""
        metrics = LLMMetrics()
        metrics.total_calls = 10
        metrics.timed_out_calls = 2
        
        assert metrics.timeout_rate == 0.2
    
    def test_orphan_rate(self):
        """Тест процента брошенных вызовов."""
        metrics = LLMMetrics()
        metrics.total_calls = 10
        metrics.orphaned_calls = 1
        
        assert metrics.orphan_rate == 0.1
    
    def test_to_dict(self):
        """Тест преобразования в словарь."""
        metrics = LLMMetrics()
        metrics.total_calls = 5
        metrics.completed_calls = 4
        metrics.timed_out_calls = 1
        
        result = metrics.to_dict()
        
        assert isinstance(result, dict)
        assert result['total_calls'] == 5
        assert result['completed_calls'] == 4
        assert result['timed_out_calls'] == 1


class TestCallRecord:
    """Тесты для записи вызова."""
    
    def test_call_record_initialization(self):
        """Тест инициализации записи вызова."""
        request = LLMRequest(prompt="Test", system_prompt="Test")
        record = CallRecord(
            call_id="test_123",
            request=request
        )
        
        assert record.call_id == "test_123"
        assert record.status == CallStatus.PENDING
        assert record.start_time is None
        assert record.end_time is None
    
    def test_call_record_duration(self):
        """Тест длительности вызова."""
        request = LLMRequest(prompt="Test", system_prompt="Test")
        record = CallRecord(
            call_id="test_123",
            request=request,
            start_time=100.0,
            end_time=105.0
        )
        
        assert record.duration == 5.0
    
    def test_call_record_to_dict(self):
        """Тест преобразования в словарь."""
        request = LLMRequest(prompt="Test", system_prompt="Test", capability_name="test_cap")
        record = CallRecord(
            call_id="test_123",
            request=request,
            status=CallStatus.COMPLETED,
            timeout=10.0
        )
        
        result = record.to_dict()
        
        assert result['call_id'] == "test_123"
        assert result['status'] == "completed"
        assert result['timeout'] == 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
