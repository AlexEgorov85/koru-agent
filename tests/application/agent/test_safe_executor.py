"""
Тесты для SafeExecutor.

Проверяет:
1. Успешное выполнение действий
2. Обработку TRANSIENT ошибок с retry
3. Обработку LOGIC ошибок (switch pattern)
4. Обработку VALIDATION ошибок (abort)
5. Обработку FATAL ошибок (fail immediately)
6. Запись в FailureMemory
7. Экспоненциальную задержку с jitter
8. Сброс FailureMemory при успехе
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.common_enums import ErrorCategory, ErrorType
from core.agent.components.safe_executor import SafeExecutor
from core.agent.components.failure_memory import FailureMemory
from core.agent.components.action_executor import ActionExecutor, ExecutionContext


class MockActionExecutor:
    """Мок ActionExecutor для тестов."""
    
    def __init__(self):
        self.call_count = 0
        self.behavior = "success"  # success, transient_error, logic_error, etc.
        self.error_to_raise = None
    
    async def execute_action(self, action_name, parameters, context):
        self.call_count += 1
        
        if self.error_to_raise:
            raise self.error_to_raise
        
        if self.behavior == "success":
            return ExecutionResult.success(data={"result": "ok"})
        elif self.behavior == "transient_error":
            raise TimeoutError("Connection timeout")
        elif self.behavior == "logic_error":
            raise Exception("Unexpected result format")
        elif self.behavior == "validation_error":
            raise ValueError("Invalid parameter: required field missing")
        elif self.behavior == "fatal_error":
            raise RuntimeError("Fatal error: system corrupt")
        elif self.behavior == "flaky":
            # Успех только после 2 попыток
            if self.call_count >= 2:
                return ExecutionResult.success(data={"result": "ok after retry"})
            raise TimeoutError("Temporary failure")
        
        return ExecutionResult.success(data={"result": "ok"})


class TestSafeExecutorInitialization:
    """Тесты инициализации SafeExecutor."""

    def test_init_with_defaults(self):
        """Тест: инициализация с параметрами по умолчанию."""
        executor = MockActionExecutor()
        failure_memory = FailureMemory()
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory
        )
        
        assert safe_executor.executor is executor
        assert safe_executor.failure_memory is failure_memory
        assert safe_executor.max_retries == 3
        assert safe_executor.base_delay == 0.5
        assert safe_executor.max_delay == 5.0
        assert safe_executor.jitter is True

    def test_init_with_custom_params(self):
        """Тест: инициализация с кастомными параметрами."""
        executor = MockActionExecutor()
        failure_memory = FailureMemory()
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory,
            max_retries=5,
            base_delay=1.0,
            max_delay=10.0,
            jitter=False
        )
        
        assert safe_executor.max_retries == 5
        assert safe_executor.base_delay == 1.0
        assert safe_executor.max_delay == 10.0
        assert safe_executor.jitter is False


class TestSafeExecutorSuccess:
    """Тесты успешного выполнения."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Тест: успешное выполнение с первой попытки."""
        executor = MockActionExecutor()
        executor.behavior = "success"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory()
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={"param": "value"},
            context=context
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert result.data == {"result": "ok"}
        assert result.error is None
        assert executor.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_success_after_retry(self):
        """Тест: успех после retry (flaky сервис)."""
        executor = MockActionExecutor()
        executor.behavior = "flaky"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            max_retries=3,
            base_delay=0.01  # Быстрая задержка для тестов
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={"param": "value"},
            context=context
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert executor.call_count == 2  # 2 попытки
        assert result.metadata.get("retry_count") == 1

    @pytest.mark.asyncio
    async def test_failure_memory_reset_on_success(self):
        """Тест: FailureMemory сбрасывается при успехе."""
        executor = MockActionExecutor()
        executor.behavior = "success"
        failure_memory = FailureMemory()
        
        # Предварительно записываем ошибку
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
            timestamp=datetime.now()
        )
        
        assert failure_memory.get_count("test.capability") == 1
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        # После успеха failure memory сброшена
        assert failure_memory.get_count("test.capability") == 0


