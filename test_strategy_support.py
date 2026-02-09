#!/usr/bin/env python3
"""
Тест для проверки обновленных навыков с поддержкой стратегий
"""

import sys
import os
import asyncio
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.skills.book_library.skill import BookLibrarySkill
from core.skills.planning.skill import PlanningSkill


def test_strategy_support():
    """Тестируем поддержку стратегий в навыках"""
    
    print("=== Тестирование поддержки стратегий в навыках ===")
    
    # Создаем mock для system_context
    mock_system_context = MagicMock()
    mock_system_context.get_resource = MagicMock()
    
    # Тестируем BookLibrarySkill
    book_skill = BookLibrarySkill(name="book_library", system_context=mock_system_context)
    
    print(f"BookLibrarySkill.supported_strategies: {book_skill.supported_strategies}")
    assert book_skill.supported_strategies == ["react", "planning"], "BookLibrarySkill должен поддерживать обе стратегии"
    
    assert book_skill.supports_strategy("react"), "BookLibrarySkill должен поддерживать react"
    assert book_skill.supports_strategy("planning"), "BookLibrarySkill должен поддерживать planning"
    assert not book_skill.supports_strategy("other"), "BookLibrarySkill не должен поддерживать другие стратегии"
    
    print("+ BookLibrarySkill правильно поддерживает стратегии")
    
    # Тестируем PlanningSkill
    plan_skill = PlanningSkill(name="planning", system_context=mock_system_context)
    
    print(f"PlanningSkill.supported_strategies: {plan_skill.supported_strategies}")
    assert plan_skill.supported_strategies == ["planning"], "PlanningSkill должен поддерживать только планирование"
    
    assert not plan_skill.supports_strategy("react"), "PlanningSkill не должен поддерживать react"
    assert plan_skill.supports_strategy("planning"), "PlanningSkill должен поддерживать planning"
    assert not plan_skill.supports_strategy("other"), "PlanningSkill не должен поддерживать другие стратегии"
    
    print("+ PlanningSkill правильно поддерживает стратегии")
    
    # Проверяем, что все capability в BookLibrarySkill имеют поле supported_strategies
    book_capabilities = book_skill.get_capabilities()
    for cap in book_capabilities:
        assert hasattr(cap, 'supported_strategies'), f"Capability {cap.name} должна иметь поле supported_strategies"
        assert cap.supported_strategies == ["react", "planning"], f"Capability {cap.name} должна поддерживать обе стратегии"
    
    print("+ Все capability в BookLibrarySkill имеют правильное поле supported_strategies")
    
    # Проверяем, что все capability в PlanningSkill имеют поле supported_strategies
    plan_capabilities = plan_skill.get_capabilities()
    for cap in plan_capabilities:
        assert hasattr(cap, 'supported_strategies'), f"Capability {cap.name} должна иметь поле supported_strategies"
        assert cap.supported_strategies == ["planning"], f"Capability {cap.name} должна поддерживать только планирование"
    
    print("+ Все capability в PlanningSkill имеют правильное поле supported_strategies")
    
    print("\n=== Все тесты пройдены успешно! ===")
    return True


def main():
    try:
        success = test_strategy_support()
        if success:
            print("\n[SUCCESS] Все тесты поддержки стратегий прошли успешно!")
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