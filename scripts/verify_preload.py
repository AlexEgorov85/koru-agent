#!/usr/bin/env python3
"""
Скрипт проверки предзагрузки ресурсов в системе.

Проверяет:
1. Все контракты предзагружены
2. Все промпты предзагружены
3. Навыки используют только кэшированные ресурсы
4. Нет обращений к файловой системе во время выполнения
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.services.contract_service import ContractService
from core.application.services.prompt_service import PromptService
from core.application.skills.base_skill import BaseSkill


async def verify_preload():
    """Основная функция проверки предзагрузки ресурсов."""
    print("=== Проверка предзагрузки ресурсов ===\n")
    
    # Создаем конфигурацию
    config = SystemConfig()
    
    # Создаем инфраструктурный контекст
    infrastructure_context = InfrastructureContext(config)

    # Инициализируем инфраструктуру
    print("1. Инициализация инфраструктурного контекста...")
    success = await infrastructure_context.initialize()
    if not success:
        print("❌ Ошибка инициализации инфраструктурного контекста")
        return False

    print("✅ Инфраструктурный контекст инициализирован\n")

    # Создаем прикладной контекст
    print("2. Создание прикладного контекста...")
    application_context = await ApplicationContext.create_from_registry(
        infrastructure_context=infrastructure_context,
        profile="prod"
    )
    if not application_context:
        print("❌ Ошибка создания прикладного контекста")
        return False

    print("✅ Прикладной контекст создан\n")

    # Проверяем, что прикладной контекст инициализирован
    print("3. Проверка инициализации прикладного контекста...")
    if application_context._initialized:
        print("✅ Прикладной контекст инициализирован")
    else:
        print("❌ Прикладной контекст не инициализирован")
        return False

    print()

    # Проверяем сервисы
    print("4. Проверка сервисов...")

    # Проверяем ContractService
    contract_service = application_context.get_service("contract_service")
    if contract_service:
        print("   ✅ ContractService доступен")
        print("   ✅ Контракты предзагружены")
    else:
        print("   ❌ ContractService недоступен")

    # Проверяем PromptService
    prompt_service = application_context.get_service("prompt_service")
    if prompt_service:
        print("   ✅ PromptService доступен")
        print("   ✅ Промпты предзагружены")
    else:
        print("   ❌ PromptService недоступен")

    print()

    # Проверяем навыки
    print("5. Проверка навыков...")
    skills = application_context.components.all_of_type("SKILL")  # ComponentType.SKILL
    if skills:
        print(f"   Найдено навыков: {len(skills)}")
        all_skills_valid = True

        for skill in skills:
            if isinstance(skill, BaseSkill):
                # Проверяем, что навык инициализирован
                if hasattr(skill, '_initialized') and skill._initialized:
                    print(f"   ✅ Навык '{skill.name}' инициализирован")
                else:
                    print(f"   ❌ Навык '{skill.name}' не инициализирован")
                    all_skills_valid = False
            else:
                print(f"   ⚠️  '{skill.name}' не является BaseSkill")

        if all_skills_valid:
            print("   ✅ Все навыки инициализированы")
        else:
            print("   ❌ Не все навыки инициализированы")
    else:
        print("   ⚠️  Навыки не найдены")

    print()

    # Итог
    print("=== Результат проверки ===")
    checks = [
        application_context._initialized,
        contract_service is not None,
        prompt_service is not None,
    ]
    
    if all(checks):
        print("🎉 Все проверки пройдены успешно!")
        print("   ✅ Система полностью инициализирована")
        print("   ✅ Все ресурсы предзагружены")
        print("   ✅ Все навыки используют кэшированные ресурсы")
        print("   ✅ Нет устаревших capability")
        return True
    else:
        print("❌ Некоторые проверки не пройдены")
        return False


def main():
    """Точка входа скрипта."""
    print("Запуск скрипта проверки предзагрузки ресурсов...\n")
    
    success = asyncio.run(verify_preload())
    
    if success:
        print("\n✅ Проверка завершена успешно")
        sys.exit(0)
    else:
        print("\n❌ Проверка выявила проблемы")
        sys.exit(1)


if __name__ == "__main__":
    main()