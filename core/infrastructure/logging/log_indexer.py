"""
LogIndexer - индексация логов для быстрого поиска.

FEATURES:
- Индексация сессий по session_id
- Индексация агентов по agent_id
- Быстрый поиск последних логов
- Автоматическое обновление индекса

STRUCTURE:
logs/indexed/
├── sessions_index.jsonl       ← {session_id, timestamp, path, agent_id, goal}
└── agents_index.jsonl         ← {agent_id, session_ids[], last_session_timestamp}
"""
import os
import json
import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any, Set
from dataclasses import dataclass, asdict

from core.infrastructure.logging.log_config_new import LoggingConfig, get_logging_config


logger = logging.getLogger(__name__)


@dataclass
class SessionIndexEntry:
    """Запись индекса сессии."""
    session_id: str
    timestamp: str  # ISO формат
    path: str
    agent_id: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[str] = None  # started, completed, failed
    steps: Optional[int] = None
    total_time_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionIndexEntry':
        return cls(**data)


@dataclass
class AgentIndexEntry:
    """Запись индекса агента."""
    agent_id: str
    session_ids: List[str]
    first_session: Optional[str] = None
    last_session: Optional[str] = None
    total_sessions: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentIndexEntry':
        return cls(**data)


class LogIndexer:
    """
    Индексатор логов для быстрого поиска.
    
    FEATURES:
    - Сканирование архива логов
    - Извлечение метаданных из файлов
    - Построение индексов sessions и agents
    - Периодическое обновление
    
    USAGE:
        indexer = LogIndexer()
        await indexer.initialize()
        
        # Поиск последней сессии
        last_session = await indexer.get_latest_session()
        
        # Поиск сессии по ID
        session = await indexer.find_session(session_id)
        
        # Поиск всех сессий агента
        sessions = await indexer.get_agent_sessions(agent_id)
    """
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Инициализация LogIndexer.
        
        ARGS:
            config: Конфигурация логирования
        """
        self.config = config or get_logging_config()
        self._initialized = False
        
        # Кэши индексов
        self._sessions_index: Dict[str, SessionIndexEntry] = {}
        self._agents_index: Dict[str, AgentIndexEntry] = {}
        
        # Блокировка для потокобезопасности
        self._lock = asyncio.Lock()
        
        # Задача фонового обновления
        self._background_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """
        Инициализация индексатора.
        
        - Загрузка существующих индексов
        - Сканирование архива
        - Запуск фонового обновления
        """
        if self._initialized:
            logger.warning("LogIndexer уже инициализирован")
            return
        
        logger.info("Инициализация LogIndexer...")
        
        # Создание директории индексов
        self.config.indexed_dir.mkdir(parents=True, exist_ok=True)
        
        # Загрузка существующих индексов
        await self._load_indexes()
        
        # Сканирование архива
        await self._scan_archive()
        
        # Сохранение индексов
        await self._save_indexes()
        
        # Запуск фонового обновления
        if self.config.indexing.enabled:
            await self._start_background_update()
        
        self._initialized = True
        logger.info(f"LogIndexer инициализирован ({len(self._sessions_index)} сессий, {len(self._agents_index)} агентов)")
    
    async def _load_indexes(self) -> None:
        """Загрузка существующих индексов."""
        # Загрузка sessions_index.jsonl
        sessions_path = self.config.get_sessions_index_path()
        if sessions_path.exists():
            try:
                with open(sessions_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            data = json.loads(line)
                            entry = SessionIndexEntry.from_dict(data)
                            self._sessions_index[entry.session_id] = entry
                logger.debug(f"Загружено {len(self._sessions_index)} записей сессий")
            except Exception as e:
                logger.error(f"Ошибка загрузки sessions_index: {e}")
        
        # Загрузка agents_index.jsonl
        agents_path = self.config.get_agents_index_path()
        if agents_path.exists():
            try:
                with open(agents_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            data = json.loads(line)
                            entry = AgentIndexEntry.from_dict(data)
                            self._agents_index[entry.agent_id] = entry
                logger.debug(f"Загружено {len(self._agents_index)} записей агентов")
            except Exception as e:
                logger.error(f"Ошибка загрузки agents_index: {e}")
    
    async def _save_indexes(self) -> None:
        """Сохранение индексов."""
        async with self._lock:
            # Сохранение sessions_index.jsonl
            sessions_path = self.config.get_sessions_index_path()
            with open(sessions_path, 'w', encoding='utf-8') as f:
                for entry in self._sessions_index.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')
            
            # Сохранение agents_index.jsonl
            agents_path = self.config.get_agents_index_path()
            with open(agents_path, 'w', encoding='utf-8') as f:
                for entry in self._agents_index.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')
            
            logger.debug(f"Сохранено индексов: {len(self._sessions_index)} сессий, {len(self._agents_index)} агентов")
    
    async def _scan_archive(self) -> None:
        """Сканирование архива логов для обновления индексов."""
        if not self.config.archive_dir.exists():
            return
        
        # Поиск всех файлов сессий
        sessions_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_session_([a-f0-9-]+)\.log')
        
        for year_dir in self.config.archive_dir.iterdir():
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue
                
                sessions_dir = month_dir / "sessions"
                if not sessions_dir.exists():
                    continue
                
                for log_file in sessions_dir.glob("*.log"):
                    match = sessions_pattern.match(log_file.name)
                    if match:
                        timestamp_str = match.group(1)
                        session_id = match.group(2)
                        
                        # Если сессия уже в индексе, пропускаем
                        if session_id in self._sessions_index:
                            continue
                        
                        # Извлечение метаданных из файла
                        metadata = await self._extract_metadata(log_file)
                        
                        # Создание записи индекса
                        entry = SessionIndexEntry(
                            session_id=session_id,
                            timestamp=timestamp_str.replace('_', 'T') + '.000Z',
                            path=str(log_file),
                            agent_id=metadata.get('agent_id'),
                            goal=metadata.get('goal'),
                            status=metadata.get('status'),
                            steps=metadata.get('steps'),
                            total_time_ms=metadata.get('total_time_ms'),
                        )
                        
                        self._sessions_index[session_id] = entry
                        
                        # Обновление индекса агента
                        if entry.agent_id:
                            await self._update_agent_index(entry.agent_id, session_id, entry.timestamp)
        
        logger.debug(f"Отсканировано архивов: {len(self._sessions_index)} сессий найдено")
    
    async def _extract_metadata(self, log_file: Path) -> Dict[str, Any]:
        """
        Извлечение метаданных из файла сессии.
        
        ARGS:
            log_file: Путь к файлу сессии
            
        RETURNS:
            Dict с метаданными (agent_id, goal, status, etc.)
        """
        metadata = {}
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                for line in lines[:100]:  # Читаем первые 100 строк
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        if data.get('type') == 'session_started':
                            metadata['agent_id'] = data.get('agent_id')
                            metadata['goal'] = data.get('goal')
                            metadata['status'] = 'started'
                        
                        elif data.get('type') == 'session_completed':
                            metadata['status'] = 'completed'
                            metadata['steps'] = data.get('steps')
                            metadata['total_time_ms'] = data.get('total_time_ms')
                        
                        elif data.get('type') == 'session_failed':
                            metadata['status'] = 'failed'
                        
                        # Если нашли и start и complete, прекращаем
                        if metadata.get('agent_id') and metadata.get('status') in ('completed', 'failed'):
                            break
                            
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.debug(f"Ошибка извлечения метаданных из {log_file}: {e}")
        
        return metadata
    
    async def _update_agent_index(self, agent_id: str, session_id: str, timestamp: str) -> None:
        """
        Обновление индекса агента.
        
        ARGS:
            agent_id: ID агента
            session_id: ID сессии
            timestamp: Временная метка сессии
        """
        if agent_id not in self._agents_index:
            self._agents_index[agent_id] = AgentIndexEntry(
                agent_id=agent_id,
                session_ids=[],
                first_session=timestamp,
                last_session=timestamp,
                total_sessions=0,
            )
        
        entry = self._agents_index[agent_id]
        
        if session_id not in entry.session_ids:
            entry.session_ids.append(session_id)
            entry.total_sessions = len(entry.session_ids)
            
            # Обновление временных меток
            if timestamp < (entry.first_session or ''):
                entry.first_session = timestamp
            if timestamp > (entry.last_session or ''):
                entry.last_session = timestamp
    
    async def _start_background_update(self) -> None:
        """Запуск фонового обновления индекса."""
        self._stop_event.clear()
        self._background_task = asyncio.create_task(self._background_update_loop())
        logger.debug(f"Запущено фоновое обновление индекса (интервал: {self.config.indexing.update_interval_sec}с)")
    
    async def _background_update_loop(self) -> None:
        """Фоновый цикл обновления индекса."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.config.indexing.update_interval_sec)
                await self._scan_archive()
                await self._save_indexes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка фонового обновления индекса: {e}")
    
    async def add_session(self, session_id: str, agent_id: Optional[str] = None, 
                          goal: Optional[str] = None) -> None:
        """
        Добавление сессии в индекс.
        
        ARGS:
            session_id: ID сессии
            agent_id: ID агента (опционально)
            goal: Цель сессии (опционально)
        """
        async with self._lock:
            timestamp = datetime.now().isoformat() + 'Z'
            log_path = self._get_session_log_path(session_id)
            
            entry = SessionIndexEntry(
                session_id=session_id,
                timestamp=timestamp,
                path=str(log_path) if log_path else '',
                agent_id=agent_id,
                goal=goal,
                status='started',
            )
            
            self._sessions_index[session_id] = entry
            
            if agent_id:
                await self._update_agent_index(agent_id, session_id, timestamp)
            
            # Сохранение индекса
            await self._save_indexes()
    
    async def update_session_status(self, session_id: str, status: str,
                                     steps: Optional[int] = None,
                                     total_time_ms: Optional[int] = None) -> None:
        """
        Обновление статуса сессии.
        
        ARGS:
            session_id: ID сессии
            status: Статус (completed, failed)
            steps: Количество шагов
            total_time_ms: Общее время в мс
        """
        async with self._lock:
            if session_id in self._sessions_index:
                entry = self._sessions_index[session_id]
                entry.status = status
                entry.steps = steps
                entry.total_time_ms = total_time_ms
                
                await self._save_indexes()
    
    def _get_session_log_path(self, session_id: str) -> Optional[Path]:
        """Получение пути к файлу сессии."""
        now = datetime.now()
        sessions_dir = self.config.get_archive_sessions_dir(now.year, now.month)
        
        # Поиск файла
        for log_file in sessions_dir.glob(f"*_session_{session_id}.log"):
            return log_file
        
        return None
    
    async def get_latest_session(self) -> Optional[SessionIndexEntry]:
        """
        Получение последней сессии.
        
        RETURNS:
            SessionIndexEntry или None
        """
        if not self._sessions_index:
            return None
        
        # Сортировка по timestamp
        sorted_sessions = sorted(
            self._sessions_index.values(),
            key=lambda x: x.timestamp,
            reverse=True
        )
        
        return sorted_sessions[0] if sorted_sessions else None
    
    async def find_session(self, session_id: str) -> Optional[SessionIndexEntry]:
        """
        Поиск сессии по ID.
        
        ARGS:
            session_id: ID сессии
            
        RETURNS:
            SessionIndexEntry или None
        """
        return self._sessions_index.get(session_id)
    
    async def get_agent_sessions(self, agent_id: str, 
                                  limit: Optional[int] = None) -> List[SessionIndexEntry]:
        """
        Получение всех сессий агента.
        
        ARGS:
            agent_id: ID агента
            limit: Максимальное количество сессий
            
        RETURNS:
            Список SessionIndexEntry
        """
        if agent_id not in self._agents_index:
            return []
        
        agent_entry = self._agents_index[agent_id]
        sessions = []
        
        for session_id in agent_entry.session_ids:
            if session_id in self._sessions_index:
                sessions.append(self._sessions_index[session_id])
        
        # Сортировка по timestamp (новые первые)
        sessions.sort(key=lambda x: x.timestamp, reverse=True)
        
        if limit:
            sessions = sessions[:limit]
        
        return sessions
    
    async def get_agents(self) -> List[AgentIndexEntry]:
        """
        Получение списка всех агентов.
        
        RETURNS:
            Список AgentIndexEntry
        """
        return list(self._agents_index.values())
    
    async def search_sessions(self, goal_pattern: Optional[str] = None,
                               status: Optional[str] = None,
                               date_from: Optional[datetime] = None,
                               date_to: Optional[datetime] = None,
                               limit: Optional[int] = None) -> List[SessionIndexEntry]:
        """
        Поиск сессий по фильтрам.
        
        ARGS:
            goal_pattern: Паттерн для поиска в goal
            status: Фильтр по статусу
            date_from: Дата от
            date_to: Дата до
            limit: Максимальное количество результатов
            
        RETURNS:
            Список SessionIndexEntry
        """
        results = []
        
        for entry in self._sessions_index.values():
            # Фильтр по статусу
            if status and entry.status != status:
                continue
            
            # Фильтр по goal
            if goal_pattern and entry.goal:
                if goal_pattern.lower() not in entry.goal.lower():
                    continue
            
            # Фильтр по дате
            if date_from or date_to:
                try:
                    entry_date = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                    if date_from and entry_date < date_from:
                        continue
                    if date_to and entry_date > date_to:
                        continue
                except (ValueError, TypeError):
                    continue
            
            results.append(entry)
        
        # Сортировка по timestamp (новые первые)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        if limit:
            results = results[:limit]
        
        return results
    
    async def rebuild_index(self) -> int:
        """
        Перестроение индекса с нуля.
        
        RETURNS:
            Количество проиндексированных сессий
        """
        logger.info("Перестроение индекса...")
        
        # Очистка кэшей
        self._sessions_index.clear()
        self._agents_index.clear()
        
        # Сканирование архива
        await self._scan_archive()
        
        # Сохранение
        await self._save_indexes()
        
        logger.info(f"Индекс перестроен: {len(self._sessions_index)} сессий")
        return len(self._sessions_index)
    
    async def shutdown(self) -> None:
        """Завершение работы индексатора."""
        logger.info("Завершение работы LogIndexer...")
        
        # Остановка фонового обновления
        self._stop_event.set()
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        
        # Сохранение индексов
        await self._save_indexes()
        
        self._initialized = False
        logger.info("LogIndexer завершил работу")
    
    @property
    def sessions_count(self) -> int:
        """Количество проиндексированных сессий."""
        return len(self._sessions_index)
    
    @property
    def agents_count(self) -> int:
        """Количество проиндексированных агентов."""
        return len(self._agents_index)


# Глобальный экземпляр
_indexer: Optional[LogIndexer] = None


def get_log_indexer() -> LogIndexer:
    """Получение глобального LogIndexer."""
    global _indexer
    if _indexer is None:
        _indexer = LogIndexer()
    return _indexer


async def init_log_indexer(config: Optional[LoggingConfig] = None) -> LogIndexer:
    """
    Инициализация глобального LogIndexer.
    
    ARGS:
        config: Конфигурация
        
    RETURNS:
        LogIndexer: Инициализированный индексатор
    """
    global _indexer
    _indexer = LogIndexer(config)
    await _indexer.initialize()
    return _indexer
