"""
Базовый класс для версионированных хранилищ.

АРХИТЕКТУРА:
- Общая логика поиска версионированных файлов
- Поддержка JSON/YAML форматов
- Поиск по подкаталогам с учётом ComponentType
- Валидация директорий

FEATURES:
- Автоматическое создание директорий
- Поиск файлов по множеству путей
- Поддержка компонент-специфичных подкаталогов
- Санитизация путей
"""
import json
import logging
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Generic

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.errors.version_not_found import VersionNotFoundError
from core.models.enums.common_enums import ComponentType


_logger = logging.getLogger(__name__)


T = TypeVar('T')


class VersionedStorage(ABC, Generic[T]):
    """
    Базовый класс для версионированных хранилищ.

    RESPONSIBILITIES:
    - Валидация директории хранилища
    - Поиск файлов по множеству путей
    - Загрузка JSON/YAML файлов
    - Поддержка компонент-специфичных подкаталогов

    USAGE:
    ```python
    class MyStorage(VersionedStorage[MyModel]):
        async def load(self, capability_name: str, version: str, ...) -> MyModel:
            files_to_check = self._build_file_search_paths(
                capability_name, version,
                extensions=['.json', '.yaml', '.yml']
            )
            file_path, file_format = self._find_existing_file(files_to_check)
            return self._parse_file(file_path, file_format)
    ```
    """

    # Стандартные подкаталоги для поиска
    STANDARD_SUBDIRS = ['skills', 'services', 'contracts', 'behaviors', 'sql_generation']

    def __init__(self, storage_dir: Path, event_bus=None):
        """
        Инициализация хранилища.

        ARGS:
        - storage_dir: директория для хранения
        - event_bus: шина событий для логирования (опционально)
        """
        self.storage_dir = storage_dir.resolve()
        self._validate_directory()

        _logger.info(
            f"{self.__class__.__name__} инициализировано: {self.storage_dir}",
            extra={"event_type": EventType.SYSTEM_INIT}
        )

    def _validate_directory(self) -> None:
        """Валидация директории хранилища."""
        if not self.storage_dir.exists():
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        if not self.storage_dir.is_dir():
            raise ValueError(f"Путь не является директорией: {self.storage_dir}")

    def _get_subdirs_for_component(self, component_type: Optional[ComponentType]) -> List[str]:
        """
        Получение списка подкаталогов для поиска по типу компонента.

        ARGS:
        - component_type: тип компонента или None

        RETURNS:
        - List[str]: список подкаталогов для поиска
        """
        if component_type is None:
            return self.STANDARD_SUBDIRS.copy()

        subdir_map = {
            ComponentType.SKILL: ['skills'],
            ComponentType.SERVICE: ['services'],
            ComponentType.TOOL: ['tools'],
            ComponentType.SQL_GENERATION: ['sql_generation'],
            ComponentType.CONTRACT: ['contracts'],
            ComponentType.BEHAVIOR: ['behaviors'],
        }

        return subdir_map.get(component_type, self.STANDARD_SUBDIRS.copy())

    def _build_file_search_paths(
        self,
        capability_name: str,
        version: str,
        extensions: List[str],
        component_type: Optional[ComponentType] = None,
        direction: Optional[str] = None,
        include_flat: bool = True,
        include_category: bool = True
    ) -> List[Path]:
        """
        Построение списка путей для поиска файла.

        ARGS:
        - capability_name: имя capability (например, "planning.create_plan")
        - version: версия (например, "v1.0.0")
        - extensions: список расширений для поиска (например, ['.json', '.yaml', '.yml'])
        - component_type: тип компонента для поиска в подкаталогах
        - direction: направление для контрактов ("input"/"output")
        - include_flat: включать ли плоскую структуру (capability_name_version.ext)
        - include_category: включать ли структуру по категориям

        RETURNS:
        - List[Path]: список путей для проверки
        """
        files_to_check = []

        # Преобразуем точки в слэши для пути
        capability_path = capability_name.replace(".", "/")
        parts = capability_name.split('.')

        # Определяем категорию и специфичную часть
        category = parts[0] if parts else capability_name
        specific = parts[1] if len(parts) >= 2 else ""

        # 1. Основной путь: {capability_path}/{version}.ext
        for ext in extensions:
            files_to_check.append(self.storage_dir / capability_path / f"{version}{ext}")

        # 2. Плоская структура: {capability_name_with_underscores}_{version}.ext
        if include_flat:
            flat_name = capability_name.replace('.', '_')
            for ext in extensions:
                files_to_check.append(self.storage_dir / f"{flat_name}_{version}{ext}")

        # 3. Компонент-специфичные подкаталоги
        standard_subdirs = self._get_subdirs_for_component(component_type)

        for subdir in standard_subdirs:
            subdir_path = self.storage_dir / subdir / capability_path
            for ext in extensions:
                files_to_check.append(subdir_path / f"{version}{ext}")

            # Если есть specific часть, добавляем файлы с specific_{version}.ext
            if specific:
                for ext in extensions:
                    files_to_check.append(
                        self.storage_dir / subdir / category / f"{specific}_{version}{ext}"
                    )

        # 4. Структура по категориям: {category}/{specific}_{direction}_{version}.ext
        if include_category and specific:
            for ext in extensions:
                if direction:
                    files_to_check.append(
                        self.storage_dir / category / f"{specific}_{direction}_{version}{ext}"
                    )
                    files_to_check.append(
                        self.storage_dir / category / f"{category}_{specific}_{direction}_{version}{ext}"
                    )
                else:
                    files_to_check.append(
                        self.storage_dir / category / f"{specific}_{version}{ext}"
                    )

        return files_to_check

    def _find_existing_file(
        self,
        files_to_check: List[Path]
    ) -> tuple[Optional[Path], Optional[str]]:
        """
        Поиск первого существующего файла в списке.

        ARGS:
        - files_to_check: список путей для проверки

        RETURNS:
        - tuple[Path, str]: (путь к файлу, формат) или (None, None)
        """
        for file_path in files_to_check:
            if file_path and file_path.exists():
                file_format = self._determine_file_format(file_path)
                return file_path, file_format

        return None, None

    def _determine_file_format(self, file_path: Path) -> str:
        """
        Определение формата файла по расширению.

        ARGS:
        - file_path: путь к файлу

        RETURNS:
        - str: 'json', 'yaml' или 'unknown'
        """
        suffix = file_path.suffix.lower()
        if suffix == '.json':
            return 'json'
        elif suffix in ['.yaml', '.yml']:
            return 'yaml'
        return 'unknown'

    def _load_file(self, file_path: Path, file_format: str) -> Any:
        """
        Загрузка данных из файла.

        ARGS:
        - file_path: путь к файлу
        - file_format: формат файла ('json' или 'yaml')

        RETURNS:
        - Any: данные из файла
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_format == 'json':
                    return json.load(f)
                elif file_format == 'yaml':
                    return yaml.safe_load(f)
                else:
                    raise ValueError(f"Неизвестный формат файла: {file_format}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ошибка парсинга JSON файла {file_path}: {e}")
        except yaml.YAMLError as e:
            raise RuntimeError(f"Ошибка парсинга YAML файла {file_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки файла {file_path}: {type(e).__name__}: {e}")

    def _save_file(
        self,
        file_path: Path,
        data: Any,
        file_format: str = 'yaml'
    ) -> None:
        """
        Сохранение данных в файл.

        ARGS:
        - file_path: путь к файлу
        - data: данные для сохранения
        - file_format: формат файла ('json' или 'yaml')
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if file_format == 'json':
                    json.dump(data, f, indent=2, ensure_ascii=False)
                elif file_format == 'yaml':
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, indent=2)
        except Exception as e:
            raise RuntimeError(f"Ошибка сохранения файла {file_path}: {type(e).__name__}: {e}")

    def _create_file_not_found_error(
        self,
        capability_name: str,
        version: str,
        files_to_check: List[Path],
        component_type: Optional[ComponentType] = None,
        direction: Optional[str] = None,
        item_type: str = "Ресурс"
    ) -> VersionNotFoundError:
        """
        Создание ошибки "файл не найден" с подробной информацией.

        ARGS:
        - capability_name: имя capability
        - version: версия
        - files_to_check: список проверенных путей
        - component_type: тип компонента
        - direction: направление (для контрактов)
        - item_type: тип элемента ("Промпт", "Контракт" и т.д.)

        RETURNS:
        - VersionNotFoundError: ошибка с подробным сообщением
        """
        message = (
            f"{item_type} не найден: capability={capability_name}, version={version}"
        )
        if component_type:
            message += f", component_type={component_type}"
        if direction:
            message += f", direction={direction}"

        message += f"\nПроверьте пути:\n"
        for i, path in enumerate(files_to_check[:10], 1):  # Показываем первые 10 путей
            message += f"  {i}. {path}\n"

        if len(files_to_check) > 10:
            message += f"  ... и ещё {len(files_to_check) - 10} путей\n"

        return VersionNotFoundError(message)

    async def exists(self, file_path: Path) -> bool:
        """
        Проверка существования файла.

        ARGS:
        - file_path: путь к файлу

        RETURNS:
        - bool: True если файл существует
        """
        return file_path.exists()

    @abstractmethod
    async def load(self, capability_name: str, version: str, **kwargs) -> T:
        """
        Загрузка элемента из хранилища.

        ДОЛЖЕН БЫТЬ РЕАЛИЗОВАН в наследниках.

        ARGS:
        - capability_name: имя capability
        - version: версия
        - **kwargs: дополнительные параметры

        RETURNS:
        - T: загруженный элемент
        """
        pass

    @abstractmethod
    async def save(self, capability_name: str, version: str, item: T, **kwargs) -> None:
        """
        Сохранение элемента в хранилище.

        ДОЛЖНО БЫТЬ РЕАЛИЗОВАНО в наследниках.

        ARGS:
        - capability_name: имя capability
        - version: версия
        - item: элемент для сохранения
        - **kwargs: дополнительные параметры
        """
        pass
