"""
Тест изоляции сервисов между разными экземплярами ApplicationContext.
"""
import pytest
import tempfile
import os
from pathlib import Path

from core.config.models import SystemConfig, AgentConfig
from core.config.component_config import ComponentConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


@pytest.mark.asyncio
async def test_prompt_service_isolation():
    """Проверка изоляции кэшей промптов между разными экземплярами ApplicationContext."""
    
    # Создаем временную директорию для тестовых промптов
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Создаем тестовые промпты разных версий
        prompts_dir = temp_path / "prompts" / "skills" / "test"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        # Создаем промпт версии 1.0.0
        v1_prompt_path = prompts_dir / "cap_v1.0.0.yaml"
        v1_prompt_path.write_text("""capability: "test.cap"
version: "v1.0.0"
skill: "test"
author: "test"
content: "This is prompt version 1.0.0"
""")

        # Создаем промпт версии 2.0.0
        v2_prompt_path = prompts_dir / "cap_v2.0.0.yaml"
        v2_prompt_path.write_text("""capability: "test.cap"
version: "v2.0.0"
skill: "test"
author: "test"
content: "This is prompt version 2.0.0"
""")
        
        # Создаем системную конфигурацию
        config = SystemConfig(data_dir=str(temp_path))
        
        # Создаем инфраструктурный контекст
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            # Контекст 1 с версией v1.0.0
            ctx1_config = AgentConfig(
                prompt_versions={"test.cap": "v1.0.0"},
                input_contract_versions={},
                output_contract_versions={}
            )
            ctx1 = ApplicationContext(infra, ctx1_config)
            await ctx1.initialize()
            
            # Контекст 2 с версией v2.0.0
            ctx2_config = AgentConfig(
                prompt_versions={"test.cap": "v2.0.0"},
                input_contract_versions={},
                output_contract_versions={}
            )
            ctx2 = ApplicationContext(infra, ctx2_config)
            await ctx2.initialize()
            
            # Проверка изоляции экземпляров сервисов
            assert id(ctx1._prompt_service) != id(ctx2._prompt_service), \
                "Должны быть разные экземпляры PromptService"
            
            # Проверка изоляции кэшей
            assert id(ctx1._prompt_service._cached_prompts) != id(ctx2._prompt_service._cached_prompts), \
                "Кэши должны быть разными объектами"
            
            # Проверка разных значений в кэшах
            p1 = ctx1.get_prompt("test.cap")
            p2 = ctx2.get_prompt("test.cap")
            
            assert p1 != p2, "Промпты должны отличаться для разных версий"
            assert "1.0.0" in p1, f"Промпт 1 должен содержать 1.0.0, но содержит: {p1}"
            assert "2.0.0" in p2, f"Промпт 2 должен содержать 2.0.0, но содержит: {p2}"
            
            print(f"Промпт 1: {p1}")
            print(f"Промпт 2: {p2}")
            
        finally:
            await infra.shutdown()


