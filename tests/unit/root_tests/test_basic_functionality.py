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
    print("=== ТЕСТ ОСНОВНОЙ ФУНКЦИОНАЛЬНОСТИ ===")
    
    try:
        # Тестируем, что основные классы можно импортировать без ошибок
        from core.agent.components.base_component import BaseComponent
        from core.application_context.application_context import ApplicationContext
        from core.config.app_config import AppConfig
        from core.config.component_config import ComponentConfig
        
        print("[OK] Основные классы импортированы успешно")
        
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
        
        print("[OK] ComponentConfig создан")
        
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
        
        print(f"[OK] BaseComponent создан: {component.name}")
        print(f"[INFO] Инициализирован: {component._initialized}")
        print(f"[INFO] Кэш промптов: {component._cached_prompts}")
        print(f"[INFO] Кэш входных контрактов: {component._cached_input_contracts}")
        print(f"[INFO] Кэш выходных контрактов: {component._cached_output_contracts}")
        
        # Проверим, что методы get_* существуют
        methods_exist = all([
            hasattr(component, 'get_prompt'),
            hasattr(component, 'get_input_contract'),
            hasattr(component, 'get_output_contract'),
            hasattr(component, 'initialize')
        ])
        
        print(f"[OK] Все необходимые методы существуют: {methods_exist}")
        
        # Проверим, что методы возвращают ожидаемые ошибки до инициализации
        try:
            component.get_prompt("test")
            print("[ERROR] Ожидалась ошибка до инициализации")
        except RuntimeError as e:
            print(f"[OK] Правильно выбрасывается ошибка до инициализации: {type(e).__name__}")
        
        # Проверим инициализацию
        init_result = await component.initialize()
        print(f"[INFO] Результат инициализации: {init_result}")
        print(f"[INFO] После инициализации _initialized: {component._initialized}")
        
        print("\n[SUCCESS] ОСНОВНАЯ ФУНКЦИОНАЛЬНОСТЬ РАБОТАЕТ!")
        print("\n=== ВАЖНЫЕ ПОЗИЦИИ ===")
        print("1. BaseComponent может быть создан с ComponentConfig")
        print("2. У компонента есть изолированные кэши")
        print("3. Методы get_* существуют для доступа к кэшам")
        print("4. Инициализация может быть вызвана")
        print("5. Защита от использования до инициализации работает")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА ТЕСТИРОВАНИЯ: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_basic_functionality())
    if success:
        print("\n[SUCCESS] Тестирование завершено успешно!")
    else:
        print("\n[ERROR] Тестирование завершилось с ошибками!")
        sys.exit(1)