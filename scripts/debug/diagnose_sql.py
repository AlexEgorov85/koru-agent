#!/usr/bin/env python3
"""
Диагностика SQL Tool — аналитика по всем контекстам и компонентам.

Поднимает InfrastructureContext + ApplicationContext и показывает:
- Статус DB провайдеров
- Статус sql_tool и его способность выполнять запросы
- Статус table_description_service
- Граф зависимостей компонентов
- Порядок инициализации
- Работу executor при вызовах sql_tool.execute и table_description_service.get_table

ИСПОЛЬЗОВАНИЕ:
    python diagnose_sql.py
    python diagnose_sql.py --test-query "SELECT 1"
    python diagnose_sql.py --verbose
"""
import asyncio
import sys
import traceback
from pathlib import Path

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.models.enums.common_enums import ResourceType, ComponentType
from core.components.services.registry.component_registry import ComponentRegistry

# ============================================================================
# КОНСТАНТЫ
# ============================================================================

PROFILE = "prod"
DATA_DIR = "data"

# Цвета
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
HEADER = "\033[95m"

# ============================================================================
# УТИЛИТЫ
# ============================================================================

def sep(char="═", length=70):
    print(f"{CYAN}{char * length}{RESET}")

def section(title):
    print(f"\n{HEADER}{BOLD}{'─'*3} {title} {'─'*3}{RESET}")

def ok(text):
    print(f"  {GREEN}✅{RESET} {text}")

def warn(text):
    print(f"  {YELLOW}⚠️ {RESET}{text}")

def fail(text):
    print(f"  {RED}❌{RESET} {text}")

def info(text, indent=2):
    print(f"{'  ' * indent}{DIM}{text}{RESET}")


# ============================================================================
# ДИАГНОСТИКА
# ============================================================================

async def diagnose_infrastructure() -> InfrastructureContext:
    """Диагностика InfrastructureContext."""
    section("1. INFRASTRUCTURE CONTEXT")

    config = get_config(profile=PROFILE, data_dir=DATA_DIR)
    ok(f"Конфигурация загружена: profile={PROFILE}")
    info(f"data_dir: {getattr(config, 'data_dir', 'N/A')}")
    info(f"llm_providers: {list(getattr(config, 'llm_providers', {}).keys())}")
    info(f"db_providers: {list(getattr(config, 'db_providers', {}).keys())}")

    infra_ctx = InfrastructureContext(config)
    success = await infra_ctx.initialize()

    if success:
        ok(f"InfrastructureContext инициализирован: {infra_ctx.id}")
    else:
        fail("InfrastructureContext НЕ инициализирован!")

    # DB провайдеры
    section("1.1. DB Провайдеры")
    db_resources = infra_ctx.resource_registry.get_resources_by_type(ResourceType.DATABASE)
    if db_resources:
        ok(f"Найдено DB провайдеров: {len(db_resources)}")
        for res in db_resources:
            ok(f"{res.name}: type={res.resource_type.value}, default={res.is_default}, instance={type(res.instance).__name__ if res.instance else None}")
    else:
        fail("DB провайдеры НЕ зарегистрированы!")
        info("Проверьте core/config/defaults/*.yaml — секция db_providers")

    # LLM провайдеры
    section("1.2. LLM Провайдеры")
    llm_resources = infra_ctx.resource_registry.get_resources_by_type(ResourceType.LLM)
    if llm_resources:
        ok(f"Найдено LLM провайдеров: {len(llm_resources)}")
        for res in llm_resources:
            ok(f"{res.name}: type={res.resource_type.value}, instance={type(res.instance).__name__ if res.instance else None}")
    else:
        warn("LLM провайдеры НЕ зарегистрированы")

    # Resource Loader
    section("1.3. Resource Loader")
    if hasattr(infra_ctx, "resource_loader") and infra_ctx.resource_loader:
        rl = infra_ctx.resource_loader
        ok(f"ResourceLoader: profile={rl.profile}")
        stats = rl.get_stats()
        info(f"Промптов загружено: {stats['prompts_loaded']}")
        info(f"Контрактов загружено: {stats['contracts_loaded']}")
    else:
        warn("ResourceLoader не найден")

    return infra_ctx


