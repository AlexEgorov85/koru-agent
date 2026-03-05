#!/usr/bin/env python3
"""
Быстрая диагностика capabilities без вызова LLM.
"""
import sys
import os

if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    sys.stdout.reconfigure(encoding='utf-8')

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig
import asyncio


async def diagnose():
    print("=" * 80)
    print("ДИАГНОСТИКА CAPABILITIES (без LLM)")
    print("=" * 80)
    
    config = get_config(profile='dev')
    print(f"\n1. ✅ Конфигурация: {config.profile}")
    
    infra = InfrastructureContext(config)
    await infra.initialize()
    print(f"2. ✅ InfrastructureContext: {infra.id}")
    
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=str(getattr(infra.config, 'data_dir', 'data')),
        discovery=infra.get_resource_discovery()
    )
    print(f"3. ✅ AppConfig: {app_config.config_id}")
    
    print(f"\n4. Конфигурации компонентов:")
    print(f"   - Skills: {list(app_config.skill_configs.keys())}")
    print(f"   - Tools: {list(app_config.tool_configs.keys())}")
    print(f"   - Behaviors: {list(app_config.behavior_configs.keys())}")
    
    app_ctx = ApplicationContext(infra, app_config, "prod")
    await app_ctx.initialize()
    print(f"5. ✅ ApplicationContext: {app_ctx.id}")
    
    from core.models.enums.common_enums import ComponentType
    
    skills = app_ctx.components.all_of_type(ComponentType.SKILL)
    tools = app_ctx.components.all_of_type(ComponentType.TOOL)
    behaviors = app_ctx.components.all_of_type(ComponentType.BEHAVIOR)
    
    print(f"\n6. Зарегистрированные компоненты:")
    print(f"   - Skills: {[s.name for s in skills]}")
    print(f"   - Tools: {[t.name for t in tools]}")
    print(f"   - Behaviors: {[b.name for b in behaviors]}")
    
    all_caps = app_ctx.get_all_capabilities()
    print(f"\n7. ✅ Всего capabilities: {len(all_caps)}")
    for cap in all_caps:
        print(f"   - {cap.name}")
    
    # Проверка book_library skill
    print(f"\n8. Проверка book_library skill:")
    book_lib = app_ctx.components.get(ComponentType.TOOL, 'book_library')
    if book_lib:
        print(f"   ✅ book_library найден")
        if hasattr(book_lib, 'get_capabilities'):
            caps = book_lib.get_capabilities()
            print(f"   ✅ Возвращает {len(caps)} capabilities:")
            for c in caps:
                print(f"      - {c.name}")
    else:
        print(f"   ❌ book_library НЕ найден!")
    
    print("\n" + "=" * 80)
    print("ФИНАЛЬНЫЙ ДИАГНОЗ:")
    print("=" * 80)
    
    if len(all_caps) == 0:
        print("❌ НЕТ CAPABILITIES - агент будет сразу возвращать STOP")
    elif len(skills) == 0 and len(tools) == 0:
        print("❌ НЕТ SKILLS/TOOLS - агент не может выполнять действия")
    else:
        print(f"✅ {len(all_caps)} capabilities доступно - агент должен работать")
    
    await infra.shutdown()
    from core.infrastructure.logging import shutdown_logging_system
    await shutdown_logging_system()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(diagnose()))
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
