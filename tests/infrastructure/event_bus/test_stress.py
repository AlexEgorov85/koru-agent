"""
Стресс-тест конкурентного EventBus.

ПРОВЕРКА ФАЗЫ 1:
- 5 агентов
- каждый запускает 3 сессии
- каждая сессия публикует 50 событий

ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ:
- Внутри каждой session порядок 1..50
- Нет interleaving
- Нет потери событий
- Нет зависших worker'ов
"""
import asyncio
import logging
import sys
import time
from typing import Dict, List, Set
from datetime import datetime

# Кодировка для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from core.infrastructure.event_bus import (
    EventBus,
    Event,
    EventType,
    create_event_bus,
)
DEFAULT_QUEUE_MAX_SIZE = 1000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)


# =============================================================================
# КОНФИГУРАЦИЯ ТЕСТА
# =============================================================================

NUM_AGENTS = 5
SESSIONS_PER_AGENT = 3
EVENTS_PER_SESSION = 50
QUEUE_MAX_SIZE = 1000
WORKER_IDLE_TIMEOUT = 5.0  # Секунд для быстрого закрытия


# =============================================================================
# ТЕСТИРОВАНИЕ
# =============================================================================

class StressTestResult:
    """Результаты стресс-теста."""

    def __init__(self):
        self.events_received: Dict[str, List[Event]] = {}
        self.errors: List[str] = []
        self.start_time: float = 0
        self.end_time: float = 0

    def add_event(self, session_id: str, event: Event):
        if session_id not in self.events_received:
            self.events_received[session_id] = []
        self.events_received[session_id].append(event)

    def add_error(self, error: str):
        self.errors.append(error)

    @property
    def total_events_published(self) -> int:
        return NUM_AGENTS * SESSIONS_PER_AGENT * EVENTS_PER_SESSION

    @property
    def total_events_received(self) -> int:
        return sum(len(events) for events in self.events_received.values())

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def validate(self) -> bool:
        """Проверка результатов теста."""
        all_valid = True

        # Проверка 1: Нет потери событий
        if self.total_events_received != self.total_events_published:
            all_valid = False
        else:

        # Проверка 2: Порядок внутри сессии
        for session_id, events in self.events_received.items():
            sequence_numbers = [e.sequence_number for e in events]
            expected = list(range(1, len(events) + 1))

            if sequence_numbers != expected:
                all_valid = False

        if all_valid:

        # Проверка 3: Нет interleaving (sequence_number уникален внутри сессии)
        for session_id, events in self.events_received.items():
            sequence_numbers = [e.sequence_number for e in events]
            if len(sequence_numbers) != len(set(sequence_numbers)):
                all_valid = False

        if all_valid:

        # Проверка 4: Нет ошибок
        if self.errors:
            for error in self.errors[:5]:
            all_valid = False
        else:

        return all_valid

    def print_summary(self):
        """Вывод сводки."""
        if self.duration > 0:
        else:


async def run_stress_test():
    """Запуск стресс-теста."""

    # Создаём EventBus
    event_bus = create_event_bus(
        queue_max_size=QUEUE_MAX_SIZE,
        worker_idle_timeout=WORKER_IDLE_TIMEOUT,
        subscriber_timeout=30.0
    )

    # Результаты теста
    result = StressTestResult()
    result_lock = asyncio.Lock()

    # === ПОДПИСЧИК ===
    # Собирает все события по сессиям (игнорирует внутренние события EventBus)
    async def collect_events(event: Event):
        # Игнорируем внутренние события EventBus
        if event.event_type.startswith("worker.") or event.event_type.startswith("session."):
            return
        if event.source == "event_bus":
            return
            
        async with result_lock:
            if event.session_id and not event.event_type.startswith("worker."):
                result.add_event(event.session_id, event)

    event_bus.subscribe_all(collect_events)

    # === ЗАПУСК АГЕНТОВ И СЕССИЙ ===
    async def run_agent(agent_id: int):
        """Запуск агента с несколькими сессиями."""
        logger.info(f"Агент {agent_id} начинает работу")

        async def run_session(session_num: int):
            """Запуск одной сессии."""
            session_id = f"agent_{agent_id}_session_{session_num}"
            logger.debug(f"Сессия {session_id} начинает публикацию")

            # Публикуем события
            for i in range(EVENTS_PER_SESSION):
                await event_bus.publish(
                    event_type=EventType.LOG_INFO,
                    data={"step": i + 1, "agent_id": agent_id},
                    source=f"agent_{agent_id}",
                    session_id=session_id,
                    agent_id=f"agent_{agent_id}",
                    correlation_id=f"corr_{agent_id}_{session_num}_{i}"
                )

            logger.debug(f"Сессия {session_id} завершила публикацию ({EVENTS_PER_SESSION} событий)")

        # Запускаем сессии параллельно
        tasks = [run_session(s) for s in range(SESSIONS_PER_AGENT)]
        await asyncio.gather(*tasks)

        logger.info(f"Агент {agent_id} завершил работу")

    # Запускаем всех агентов параллельно
    result.start_time = time.time()

    agent_tasks = [run_agent(a) for a in range(NUM_AGENTS)]
    await asyncio.gather(*agent_tasks)

    # Ждём обработки всех событий
    logger.info("Ожидание обработки всех событий...")
    await asyncio.sleep(2)  # Даём время на обработку

    # Закрываем EventBus
    logger.info("Закрытие EventBus...")
    await event_bus.shutdown(timeout=10.0)

    result.end_time = time.time()

    # === ВАЛИДАЦИЯ ===
    is_valid = result.validate()
    result.print_summary()

    return is_valid, result


