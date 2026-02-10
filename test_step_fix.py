#!/usr/bin/env python3
"""
Тест для проверки исправления ошибки с дублированием шагов
"""

import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.session_context.session_context import SessionContext
from core.session_context.model import AgentStep
from models.execution import ExecutionStatus


def test_step_context_unique_numbers():
    """Тест уникальности номеров шагов в StepContext"""
    print("Тест: Уникальность номеров шагов...")
    
    session_context = SessionContext()
    
    # Создаем несколько шагов с разными номерами
    step1 = AgentStep(
        step_number=1,
        capability_name="test.capability1",
        skill_name="TestSkill",
        action_item_id="action1",
        observation_item_ids=["obs1"],
        summary="Test step 1",
        status=ExecutionStatus.SUCCESS
    )
    
    step2 = AgentStep(
        step_number=2,
        capability_name="test.capability2",
        skill_name="TestSkill",
        action_item_id="action2",
        observation_item_ids=["obs2"],
        summary="Test step 2",
        status=ExecutionStatus.SUCCESS
    )
    
    # Добавляем шаги
    session_context.register_step(
        step_number=1,
        capability_name="test.capability1",
        skill_name="TestSkill",
        action_item_id="action1",
        observation_item_ids=["obs1"],
        summary="Test step 1",
        status=ExecutionStatus.SUCCESS
    )
    
    session_context.register_step(
        step_number=2,
        capability_name="test.capability2",
        skill_name="TestSkill",
        action_item_id="action2",
        observation_item_ids=["obs2"],
        summary="Test step 2",
        status=ExecutionStatus.SUCCESS
    )
    
    print(f"Добавлено шагов: {session_context.step_context.count()}")
    assert session_context.step_context.count() == 2, "Должно быть 2 шага"
    
    # Проверяем, что номера шагов уникальны
    step_numbers = [step.step_number for step in session_context.step_context.steps]
    assert step_numbers == [1, 2], f"Ожидались номера [1, 2], получены {step_numbers}"
    
    print("[OK] Уникальность номеров шагов работает корректно")


def test_step_context_duplicate_numbers():
    """Тест, что дублирование номеров шагов вызывает ошибку"""
    print("\nТест: Повторная регистрация шага с тем же номером...")
    
    session_context = SessionContext()
    
    # Добавляем первый шаг
    session_context.register_step(
        step_number=1,
        capability_name="test.capability1",
        skill_name="TestSkill",
        action_item_id="action1",
        observation_item_ids=["obs1"],
        summary="Test step 1",
        status=ExecutionStatus.SUCCESS
    )
    
    # Пытаемся добавить шаг с тем же номером - должно вызвать ошибку
    try:
        session_context.register_step(
            step_number=1,  # тот же номер
            capability_name="test.capability2",
            skill_name="TestSkill",
            action_item_id="action2",
            observation_item_ids=["obs2"],
            summary="Test step 2",
            status=ExecutionStatus.SUCCESS
        )
        assert False, "Ожидалось исключение при дублировании номера шага"
    except ValueError as e:
        assert "уже существует" in str(e), f"Неправильное сообщение об ошибке: {e}"
        print("[OK] Корректно выброшено исключение при дублировании номера шага")


def test_runtime_step_number_generation():
    """Тест генерации номеров шагов в runtime"""
    print("\nТест: Генерация номеров шагов в runtime...")
    
    session_context = SessionContext()
    
    # Имитируем работу runtime - используем длину списка шагов + 1
    current_step = len(session_context.step_context.steps) + 1
    assert current_step == 1, f"Первый шаг должен иметь номер 1, получен {current_step}"
    
    # Добавляем первый шаг
    session_context.register_step(
        step_number=current_step,
        capability_name="test.capability1",
        skill_name="TestSkill",
        action_item_id="action1",
        observation_item_ids=["obs1"],
        summary="Test step 1",
        status=ExecutionStatus.SUCCESS
    )
    
    # Следующий шаг должен получить номер 2
    current_step = len(session_context.step_context.steps) + 1
    assert current_step == 2, f"Второй шаг должен иметь номер 2, получен {current_step}"
    
    # Добавляем второй шаг
    session_context.register_step(
        step_number=current_step,
        capability_name="test.capability2",
        skill_name="TestSkill",
        action_item_id="action2",
        observation_item_ids=["obs2"],
        summary="Test step 2",
        status=ExecutionStatus.SUCCESS
    )
    
    # Проверяем, что оба шага добавлены
    assert session_context.step_context.count() == 2, "Должно быть 2 шага"
    
    step_numbers = [step.step_number for step in session_context.step_context.steps]
    assert step_numbers == [1, 2], f"Ожидались номера [1, 2], получены {step_numbers}"
    
    print("[OK] Генерация номеров шагов в runtime работает корректно")


if __name__ == "__main__":
    print("Запуск тестов для проверки исправления ошибки с дублированием шагов...")
    
    try:
        test_step_context_unique_numbers()
        test_step_context_duplicate_numbers()
        test_runtime_step_number_generation()
        
        print("\n[OK] Все тесты пройдены успешно!")
        print("Ошибка с дублированием шагов исправлена.")
    except Exception as e:
        print(f"\n[ERROR] Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)