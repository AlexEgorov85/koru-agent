"""
Централизованное управление путями приложения.

ЦЕЛЬ:
- Устранить hardcoded пути (Path("logs/..."), Path("data/..."))
- Единая точка изменения структуры директорий
- Валидация и создание директорий при инициализации

ИСПОЛЬЗОВАНИЕ:
```python
from core.config.paths import app_paths, log_paths

# Логирование
session_dir = log_paths.get_session_dir("session_123")
llm_log = log_paths.get_llm_log_path("session_123")

# Данные
cache_dir = app_paths.cache_dir
```
"""
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict
import os


# ============================================================
# Пути логирования
# ============================================================

class LogPaths(BaseModel):
    """
    Централизованные пути для системы логирования.
    
    ЗАМЕНЯЕТ:
    - Path("logs/sessions") в session_log_handler.py
    - Path("logs/archive") в handlers.py
    - Path("data/logs") в log_storage.py
    - Path("logs/audit") в event_handlers.py
    - Path("logs/debug") в event_handlers.py
    
    STRUCTURE:
    logs/
    ├── sessions/           ← Активные сессии
    │   └── YYYY-MM-DD_HH-MM-SS/
    │       ├── session.log
    │       ├── llm.jsonl
    │       └── metrics.jsonl
    ├── archive/            ← Архив (LogRotator)
    │   └── YYYY/MM/
    │       └── sessions/
    ├── indexed/            ← Индексы для поиска
    │   ├── sessions_index.jsonl
    │   └── agents_index.jsonl
    ├── common/             ← Общие логи
    └── audit/              ← Аудит безопасности
    """
    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)
    
    base_dir: Path = Field(default=Path("logs"), description="Базовая директория логов")
    
    @field_validator('base_dir', mode='before')
    @classmethod
    def convert_to_path(cls, v):
        """Конвертация строки в Path."""
        if isinstance(v, str):
            return Path(v)
        return v
    
    @property
    def sessions_dir(self) -> Path:
        """Директория активных сессий."""
        return self.base_dir / "sessions"
    
    @property
    def archive_dir(self) -> Path:
        """Директория архива."""
        return self.base_dir / "archive"
    
    @property
    def indexed_dir(self) -> Path:
        """Директория индексов."""
        return self.base_dir / "indexed"
    
    @property
    def common_dir(self) -> Path:
        """Директория общих логов."""
        return self.base_dir / "common"
    
    @property
    def audit_dir(self) -> Path:
        """Директория аудита."""
        return self.base_dir / "audit"
    
    @property
    def debug_dir(self) -> Path:
        """Директория отладочных логов."""
        return self.base_dir / "debug"
    
    @property
    def llm_dir(self) -> Path:
        """Директория LLM логов."""
        return self.base_dir / "llm"
    
    def get_session_dir(self, session_id: str) -> Path:
        """
        Получить директорию сессии.
        
        ARGS:
        - session_id: ID сессии (или имя папки)
        
        RETURNS:
        - Path к директории сессии
        """
        return self.sessions_dir / session_id
    
    def get_archive_session_dir(self, year: int, month: int) -> Path:
        """
        Получить директорию архива сессий за месяц.
        
        ARGS:
        - year: Год
        - month: Месяц
        
        RETURNS:
        - Path к директории архива
        """
        return self.archive_dir / str(year) / f"{month:02d}" / "sessions"
    
    def get_archive_llm_dir(self, year: int, month: int) -> Path:
        """
        Получить директорию архива LLM логов за месяц.
        
        ARGS:
        - year: Год
        - month: Месяц
        
        RETURNS:
        - Path к директории архива
        """
        return self.archive_dir / str(year) / f"{month:02d}" / "llm"
    
    @property
    def sessions_index_path(self) -> Path:
        """Путь к индексу сессий."""
        return self.indexed_dir / "sessions_index.jsonl"
    
    @property
    def agents_index_path(self) -> Path:
        """Путь к индексу агентов."""
        return self.indexed_dir / "agents_index.jsonl"
    
    def create_directories(self) -> None:
        """Создать все директории."""
        dirs = [
            self.base_dir,
            self.sessions_dir,
            self.archive_dir,
            self.indexed_dir,
            self.common_dir,
            self.audit_dir,
            self.debug_dir,
            self.llm_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> list:
        """
        Проверка путей.
        
        RETURNS:
        - Список ошибок (пустой если всё ок)
        """
        errors = []
        
        # Проверка на запись
        try:
            test_file = self.base_dir / ".write_test"
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.touch()
            test_file.unlink()
        except (OSError, PermissionError) as e:
            errors.append(f"No write permission: {self.base_dir} - {e}")
        
        # Проверка места на диске
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.base_dir)
            if free < 100 * 1024 * 1024:  # < 100 MB
                errors.append(f"Low disk space: {free // (1024*1024)} MB free")
        except OSError:
            pass  # Игнорируем если не удалось проверить
        
        return errors
    
    def __repr__(self) -> str:
        return f"LogPaths(base_dir={self.base_dir})"


