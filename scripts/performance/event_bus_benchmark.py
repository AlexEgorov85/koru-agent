"""
Нагрузочный тест для EventBus.

СРАВНЕНИЕ:
- EventBusConcurrent (legacy)
- UnifiedEventBus (новая шина)

ТЕСТЫ:
1. Публикация 1000 событий — время выполнения
2. Memory usage — потребление памяти
3. Session isolation — производительность с сессиями
4. Domain routing — накладные расходы на фильтрацию

ЗАПУСК:
```bash
python scripts/performance/event_bus_benchmark.py
```
"""
import asyncio
import time
import tracemalloc
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# БЕНЧМАРКИ
# =============================================================================

async def benchmark_publish_performance():
    """
    Тест 1: Публикация 1000 событий.

    Сравниваем время публикации событий в legacy и новой шине.
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 1: Публикация 1000 событий")
    print("=" * 60)

    from core.infrastructure.event_bus.event_bus_concurrent import EventBus as EventBusConcurrent
    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType

    results = {}

    # === Legacy: EventBusConcurrent ===
    legacy_bus = EventBusConcurrent()
    legacy_events = []

    async def legacy_handler(event):
        legacy_events.append(event)

    legacy_bus.subscribe(EventType.AGENT_STARTED, legacy_handler)

    start = time.perf_counter()
    for i in range(1000):
        await legacy_bus.publish(
            EventType.AGENT_STARTED,
            data={"seq": i},
            session_id="benchmark_session"
        )
    legacy_time = time.perf_counter() - start

    await asyncio.sleep(0.1)  # Ждём обработки

    results["legacy"] = {
        "time_ms": legacy_time * 1000,
        "events_processed": len(legacy_events)
    }

    print(f"EventBusConcurrent (legacy): {legacy_time * 1000:.2f} ms, {len(legacy_events)} событий")

    # Очистка
    await legacy_bus.shutdown(timeout=5.0)

    # === New: UnifiedEventBus ===
    unified_bus = UnifiedEventBus()
    unified_events = []

    async def unified_handler(event):
        unified_events.append(event)

    unified_bus.subscribe(EventType.AGENT_STARTED, unified_handler)

    start = time.perf_counter()
    for i in range(1000):
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"seq": i},
            session_id="benchmark_session"
        )
    unified_time = time.perf_counter() - start

    await asyncio.sleep(0.1)  # Ждём обработки

    results["unified"] = {
        "time_ms": unified_time * 1000,
        "events_processed": len(unified_events)
    }

    print(f"UnifiedEventBus (new):     {unified_time * 1000:.2f} ms, {len(unified_events)} событий")

    # === Сравнение ===
    if legacy_time > 0:
        improvement = (legacy_time / unified_time - 1) * 100
        print(f"\nУлучшение производительности: {improvement:+.1f}%")

    await unified_bus.shutdown(timeout=5.0)

    return results


async def benchmark_memory_usage():
    """
    Тест 2: Потребление памяти.

    Сравниваем память при создании 100 сессий.
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Потребление памяти (100 сессий)")
    print("=" * 60)

    from core.infrastructure.event_bus.event_bus_concurrent import EventBus as EventBusConcurrent
    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType

    results = {}

    # === Legacy: EventBusConcurrent ===
    tracemalloc.start()

    legacy_bus = EventBusConcurrent()

    # Создаём 100 сессий
    for i in range(100):
        await legacy_bus.publish(
            EventType.AGENT_STARTED,
            data={"session": i},
            session_id=f"session_{i}"
        )

    await asyncio.sleep(0.1)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    results["legacy"] = {
        "current_mb": current / 1024 / 1024,
        "peak_mb": peak / 1024 / 1024
    }

    print(f"EventBusConcurrent (legacy):")
    print(f"  Текущая: {current / 1024 / 1024:.2f} MB")
    print(f"  Пиковая: {peak / 1024 / 1024:.2f} MB")

    await legacy_bus.shutdown(timeout=5.0)

    # === New: UnifiedEventBus ===
    tracemalloc.start()

    unified_bus = UnifiedEventBus()

    # Создаём 100 сессий
    for i in range(100):
        await unified_bus.publish(
            EventType.AGENT_STARTED,
            data={"session": i},
            session_id=f"session_{i}"
        )

    await asyncio.sleep(0.1)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    results["unified"] = {
        "current_mb": current / 1024 / 1024,
        "peak_mb": peak / 1024 / 1024
    }

    print(f"\nUnifiedEventBus (new):")
    print(f"  Текущая: {current / 1024 / 1024:.2f} MB")
    print(f"  Пиковая: {peak / 1024 / 1024:.2f} MB")

    # === Сравнение ===
    legacy_peak = results["legacy"]["peak_mb"]
    unified_peak = results["unified"]["peak_mb"]

    if legacy_peak > 0:
        memory_saved = (legacy_peak - unified_peak) / legacy_peak * 100
        print(f"\nЭкономия памяти: {memory_saved:+.1f}%")

    await unified_bus.shutdown(timeout=5.0)

    return results


