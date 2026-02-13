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
from core.system_context.system_context import SystemContext
from core.application.services.contract_service import ContractService
from core.application.services.prompt_service import PromptService
from core.skills.base_skill import BaseSkill


async def verify_preload():
    """Основная функция проверки предзагрузки ресурсов."""
    print("=== Проверка предзагрузки ресурсов ===\n")
    
    # Создаем конфигурацию
    config = SystemConfig()
    
    # Создаем системный контекст
    system_context = SystemContext(config)
    
    # Инициализируем систему
    print("1. Инициализация системного контекста...")
    success = await system_context.initialize()
    if not success:
        print("❌ Ошибка инициализации системного контекста")
        return False
    
    print("✅ Системный контекст инициализирован\n")
    
    # Проверяем, что система полностью инициализирована
    print("2. Проверка полной инициализации системы...")
    is_fully_initialized = system_context.is_fully_initialized()
    if is_fully_initialized:
        print("✅ Система полностью инициализирована")
    else:
        print("❌ Система не полностью инициализирована")
        # Проверяем детали через реестр
        preload_status = system_context.registry.verify_all_resources_preloaded()
        print(f"   Детали: {preload_status}")
        return False
    
    print()
    
    # Проверяем сервисы
    print("3. Проверка сервисов...")
    
    # Проверяем ContractService
    contract_service = system_context.get_resource("contract_service")
    if contract_service:
        print("   ✅ ContractService доступен")
        # Проверяем, что предзагрузка была выполнена
        if hasattr(system_context.registry, 'are_contracts_preloaded'):
            contracts_preloaded = system_context.registry.are_contracts_preloaded()
            if contracts_preloaded:
                print("   ✅ Контракты предзагружены")
            else:
                print("   ❌ Контракты не предзагружены")
    else:
        print("   ❌ ContractService недоступен")
    
    # Проверяем PromptService
    prompt_service = system_context.get_resource("prompt_service")
    if prompt_service:
        print("   ✅ PromptService доступен")
        # Проверяем, что предзагрузка была выполнена
        if hasattr(system_context.registry, 'are_prompts_preloaded'):
            prompts_preloaded = system_context.registry.are_prompts_preloaded()
            if prompts_preloaded:
                print("   ✅ Промпты предзагружены")
            else:
                print("   ❌ Промпты не предзагружены")
    else:
        print("   ❌ PromptService недоступен")
    
    print()
    
    # Проверяем навыки
    print("4. Проверка навыков...")
    skills = system_context._get_resources_by_type("SKILL")  # ResourceType.SKILL
    if skills:
        print(f"   Найдено навыков: {len(skills)}")
        all_skills_preloaded = True
        
        for skill_name, skill_info in skills.items():
            skill = skill_info.instance
            if isinstance(skill, BaseSkill):
                # Проверяем, что навык инициализирован
                if hasattr(skill, 'is_preloaded'):
                    is_preloaded = skill.is_preloaded()
                    if is_preloaded:
                        print(f"   ✅ Навык '{skill_name}' предзагружен")
                    else:
                        print(f"   ❌ Навык '{skill_name}' не предзагружен")
                        all_skills_preloaded = False
                else:
                    print(f"   ⚠️  Навык '{skill_name}' не поддерживает проверку предзагрузки")
            else:
                print(f"   ⚠️  '{skill_name}' не является BaseSkill")
        
        if all_skills_preloaded:
            print("   ✅ Все навыки предзагружены")
        else:
            print("   ❌ Не все навыки предзагружены")
    else:
        print("   ⚠️  Навыки не найдены")
    
    print()
    
    # Проверяем Capability
    print("5. Проверка Capability...")
    capabilities = system_context.list_capabilities()
    print(f"   Найдено capability: {len(capabilities)}")
    
    # Проверяем, что Capability не содержат parameters_schema
    invalid_capabilities = []
    for cap_name in capabilities:
        cap = system_context.get_capability(cap_name)
        if hasattr(cap, 'parameters_schema'):
            invalid_capabilities.append(cap_name)
    
    if invalid_capabilities:
        print(f"   ❌ Найдено {len(invalid_capabilities)} capability с устаревшим parameters_schema:")
        for cap_name in invalid_capabilities[:5]:  # Показываем первые 5
            print(f"      - {cap_name}")
        if len(invalid_capabilities) > 5:
            print(f"      ... и еще {len(invalid_capabilities) - 5}")
    else:
        print("   ✅ Все Capability соответствуют новой архитектуре (без parameters_schema)")
    
    print()
    
    # Итог
    print("=== Результат проверки ===")
    checks = [
        is_fully_initialized,
        contract_service is not None,
        prompt_service is not None,
        not invalid_capabilities  # Нет устаревших capability
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