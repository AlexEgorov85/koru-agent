"""
Хранилище логов на файловой системе.

КОМПОНЕНТЫ:
- FileSystemLogStorage: реализация ILogStorage

FEATURES:
- Сохранение логов в JSON файлы
- Индексация по agent_id, session_id, capability
- Очистка старых логов
- Потокобезопасная запись
"""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from core.benchmarks.benchmark_models import LogEntry, LogType
from core.infrastructure.interfaces.metrics_log_interfaces import ILogStorage
from core.infrastructure.storage.base.base_storage import FileSystemStorage


class FileSystemLogStorage(FileSystemStorage[LogEntry], ILogStorage):
    """
    Хранилище логов на файловой системе.

    STRUCTURE:
    data/
    └── logs/
        ├── by_agent/
        │   └── {agent_id}/
        │       └── {session_id}/
        │           └── logs.json
        ├── by_capability/
        │   └── {capability}/
        │       └── logs.json
        └── all/
            └── logs_{date}.json

    FEATURES:
    - Автоматическое создание директорий
    - Потокобезопасная запись через lock
    - Индексация по разным ключам
    """

    def __init__(self, base_dir: Path = None):
        """
        Инициализация хранилища.

        ARGS:
        - base_dir: базовая директория для хранения (по умолчанию data/logs)
        """
        if base_dir is None:
            base_dir = Path('data/logs')

        super().__init__(base_dir, file_prefix='logs')

        # Создание поддиректорий
        (self.base_dir / 'by_agent').mkdir(exist_ok=True)
        (self.base_dir / 'by_capability').mkdir(exist_ok=True)
        (self.base_dir / 'all').mkdir(exist_ok=True)

    def _parse_item(self, data: Dict[str, Any]) -> Optional[LogEntry]:
        """Парсинг записи лога из словаря"""
        try:
            return LogEntry.from_dict(data)
        except (KeyError, ValueError):
            return None

    def _item_to_dict(self, item: LogEntry) -> Dict[str, Any]:
        """Преобразование записи лога в словарь"""
        return item.to_dict()

    # Методы для обратной совместимости с тестами
    def _load_json_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Загрузка данных из JSON файла (для обратной совместимости)"""
        return super()._load_json_file(file_path)

    def _save_json_file(self, file_path: Path, data: List[Dict[str, Any]]) -> None:
        """Сохранение данных в JSON файл (для обратной совместимости)"""
        super()._save_json_file(file_path, data)

    def _parse_log_entry(self, data: Dict[str, Any]) -> Optional[LogEntry]:
        """Парсинг записи лога из словаря (для обратной совместимости)"""
        return self._parse_item(data)

    async def save(self, entry: LogEntry) -> None:
        """
        Сохранение записи лога.

        ARGS:
        - entry: объект записи лога

        FEATURES:
        - Сохранение в 3 места:
          1. by_agent/{agent_id}/{session_id}/logs.json
          2. by_capability/{capability}/logs.json (если указан)
          3. all/logs_{date}.json
        - Потокобезопасная запись через lock
        """
        async with self._lock:
            # 1. Сохранение в директорию агента/сессии
            if entry.agent_id and entry.session_id:
                agent_file = self._get_agent_session_file(entry.agent_id, entry.session_id)
                await self._atomic_append(agent_file, entry, max_items=10000)

            # 2. Сохранение в директорию capability
            if entry.capability:
                cap_file = self._get_capability_file(entry.capability)
                await self._atomic_append(cap_file, entry, max_items=10000)

            # 3. Сохранение в общие логи
            all_file = self._get_all_logs_file(entry.timestamp)
            await self._atomic_append(all_file, entry, max_items=100000)

    def _get_agent_session_dir(self, agent_id: str, session_id: str) -> Path:
        """Получение директории для сессии агента"""
        safe_agent_id = agent_id.replace('/', '_').replace('\\', '_')
        safe_session_id = session_id.replace('/', '_').replace('\\', '_')

        dir_path = self.base_dir / 'by_agent' / safe_agent_id / safe_session_id
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    def _get_capability_dir(self, capability: str) -> Path:
        """Получение директории для capability"""
        safe_capability = capability.replace('/', '_').replace('\\', '_')

        dir_path = self.base_dir / 'by_capability' / safe_capability
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    def _get_all_logs_file(self, date: datetime = None) -> Path:
        """Получение пути к файлу всех логов за день"""
        if date is None:
            date = datetime.now()

        date_str = date.strftime('%Y-%m-%d')
        return self.base_dir / 'all' / f'logs_{date_str}.json'

    def _get_agent_session_file(self, agent_id: str, session_id: str) -> Path:
        """Получение пути к файлу логов сессии"""
        dir_path = self._get_agent_session_dir(agent_id, session_id)
        return dir_path / 'logs.json'

    def _get_capability_file(self, capability: str) -> Path:
        """Получение пути к файлу логов capability"""
        dir_path = self._get_capability_dir(capability)
        return dir_path / 'logs.json'

    async def get_by_session(
        self,
        agent_id: str,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Получение логов сессии.

        ARGS:
        - agent_id: идентификатор агента
        - session_id: идентификатор сессии
        - limit: максимальное количество записей (опционально)

        RETURNS:
        - List[LogEntry]: список записей лога
        """
        file_path = self._get_agent_session_file(agent_id, session_id)
        entries = await self._load_items(file_path)

        # Сортировка по времени
        entries.sort(key=lambda e: e.timestamp)

        # Ограничение количества
        if limit:
            entries = entries[-limit:]

        return entries

    async def get_by_capability(
        self,
        capability: str,
        log_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Получение логов по способности.

        ARGS:
        - capability: название способности
        - log_type: тип лога (опционально)
        - limit: максимальное количество записей (опционально)

        RETURNS:
        - List[LogEntry]: список записей лога
        """
        file_path = self._get_capability_file(capability)
        entries = await self._load_items(file_path)

        # Фильтрация по типу лога
        if log_type:
            entries = [e for e in entries if e.log_type.value == log_type]

        # Сортировка по времени
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        # Ограничение количества
        if limit:
            entries = entries[:limit]

        return entries

    async def clear_old(self, older_than: datetime) -> int:
        """
        Очистка старых логов.

        ARGS:
        - older_than: удалять логи старше этой даты

        RETURNS:
        - int: количество удалённых записей
        """
        async with self._lock:
            deleted_count = 0

            # Удаление старых файлов в all/
            all_dir = self.base_dir / 'all'
            if all_dir.exists():
                for file_path in all_dir.glob('logs_*.json'):
                    try:
                        date_str = file_path.stem.replace('logs_', '')
                        file_date = datetime.strptime(date_str, '%Y-%m-%d')

                        if file_date < older_than:
                            # Подсчёт записей перед удалением
                            data = self._load_json_file(file_path)
                            deleted_count += len(data)
                            file_path.unlink()
                    except (ValueError, OSError):
                        continue

            # Очистка старых записей в файлах by_agent и by_capability
            for pattern in ['by_agent/**/*.json', 'by_capability/**/*.json']:
                for file_path in self.base_dir.glob(pattern):
                    data = self._load_json_file(file_path)
                    original_count = len(data)

                    # Фильтрация старых записей
                    filtered_data = []
                    for item in data:
                        try:
                            timestamp = datetime.fromisoformat(item.get('timestamp', ''))
                            if timestamp >= older_than:
                                filtered_data.append(item)
                            else:
                                deleted_count += 1
                        except (ValueError, TypeError):
                            filtered_data.append(item)

                    # Сохранение отфильтрованных данных
                    if len(filtered_data) != original_count:
                        self._save_json_file(file_path, filtered_data)

            return deleted_count

    async def get_all_logs(
        self,
        date: datetime = None,
        limit: Optional[int] = None
    ) -> List[LogEntry]:
        """
        Получение всех логов за день.

        ARGS:
        - date: дата для получения (по умолчанию сегодня)
        - limit: максимальное количество записей (опционально)

        RETURNS:
        - List[LogEntry]: список записей лога
        """
        if date is None:
            date = datetime.now()

        file_path = self._get_all_logs_file(date)
        entries = await self._load_items(file_path)

        # Сортировка по времени
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        # Ограничение количества
        if limit:
            entries = entries[:limit]

        return entries

    async def get_agents(self) -> List[str]:
        """
        Получение списка всех агентов.

        RETURNS:
        - List[str]: список идентификаторов агентов
        """
        agents = []
        by_agent_dir = self.base_dir / 'by_agent'

        if by_agent_dir.exists():
            for item in by_agent_dir.iterdir():
                if item.is_dir():
                    agents.append(item.name.replace('_', '/'))

        return agents

    async def get_sessions(self, agent_id: str) -> List[str]:
        """
        Получение списка сессий для агента.

        ARGS:
        - agent_id: идентификатор агента

        RETURNS:
        - List[str]: список идентификаторов сессий
        """
        sessions = []
        safe_agent_id = agent_id.replace('/', '_')
        agent_dir = self.base_dir / 'by_agent' / safe_agent_id

        if agent_dir.exists():
            for item in agent_dir.iterdir():
                if item.is_dir():
                    sessions.append(item.name.replace('_', '/'))

        return sessions

    async def get_capabilities(self) -> List[str]:
        """
        Получение списка всех capability.

        RETURNS:
        - List[str]: список названий capability
        """
        capabilities = []
        by_cap_dir = self.base_dir / 'by_capability'

        if by_cap_dir.exists():
            for item in by_cap_dir.iterdir():
                if item.is_dir():
                    capabilities.append(item.name.replace('_', '/'))

        return capabilities
