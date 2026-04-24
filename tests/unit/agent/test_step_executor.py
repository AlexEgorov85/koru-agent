"""
Unit-тесты для StepExecutor и конфигурируемых шагов.

Покрывает:
- Парсинг YAML и валидация StepConfig
- Retry логика с экспоненциальным backoff
- Timeout через asyncio.wait_for
- Fallback стратегия
- Сбор метрик выполнения
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.agent.models import (
    StepConfig, 
    StepExecutionStatus, 
    StepAttempt, 
    StepMetrics,
    StepInstance,
    StepOnErrorStrategy
)
from core.config.agent_config import AgentConfig
from core.models.data.execution import ExecutionResult, ExecutionStatus


class TestStepConfig:
    """Тесты модели StepConfig."""
    
    def test_create_minimal_config(self):
        """Создание минимальной конфигурации."""
        config = StepConfig(capability="test.capability")
        
        assert config.capability == "test.capability"
        assert config.timeout_ms == 60000  # default
        assert config.max_retries == 1  # default
        assert config.on_error == StepOnErrorStrategy.RETRY
    
    def test_create_full_config(self):
        """Создание полной конфигурации."""
        config = StepConfig(
            capability="sql.generate",
            description="Генерация SQL",
            timeout_ms=30000,
            max_retries=3,
            retry_delay_ms=500,
            retry_backoff_multiplier=2.0,
            on_error=StepOnErrorStrategy.FALLBACK,
            fallback_capability="sql.simple",
            metadata={"priority": "high"}
        )
        
        assert config.description == "Генерация SQL"
        assert config.timeout_ms == 30000
        assert config.max_retries == 3
        assert config.retry_delay_ms == 500
        assert config.on_error == StepOnErrorStrategy.FALLBACK
        assert config.fallback_capability == "sql.simple"
        assert config.metadata["priority"] == "high"
    
    def test_has_fallback(self):
        """Проверка наличия fallback."""
        config_with = StepConfig(
            capability="test",
            fallback_capability="fallback.cap"
        )
        config_without = StepConfig(capability="test")
        
        assert config_with.has_fallback() is True
        assert config_without.has_fallback() is False
    
    def test_has_retry(self):
        """Проверка необходимости retry."""
        config_with_retry = StepConfig(capability="test", max_retries=3)
        config_no_retry = StepConfig(capability="test", max_retries=0)
        
        assert config_with_retry.has_retry() is True
        assert config_no_retry.has_retry() is False
    
    def test_get_timeout_seconds(self):
        """Конвертация таймаута в секунды."""
        config = StepConfig(capability="test", timeout_ms=45000)
        assert config.get_timeout_seconds() == 45.0
    
    def test_get_retry_delay_seconds(self):
        """Расчёт задержки с экспоненциальным backoff."""
        config = StepConfig(
            capability="test",
            retry_delay_ms=1000,
            retry_backoff_multiplier=2.0
        )
        
        assert config.get_retry_delay_seconds(0) == 1.0   # 1000ms
        assert config.get_retry_delay_seconds(1) == 2.0   # 2000ms
        assert config.get_retry_delay_seconds(2) == 4.0   # 4000ms
    
    def test_validation_timeout_range(self):
        """Валидация диапазона timeout_ms."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            StepConfig(capability="test", timeout_ms=0)
        
        with pytest.raises(Exception):
            StepConfig(capability="test", timeout_ms=400000)  # > 300000
    
    def test_validation_retries_range(self):
        """Валидация диапазона max_retries."""
        with pytest.raises(Exception):
            StepConfig(capability="test", max_retries=-1)
        
        with pytest.raises(Exception):
            StepConfig(capability="test", max_retries=6)  # > 5


class TestStepMetrics:
    """Тесты модели StepMetrics."""
    
    def test_create_metrics(self):
        """Создание метрик шага."""
        metrics = StepMetrics(step_id="step_1", capability="test.cap")
        
        assert metrics.step_id == "step_1"
        assert metrics.capability == "test.cap"
        assert metrics.total_attempts == 0
        assert metrics.fallback_triggered is False
    
    def test_add_attempt_success(self):
        """Добавление успешной попытки."""
        metrics = StepMetrics(step_id="step_1", capability="test.cap")
        
        attempt = StepAttempt(
            attempt_number=1,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            duration_ms=1500,
            status=StepExecutionStatus.COMPLETED
        )
        
        metrics.add_attempt(attempt)
        
        assert metrics.total_attempts == 1
        assert metrics.successful_attempt == 1
        assert metrics.total_duration_ms == 1500
        assert metrics.avg_duration_ms == 1500.0
    
    def test_add_multiple_attempts(self):
        """Добавление нескольких попыток."""
        metrics = StepMetrics(step_id="step_1", capability="test.cap")
        
        for i in range(3):
            attempt = StepAttempt(
                attempt_number=i + 1,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                duration_ms=1000 * (i + 1),
                status=StepExecutionStatus.FAILED if i < 2 else StepExecutionStatus.COMPLETED
            )
            metrics.add_attempt(attempt)
        
        assert metrics.total_attempts == 3
        assert metrics.successful_attempt == 3
        assert metrics.total_duration_ms == 6000  # 1000 + 2000 + 3000
        assert metrics.avg_duration_ms == 2000.0
    
    def test_to_dict(self):
        """Сериализация в словарь."""
        metrics = StepMetrics(step_id="step_1", capability="test.cap")
        result = metrics.to_dict()
        
        assert isinstance(result, dict)
        assert result["step_id"] == "step_1"
        assert result["capability"] == "test.cap"


