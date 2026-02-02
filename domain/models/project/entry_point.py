"""Модели для представления точек входа в проект.

Этот модуль содержит модель для работы с точками входа в проект:
- EntryPointInfo - информация о точке входа

Модель разработана для:
1. Отслеживания основных точек входа в приложение
2. Определения структуры запуска приложения
3. Анализа архитектуры проекта
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class EntryPointInfo:
    """Информация о точке входа в проекте.
    Представляет основные точки входа в приложение:
    - main функции
    - классы приложений
    - API endpoints

    Атрибуты:
    - name: имя точки входа
    - file_path: путь к файлу
    - line: строка в файле
    - entry_type: тип точки входа ("main", "api", "export", "class")

    Пример:
    ```python
    entry_point = EntryPointInfo(
        name="main",
        file_path="core/main.py",
        line=10,
        entry_type="main"
    )
    ```
    """

    name: str
    file_path: str
    line: int
    entry_type: str

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        return {
            'name': self.name,
            'file_path': self.file_path,
            'line': self.line,
            'entry_type': self.entry_type
        }