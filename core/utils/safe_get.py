"""
Безопасный доступ к словарям с диагностикой ошибок.

USAGE:
```python
from core.utils.safe_get import safe_get

# Вместо result.get('key')
value = safe_get(result, 'key', default=None, location="my_function")

# Вместо metadata.get('error')
error = safe_get(metadata, 'error', default=None, location="error_handler")
```
"""
import traceback
from typing import Any, Optional

from core.infrastructure.event_bus.unified_event_bus import EventType, EventDomain, UnifiedEventBus


async def safe_get(
    obj: Any,
    key: str,
    default: Any = None,
    location: str = "unknown",
    event_bus: Optional[UnifiedEventBus] = None,
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None
):
    """
    Безопасный доступ к .get() с диагностикой.
    
    ARGS:
    - obj: Объект для доступа
    - key: Ключ для получения
    - default: Значение по умолчанию
    - location: Место вызова для логирования
    - event_bus: опциональная шина событий для логирования
    - session_id: опциональный ID сессии
    - agent_id: опциональный ID агента
    
    RETURNS:
    - Результат obj.get(key, default) или default если obj не dict
    """
    if obj is None:
        return default
    
    if not isinstance(obj, dict):
        tb = traceback.format_stack()
        if event_bus:
            await event_bus.publish(
                EventType.LOG_WARNING,
                data={
                    "message": f"safe_get: объект не dict (тип: {type(obj).__name__}) в {location}. Ключ: {key}",
                    "traceback": "".join(tb[-3:-1])
                },
                session_id=session_id,
                domain=EventDomain.COMMON
            )
        return default
    
    return obj.get(key, default)


async def safe_get_nested(
    obj: Any,
    *keys: str,
    default: Any = None,
    location: str = "unknown",
    event_bus: Optional[UnifiedEventBus] = None,
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None
):
    """
    Безопасный доступ к вложенным ключам.
    
    ARGS:
    - obj: Объект для доступа
    - *keys: Последовательность ключей
    - default: Значение по умолчанию
    - location: Место вызова для логирования
    - event_bus: опциональная шина событий для логирования
    - session_id: опциональный ID сессии
    - agent_id: опциональный ID агента
    
    RETURNS:
    - Результат obj.get(k1, {}).get(k2, {})... или default
    """
    current = obj
    
    for key in keys:
        if current is None:
            return default
        
        if not isinstance(current, dict):
            tb = traceback.format_stack()
            if event_bus:
                await event_bus.publish(
                    EventType.LOG_WARNING,
                    data={
                        "message": f"safe_get_nested: объект не dict (тип: {type(current).__name__}) в {location}. Ключи: {keys}",
                        "traceback": "".join(tb[-3:-1])
                    },
                    session_id=session_id,
                    domain=EventDomain.COMMON
                )
            return default
        
        current = current.get(key)
        
        if current is None:
            return default
    
    return current


def dict_get_required(
    obj,
    key,
    location: str = "unknown"
):
    """
    Получить обязательное значение из dict.
    
    RAISES:
    - ValueError: если obj не dict или ключ отсутствует
    
    ARGS:
    - obj: Объект для доступа
    - key: Ключ для получения
    - location: Место вызова для сообщения об ошибке
    
    RETURNS:
    - obj[key]
    """
    if obj is None:
        raise ValueError(f"{location}: объект None вместо dict для ключа '{key}'")
    
    if not isinstance(obj, dict):
        raise ValueError(
            f"{location}: объект типа {type(obj).__name__} вместо dict для ключа '{key}'. "
            f"Значение: {obj!r}"
        )
    
    if key not in obj:
        raise ValueError(f"{location}: ключ '{key}' отсутствует в dict. Ключи: {list(obj.keys())}")
    
    return obj[key]
