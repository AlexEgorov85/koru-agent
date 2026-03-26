"""
Р®РЅРёС‚-С‚РµСЃС‚С‹ РґР»СЏ InfrastructureContext.

РўРµСЃС‚РёСЂСѓРµС‚:
- Р›РѕРіРёРєСѓ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё/Р·Р°РІРµСЂС€РµРЅРёСЏ
- Р РµРіРёСЃС‚СЂР°С†РёСЋ С‚РѕР»СЊРєРѕ РІРєР»СЋС‡С‘РЅРЅС‹С… РїСЂРѕРІР°Р№РґРµСЂРѕРІ
- РРјРјСѓС‚Р°Р±РµР»СЊРЅРѕСЃС‚СЊ РїРѕСЃР»Рµ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext


@pytest.mark.asyncio
async def test_infrastructure_registers_only_enabled_providers():
    """РџСЂРѕРІРµСЂРєР°: С‚РѕР»СЊРєРѕ РІРєР»СЋС‡С‘РЅРЅС‹Рµ РїСЂРѕРІР°Р№РґРµСЂС‹ СЂРµРіРёСЃС‚СЂРёСЂСѓСЋС‚СЃСЏ"""
    # РџРѕРґРіРѕС‚РѕРІРєР° РєРѕРЅС„РёРіСѓСЂР°С†РёРё СЃ РІРєР»СЋС‡С‘РЅРЅС‹Рј Рё РѕС‚РєР»СЋС‡С‘РЅРЅС‹Рј РїСЂРѕРІР°Р№РґРµСЂР°РјРё
    config = SystemConfig(
        llm_providers={
            "prod_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="qwen-4b",
                enabled=True,
                parameters={"model_name": "qwen-4b", "temperature": 0.7}
            ),
            "backup_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="qwen-4b",
                enabled=False,  # в†ђ РћС‚РєР»СЋС‡С‘РЅ
                parameters={"model_name": "qwen-4b", "temperature": 0.7}
            ),
        },
        db_providers={
            "primary_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={"database": "test_primary.db", "host": "localhost"}
            ),
            "secondary_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=False,  # в†ђ РћС‚РєР»СЋС‡С‘РЅ
                parameters={"database": "test_secondary.db", "host": "localhost"}
            ),
        }
    )
    
    # РЎРѕР·РґР°РЅРёРµ Рё РёРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РёРЅС„СЂР°СЃС‚СЂСѓРєС‚СѓСЂРЅРѕРіРѕ РєРѕРЅС‚РµРєСЃС‚Р°
    infra = InfrastructureContext(config)
    
    # Р’С‹Р·РѕРІ РјРµС‚РѕРґР° РёРЅРёС†РёР°Р»РёР·Р°С†РёРё, РєРѕС‚РѕСЂС‹Р№ СЃР°Рј СЂРµРіРёСЃС‚СЂРёСЂСѓРµС‚ РїСЂРѕРІР°Р№РґРµСЂРѕРІ
    await infra.initialize()
    
    # РџСЂРѕРІРµСЂРєР°: С‚РѕР»СЊРєРѕ РІРєР»СЋС‡С‘РЅРЅС‹Рµ РїСЂРѕРІР°Р№РґРµСЂС‹ РІ СЂРµРµСЃС‚СЂРµ
    resource_names = infra.resource_registry.get_all_names()
    
    # prod_llm РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ
    assert "prod_llm" in resource_names
    # backup_llm РЅРµ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ
    assert "backup_llm" not in resource_names
    
    # primary_db РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ
    assert "primary_db" in resource_names
    # secondary_db РЅРµ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ
    assert "secondary_db" not in resource_names


@pytest.mark.asyncio
async def test_infrastructure_immutable_after_init():
    """РџСЂРѕРІРµСЂРєР°: РєРѕРЅС‚РµРєСЃС‚ СЃС‚Р°РЅРѕРІРёС‚СЃСЏ РЅРµРёР·РјРµРЅСЏРµРјС‹Рј РїРѕСЃР»Рµ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # РџРѕРїС‹С‚РєР° РёР·РјРµРЅРµРЅРёСЏ РїРѕСЃР»Рµ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё в†’ РёСЃРєР»СЋС‡РµРЅРёРµ
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.new_attribute = "value"


@pytest.mark.asyncio
async def test_infrastructure_cannot_be_modified_after_init():
    """РџСЂРѕРІРµСЂРєР°: РЅРµР»СЊР·СЏ РёР·РјРµРЅСЏС‚СЊ Р°С‚СЂРёР±СѓС‚С‹ РїРѕСЃР»Рµ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        await infra.initialize()
    
    # РџРѕРїС‹С‚РєР° РёР·РјРµРЅРёС‚СЊ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёР№ Р°С‚СЂРёР±СѓС‚
    with pytest.raises(AttributeError, match="immutable after initialization"):
        infra.config = SystemConfig()


def test_infrastructure_context_initialization_state():
    """РџСЂРѕРІРµСЂРєР° РЅР°С‡Р°Р»СЊРЅРѕРіРѕ СЃРѕСЃС‚РѕСЏРЅРёСЏ РєРѕРЅС‚РµРєСЃС‚Р° РґРѕ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # РџСЂРѕРІРµСЂРєР° РЅР°С‡Р°Р»СЊРЅС‹С… Р·РЅР°С‡РµРЅРёР№
    assert infra._initialized is False
    assert infra.id is not None
    assert infra.config == config
    assert infra.lifecycle_manager is None
    assert infra.event_bus is None
    assert infra.resource_registry is None