async def diagnose_application_context(infra_ctx: InfrastructureContext) -> ApplicationContext:
    """Диагностика ApplicationContext."""
    section("2. APPLICATION CONTEXT")

    app_config = AppConfig.from_discovery(
        profile=PROFILE,
        data_dir=DATA_DIR,
    )

    ok(f"AppConfig создан из discovery")
    info(f"skill_configs: {app_config.skill_configs}")
    info(f"service_configs: {app_config.service_configs}")
    info(f"tool_configs: {app_config.tool_configs}")
    info(f"behavior_configs: {app_config.behavior_configs}")

    app_ctx = ApplicationContext(
        infrastructure_context=infra_ctx,
        config=app_config,
        profile=PROFILE,
    )

    success = await app_ctx.initialize()

    if success:
        ok(f"ApplicationContext инициализирован: {app_ctx.id}")
    else:
        fail("ApplicationContext НЕ инициализирован!")
        # Попробуем понять почему
        info(f"is_initialized: {app_ctx.is_initialized}")
        info(f"Возможные причины:")
        info("- Ошибка при инициализации одного из компонентов")
        info("- Циклические зависимости")
        info("- Компонент не найден в discovery")

    # Компоненты по типам
    section("2.1. Зарегистрированные компоненты")
    registry = app_ctx.components

    for comp_type in [ComponentType.TOOL, ComponentType.SERVICE, ComponentType.SKILL, ComponentType.BEHAVIOR]:
        comps = registry.all_of_type(comp_type)
        if comps:
            ok(f"{comp_type.value}: {len(comps)} компонентов")
            for comp in comps:
                init_status = "✅" if getattr(comp, "_initialized", False) else "❌"
                deps = getattr(comp, "DEPENDENCIES", [])
                info(f"{init_status} {comp.name} (deps: {deps})")
        else:
            warn(f"{comp_type.value}: нет компонентов")

    # Проверим table_description_service отдельно
    section("2.2. Проверка table_description_service")
    tds = registry.get(ComponentType.SERVICE, "table_description_service")
    if tds:
        ok(f"table_description_service найден: {type(tds).__name__}, _initialized={getattr(tds, '_initialized', False)}")
    else:
        fail("table_description_service НЕ НАЙДЕН!")
        # Попробуем найти через ComponentDiscovery
        from core.agent.components.component_discovery import ComponentDiscovery
        disc = ComponentDiscovery()
        disc.scan()
        entry = disc.find_component("service", "table_description")
        if entry:
            ok(f"ComponentDiscovery нашёл: {entry.class_name} в {entry.file_path}")
        else:
            fail("ComponentDiscovery тоже не нашёл!")

    return app_ctx