# ============================================================
# Пути приложения
# ============================================================

class AppPaths(BaseModel):
    """
    Централизованные пути приложения.
    
    STRUCTURE:
    data/
    ├── cache/              ← Кэш
    ├── vector_store/       ← Векторное хранилище
    ├── models/             ← Загруженные модели
    ├── temp/               ← Временные файлы
    └── config/             ← Конфигурация пользователя
    """
    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)
    
    base_dir: Path = Field(default=Path("data"), description="Базовая директория данных")
    
    @field_validator('base_dir', mode='before')
    @classmethod
    def convert_to_path(cls, v):
        """Конвертация строки в Path."""
        if isinstance(v, str):
            return Path(v)
        return v
    
    @property
    def cache_dir(self) -> Path:
        """Директория кэша."""
        return self.base_dir / "cache"
    
    @property
    def vector_store_dir(self) -> Path:
        """Директория векторного хранилища."""
        return self.base_dir / "vector_store"
    
    @property
    def models_dir(self) -> Path:
        """Директория моделей."""
        return self.base_dir / "models"
    
    @property
    def temp_dir(self) -> Path:
        """Директория временных файлов."""
        return self.base_dir / "temp"
    
    @property
    def config_dir(self) -> Path:
        """Директория конфигурации пользователя."""
        return self.base_dir / "config"
    
    @property
    def logs_dir(self) -> Path:
        """Директория логов (для совместимости)."""
        return self.base_dir / "logs"
    
    def create_directories(self) -> None:
        """Создать все директории."""
        dirs = [
            self.base_dir,
            self.cache_dir,
            self.vector_store_dir,
            self.models_dir,
            self.temp_dir,
            self.config_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def __repr__(self) -> str:
        return f"AppPaths(base_dir={self.base_dir})"


# ============================================================
# Глобальные экземпляры
# ============================================================

_log_paths: Optional[LogPaths] = None
_app_paths: Optional[AppPaths] = None


def get_log_paths() -> LogPaths:
    """
    Получить пути логирования.
    
    RETURNS:
    - LogPaths: глобальный экземпляр путей
    """
    global _log_paths
    if _log_paths is None:
        _log_paths = LogPaths()
    return _log_paths


def get_app_paths() -> AppPaths:
    """
    Получить пути приложения.
    
    RETURNS:
    - AppPaths: глобальный экземпляр путей
    """
    global _app_paths
    if _app_paths is None:
        _app_paths = AppPaths()
    return _app_paths


def init_paths(
    logs_base: Optional[str] = None,
    data_base: Optional[str] = None
) -> None:
    """
    Инициализация путей.
    
    ARGS:
    - logs_base: Базовая директория для логов (по умолчанию "logs")
    - data_base: Базовая директория для данных (по умолчанию "data")
    """
    global _log_paths, _app_paths
    
    if logs_base:
        _log_paths = LogPaths(base_dir=Path(logs_base))
    
    if data_base:
        _app_paths = AppPaths(base_dir=Path(data_base))


def create_all_directories() -> None:
    """Создать все директории приложения."""
    get_log_paths().create_directories()
    get_app_paths().create_directories()


# ============================================================
# Алиасы для удобства
# ============================================================

log_paths = get_log_paths()
app_paths = get_app_paths()


# ============================================================
# Утилиты
# ============================================================

def ensure_dir(path: Path) -> Path:
    """
    Гарантировать существование директории.
    
    ARGS:
    - path: Путь к директории
    
    RETURNS:
    - Тот же путь (для chaining)
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_relative_to_project(path: str) -> Path:
    """
    Получить путь относительно корня проекта.
    
    ARGS:
    - path: Относительный путь
    
    RETURNS:
    - Абсолютный путь
    """
    # Находим корень проекта (где лежит main.py)
    project_root = Path(__file__).parent.parent.parent
    return project_root / path


def is_path_safe(path: Path, base: Path) -> bool:
    """
    Проверка что путь находится внутри базовой директории.
    
    ARGS:
    - path: Проверяемый путь
    - base: Базовая директория
    
    RETURNS:
    - True если путь безопасен
    """
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