@pytest.mark.asyncio
async def test_contract_service_isolation():
    """Проверка изоляции кэшей контрактов между разными экземплярами ApplicationContext."""
    
    # Создаем временную директорию для тестовых контрактов
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Создаем тестовые контракты разных версий
        # ContractStorage ищет в {data_dir}/contracts, поэтому создаем файлы там
        contracts_dir = temp_path / "contracts"  # Это директория, где ContractStorage будет искать файлы
        contracts_dir.mkdir(parents=True, exist_ok=True)

        # Создаем входной контракт версии 1.0.0
        input_v1_path = contracts_dir / "test_cap_input_v1.0.0.json"
        input_v1_path.write_text("""{
"capability_name": "test.cap",
"version": "v1.0.0",
"direction": "input",
"schema": {
  "type": "object",
  "properties": {
    "param1": {
      "type": "string",
      "description": "Parameter for version 1"
    }
  }
}
}
""")

        # Создаем входной контракт версии 2.0.0
        input_v2_path = contracts_dir / "test_cap_input_v2.0.0.json"
        input_v2_path.write_text("""{
"capability_name": "test.cap",
"version": "v2.0.0",
"direction": "input",
"schema": {
  "type": "object",
  "properties": {
    "param2": {
      "type": "integer",
      "description": "Parameter for version 2"
    }
  }
}
}
""")

        # Создаем выходной контракт версии 1.0.0 (для тестирования)
        output_v1_path = contracts_dir / "test_cap_output_v1.0.0.json"
        output_v1_path.write_text("""{
"capability_name": "test.cap",
"version": "v1.0.0",
"direction": "output",
"schema": {
  "type": "object",
  "properties": {
    "result": {
      "type": "string",
      "description": "Result of the operation"
    }
  }
}
}
""")

        # Создаем выходной контракт версии 2.0.0 (для тестирования)
        output_v2_path = contracts_dir / "test_cap_output_v2.0.0.json"
        output_v2_path.write_text("""{
"capability_name": "test.cap",
"version": "v2.0.0",
"direction": "output",
"schema": {
  "type": "object",
  "properties": {
    "result": {
      "type": "string",
      "description": "Result of the operation"
    }
  }
}
}
""")
        
        # Создаем системную конфигурацию
        config = SystemConfig(data_dir=str(temp_path))
        
        # Создаем инфраструктурный контекст
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            # Контекст 1 с версией v1.0.0
            ctx1_config = AgentConfig(
                prompt_versions={},
                contract_versions={"test.cap": "v1.0.0"}
            )
            ctx1 = ApplicationContext(infra, ctx1_config)
            await ctx1.initialize()

            # Контекст 2 с версией v2.0.0
            ctx2_config = AgentConfig(
                prompt_versions={},
                contract_versions={"test.cap": "v2.0.0"}
            )
            ctx2 = ApplicationContext(infra, ctx2_config)
            await ctx2.initialize()
            
            # Проверка изоляции экземпляров сервисов
            assert id(ctx1._contract_service) != id(ctx2._contract_service), \
                "Должны быть разные экземпляры ContractService"
            
            # Проверка изоляции кэшей
            assert id(ctx1._contract_service._cached_contracts) != id(ctx2._contract_service._cached_contracts), \
                "Кэши контрактов должны быть разными объектами"
            
            # Проверка разных значений в кэшах
            schema1 = ctx1.get_input_contract("test.cap")
            schema2 = ctx2.get_input_contract("test.cap")
            
            assert schema1 != schema2, "Схемы контрактов должны отличаться для разных версий"
            assert "param1" in schema1["schema"]["properties"], f"Схема 1 должна содержать param1, но содержит: {schema1}"
            assert "param2" in schema2["schema"]["properties"], f"Схема 2 должна содержать param2, но содержит: {schema2}"
            
            print(f"Схема 1: {schema1}")
            print(f"Схема 2: {schema2}")
            
        finally:
            await infra.shutdown()


@pytest.mark.asyncio
async def test_get_resource_returns_isolated_services():
    """Проверка, что get_resource возвращает изолированные сервисы."""
    
    # Создаем временную директорию для тестовых промптов
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Создаем тестовые промпты
        prompts_dir = temp_path / "prompts" / "skills" / "test"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        v1_prompt_path = prompts_dir / "cap_v1.0.0.yaml"
        v1_prompt_path.write_text("""capability: "test.cap"
version: "v1.0.0"
skill: "test"
author: "test"
content: "Prompt version 1.0.0"
""")
        
        # Создаем системную конфигурацию
        config = SystemConfig(data_dir=str(temp_path))
        
        # Создаем инфраструктурный контекст
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        try:
            # Создаем два контекста
            ctx1_config = AgentConfig(
                prompt_versions={"test.cap": "v1.0.0"},
                input_contract_versions={},
                output_contract_versions={}
            )
            ctx1 = ApplicationContext(infra, ctx1_config)
            await ctx1.initialize()
            
            ctx2_config = AgentConfig(
                prompt_versions={"test.cap": "v1.0.0"},  # Та же версия
                input_contract_versions={},
                output_contract_versions={}
            )
            ctx2 = ApplicationContext(infra, ctx2_config)
            await ctx2.initialize()
            
            # Проверяем, что get_resource возвращает изолированные сервисы
            ps1 = ctx1.get_resource("prompt_service")
            ps2 = ctx2.get_resource("prompt_service")
            
            assert ps1 is ctx1._prompt_service, "get_resource должен возвращать изолированный сервис"
            assert ps2 is ctx2._prompt_service, "get_resource должен возвращать изолированный сервис"
            assert ps1 is not ps2, "Сервисы должны быть разными объектами"
            
            cs1 = ctx1.get_resource("contract_service")
            cs2 = ctx2.get_resource("contract_service")
            
            assert cs1 is ctx1._contract_service, "get_resource должен возвращать изолированный сервис"
            assert cs2 is ctx2._contract_service, "get_resource должен возвращать изолированный сервис"
            assert cs1 is not cs2, "Сервисы должны быть разными объектами"
            
        finally:
            await infra.shutdown()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_prompt_service_isolation())
    asyncio.run(test_contract_service_isolation())
    asyncio.run(test_get_resource_returns_isolated_services())
    print("Все тесты пройдены успешно!")