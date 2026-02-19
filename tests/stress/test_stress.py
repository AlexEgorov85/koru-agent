"""
Стресс-тесты для Agent_v5.

Запуск:
    pytest tests/stress/ -v -m stress
    pytest tests/stress/test_stress.py::test_concurrent_agents -v
"""
import pytest
import asyncio
import time
from pathlib import Path

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


# ============================================================================
# STRESS TESTS: Параллельные агенты
# ============================================================================

@pytest.mark.stress
@pytest.mark.parametrize("agent_count", [10, 25, 50])
async def test_concurrent_agents(agent_count):
    """
    Стресс-тест: Инициализация множества агентов параллельно.
    
    Цель: Проверка стабильности при высокой нагрузке.
    """
    async def create_agent(agent_id):
        config = SystemConfig(data_dir="./data", debug=False)
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        app_config = AppConfig.from_registry(profile='prod')
        app_context = ApplicationContext(
            infrastructure_context=infra,
            config=app_config,
            profile='prod'
        )
        await app_context.initialize()
        
        # Проверка что компоненты загружены
        skills = app_context.components.all_of_type(
            app_context.ComponentType.SKILL
        )
        assert len(skills) > 0
        
        return app_context
    
    # Создаем агентов параллельно
    start_time = time.perf_counter()
    
    tasks = [create_agent(i) for i in range(agent_count)]
    contexts = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.perf_counter() - start_time
    
    # Проверка результатов
    successful = sum(1 for c in contexts if not isinstance(c, Exception))
    failed = sum(1 for c in contexts if isinstance(c, Exception))
    
    print(f"\nАгентов создано: {successful}/{agent_count}")
    print(f"Время: {elapsed:.2f} сек")
    print(f"Среднее время на агента: {elapsed/agent_count*1000:.2f} мс")
    
    assert successful == agent_count, f"{failed} агентов не удалось создать"
    
    # Cleanup
    for ctx in contexts:
        if not isinstance(ctx, Exception):
            # Находим infra_context через closure
            pass  # В реальном тесте нужно сохранить infra для shutdown


@pytest.mark.stress
async def test_memory_leak_detection():
    """
    Стресс-тест: Проверка на утечки памяти.
    
    Цель: Обнаружение утечек при длительной работе.
    """
    import gc
    import tracemalloc
    
    tracemalloc.start()
    
    iterations = 10
    snapshots = []
    
    for i in range(iterations):
        # Создаем и уничтожаем контекст
        config = SystemConfig(data_dir="./data", debug=False)
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        app_config = AppConfig.from_registry(profile='prod')
        app_context = ApplicationContext(
            infrastructure_context=infra,
            config=app_config,
            profile='prod'
        )
        await app_context.initialize()
        
        # Делаем снимок памяти
        snapshot = tracemalloc.take_snapshot()
        snapshots.append(snapshot)
        
        await infra.shutdown()
        
        # Принудительная сборка мусора
        gc.collect()
    
    # Сравниваем снимки
    if len(snapshots) >= 2:
        top_stats = snapshots[-1].compare_to(snapshots[0], 'lineno')
        
        print("\nТоп-10 источников утечек памяти:")
        for stat in top_stats[:10]:
            print(stat)
        
        # Проверка что нет значительного роста
        total_growth = sum(stat.size_diff for stat in top_stats[:20])
        print(f"\nОбщий рост памяти: {total_growth / 1024:.2f} KB")
        
        # Допускаем рост до 1 MB
        assert total_growth < 1024 * 1024, "Обнаружена утечка памяти"
    
    tracemalloc.stop()


@pytest.mark.stress
async def test_rapid_initialization_cycle():
    """
    Стресс-тест: Быстрые циклы инициализации/завершения.
    
    Цель: Проверка стабильности при частых перезапусках.
    """
    cycles = 20
    times = []
    
    for i in range(cycles):
        start = time.perf_counter()
        
        config = SystemConfig(data_dir="./data", debug=False)
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        app_config = AppConfig.from_registry(profile='prod')
        app_context = ApplicationContext(
            infrastructure_context=infra,
            config=app_config,
            profile='prod'
        )
        await app_context.initialize()
        
        await infra.shutdown()
        
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    
    print(f"\nЦиклов: {cycles}")
    print(f"Среднее время: {avg_time*1000:.2f} мс")
    print(f"Мин время: {min_time*1000:.2f} мс")
    print(f"Макс время: {max_time*1000:.2f} мс")
    
    # Проверка стабильности (разброс не более 50%)
    assert max_time < avg_time * 1.5, "Нестабильное время инициализации"


# ============================================================================
# STRESS TESTS: Нагрузка на компоненты
# ============================================================================

@pytest.mark.stress
async def test_concurrent_component_access():
    """
    Стресс-тест: Параллельный доступ к компонентам.
    
    Цель: Проверка thread-safety компонентов.
    """
    # Инициализация
    config = SystemConfig(data_dir="./data", debug=False)
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_config = AppConfig.from_registry(profile='prod')
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile='prod'
    )
    await app_context.initialize()
    
    # Параллельный доступ
    async def access_component(component_name, access_count):
        for _ in range(access_count):
            skill = app_context.get_skill(component_name)
            assert skill is not None
            await asyncio.sleep(0.001)  # Имитация работы
    
    # Запускаем параллельные доступы
    tasks = [
        access_component("planning", 100),
        access_component("book_library", 100),
        access_component("final_answer", 100),
    ]
    
    start = time.perf_counter()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start
    
    print(f"\nПараллельных доступов: {len(tasks) * 100}")
    print(f"Время: {elapsed:.2f} сек")
    print(f"Запросов в секунду: {len(tasks) * 100 / elapsed:.2f}")
    
    await infra.shutdown()


# ============================================================================
# STRESS TESTS: Нагрузка на промпты/контракты
# ============================================================================

@pytest.mark.stress
async def test_prompt_rendering_load():
    """
    Стресс-тест: Массовый рендеринг промптов.
    
    Цель: Проверка производительности рендеринга.
    """
    config = SystemConfig(data_dir="./data", debug=False)
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_config = AppConfig.from_registry(profile='prod')
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile='prod'
    )
    await app_context.initialize()
    
    # Получаем все промпты
    prompts = app_context.data_repository._prompts_index
    render_count = 0
    
    start = time.perf_counter()
    
    for cap_version, prompt_obj in prompts.items():
        try:
            # Пытаемся отрендерить с тестовыми данными
            rendered = prompt_obj.render(
                goal="Test",
                capabilities_list=["test"],
                context="Test context"
            )
            if rendered:
                render_count += 1
        except Exception:
            pass  # Некоторые промпты могут требовать другие параметры
    
    elapsed = time.perf_counter() - start
    
    print(f"\nПромптов отрендерено: {render_count}/{len(prompts)}")
    print(f"Время: {elapsed:.2f} сек")
    print(f"Среднее время на промпт: {elapsed/max(render_count,1)*1000:.2f} мс")
    
    await infra.shutdown()
