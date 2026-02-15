"""
Финальный тест для проверки решения проблемы с отсутствующим executor параметром
"""
import asyncio
from core.config.component_config import ComponentConfig
from core.application.agent.components.action_executor import ActionExecutor
from core.application.skills.book_library.skill import BookLibrarySkill
from core.application.tools.sql_tool import SQLTool


async def test_all_components_executor():
    print("=== Финальный тест: проверка всех компонентов с executor ===")
    
    try:
        # Создаем фейковый Application Context
        class FakeAppContext:
            def __init__(self):
                self.id = "fake_app_context"
                self.logger = None
                self.infrastructure_context = self  # для SQLTool
                
            def get_provider(self, name):
                return None
                
        fake_app_context = FakeAppContext()
        
        # Создаем фейковый executor
        fake_executor = ActionExecutor(fake_app_context)
        
        # Создаем конфигурацию
        config = ComponentConfig(
            variant_id="test_config",
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            resolved_prompts={},
            resolved_input_contracts={},
            resolved_output_contracts={}
        )
        
        # Тестируем BookLibrarySkill (ранее вызывал ошибку)
        print("Создание BookLibrarySkill...")
        skill = BookLibrarySkill(
            name="test_book_library",
            application_context=fake_app_context,
            component_config=config,
            executor=fake_executor
        )
        print("[OK] BookLibrarySkill успешно создан")
        
        # Тестируем SQLTool (ранее вызывал ошибку)
        print("Создание SQLTool...")
        tool = SQLTool(
            name="test_sql_tool",
            application_context=fake_app_context,
            component_config=config,
            executor=fake_executor
        )
        print("[OK] SQLTool успешно создан")
        
        # Проверим, что executor установлен в обоих компонентах
        assert skill.executor == fake_executor, "Executor должен быть установлен в BookLibrarySkill"
        assert tool.executor == fake_executor, "Executor должен быть установлен в SQLTool"
        print("[OK] Executor правильно установлен в обоих компонентах")
        
        print("\n=== Финальный тест пройден успешно! ===")
        print("Все компоненты теперь принимают executor параметр")
        print("Проблема с 'missing 1 required positional argument: executor' решена")
        return True
        
    except Exception as e:
        print(f"[ERROR] Ошибка в финальном тесте: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_all_components_executor())
    if not success:
        exit(1)