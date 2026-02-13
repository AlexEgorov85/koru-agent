"""
Тест для проверки, что все сервисы перенесены в ApplicationContext.
"""
import asyncio
from core.application.context.application_context import ApplicationContext
from core.config.models import AgentConfig, SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext


async def test_all_services_in_application_context():
    """Тест проверяет, что все сервисы создаются в ApplicationContext."""
    # Создаём системную конфигурацию
    system_config = SystemConfig()
    
    # Создаём инфраструктурный контекст
    infrastructure_context = InfrastructureContext(config=system_config)
    await infrastructure_context.initialize()
    
    # Создаём прикладной контекст
    config = AgentConfig(
        agent_id="test_agent",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={}
    )
    ctx = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=config
    )
    await ctx.initialize()
    
    # Проверяем, что все сервисы созданы в прикладном контексте
    services_to_check = [
        "prompt_service",
        "contract_service", 
        "table_description_service",
        "sql_generation_service",
        "sql_query_service",
        "sql_validator_service"
    ]
    
    all_services_exist = True
    for service_name in services_to_check:
        service = ctx.get_service(service_name)
        if service is None:
            print(f"X Сервис {service_name} НЕ найден в ApplicationContext")
            all_services_exist = False
        else:
            print(f"OK Сервис {service_name} найден в ApplicationContext: {type(service).__name__}")
    
    # Проверим, что сервисы - разные объекты (изолированные)
    prompt_service_1 = ctx.get_service("prompt_service")
    contract_service_1 = ctx.get_service("contract_service")
    
    # Создадим второй контекст для сравнения изоляции
    config2 = AgentConfig(
        agent_id="test_agent_2",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={}
    )
    ctx2 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=config2
    )
    await ctx2.initialize()
    
    prompt_service_2 = ctx2.get_service("prompt_service")
    contract_service_2 = ctx2.get_service("contract_service")
    
    # Проверим изоляцию
    isolation_ok = (
        prompt_service_1 is not prompt_service_2 and
        contract_service_1 is not contract_service_2
    )
    
    print(f"\nИзоляция между контекстами: {'OK' if isolation_ok else 'FAIL'}")
    
    if all_services_exist and isolation_ok:
        print("\nSUCCESS: Все сервисы успешно перенесены в ApplicationContext с изоляцией!")
        return True
    else:
        print("\nERROR: Не все сервисы перенесены или изоляция не работает")
        return False


if __name__ == "__main__":
    asyncio.run(test_all_services_in_application_context())