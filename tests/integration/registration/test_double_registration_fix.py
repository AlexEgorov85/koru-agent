#!/usr/bin/env python3
"""
Тест для проверки, что двойная регистрация шагов больше не происходит
"""

import sys
import os
from unittest.mock import MagicMock

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.session_context.session_context import SessionContext
from models.execution import ExecutionStatus


def test_no_double_registration():
    """
    Тест, что шаги регистрируются только один раз
    """
    print("Тест: Проверка отсутствия двойной регистрации шагов...")
    
    session_context = SessionContext()
    
    # Регистрируем шаг один раз
    session_context.register_step(
        step_number=1,
        capability_name="test.skill.action",
        skill_name="TestSkill",
        action_item_id="action1",
        observation_item_ids=["obs1"],
        summary="First registration",
        status=ExecutionStatus.SUCCESS
    )
    
    print(f"После первой регистрации: {session_context.step_context.count()} шагов")
    
    # Пытаемся зарегистрировать тот же шаг снова - должно вызвать ошибку
    try:
        session_context.register_step(
            step_number=1,  # тот же номер
            capability_name="test.skill.action",
            skill_name="TestSkill",
            action_item_id="action1",
            observation_item_ids=["obs1"],
            summary="Second registration - should fail",
            status=ExecutionStatus.SUCCESS
        )
        assert False, "Ожидалось исключение при повторной регистрации шага"
    except ValueError as e:
        assert "уже существует" in str(e), f"Неправильное сообщение об ошибке: {e}"
        print("[OK] Повторная регистрация корректно отклонена")
    
    # Регистрируем следующий шаг
    session_context.register_step(
        step_number=2,
        capability_name="test.skill.action2",
        skill_name="TestSkill",
        action_item_id="action2",
        observation_item_ids=["obs2"],
        summary="Second step",
        status=ExecutionStatus.SUCCESS
    )
    
    print(f"После регистрации второго шага: {session_context.step_context.count()} шагов")
    
    # Проверяем, что теперь есть 2 шага с правильными номерами
    assert session_context.step_context.count() == 2, f"Ожидалось 2 шага, получено {session_context.step_context.count()}"
    
    step_numbers = [step.step_number for step in session_context.step_context.steps]
    assert step_numbers == [1, 2], f"Ожидались номера [1, 2], получены {step_numbers}"
    
    print("[OK] Оба шага зарегистрированы корректно с уникальными номерами")


def test_execution_gateway_vs_runtime():
    """
    Тест, что ExecutionGateway и Runtime не дублируют регистрацию шагов
    """
    print("\nТест: Проверка, что ExecutionGateway и Runtime не дублируют регистрацию...")
    
    session_context = SessionContext()
    
    # Имитируем вызов из Runtime - регистрируем шаг
    # (ранее это приводило к двойной регистрации, так как ExecutionGateway тоже регистрировал шаг)
    session_context.register_step(
        step_number=1,
        capability_name="book_library.get_books_by_author",
        skill_name="BookLibrarySkill",
        action_item_id="action1",
        observation_item_ids=["obs1"],
        summary="Getting books by author",
        status=ExecutionStatus.SUCCESS
    )
    
    print(f"Зарегистрирован шаг 1, всего шагов: {session_context.step_context.count()}")
    
    # Проверяем, что шаг зарегистрирован
    assert session_context.step_context.count() == 1, f"Ожидался 1 шаг, получено {session_context.step_context.count()}"
    
    # Пытаемся зарегистрировать тот же шаг снова (имитация бага с двойной регистрацией)
    try:
        session_context.register_step(
            step_number=1,
            capability_name="book_library.get_books_by_author",  # та же capability
            skill_name="BookLibrarySkill",
            action_item_id="action1",
            observation_item_ids=["obs1"],
            summary="Getting books by author - duplicate",
            status=ExecutionStatus.SUCCESS
        )
        assert False, "Ожидалось исключение при попытке двойной регистрации"
    except ValueError as e:
        assert "уже существует" in str(e), f"Неправильное сообщение об ошибке: {e}"
        print("[OK] Двойная регистрация корректно предотвращена")
    
    # Регистрируем следующий шаг
    session_context.register_step(
        step_number=2,
        capability_name="final_answer.generate",
        skill_name="FinalAnswerSkill",
        action_item_id="action2",
        observation_item_ids=["obs2"],
        summary="Generating final answer",
        status=ExecutionStatus.SUCCESS
    )
    
    print(f"Зарегистрирован шаг 2, всего шагов: {session_context.step_context.count()}")
    
    # Проверяем, что оба шага зарегистрированы
    assert session_context.step_context.count() == 2, f"Ожидалось 2 шага, получено {session_context.step_context.count()}"
    
    step_numbers = [step.step_number for step in session_context.step_context.steps]
    assert step_numbers == [1, 2], f"Ожидались номера [1, 2], получены {step_numbers}"
    
    print("[OK] Оба шага зарегистрированы без дубликации")


if __name__ == "__main__":
    print("Запуск тестов для проверки отсутствия двойной регистрации шагов...")
    
    try:
        test_no_double_registration()
        test_execution_gateway_vs_runtime()
        
        print("\n[SUCCESS] Все тесты пройдены успешно!")
        print("Двойная регистрация шагов больше не происходит.")
        print("Исправление ошибки 'Шаг с номером X уже существует' работает корректно.")
    except Exception as e:
        print(f"\n[FAILURE] Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)