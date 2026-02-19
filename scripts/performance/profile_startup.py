#!/usr/bin/env python3
"""
Утилита для профилирования производительности Agent_v5.

Запуск:
    python scripts/performance/profile_startup.py
    python scripts/performance/profile_startup.py --output profile.prof
    
Анализ:
    python -m pstats profile.prof
    или
    snakeviz profile.prof  # визуализация
"""
import argparse
import asyncio
import cProfile
import pstats
import io
import sys
from pathlib import Path

# Добавляем проект в path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext


async def measure_startup_time(data_dir: str = "./data"):
    """Измерение времени запуска системы."""
    import time
    
    start = time.perf_counter()
    
    config = SystemConfig(data_dir=data_dir)
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_config = AppConfig.from_registry(profile='prod')
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile='prod'
    )
    await app_context.initialize()
    
    end = time.perf_counter()
    
    await infra.shutdown()
    
    elapsed = end - start
    return elapsed


async def profile_startup(output_file: str = "profile.prof"):
    """Профилирование запуска системы."""
    profiler = cProfile.Profile()
    
    profiler.enable()
    
    config = SystemConfig(data_dir="./data")
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
    
    profiler.disable()
    
    # Сохранение результатов
    profiler.dump_stats(output_file)
    
    # Вывод статистики
    stats_stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stats_stream).sort_stats('cumulative')
    stats.print_stats(20)
    
    return stats_stream.getvalue()


def measure_memory_usage():
    """Измерение использования памяти."""
    import tracemalloc
    
    async def measure():
        tracemalloc.start()
        
        config = SystemConfig(data_dir="./data")
        infra = InfrastructureContext(config)
        await infra.initialize()
        
        app_config = AppConfig.from_registry(profile='prod')
        app_context = ApplicationContext(
            infrastructure_context=infra,
            config=app_config,
            profile='prod'
        )
        await app_context.initialize()
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        await infra.shutdown()
        
        return current, peak
    
    current, peak = asyncio.run(measure())
    
    print(f"\nИспользование памяти:")
    print(f"  Текущее: {current / 1024 / 1024:.2f} MB")
    print(f"  Пиковое: {peak / 1024 / 1024:.2f} MB")
    
    return current, peak


def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Профилирование производительности")
    parser.add_argument(
        "--output", "-o",
        default="profile.prof",
        help="Файл для сохранения результатов профилирования"
    )
    parser.add_argument(
        "--memory", "-m",
        action="store_true",
        help="Измерить использование памяти"
    )
    parser.add_argument(
        "--time", "-t",
        action="store_true",
        help="Измерить время запуска"
    )
    parser.add_argument(
        "--profile", "-p",
        action="store_true",
        help="Запустить профилирование"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Профилирование производительности Agent_v5")
    print("=" * 60)
    
    if args.time or not (args.memory or args.profile):
        print("\n⏱️  Измерение времени запуска...")
        elapsed = asyncio.run(measure_startup_time())
        print(f"   Время инициализации: {elapsed*1000:.2f} мс")
        
        if elapsed < 0.1:
            print("   ✅ Отлично (< 100 мс)")
        elif elapsed < 0.5:
            print("   ⚠️  Нормально (< 500 мс)")
        else:
            print("   ❌ Медленно (> 500 мс)")
    
    if args.memory:
        print("\n💾 Измерение использования памяти...")
        current, peak = measure_memory_usage()
        
        if peak < 50 * 1024 * 1024:
            print("   ✅ Отлично (< 50 MB)")
        elif peak < 100 * 1024 * 1024:
            print("   ⚠️  Нормально (< 100 MB)")
        else:
            print("   ❌ Много (> 100 MB)")
    
    if args.profile or not (args.memory or args.time):
        print(f"\n📊 Профилирование...")
        stats = asyncio.run(profile_startup(args.output))
        print(f"   Результаты сохранены в: {args.output}")
        print("\nТоп-20 функций по времени выполнения:")
        print(stats)
    
    print("\n" + "=" * 60)
    print("Профилирование завершено")
    print("=" * 60)


if __name__ == "__main__":
    main()
