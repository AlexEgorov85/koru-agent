"""
LoggingSession — единая точка управления файловыми логами.

АРХИТЕКТУРА:
┌───────────────────────────────────────────────────────────────┐
│  LoggingSession (создаётся при инициализации InfraContext)    │
│  ├── run_timestamp: "2026-04-10_14-30-00"                     │
│  ├── base_dir: logs/2026-04-10_14-30-00/                      │
│  ├── agents_dir: logs/.../agents/                             │
│  ├── infra_logger: logging.Logger → infra_context.log         │
│  ├── app_logger: logging.Logger → app_context.log             │
│  └── create_agent_logger() → logging.Logger → agents/{ts}.log │
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

    def create_agent_logger(self, agent_id: str) -> logging.Logger:
        """
        Создаёт логгер для сессии агента.

        ПРАВИЛО: 1 сессия = 1 файл.
        Файл: agents/{timestamp}.log

        ARGS:
        - agent_id: Уникальный идентификатор агента

        RETURNS:
        - logging.Logger: Настроенный логгер агента
        """
        if not self._handlers_setup:
            self.setup_context_loggers()

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = self.agents_dir / f"{ts}.log"
        logger = self._setup_file_logger(f"agent.{agent_id}", log_path)
        self._agent_loggers[agent_id] = logger
        return logger

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
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))
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
            "%(levelname)-7s | %(message)s"
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