class TestSafeExecutorTransientErrors:
    """Тесты обработки TRANSIENT ошибок."""

    @pytest.mark.asyncio
    async def test_transient_error_retry(self):
        """Тест: TRANSIENT ошибка вызывает retry."""
        executor = MockActionExecutor()
        executor.behavior = "transient_error"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            max_retries=3,
            base_delay=0.01  # Быстрая задержка для тестов
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        # Все попытки исчерпаны
        assert result.status == ExecutionStatus.FAILED
        assert executor.call_count == 3  # 3 попытки
        assert result.metadata.get("error_type") == "transient"
        assert result.metadata.get("recommendation") == "max_retries_exceeded"

    @pytest.mark.asyncio
    async def test_transient_error_records_in_failure_memory(self):
        """Тест: TRANSIENT ошибка записывается в FailureMemory."""
        executor = MockActionExecutor()
        executor.behavior = "transient_error"
        failure_memory = FailureMemory()
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory,
            max_retries=1,  # Только 1 попытка
            base_delay=0.01
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        assert result.status == ExecutionStatus.FAILED
        # Ошибка записана в FailureMemory
        assert failure_memory.get_count("test.capability", ErrorType.TRANSIENT) == 1


class TestSafeExecutorLogicErrors:
    """Тесты обработки LOGIC ошибок."""

    @pytest.mark.asyncio
    async def test_logic_error_no_retry(self):
        """Тест: LOGIC ошибка не вызывает retry."""
        executor = MockActionExecutor()
        executor.behavior = "logic_error"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            max_retries=3,
            base_delay=0.01
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        # Только 1 попытка (нет retry для LOGIC ошибок)
        assert result.status == ExecutionStatus.FAILED
        assert executor.call_count == 1
        assert result.metadata.get("error_type") == "logic"
        assert result.metadata.get("recommendation") == "switch_pattern"

    @pytest.mark.asyncio
    async def test_logic_error_records_in_failure_memory(self):
        """Тест: LOGIC ошибка записывается в FailureMemory."""
        executor = MockActionExecutor()
        executor.behavior = "logic_error"
        failure_memory = FailureMemory()
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory,
            max_retries=1
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        assert failure_memory.get_count("test.capability", ErrorType.LOGIC) == 1
        assert result.metadata.get("should_switch_pattern") is False  # Пока только 1 ошибка


class TestSafeExecutorValidationErrors:
    """Тесты обработки VALIDATION ошибок."""

    @pytest.mark.asyncio
    async def test_validation_error_no_retry(self):
        """Тест: VALIDATION ошибка не вызывает retry."""
        executor = MockActionExecutor()
        executor.behavior = "validation_error"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            max_retries=3,
            base_delay=0.01
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        # Только 1 попытка (нет retry для VALIDATION ошибок)
        assert result.status == ExecutionStatus.FAILED
        assert executor.call_count == 1
        assert result.metadata.get("error_type") == "validation"
        assert result.metadata.get("recommendation") == "abort_and_log"


class TestSafeExecutorFatalErrors:
    """Тесты обработки FATAL ошибок."""

    @pytest.mark.asyncio
    async def test_fatal_error_immediate_fail(self):
        """Тест: FATAL ошибка вызывает немедленный fail."""
        executor = MockActionExecutor()
        executor.behavior = "fatal_error"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            max_retries=3,
            base_delay=0.01
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        # Только 1 попытка (нет retry для FATAL ошибок)
        assert result.status == ExecutionStatus.FAILED
        assert executor.call_count == 1
        assert result.metadata.get("error_type") == "fatal"
        assert result.metadata.get("recommendation") == "fail_immediately"


