"""
Оценка размера данных и политика сохранения observation.
Детерминированно решает: raw_data или summary.
"""
import json
from typing import Any


class ObservationPolicy:
    """Политика определения типа сохранения данных для observation."""
    
    MAX_ROWS = 20
    MAX_JSON_BYTES = 1500
    MAX_TEXT_CHARS = 1500
    MAX_DICT_KEYS = 10
    
    @classmethod
    def decide(cls, raw_data: Any, explicit_mode: str = "auto") -> str:
        """
        Возвращает 'raw_data' или 'summary'.
        
        ARGS:
        - raw_data: данные для сохранения
        - explicit_mode: явный режим ('auto', 'full', 'summary')
        
        RETURNS:
        - 'raw_data' если данные помещаются в пороги
        - 'summary' если данные слишком большие
        """
        if explicit_mode in ("full", "summary"):
            if explicit_mode == "full" and cls._is_too_large(raw_data):
                return "summary"
            return explicit_mode
        
        return "summary" if cls._is_too_large(raw_data) else "raw_data"
    
    @classmethod
    def _is_too_large(cls, data: Any) -> bool:
        """Проверяет, превышают ли данные пороги."""
        if isinstance(data, list):
            if not data:
                return True
            if len(data) > cls.MAX_ROWS:
                return True
            try:
                return len(json.dumps(data, ensure_ascii=False)) > cls.MAX_JSON_BYTES
            except (TypeError, ValueError):
                return True
        if isinstance(data, str):
            return len(data) > cls.MAX_TEXT_CHARS
        if isinstance(data, dict):
            if len(data) > cls.MAX_DICT_KEYS:
                return True
            try:
                return len(json.dumps(data, ensure_ascii=False)) > cls.MAX_JSON_BYTES
            except (TypeError, ValueError):
                return True
        return True
    
    @classmethod
    def get_size_info(cls, data: Any) -> dict:
        """Возвращает информацию о размере данных."""
        info = {"type": type(data).__name__, "too_large": cls._is_too_large(data)}
        
        if isinstance(data, list):
            info["row_count"] = len(data)
            try:
                info["json_size"] = len(json.dumps(data, ensure_ascii=False))
            except (TypeError, ValueError):
                info["json_size"] = None
        elif isinstance(data, str):
            info["char_count"] = len(data)
        elif isinstance(data, dict):
            info["key_count"] = len(data)
            try:
                info["json_size"] = len(json.dumps(data, ensure_ascii=False))
            except (TypeError, ValueError):
                info["json_size"] = None
        
        return info