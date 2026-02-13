#!/usr/bin/env python3
"""
Скрипт для проверки работы инструментов в новой архитектуре.
"""
import asyncio
import tempfile
import os
from pathlib import Path

from core.config.models import SystemConfig, AgentConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


async def test_tools_context():
    """Тестирование контекста инструментов"""
    print("=== Тестирование контекста инструментов ===")
    
    # Создаем временную директорию для тестов
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Используем временную директорию: {temp_dir}")
        
        # Создаем системную конфигурацию
        system_config = SystemConfig(
            data_dir=temp_dir,
            log_dir=os.path.join(temp_dir, "logs")
        )
        
        # Создаем ProviderFactory и обновляем путь к инструментам
        # Импортируем ProviderFactory
        from core.infrastructure.providers.factory import ProviderFactory
        from core.system_context.base_system_contex import BaseSystemContext
        
        # Создаем адаптер, чтобы InfrastructureContext мог использоваться как BaseSystemContext
        class InfrastructureContextAdapter(BaseSystemContext):
            def __init__(self, infra_context):
                self.infra_context = infra_context
                # Проксируем необходимые атрибуты
                self.config = infra_context.config
                self.registry = infra_context.resource_registry
                
            async def initialize(self):
                return await self.infra_context.initialize()
                
            async def shutdown(self):
                return await self.infra_context.shutdown()
                
            def get_resource(self, name):
                return self.infra_context.get_resource(name)
                
            def get_capability(self, name):
                # Временная заглушка
                return None
                
            def list_capabilities(self):
                # Временная заглушка
                return []
                
            async def call_llm(self, request):
                # Временная заглушка
                pass
                
            async def create_agent(self, **kwargs):
                # Временная заглушка
                pass
                
            async def execute_sql_query(self, query, params=None, db_provider_name="default_db"):
                # Временная заглушка
                pass
                
            async def call_llm_with_params(self, prompt, system_prompt=None, temperature=None, max_tokens=None, llm_provider_name="default_llm", output_format=None, output_schema=None, **kwargs):
                # Временная заглушка
                pass
                
            async def run_skill(self, skill_name, capability_name, parameters, session_context=None):
                # Временная заглушка
                pass
                
            async def _select_strategy_for_question(self, question):
                # Временная заглушка
                pass

        # Создаем системную конфигурацию
        system_config = SystemConfig(
            data_dir=temp_dir,
            log_dir=os.path.join(temp_dir, "logs")
        )
        
        # Создаем адаптер и фабрику до создания инфраструктурного контекста
        # Создаем временный инфраструктурный контекст для адаптера
        temp_infra_context = InfrastructureContext(config=system_config)
        
        # Создаем адаптер
        adapter = InfrastructureContextAdapter(temp_infra_context)
        
        # Создаем ProviderFactory с адаптером
        provider_factory = ProviderFactory(adapter)
        
        # Обновляем путь к инструментам
        from pathlib import Path
        provider_factory.tools_dir = Path("core/application/tools")
        
        # Теперь создаем настоящий инфраструктурный контекст
        print("Создание инфраструктурного контекста...")
        infra_context = InfrastructureContext(config=system_config)
        
        # Присваиваем фабрику инфраструктурному контексту до инициализации
        infra_context.provider_factory = provider_factory
        
        try:
            # Инициализируем инфраструктурный контекст
            print("Инициализация инфраструктурного контекста...")
            success = await infra_context.initialize()
            if not success:
                print("Ошибка инициализации инфраструктурного контекста")
                return
            print("Инфраструктурный контекст инициализирован успешно")
            
            # Создаем конфигурацию агента
            agent_config = AgentConfig(
                prompt_versions={
                    "file_operations.read_file": "v1.0.0",
                    "file_operations.write_file": "v1.0.0"
                },
                input_contract_versions={
                    "file_operations.read_file": "v1.0.0",
                    "file_operations.write_file": "v1.0.0"
                },
                output_contract_versions={
                    "file_operations.read_file": "v1.0.0",
                    "file_operations.write_file": "v1.0.0"
                },
                side_effects_enabled=True  # Включаем побочные эффекты для тестирования
            )
            
            # Создаем прикладной контекст
            print("Создание прикладного контекста...")
            app_context = ApplicationContext(
                infrastructure_context=infra_context,
                config=agent_config
            )
            
            # Инициализируем прикладной контекст
            print("Инициализация прикладного контекста...")
            success = await app_context.initialize()
            if not success:
                print("Ошибка инициализации прикладного контекста")
                return
            print("Прикладной контекст инициализирован успешно")
            
            # Проверяем наличие инструментов
            print("\n=== Проверка наличия инструментов ===")
            
            # Проверим, что инфраструктурный контекст имеет нужные сервисы
            prompt_service = infra_context.get_service("prompt_service")
            if not prompt_service:
                print("PromptService не найден в инфраструктурном контексте")
            else:
                print("PromptService найден в инфраструктурном контексте")

            # Попробуем получить FileTool
            file_tool = app_context.get_tool("file_tool")
            if file_tool:
                print(f"FOUND FileTool: {type(file_tool).__name__}")
                print(f"  - ComponentConfig: {hasattr(file_tool, 'component_config')}")
                print(f"  - Side effects enabled: {file_tool.component_config.side_effects_enabled}")
            else:
                print("MISSING FileTool")

            # Попробуем получить SQLTool
            sql_tool = app_context.get_tool("sql_tool")
            if sql_tool:
                print(f"FOUND SQLTool: {type(sql_tool).__name__}")
            else:
                print("MISSING SQLTool")
                
            # Создаем тестовый файл для проверки FileTool
            test_file_path = os.path.join(temp_dir, "test_file.txt")
            test_content = "Тестовое содержимое файла"
            
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            print(f"\n=== Тестирование FileTool ===")
            if file_tool:
                try:
                    # Подготовим входные данные для FileTool
                    from core.application.tools.file_tool import FileToolInput
                    
                    # Тестируем операцию чтения
                    read_input = FileToolInput(
                        operation="read",
                        path=test_file_path
                    )
                    
                    print(f"Попытка чтения файла: {test_file_path}")
                    result = await file_tool.execute(read_input)
                    
                    print(f"Результат выполнения: success={result.success}")
                    if result.success:
                        print(f"Содержимое файла: {result.data.get('content', 'N/A')[:50]}...")
                    if result.error:
                        print(f"Ошибка: {result.error}")
                        
                except Exception as e:
                    print(f"Ошибка при выполнении FileTool: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("FileTool недоступен для тестирования")
            
            print("\n=== Завершение работы ===")
            
        finally:
            # Завершаем работу контекстов
            print("Завершение прикладного контекста...")
            if 'app_context' in locals():
                if hasattr(app_context, 'dispose') and callable(app_context.dispose):
                    await app_context.dispose()
                    
            print("Завершение инфраструктурного контекста...")
            await infra_context.shutdown()
    
    print("Тестирование завершено")


if __name__ == "__main__":
    asyncio.run(test_tools_context())