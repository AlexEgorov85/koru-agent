"""
Тесты для проверки таймаутов выполнения атомарных действий.

АРХИТЕКТУРА:
- Проверяет корректную обработку таймаутов в исполнителе действий
- Проверяет поведение при превышении времени выполнения
- Проверяет возврат ошибки таймаута
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from application.orchestration.atomic_actions.executor import AtomicActionExecutor
from application.orchestration.atomic_actions.react_actions import ThinkAction
from domain.models.atomic_action.types import AtomicActionType
from domain.models.atomic_action.result import AtomicActionResult


class SlowThinkAction(ThinkAction):
    """Мок-действие, которое имитирует медленное выполнение."""
    
    async def execute(self, parameters):
        """Выполняет действие с искусственной задержкой."""
        await asyncio.sleep(10)  # Длительная операция
        return AtomicActionResult(
            success=True,
            action_type=AtomicActionType.THINK,
            result={"thought": "slow result", "reasoning": "delayed reasoning"},
            error_message=None,
            execution_time=10.0,
            metadata={}
        )


@pytest.mark.asyncio
async def test_action_timeout():
    """Действие превышает лимит времени выполнения"""
    # Создаем моки
    mock_llm = AsyncMock()
    mock_renderer = Mock()
    
    # Настройка мока для имитации задержки
    async def slow_generate(*args, **kwargs):
        await asyncio.sleep(10)  # Искусственно медленный ответ
        return Mock(parsed={"thought": "slow result", "reasoning": "delayed reasoning"})
    
    mock_llm.generate = slow_generate
    
    # Создаем действие
    think_action = ThinkAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
    
    # Регистрируем в исполнителе
    executor = AtomicActionExecutor()
    executor.register_action(think_action)
    
    # Выполняем последовательность с коротким таймаутом
    sequence = [{"action_type": AtomicActionType.THINK, "parameters": {"goal": "test"}}]
    
    # Устанавливаем короткий таймаут (0.1 секунды против 10 секунд выполнения)
    results = await executor.execute_sequence(sequence, timeout_per_action=0.1)
    
    # Проверки
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error_type == "TIMEOUT"
    assert "timeout" in str(results[0].error_message).lower() if results[0].error_message else True


@pytest.mark.asyncio
async def test_multiple_actions_with_timeout():
    """Таймаут в середине последовательности действий"""
    # Моки
    mock_llm = AsyncMock()
    mock_renderer = Mock()
    mock_registry = AsyncMock()
    
    # Создаем нормальное быстрое действие
    fast_think_action = ThinkAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
    
    # Мок для быстрого генерации
    mock_llm.generate.return_value = Mock(parsed={"thought": "quick thought", "reasoning": "fast reasoning"})
    
    # Регистрируем действия
    executor = AtomicActionExecutor()
    executor.register_action(fast_think_action)
    
    # Последовательность с таймаутом на втором действии
    sequence = [
        {
            "action_type": AtomicActionType.THINK,
            "parameters": {"goal": "first quick action"}
        },
        {
            "action_type": AtomicActionType.THINK,
            "parameters": {"goal": "second slow action"}  # Это вызовет таймаут
        }
    ]
    
    # Имитируем таймаут на втором действии
    original_generate = mock_llm.generate
    
    async def conditional_slow_generate(*args, **kwargs):
        if "second" in str(kwargs.get('parameters', {}).get('goal', '')):
            await asyncio.sleep(10)  # Искусственно медленное выполнение
        else:
            await asyncio.sleep(0.01)  # Быстрое выполнение
        return Mock(parsed={"thought": "result", "reasoning": "reasoning"})
    
    mock_llm.generate = conditional_slow_generate
    
    # Выполняем с коротким таймаутом
    results = await executor.execute_sequence(sequence, timeout_per_action=0.1)
    
    # Проверки
    assert len(results) == 2
    assert results[0].success is True  # Первое действие должно пройти
    assert results[1].success is False  # Второе действие должно завершиться таймаутом
    assert results[1].error_type == "TIMEOUT"


@pytest.mark.asyncio
async def test_action_with_custom_timeout():
    """Действие с пользовательским таймаутом"""
    # Моки
    mock_llm = AsyncMock()
    mock_renderer = Mock()
    
    # Создаем быстрое действие
    think_action = ThinkAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
    
    # Мок для быстрого генерации
    mock_llm.generate.return_value = Mock(parsed={"thought": "quick thought", "reasoning": "fast reasoning"})
    
    # Регистрируем действие
    executor = AtomicActionExecutor()
    executor.register_action(think_action)
    
    # Выполняем с достаточным таймаутом
    sequence = [{"action_type": AtomicActionType.THINK, "parameters": {"goal": "test"}}]
    results = await executor.execute_sequence(sequence, timeout_per_action=5.0)  # Достаточный таймаут
    
    # Проверки
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].action_type == AtomicActionType.THINK


@pytest.mark.asyncio
async def test_zero_timeout_handling():
    """Обработка нулевого или отрицательного таймаута"""
    # Моки
    mock_llm = AsyncMock()
    mock_renderer = Mock()
    
    # Создаем действие
    think_action = ThinkAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
    
    # Мок для быстрого генерации
    mock_llm.generate.return_value = Mock(parsed={"thought": "quick thought", "reasoning": "fast reasoning"})
    
    # Регистрируем действие
    executor = AtomicActionExecutor()
    executor.register_action(think_action)
    
    # Выполняем с нулевым таймаутом (должно обрабатываться как отсутствие таймаута)
    sequence = [{"action_type": AtomicActionType.THINK, "parameters": {"goal": "test"}}]
    results = await executor.execute_sequence(sequence, timeout_per_action=0)
    
    # Проверки
    assert len(results) == 1
    assert results[0].success is True  # Должно выполниться успешно, т.к. таймаут не применяется


@pytest.mark.asyncio
async def test_negative_timeout_handling():
    """Обработка отрицательного таймаута"""
    # Моки
    mock_llm = AsyncMock()
    mock_renderer = Mock()
    
    # Создаем действие
    think_action = ThinkAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
    
    # Мок для быстрого генерации
    mock_llm.generate.return_value = Mock(parsed={"thought": "quick thought", "reasoning": "fast reasoning"})
    
    # Регистрируем действие
    executor = AtomicActionExecutor()
    executor.register_action(think_action)
    
    # Выполняем с отрицательным таймаутом (должно обрабатываться как отсутствие таймаута)
    sequence = [{"action_type": AtomicActionType.THINK, "parameters": {"goal": "test"}}]
    results = await executor.execute_sequence(sequence, timeout_per_action=-1)
    
    # Проверки
    assert len(results) == 1
    assert results[0].success is True  # Должно выполниться успешно, т.к. таймаут не применяется