"""
Конфигурация системы логирования.

FEATURES:
- Централизованная конфигурация
- Политики хранения и ротации
- Настройки форматов логов
"""
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class LogFormat(str, Enum):
    """Форматы логов."""
    TEXT = "text"
    JSON = "json"
    JSONL = "jsonl"


@dataclass
class RetentionConfig:
    """Политика хранения логов."""
    active_days: int = 7
    archive_months: int = 12
    max_size_mb: int = 100
    max_files_per_day: int = 100


@dataclass
class IndexingConfig:
    """Настройки индексации."""
    enabled: bool = True
    index_sessions: bool = True
    index_agents: bool = True
    update_interval_sec: int = 60


@dataclass
class SymlinksConfig:
    """Настройки symlink."""
    enabled: bool = True
    latest_session: bool = True
    latest_agent: bool = True
    latest_llm: bool = True


@dataclass
class LoggingConfig:
    """
    Конфигурация системы логирования.

    ATTRIBUTES:
    - base_dir: Базовая директория для логов
    - agent_format: Формат логов агента
    - session_format: Формат логов сессии
    - llm_format: Формат LLM логов
    - metrics_format: Формат метрик
    - retention: Политика хранения
    - indexing: Настройки индексации
    - symlinks: Настройки symlink
    """
    base_dir: str = "logs"

    agent_format: LogFormat = LogFormat.TEXT
    session_format: LogFormat = LogFormat.JSONL
    llm_format: LogFormat = LogFormat.JSONL
    metrics_format: LogFormat = LogFormat.JSONL

    retention: RetentionConfig = field(default_factory=RetentionConfig)
    indexing: IndexingConfig = field(default_factory=IndexingConfig)
    symlinks: SymlinksConfig = field(default_factory=SymlinksConfig)

    level: str = "INFO"

    @property
    def active_dir(self) -> Path:
        """Директория активных логов."""
        return Path(self.base_dir) / "active"

    @property
    def archive_dir(self) -> Path:
        """Директория архива."""
        return Path(self.base_dir) / "archive"

    @property
    def indexed_dir(self) -> Path:
        """Директория индексов."""
        return Path(self.base_dir) / "indexed"

    @property
    def config_dir(self) -> Path:
        """Директория конфигурации."""
        return Path(self.base_dir) / "config"

    def get_active_sessions_dir(self) -> Path:
        """Директория активных сессий."""
        return self.active_dir / "sessions"

    def get_active_llm_dir(self) -> Path:
        """Директория активных LLM логов."""
        return self.active_dir / "llm"

    def get_archive_sessions_dir(self, year: int, month: int) -> Path:
        """Директория архива сессий за месяц."""
        return self.archive_dir / str(year) / f"{month:02d}" / "sessions"

    def get_archive_llm_dir(self, year: int, month: int) -> Path:
        """Директория архива LLM логов за месяц."""
        return self.archive_dir / str(year) / f"{month:02d}" / "llm"

    def get_sessions_index_path(self) -> Path:
        """Путь к индексу сессий."""
        return self.indexed_dir / "sessions_index.jsonl"

    def get_agents_index_path(self) -> Path:
        """Путь к индексу агентов."""
        return self.indexed_dir / "agents_index.jsonl"


# Глобальный экземпляр конфигурации
_default_config: Optional[LoggingConfig] = None


def get_logging_config() -> LoggingConfig:
    """Получение конфигурации логирования."""
    global _default_config
    if _default_config is None:
        _default_config = LoggingConfig()
    return _default_config


def configure_logging(config: LoggingConfig) -> None:
    """
    Настройка конфигурации логирования.

    ARGS:
        config: Новая конфигурация
    """
    global _default_config
    _default_config = config


def load_config_from_yaml(yaml_path: str) -> LoggingConfig:
    """
    Загрузка конфигурации из YAML файла.

    ARGS:
        yaml_path: Путь к YAML файлу

    RETURNS:
        LoggingConfig: Конфигурация
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required. Install with: pip install pyyaml")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    logging_data = data.get('logging', {})

    retention_data = logging_data.get('retention', {})
    retention = RetentionConfig(
        active_days=retention_data.get('active_days', 7),
        archive_months=retention_data.get('archive_months', 12),
        max_size_mb=retention_data.get('max_size_mb', 100),
        max_files_per_day=retention_data.get('max_files_per_day', 100),
    )

    indexing_data = logging_data.get('indexing', {})
    indexing = IndexingConfig(
        enabled=indexing_data.get('enabled', True),
        index_sessions=indexing_data.get('index_sessions', True),
        index_agents=indexing_data.get('index_agents', True),
        update_interval_sec=indexing_data.get('update_interval_sec', 60),
    )

    symlinks_data = logging_data.get('symlinks', {})
    symlinks = SymlinksConfig(
        enabled=symlinks_data.get('enabled', True),
        latest_session=symlinks_data.get('latest_session', True),
        latest_agent=symlinks_data.get('latest_agent', True),
        latest_llm=symlinks_data.get('latest_llm', True),
    )

    formats_data = logging_data.get('formats', {})

    def parse_format(fmt_str: str) -> LogFormat:
        try:
            return LogFormat(fmt_str.lower())
        except ValueError:
            return LogFormat.TEXT

    config = LoggingConfig(
        base_dir=logging_data.get('paths', {}).get('base', 'logs'),
        agent_format=parse_format(formats_data.get('agent', 'text')),
        session_format=parse_format(formats_data.get('session', 'jsonl')),
        llm_format=parse_format(formats_data.get('llm', 'jsonl')),
        metrics_format=parse_format(formats_data.get('metrics', 'jsonl')),
        retention=retention,
        indexing=indexing,
        symlinks=symlinks,
        level=logging_data.get('level', 'INFO'),
    )

    return config


def save_config_to_yaml(config: LoggingConfig, yaml_path: str) -> None:
    """
    Сохранение конфигурации в YAML файл.

    ARGS:
        config: Конфигурация
        yaml_path: Путь к файлу
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required. Install with: pip install pyyaml")

    data = {
        'logging': {
            'paths': {
                'base': config.base_dir,
                'active': str(config.active_dir),
                'archive': str(config.archive_dir),
                'index': str(config.indexed_dir),
            },
            'formats': {
                'agent': config.agent_format.value,
                'session': config.session_format.value,
                'llm': config.llm_format.value,
                'metrics': config.metrics_format.value,
            },
            'retention': {
                'active_days': config.retention.active_days,
                'archive_months': config.retention.archive_months,
                'max_size_mb': config.retention.max_size_mb,
                'max_files_per_day': config.retention.max_files_per_day,
            },
            'indexing': {
                'enabled': config.indexing.enabled,
                'index_sessions': config.indexing.index_sessions,
                'index_agents': config.indexing.index_agents,
                'update_interval_sec': config.indexing.update_interval_sec,
            },
            'symlinks': {
                'enabled': config.symlinks.enabled,
                'latest_session': config.symlinks.latest_session,
                'latest_agent': config.symlinks.latest_agent,
                'latest_llm': config.symlinks.latest_llm,
            },
            'level': config.level,
        }
    }

    Path(yaml_path).parent.mkdir(parents=True, exist_ok=True)

    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
