"""
КРИТИЧЕСКИЙ ТЕСТ: проверка изоляции кэшей контрактов между контекстами.
"""
import asyncio
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig


@pytest.mark.asyncio
async def test_contract_cache_isolation():
    """КРИТИЧЕСКИЙ ТЕСТ: проверка изоляции кэшей контрактов между контекстами."""
    
    # Создаём временную структуру контрактов
    with TemporaryDirectory() as tmpdir:
        import json  # добавляем импорт json в начале тела функции
        data_dir = Path(tmpdir)
        contracts_dir = data_dir / "contracts"
        contracts_dir.mkdir()
        
        # Создаём подкаталог для промптов
        prompts_dir = data_dir / "prompts"
        prompts_dir.mkdir()
        test_cap_dir = prompts_dir / "test" / "capability"
        test_cap_dir.mkdir(parents=True)
        
        # Создаём файлы промптов (нужны для инициализации)
        prompt_v1_data = {
            "content": "Test prompt v1.0.0",
            "metadata": {
                "version": "v1.0.0",
                "skill": "test",
                "capability": "test.capability",
                "author": "test"
            }
        }
        (test_cap_dir / "v1.0.0.json").write_text(json.dumps(prompt_v1_data, ensure_ascii=False), encoding='utf-8')

        # Создаём два разных контракта для одной capability
        contract_v1_input = {
            "capability_name": "test_capability",
            "version": "v1.0.0",
            "direction": "input",
            "schema": {"type": "object", "properties": {"field1": {"type": "string"}}}
        }
        (contracts_dir / "test_capability_input_v1.0.0.json").write_text(json.dumps(contract_v1_input, ensure_ascii=False), encoding='utf-8')

        contract_v2_input = {
            "capability_name": "test_capability",
            "version": "v2.0.0",
            "direction": "input",
            "schema": {"type": "object", "properties": {"field2": {"type": "number"}}}
        }
        (contracts_dir / "test_capability_input_v2.0.0.json").write_text(json.dumps(contract_v2_input, ensure_ascii=False), encoding='utf-8')

        contract_v1_output = {
            "capability_name": "test_capability",
            "version": "v1.0.0",
            "direction": "output",
            "schema": {"type": "object", "properties": {"result1": {"type": "string"}}}
        }
        (contracts_dir / "test_capability_output_v1.0.0.json").write_text(json.dumps(contract_v1_output, ensure_ascii=False), encoding='utf-8')  # Используем v1 структуру для v1 output

        contract_v2_output = {
            "capability_name": "test_capability",
            "version": "v2.0.0",
            "direction": "output",
            "schema": {"type": "object", "properties": {"result2": {"type": "number"}}}
        }
        (contracts_dir / "test_capability_output_v2.0.0.json").write_text(json.dumps(contract_v2_output, ensure_ascii=False), encoding='utf-8')
        
        # Инфраструктурный контекст
        infra_config = SystemConfig(
            data_dir=str(data_dir),
            llm_providers={},
            db_providers={}
        )
        infra = InfrastructureContext(infra_config)
        await infra.initialize()
        
        # === Контекст 1: использует v1.0.0 ===
        from core.config.agent_config import AgentConfig
        agent_config1 = AgentConfig(
            prompt_versions={"test.capability": "v1.0.0"},  # Добавляем хотя бы один промпт для правильной инициализации
            contract_versions={"test_capability": "v1.0.0"}
        )
        ctx1 = ApplicationContext(
            infrastructure_context=infra,
            config=agent_config1
        )
        await ctx1.initialize()

        # === Контекст 2: использует v2.0.0 ===
        agent_config2 = AgentConfig(
            prompt_versions={"test.capability": "v1.0.0"},  # Добавляем хотя бы один промпт для правильной инициализации
            contract_versions={"test_capability": "v2.0.0"}
        )
        ctx2 = ApplicationContext(
            infrastructure_context=infra,
            config=agent_config2
        )
        await ctx2.initialize()
        
        # === ПРОВЕРКА ИЗОЛЯЦИИ ===
        input_contract1 = ctx1.get_input_contract("test_capability")
        input_contract2 = ctx2.get_input_contract("test_capability")
        
        output_contract1 = ctx1.get_output_contract("test_capability")
        output_contract2 = ctx2.get_output_contract("test_capability")
        
        # Входные контракты должны быть РАЗНЫМИ
        assert input_contract1 != input_contract2, (
            "КРИТИЧЕСКАЯ ОШИБКА: входные кэши контрактов НЕ изолированы!"
        )
        
        # Выходные контракты должны быть РАЗНЫМИ
        assert output_contract1 != output_contract2, (
            "КРИТИЧЕСКАЯ ОШИБКА: выходные кэши контрактов НЕ изолированы!"
        )
        
        # Проверка: разные объекты кэшей в памяти
        assert id(ctx1._contract_service._cached_contracts) != id(ctx2._contract_service._cached_contracts), \
            "Кэши контрактов должны быть разными объектами в памяти"
        
        # Проверка: общий инфраструктурный контекст
        assert id(ctx1.infrastructure_context) == id(ctx2.infrastructure_context), \
            "Инфраструктурный контекст должен быть общим"
        
        print("✅ Тест изоляции контрактов пройден: кэши полностью изолированы")