async def diagnose_sql_tool(app_ctx: ApplicationContext):
    """Диагностика sql_tool."""
    section("3. SQL TOOL")

    registry = app_ctx.components
    sql_tool = registry.get(ComponentType.TOOL, "sql_tool")

    if not sql_tool:
        fail("sql_tool НЕ найден в реестре компонентов!")
        return

    ok(f"sql_tool найден: {type(sql_tool).__name__}")
    info(f"name: {sql_tool.name}")
    info(f"description: {sql_tool.description}")
    info(f"_initialized: {getattr(sql_tool, '_initialized', False)}")
    info(f"DEPENDENCIES: {getattr(sql_tool, 'DEPENDENCIES', [])}")
    info(f"component_config: {sql_tool.component_config is not None}")

    # Проверка метода _get_db_provider
    section("3.1. Получение DB провайдера")
    if hasattr(sql_tool, "_get_db_provider"):
        db_provider = sql_tool._get_db_provider()
        if db_provider:
            ok(f"_get_db_provider() вернул: {type(db_provider).__name__}")
            info(f"provider attributes: {dir(db_provider)}")
        else:
            fail("_get_db_provider() вернул None!")
            info("sql_tool не может получить DB провайдер из infrastructure_context")
    else:
        fail("Метод _get_db_provider() НЕ НАЙДЕН!")

    # Проверка контрактов
    section("3.2. Контракты")
    input_contracts = getattr(sql_tool, "input_contracts", {})
    output_contracts = getattr(sql_tool, "output_contracts", {})
    info(f"input_contracts: {list(input_contracts.keys()) if input_contracts else 'нет'}")
    info(f"output_contracts: {list(output_contracts.keys()) if output_contracts else 'нет'}")

    # Тестовый запрос
    section("3.3. Тестовый SQL запрос (через executor)")
    db_provider = None
    if hasattr(sql_tool, "_get_db_provider"):
        db_provider = sql_tool._get_db_provider()

    if db_provider:
        from core.models.data.capability import Capability
        from core.agent.components.action_executor import ExecutionContext

        cap = Capability(
            name="sql_tool.execute",
            description="Test query",
            skill_name="sql_tool",
        )
        exec_ctx = ExecutionContext()

        test_query = "SELECT 1 as test_value"
        info(f"Запрос: {test_query}")

        try:
            result = await sql_tool.execute(
                capability=cap,
                parameters={"sql": test_query},
                execution_context=exec_ctx,
            )
            ok(f"Результат: {result}")
        except Exception as e:
            fail(f"Ошибка выполнения: {e}")
            info(traceback.format_exc())
    else:
        warn("Пропуск — DB провайдер недоступен")
        info("sql_tool._get_db_provider() вернул None")


async def diagnose_table_description_service(app_ctx: ApplicationContext):
    """Диагностика table_description_service."""
    section("4. TABLE DESCRIPTION SERVICE")

    registry = app_ctx.components
    tds = registry.get(ComponentType.SERVICE, "table_description_service")

    if not tds:
        fail("table_description_service НЕ найден в реестре компонентов!")
        return

    ok(f"table_description_service найден: {type(tds).__name__}")
    info(f"name: {tds.name}")
    info(f"_initialized: {getattr(tds, '_initialized', False)}")
    info(f"DEPENDENCIES: {getattr(tds, 'DEPENDENCIES', [])}")

    # Проверка executor
    section("4.1. Executor")
    executor = getattr(tds, "executor", None)
    if executor:
        ok(f"Executor найден: {type(executor).__name__}")
    else:
        fail("Executor НЕ НАЙДЕН!")
        info("table_description_service не сможет вызывать sql_tool.execute")

    # Тестовый вызов через executor
    section("4.2. Тестовый вызов table_description_service.get_table")
    if executor:
        # Проверяем что sql_tool доступен и имеет DB провайдер
        sql_tool = registry.get(ComponentType.TOOL, "sql_tool")
        db_available = False
        if sql_tool and hasattr(sql_tool, "_get_db_provider"):
            db_available = sql_tool._get_db_provider() is not None

        if db_available:
            from core.agent.components.action_executor import ExecutionContext

            exec_ctx = ExecutionContext()

            try:
                result = await executor.execute_action(
                    action_name="table_description_service.get_table",
                    parameters={"table_name": "books", "schema_name": "Lib"},
                    context=exec_ctx,
                )
                if hasattr(result, "status") and result.status.name == "COMPLETED":
                    ok(f"Результат: status={result.status.name}")
                    if hasattr(result, "data") and result.data:
                        meta = result.data.get("metadata", {})
                        cols = meta.get("columns", [])
                        info(f"columns: {len(cols)}")
                        for col in cols[:5]:
                            info(f"  - {col}")
                        if len(cols) > 5:
                            info(f"  ... и ещё {len(cols) - 5}")
                else:
                    fail(f"Ошибка: {getattr(result, 'error', 'unknown')}")
            except Exception as e:
                fail(f"Исключение при вызове: {e}")
                info(traceback.format_exc())
        else:
            warn("Пропуск — sql_tool или DB провайдер недоступны")
    else:
        warn("Пропуск — нет executor")


