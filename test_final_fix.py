"""
Тестирование решения проблемы с инициализацией ApplicationContext
"""
import asyncio
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.models import SystemConfig


async def test_context_initialization():
    print("=== Тестирование инициализации ApplicationContext ===")
    
    try:
        # Создаем минимальную системную конфигурацию
        from pydantic import BaseModel
        class MinimalSystemConfig(BaseModel):
            data_dir: str = "./data"
            prompts_dir: str = "./data/prompts"
            contracts_dir: str = "./data/contracts"
            providers: dict = {}
            storage: dict = {}
        
        sys_config = MinimalSystemConfig()
        
        # Создаем инфраструктурный контекст
        infra = InfrastructureContext(sys_config)
        
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
        
        # Инициализируем контекст
        result = await ctx.initialize()
        print(f"[OK] ApplicationContext успешно инициализирован: {result}")
        
        print("\n=== Тест пройден успешно! ===")
        print("Проблема с отсутствующим executor решена")
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_context_initialization())
    if not success:
        exit(1)