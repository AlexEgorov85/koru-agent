"""
КРИТИЧЕСКИЙ ТЕСТ: проверка изоляции кэшей промптов между контекстами.
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
async def test_prompt_cache_isolation():
    """КРИТИЧЕСКИЙ ТЕСТ: проверка изоляции кэшей промптов между контекстами."""
    
    # Создаём временную структуру промптов
    with TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        prompts_dir = data_dir / "prompts"
        prompts_dir.mkdir()
        
        # Создаём поддиректорию для тестовой capability
        test_cap_dir = prompts_dir / "test" / "capability"
        test_cap_dir.mkdir(parents=True)
        
        # Создаём два разных промпта для одной capability
        import json
        prompt_v1_data = {
            "content": "Prompt v1.0.0",
            "metadata": {
                "version": "v1.0.0",
                "skill": "test",
                "capability": "test.capability",
                "author": "test"
            }
        }
        (test_cap_dir / "v1.0.0.json").write_text(json.dumps(prompt_v1_data, ensure_ascii=False), encoding='utf-8')
        
        prompt_v2_data = {
            "content": "Prompt v2.0.0 DIFFERENT",
            "metadata": {
                "version": "v2.0.0",
                "skill": "test",
                "capability": "test.capability",
                "author": "test"
            }
        }
        (test_cap_dir / "v2.0.0.json").write_text(json.dumps(prompt_v2_data, ensure_ascii=False), encoding='utf-8')
        
        # Инфраструктурный контекст
        infra_config = SystemConfig(
            data_dir=str(data_dir),
            llm_providers={},
            db_providers={}
        )
        infra = InfrastructureContext(infra_config)
        await infra.initialize()
        
        # === Контекст 1: использует v1.0.0 ===
        component_config1 = ComponentConfig(
            variant_id="ctx1",
            prompt_versions={"test.capability": "v1.0.0"},
            input_contract_versions={},
            output_contract_versions={}
        )
        ctx1 = ApplicationContext(
            infrastructure_context=infra,
            config=component_config1
        )
        await ctx1.initialize()
        
        # === Контекст 2: использует v2.0.0 ===
        component_config2 = ComponentConfig(
            variant_id="ctx2",
            prompt_versions={"test.capability": "v2.0.0"},
            input_contract_versions={},
            output_contract_versions={}
        )
        ctx2 = ApplicationContext(
            infrastructure_context=infra,
            config=component_config2
        )
        await ctx2.initialize()
        
        # === ПРОВЕРКА ИЗОЛЯЦИИ ===
        prompt1 = ctx1.get_prompt("test.capability")
        prompt2 = ctx2.get_prompt("test.capability")
        
        # Должны быть РАЗНЫМИ
        assert prompt1 != prompt2, (
            "КРИТИЧЕСКАЯ ОШИБКА: кэши промптов НЕ изолированы!\n"
            f"Ctx1: {prompt1}\nCtx2: {prompt2}"
        )
        
        # Должны соответствовать ожидаемым версиям
        assert "v1.0.0" in prompt1 or "v1" in prompt1.lower()
        assert "v2.0.0" in prompt2 or "v2" in prompt2.lower() or "ДРУГОЙ" in prompt2
        
        # Проверка: разные объекты кэшей в памяти
        assert id(ctx1._prompt_service._cached_prompts) != id(ctx2._prompt_service._cached_prompts), \
            "Кэши должны быть разными объектами в памяти"
        
        # Проверка: общий инфраструктурный контекст
        assert id(ctx1.infrastructure_context) == id(ctx2.infrastructure_context), \
            "Инфраструктурный контекст должен быть общим"
        
        print("✅ Тест изоляции промптов пройден: кэши полностью изолированы")