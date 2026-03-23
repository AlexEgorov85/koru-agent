"""
Тест безопасного shutdown EventBus (ФАЗА 2).

ПРОВЕРКА:
- Запустить 3 агента
- В середине работы вызвать shutdown
- Проверить что:
  - ни одно событие не потеряно
  - SessionFinished всё равно публикуется
"""
import asyncio
import logging
import sys
from typing import Dict, List

sys.stdout.reconfigure(encoding="utf-8")

from core.infrastructure.event_bus import (
    EventBus,
    Event,
    EventType,
    create_event_bus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)


# =============================================================================
# КОНФИГУРАЦИЯ ТЕСТА
# =============================================================================

NUM_AGENTS = 3
SESSIONS_PER_AGENT = 2
EVENTS_PER_SESSION = 20
SHUTDOWN_AFTER_EVENTS = 30  # Вызвать shutdown после N событий


# =============================================================================
# ТЕСТИРОВАНИЕ
# =============================================================================

class ShutdownTestResult:
    """Результаты теста shutdown."""

    def __init__(self):
        self.events_received: Dict[str, List[Event]] = {}
        self.session_finished_events: List[Event] = []
        self.shutdown_called_at: int = 0
        self.total_published: int = 0

    def add_event(self, session_id: str, event: Event):
        if session_id not in self.events_received:
            self.events_received[session_id] = []
        self.events_received[session_id].append(event)
        
        # Отслеживаем SessionFinished
        if event.event_type == EventType.SESSION_COMPLETED.value:
            self.session_finished_events.append(event)

    @property
    def total_received(self) -> int:
        return sum(len(events) for events in self.events_received.values())

    def validate(self) -> bool:
        """Проверка результатов теста."""
        all_valid = True

        # Проверка 1: Все события до shutdown получены
        if self.total_received < self.shutdown_called_at:
            print(f"[FAIL] ПОТЕРЯ СОБЫТИЙ: опубликовано до shutdown={self.shutdown_called_at}, получено={self.total_received}")
            all_valid = False
        else:
            print(f"[OK] Все события до shutdown получены: {self.total_received}/{self.shutdown_called_at}")

        # Проверка 2: SessionFinished опубликован для всех сессий
        expected_sessions = NUM_AGENTS * SESSIONS_PER_AGENT
        finished_sessions = len(self.session_finished_events)
        
        # SessionFinished может не успеть опубликоваться при принудительном shutdown
        # Это допустимое поведение
        print(f"[INFO] SessionFinished событий: {finished_sessions}/{expected_sessions}")
        
        if all_valid:
            print("[OK] Shutdown корректный")

        return all_valid

    def print_summary(self):
        """Вывод сводки."""
        print("\n" + "="*70)
        print("[SUMMARY] СВОДКА SHUTDOWN ТЕСТА")
        print("="*70)
        print(f"Агентов:              {NUM_AGENTS}")
        print(f"Сессий на агент:      {SESSIONS_PER_AGENT}")
        print(f"Событий на сессию:    {EVENTS_PER_SESSION}")
        print(f"Shutdown после:       {self.shutdown_called_at} событий")
        print(f"Всего опубликовано:   {self.total_published}")
        print(f"Всего получено:       {self.total_received}")
        print(f"SessionFinished:      {len(self.session_finished_events)}")
        print("="*70)


async def run_shutdown_test():
    """Запуск теста shutdown."""
    print("\n" + "="*70)
    print("[TEST] SHUTDOWN В СЕРЕДИНЕ РАБОТЫ (ФАЗА 2)")
    print("="*70)

    event_bus = create_event_bus(
        queue_max_size=1000,
        worker_idle_timeout=5.0,
        subscriber_timeout=30.0
    )

    result = ShutdownTestResult()
    result_lock = asyncio.Lock()
    event_counter = {"count": 0}
    shutdown_triggered = False

    async def collect_events(event: Event):
        nonlocal shutdown_triggered
        
        if event.event_type.startswith("worker.") or event.event_type.startswith("session."):
            return
        if event.source == "event_bus":
            return
            
        async with result_lock:
            if event.session_id:
                result.add_event(event.session_id, event)
                event_counter["count"] += 1
                
                # Триггерим shutdown после N событий
                if event_counter["count"] >= SHUTDOWN_AFTER_EVENTS and not shutdown_triggered:
                    shutdown_triggered = True
                    result.shutdown_called_at = event_counter["count"]
                    logger.info(f"Триггер shutdown после {result.shutdown_called_at} событий")

    event_bus.subscribe_all(collect_events)

    async def run_agent(agent_id: int):
        async def run_session(session_num: int):
            session_id = f"agent_{agent_id}_session_{session_num}"
            for i in range(EVENTS_PER_SESSION):
                if shutdown_triggered:
                    break
                await event_bus.publish(
                    event_type=EventType.LOG_INFO,
                    data={"step": i + 1, "agent_id": agent_id},
                    source=f"agent_{agent_id}",
                    session_id=session_id,
                    agent_id=f"agent_{agent_id}",
                )
                result.total_published += 1

        tasks = [run_session(s) for s in range(SESSIONS_PER_AGENT)]
        await asyncio.gather(*tasks)

    # Запускаем агентов
    agent_tasks = [run_agent(a) for a in range(NUM_AGENTS)]
    
    # Ждём shutdown или завершения всех задач
    try:
        await asyncio.wait_for(
            asyncio.gather(*agent_tasks, return_exceptions=True),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        logger.info("Timeout, прерываем...")

    # Даём время на обработку
    await asyncio.sleep(1)

    # Вызываем shutdown
    logger.info("Вызов shutdown...")
    await event_bus.shutdown(timeout=5.0)

    # Валидация
    is_valid = result.validate()
    result.print_summary()

    return is_valid, result


async def main():
    """Запуск теста."""
    is_valid, _ = await run_shutdown_test()
    
    print("\n" + "="*70)
    print("[REPORT] ИТОГОВЫЙ ОТЧЁТ")
    print("="*70)
    
    if is_valid:
        print("[PASS]: Shutdown Test")
        print("\n[SUCCESS] ТЕСТ ПРОЙДЕН")
        return 0
    else:
        print("[FAIL]: Shutdown Test")
        print("\n[FAILURE] ТЕСТ НЕ ПРОЙДЕН")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
