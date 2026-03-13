"""
LogSearch - поиск по логам с использованием индексов.

FEATURES:
- Быстрый поиск сессий по ID
- Поиск по agent_id
- Поиск по содержимому логов
- Поиск последних LLM вызовов
- Экспорт результатов

USAGE:
    from core.infrastructure.logging.log_search import LogSearch
    
    search = LogSearch()
    await search.initialize()
    
    # Найти последнюю сессию
    session = await search.get_latest_session()
    
    # Найти сессию по ID
    session = await search.find_session(session_id)
    
    # Найти все LLM вызовы сессии
    llm_calls = await search.get_session_llm_calls(session_id)
"""
import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator, AsyncIterator

from core.config.logging_config import LoggingConfig, get_logging_config
from core.infrastructure.logging.log_indexer import LogIndexer, SessionIndexEntry, get_log_indexer


def _debug(msg: str) -> None:
    """Отладочный вывод (не через logging)."""
    if os.environ.get("KORU_DEBUG"):
        print(f"[LogSearch DEBUG] {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    """Информационный вывод (не через logging)."""
    print(f"[LogSearch] {msg}", file=sys.stderr)


def _error(msg: str) -> None:
    """Вывод ошибок (не через logging)."""
    print(f"[LogSearch ERROR] {msg}", file=sys.stderr)


def _warning(msg: str) -> None:
    """Вывод предупреждений (не через logging)."""
    print(f"[LogSearch WARNING] {msg}", file=sys.stderr)


class LogSearch:
    """
    Поиск по логам с использованием индексов.
    
    FEATURES:
    - Поиск по индексам (быстро)
    - Полнотекстовый поиск по файлам (медленно)
    - Поиск LLM вызовов
    - Агрегация результатов
    
    USAGE:
        search = LogSearch()
        await search.initialize()
        
        # Поиск сессии
        session = await search.find_session("abc123")
        
        # Поиск по goal
        sessions = await search.search_by_goal("книги")
        
        # Экспорт сессии
        export = await search.export_session("abc123")
    """
    
    def __init__(self, config: Optional[LoggingConfig] = None, indexer: Optional[LogIndexer] = None):
        """
        Инициализация LogSearch.
        
        ARGS:
            config: Конфигурация логирования
            indexer: Индексатор (опционально)
        """
        self.config = config or get_logging_config()
        self._indexer = indexer
        self._initialized = False
    
    async def initialize(self) -> None:
        """Инициализация поиска."""
        if self._initialized:
            _error("LogSearch уже инициализирован")
            return

        # Инициализация индексатора если не передан
        if self._indexer is None:
            self._indexer = get_log_indexer()
            if not self._indexer.is_initialized:
                await self._indexer.initialize()

        self._initialized = True
        _info("LogSearch инициализирован")
    
    async def get_latest_session(self) -> Optional[SessionIndexEntry]:
        """
        Получение последней сессии.

        RETURNS:
            SessionIndexEntry или None
        """
        if not self._initialized:
            _error("LogSearch не инициализирован")
            return None

        return await self._indexer.get_latest_session()

    async def find_session(self, session_id: str) -> Optional[SessionIndexEntry]:
        """
        Поиск сессии по ID.

        ARGS:
            session_id: ID сессии

        RETURNS:
            SessionIndexEntry или None
        """
        if not self._initialized:
            _error("LogSearch не инициализирован")
            return None

        return await self._indexer.find_session(session_id)

    async def get_session_logs(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Получение всех логов сессии.

        ARGS:
            session_id: ID сессии

        RETURNS:
            Список записей лога или None
        """
        if not self._initialized:
            _error("LogSearch не инициализирован")
            return None
        
        # Поиск файла сессии
        session_entry = await self._indexer.find_session(session_id)
        
        if not session_entry:
            # Попытка найти файл напрямую
            file_path = self._find_session_file(session_id)
            if not file_path:
                return None
        else:
            file_path = Path(session_entry.path)
        
        if not file_path.exists():
            return None
        
        # Чтение файла
        logs = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        logs.append(data)
                    except json.JSONDecodeError:
                        # Текстовый формат
                        logs.append({'raw': line})

            return logs

        except Exception as e:
            _error(f"Ошибка чтения логов сессии {session_id}: {e}")
            return None
    
    def _find_session_file(self, session_id: str) -> Optional[Path]:
        """
        Поиск файла сессии по ID.
        
        ARGS:
            session_id: ID сессии
            
        RETURNS:
            Path к файлу или None
        """
        # Поиск в текущем месяце
        now = datetime.now()
        sessions_dir = self.config.get_archive_sessions_dir(now.year, now.month)
        
        # Поиск по паттерну
        pattern = f"*_session_{session_id}.log"
        for file_path in sessions_dir.glob(pattern):
            return file_path
        
        # Поиск во всех месяцах
        if self.config.archive_dir.exists():
            for file_path in self.config.archive_dir.rglob(pattern):
                return file_path
        
        return None
    
    async def get_session_llm_calls(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Получение всех LLM вызовов сессии.
        
        ARGS:
            session_id: ID сессии
            
        RETURNS:
            Список LLM вызовов
        """
        if not self._initialized:
            _error("LogSearch не инициализирован")
            return []
        
        # Поиск файла LLM логов
        now = datetime.now()
        llm_dir = self.config.get_archive_llm_dir(now.year, now.month)
        
        pattern = f"*_session_{session_id}.jsonl"
        llm_file = None
        
        for file_path in llm_dir.glob(pattern):
            llm_file = file_path
            break
        
        if not llm_file:
            # Поиск во всех месяцах
            for file_path in self.config.archive_dir.rglob(pattern):
                llm_file = file_path
                break
        
        if not llm_file or not llm_file.exists():
            return []
        
        # Чтение файла
        calls = []
        try:
            with open(llm_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        if data.get('type') in ('llm_prompt', 'llm_response', 'llm_event'):
                            calls.append(data)
                    except json.JSONDecodeError:
                        continue

            return calls

        except Exception as e:
            _error(f"Ошибка чтения LLM логов сессии {session_id}: {e}")
            return []
    
    async def get_last_llm_call(self, session_id: str, 
                                 phase: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Получение последнего LLM вызова сессии.
        
        ARGS:
            session_id: ID сессии
            phase: Фильтр по фазе (think/act/observe)
            
        RETURNS:
            Данные LLM вызова или None
        """
        calls = await self.get_session_llm_calls(session_id)
        
        if not calls:
            return None
        
        # Фильтрация по phase
        if phase:
            calls = [c for c in calls if c.get('phase') == phase]
        
        if not calls:
            return None
        
        # Возврат последнего
        return calls[-1]
    
    async def search_by_goal(self, goal_pattern: str, 
                              limit: Optional[int] = None) -> List[SessionIndexEntry]:
        """
        Поиск сессий по паттерну в goal.

        ARGS:
            goal_pattern: Паттерн для поиска
            limit: Максимальное количество результатов

        RETURNS:
            Список SessionIndexEntry
        """
        if not self._initialized:
            _error("LogSearch не инициализирован")
            return []

        return await self._indexer.search_sessions(goal_pattern=goal_pattern, limit=limit)

    async def search_by_agent(self, agent_id: str,
                               limit: Optional[int] = None) -> List[SessionIndexEntry]:
        """
        Поиск всех сессий агента.

        ARGS:
            agent_id: ID агента
            limit: Максимальное количество результатов

        RETURNS:
            Список SessionIndexEntry
        """
        if not self._initialized:
            _error("LogSearch не инициализирован")
            return []

        return await self._indexer.get_agent_sessions(agent_id, limit)

    async def search_by_status(self, status: str,
                                limit: Optional[int] = None) -> List[SessionIndexEntry]:
        """
        Поиск сессий по статусу.

        ARGS:
            status: Статус (started, completed, failed)
            limit: Максимальное количество результатов

        RETURNS:
            Список SessionIndexEntry
        """
        if not self._initialized:
            _error("LogSearch не инициализирован")
            return []

        return await self._indexer.search_sessions(status=status, limit=limit)
    
    async def search_by_date_range(self, date_from: datetime,
                                    date_to: datetime,
                                    limit: Optional[int] = None) -> List[SessionIndexEntry]:
        """
        Поиск сессий по диапазону дат.
        
        ARGS:
            date_from: Дата от
            date_to: Дата до
            limit: Максимальное количество результатов

        RETURNS:
            Список SessionIndexEntry
        """
        if not self._initialized:
            _error("LogSearch не инициализирован")
            return []

        return await self._indexer.search_sessions(
            date_from=date_from,
            date_to=date_to,
            limit=limit
        )
    
    async def search_in_logs(self, session_id: str, 
                              pattern: str,
                              case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Полнотекстовый поиск в логах сессии.
        
        ARGS:
            session_id: ID сессии
            pattern: Паттерн для поиска (regex)
            case_sensitive: Учитывать регистр
            
        RETURNS:
            Список совпадений
        """
        logs = await self.get_session_logs(session_id)
        
        if not logs:
            return []
        
        # Компиляция regex
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            _error(f"Неверный regex паттерн: {e}")
            return []
        
        # Поиск совпадений
        matches = []
        for log_entry in logs:
            raw = log_entry.get('raw', str(log_entry))
            
            if regex.search(raw):
                matches.append({
                    'log': log_entry,
                    'match': regex.findall(raw),
                })
        
        return matches
    
    async def export_session(self, session_id: str, 
                              output_path: Optional[str] = None,
                              format: str = 'json') -> Optional[str]:
        """
        Экспорт сессии в файл.
        
        ARGS:
            session_id: ID сессии
            output_path: Путь для экспорта (опционально)
            format: Формат экспорта (json, text)
            
        RETURNS:
            Путь к файлу экспорта или None
        """
        logs = await self.get_session_logs(session_id)
        
        if not logs:
            _warning(f"Сессия {session_id} не найдена")
            return None
        
        # Генерация пути
        if output_path:
            export_path = Path(output_path)
        else:
            export_path = Path(f"session_{session_id}_export.json")
        
        try:
            if format == 'json':
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, ensure_ascii=False, indent=2, default=str)
            
            elif format == 'text':
                with open(export_path, 'w', encoding='utf-8') as f:
                    for log_entry in logs:
                        if 'raw' in log_entry:
                            f.write(log_entry['raw'] + '\n')
                        else:
                            f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + '\n')
            
            else:
                _error(f"Неизвестный формат экспорта: {format}")
                return None

            _info(f"Сессия экспортирована: {export_path}")
            return str(export_path)

        except Exception as e:
            _error(f"Ошибка экспорта сессии: {e}")
            return None
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики поиска.
        
        RETURNS:
            Dict со статистикой
        """
        if not self._initialized:
            return {}
        
        return {
            'sessions_indexed': self._indexer.sessions_count,
            'agents_indexed': self._indexer.agents_count,
        }
    
    async def shutdown(self) -> None:
        """Завершение работы поиска."""
        _info("Завершение работы LogSearch...")
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации."""
        return self._initialized


# Глобальный экземпляр
_search: Optional[LogSearch] = None


def get_log_search() -> LogSearch:
    """Получение глобального LogSearch."""
    global _search
    if _search is None:
        _search = LogSearch()
    return _search


async def init_log_search(config: Optional[LoggingConfig] = None,
                           indexer: Optional[LogIndexer] = None) -> LogSearch:
    """
    Инициализация глобального LogSearch.
    
    ARGS:
        config: Конфигурация
        indexer: Индексатор (опционально)
        
    RETURNS:
        LogSearch: Инициализированный поиск
    """
    global _search
    _search = LogSearch(config, indexer)
    await _search.initialize()
    return _search


# ============================================================================
# УТИЛИТЫ ДЛЯ БЫСТРОГО ДОСТУПА
# ============================================================================

async def get_latest_session() -> Optional[SessionIndexEntry]:
    """Быстрое получение последней сессии."""
    search = get_log_search()
    if not search.is_initialized:
        await search.initialize()
    return await search.get_latest_session()


async def find_session(session_id: str) -> Optional[SessionIndexEntry]:
    """Быстрый поиск сессии по ID."""
    search = get_log_search()
    if not search.is_initialized:
        await search.initialize()
    return await search.find_session(session_id)


async def get_session_llm_calls(session_id: str) -> List[Dict[str, Any]]:
    """Быстрое получение LLM вызовов сессии."""
    search = get_log_search()
    if not search.is_initialized:
        await search.initialize()
    return await search.get_session_llm_calls(session_id)


async def get_last_llm_call(session_id: str, 
                             phase: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Быстрое получение последнего LLM вызова."""
    search = get_log_search()
    if not search.is_initialized:
        await search.initialize()
    return await search.get_last_llm_call(session_id, phase)