@pytest.mark.asyncio
async def test_infrastructure_initialize_twice():
    """РџСЂРѕРІРµСЂРєР°: РїРѕРІС‚РѕСЂРЅР°СЏ РёРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РЅРµ РІС‹Р·С‹РІР°РµС‚ РѕС€РёР±РѕРє"""
    config = SystemConfig()
    infra = InfrastructureContext(config)
    
    # РњРѕРєРёСЂСѓРµРј РІРЅСѓС‚СЂРµРЅРЅРёРµ РјРµС‚РѕРґС‹
    with patch.object(infra, '_register_providers_from_config', new_callable=AsyncMock) as mock_register:
        mock_register.return_value = None
        
        # РџРµСЂРІР°СЏ РёРЅРёС†РёР°Р»РёР·Р°С†РёСЏ
        result1 = await infra.initialize()
        assert result1 is True
        assert infra._initialized is True
        
        # Р’С‚РѕСЂР°СЏ РёРЅРёС†РёР°Р»РёР·Р°С†РёСЏ (РґРѕР»Р¶РЅР° РІРµСЂРЅСѓС‚СЊ True Р±РµР· РѕС€РёР±РѕРє)
        result2 = await infra.initialize()
        assert result2 is True


@pytest.mark.asyncio
async def test_get_provider_returns_correct_instance():
    """РџСЂРѕРІРµСЂРєР°: РїРѕР»СѓС‡РµРЅРёРµ РїСЂРѕРІР°Р№РґРµСЂР° РїРѕ РёРјРµРЅРё СЂР°Р±РѕС‚Р°РµС‚ РєРѕСЂСЂРµРєС‚РЅРѕ"""
    config = SystemConfig()
    infra = InfrastructureContext(config)

    # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј РёРЅС„СЂР°СЃС‚СЂСѓРєС‚СѓСЂСѓ
    await infra.initialize()

    # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј РјРѕРє-РїСЂРѕРІР°Р№РґРµСЂ С‡РµСЂРµР· СЂРµРµСЃС‚СЂ СЂРµСЃСѓСЂСЃРѕРІ
    from core.models.data.resource import ResourceInfo, ResourceType
    mock_provider = MagicMock()
    resource_info = ResourceInfo(
        name="test_provider",
        resource_type=ResourceType.LLM,
        instance=mock_provider
    )
    infra.resource_registry.register_resource(resource_info)

    # РџРѕР»СѓС‡Р°РµРј РїСЂРѕРІР°Р№РґРµСЂ
    retrieved = infra.get_provider("test_provider")

    assert retrieved is mock_provider


@pytest.mark.asyncio
async def test_get_nonexistent_provider_returns_none():
    """РџСЂРѕРІРµСЂРєР°: РїРѕР»СѓС‡РµРЅРёРµ РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ РїСЂРѕРІР°Р№РґРµСЂР° РІРѕР·РІСЂР°С‰Р°РµС‚ None"""
    config = SystemConfig()
    infra = InfrastructureContext(config)

    # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј РёРЅС„СЂР°СЃС‚СЂСѓРєС‚СѓСЂСѓ
    await infra.initialize()

    # РџРѕР»СѓС‡Р°РµРј РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёР№ РїСЂРѕРІР°Р№РґРµСЂ
    retrieved = infra.get_provider("nonexistent_provider")

    assert retrieved is None


@pytest.mark.asyncio
async def test_get_resource_returns_correct_instance():
    """РџСЂРѕРІРµСЂРєР°: РїРѕР»СѓС‡РµРЅРёРµ СЂРµСЃСѓСЂСЃР° РїРѕ РёРјРµРЅРё СЂР°Р±РѕС‚Р°РµС‚ РєРѕСЂСЂРµРєС‚РЅРѕ"""
    config = SystemConfig()
    infra = InfrastructureContext(config)

    # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј РєРѕРЅС‚РµРєСЃС‚
    await infra.initialize()

    # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј С‚РµСЃС‚РѕРІС‹Р№ СЂРµСЃСѓСЂСЃ
    from core.models.data.resource import ResourceInfo, ResourceType
    test_resource = MagicMock()
    resource_info = ResourceInfo(
        name="test_resource",
        resource_type=ResourceType.SERVICE,
        instance=test_resource
    )
    infra.resource_registry.register_resource(resource_info)

    # РџРѕР»СѓС‡Р°РµРј СЂРµСЃСѓСЂСЃ
    retrieved = infra.get_resource("test_resource")
    assert retrieved is test_resource


@pytest.mark.asyncio
async def test_shutdown_sets_initialized_to_false():
    """РџСЂРѕРІРµСЂРєР°: shutdown СѓСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ _initialized РІ False"""
    config = SystemConfig()
    infra = InfrastructureContext(config)

    # РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ
    await infra.initialize()

    assert infra._initialized is True

    # Р—Р°РІРµСЂС€РµРЅРёРµ СЂР°Р±РѕС‚С‹
    await infra.shutdown()

    assert infra._initialized is False