class TestSafeExecutorDelayCalculation:
    """Тесты расчёта задержек."""

    def test_calculate_delay_exponential(self):
        """Тест: экспоненциальная задержка."""
        executor = MockActionExecutor()
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            base_delay=0.5,
            max_delay=10.0,
            jitter=False
        )
        
        # Проверка экспоненциального увеличения
        assert safe_executor._calculate_delay(0) == 0.5  # 0.5 * 2^0
        assert safe_executor._calculate_delay(1) == 1.0  # 0.5 * 2^1
        assert safe_executor._calculate_delay(2) == 2.0  # 0.5 * 2^2
        assert safe_executor._calculate_delay(3) == 4.0  # 0.5 * 2^3

    def test_calculate_delay_max_cap(self):
        """Тест: ограничение максимальной задержки."""
        executor = MockActionExecutor()
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            base_delay=1.0,
            max_delay=5.0,
            jitter=False
        )
        
        # После 10 попытки задержка должна быть ограничена max_delay
        delay = safe_executor._calculate_delay(10)
        assert delay == 5.0  # max_delay

    def test_calculate_delay_with_jitter(self):
        """Тест: задержка с jitter."""
        executor = MockActionExecutor()
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            base_delay=1.0,
            jitter=True
        )
        
        # Задержка с jitter должна быть в диапазоне 50%-150%
        for _ in range(10):
            delay = safe_executor._calculate_delay(1)  # base = 2.0
            assert 1.0 <= delay <= 3.0  # 2.0 * 0.5 до 2.0 * 1.5


class TestSafeExecutorFailureMemoryIntegration:
    """Тесты интеграции с FailureMemory."""

    @pytest.mark.asyncio
    async def test_should_switch_pattern_after_two_errors(self):
        """Тест: should_switch_pattern после 2 ошибок."""
        executor = MockActionExecutor()
        executor.behavior = "transient_error"
        failure_memory = FailureMemory()
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory,
            max_retries=1  # 1 попытка на каждый вызов
        )
        
        context = ExecutionContext()
        
        # Первая ошибка
        await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        assert failure_memory.should_switch_pattern("test.capability") is False
        
        # Вторая ошибка
        await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        assert failure_memory.should_switch_pattern("test.capability") is True

    @pytest.mark.asyncio
    async def test_metadata_contains_failure_info(self):
        """Тест: metadata содержит информацию об ошибках."""
        executor = MockActionExecutor()
        executor.behavior = "logic_error"
        failure_memory = FailureMemory()
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory,
            max_retries=1
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        # Проверка metadata
        assert "error_type" in result.metadata
        assert "recommendation" in result.metadata
        assert "failure_count" in result.metadata
        assert "retry_count" in result.metadata
        assert "should_switch_pattern" in result.metadata

    @pytest.mark.asyncio
    async def test_get_failure_memory(self):
        """Тест: получение FailureMemory через геттер."""
        executor = MockActionExecutor()
        failure_memory = FailureMemory()
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=failure_memory
        )
        
        assert safe_executor.get_failure_memory() is failure_memory


class TestSafeExecutorErrorCategoryMapping:
    """Тесты маппинга ErrorType → ErrorCategory."""

    @pytest.mark.asyncio
    async def test_transient_error_category(self):
        """Тест: TRANSIENT ошибка маппится на ErrorCategory.TRANSIENT."""
        executor = MockActionExecutor()
        executor.behavior = "transient_error"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            max_retries=1
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        assert result.error_category == ErrorCategory.TRANSIENT

    @pytest.mark.asyncio
    async def test_validation_error_category(self):
        """Тест: VALIDATION ошибка маппится на ErrorCategory.INVALID_INPUT."""
        executor = MockActionExecutor()
        executor.behavior = "validation_error"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            max_retries=1
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        assert result.error_category == ErrorCategory.INVALID_INPUT

    @pytest.mark.asyncio
    async def test_fatal_error_category(self):
        """Тест: FATAL ошибка маппится на ErrorCategory.FATAL."""
        executor = MockActionExecutor()
        executor.behavior = "fatal_error"
        
        safe_executor = SafeExecutor(
            executor=executor,
            failure_memory=FailureMemory(),
            max_retries=1
        )
        
        context = ExecutionContext()
        result = await safe_executor.execute(
            capability_name="test.capability",
            parameters={},
            context=context
        )
        
        assert result.error_category == ErrorCategory.FATAL


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
