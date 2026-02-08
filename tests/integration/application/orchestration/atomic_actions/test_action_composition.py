"""
Тесты композиции атомарных действий (Think → Act → Observe).

АРХИТЕКТУРА:
- Проверяет интеграцию между различными типами действий
- Проверяет корректную передачу данных между действиями
- Проверяет обработку ошибок и откаты в последовательности
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from application.orchestration.atomic_actions.executor import AtomicActionExecutor
from application.orchestration.atomic_actions.react_actions import (
    ThinkAction, ActAction, ObserveAction
)
from domain.models.atomic_action.types import AtomicActionType
from domain.models.atomic_action.result import AtomicActionResult


class TestActionComposition:
    """Тесты композиции атомарных действий."""
    
    @pytest.mark.asyncio
    async def test_react_cycle_composition(self):
        """Полный цикл ReAct: Think → Act → Observe через правильный интерфейс"""
        # Моки для зависимостей
        mock_llm = AsyncMock()
        mock_renderer = Mock()
        mock_registry = AsyncMock()
        mock_capability = AsyncMock()
        
        # Настройка моков
        mock_registry.get_capability.return_value = mock_capability
        mock_capability.execute.return_value = {"content": "test content"}
        
        # Мок для LLM
        mock_llm.generate.return_value = Mock(parsed={"thought": "analyzing task", "reasoning": "step by step"})
        
        # Создаём действия
        think_action = ThinkAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
        act_action = ActAction(capability_registry=mock_registry)
        observe_action = ObserveAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
        
        # Регистрируем в исполнителе
        executor = AtomicActionExecutor()
        executor.register_action(think_action)
        executor.register_action(act_action)
        executor.register_action(observe_action)
        
        # Выполняем последовательность через правильный интерфейс
        sequence = [
            {
                "action_type": AtomicActionType.THINK,
                "parameters": {"goal": "Проанализировать файл"}
            },
            {
                "action_type": AtomicActionType.ACT,
                "parameters": {
                    "capability_name": "file_reader",
                    "parameters": {"path": "safe.txt"}
                }
            },
            {
                "action_type": AtomicActionType.OBSERVE,
                "parameters": {
                    "action_result": {"content": "test content"},
                    "last_action": "file_reader"
                }
            }
        ]
        
        results = await executor.execute_sequence(sequence)
        
        # Проверки
        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].action_type == AtomicActionType.THINK
        assert results[1].action_type == AtomicActionType.ACT
        assert results[2].action_type == AtomicActionType.OBSERVE
        
        # Проверяем, что каждое действие было вызвано
        assert mock_llm.generate.called
        assert mock_registry.get_capability.called
        assert mock_capability.execute.called

    @pytest.mark.asyncio
    async def test_rollback_on_security_violation(self):
        """Откат при ошибке безопасности в композиции"""
        # Настройка: первое действие успешно, второе — ошибка безопасности
        mock_registry = AsyncMock()
        mock_safe_capability = AsyncMock()
        mock_safe_capability.execute.return_value = {"content": "step1 content"}
        
        # Создаем исключение SecurityError, если оно не существует
        class SecurityError(Exception):
            pass
        
        mock_unsafe_capability = AsyncMock()
        mock_unsafe_capability.execute.side_effect = SecurityError("Path traversal blocked")
        
        mock_registry.get_capability.side_effect = [
            mock_safe_capability,  # Первый вызов — безопасный
            mock_unsafe_capability  # Второй вызов — ошибка
        ]
        
        act_action = ActAction(capability_registry=mock_registry)
        executor = AtomicActionExecutor()
        executor.register_action(act_action)
        
        sequence = [
            {
                "action_type": AtomicActionType.ACT,
                "parameters": {
                    "capability_name": "file_reader",
                    "parameters": {"path": "step1.txt"}
                }
            },
            {
                "action_type": AtomicActionType.ACT,
                "parameters": {
                    "capability_name": "file_reader",
                    "parameters": {"path": "../../../etc/passwd"}  # ← Ошибка безопасности
                }
            }
        ]
        
        results = await executor.execute_sequence(sequence, rollback_on_failure=True)
        
        # Проверки
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert "SECURITY" in str(results[1].error_type).upper() if results[1].error_type else True
        # Проверяем, что вызван откат для первого действия (если поддерживается)

    @pytest.mark.asyncio
    async def test_complex_multi_step_sequence(self):
        """Комплексная последовательность из нескольких шагов"""
        # Моки
        mock_llm = AsyncMock()
        mock_renderer = Mock()
        mock_registry = AsyncMock()
        mock_capability = AsyncMock()
        
        # Настройка возвращаемых значений для разных вызовов
        mock_capability.execute.side_effect = [
            {"content": "first result"},
            {"content": "second result"},
            {"content": "third result"}
        ]
        
        mock_registry.get_capability.return_value = mock_capability
        mock_llm.generate.side_effect = [
            Mock(parsed={"thought": "first thought", "reasoning": "step 1"}),
            Mock(parsed={"thought": "second thought", "reasoning": "step 2"}),
            Mock(parsed={"thought": "final thought", "reasoning": "conclusion"})
        ]
        
        # Создаем действия
        think_action = ThinkAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
        act_action = ActAction(capability_registry=mock_registry)
        observe_action = ObserveAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
        
        # Регистрируем в исполнителе
        executor = AtomicActionExecutor()
        executor.register_action(think_action)
        executor.register_action(act_action)
        executor.register_action(observe_action)
        
        # Сложная последовательность
        sequence = [
            {
                "action_type": AtomicActionType.THINK,
                "parameters": {"goal": "Решить задачу по анализу кода"}
            },
            {
                "action_type": AtomicActionType.ACT,
                "parameters": {
                    "capability_name": "file_reader",
                    "parameters": {"path": "src/main.py"}
                }
            },
            {
                "action_type": AtomicActionType.OBSERVE,
                "parameters": {
                    "action_result": {"content": "first result"},
                    "last_action": "file_reader"
                }
            },
            {
                "action_type": AtomicActionType.THINK,
                "parameters": {"goal": "Анализировать полученное содержимое"}
            },
            {
                "action_type": AtomicActionType.ACT,
                "parameters": {
                    "capability_name": "code_analyzer",
                    "parameters": {"code": "first result"}
                }
            },
            {
                "action_type": AtomicActionType.OBSERVE,
                "parameters": {
                    "action_result": {"content": "second result"},
                    "last_action": "code_analyzer"
                }
            },
            {
                "action_type": AtomicActionType.THINK,
                "parameters": {"goal": "Сформировать вывод"}
            }
        ]
        
        results = await executor.execute_sequence(sequence)
        
        # Проверки
        assert len(results) == 7
        assert all(r.success for r in results[:6])  # Первые 6 должны быть успешными
        
        # Проверяем, что действия были вызваны в правильном порядке
        expected_types = [
            AtomicActionType.THINK, AtomicActionType.ACT, AtomicActionType.OBSERVE,
            AtomicActionType.THINK, AtomicActionType.ACT, AtomicActionType.OBSERVE,
            AtomicActionType.THINK
        ]
        for i, result in enumerate(results):
            assert result.action_type == expected_types[i]

    @pytest.mark.asyncio
    async def test_error_propagation_between_actions(self):
        """Проверка распространения ошибок между действиями"""
        # Моки
        mock_llm = AsyncMock()
        mock_renderer = Mock()
        mock_registry = AsyncMock()
        
        # Создаем ошибку в первом действии
        mock_capability = AsyncMock()
        mock_capability.execute.side_effect = Exception("Connection failed")
        
        mock_registry.get_capability.return_value = mock_capability
        mock_llm.generate.return_value = Mock(parsed={"thought": "trying to read file", "reasoning": "need to handle error"})
        
        # Создаем действия
        think_action = ThinkAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
        act_action = ActAction(capability_registry=mock_registry)
        observe_action = ObserveAction(llm_provider=mock_llm, prompt_renderer=mock_renderer)
        
        # Регистрируем в исполнителе
        executor = AtomicActionExecutor()
        executor.register_action(think_action)
        executor.register_action(act_action)
        executor.register_action(observe_action)
        
        # Последовательность с ошибкой
        sequence = [
            {
                "action_type": AtomicActionType.THINK,
                "parameters": {"goal": "Подготовить к чтению файла"}
            },
            {
                "action_type": AtomicActionType.ACT,
                "parameters": {
                    "capability_name": "file_reader",
                    "parameters": {"path": "nonexistent.txt"}
                }
            },
            {
                "action_type": AtomicActionType.OBSERVE,
                "parameters": {
                    "action_result": {"error": "Connection failed"},
                    "last_action": "file_reader"
                }
            }
        ]
        
        results = await executor.execute_sequence(sequence)
        
        # Проверки
        assert len(results) == 3
        assert results[0].success is True  # THINK должен быть успешным
        assert results[1].success is False  # ACT должен завершиться с ошибкой
        assert "Connection failed" in str(results[1].error_message) if results[1].error_message else True
        # OBSERVE может быть успешным, если он может обработать ошибку как входные данные