class TestStepInstance:
    """Тесты модели StepInstance."""
    
    def test_create_instance(self):
        """Создание экземпляра шага."""
        config = StepConfig(capability="test.cap")
        instance = StepInstance(step_id="step_1", config=config)
        
        assert instance.status == StepExecutionStatus.PENDING
        assert instance.result is None
        assert instance.metrics is not None
    
    def test_mark_running(self):
        """Отметка шага как выполняемого."""
        config = StepConfig(capability="test.cap")
        instance = StepInstance(step_id="step_1", config=config)
        
        instance.mark_running()
        
        assert instance.status == StepExecutionStatus.RUNNING
    
    def test_mark_completed(self):
        """Отметка шага как завершённого."""
        config = StepConfig(capability="test.cap")
        instance = StepInstance(step_id="step_1", config=config)
        
        result_data = {"data": "success"}
        instance.mark_completed(result_data)
        
        assert instance.status == StepExecutionStatus.COMPLETED
        assert instance.result == result_data
    
    def test_mark_failed(self):
        """Отметка шага как неудачного."""
        config = StepConfig(capability="test.cap")
        instance = StepInstance(step_id="step_1", config=config)
        
        instance.mark_failed("Connection error", "TRANSIENT")
        
        assert instance.status == StepExecutionStatus.FAILED
        assert instance.result["error"] == "Connection error"
        assert instance.result["error_type"] == "TRANSIENT"
    
    def test_is_finished(self):
        """Проверка завершённости шага."""
        config = StepConfig(capability="test.cap")
        
        pending = StepInstance(step_id="s1", config=config)
        assert pending.is_finished() is False
        
        running = StepInstance(step_id="s2", config=config)
        running.mark_running()
        assert running.is_finished() is False
        
        completed = StepInstance(step_id="s3", config=config)
        completed.mark_completed()
        assert completed.is_finished() is True


class TestAgentConfigYaml:
    """Тесты загрузки конфигурации из YAML."""
    
    def test_load_yaml_basic(self, tmp_path):
        """Загрузка базового YAML файла."""
        yaml_content = """
max_steps: 20
steps:
  step1:
    capability: "test.capability"
    timeout_ms: 30000
    max_retries: 2
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)
        
        config = AgentConfig.from_yaml(str(yaml_file))
        
        # max_steps теперь берётся из AppConfig.agent_defaults, а не из AgentConfig
        assert len(config.steps) == 1
        assert "step1" in config.steps
        assert config.steps["step1"].capability == "test.capability"
        assert config.steps["step1"].timeout_ms == 30000
    
    def test_load_yaml_with_validation(self, tmp_path):
        """Загрузка YAML с валидацией capability registry."""
        yaml_content = """
steps:
  step1:
    capability: "valid.cap"
    fallback_capability: "also.valid"
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)
        
        registry = {"valid.cap", "also.valid"}
        config = AgentConfig.from_yaml(str(yaml_file), capability_registry=registry)
        
        assert len(config.steps) == 1
    
    def test_load_yaml_invalid_capability(self, tmp_path):
        """Загрузка YAML с несуществующей capability."""
        yaml_content = """
steps:
  step1:
    capability: "nonexistent.cap"
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)
        
        registry = {"valid.cap"}
        
        with pytest.raises(ValueError, match="несуществующую capability"):
            AgentConfig.from_yaml(str(yaml_file), capability_registry=registry)
    
    def test_load_yaml_self_fallback(self, tmp_path):
        """Загрузка YAML с fallback на себя."""
        yaml_content = """
steps:
  step1:
    capability: "test.cap"
    fallback_capability: "test.cap"
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)
        
        registry = {"test.cap"}
        
        with pytest.raises(ValueError, match="не может указывать на себя"):
            AgentConfig.from_yaml(str(yaml_file), capability_registry=registry)