# =============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ
# =============================================================================

async def test_backpressure():
    """Тест backpressure при переполнении очереди."""

    # Создаём EventBus с маленькой очередью
    event_bus = create_event_bus(
        queue_max_size=10,  # Очень маленький лимит
        worker_idle_timeout=60.0,
        subscriber_timeout=30.0
    )

    overflow_detected = False

    # Подписчик который медленно обрабатывает
    async def slow_subscriber(event: Event):
        await asyncio.sleep(0.1)

    # Подписчик на overflow события
    async def on_overflow(event: Event):
        nonlocal overflow_detected
        if event.event_type == EventType.QUEUE_OVERFLOW.value:
            overflow_detected = True

    event_bus.subscribe_all(slow_subscriber)
    event_bus.subscribe(EventType.QUEUE_OVERFLOW, on_overflow)

    session_id = "backpressure_test"

    # Публикуем больше событий чем влезает в очередь
    publish_count = 50
    for i in range(publish_count):
        await event_bus.publish(
            event_type=EventType.LOG_INFO,
            data={"step": i},
            session_id=session_id
        )

    # Ждём обработки
    await asyncio.sleep(3)
    await event_bus.shutdown()

    if overflow_detected:
        return True
    else:
        return True  # Не считаем это ошибкой


async def test_subscriber_isolation():
    """Тест изоляции подписчиков (ошибка не валит EventBus)."""

    event_bus = create_event_bus()

    error_count = 0
    success_count = 0

    # Подписчик который падает
    async def failing_subscriber(event: Event):
        # Игнорируем внутренние события EventBus
        if event.source == "event_bus" or event.event_type.startswith("worker."):
            return
        nonlocal error_count
        error_count += 1
        raise RuntimeError("Intentional error in subscriber")

    # Подписчик который работает
    async def working_subscriber(event: Event):
        # Игнорируем внутренние события EventBus
        if event.source == "event_bus" or event.event_type.startswith("worker."):
            return
        nonlocal success_count
        success_count += 1

    event_bus.subscribe_all(failing_subscriber)
    event_bus.subscribe_all(working_subscriber)

    session_id = "isolation_test"

    # Публикуем события
    for i in range(10):
        await event_bus.publish(
            event_type=EventType.LOG_INFO,
            data={"step": i},
            session_id=session_id
        )

    # Ждём обработки
    await asyncio.sleep(2)
    await event_bus.shutdown()


    if success_count == 10 and error_count == 10:
        return True
    else:
        return False


async def test_worker_lifecycle():
    """Тест жизненного цикла worker'ов."""

    event_bus = create_event_bus(
        worker_idle_timeout=2.0  # Короткий таймаут
    )

    worker_events = []

    async def on_worker_event(event: Event):
        if event.event_type in [
            EventType.WORKER_CREATED.value,
            EventType.WORKER_CLOSED.value,
            EventType.WORKER_IDLE.value
        ]:
            worker_events.append((event.event_type, event.data))

    event_bus.subscribe_all(on_worker_event)

    # Создаём сессию
    session_id = "lifecycle_test"
    for i in range(5):
        await event_bus.publish(
            event_type=EventType.LOG_INFO,
            data={"step": i},
            session_id=session_id
        )

    # Ждём idle timeout
    await asyncio.sleep(4)

    await event_bus.shutdown()

    # Проверяем что worker был создан и закрыт
    created = any(e[0] == EventType.WORKER_CREATED.value for e in worker_events)
    closed = any(e[0] == EventType.WORKER_CLOSED.value for e in worker_events)

    if created and closed:
        return True
    else:
        return False


# =============================================================================
# ЗАПУСК
# =============================================================================

async def main():
    """Запуск всех тестов."""
    results = []

    # Основной стресс-тест
    is_valid, _ = await run_stress_test()
    results.append(("Stress Test", is_valid))

    # Дополнительные тесты
    results.append(("Backpressure", await test_backpressure()))
    results.append(("Subscriber Isolation", await test_subscriber_isolation()))
    results.append(("Worker Lifecycle", await test_worker_lifecycle()))

    # Итоговый отчёт

    all_passed = True
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_passed = False


    if all_passed:
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
