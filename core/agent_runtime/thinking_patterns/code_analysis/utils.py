"""
Детерминированные утилиты без эвристики для анализа кода.
"""
import re
from typing import Optional, Dict, Any
from .models import ErrorLocation


def parse_error_stack(error_log: str) -> Optional[ErrorLocation]:
    """ДЕТЕРМИНИРОВАННЫЙ парсинг стека вызовов через регулярные выражения."""
    # Регулярка для извлечения местоположения (файл, строка, метод)
    location_pattern = r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\w+)'
    location_match = re.search(location_pattern, error_log)
    
    if not location_match:
        return None
    
    file_path = location_match.group(1)
    line = int(location_match.group(2))
    method = location_match.group(3)
    
    # Регулярка для извлечения типов из сообщения об ошибке
    type_mismatch_pattern = r"expected\s+([\w\[\]]+)\s+instance,\s+but\s+got\s+([\w\[\]]+)"
    type_match = re.search(type_mismatch_pattern, error_log, re.IGNORECASE)
    
    actual_type = None
    expected_type = None
    if type_match:
        expected_type = type_match.group(1)
        actual_type = type_match.group(2)
    
    # Извлечение полного сообщения об ошибке
    error_lines = [line.strip() for line in error_log.split('\n') if line.strip()]
    error_message = error_lines[-1] if error_lines else "Неизвестная ошибка"
    
    return ErrorLocation(
        file_path=file_path,
        line=line,
        method=method,
        actual_type=actual_type,
        expected_type=expected_type,
        error_message=error_message[:1000]
    )


def normalize_path(path: str) -> str:
    """Нормализация пути без эвристик."""
    return path.replace('\\', '/').replace('//', '/')


def extract_code_context_from_error(goal: str) -> Optional[ErrorLocation]:
    """Извлечение контекста ошибки из цели пользователя."""
    # Проверка на наличие стека ошибок в цели
    if "Traceback" in goal or "File \"" in goal or "sequence item" in goal:
        return parse_error_stack(goal)
    return None