async def benchmark_session_isolation():
    """
    Тест 3: Изоляция сессий.

    Проверяем что события сессии A не попадают в сессию B.
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Изоляция сессий")
    print("=" * 60)

    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType

    bus = UnifiedEventBus()

    session_a_events = []
    session_b_events = []

    bus.subscribe(
        EventType.AGENT_STARTED,
        lambda e: session_a_events.append(e),
        session_id="session_a"
    )
    bus.subscribe(
        EventType.AGENT_STARTED,
        lambda e: session_b_events.append(e),
        session_id="session_b"
    )

    # Публикуем события в разные сессии
    for i in range(10):
        await bus.publish(
            EventType.AGENT_STARTED,
            data={"seq": i},
            session_id="session_a"
        )
        await bus.publish(
            EventType.AGENT_STARTED,
            data={"seq": i},
            session_id="session_b"
        )

    await asyncio.sleep(0.1)

    print(f"Сессия A получено: {len(session_a_events)} событий")
    print(f"Сессия B получено: {len(session_b_events)} событий")

    # Проверка изоляции
    assert len(session_a_events) == 10, f"Ожидалось 10 событий, получено {len(session_a_events)}"
    assert len(session_b_events) == 10, f"Ожидалось 10 событий, получено {len(session_b_events)}"

    print("[OK] Изоляция сессий работает корректно")

    await bus.shutdown(timeout=5.0)

    return {
        "session_a_count": len(session_a_events),
        "session_b_count": len(session_b_events),
        "isolation_ok": len(session_a_events) == 10 and len(session_b_events) == 10
    }


async def benchmark_domain_routing():
    """
    Тест 4: Domain routing.

    Проверяем фильтрацию событий по доменам.
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Domain routing")
    print("=" * 60)

    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType, EventDomain

    bus = UnifiedEventBus()

    agent_events = []
    infra_events = []

    bus.subscribe(
        EventType.AGENT_STARTED,
        lambda e: agent_events.append(e),
        domain=EventDomain.AGENT
    )
    bus.subscribe(
        EventType.SYSTEM_INITIALIZED,
        lambda e: infra_events.append(e),
        domain=EventDomain.INFRASTRUCTURE
    )

    # Публикуем события разных доменов
    for i in range(10):
        await bus.publish(
            EventType.AGENT_STARTED,
            data={"seq": i},
            domain=EventDomain.AGENT
        )
        await bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={"seq": i},
            domain=EventDomain.INFRASTRUCTURE
        )

    await asyncio.sleep(0.1)

    print(f"AGENT события: {len(agent_events)}")
    print(f"INFRASTRUCTURE события: {len(infra_events)}")

    # Проверка routing
    assert len(agent_events) == 10, f"Ожидалось 10 AGENT событий, получено {len(agent_events)}"
    assert len(infra_events) == 10, f"Ожидалось 10 INFRASTRUCTURE событий, получено {len(infra_events)}"

    print("[OK] Domain routing работает корректно")

    await bus.shutdown(timeout=5.0)

    return {
        "agent_count": len(agent_events),
        "infra_count": len(infra_events),
        "routing_ok": len(agent_events) == 10 and len(infra_events) == 10
    }


async def benchmark_no_duplication():
    """
    Тест 5: Отсутствие дублирования событий.

    Критичный тест! Событие должно быть получено ровно 1 раз.
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Отсутствие дублирования событий")
    print("=" * 60)

    from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType

    bus = UnifiedEventBus()

    received_count = 0

    def handler(event):
        nonlocal received_count
        received_count += 1

    bus.subscribe(EventType.AGENT_STARTED, handler)

    # Публикуем 100 событий
    for i in range(100):
        await bus.publish(
            EventType.AGENT_STARTED,
            data={"seq": i},
            session_id="test_session"
        )

    await asyncio.sleep(0.1)

    print(f"Отправлено: 100 событий")
    print(f"Получено: {received_count} событий")

    if received_count == 100:
        print("[OK] Дублирования НЕТ (ожидалось 100, получено 100)")
    else:
        print(f"[FAIL] ОБНАРУЖЕНО ДУБЛИРОВАНИЕ! (ожидалось 100, получено {received_count})")

    await bus.shutdown(timeout=5.0)

    return {
        "sent": 100,
        "received": received_count,
        "duplication": received_count != 100
    }


async def run_all_benchmarks():
    """Запуск всех бенчмарков."""
    print("\n" + "=" * 60)
    print("НАГРУЗОЧНЫЙ ТЕСТ EVENT BUS")
    print(f"Время запуска: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }

    # Тест 1: Производительность публикации
    results["tests"]["publish_performance"] = await benchmark_publish_performance()

    # Тест 2: Потребление памяти
    results["tests"]["memory_usage"] = await benchmark_memory_usage()

    # Тест 3: Изоляция сессий
    results["tests"]["session_isolation"] = await benchmark_session_isolation()

    # Тест 4: Domain routing
    results["tests"]["domain_routing"] = await benchmark_domain_routing()

    # Тест 5: Отсутствие дублирования
    results["tests"]["no_duplication"] = await benchmark_no_duplication()

    # Итоговый отчёт
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 60)

    all_passed = True

    # Проверка результатов
    if results["tests"]["session_isolation"]["isolation_ok"]:
        print("[OK] Тест 3: Изоляция сессий — PASSED")
    else:
        print("[FAIL] Тест 3: Изоляция сессий — FAILED")
        all_passed = False

    if results["tests"]["domain_routing"]["routing_ok"]:
        print("[OK] Тест 4: Domain routing — PASSED")
    else:
        print("[FAIL] Тест 4: Domain routing — FAILED")
        all_passed = False

    if not results["tests"]["no_duplication"]["duplication"]:
        print("[OK] Тест 5: Отсутствие дублирования — PASSED")
    else:
        print("[FAIL] Тест 5: Отсутствие дублирования — FAILED")
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    else:
        print("[FAIL] НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
    print("=" * 60)

    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
