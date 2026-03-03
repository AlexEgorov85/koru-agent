"""
Менеджер динамической конфигурации с hot-reload.

АРХИТЕКТУРА:
- Наблюдение за файлами конфигурации
- Автоматическая перезагрузка при изменениях
- Callback-и для уведомления об изменениях
- Валидация новой конфигурации перед применением
- Откат к предыдущей конфигурации при ошибках

ПРЕИМУЩЕСТВА:
- ✅ Изменение конфигурации без перезапуска
- ✅ A/B тестирование конфигураций
- ✅ Динамическое переключение профилей
- ✅ Аудит изменений конфигурации
- ✅ Безопасное применение изменений
"""
import asyncio
import inspect
import os
import shutil
import time
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from core.config.config_loader import ConfigLoader
from core.config.models import SystemConfig
from core.infrastructure.event_bus import (
    EventDomain,
    EventType,
)
from core.infrastructure.logging import EventBusLogger


@dataclass
class ConfigChangeEvent:
    """Событие изменения конфигурации."""
    old_config: Dict[str, Any]
    new_config: Dict[str, Any]
    changed_keys: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "file_watch"
    
    def to_dict(self) -> Dict:
        return {
            "changed_keys": self.changed_keys,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "old_config_summary": self._summarize_config(self.old_config),
            "new_config_summary": self._summarize_config(self.new_config),
        }
    
    @staticmethod
    def _summarize_config(config: Dict) -> Dict:
        """Краткое описание конфигурации."""
        return {
            "profile": config.get("profile", "unknown"),
            "debug": config.get("debug", False),
            "keys_count": len(config),
        }


@dataclass
class ConfigSnapshot:
    """Снимок конфигурации для отката."""
    config: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    checksum: str = ""
    
    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()
    
    def _compute_checksum(self) -> str:
        """Вычисление контрольной суммы конфигурации."""
        import hashlib
        config_str = str(sorted(self.config.items()))
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "config": self.config,
            "timestamp": self.timestamp.isoformat(),
            "checksum": self.checksum,
        }


