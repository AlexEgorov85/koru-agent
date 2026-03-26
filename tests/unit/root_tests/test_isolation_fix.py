"""
Тест изоляции конфигурации компонентов после исправления архитектурной ошибки.
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.abspath('.'))

async def test_component_isolation():
    """Тест изоляции конфигурации компонентов."""
    
    try:
        from core.config.app_config import AppConfig
        from core.agent.components.base_component import BaseComponent
        from core.application_context.application_context import ApplicationContext
        from core.config.component_config import ComponentConfig
        
        
        # Загружаем конфигурацию из реестра
        app_config = AppConfig.from_discovery(profile="prod", data_dir="data")
        
        # 1. Проверяем, что у инструмента НЕТ промптов навыков
        sql_tool_config = app_config.tool_configs["sql_tool"]
        
        assert sql_tool_config.prompt_versions == {}, \
            f"Ожидался пустой словарь, но получено: {sql_tool_config.prompt_versions}"
        
        # 2. Проверяем, что у навыка ЕСТЬ только свои промпты
        planning_config = app_config.skill_configs["planning"]
        
        assert "planning.create_plan" in planning_config.prompt_versions, \
            "Навык планирования должен иметь свои промпты"
        
        assert "book_library.search_books" not in planning_config.prompt_versions, \
            "Навык планирования не должен зависеть от промптов библиотеки!"
        
        # 3. Проверяем, что у другого навыка тоже только свои промпты
        book_library_config = app_config.skill_configs["book_library"]
        
        assert "book_library.search_books" in book_library_config.prompt_versions, \
            "Навык библиотеки должен иметь свои промпты"
        
        assert "planning.create_plan" not in book_library_config.prompt_versions, \
            "Навык библиотеки не должен зависеть от промптов планирования!"
        
        # 4. Создаем фейковый Application Context для тестирования инициализации
        
        class MockResource:
            def __init__(self):
                self.resources = {}
            
            def get_resource(self, name):
                if name not in self.resources:
                    # Создаем mock-сервисы
                    if name == "prompt_service":
                        class MockPromptService:
                            async def preload_prompts(self, config):
                                pass
                            
                            def get_prompt_from_cache(self, cap_name):
                                return f"Mock prompt for {cap_name}"
                        
                        self.resources[name] = MockPromptService()
                    elif name == "contract_service":
                        class MockContractService:
                            async def preload_contracts(self, config):
                                pass
                            
                            def get_contract_schema_from_cache(self, cap_name, direction="input"):
                                return {"mock": f"schema for {cap_name} {direction}"}
                        
                        self.resources[name] = MockContractService()
                    else:
                        self.resources[name] = None
                
                return self.resources[name]
        
        app_context = MockResource()
        
        # 5. Проверяем успешную инициализацию инструмента без промптов
        class MockTool(BaseComponent):
            async def execute(self, capability, parameters, context):
                pass
        
        tool = MockTool(name="sql_tool", application_context=app_context, component_config=sql_tool_config)
        init_result = await tool.initialize()
        
        assert init_result == True, "Инструмент должен инициализироваться без промптов"
        assert tool._initialized == True, "Флаг инициализации инструмента должен быть True"
        assert tool._cached_prompts == {}, "Кэш промптов инструмента должен быть пустым"
        
        # 6. Проверяем инициализацию навыка с промптами
        skill = MockTool(name="planning", application_context=app_context, component_config=planning_config)
        init_result = await skill.initialize()
        
        assert init_result == True, "Навык должен инициализироваться с промптами"
        assert skill._initialized == True, "Флаг инициализации навыка должен быть True"
        assert len(skill._cached_prompts) > 0, "Кэш промптов навыка должен содержать элементы"
        assert "planning.create_plan" in skill._cached_prompts, "Навык должен иметь свои промпты в кэше"
        
        
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_component_isolation())
    if success:
    else:
        sys.exit(1)