async def diagnose_dependency_graph(app_ctx: ApplicationContext):
    """Диагностика графа зависимостей."""
    section("5. ПОРЯДОК ИНИЦИАЛИЗАЦИИ")

    registry = app_ctx.components
    all_comps = registry.all_components()

    # Реальный порядок из application_context
    type_order_labels = {
        ComponentType.TOOL: "TOOL",
        ComponentType.SERVICE: "SERVICE",
        ComponentType.SKILL: "SKILL",
        ComponentType.BEHAVIOR: "BEHAVIOR",
    }

    type_order = [ComponentType.TOOL, ComponentType.SERVICE, ComponentType.SKILL, ComponentType.BEHAVIOR]
    order_num = 1

    for comp_type in type_order:
        type_components = registry.all_of_type(comp_type)
        type_components.sort(key=lambda c: c.name)
        type_label = type_order_labels.get(comp_type, "?")

        for comp in type_components:
            deps = getattr(comp, "DEPENDENCIES", [])
            cls_name = comp.__class__.__name__
            if "Tool" in cls_name:
                icon = f"{YELLOW}[TOOL]{RESET}"
            elif "Service" in cls_name:
                icon = f"{MAGENTA}[SERVICE]{RESET}"
            elif "Skill" in cls_name or cls_name.endswith("Skill"):
                icon = f"{GREEN}[SKILL]{RESET}"
            elif "Pattern" in cls_name:
                icon = f"{CYAN}[BEHAVIOR]{RESET}"
            else:
                icon = ""

            if deps:
                info(f"{order_num:2d}. {icon} {comp.name} ← зависит от: {deps}")
            else:
                info(f"{order_num:2d}. {icon} {comp.name}")
            order_num += 1

    ok(f"Всего компонентов: {len(all_comps)}")
    ok(f"Порядок: tool → service → skill → behavior")


async def diagnose_executor(app_ctx: ApplicationContext):
    """Диагностика ActionExecutor."""
    section("6. ACTION EXECOR")

    executor = getattr(app_ctx, "executor", None)
    if not executor:
        # Ищем executor в компонентах
        for comp in app_ctx.components.all_components():
            if hasattr(comp, "executor") and comp.executor:
                executor = comp.executor
                break

    if executor:
        ok(f"ActionExecutor найден: {type(executor).__name__}")
        info(f"application_context: {executor.application_context is not None}")
        info(f"event_bus: {getattr(executor, '_event_bus', None) is not None}")
    else:
        fail("ActionExecutor НЕ НАЙДЕН!")


# ============================================================================
# MAIN
# ============================================================================

async def main_async():
    """Главная функция диагностики."""
    sep()
    print(f"{BOLD}{CYAN}🔍 DIAGNOSTIC: SQL TOOL & TABLE DESCRIPTION SERVICE{RESET}")
    sep()

    infra_ctx = None
    app_ctx = None

    try:
        # 1. Инфраструктура
        infra_ctx = await diagnose_infrastructure()

        # 2. Приложение
        app_ctx = await diagnose_application_context(infra_ctx)

        # 3. sql_tool (работаем с тем что есть)
        await diagnose_sql_tool(app_ctx)

        # 4. table_description_service
        await diagnose_table_description_service(app_ctx)

        # 5. Граф зависимостей
        await diagnose_dependency_graph(app_ctx)

        # 6. Executor
        await diagnose_executor(app_ctx)

        sep()
        print(f"\n{BOLD}{GREEN}✅ Диагностика завершена{RESET}")

    except Exception as e:
        print(f"\n{RED}{BOLD}❌ ОШИБКА: {e}{RESET}")
        traceback.print_exc()

    finally:
        if app_ctx:
            await app_ctx.shutdown()
        if infra_ctx:
            await infra_ctx.shutdown()


def main():
    """Точка входа."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