class TestStepExecutorIntegration:
    """Интеграционные тесты StepExecutor."""
    
    @pytest.mark.asyncio
    async def test_execute_success_first_attempt(self):
        """Успешное выполнение с первой попытки."""
        from core.agent.components.step_executor import StepExecutor
        
        # Мок SafeExecutor без импорта ExecutionContext
        mock_safe_executor = AsyncMock()
        mock_safe_executor.execute.return_value = ExecutionResult.success(data={"result": "ok"})
        
        step_executor = StepExecutor(safe_executor=mock_safe_executor)
        
        config = StepConfig(capability="test.cap", timeout_ms=5000, max_retries=2)
        context = MagicMock()  # Простой мок вместо ExecutionContext
        
        result = await step_executor.execute_with_config(
            step_config=config,
            parameters={"param": "value"},
            context=context,
            step_id="test_step"
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert mock_safe_executor.execute.call_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_retry(self):
        """Выполнение с retry после ошибки."""
        from core.agent.components.step_executor import StepExecutor
        
        mock_safe_executor = AsyncMock()
        
        # Первые 2 попытки失败, третья успешна
        mock_safe_executor.execute.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            ExecutionResult.success(data={"result": "ok"})
        ]
        
        step_executor = StepExecutor(safe_executor=mock_safe_executor)
        
        config = StepConfig(
            capability="test.cap",
            timeout_ms=5000,
            max_retries=3,
            retry_delay_ms=10  # Короткая задержка для теста
        )
        context = MagicMock()
        
        result = await step_executor.execute_with_config(
            step_config=config,
            parameters={},
            context=context
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert mock_safe_executor.execute.call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """Превышение таймаута."""
        from core.agent.components.step_executor import StepExecutor
        
        mock_safe_executor = AsyncMock()
        
        # Имитация долгого выполнения
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(10)
            return ExecutionResult.success()
        
        mock_safe_executor.execute.side_effect = slow_execute
        
        step_executor = StepExecutor(safe_executor=mock_safe_executor)
        
        config = StepConfig(
            capability="test.cap",
            timeout_ms=100,  # 100ms таймаут
            max_retries=0
        )
        context = MagicMock()
        
        result = await step_executor.execute_with_config(
            step_config=config,
            parameters={},
            context=context
        )
        
        assert result.status == ExecutionStatus.FAILED
        # Проверяем что ошибка связана с таймаутом (в metadata или error)
        assert "timeout" in result.error.lower() or "timed out" in result.error.lower() or \
               (result.metadata and any("timeout" in str(v).lower() for v in result.metadata.values()))
    
    @pytest.mark.asyncio
    async def test_execute_fallback_success(self):
        """Успешный fallback."""
        from core.agent.components.step_executor import StepExecutor
        
        mock_safe_executor = AsyncMock()
        
        # Основная capability падает, fallback успешен
        async def execute_side_effect(capability_name, **kwargs):
            if capability_name == "main.cap":
                raise Exception("Main failed")
            return ExecutionResult.success(data={"from": "fallback"})
        
        mock_safe_executor.execute.side_effect = execute_side_effect
        
        step_executor = StepExecutor(safe_executor=mock_safe_executor)
        
        config = StepConfig(
            capability="main.cap",
            timeout_ms=5000,
            max_retries=0,
            on_error=StepOnErrorStrategy.FALLBACK,
            fallback_capability="fallback.cap"
        )
        context = MagicMock()
        
        result = await step_executor.execute_with_config(
            step_config=config,
            parameters={},
            context=context
        )
        
        assert result.status == ExecutionStatus.COMPLETED
        assert result.data.get("from") == "fallback"
    
    @pytest.mark.asyncio
    async def test_execute_all_attempts_exhausted(self):
        """Исчерпание всех попыток."""
        from core.agent.components.step_executor import StepExecutor
        
        mock_safe_executor = AsyncMock()
        mock_safe_executor.execute.side_effect = Exception("Always fails")
        
        step_executor = StepExecutor(safe_executor=mock_safe_executor)
        
        config = StepConfig(
            capability="test.cap",
            timeout_ms=5000,
            max_retries=2,
            retry_delay_ms=10
        )
        context = MagicMock()
        
        result = await step_executor.execute_with_config(
            step_config=config,
            parameters={},
            context=context
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert mock_safe_executor.execute.call_count == 3  # 1 + 2 retries
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self):
        """Сбор метрик выполнения."""
        from core.agent.components.step_executor import StepExecutor
        
        mock_safe_executor = AsyncMock()
        mock_safe_executor.execute.side_effect = [
            Exception("First fail"),
            ExecutionResult.success()
        ]
        
        step_executor = StepExecutor(safe_executor=mock_safe_executor)
        
        config = StepConfig(
            capability="test.cap",
            timeout_ms=5000,
            max_retries=2,
            retry_delay_ms=10
        )
        context = MagicMock()
        
        await step_executor.execute_with_config(
            step_config=config,
            parameters={},
            context=context,
            step_id="metrics_test"
        )
        
        metrics = step_executor.get_step_metrics("metrics_test")
        
        assert metrics is not None
        assert metrics.total_attempts >= 1
        assert len(metrics.attempts) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
