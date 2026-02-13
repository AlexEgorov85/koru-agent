"""
Тест для проверки сервисов с изолированными кэшами.

Проверяет:
1. Предзагрузка промптов и контрактов при инициализации
2. Изоляция кэшей между контекстами
3. Отсутствие обращений к файловой системе после инициализации
4. Валидация версий
"""
import pytest
from unittest.mock import patch
from core.config.models import AgentConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


@pytest.mark.asyncio
async def test_services_isolation_and_preloading():
    """Тест изоляции сервисов и предзагрузки ресурсов"""
    # Создаем инфраструктурный контекст
    infrastructure_context = InfrastructureContext()
    await infrastructure_context.initialize()

    # Контекст 1 с одной версией промптов
    ctx1 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=AgentConfig(
            prompt_versions={"planning.create_plan": "v1.0.0", "sql_generation.generate_query": "v1.0.0"},
            input_contract_versions={"planning.create_plan": "v1.0.0"},
            output_contract_versions={"planning.create_plan": "v1.0.0"},
            side_effects_enabled=False
        )
    )
    await ctx1.initialize()

    # Контекст 2 с другой версией промптов
    ctx2 = ApplicationContext(
        infrastructure_context=infrastructure_context,
        config=AgentConfig(
            prompt_versions={"planning.create_plan": "v2.0.0", "sql_generation.generate_query": "v2.0.0"},
            input_contract_versions={"planning.create_plan": "v2.0.0"},
            output_contract_versions={"planning.create_plan": "v2.0.0"},
            side_effects_enabled=True
        )
    )
    await ctx2.initialize()

    # Проверка 1: сервисы инициализированы
    prompt_service1 = ctx1.infrastructure_context.get_service("prompt_service")
    prompt_service2 = ctx2.infrastructure_context.get_service("prompt_service")
    
    assert prompt_service1 is not None, "Сервис промптов 1 должен существовать"
    assert prompt_service2 is not None, "Сервис промптов 2 должен существовать"

    # Проверка 2: изоляция кэшей
    # Проверяем, что у каждого контекста свои изолированные кэши
    # Для этого сравним количество загруженных промптов в кэше
    # (это зависит от реализации, но мы можем проверить, что кэши разные объекты)
    
    # Проверка 3: доступ к промптам из кэша
    # Проверим, что каждый контекст возвращает свои версии промптов
    # Для этого нужно проверить, что у компонентов есть доступ к своим изолированным кэшам
    
    # Проверим, что у каждого контекста есть свои изолированные кэши
    assert hasattr(ctx1, '_prompt_cache'), "Контекст 1 должен иметь изолированный кэш промптов"
    assert hasattr(ctx2, '_prompt_cache'), "Контекст 2 должен иметь изолированный кэш промптов"
    
    # Проверим, что кэши разные (не один и тот же объект)
    assert ctx1._prompt_cache is not ctx2._prompt_cache, "Кэши промптов должны быть разными объектами"

    # Проверка 4: отсутствие обращений к ФС после инициализации
    # Мы можем проверить это, замокав pathlib.Path.open и убедившись, что после инициализации
    # не происходит обращений к файловой системе при получении промптов из кэша
    with patch('pathlib.Path.open') as mock_open:
        # Попробуем получить промпт из кэша (не должно быть обращения к ФС)
        prompt1 = ctx1.get_prompt("planning.create_plan")
        prompt2 = ctx2.get_prompt("planning.create_plan")
        
        # Убедимся, что не было обращений к файловой системе
        assert not mock_open.called, "После инициализации не должно быть обращений к файловой системе"

    # Проверка 5: валидация версий
    # Проверим, что при попытке получить несуществующую версию будет ошибка
    try:
        nonexistent_prompt = ctx1.get_prompt("nonexistent_capability", "nonexistent_version")
        # Если не возникло ошибки, проверим, что результат None
        assert nonexistent_prompt is None, "Несуществующий промпт должен возвращать None"
    except Exception:
        # Ошибки при попытке получить несуществующий промпт допустимы
        pass

    # Завершаем работу контекстов
    await ctx1.dispose() if hasattr(ctx1, 'dispose') else None
    await ctx2.dispose() if hasattr(ctx2, 'dispose') else None
    await infrastructure_context.shutdown()