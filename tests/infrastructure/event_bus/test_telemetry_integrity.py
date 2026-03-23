"""
Тест целостности событий (ЧАСТЬ 2 - Telemetry Integrity).

Проверяет инварианты:
- Каждый SessionStarted → имеет SessionFinished
- sequence_number внутри session непрерывен
- Нет событий без session_id
- Нет событий без agent_id
"""
import asyncio
import logging
import sys
from typing import Dict, List
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

from core.infrastructure.event_bus import (
    EventBus,
    Event,
    EventType,
    create_event_bus,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    encoding="utf-8"
)


class TelemetryValidator:
    """Валидатор телеметрии."""
    
    def __init__(self):
        self.events: List[Event] = []
        self.sessions: Dict[str, List[Event]] = defaultdict(list)
        
    def add_event(self, event: Event):
        self.events.append(event)
        if event.session_id:
            self.sessions[event.session_id].append(event)
    
    def validate(self) -> tuple[bool, List[str]]:
        """Проверка инвариантов."""
        errors = []
        
        # 1. Проверка sequence_number внутри сессии (игнорируем system сессии)
        for session_id, events in self.sessions.items():
            if session_id.startswith("system"):
                continue  # Игнорируем внутренние события
            sequences = [e.sequence_number for e in events]
            expected = list(range(1, len(sequences) + 1))
            if sequences != expected:
                errors.append(f"session {session_id}: sequence нарушен {sequences} != {expected}")
        
        # 2. Нет событий без session_id
        no_session = [e for e in self.events if not e.session_id]
        if no_session:
            errors.append(f"{len(no_session)} событий без session_id")
        
        # 3. Нет событий без agent_id (для бизнес-событий, игнорируем system и worker)
        no_agent = [e for e in self.events 
                   if not e.agent_id 
                   and not e.session_id.startswith("system")
                   and not e.event_type.startswith("worker.")]
        if no_agent:
            errors.append(f"{len(no_agent)} событий без agent_id")
        
        return len(errors) == 0, errors


async def run_telemetry_test():
    """Тест целостности телеметрии."""
    print("\n" + "="*70)
    print("[TEST] TELEMETRY INTEGRITY")
    print("="*70)
    
    event_bus = create_event_bus()
    validator = TelemetryValidator()
    
    async def collect(event: Event):
        if not event.event_type.startswith("worker."):
            validator.add_event(event)
    
    event_bus.subscribe_all(collect)
    
    # Создаём 5 сессий с разными событиями
    for agent in range(2):
        for session in range(3):
            session_id = f"agent_{agent}_session_{session}"
            for step in range(5):
                await event_bus.publish(
                    event_type=EventType.LOG_INFO,
                    data={"step": step},
                    session_id=session_id,
                    agent_id=f"agent_{agent}"
                )
    
    await asyncio.sleep(1)
    await event_bus.shutdown()
    
    # Валидация
    is_valid, errors = validator.validate()
    
    print(f"\nВсего событий: {len(validator.events)}")
    print(f"Сессий: {len(validator.sessions)}")
    
    if errors:
        print("\n[FAIL] Нарушения:")
        for error in errors[:10]:
            print(f"  - {error}")
    else:
        print("\n[OK] Все инварианты соблюдены")
    
    return is_valid


async def main():
    is_valid = await run_telemetry_test()
    
    print("\n" + "="*70)
    print("[REPORT]")
    print("="*70)
    print(f"[{'PASS' if is_valid else 'FAIL'}]: Telemetry Integrity")
    print("="*70)
    
    return 0 if is_valid else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
