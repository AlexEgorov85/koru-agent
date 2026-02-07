"""Модели для представления структуры проекта.

Этот модуль содержит основную модель для работы со структурой проекта:
- ProjectStructure - основная структура проекта

Модель разработана для:
1. Эффективного хранения иерархической структуры проекта
2. Быстрого поиска и фильтрации
3. Анализа зависимостей между компонентами
4. Интеграции с LLM для анализа кодовой базы

Примеры использования:

1. Создание ProjectStructure:
```python
project = ProjectStructure(root_dir="core/skills")
project.add_file(FileInfo(
    file_path="core/skills/project_map/skill.py",
    size=15000,
    last_modified=170000
))
```
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

from domain.core.project.value_objects.code_unit import CodeUnit
from domain.core.project.value_objects.directory_info import DirectoryInfo
from domain.core.project.value_objects.entry_point import EntryPointInfo
from domain.core.project.value_objects.file_dependency import FileDependency
from domain.core.project.value_objects.file_info import FileInfo


class ProjectStructure:
    """Структура карты проекта.
    Основной класс для хранения и работы со структурой проекта.
    Содержит полную информацию о проекте в удобном для анализа формате.

    Особенности:
    1. Иерархическое представление файловой структуры
    2. Плоские списки для быстрого поиска
    3. Кэширование для производительности
    4. Поддержка анализа зависимостей

    Атрибуты:
    - root_dir: корневая директория проекта
    - scan_time: время последнего сканирования
    - total_files: общее количество файлов
    - total_code_units: общее количество единиц кода
    - files: словарь файлов (file_path -> FileInfo)
    - directory_tree: иерархическая структура директорий
    - code_units: словарь единиц кода (unit_id -> CodeUnit)
    - file_dependencies: зависимости между файлами
    - entry_points: основные точки входа
    - _cache: кэш для быстрого поиска

    Примеры использования:

    1. Создание и наполнение:
    ```python
    project = ProjectStructure()
    project.root_dir = "core/skills"
    project.add_file(FileInfo(file_path="core/skills/__init__.py", size=100, last_modified=1700000000))
    ```

    2. Получение информации о файле:
    ```python
    file_info = project.get_file_info("core/skills/project_map/skill.py")
    if file_info:
        print(f"Файл содержит {len(file_info.code_unit_ids)} единиц кода")
    ```

    3. Получение единиц кода по типу:
    ```python
    classes = project.get_code_units_by_type("class")
    print(f"Найдено классов: {len(classes)}")
    ```

    4. Поиск по имени:
    ```python
    main_units = project.get_code_units_by_name("main", exact=True)
    ```

    5. Сериализация для LLM:
    ```python
    data = project.to_dict()
    print(f"Структура проекта: {json.dumps(data, indent=2)}")
    ```
    """

    def __init__(self):
        # Основная информация о проекте
        self.root_dir: str = ""
        self.scan_time: datetime = datetime.utcnow()
        self.total_files: int = 0
        self.total_code_units: int = 0
        
        # Файловая структура (плоский список для быстрого доступа)
        self.files: Dict[str, 'FileInfo'] = {}  # file_path -> FileInfo
        
        # Иерархическая структура директорий
        self.directory_tree: Dict[str, 'DirectoryInfo'] = {}  # path -> DirectoryInfo
        
        # Все единицы кода (плоский список для быстрого поиска)
        self.code_units: Dict[str, CodeUnit] = {}  # unit_id -> CodeUnit
        
        # Зависимости между файлами
        self.file_dependencies: Dict[str, List['FileDependency']] = {}  # file_path -> [dependencies]
        
        # Точки входа в проект
        self.entry_points: List['EntryPointInfo'] = []
        
        # Кэш для быстрого поиска
        self._cache: Dict[str, Any] = {
            'by_type': {},  # type -> [unit_ids]
            'by_name': {},  # name -> [unit_ids]
            'by_file': {}   # file_path -> [unit_ids]
        }

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации.
        
        Возвращает компактное представление структуры проекта,
        подходящее для передачи в LLM.
        
        Returns:
            Dict[str, Any]: сериализованная структура проекта
        """
        return {
            'root_dir': self.root_dir,
            'scan_time': self.scan_time,
            'total_files': self.total_files,
            'total_code_units': self.total_code_units,
            'files_count': len(self.files),
            'directory_count': len(self.directory_tree),
            'code_units_count': len(self.code_units),
            'entry_points_count': len(self.entry_points),
            'dependencies_count': sum(len(deps) for deps in self.file_dependencies.values()),
            'file_types': self._get_file_types_summary(),
            'top_entry_points': [ep.to_dict() for ep in self.entry_points[:10]]
        }

    def _get_file_types_summary(self) -> Dict[str, int]:
        """Получение сводки по типам файлов."""
        summary = {}
        for file_path in self.files.keys():
            ext = file_path.split('.')[-1]
            summary[ext] = summary.get(ext, 0) + 1
        return summary

    def get_file_info(self, file_path: str) -> Optional['FileInfo']:
        """Получение информации о файле.
        
        Args:
            file_path: путь к файлу относительно корня проекта
            
        Returns:
            Optional[FileInfo]: информация о файле или None если не найден
        """
        return self.files.get(file_path)

    def get_code_units_by_file(self, file_path: str) -> List[CodeUnit]:
        """Получение всех единиц кода из файла.
        
        Args:
            file_path: путь к файлу
            
        Returns:
            List[CodeUnit]: список единиц кода в файле
        """
        if file_path not in self._cache['by_file']:
            units = [unit for unit in self.code_units.values() if unit.location.file_path == file_path]
            self._cache['by_file'][file_path] = units
        return self._cache['by_file'][file_path]

    def get_code_units_by_type(self, unit_type: str) -> List[CodeUnit]:
        """Получение единиц кода по типу.
        
        Args:
            unit_type: тип единицы кода (например, "class", "function")
            
        Returns:
            List[CodeUnit]: список единиц кода указанного типа
        """
        if unit_type not in self._cache['by_type']:
            units = [unit for unit in self.code_units.values() if unit.type.value == unit_type]
            self._cache['by_type'][unit_type] = units
        return self._cache['by_type'][unit_type]

    def get_code_units_by_name(self, name: str, exact: bool = False) -> List[CodeUnit]:
        """Поиск единиц кода по имени.
        
        Args:
            name: имя для поиска
            exact: точное совпадение или частичное
            
        Returns:
            List[CodeUnit]: список найденных единиц кода
        """
        cache_key = f"{'exact' if exact else 'partial'}_{name}"
        if cache_key not in self._cache['by_name']:
            if exact:
                units = [unit for unit in self.code_units.values() if unit.name == name]
            else:
                units = [unit for unit in self.code_units.values() if name.lower() in unit.name.lower()]
            self._cache['by_name'][cache_key] = units
        return self._cache['by_name'][cache_key]