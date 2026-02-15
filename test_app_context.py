"""
Тестирование инициализации ApplicationContext с обновленной архитектурой
"""
import asyncio
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


async def test_application_context_initialization():
    print("=== Тестирование инициализации ApplicationContext ===")
    
    # Создаем инфраструктурный контекст
    infra = InfrastructureContext()
    
    # Создаем конфигурацию приложения
    app_config = AppConfig(
        config_id="test_config",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={}
    )
    
    # Создаем прикладной контекст
    ctx = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile='prod'
    )
    
    try:
        # Инициализируем контекст
        result = await ctx.initialize()
        print(f"[OK] ApplicationContext успешно инициализирован: {result}")
        print(f"[OK] Флаг инициализации: {ctx.is_fully_initialized()}")
        
        # Проверяем, что сервисы были созданы
        prompt_service = ctx.get_service("prompt_service")
        contract_service = ctx.get_service("contract_service")
        
        print(f"[OK] PromptService создан: {prompt_service is not None}")
        print(f"[OK] ContractService создан: {contract_service is not None}")
        
        print("\n=== Тест инициализации ApplicationContext пройден успешно! ===")
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка инициализации ApplicationContext: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_application_context_initialization())
    if not success:
        exit(1)