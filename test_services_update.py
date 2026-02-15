"""
Простой тест для проверки обновленных сервисов
"""
import asyncio
from core.config.component_config import ComponentConfig
from core.application.agent.components.action_executor import ActionExecutor
from core.application.services.prompt_service import PromptService
from core.application.services.contract_service import ContractService
from core.application.services.table_description_service import TableDescriptionService
from core.application.services.sql_generation.service import SQLGenerationService
from core.application.services.sql_query.service import SQLQueryService
from core.application.services.sql_validator.service import SQLValidatorService


async def test_updated_services():
    print("=== Тестирование обновленных сервисов ===")
    
    # Создаем фейковый Application Context
    class FakeApplicationContext:
        def __init__(self):
            self.id = "fake_context"
            self.infrastructure_context = self
            self.logger = None
            
        def get_provider(self, name):
            return None
    
    fake_app_context = FakeApplicationContext()
    
    # Создаем фейковый executor
    fake_executor = ActionExecutor(fake_app_context)
    
    # Создаем минимальную конфигурацию
    config = ComponentConfig(
        variant_id="test_config",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={}
    )
    
    try:
        # Тестируем каждый сервис с новым конструктором
        print("Создание PromptService...")
        prompt_service = PromptService(
            application_context=fake_app_context,
            component_config=config,
            executor=fake_executor
        )
        print("[OK] PromptService создан успешно")
        
        print("Создание ContractService...")
        contract_service = ContractService(
            application_context=fake_app_context,
            component_config=config,
            executor=fake_executor
        )
        print("[OK] ContractService создан успешно")
        
        print("Создание TableDescriptionService...")
        table_service = TableDescriptionService(
            application_context=fake_app_context,
            component_config=config,
            executor=fake_executor
        )
        print("[OK] TableDescriptionService создан успешно")
        
        print("Создание SQLGenerationService...")
        sql_gen_service = SQLGenerationService(
            application_context=fake_app_context,
            component_config=config,
            executor=fake_executor
        )
        print("[OK] SQLGenerationService создан успешно")
        
        print("Создание SQLQueryService...")
        sql_query_service = SQLQueryService(
            application_context=fake_app_context,
            component_config=config,
            executor=fake_executor
        )
        print("[OK] SQLQueryService создан успешно")
        
        print("Создание SQLValidatorService...")
        sql_validator_service = SQLValidatorService(
            application_context=fake_app_context,
            component_config=config,
            executor=fake_executor
        )
        print("[OK] SQLValidatorService создан успешно")
        
        # Проверяем инициализацию
        print("Инициализация PromptService...")
        result = await prompt_service.initialize()
        print(f"[OK] PromptService инициализирован: {result}")
        
        print("Инициализация ContractService...")
        result = await contract_service.initialize()
        print(f"[OK] ContractService инициализирован: {result}")
        
        print("\n=== Тест обновленных сервисов пройден успешно! ===")
        print("Все сервисы теперь принимают executor в конструкторе")
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка при создании или инициализации сервисов: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_updated_services())
    if not success:
        exit(1)