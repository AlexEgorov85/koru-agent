"""
Вспомогательные функции и утилиты для навыка навигации.
КРИТИЧЕСКИ ВАЖНО: Корректная нормализация путей для работы с разными ОС и форматами.
"""
import os
import re
from collections import OrderedDict
from typing import Any, Optional, Dict, List, Tuple


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
    НОРМАЛИЗАЦИЯ ПУТЕЙ ДЛЯ КРОСС-ПЛАТФОРМЕННОЙ СОВМЕСТИМОСТИ.
    
    ПРЕОБРАЗУЕТ ЛЮБОЙ ФОРМАТ В ЕДИНЫЙ:
    - Все разделители → прямые слеши (/)
    - Удаляет ./ и ../ в начале
    - Удаляет диск (C:/, D:/) для путей Windows
    - Приводит к нижнему регистру для надежного сравнения
    
    Примеры:
    >>> normalize_path("C:/Users/Алексей/Documents/WORK/Agent_code/core/skills/project_navigator/skill.py")
    'core/skills/project_navigator/skill.py'
    
    >>> normalize_path("core\\skills\\project_navigator\\skill.py")
    'core/skills/project_navigator/skill.py'
    
    >>> normalize_path("./core/skills/project_navigator/skill.py")
    'core/skills/project_navigator/skill.py'
    
    >>> normalize_path("/home/user/Agent_code/core/skills/project_navigator/skill.py")
    'core/skills/project_navigator/skill.py'
    """
    if not path:
        return ""
    
    # 1. Замена всех разделителей на прямые слеши
    normalized = path.replace('\\', '/').replace('//', '/')
    
    # 2. Удаление ./ и ../ в начале
    while normalized.startswith('./'):
        normalized = normalized[2:]
    while normalized.startswith('../'):
        normalized = normalized[3:]
    
    # 3. Удаление префикса диска Windows (C:/, D:/ и т.д.)
    # Регулярка для поиска диска в начале пути: "C:/", "D:/", и т.д.
    disk_match = re.match(r'^[a-zA-Z]:/', normalized)
    if disk_match:
        normalized = normalized[disk_match.end():]
    
    # 4. Удаление префикса корня проекта (все, что до "Agent_code/" или "agent_code/")
    # Ищем маркер корня проекта (регистронезависимо)
    agent_code_pos = normalized.lower().find('agent_code/')
    if agent_code_pos != -1:
        normalized = normalized[agent_code_pos + len('agent_code/'):]
    
    # 5. Удаляем начальные и конечные слеши
    normalized = normalized.strip('/')
    
    # 6. Приводим к нижнему регистру для надежного сравнения
    normalized = normalized.lower()
    
    return normalized


def is_path_match(candidate_path: str, target_path: str) -> bool:
    """
    Проверка совпадения путей с учётом нормализации и приоритета точного совпадения.
    
    СТРАТЕГИЯ ПОИСКА (в порядке приоритета):
    1. Точное совпадение нормализованных путей → возвращает True немедленно
    2. Частичное совпадение по последним компонентам → только если точное не найдено
       (например, "project_navigator/skill.py" должно совпасть с 
        "core/skills/project_navigator/skill.py", но НЕ с "core/skills/base_skill.py")
    3. Совпадение только по имени файла → последний резорт
    
    Возвращает:
    - True если пути совпадают по одной из стратегий
    - False если не совпадают
    
    Примеры:
    >>> is_path_match("core/skills/project_navigator/skill.py", "skill.py")
    True  # Совпадение по имени файла (последний резорт)
    
    >>> is_path_match("core/skills/project_navigator/skill.py", "project_navigator/skill.py")
    True  # Частичное совпадение по 2 компонентам
    
    >>> is_path_match("core/skills/project_navigator/skill.py", "core/skills/project_navigator/skill.py")
    True  # Точное совпадение
    
    >>> is_path_match("core/skills/project_navigator/skill.py", "core/skills/base_skill.py")
    False  # НЕ должно совпадать по имени файла при наличии более точного совпадения
    """
    # Нормализуем оба пути
    norm_candidate = normalize_path(candidate_path)
    norm_target = normalize_path(target_path)
    
    # 1. Точное совпадение (высший приоритет)
    if norm_candidate == norm_target:
        return True
    
    # 2. Частичное совпадение по последним компонентам
    # Разбиваем на компоненты
    candidate_parts = norm_candidate.split('/')
    target_parts = norm_target.split('/')
    
    # Проверяем, что последние компоненты совпадают
    # (например, ['project_navigator', 'skill.py'] должно совпасть с 
    #  ['core', 'skills', 'project_navigator', 'skill.py'])
    min_len = min(len(candidate_parts), len(target_parts))
    if min_len > 0:
        # Сравниваем последние компоненты в обратном порядке
        # Чем больше совпавших компонентов, тем выше приоритет
        match_count = 0
        for i in range(1, min_len + 1):
            if candidate_parts[-i] == target_parts[-i]:
                match_count += 1
            else:
                break
        
        # Если совпали ВСЕ компоненты более короткого пути → считаем совпадением
        if match_count == min_len:
            return True
    
    # 3. Совпадение только по имени файла (низший приоритет)
    if candidate_parts[-1] == target_parts[-1]:
        return True
    
    return False


def find_best_path_match(
    input_path: str,
    available_paths: List[str]
) -> Tuple[Optional[str], int]:
    """
    НАХОЖДЕНИЕ ЛУЧШЕГО СОВПАДЕНИЯ ПУТИ С УЧЕТОМ ПРИОРИТЕТОВ.
    
    Возвращает:
    - (лучший_путь, приоритет) где приоритет: 3=точное, 2=частичное, 1=по имени, 0=не найдено
    
    Приоритеты:
    3. Точное совпадение нормализованных путей
    2. Частичное совпадение по последним компонентам (чем больше компонентов, тем выше приоритет)
    1. Совпадение только по имени файла
    0. Не найдено
    
    Пример:
    >>> paths = [
    ...     "core/skills/base_skill.py",
    ...     "core/skills/project_navigator/skill.py",
    ...     "core/skills/project_map/skill.py"
    ... ]
    >>> find_best_path_match("project_navigator/skill.py", paths)
    ("core/skills/project_navigator/skill.py", 2)  # Частичное совпадение по 2 компонентам
    
    >>> find_best_path_match("core/skills/project_navigator/skill.py", paths)
    ("core/skills/project_navigator/skill.py", 3)  # Точное совпадение
    """
    if not input_path or not available_paths:
        return None, 0
    
    norm_input = normalize_path(input_path)
    input_parts = norm_input.split('/')
    
    best_path = None
    best_priority = 0  # 0 = не найдено, 1 = по имени, 2 = частичное, 3 = точное
    best_match_count = 0  # Для разрешения конфликтов при частичном совпадении
    
    for candidate_path in available_paths:
        norm_candidate = normalize_path(candidate_path)
        candidate_parts = norm_candidate.split('/')
        
        # Приоритет 3: Точное совпадение
        if norm_candidate == norm_input:
            return candidate_path, 3
        
        # Приоритет 2: Частичное совпадение по последним компонентам
        # Считаем количество совпавших последних компонентов
        match_count = 0
        for i in range(1, min(len(candidate_parts), len(input_parts)) + 1):
            if candidate_parts[-i] == input_parts[-i]:
                match_count += 1
            else:
                break
        
        # Если совпали ВСЕ компоненты входного пути → приоритет 2
        if match_count == len(input_parts) and match_count > 0:
            # Выбираем путь с максимальным количеством совпавших компонентов
            if match_count > best_match_count or (match_count == best_match_count and best_priority < 2):
                best_path = candidate_path
                best_priority = 2
                best_match_count = match_count
    
    # Приоритет 1: Совпадение только по имени файла (если ничего лучше не найдено)
    if best_priority < 2:
        for candidate_path in available_paths:
            norm_candidate = normalize_path(candidate_path)
            candidate_parts = norm_candidate.split('/')
            
            if candidate_parts[-1] == input_parts[-1] and best_priority < 1:
                best_path = candidate_path
                best_priority = 1
                break
    
    return best_path, best_priority


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


def extract_error_location(error_log: str) -> Optional[Tuple[str, int, str]]:
    """
    Извлечение местоположения ошибки из стека вызовов.
    Возвращает: (файл, строка, метод) или None
    
    Пример для ошибки из лога:
    "File \"C:\\Users\\Алексей\\Documents\\WORK\\Agent_code\\core\\skills\\project_navigator\\skill.py\", line 282, in _navigate"
    → ("core/skills/project_navigator/skill.py", 282, "_navigate")
    
    Поддерживает разные форматы стека:
    - С одинарными кавычками: File 'path', line N, in method
    - С двойными кавычками: File "path", line N, in method
    - Без кавычек: File path, line N, in method
    """
    if not error_log:
        return None
    
    # Регулярка для извлечения местоположения из стека
    # Поддерживает разные форматы кавычек и разделителей
    pattern = r'File\s+[\'\"]?([^\'\",\s]+)[\'\"]?,\s+line\s+(\d+),\s+in\s+(\w+)'
    match = re.search(pattern, error_log)
    
    if not match:
        # Альтернативный формат (без 'in method')
        alt_pattern = r'File\s+[\'\"]?([^\'\",\s]+)[\'\"]?,\s+line\s+(\d+)'
        alt_match = re.search(alt_pattern, error_log)
        if alt_match:
            file_path = alt_match.group(1)
            line_number = int(alt_match.group(2))
            method_name = "unknown"
        else:
            return None
    else:
        file_path = match.group(1)
        line_number = int(match.group(2))
        method_name = match.group(3)
    
    # Нормализуем путь для соответствия структуре проекта
    normalized_path = normalize_path(file_path)
    
    return (normalized_path, line_number, method_name)