class FileSystemWatcher:
    """
    Наблюдатель за файловой системой.
    
    FEATURES:
    - Отслеживание изменений файлов
    - Debounce для предотвращения множественных срабатываний
    - Поддержка нескольких файлов
    """
    
    def __init__(
        self,
        file_paths: List[Path],
        on_change: Callable,
        poll_interval: float = 1.0,
        debounce_seconds: float = 0.5,
    ):
        """
        Инициализация наблюдателя.
        
        ARGS:
        - file_paths: список файлов для наблюдения
        - on_change: callback при изменении
        - poll_interval: интервал опроса (сек)
        - debounce_seconds: задержка debounce (сек)
        """
        self._file_paths = file_paths
        self._on_change = on_change
        self._poll_interval = poll_interval
        self._debounce_seconds = debounce_seconds
        
        self._last_modified: Dict[Path, float] = {}
        self._pending_changes: Set[Path] = set()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Логгер будет инициализирован позже через event_bus
        self._logger = None

        # Инициализация временных меток
        for path in file_paths:
            if path.exists():
                self._last_modified[path] = path.stat().st_mtime

    def _init_logger(self, event_bus=None):
        """Инициализация логгера."""
        if event_bus is not None:
            self._logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="FileSystemWatcher")
            self._use_event_logging = True
        else:
            import logging
            self._logger = logging.getLogger(f"{__name__}.FileSystemWatcher")
            self._use_event_logging = False

    def _log_warning(self, message: str, *args, **kwargs):
        """Предупреждение."""
        if self._logger:
            if self._use_event_logging:
                self._logger.warning(message, *args, **kwargs)
            else:
                self._logger.warning(message, *args, **kwargs)

    def _log_info(self, message: str, *args, **kwargs):
        """Информационное сообщение."""
        if self._logger:
            if self._use_event_logging:
                self._logger.info(message, *args, **kwargs)
            else:
                self._logger.info(message, *args, **kwargs)

    def _log_debug(self, message: str, *args, **kwargs):
        """Отладочное сообщение."""
        if self._logger:
            if self._use_event_logging:
                self._logger.debug(message, *args, **kwargs)
            else:
                self._logger.debug(message, *args, **kwargs)

    def _log_error(self, message: str, *args, **kwargs):
        """Ошибка."""
        if self._logger:
            if self._use_event_logging:
                self._logger.error(message, *args, **kwargs)
            else:
                self._logger.error(message, *args, **kwargs)

    async def start(self):
        """Запуск наблюдателя."""
        if self._running:
            self._log_warning("Наблюдатель уже запущен")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        self._log_info(f"Наблюдатель запущен для {len(self._file_paths)} файлов")
    
    async def stop(self):
        """Остановка наблюдателя."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._log_info("Наблюдатель остановлен")
    
    async def _watch_loop(self):
        """Цикл наблюдения за файлами."""
        while self._running:
            try:
                await self._check_files()
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log_error(f"Ошибка в цикле наблюдения: {e}", exc_info=True)
    
    async def _check_files(self):
        """Проверка файлов на изменения."""
        for path in self._file_paths:
            if not path.exists():
                continue
            
            try:
                mtime = path.stat().st_mtime
                last_mtime = self._last_modified.get(path, 0)
                
                if mtime > last_mtime:
                    # Файл изменен
                    self._pending_changes.add(path)
                    self._last_modified[path] = mtime
                    
                    # Debounce
                    await asyncio.sleep(self._debounce_seconds)
                    
                    if path in self._pending_changes:
                        self._pending_changes.remove(path)
                        self._log_debug(f"Файл изменен: {path}")
                        
                        if inspect.iscoroutinefunction(self._on_change):
                            await self._on_change(path)
                        else:
                            self._on_change(path)
                            
            except Exception as e:
                self._log_error(f"Ошибка проверки файла {path}: {e}")


class DynamicConfigManager:
    """
    Менеджер динамической конфигурации с hot-reload.
    
    FEATURES:
    - Загрузка конфигурации из файлов
    - Hot-reload при изменениях
    - Callback-и для уведомлений об изменениях
    - Снимки конфигурации для отката
    - Валидация новой конфигурации
    - Интеграция с Event Bus
    
    USAGE:
    ```python
    # Создание менеджера
    config_manager = DynamicConfigManager(
        config_path=Path("registry.yaml"),
        profile="prod"
    )
    
    # Регистрация callback на изменения
    async def on_config_change(old, new):
        # Логирование через logger вместо print
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Конфигурация изменена: {new}")
    
    config_manager.on_config_change(on_config_change)
    
    # Инициализация (загрузка + запуск watcher)
    await config_manager.initialize()
    
    # Получение текущей конфигурации
    config = config_manager.get_config()
    
    # Завершение работы
    await config_manager.shutdown()
    ```
    """
    
    def __init__(
        self,
        config_path: Path,
        profile: str = "prod",
        config_loader: ConfigLoader = None,
        event_bus=None,  # UnifiedEventBus или EventBusConcurrent
        enable_hot_reload: bool = True,
        poll_interval: float = 1.0,
        max_backup_count: int = 5,
    ):
        """
        Инициализация менеджера конфигурации.

        ARGS:
        - config_path: путь к основному файлу конфигурации
        - profile: профиль конфигурации
        - config_loader: загрузчик конфигурации (опционально)
        - event_bus: шина событий (опционально)
        - enable_hot_reload: включить hot-reload
        - poll_interval: интервал опроса файлов (сек)
        - max_backup_count: макс. количество бэкапов
        """
        self._config_path = config_path
        self._profile = profile
        self._config_loader = config_loader or ConfigLoader(profile=profile)
        self._event_bus = event_bus
        self._enable_hot_reload = enable_hot_reload
        self._poll_interval = poll_interval
        self._max_backup_count = max_backup_count
        
        self._config: Optional[Dict[str, Any]] = None
        self._system_config: Optional[SystemConfig] = None
        self._callbacks: List[Callable] = []
        self._snapshots: List[ConfigSnapshot] = []
        self._watcher: Optional[FileSystemWatcher] = None
        self._initialized = False

        # Инициализация логгера
        if event_bus is not None:
            self._logger = EventBusLogger(event_bus, session_id="system", agent_id="system", component="DynamicConfigManager")
            self._use_event_logging = True
        else:
            import logging
            self._logger = logging.getLogger(f"{__name__}.DynamicConfigManager")
            self._use_event_logging = False
        
        self._log_info(f"Создан DynamicConfigManager для {config_path}")

    async def initialize(self):
        """
        Инициализация менеджера.

        Загружает конфигурацию и запускает watcher если включен hot-reload.
        """
        self._log_info("Инициализация DynamicConfigManager")
        
        # Загрузка конфигурации
        await self._load_config()
        
        # Запуск watcher если включен hot-reload
        if self._enable_hot_reload:
            await self._start_watcher()
        
        self._initialized = True

        # Событие инициализации
        if self._event_bus:
            await self._event_bus.publish(
                EventType.SYSTEM_INITIALIZED,
                data={
                    "component": "DynamicConfigManager",
                    "config_path": str(self._config_path),
                    "profile": self._profile,
                },
                domain=EventDomain.INFRASTRUCTURE,
            )

        self._log_info("DynamicConfigManager инициализирован")

    async def shutdown(self):
        """Завершение работы менеджера."""
        self._log_info("Завершение работы DynamicConfigManager")

        # Остановка watcher
        if self._watcher:
            await self._watcher.stop()

        self._initialized = False

        # Событие shutdown
        if self._event_bus:
            await self._event_bus.publish(
                EventType.SYSTEM_SHUTDOWN,
                data={"component": "DynamicConfigManager"},
                domain=EventDomain.INFRASTRUCTURE,
        )
        
        self._log_info("DynamicConfigManager завершен")
    
    async def _load_config(self) -> bool:
        """
        Загрузка конфигурации из файла.

        RETURNS:
        - bool: True если загрузка успешна
        """
        try:
            self._log_debug(f"Загрузка конфигурации из {self._config_path}")

            # Сохранение текущего снимка для отката (если есть предыдущая конфигурация)
            if self._config:
                self._save_snapshot(self._config)

            # Загрузка через ConfigLoader
            self._system_config = self._config_loader.load()

            # Загрузка raw конфигурации для сравнения
            new_config = await self._load_raw_config()
            
            # Сохраняем снимок после загрузки (включая первую загрузку)
            if new_config:
                self._save_snapshot(new_config)
            
            self._config = new_config

            self._log_info(f"Конфигурация загружена: profile={self._profile}")
            return True

        except Exception as e:
            self._log_error(f"Ошибка загрузки конфигурации: {e}", exc_info=True)

            # Событие ошибки
            if self._event_bus:
                await self._event_bus.publish(
                    EventType.SYSTEM_ERROR,
                    data={
                        "component": "DynamicConfigManager",
                        "error": str(e),
                        "stage": "load_config",
                    },
                    domain=EventDomain.INFRASTRUCTURE,
                )

            return False
    
    async def _load_raw_config(self) -> Dict[str, Any]:
        """Загрузка raw конфигурации из YAML."""
        if not self._config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {self._config_path}")
        
        with open(self._config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _save_snapshot(self, config: Dict[str, Any]):
        """Сохранение снимка конфигурации для отката."""
        snapshot = ConfigSnapshot(config=config)
        self._snapshots.append(snapshot)
        
        # Ограничение количества снимков
        if len(self._snapshots) > self._max_backup_count:
            self._snapshots.pop(0)
        
        self._log_debug(f"Сохранен снимок конфигурации (всего: {len(self._snapshots)})")
    
    def _create_backup(self) -> Optional[Path]:
        """
        Создание бэкапа файла конфигурации.
        
        RETURNS:
        - Path: путь к бэкапу или None если ошибка
        """
        if not self._config_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self._config_path.with_suffix(f".{timestamp}.bak")
        
        try:
            shutil.copy2(self._config_path, backup_path)
            self._log_debug(f"Создан бэкап: {backup_path}")
            
            # Удаление старых бэкапов
            self._cleanup_old_backups()
            
            return backup_path
            
        except Exception as e:
            self._log_error(f"Ошибка создания бэкапа: {e}")
            return None
    
    def _cleanup_old_backups(self):
        """Удаление старых бэкапов."""
        backup_dir = self._config_path.parent
        pattern = f"{self._config_path.stem}.*.bak"
        
        backups = sorted(
            backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime
        )
        
        # Удаление старых бэкапов
        while len(backups) > self._max_backup_count:
            old_backup = backups.pop(0)
            try:
                old_backup.unlink()
                self._log_debug(f"Удален старый бэкап: {old_backup}")
            except Exception as e:
                self._log_error(f"Ошибка удаления бэкапа {old_backup}: {e}")
    
    async def _start_watcher(self):
        """Запуск наблюдателя за файлами."""
        if not self._config_path.exists():
            self._log_warning(f"Файл конфигурации не найден: {self._config_path}")
            return
        
        self._watcher = FileSystemWatcher(
            file_paths=[self._config_path],
            on_change=self._on_config_changed,
            poll_interval=self._poll_interval,
        )
        
        await self._watcher.start()
        self._log_info(f"Watcher запущен для {self._config_path}")
    
    async def _on_config_changed(self, path: Path):
        """
        Обработка изменения конфигурации.
        
        ARGS:
        - path: путь к измененному файлу
        """
        self._log_info(f"Обнаружено изменение конфигурации: {path}")
        
        # Создание бэкапа перед применением изменений
        backup_path = self._create_backup()
        
        # Загрузка новой конфигурации
        old_config = self._config.copy() if self._config else {}
        
        if not await self._load_config():
            self._log_error("Не удалось загрузить новую конфигурацию, откат...")
            # Откат не требуется т.к. _config не изменился при ошибке
            return
        
        # Определение измененных ключей
        changed_keys = self._detect_changes(old_config, self._config)
        
        # Создание события изменения
        change_event = ConfigChangeEvent(
            old_config=old_config,
            new_config=self._config,
            changed_keys=changed_keys,
        )
        
        self._log_info(f"Изменены ключи конфигурации: {changed_keys}")

        # Уведомление callback-ов
        await self._notify_callbacks(change_event)

        # Публикация события
        if self._event_bus:
            await self._event_bus.publish(
                EventType.VERSION_CREATED,  # Используем как событие изменения конфига
                data=change_event.to_dict(),
                domain=EventDomain.INFRASTRUCTURE,
            )
    
    def _detect_changes(self, old_config: Dict, new_config: Dict) -> List[str]:
        """
        Определение измененных ключей конфигурации.
        
        ARGS:
        - old_config: старая конфигурация
        - new_config: новая конфигурация
        
        RETURNS:
        - List[str]: список измененных ключей
        """
        changed = []
        
        all_keys = set(old_config.keys()) | set(new_config.keys())
        
        for key in all_keys:
            old_value = old_config.get(key)
            new_value = new_config.get(key)
            
            if old_value != new_value:
                changed.append(key)
        
        return changed
    
    async def _notify_callbacks(self, event: ConfigChangeEvent):
        """
        Уведомление зарегистрированных callback-ов.
        
        ARGS:
        - event: событие изменения конфигурации
        """
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                self._log_error(f"Ошибка в callback конфигурации: {e}", exc_info=True)
    
    def on_config_change(self, callback: Callable):
        """
        Регистрация callback на изменение конфигурации.
        
        ARGS:
        - callback: функция для вызова при изменениях
        """
        self._callbacks.append(callback)
        self._log_debug(f"Зарегистрирован callback конфигурации (всего: {len(self._callbacks)})")
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """
        Получение текущей конфигурации.
        
        RETURNS:
        - Dict[str, Any]: текущая конфигурация
        """
        return self._config
    
    def get_system_config(self) -> Optional[SystemConfig]:
        """
        Получение типизированной конфигурации.
        
        RETURNS:
        - SystemConfig: типизированная конфигурация
        """
        return self._system_config
    
    def get_value(self, key_path: str, default: Any = None) -> Any:
        """
        Получение значения по пути ключа.
        
        ARGS:
        - key_path: путь ключа (например, "agent.max_steps")
        - default: значение по умолчанию
        
        RETURNS:
        - Any: значение или default
        
        EXAMPLE:
        ```python
        max_steps = config_manager.get_value("agent.max_steps", 10)
        ```
        """
        current = self._config
        if not current:
            return default
        
        keys = key_path.split('.')
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    async def reload_config(self) -> bool:
        """
        Принудительная перезагрузка конфигурации.

        RETURNS:
        - bool: True если перезагрузка успешна
        """
        self._log_info("Принудительная перезагрузка конфигурации")
        
        # Создание бэкапа перед перезагрузкой
        self._create_backup()
        
        return await self._load_config()
    
    def get_snapshot(self, index: int = -1) -> Optional[ConfigSnapshot]:
        """
        Получение снимка конфигурации.
        
        ARGS:
        - index: индекс снимка (-1 для последнего)
        
        RETURNS:
        - ConfigSnapshot или None
        """
        if not self._snapshots:
            return None
        
        return self._snapshots[index] if 0 <= abs(index) <= len(self._snapshots) else None
    
    async def rollback_to_snapshot(self, index: int = -1) -> bool:
        """
        Откат к снимку конфигурации.
        
        ARGS:
        - index: индекс снимка (-1 для последнего)
        
        RETURNS:
        - bool: True если откат успешен
        """
        snapshot = self.get_snapshot(index)
        if not snapshot:
            self._log_error("Снимок конфигурации не найден")
            return False
        
        self._log_info(f"Откат к снимку конфигурации от {snapshot.timestamp}")
        
        old_config = self._config.copy() if self._config else {}
        self._config = snapshot.config.copy()
        
        # Уведомление об изменении
        change_event = ConfigChangeEvent(
            old_config=old_config,
            new_config=self._config,
            changed_keys=["rollback"],
            source="rollback",
        )
        
        await self._notify_callbacks(change_event)
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики менеджера."""
        return {
            "config_path": str(self._config_path),
            "profile": self._profile,
            "initialized": self._initialized,
            "hot_reload_enabled": self._enable_hot_reload,
            "callbacks_count": len(self._callbacks),
            "snapshots_count": len(self._snapshots),
            "watcher_running": self._watcher._running if self._watcher else False,
        }
    
    @property
    def is_initialized(self) -> bool:
        """Статус инициализации."""
        return self._initialized


# Глобальный менеджер конфигурации (singleton)
_global_config_manager: Optional[DynamicConfigManager] = None


def get_config_manager() -> DynamicConfigManager:
    """
    Получение глобального менеджера конфигурации.
    
    RETURNS:
    - DynamicConfigManager: глобальный экземпляр
    """
    global _global_config_manager
    if _global_config_manager is None:
        raise RuntimeError(
            "DynamicConfigManager не инициализирован. "
            "Вызовите create_config_manager() перед использованием."
        )
    return _global_config_manager


def create_config_manager(
    config_path: Path,
    profile: str = "prod",
    **kwargs
) -> DynamicConfigManager:
    """
    Создание глобального менеджера конфигурации.
    
    ARGS:
    - config_path: путь к файлу конфигурации
    - profile: профиль конфигурации
    - **kwargs: дополнительные параметры для DynamicConfigManager
    
    RETURNS:
    - DynamicConfigManager: созданный экземпляр
    """
    global _global_config_manager
    _global_config_manager = DynamicConfigManager(
        config_path=config_path,
        profile=profile,
        **kwargs
    )
    return _global_config_manager


def reset_config_manager():
    """Сброс глобального менеджера (для тестов)."""
    global _global_config_manager
    _global_config_manager = None
