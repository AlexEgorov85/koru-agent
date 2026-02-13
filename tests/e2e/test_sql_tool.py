#!/usr/bin/env python3
"""
Скрипт для проверки работы SQLTool через ApplicationContext.
"""
import asyncio
import tempfile
import os
from pathlib import Path

from core.config.models import SystemConfig, AgentConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


async def test_sql_tool():
    """Тестирование SQLTool через ApplicationContext"""
    print("=== Тестирование SQLTool через ApplicationContext ===")
    
    # Создаем временную директорию для тестов
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Используем временную директорию: {temp_dir}")
        
        # Создаем системную конфигурацию
        system_config = SystemConfig(
            data_dir=temp_dir,
            log_dir=os.path.join(temp_dir, "logs")
        )
        
        # Добавим конфигурацию БД в системную конфигурацию
        from core.config.models import DBProviderConfig
        system_config.db_providers = {
            "default_db": DBProviderConfig(
                type_provider="sqlite",  # используем SQLite для тестирования
                enabled=True,
                parameters={
                    "database": os.path.join(temp_dir, "test.db"),  # используем временный файл БД
                    "pool_size": 5
                }
            )
        }
        
        # Создаем ProviderFactory и обновляем путь к инструментам
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

        # Создаем адаптер и фабрику
        temp_infra_context = InfrastructureContext(config=system_config)
        adapter = InfrastructureContextAdapter(temp_infra_context)
        provider_factory = ProviderFactory(adapter)
        
        # Обновляем путь к инструментам
        provider_factory.tools_dir = Path("core/application/tools")
        
        # Создаем инфраструктурный контекст
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
                    "sql_operations.select": "v1.0.0",
                    "sql_operations.version": "v1.0.0"
                },
                input_contract_versions={
                    "sql_operations.select": "v1.0.0",
                    "sql_operations.version": "v1.0.0"
                },
                output_contract_versions={
                    "sql_operations.select": "v1.0.0",
                    "sql_operations.version": "v1.0.0"
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
            
            # Попробуем получить SQLTool
            sql_tool = app_context.get_tool("sql_tool")
            if sql_tool:
                print(f"FOUND SQLTool: {type(sql_tool).__name__}")
                print(f"  - ComponentConfig: {hasattr(sql_tool, 'component_config')}")
                print(f"  - Side effects enabled: {sql_tool.component_config.side_effects_enabled}")
            else:
                print("MISSING SQLTool")
                
            # Проверим, есть ли провайдер БД
            db_provider = infra_context.get_provider("default_db")
            if db_provider:
                print(f"FOUND DB Provider: {type(db_provider).__name__}")
            else:
                print("MISSING DB Provider - проверим, есть ли хотя бы один провайдер:")
                for name, provider in infra_context._providers.items():
                    print(f"  Provider: {name} -> {type(provider).__name__}")
            
            print(f"\n=== Тестирование SQLTool ===")
            if sql_tool and db_provider:
                try:
                    # Подготовим входные данные для SQLTool
                    from core.application.tools.sql_tool import SQLToolInput
                    
                    # Попробуем выполнить запрос версии БД (универсальный запрос)
                    version_queries = [
                        "SELECT sqlite_version() AS version;",  # для SQLite
                        "SELECT version();",  # для PostgreSQL
                        "SELECT @@VERSION AS version;",  # для SQL Server
                        "SELECT 1 AS test;"  # простой тестовый запрос
                    ]
                    
                    for i, query in enumerate(version_queries):
                        print(f"\nПопытка {i+1}: Выполнение запроса: {query}")
                        try:
                            input_data = SQLToolInput(
                                sql=query,
                                max_rows=1
                            )
                            
                            result = await sql_tool.execute(input_data)
                            
                            print(f"Результат выполнения: success=True")
                            print(f"Количество строк: {result.rowcount}")
                            print(f"Колонки: {result.columns}")
                            print(f"Время выполнения: {result.execution_time:.4f} сек")
                            
                            if result.rows:
                                print(f"Данные: {result.rows[0]}")
                                
                            # Если запрос выполнился успешно, выходим из цикла
                            if result.rowcount > 0:
                                print(f"✓ Успешно выполнен запрос версии БД")
                                break
                                
                        except Exception as e:
                            print(f"Ошибка выполнения запроса {i+1}: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Ошибка при выполнении SQLTool: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("SQLTool или DB Provider недоступен для тестирования")
            
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
    asyncio.run(test_sql_tool())