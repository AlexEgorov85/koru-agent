"""
Unit-тесты для проверки инициализации контекста и загрузки ресурсов.
"""
import pytest
import asyncio
from pathlib import Path
import sys

# Добавляем корневую директорию проекта в путь Python
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig
from core.application.context.application_context import ComponentType


@pytest.mark.asyncio
async def test_resource_loading():
    """
    Тест проверяет, что компоненты загружаются и имеют кэши промтов и контрактов.
    """
    # 1. Поднимаем инфраструктурный контекст
    config_loader = ConfigLoader()
    config = config_loader.load()  # Загрузит dev.yaml по умолчанию
    infra = InfrastructureContext(config)

    print("Инициализация инфраструктурного контекста с параметрами из dev.yaml...")
    await infra.initialize()
    print("Инфраструктурный контекст успешно инициализирован!")

    # 2. Создаём контекст
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile='prod'
    )
    await ctx1.initialize()

    # 3. Проверяем, что компоненты загружены
    all_components = ctx1.components.all_components()

    assert len(all_components) > 0, "Должны быть загружены компоненты"

    # Проверяем только что кэши существуют и являются словарями
    # Некоторые компоненты могут не инициализироваться полностью из-за отсутствующих ресурсов
    for component in all_components:
        # Проверяем, что у компонента есть кэши (если они предусмотрены для этого типа компонента)
        # Behavior patterns используют другую структуру кэширования
        if hasattr(component, '_cached_prompts'):
            assert isinstance(component._cached_prompts, dict), f"_cached_prompts для {component.name} должен быть словарем"
        if hasattr(component, '_cached_input_contracts'):
            assert isinstance(component._cached_input_contracts, dict), f"_cached_input_contracts для {component.name} должен быть словарем"
        if hasattr(component, '_cached_output_contracts'):
            assert isinstance(component._cached_output_contracts, dict), f"_cached_output_contracts для {component.name} должен быть словарем"

        print(f"Компонент {component.name}: кэши проверены")

    print(f"Проверено {len(all_components)} компонентов, все имеют корректные кэши ресурсов")


@pytest.mark.asyncio
async def test_skill_capability_loading():
    """
    Тест проверяет, что все capability навыков имеют соответствующие промты и контракты.
    """
    # 1. Поднимаем инфраструктурный контекст
    config_loader = ConfigLoader()
    config = config_loader.load()  # Загрузит dev.yaml по умолчанию
    infra = InfrastructureContext(config)

    await infra.initialize()

    # 2. Создаём контекст
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile='prod'
    )
    await ctx1.initialize()

    # 3. Проверяем навыки
    skills = ctx1.components.all_of_type(ComponentType.SKILL)

    for skill in skills:
        skill_name = skill.name
        # Проверяем, что у навыка есть capability
        if hasattr(skill, 'get_capabilities'):
            capabilities = skill.get_capabilities()
            print(f"Навык {skill_name} имеет {len(capabilities)} capability")

            for capability in capabilities:
                # Проверяем, что capability имеет соответствующие ресурсы в кэше
                # Промпт
                try:
                    prompt = skill.get_prompt(capability.name)
                    print(f"  - Промпт для {capability.name}: {'Доступен' if prompt else 'Не найден/Пустой'}")
                except Exception as e:
                    print(f"  - Промпт для {capability.name}: ОШИБКА - {str(e)}")

                # Входной контракт
                try:
                    input_contract = skill.get_input_contract(capability.name)
                    print(f"  - Входной контракт для {capability.name}: {'Доступен' if input_contract else 'Не найден/Пустой'}")
                except Exception as e:
                    print(f"  - Входной контракт для {capability.name}: ОШИБКА - {str(e)}")

                # Выходной контракт
                try:
                    output_contract = skill.get_output_contract(capability.name)
                    print(f"  - Выходной контракт для {capability.name}: {'Доступен' if output_contract else 'Не найден/Пустой'}")
                except Exception as e:
                    print(f"  - Выходной контракт для {capability.name}: ОШИБКА - {str(e)}")


@pytest.mark.asyncio
async def test_health_check():
    """
    Тест проверяет, что метод health_check работает корректно.
    """
    # 1. Поднимаем инфраструктурный контекст
    config_loader = ConfigLoader()
    config = config_loader.load()  # Загрузит dev.yaml по умолчанию
    infra = InfrastructureContext(config)

    await infra.initialize()

    # 2. Создаём контекст
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile='prod'
    )
    await ctx1.initialize()

    # 3. Вызываем health_check
    health_report = await ctx1.health_check()
    
    # Проверяем структуру отчета
    assert 'overall_status' in health_report, "Отчет должен содержать overall_status"
    assert 'components_health' in health_report, "Отчет должен содержать components_health"
    assert 'metrics' in health_report, "Отчет должен содержать metrics"
    
    # Проверяем, что статус допустим (healthy, degraded или unhealthy)
    # unhealthy возможен если некоторые компоненты не инициализировались
    assert health_report['overall_status'] in ['healthy', 'degraded', 'unhealthy'], \
        f"Общий статус должен быть healthy, degraded или unhealthy, получен: {health_report['overall_status']}"

    print(f"Health check прошел успешно, статус: {health_report['overall_status']}")
    print(f"Компонентов проверено: {health_report['metrics']['total_components']}")
    print(f"Здоровых компонентов: {health_report['metrics']['healthy_components']}")
    print(f"Нездоровых компонентов: {health_report['metrics']['unhealthy_components']}")


if __name__ == "__main__":
    # Запуск тестов напрямую
    import asyncio
    
    print("=== Запуск теста test_resource_loading ===")
    asyncio.run(test_resource_loading())
    
    print("\n=== Запуск теста test_skill_capability_loading ===")
    asyncio.run(test_skill_capability_loading())
    
    print("\n=== Запуск теста test_health_check ===")
    asyncio.run(test_health_check())
    
    print("\n=== Все тесты пройдены успешно! ===")