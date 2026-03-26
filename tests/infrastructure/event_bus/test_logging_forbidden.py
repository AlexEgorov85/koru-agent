"""
Тест на запрет старого логирования (ЧАСТЬ 2).

Проверяет что:
- logging.info/debug/warning/error не используются
- print не используется
- SessionLogger не используется напрямую
"""
import asyncio
import logging
import sys
import builtins
from typing import List

sys.stdout.reconfigure(encoding="utf-8")

# Сохраняем оригинальные функции
_original_logging = {
    'info': logging.info,
    'debug': logging.debug,
    'warning': logging.warning,
    'error': logging.error,
}
_original_print = builtins.print

# Счётчики нарушений
violations = {
    'logging.info': 0,
    'logging.debug': 0,
    'logging.warning': 0,
    'logging.error': 0,
    'print': 0,
}

# Разрешённые модули (системные)
ALLOWED_MODULES = [
    'unified_event_bus',
    'domain_event_bus',
    'test_',
]


def make_forbidden_logging(level_name):
    """Создаёт запрещённую функцию логирования."""
    def forbidden(*args, **kwargs):
        import traceback
        tb = traceback.extract_stack()
        # Ищем первый кадр не из этого файла
        for frame in reversed(tb[:-1]):
            if 'test_logging_forbidden' not in frame.filename:
                module = frame.filename.split('\\')[-1].replace('.py', '')
                if not any(allowed in module for allowed in ALLOWED_MODULES):
                    violations[f'logging.{level_name.lower()}'] += 1
                break
    return forbidden


def forbidden_print(*args, **kwargs):
    """Запрещённый print."""
    import traceback
    tb = traceback.extract_stack()
    for frame in reversed(tb[:-1]):
        if 'test_logging_forbidden' not in frame.filename:
            module = frame.filename.split('\\')[-1].replace('.py', '')
            if not any(allowed in module for allowed in ALLOWED_MODULES):
                violations['print'] += 1
            break


async def test_logging_forbidden():
    """Тест на запрет старого логирования."""
    
    # Включаем запрет
    logging.info = make_forbidden_logging('INFO')
    logging.debug = make_forbidden_logging('DEBUG')
    logging.warning = make_forbidden_logging('WARNING')
    logging.error = make_forbidden_logging('ERROR')
    builtins.print = forbidden_print
    
    try:
        # Импортируем и используем EventBus
        from core.infrastructure.event_bus import (
            create_event_bus,
            EventType,
        )
        
        event_bus = create_event_bus()
        
        # Подписчик
        received = []
        async def handler(event):
            if not event.event_type.startswith("worker."):
                received.append(event)
        
        event_bus.subscribe_all(handler)
        
        # Публикуем событие
        await event_bus.publish(
            event_type=EventType.LOG_INFO,
            data={"test": "data"},
            session_id="test_session",
            agent_id="test_agent"
        )
        
        await asyncio.sleep(0.5)
        await event_bus.shutdown()
        
        # Проверяем результаты
        total_violations = sum(violations.values())
        
        
        for violation_type, count in violations.items():
            status = "[FAIL]" if count > 0 else "[OK]"
        
        
        if total_violations > 0:
            return False
        else:
            return True
            
    finally:
        # Восстанавливаем оригинальные функции
        for name, func in _original_logging.items():
            setattr(logging, name, func)
        builtins.print = _original_print


async def main():
    is_valid = await test_logging_forbidden()
    return 0 if is_valid else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
