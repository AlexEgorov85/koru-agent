"""
Вспомогательные функции и утилиты для навыка навигации.
"""
import os
from collections import OrderedDict
from typing import Any, Optional, Dict


class LRUCache:
    """Простой LRU кэш с ограничением по размеру."""
    
    def __init__(self, maxsize: int = 100):
        self.maxsize = maxsize
        self.cache = OrderedDict()
    
    def get(self, key: Any) -> Optional[Any]:
        """Получение значения из кэша."""
        if key in self.cache:
            # Перемещаем элемент в конец (самый недавно использованный)
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        return None
    
    def set(self, key: Any, value: Any):
        """Установка значения в кэш."""
        if key in self.cache:
            # Удаляем существующий элемент
            self.cache.pop(key)
        elif len(self.cache) >= self.maxsize:
            # Удаляем самый старый элемент
            self.cache.popitem(last=False)
        # Добавляем новый элемент
        self.cache[key] = value
    
    def clear(self):
        """Очистка кэша."""
        self.cache.clear()
    
    def __len__(self):
        """Количество элементов в кэше."""
        return len(self.cache)


def normalize_path(path: str) -> str:
    """
    Нормализация пути для кросс-платформенной совместимости.
    
    Преобразует:
    - Обратные слеши в прямые (Windows → Unix)
    - Удаляет избыточные разделители
    - Убирает ./ в начале пути
    
    Примеры:
    >>> normalize_path("core\\skills\\project_navigator\\skill.py")
    'core/skills/project_navigator/skill.py'
    >>> normalize_path("./core/skills/project_map/skill.py")
    'core/skills/project_map/skill.py'
    """
    # Замена обратных слешей на прямые
    normalized = path.replace('\\', '/').replace('//', '/')
    # Удаление начального ./ если есть
    if normalized.startswith('./'):
        normalized = normalized[2:]
    return normalized


def is_path_match(path1: str, path2: str) -> bool:
    """
    Проверка совпадения путей с учётом нормализации.
    
    Примеры:
    >>> is_path_match("core/skills/project_map/skill.py", "core\\skills\\project_map\\skill.py")
    True
    >>> is_path_match("./core/skills/project_map/skill.py", "core/skills/project_map/skill.py")
    True
    """
    return normalize_path(path1) == normalize_path(path2)


def calculate_relevance(element_name: str, query: str, exact_match: bool) -> float:
    """
    Вычисление релевантности элемента запросу.
    
    Алгоритм:
    1. Точное совпадение → 1.0
    2. Начало имени совпадает → 0.9
    3. Частичное совпадение → 0.7
    4. Похожесть по Левенштейну → 0.3-0.6
    
    Возвращает значение от 0.0 до 1.0
    """
    element_lower = element_name.lower()
    query_lower = query.lower()
    
    if exact_match:
        return 1.0 if element_lower == query_lower else 0.0
    
    if element_lower == query_lower:
        return 1.0
    
    if element_lower.startswith(query_lower):
        return 0.95
    
    if query_lower in element_lower:
        # Бонус за позицию: чем ближе к началу, тем выше релевантность
        position = element_lower.find(query_lower)
        bonus = 0.1 if position < 5 else 0.05
        return 0.8 + bonus
    
    # Fuzzy match (простая реализация)
    common_chars = sum(1 for c in query_lower if c in element_lower)
    max_len = max(len(query_lower), len(element_lower))
    similarity = common_chars / max_len if max_len > 0 else 0.0
    
    return min(0.7, similarity) if similarity > 0.3 else 0.0