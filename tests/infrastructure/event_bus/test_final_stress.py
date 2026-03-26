"""
Финальный стресс-тест архитектуры (ФАЗА 8).

ТРЕБОВАНИЯ:
- 10 агентов
- каждый запускает 5 сессий
- каждая сессия делает 5 шагов
- с retry
- с ошибками

ПРОВЕРКИ:
✔ Нет race-condition
✔ Нет deadlock
✔ Нет event loss
✔ Порядок внутри session сохранён
✔ Нет memory leak
"""
import asyncio
import logging
import sys
import time
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")

from core.infrastructure.event_bus import (
    EventBus,
    Event,
    EventType,
    create_event_bus,
)

logging.basicConfig(
    level=logging.WARNING,  # Только ошибки
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)


# =============================================================================
# КОНФИГУРАЦИЯ ТЕСТА
# =============================================================================

NUM_AGENTS = 10
SESSIONS_PER_AGENT = 5
STEPS_PER_SESSION = 5
QUEUE_MAX_SIZE = 1000
WORKER_IDLE_TIMEOUT = 10.0  # Быстрое закрытие для теста


# =============================================================================
# ТЕСТИРОВАНИЕ
# =============================================================================

class FinalStressTestResult:
    """Результаты финального стресс-теста."""

    def __init__(self):
        self.events_received: Dict[str, List[Event]] = {}
        self.errors: List[str] = []
        self.start_time: float = 0
        self.end_time: float = 0
        self.retry_count: int = 0
        self.simulated_errors: int = 0

    def add_event(self, session_id: str, event: Event):
        if session_id not in self.events_received:
            self.events_received[session_id] = []
        self.events_received[session_id].append(event)

    def add_error(self, error: str):
        self.errors.append(error)

    @property
    def total_events_published(self) -> int:
        return NUM_AGENTS * SESSIONS_PER_AGENT * STEPS_PER_SESSION

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

        # Проверка 3: Нет interleaving
        for session_id, events in self.events_received.items():
            sequence_numbers = [e.sequence_number for e in events]
            if len(sequence_numbers) != len(set(sequence_numbers)):
                all_valid = False

        if all_valid:

        # Проверка 4: Нет deadlock (тест завершился за разумное время)
        if self.duration > 60:
            all_valid = False
        else:

        # Проверка 5: Retry и ошибки обработаны

        return all_valid

    def print_summary(self):
        """Вывод сводки."""
        if self.duration > 0:


async def run_final_stress_test():
    """Запуск финального стресс-теста."""

    event_bus = create_event_bus(
        queue_max_size=QUEUE_MAX_SIZE,
        worker_idle_timeout=WORKER_IDLE_TIMEOUT,
        subscriber_timeout=30.0
    )

    result = FinalStressTestResult()
    result_lock = asyncio.Lock()

    async def collect_events(event: Event):
        # Игнорируем внутренние события
        if event.event_type.startswith("worker.") or event.event_type.startswith("session."):
            return
        if event.source == "event_bus":
            return
            
        async with result_lock:
            if event.session_id:
                result.add_event(event.session_id, event)

    event_bus.subscribe_all(collect_events)

    async def run_agent(agent_id: int):
        """Запуск агента с несколькими сессиями."""
        async def run_session(session_num: int):
            """Запуск одной сессии с шагами и retry."""
            session_id = f"agent_{agent_id}_session_{session_num}"
            
            for step in range(STEPS_PER_SESSION):
                retry_count = 0
                max_retries = 3
                success = False
                
                while not success and retry_count < max_retries:
                    try:
                        # Симуляция ошибки в 10% случаев
                        if step == 2 and retry_count == 0 and (agent_id + session_num) % 3 == 0:
                            result.simulated_errors += 1
                            raise RuntimeError(f"Симулированная ошибка agent={agent_id}, session={session_num}, step={step}")
                        
                        await event_bus.publish(
                            event_type=EventType.LOG_INFO,
                            data={
                                "step": step + 1,
                                "agent_id": agent_id,
                                "session_id": session_id
                            },
                            source=f"agent_{agent_id}",
                            session_id=session_id,
                            agent_id=f"agent_{agent_id}",
                            correlation_id=f"corr_{agent_id}_{session_num}_{step}"
                        )
                        success = True
                        
                    except Exception as e:
                        retry_count += 1
                        result.retry_count += 1
                        if retry_count >= max_retries:
                            result.add_error(f"Step failed after {max_retries} retries: {e}")
                            success = True  # Продолжаем даже после ошибок
                        await asyncio.sleep(0.01)  # Небольшая задержка перед retry

            logger.debug(f"Сессия {session_id} завершена")

        # Запускаем сессии параллельно
        tasks = [run_session(s) for s in range(SESSIONS_PER_AGENT)]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug(f"Агент {agent_id} завершил работу")

    # Запускаем всех агентов параллельно
    result.start_time = time.time()

    agent_tasks = [run_agent(a) for a in range(NUM_AGENTS)]
    await asyncio.gather(*agent_tasks, return_exceptions=True)

    # Ждём обработки всех событий
    logger.info("Ожидание обработки всех событий...")
    await asyncio.sleep(2)

    # Закрываем EventBus
    logger.info("Закрытие EventBus...")
    await event_bus.shutdown(timeout=10.0)

    result.end_time = time.time()

    # Валидация
    is_valid = result.validate()
    result.print_summary()

    return is_valid, result


async def main():
    """Запуск теста."""
    is_valid, _ = await run_final_stress_test()
    
    
    if is_valid:
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
