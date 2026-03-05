#!/usr/bin/env python3
"""
Диагностический скрипт для проверки capabilities агента.

Проверяет:
1. Какие skills/tools зарегистрированы в ApplicationContext
2. Какие capabilities они возвращают
3. Что видит LLM при генерации decision
"""
import asyncio
import sys
import os

# Устанавливаем UTF-8 кодировку для Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    sys.stdout.reconfigure(encoding='utf-8')

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def diagnose_capabilities():
    """Диагностика capabilities."""
    print("=" * 80)
    print("ДИАГНОСТИКА CAPABILITIES АГЕНТА")
    print("=" * 80)
    
    # Загрузка конфигурации
    print("\n1. Загрузка конфигурации...")
    config = get_config(profile='dev')
    print(f"   ✅ Конфигурация загружена (profile={config.profile})")
    
    # Инициализация инфраструктурного контекста
    print("\n2. Инициализация InfrastructureContext...")
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()
    print(f"   ✅ InfrastructureContext инициализирован (id={infrastructure_context.id})")
    
    # Создание AppConfig через discovery
    print("\n3. Создание AppConfig через auto-discovery...")
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=str(getattr(infrastructure_context.config, 'data_dir', 'data')),
        discovery=infrastructure_context.get_resource_discovery()
    )
    print(f"   ✅ AppConfig создан (config_id={app_config.config_id})")
    
    # Проверка конфигураций компонентов
    print("\n4. Проверка конфигураций компонентов:")
    print(f"   - Skills: {list(app_config.skill_configs.keys())}")
    print(f"   - Tools: {list(app_config.tool_configs.keys())}")
    print(f"   - Services: {list(app_config.service_configs.keys())}")
    print(f"   - Behaviors: {list(app_config.behavior_configs.keys())}")
    
    # Создание ApplicationContext
    print("\n5. Создание ApplicationContext...")
    application_context = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=app_config,
        profile="prod"
    )
    await application_context.initialize()
    print(f"   ✅ ApplicationContext инициализирован (id={application_context.id})")
    
    # Проверка зарегистрированных компонентов
    print("\n6. Проверка зарегистрированных компонентов:")
    from core.models.enums.common_enums import ComponentType
    
    skills = application_context.components.all_of_type(ComponentType.SKILL)
    tools = application_context.components.all_of_type(ComponentType.TOOL)
    services = application_context.components.all_of_type(ComponentType.SERVICE)
    behaviors = application_context.components.all_of_type(ComponentType.BEHAVIOR)
    
    print(f"   - Skills: {[s.name for s in skills]}")
    print(f"   - Tools: {[t.name for t in tools]}")
    print(f"   - Services: {[s.name for s in services]}")
    print(f"   - Behaviors: {[b.name for b in behaviors]}")
    
    # Проверка capabilities
    print("\n7. Проверка capabilities от skills:")
    for skill in skills:
        print(f"\n   Skill: {skill.name}")
        if hasattr(skill, 'get_capabilities'):
            try:
                caps = skill.get_capabilities()
                print(f"      ✅ Возвращает {len(caps)} capabilities:")
                for cap in caps:
                    print(f"         - {cap.name}: {cap.description[:80]}...")
            except Exception as e:
                print(f"      ❌ Ошибка: {e}")
        else:
            print(f"      ⚠️ Нет метода get_capabilities")
    
    print("\n8. Проверка capabilities от tools:")
    for tool in tools:
        print(f"\n   Tool: {tool.name}")
        if hasattr(tool, 'get_capabilities'):
            try:
                caps = tool.get_capabilities()
                print(f"      ✅ Возвращает {len(caps)} capabilities:")
                for cap in caps:
                    print(f"         - {cap.name}: {cap.description[:80]}...")
            except Exception as e:
                print(f"      ❌ Ошибка: {e}")
        else:
            print(f"      ⚠️ Нет метода get_capabilities")
    
    # Проверка get_all_capabilities
    print("\n9. Проверка application_context.get_all_capabilities():")
    all_caps = application_context.get_all_capabilities()
    print(f"   ✅ Всего capabilities: {len(all_caps)}")
    for cap in all_caps:
        print(f"      - {cap.name} (skill={cap.skill_name})")
    
    # Проверка behavior manager
    print("\n10. Проверка BehaviorManager:")
    from core.application.agent.components.behavior_manager import BehaviorManager
    
    behavior_manager = BehaviorManager(application_context=application_context)
    await behavior_manager.initialize(component_name="react_pattern")
    print(f"   ✅ BehaviorManager инициализирован")
    print(f"   - Текущий паттерн: {behavior_manager.get_current_pattern_id()}")
    
    # Проверка session context
    print("\n11. Создание SessionContext для теста:")
    from core.session_context.session_context import SessionContext
    session_context = SessionContext(session_id=str(infrastructure_context.id))
    session_context.set_goal("Какие книги написал Пушкин?")
    print(f"   ✅ SessionContext создан (goal={session_context.get_goal()})")
    
    # Генерация test decision
    print("\n12. Тестовая генерация decision:")
    decision = await behavior_manager.generate_next_decision(
        session_context=session_context,
        available_capabilities=all_caps
    )
    print(f"   ✅ Decision получен:")
    print(f"      - action: {decision.action}")
    print(f"      - capability_name: {getattr(decision, 'capability_name', 'N/A')}")
    print(f"      - reason: {getattr(decision, 'reason', 'N/A')[:100] if decision.reason else 'N/A'}")
    
    # ФИНАЛЬНЫЙ ДИАГНОЗ
    print("\n" + "=" * 80)
    print("ФИНАЛЬНЫЙ ДИАГНОЗ:")
    print("=" * 80)
    
    if len(all_caps) == 0:
        print("❌ ПРОБЛЕМА: Нет доступных capabilities!")
        print("   Причина: Skills/Tools не зарегистрированы или не имеют get_capabilities()")
        print("   Решение: Проверить AppConfig.from_discovery() и инициализацию компонентов")
    elif len(skills) == 0 and len(tools) == 0:
        print("❌ ПРОБЛЕМА: Нет зарегистрированных skills и tools!")
        print("   Причина: AppConfig.from_discovery() не нашёл компоненты")
        print("   Решение: Проверить наличие промптов/контрактов в data/")
    else:
        print("✅ Компоненты зарегистрированы корректно")
        
    if decision.action.value == 'STOP':
        print("⚠️ ВНИМАНИЕ: LLM вернул STOP на первом шаге!")
        print("   Возможные причины:")
        print("   - Goal уже считается достигнутым")
        print("   - LLM не понял что нужно делать")
        print("   - Промпт behavior pattern требует настройки")
    elif decision.action.value == 'ACT' and not decision.capability_name:
        print("❌ ПРОБЛЕМА: ACT decision без capability_name!")
        print("   Причина: LLM вернул невалидное решение")
        print("   Решение: Проверить промпт и output контракт behavior pattern")
    elif decision.action.value == 'ACT' and decision.capability_name:
        print(f"✅ Нормальное решение: ACT {decision.capability_name}")
    
    # Завершение
    print("\n13. Завершение...")
    await infrastructure_context.shutdown()
    from core.infrastructure.logging import shutdown_logging_system
    await shutdown_logging_system()
    print("   ✅ Завершено")
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(diagnose_capabilities())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
