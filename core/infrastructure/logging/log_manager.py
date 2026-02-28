"""
LogManager - единая точка управления системой логирования.

RESPONSIBILITIES:
- Роутинг логов по типам (агент, сессия, LLM, метрики)
- Создание symlink для быстрого доступа
- Координация с LogIndexer и LogRotator
- Инициализация структуры папок
"""
import os
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from core.infrastructure.logging.log_config import (
    LoggingConfig,
    LogFormat,
    get_logging_config,
    configure_logging
)


logger = logging.getLogger(__name__)


class LogManager:
    """
    Единая точка управления системой логирования.
    
    FEATURES:
    - Централизованное управление логами
    - Автоматическое создание структуры папок
    - Symlink для быстрого доступа
    - Координация с индексацией и ротацией
    
    USAGE:
        log_manager = LogManager()
        await log_manager.initialize()
        
        # Запись логов агента
        log_manager.log_agent("Agent started", level="INFO")
        
        # Запись логов сессии
        log_manager.log_session(session_id, {"event": "started"})
        
        # Запись LLM логов
        log_manager.log_llm(session_id, {"prompt": "...", "response": "..."})
    """
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Инициализация LogManager.
        
        ARGS:
            config: Конфигурация логирования (опционально)
        """
        self.config = config or get_logging_config()
        self._initialized = False
        
        # Кэши для активных файловых дескрипторов
        self._agent_file: Optional[Any] = None
        self._session_files: Dict[str, Any] = {}
        self._llm_files: Dict[str, Any] = {}
        
        # Ссылки на indexer и rotator
        self._indexer = None
        self._rotator = None
        
        # Блокировка для потокобезопасной записи
        self._lock = asyncio.Lock()
        
        # Настройка логгера
        self._setup_logger()
    
    def _setup_logger(self):
        """Настройка внутреннего логгера."""
        self._logger = logging.getLogger(f"koru.log_manager")
        self._logger.setLevel(getattr(logging, self.config.level))
    
    async def initialize(self) -> None:
        """
        Инициализация LogManager.
        
        Создаёт структуру папок:
        - logs/active/
        - logs/archive/YYYY/MM/
        - logs/indexed/
        - logs/config/
        """
        if self._initialized:
            logger.warning("LogManager уже инициализирован")
            return
        
        logger.info("Инициализация LogManager...")
        
        # Создание директорий
        dirs_to_create = [
            self.config.base_dir,
            self.config.active_dir,
            self.config.get_active_sessions_dir(),
            self.config.get_active_llm_dir(),
            self.config.indexed_dir,
            self.config.config_dir,
        ]
        
        # Создание директорий архива на текущий год/месяц
        now = datetime.now()
        archive_dirs = [
            self.config.archive_dir,
            self.config.archive_dir / str(now.year),
            self.config.archive_dir / str(now.year) / f"{now.month:02d}",
            self.config.get_archive_sessions_dir(now.year, now.month),
            self.config.get_archive_llm_dir(now.year, now.month),
        ]
        
        for dir_path in dirs_to_create + archive_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Создана директория: {dir_path}")
        
        # Создание symlink
        if self.config.symlinks.enabled:
            await self._create_symlinks()
        
        # Сохранение конфигурации
        self._save_config()
        
        self._initialized = True
        logger.info("LogManager успешно инициализирован")
    
    async def _create_symlinks(self) -> None:
        """
        Создание symlink для быстрого доступа.
        
        Создаёт:
        - logs/active/agent.log → ../archive/YYYY/MM/agent_YYYY-MM-DD.log
        - logs/active/sessions/latest.log → последняя сессия
        - logs/active/llm/latest.jsonl → последний LLM лог
        """
        try:
            # Symlink для agent.log
            agent_symlink = self.config.active_dir / "agent.log"
            agent_file = self._get_agent_log_path()
            
            if agent_symlink.exists() or agent_symlink.is_symlink():
                agent_symlink.unlink()
            
            if agent_file.exists():
                # На Windows создаём junction или копию
                if os.name == 'nt':
                    # Для Windows создаём ярлык или просто копию
                    agent_symlink.write_text(agent_file.read_text(encoding='utf-8'), encoding='utf-8')
                else:
                    agent_symlink.symlink_to(agent_file.relative_to(self.config.active_dir))
                logger.debug(f"Создан symlink: {agent_symlink} → {agent_file}")
            
            # Symlink для sessions/latest.log
            sessions_symlink = self.config.get_active_sessions_dir() / "latest.log"
            if sessions_symlink.exists() or sessions_symlink.is_symlink():
                sessions_symlink.unlink()
            
            # Symlink для llm/latest.jsonl
            llm_symlink = self.config.get_active_llm_dir() / "latest.jsonl"
            if llm_symlink.exists() or llm_symlink.is_symlink():
                llm_symlink.unlink()
            
        except Exception as e:
            logger.warning(f"Ошибка создания symlink: {e}")
    
    def _get_agent_log_path(self) -> Path:
        """Получение пути к текущему логу агента."""
        now = datetime.now()
        filename = f"agent_{now.strftime('%Y-%m-%d')}.log"
        return self.config.archive_dir / str(now.year) / f"{now.month:02d}" / filename
    
    def _get_session_log_path(self, session_id: str, timestamp: Optional[datetime] = None) -> Path:
        """Получение пути к логу сессии."""
        ts = timestamp or datetime.now()
        now = datetime.now()
        
        # Формирование имени файла
        filename = f"{ts.strftime('%Y-%m-%d_%H-%M-%S')}_session_{session_id}.log"
        
        return self.config.get_archive_sessions_dir(now.year, now.month) / filename
    
    def _get_llm_log_path(self, session_id: str, timestamp: Optional[datetime] = None) -> Path:
        """Получение пути к LLM логу."""
        ts = timestamp or datetime.now()
        now = datetime.now()
        
        # Формирование имени файла
        filename = f"{ts.strftime('%Y-%m-%d')}_session_{session_id}.jsonl"
        
        return self.config.get_archive_llm_dir(now.year, now.month) / filename
    
    def log_agent(self, message: str, level: str = "INFO", **kwargs) -> None:
        """
        Запись лога агента.
        
        ARGS:
            message: Сообщение лога
            level: Уровень логирования (INFO, DEBUG, WARNING, ERROR)
            **kwargs: Дополнительные поля
        """
        if not self._initialized:
            logger.warning("LogManager не инициализирован, пропуск лога")
            return
        
        timestamp = datetime.now().isoformat()
        log_level = level.upper()
        
        # Формирование строки лога
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        log_line = f"{timestamp} | {log_level:5} | koru.agent | {message}"
        if extra:
            log_line += f" | {extra}"
        log_line += "\n"
        
        # Запись в файл
        try:
            log_path = self._get_agent_log_path()
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_line)
        except Exception as e:
            logger.error(f"Ошибка записи лога агента: {e}")
    
    def log_session(self, session_id: str, event_data: Dict[str, Any]) -> None:
        """
        Запись лога сессии (JSONL формат).
        
        ARGS:
            session_id: ID сессии
            event_data: Данные события
        """
        if not self._initialized:
            logger.warning("LogManager не инициализирован, пропуск лога")
            return
        
        timestamp = datetime.now()
        event_data['timestamp'] = timestamp.isoformat() + 'Z'
        
        # Формирование JSONL строки
        import json
        log_line = json.dumps(event_data, ensure_ascii=False, default=str) + '\n'
        
        # Запись в файл
        try:
            log_path = self._get_session_log_path(session_id, timestamp)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_line)
            
            # Обновление symlink
            if self.config.symlinks.enabled and self.config.symlinks.latest_session:
                self._update_session_symlink(session_id, log_path)
            
        except Exception as e:
            logger.error(f"Ошибка записи лога сессии: {e}")
    
    def _update_session_symlink(self, session_id: str, log_path: Path) -> None:
        """Обновление symlink на последнюю сессию."""
        try:
            symlink_path = self.config.get_active_sessions_dir() / "latest.log"
            
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()
            
            # На Windows создаём копию содержимого
            if os.name == 'nt':
                # Копируем последние N строк
                with open(log_path, 'r', encoding='utf-8') as src:
                    lines = src.readlines()[-100:]  # Последние 100 строк
                with open(symlink_path, 'w', encoding='utf-8') as dst:
                    dst.writelines(lines)
            else:
                symlink_path.symlink_to(log_path.relative_to(self.config.active_dir))
                
        except Exception as e:
            logger.debug(f"Ошибка обновления symlink сессии: {e}")
    
    def log_llm(self, session_id: str, event_data: Dict[str, Any]) -> None:
        """
        Запись LLM лога (JSONL формат).
        
        ARGS:
            session_id: ID сессии
            event_data: Данные события (prompt/response)
        """
        if not self._initialized:
            logger.warning("LogManager не инициализирован, пропуск лога")
            return
        
        timestamp = datetime.now()
        event_data['timestamp'] = timestamp.isoformat() + 'Z'
        event_data['type'] = event_data.get('type', 'llm_event')
        
        # Формирование JSONL строки
        import json
        log_line = json.dumps(event_data, ensure_ascii=False, default=str) + '\n'
        
        # Запись в файл
        try:
            log_path = self._get_llm_log_path(session_id, timestamp)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_line)
            
            # Обновление symlink
            if self.config.symlinks.enabled and self.config.symlinks.latest_llm:
                self._update_llm_symlink(log_path)
            
        except Exception as e:
            logger.error(f"Ошибка записи LLM лога: {e}")
    
    def _update_llm_symlink(self, log_path: Path) -> None:
        """Обновление symlink на последний LLM лог."""
        try:
            symlink_path = self.config.get_active_llm_dir() / "latest.jsonl"
            
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()
            
            # На Windows создаём копию содержимого
            if os.name == 'nt':
                with open(log_path, 'r', encoding='utf-8') as src:
                    lines = src.readlines()[-50:]  # Последние 50 строк
                with open(symlink_path, 'w', encoding='utf-8') as dst:
                    dst.writelines(lines)
            else:
                symlink_path.symlink_to(log_path.relative_to(self.config.active_dir))
                
        except Exception as e:
            logger.debug(f"Ошибка обновления symlink LLM: {e}")
    
    def log_metrics(self, capability: str, metrics_data: Dict[str, Any]) -> None:
        """
        Запись метрик (JSONL формат).
        
        ARGS:
            capability: Название способности
            metrics_data: Данные метрик
        """
        if not self._initialized:
            logger.warning("LogManager не инициализирован, пропуск лога")
            return
        
        timestamp = datetime.now()
        now = datetime.now()
        
        metrics_data['timestamp'] = timestamp.isoformat() + 'Z'
        metrics_data['capability'] = capability
        
        # Формирование JSONL строки
        import json
        log_line = json.dumps(metrics_data, ensure_ascii=False, default=str) + '\n'
        
        # Запись в файл
        try:
            filename = f"{timestamp.strftime('%Y-%m-%d')}_{capability.replace('/', '_')}.metrics.jsonl"
            log_path = self.config.archive_dir / str(now.year) / f"{now.month:02d}" / filename
            
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_line)
                
        except Exception as e:
            logger.error(f"Ошибка записи метрик: {e}")
    
    def _save_config(self) -> None:
        """Сохранение конфигурации в logs/config/."""
        try:
            from core.infrastructure.logging.log_config import save_config_to_yaml

            config_path = self.config.config_dir / "logging_config.yaml"
            save_config_to_yaml(self.config, str(config_path))
            logger.debug(f"Конфигурация сохранена: {config_path}")
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    def set_indexer(self, indexer) -> None:
        """Установка LogIndexer для координации."""
        self._indexer = indexer
    
    def set_rotator(self, rotator) -> None:
        """Установка LogRotator для координации."""
        self._rotator = rotator
    
    async def flush(self) -> None:
        """Сброс буферов на диск."""
        async with self._lock:
            # Закрытие и переоткрытие файлов для сброса буферов
            pass  # Для текущей реализации не требуется
    
    async def shutdown(self) -> None:
        """Завершение работы LogManager."""
        logger.info("Завершение работы LogManager...")
        
        await self.flush()
        
        # Закрытие файлов
        self._agent_file = None
        self._session_files.clear()
        self._llm_files.clear()
        
        self._initialized = False
        logger.info("LogManager завершил работу")
    
    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации."""
        return self._initialized
    
    def get_session_log_path(self, session_id: str) -> Optional[Path]:
        """
        Получение пути к логу сессии.
        
        ARGS:
            session_id: ID сессии
            
        RETURNS:
            Path к файлу или None если не найден
        """
        # Поиск в архиве
        now = datetime.now()
        sessions_dir = self.config.get_archive_sessions_dir(now.year, now.month)
        
        # Поиск файла по session_id
        for log_file in sessions_dir.glob(f"*_session_{session_id}.log"):
            return log_file
        
        return None
    
    def get_llm_log_path(self, session_id: str) -> Optional[Path]:
        """
        Получение пути к LLM логу сессии.
        
        ARGS:
            session_id: ID сессии
            
        RETURNS:
            Path к файлу или None если не найден
        """
        now = datetime.now()
        llm_dir = self.config.get_archive_llm_dir(now.year, now.month)
        
        for log_file in llm_dir.glob(f"*_session_{session_id}.jsonl"):
            return log_file
        
        return None


# Глобальный экземпляр
_log_manager: Optional[LogManager] = None


def get_log_manager() -> LogManager:
    """Получение глобального LogManager."""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager


async def init_log_manager(config: Optional[LoggingConfig] = None) -> LogManager:
    """
    Инициализация глобального LogManager.
    
    ARGS:
        config: Конфигурация (опционально)
        
    RETURNS:
        LogManager: Инициализированный менеджер
    """
    global _log_manager
    _log_manager = LogManager(config)
    await _log_manager.initialize()
    return _log_manager
