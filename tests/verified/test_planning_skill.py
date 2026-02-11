#!/usr/bin/env python3
"""
Тест для проверки PlanningSkill - должен проверить, что get_capabilities() возвращает 6 объектов Capability
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем необходимые классы
from core.skills.planning.skill import PlanningSkill
from unittest.mock import Mock


def test_planning_skill_capabilities():
    """Тестируем, что PlanningSkill возвращает 6 capability"""
    
    # Создаем mock для system_context
    mock_system_context = Mock()
    mock_system_context.get_resource = Mock(return_value=Mock())
    
    # Создаем экземпляр PlanningSkill
    skill = PlanningSkill(name="planning", system_context=mock_system_context)
    
    # Получаем список capability
    capabilities = skill.get_capabilities()
    
    # Проверяем, что их 6
    assert len(capabilities) == 6, f"Ожидается 6 capability, но получено {len(capabilities)}"
    
    # Проверяем, что все capability имеют правильные имена
    expected_names = {
        "planning.create_plan",
        "planning.update_plan", 
        "planning.get_next_step",
        "planning.update_step_status",
        "planning.decompose_task",
        "planning.mark_task_completed"
    }
    
    actual_names = {cap.name for cap in capabilities}
    
    assert actual_names == expected_names, f"Ожидаемые имена: {expected_names}, полученные: {actual_names}"
    
    print(f"[SUCCESS] PlanningSkill successfully returns {len(capabilities)} capability:")
    for cap in capabilities:
        print(f"  - {cap.name}: {cap.description}")
    
    return True


if __name__ == "__main__":
    try:
        test_planning_skill_capabilities()
        print("\n[SUCCESS] All tests passed successfully!")
    except AssertionError as e:
        print(f"\n[ERROR] Test error: {e}")
        sys.exit(1)
    except ImportError as e:
        print(f"\n[ERROR] Import error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        sys.exit(1)