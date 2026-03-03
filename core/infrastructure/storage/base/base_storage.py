"""
Базовый класс для файловых хранилищ.

КОМПОНЕНТЫ:
- FileSystemStorage: базовый класс с общей логикой работы с JSON файлами

FEATURES:
- Потокобезопасная запись через asyncio.Lock
- Загрузка/сохранение JSON файлов
- Очистка старых файлов
- Автоматическое создание директорий
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, TypeVar, Generic, Callable

T = TypeVar('T')


class FileSystemStorage(Generic[T]):
    """
    Базовый класс для файловых хранилищ.

    STRUCTURE:
    data/
    └── {storage_type}/
        └── {category}/
            └── {subcategory}/
                └── files.json

    FEATURES:
    - Автоматическое создание директорий
    - Потокобезопасная запись через lock
    - Загрузка/сохранение JSON
    - Очистка старых файлов
    """

    def __init__(self, base_dir: Path, file_prefix: str = "data"):
        """
        Инициализация хранилища.

        ARGS:
        - base_dir: базовая директория для хранения
        - file_prefix: префикс для имён файлов (например, "metrics" или "logs")
        """
        self.base_dir = base_dir
        self.file_prefix = file_prefix
        self._lock = asyncio.Lock()
        self._ensure_base_dir()

    def _ensure_base_dir(self) -> None:
        """Создание базовой директории если не существует"""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_path_component(self, component: str) -> str:
        """
        Замена недопустимых символов в имени компонента пути.

        ARGS:
        - component: строка для санитизации

        RETURNS:
        - str: безопасная строка для использования в пути
        """
        return component.replace('/', '_').replace('\\', '_')

    def _load_json_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Загрузка данных из JSON файла.

        ARGS:
        - file_path: путь к файлу

        RETURNS:
        - List[Dict[str, Any]]: список словарей из файла
        """
        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []

    def _save_json_file(self, file_path: Path, data: List[Dict[str, Any]]) -> None:
        """
        Сохранение данных в JSON файл.

        ARGS:
        - file_path: путь к файлу
        - data: данные для сохранения
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _parse_item(self, data: Dict[str, Any]) -> Optional[T]:
        """
        Парсинг элемента из словаря.

        ДОЛЖЕН БЫТЬ ПЕРЕОПРЕДЕЛЁН в наследниках.

        ARGS:
        - data: словарь с данными

        RETURNS:
        - Optional[T]: объект типа T или None
        """
        raise NotImplementedError("Метод _parse_item должен быть переопределён")

    def _item_to_dict(self, item: T) -> Dict[str, Any]:
        """
        Преобразование элемента в словарь.

        ДОЛЖЕН БЫТЬ ПЕРЕОПРЕДЕЛЁН в наследниках.

        ARGS:
        - item: объект типа T

        RETURNS:
        - Dict[str, Any]: словарь с данными
        """
        raise NotImplementedError("Метод _item_to_dict должен быть переопределён")

    async def _atomic_write(self, file_path: Path, items: List[T]) -> None:
        """
        Атомарная запись списка элементов в файл.

        ARGS:
        - file_path: путь к файлу
        - items: список элементов для записи
        """
        async with self._lock:
            data = [self._item_to_dict(item) for item in items]
            self._save_json_file(file_path, data)

    async def _atomic_append(
        self,
        file_path: Path,
        item: T,
        max_items: Optional[int] = None
    ) -> None:
        """
        Атомарное добавление элемента в файл.

        ARGS:
        - file_path: путь к файлу
        - item: элемент для добавления
        - max_items: максимальное количество элементов (None = без ограничений)
        """
        loop = asyncio.get_event_loop()
        
        # Чтение в executor (не блокирует event loop)
        existing = await loop.run_in_executor(None, self._load_json_file, file_path)
        existing.append(self._item_to_dict(item))

        if max_items:
            existing = existing[-max_items:]

        # Запись в executor (не блокирует event loop)
        await loop.run_in_executor(None, self._save_json_file, file_path, existing)

    async def _load_items(self, file_path: Path) -> List[T]:
        """
        Загрузка списка элементов из файла.

        ARGS:
        - file_path: путь к файлу

        RETURNS:
        - List[T]: список элементов
        """
        data = self._load_json_file(file_path)
        items = []

        for item_data in data:
            item = self._parse_item(item_data)
            if item is not None:
                items.append(item)

        return items

    async def _load_items_from_pattern(
        self,
        pattern: str,
        parser: Optional[Callable[[Dict[str, Any]], Optional[T]]] = None
    ) -> List[T]:
        """
        Загрузка элементов из файлов по шаблону.

        ARGS:
        - pattern: glob шаблон для поиска файлов
        - parser: функция парсинга (по умолчанию используется _parse_item)

        RETURNS:
        - List[T]: список элементов
        """
        if parser is None:
            parser = self._parse_item

        items = []

        for file_path in self.base_dir.rglob(pattern):
            file_items = await self._load_items(file_path)
            items.extend(file_items)

        return items

    async def clear_old(self, older_than: datetime) -> int:
        """
        Очистка старых файлов.

        ДОЛЖЕН БЫТЬ ПЕРЕОПРЕДЕЛЁН в наследниках для специфичной логики.

        ARGS:
        - older_than: удалять файлы старше этой даты

        RETURNS:
        - int: количество удалённых записей
        """
        async with self._lock:
            deleted_count = 0

            # Поиск всех файлов с префиксом
            for file_path in self.base_dir.rglob(f'{self.file_prefix}_*.json'):
                try:
                    # Извлечение даты из имени файла
                    date_str = file_path.stem.replace(f'{self.file_prefix}_', '')
                    file_date = datetime.strptime(date_str, '%Y-%m-%d')

                    if file_date < older_than:
                        # Подсчёт записей перед удалением
                        data = self._load_json_file(file_path)
                        deleted_count += len(data)
                        file_path.unlink()
                except (ValueError, OSError):
                    continue

            return deleted_count

    def get_file_for_date(self, date: datetime, *path_parts: str) -> Path:
        """
        Получение пути к файлу для указанной даты.

        ARGS:
        - date: дата для файла
        - path_parts: дополнительные части пути

        RETURNS:
        - Path: путь к файлу
        """
        date_str = date.strftime('%Y-%m-%d')
        filename = f'{self.file_prefix}_{date_str}.json'

        dir_path = self.base_dir
        for part in path_parts:
            dir_path = dir_path / self._sanitize_path_component(part)

        return dir_path / filename

    def get_file(self, *path_parts: str, extension: str = ".json") -> Path:
        """
        Получение пути к файлу.

        ARGS:
        - path_parts: части пути
        - extension: расширение файла

        RETURNS:
        - Path: путь к файлу
        """
        dir_path = self.base_dir

        for i, part in enumerate(path_parts):
            sanitized = self._sanitize_path_component(part)
            if i == len(path_parts) - 1 and extension:
                # Последний элемент - это имя файла
                dir_path = dir_path / f"{sanitized}{extension}"
            else:
                dir_path = dir_path / sanitized

        return dir_path

    def get_dir(self, *path_parts: str) -> Path:
        """
        Получение пути к директории.

        ARGS:
        - path_parts: части пути

        RETURNS:
        - Path: путь к директории
        """
        dir_path = self.base_dir

        for part in path_parts:
            sanitized = self._sanitize_path_component(part)
            dir_path = dir_path / sanitized
            dir_path.mkdir(parents=True, exist_ok=True)

        return dir_path
