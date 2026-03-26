"""
Простой тест для демонстрации, что основная функциональность работает.
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.abspath('.'))

async def test_basic_functionality():
    """Тест основной функциональности."""
    
    try:
        # Тестируем, что основные классы можно импортировать без ошибок
        from core.agent.components.base_component import BaseComponent
        from core.application_context.application_context import ApplicationContext
        from core.config.app_config import AppConfig
        from core.config.component_config import ComponentConfig
        
        
        # Создаем минимальный ComponentConfig для теста
        config = ComponentConfig(
            variant_id="test_component",
            prompt_versions={
                "test.capability": "v1.0.0"
            },
            input_contract_versions={
                "test.capability": "v1.0.0"
            },
            output_contract_versions={
                "test.capability": "v1.0.0"
            }
        )
        
        
        # Создаем фиктивный контекст для теста
        class MockAppContext:
            def __init__(self):
                self.logger = None
                self.get_resource = lambda name: None
        
        mock_context = MockAppContext()
        
        # Создаем тестовый класс, наследующийся от BaseComponent
        from abc import abstractmethod
        
        class TestComponent(BaseComponent):
            async def execute(self, capability, parameters, context):
                # Заглушка для абстрактного метода
                return {"result": "executed"}
        
        # Создаем экземпляр тестового компонента
        component = TestComponent(
            name="test_component",
            application_context=mock_context,
            component_config=config
        )
        
        
        # Проверим, что методы get_* существуют
        methods_exist = all([
            hasattr(component, 'get_prompt'),
            hasattr(component, 'get_input_contract'),
            hasattr(component, 'get_output_contract'),
            hasattr(component, 'initialize')
        ])
        
        
        # Проверим, что методы возвращают ожидаемые ошибки до инициализации
        try:
            component.get_prompt("test")
        except RuntimeError as e:
        
        # Проверим инициализацию
        init_result = await component.initialize()
        
        
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_basic_functionality())
    if success:
    else:
        sys.exit(1)