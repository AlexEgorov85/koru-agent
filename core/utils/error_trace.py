"""
Утилита для детальной записи ошибок с информацией о файле и строке.

USAGE:
```python
from core.utils.error_trace import format_error_with_trace
from core.infrastructure.event_bus.unified_event_bus import EventType, EventDomain

try:
    result = risky_operation()
except Exception as e:
    error_msg = format_error_with_trace(e)
    await event_bus.publish(
        EventType.LOG_ERROR,
        data={"message": error_msg},
        session_id=session_id,
        domain=EventDomain.COMMON
    )
```
"""
import traceback
import sys
from typing import Optional, Dict, Any


def format_error_with_trace(
    error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Форматировать ошибку с полной трассировкой.
    
    ARGS:
    - error: Исключение
    - context: Дополнительный контекст (опционально)
    
    RETURNS:
    - Строка с детальной информацией об ошибке
    """
    tb_str = traceback.format_exc()
    
    # Получаем информацию о файле и строке
    tb = sys.exc_info()[2]
    if tb:
        frame = tb.tb_frame
        lineno = tb.tb_lineno
        filename = frame.f_code.co_filename
        
        # Пытаемся получить имя функции
        func_name = frame.f_code.co_name
        
        file_info = f"Файл: {filename}, Строка: {lineno}, Функция: {func_name}"
    else:
        file_info = "Не удалось получить информацию о файле"
    
    # Формируем сообщение
    msg_parts = [
        f"❌ ОШИБКА: {error}",
        f"📋 Тип: {type(error).__name__}",
        f"📁 {file_info}",
        f"📝 Traceback:\n{tb_str}",
    ]
    
    # Добавляем контекст если есть
    if context:
        msg_parts.append(f"🔧 Контекст: {context}")
    
    return "\n".join(msg_parts)


def get_error_location(error: Exception) -> Dict[str, Any]:
    """
    Получить информацию о местоположении ошибки.
    
    ARGS:
    - error: Исключение
    
    RETURNS:
    - Dict с информацией: filename, lineno, func_name, module
    """
    tb = sys.exc_info()[2]
    info = {
        "filename": "unknown",
        "lineno": 0,
        "func_name": "unknown",
        "module": "unknown",
    }
    
    if tb:
        # Проходим по traceback до конца (последний frame)
        current_tb = tb
        while current_tb.tb_next:
            current_tb = current_tb.tb_next
        
        frame = current_tb.tb_frame
        code = frame.f_code
        
        info["filename"] = code.co_filename
        info["lineno"] = current_tb.tb_lineno
        info["func_name"] = code.co_name
        info["module"] = code.co_name  # module не всегда доступен
        
    return info


def error_to_dict(error: Exception) -> Dict[str, Any]:
    """
    Конвертировать ошибку в словарь для логирования.
    
    ARGS:
    - error: Исключение
    
    RETURNS:
    - Dict с полной информацией об ошибке
    """
    import traceback
    
    return {
        "error_message": str(error),
        "error_type": type(error).__name__,
        "error_class": error.__class__.__name__,
        "traceback": traceback.format_exc(),
        "location": get_error_location(error),
    }
