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
import logging
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

logger = logging.getLogger(__name__)
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()


def safe_get(
    obj,
    key,
    default=None,
    location: str = "unknown"
):
    """
    Безопасный доступ к .get() с диагностикой.
    
    ARGS:
    - obj: Объект для доступа
    - key: Ключ для получения
    - default: Значение по умолчанию
    - location: Место вызова для логирования
    
    RETURNS:
    - Результат obj.get(key, default) или default если obj не dict
    """
    if obj is None:
        return default
    
    if not isinstance(obj, dict):
        # Логируем предупреждение с traceback
        tb = traceback.format_stack()
        logger.warning(
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            f"⚠️ safe_get: объект не dict (тип: {type(obj).__name__}) "
            f"в {location}. Ключ: {key}. Traceback: {''.join(tb[-3:-1])}"
        )
        return default
    
    return obj.get(key, default)


def safe_get_nested(
    obj,
    *keys,
    default=None,
    location: str = "unknown"
):
    """
    Безопасный доступ к вложенным ключам.
    
    ARGS:
    - obj: Объект для доступа
    - *keys: Последовательность ключей
    - default: Значение по умолчанию
    - location: Место вызова для логирования
    
    RETURNS:
    - Результат obj.get(k1, {}).get(k2, {})... или default
    """
    current = obj
    
    for key in keys:
        if current is None:
            return default
        
        if not isinstance(current, dict):
            tb = traceback.format_stack()
            logger.warning(
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"⚠️ safe_get_nested: объект не dict (тип: {type(current).__name__}) "
                f"в {location}. Ключи: {keys}. Traceback: {''.join(tb[-3:-1])}"
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
