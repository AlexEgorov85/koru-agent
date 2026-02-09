#!/usr/bin/env python3
"""
Тест для проверки функциональности перезапуска компонентов с перезагрузкой модуля
"""

import sys
import os
import asyncio
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.skills.book_library.skill import BookLibrarySkill
from core.skills.planning.skill import PlanningSkill


def test_module_reload_functionality():
    """Тестируем функциональность перезапуска с перезагрузкой модуля"""
    
    print("=== Тестирование функциональности перезапуска с перезагрузкой модуля ===")
    
    # Создаем mock для system_context
    mock_system_context = MagicMock()
    mock_system_context.get_resource = MagicMock()
    
    # Тестируем BookLibrarySkill
    book_skill = BookLibrarySkill(name="book_library", system_context=mock_system_context)
    
    # Проверяем, что метод restart_with_module_reload существует
    assert hasattr(book_skill, 'restart_with_module_reload'), "BookLibrarySkill должен иметь метод restart_with_module_reload"
    assert callable(getattr(book_skill, 'restart_with_module_reload')), "Метод restart_with_module_reload должен быть вызываемым"
    
    print("+ BookLibrarySkill поддерживает перезапуск с перезагрузкой модуля")
    
    # Тестируем PlanningSkill
    plan_skill = PlanningSkill(name="planning", system_context=mock_system_context)
    
    # Проверяем, что метод restart_with_module_reload существует
    assert hasattr(plan_skill, 'restart_with_module_reload'), "PlanningSkill должен иметь метод restart_with_module_reload"
    assert callable(getattr(plan_skill, 'restart_with_module_reload')), "Метод restart_with_module_reload должен быть вызываемым"
    
    print("+ PlanningSkill поддерживает перезапуск с перезагрузкой модуля")
    
    # Проверяем, что обычный метод restart также существует
    assert hasattr(book_skill, 'restart'), "BookLibrarySkill должен иметь метод restart"
    assert hasattr(plan_skill, 'restart'), "PlanningSkill должен иметь метод restart"
    
    print("+ Все навыки поддерживают обычный перезапуск")
    
    print("\n=== Тестирование функциональности перезапуска с перезагрузкой модуля завершено успешно! ===")
    print("Примечание: Реальная перезагрузка модуля может быть выполнена только в специальных условиях")
    print("и требует осторожного обращения из-за потенциальных проблем с состоянием объектов.")
    
    return True


def main():
    try:
        success = test_module_reload_functionality()
        if success:
            print("\n[SUCCESS] Все тесты перезапуска с перезагрузкой модуля прошли успешно!")
            return True
        else:
            print("\n[ERROR] Один или несколько тестов не прошли")
            return False
    except Exception as e:
        print(f"\n[ERROR] Непредвиденная ошибка в тесте: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)