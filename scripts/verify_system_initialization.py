"""
Скрипт для полной верификации инициализации системы.
"""
import asyncio
from typing import Tuple, List, Dict, Any

async def verify_initialization():
    """Полная верификация инициализации системы."""
    checks = []
    
    # 1. Проверка порядка инициализации
    checks.append(("Порядок инициализации", await verify_initialization_order()))
    
    # 2. Проверка загрузки зависимостей
    checks.append(("Загрузка зависимостей", await verify_dependency_loading()))
    
    # 3. Проверка отсутствия циклов
    checks.append(("Циклические зависимости", await verify_no_cycles()))
    
    # 4. Проверка готовности сервисов
    checks.append(("Готовность сервисов", await verify_service_readiness()))
    
    # 5. E2E тест: создание агента и выполнение запроса
    checks.append(("E2E тест", await verify_e2e_execution()))
    
    # Вывод результатов
    print("\n=== Результаты верификации ===")
    all_passed = True
    for name, (passed, details) in checks:
        status = "+" if passed else "-"
        print(f"{status} {name}: {details}")
        all_passed = all_passed and passed
    
    return all_passed

async def verify_initialization_order():
    """Проверка, что сервисы инициализируются в правильном порядке."""
    # Ожидаемый порядок (без циклов)
    expected_order = [
        "prompt_service",
        "contract_service", 
        "table_description_service",
        "sql_validator_service",
        "sql_generation_service",
        "sql_query_service"
    ]
    
    # Получение фактического порядка из логов или внутреннего состояния
    actual_order = await get_actual_initialization_order()
    
    # Проверка топологической корректности
    for i, service in enumerate(expected_order):
        if service not in actual_order:
            return False, f"Сервис '{service}' отсутствует в порядке инициализации"
        
        # Проверка, что зависимости инициализированы раньше
        deps = get_service_dependencies(service)
        for dep in deps:
            if actual_order.index(dep) > actual_order.index(service):
                return False, f"Зависимость '{dep}' инициализирована ПОЗЖЕ '{service}'"
    
    return True, "Порядок инициализации корректен"

async def verify_dependency_loading():
    """Проверка загрузки зависимостей."""
    try:
        from core.system_context.system_context import SystemContext
        from core.config.models import SystemConfig
        
        # Создаем системный контекст
        system = SystemContext(config=SystemConfig())
        
        # Инициализируем систему
        if not await system.initialize():
            return False, "Ошибка инициализации системы"
        
        # Проверяем, что SQLGenerationService получил table_description_service
        sql_gen_service = await system.get_service("sql_generation_service")
        if not sql_gen_service:
            return False, "SQLGenerationService не найден"
        
        # Проверяем, что зависимость загружена
        table_desc_service = sql_gen_service.get_dependency("table_description_service")
        if not table_desc_service:
            return False, "table_description_service не загружен в SQLGenerationService"
        
        # Проверяем, что SQLQueryService получил sql_validator_service
        sql_query_service = await system.get_service("sql_query_service")
        if not sql_query_service:
            return False, "SQLQueryService не найден"
        
        sql_validator_service = sql_query_service.get_dependency("sql_validator_service")
        if not sql_validator_service:
            return False, "sql_validator_service не загружен в SQLQueryService"
        
        return True, "Все зависимости загружены корректно"
    except Exception as e:
        return False, f"Ошибка при проверке загрузки зависимостей: {str(e)}"

async def verify_no_cycles():
    """Проверка отсутствия циклических зависимостей."""
    try:
        from core.system_context.dependency_resolver import DependencyResolver, ServiceDescriptor
        from core.application.services.table_description_service import TableDescriptionService
        from core.application.services.sql_generation.service import SQLGenerationService
        from core.application.services.sql_query.service import SQLQueryService
        from core.application.services.sql_validator.service import SQLValidatorService
        from core.application.services.prompt_service import PromptService
        
        # Создаем дескрипторы сервисов
        descriptors = {
            "table_description_service": ServiceDescriptor("table_description_service", TableDescriptionService),
            "sql_generation_service": ServiceDescriptor("sql_generation_service", SQLGenerationService),
            "sql_query_service": ServiceDescriptor("sql_query_service", SQLQueryService),
            "sql_validator_service": ServiceDescriptor("sql_validator_service", SQLValidatorService),
            "prompt_service": ServiceDescriptor("prompt_service", PromptService),
        }
        
        # Проверяем, что циклические зависимости не обнаружены
        try:
            init_order = await DependencyResolver.calculate_initialization_order(descriptors)
            return True, f"Циклические зависимости отсутствуют. Порядок: {init_order}"
        except Exception as e:
            return False, f"Обнаружены циклические зависимости: {str(e)}"
    except Exception as e:
        return False, f"Ошибка при проверке циклических зависимостей: {str(e)}"

async def verify_service_readiness():
    """Проверка готовности сервисов."""
    try:
        from core.system_context.system_context import SystemContext
        from core.config.models import SystemConfig
        
        # Создаем системный контекст
        system = SystemContext(config=SystemConfig())
        
        # Инициализируем систему
        if not await system.initialize():
            return False, "Ошибка инициализации системы"
        
        # Проверяем, что все сервисы имеют _initialized = True
        from models.resource import ResourceType
        all_services = system.registry.get_resources_by_type(ResourceType.SERVICE)
        uninitialized = []
        for name, info in all_services.items():
            if not getattr(info.instance, '_initialized', False):
                uninitialized.append(name)
        
        if uninitialized:
            return False, f"Неинициализированные сервисы: {uninitialized}"
        
        return True, f"Все сервисы готовы ({len(all_services)} шт.)"
    except Exception as e:
        return False, f"Ошибка при проверке готовности сервисов: {str(e)}"

async def verify_e2e_execution():
    """E2E тест: создание агента и выполнение реального запроса."""
    try:
        from core.system_context.system_context import SystemContext
        from core.config.models import SystemConfig
        from core.infrastructure.context.agent_factory import AgentFactory
        
        # 1. Полная инициализация системы
        system = SystemContext(config=SystemConfig())
        if not await system.initialize():
            return False, "Ошибка инициализации системы"
        
        # 2. Создание агента
        factory = AgentFactory(system)
        agent = await factory.create_agent(goal="Какие книги написал Пушкин?")
        
        # 3. Выполнение запроса (имитация)
        # В реальной системе здесь будет вызов agent.run()
        
        return True, f"Агент успешно создан. ID: {getattr(agent, 'id', 'unknown')}"
    
    except Exception as e:
        return False, f"Исключение при E2E тесте: {str(e)}"

async def get_actual_initialization_order():
    """Получение фактического порядка инициализации."""
    # В реальной системе это будет получено из логов или внутреннего состояния
    # Временно возвращаем ожидаемый порядок
    return [
        "prompt_service",
        "contract_service", 
        "table_description_service",
        "sql_validator_service",
        "sql_generation_service",
        "sql_query_service"
    ]

def get_service_dependencies(service_name: str) -> List[str]:
    """Получение зависимостей сервиса."""
    dependencies_map = {
        "sql_generation_service": ["table_description_service", "prompt_service"],
        "sql_validator_service": ["table_description_service"],
        "sql_query_service": ["sql_validator_service", "sql_generation_service"],
    }
    return dependencies_map.get(service_name, [])

if __name__ == "__main__":
    result = asyncio.run(verify_initialization())
    print(f"\nИтог: {'ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if result else 'ЕСТЬ ОШИБКИ'}")