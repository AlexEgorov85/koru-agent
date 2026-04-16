"""
LoggingSession — единая точка управления файловыми логами.

АРХИТЕКТУРА:
┌───────────────────────────────────────────────────────────────┐
│  LoggingSession (создаётся при инициализации InfraContext)    │
│  ├── run_timestamp: "2026-04-10_14-30-00"                     │
│  ├── base_dir: logs/2026-04-10_14-30-00/                      │
│  ├── agents_dir: logs/.../agents/                             │
│  ├── infra_logger: logging.Logger → infra_context.log         │
│  └── app_logger: logging.Logger → app_context.log             │
│                                                               │
│  Компоненты (через get_component_logger):                     │
│    → app_context.log (сервисы, скиллы, инструменты)           │
│                                                               │
│  Агенты (через create_agent_logger):                           │
│    → agents/{timestamp}.log (ОДИН файл на сессию)             │
└───────────────────────────────────────────────────────────────┘

FEATURES:
- Одна директория на запуск (генерируется один раз)
- Чёткое разделение: infra.context, app.context, agent.*
- 1 сессия агента = 1 файл
- Консольный вывод с фильтрацией через EventTypeFilter
- Не использует EventBus — стандартный logging для надёжности

USAGE:
```python
from core.config.logging_config import LoggingConfig
from core.infrastructure.logging.session import LoggingSession

config = LoggingConfig()
session = LoggingSession(config)
session.setup_context_loggers()

# В InfrastructureContext:
session.infra_logger.info("Инициализация инфраструктуры...")

# В ApplicationContext:
session.app_logger.debug("Загрузка компонентов...")

# Для агента:
agent_logger = session.create_agent_logger("agent-1")
agent_logger.info("Агент запущен")
```
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from core.config.logging_config import LoggingConfig


class _LogFileFormatter(logging.Formatter):
    """Форматтер для файловых логов с поддержкой event_type и component.

    Формат:
    %(asctime)s | %(levelname)-8s | %(event_type)s | %(component)s | %(message)s

    Если event_type/component не указаны — выводится прочерк.
    """

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(event_type)-20s | %(component)-30s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S,%f",
        )

    def formatTime(self, record, datefmt=None):
        """Форматирование времени с миллисекундами."""
        dt = datetime.fromtimestamp(record.created)
        if datefmt:
            # Убираем последние 3 цифры микросекунд (оставляем миллисекунды)
            return dt.strftime(datefmt)[:-3]
        return dt.isoformat(timespec="milliseconds")

    def format(self, record):
        """Форматирование записи с подстановкой event_type и component."""
        # Подставляем event_type из extra или прочерк
        event_type = getattr(record, "event_type", None)
        if event_type is not None:
            # Если это enum — берём value, иначе строковое представление
            record.event_type = event_type.value if hasattr(event_type, "value") else str(event_type)
        else:
            record.event_type = "-"

        # Подставляем component из extra или прочерк
        component = getattr(record, "component", None)
        if component is None:
            # Пытаемся определить component из logger name
            # Например "component.behavior.react_pattern" -> "behavior.react_pattern"
            name = getattr(record, "name", "")
            if name.startswith("component."):
                record.component = name[len("component."):]
            elif name:
                record.component = name
            else:
                record.component = "-"
        # Если component уже задан в extra — используем его
        return super().format(record)


class LoggingSession:
    """
    Управляет жизненным циклом логов одной сессии запуска.

    АРХИТЕКТУРА:
    - Создаёт директорию: logs/{run_timestamp}/
    - Настраивает FileHandler для контекстов (infra, app)
    - Предоставляет create_agent_logger() для сессий агентов
    - Настраивает StreamHandler для консоли с фильтрацией

    ATTRIBUTES:
    - config: LoggingConfig — конфигурация
    - run_timestamp: str — метка времени запуска
    - base_dir: Path — базовая директория логов
    - agents_dir: Path — директория для логов агентов
    - infra_logger: logging.Logger — логгер инфраструктуры
    - app_logger: logging.Logger — логгер приложения
    - _agent_loggers: Dict[str, logging.Logger] — кэш логгеров агентов
    - _handlers_setup: bool — флаг настройки
    """

    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Инициализация сессии логирования.

        ARGS:
        - config: Конфигурация логирования (создаст дефолтную если None)
        """
        self.config = config or LoggingConfig()
        self.run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.base_dir = self.config.logs_dir / self.run_timestamp
        self.agents_dir = self.base_dir / "agents"

        self.infra_logger: Optional[logging.Logger] = None
        self.app_logger: Optional[logging.Logger] = None
        self._agent_loggers: Dict[str, logging.Logger] = {}
        self._handlers_setup = False

    def setup_context_loggers(self) -> None:
        """
        Создаёт директорию и настраивает логи контекстов.

        Создаёт:
        - base_dir/infra_context.log
        - base_dir/app_context.log
        - Консольный StreamHandler с фильтрацией
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.agents_dir.mkdir(parents=True, exist_ok=True)

        # 1. Инфраструктура
        self.infra_logger = self._setup_file_logger(
            "infra.context",
            self.base_dir / "infra_context.log"
        )

        # 2. Приложение
        self.app_logger = self._setup_file_logger(
            "app.context",
            self.base_dir / "app_context.log"
        )

        # 3. Консоль (терминал)
        self._setup_console_handler()
        self._handlers_setup = True

    def get_component_logger(self, component_name: str) -> logging.LoggerAdapter:
        """
        Создаёт или возвращает логгер для компонента с LoggerAdapter.

        Все компоненты пишут в app_context.log (единый файл приложения).

        ARGS:
        - component_name: Имя компонента (например, "skill.planning", "tool.sql")

        RETURNS:
        - logging.LoggerAdapter: Логгер с автоматически заданным component
        """
        if not self._handlers_setup:
            self.setup_context_loggers()

        logger_name = f"component.{component_name}"
        logger = logging.getLogger(logger_name)

        # Если хендлеры ещё не добавлены — добавляем
        if not logger.handlers:
            logger.setLevel(logging.DEBUG)
            logger.propagate = False  # Не дублировать в root

            # Файловый хендлер — пишем в app_context.log
            app_log_path = self.base_dir / "app_context.log"
            file_handler = logging.FileHandler(app_log_path, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            from core.infrastructure.logging.session import _LogFileFormatter
            file_handler.setFormatter(_LogFileFormatter())
            logger.addHandler(file_handler)

            # Консольный хендлер с фильтрацией (копия из _setup_console_handler)
            self._add_console_handler(logger)

        # Возвращаем LoggerAdapter с автоматически заданным component
        return logging.LoggerAdapter(
            logger,
            extra={"component": component_name}
        )

    def _add_console_handler(self, logger: logging.Logger) -> None:
        """Добавляет консольный хендлер с фильтрацией."""
        from core.infrastructure.logging.handlers import EventTypeFilter
        import sys
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(self.config.console.level)
        console.setFormatter(logging.Formatter("%(message)s"))
        allowed_events = getattr(self.config.console, "allowed_terminal_events", None)
        if allowed_events:
            console.addFilter(EventTypeFilter(allowed_events))
        logger.addHandler(console)

    def create_agent_logger(self, agent_id: str) -> logging.Logger:
        """
        Создаёт логгер для сессии агента.

        ПРАВИЛО: 1 сессия = 1 файл.
        Файл: agents/{timestamp}.log

        ВАЖНО: Если логгер для agent_id уже существует — возвращается он.
        Это предотвращает создание дублирующих файлов при повторном вызове.

        ARGS:
        - agent_id: Уникальный идентификатор агента

        RETURNS:
        - logging.Logger: Настроенный логгер агента
        """
        if not self._handlers_setup:
            self.setup_context_loggers()

        # Если логгер уже существует — возвращаем его (предотвращаем дубли)
        if agent_id in self._agent_loggers:
            return self._agent_loggers[agent_id]

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = self.agents_dir / f"{ts}.log"
        logger = self._setup_file_logger(f"agent.{agent_id}", log_path)
        # Добавляем консольный хендлер с фильтрацией для агента
        self._add_console_handler(logger)
        self._agent_loggers[agent_id] = logger
        return logger

    def get_last_agent_log_path(self) -> Optional[Path]:
        """
        Получить путь к последнему лог-файлу агента.

        Если есть созданные логгеры — возвращает путь последнего.
        Если логгеров нет — ищет последний файл в agents_dir.

        RETURNS:
        - Path к лог-файлу или None
        """
        # Если есть созданные логгеры — берём последний
        if self._agent_loggers:
            last_id = list(self._agent_loggers.keys())[-1]
            last_logger = self._agent_loggers[last_id]
            # Путь можно получить из handlers
            for handler in last_logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    return Path(handler.baseFilename)

        # Fallback: ищем последний файл в agents_dir
        if self.agents_dir.exists():
            log_files = sorted(self.agents_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
            if log_files:
                return log_files[-1]

        return None

    def shutdown(self) -> None:
        """Корректно закрывает все обработчики."""
        for logger in [self.infra_logger, self.app_logger]:
            if logger:
                for handler in logger.handlers:
                    handler.close()

        for logger in self._agent_loggers.values():
            for handler in logger.handlers:
                handler.close()

        self._agent_loggers.clear()

    def _setup_file_logger(
        self,
        name: str,
        path: Path
    ) -> logging.Logger:
        """
        Создаёт файловый логгер.

        ARGS:
        - name: Имя логгера (например, "infra.context")
        - path: Путь к файлу лога

        RETURNS:
        - logging.Logger: Настроенный логгер
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.propagate = False  # Не дублировать в root

        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(_LogFileFormatter())
        logger.addHandler(handler)
        return logger

    def _setup_console_handler(self) -> None:
        """
        Настраивает вывод в терминал с фильтрацией.

        StreamHandler пишет в stdout.
        Фильтр по EventTypeFilter применяется если настроен.
        """
        console = logging.StreamHandler(sys.stdout)
        console_level = getattr(
            logging,
            self.config.console.level.upper(),
            logging.INFO
        )
        console.setLevel(console_level)
        console.setFormatter(logging.Formatter(
            "%(message)s"
        ))

        # Добавляем фильтр по типам событий если настроен
        # (фильтрация работает через handlers.py::EventTypeFilter)
        allowed_events = getattr(
            self.config.console,
            "allowed_terminal_events",
            None
        )
        if allowed_events:
            from core.infrastructure.logging.handlers import EventTypeFilter
            console.addFilter(EventTypeFilter(allowed_events))

        root_logger = logging.getLogger()
        root_logger.addHandler(console)
        root_logger.setLevel(logging.DEBUG)
