"""
Обработчик событий логирования.

Подписывается на события LOG_* и выводит их в файл/консоль.
"""
import logging
from core.infrastructure.event_bus.event_bus import EventBus, Event, EventType


logger = logging.getLogger(__name__)


class LogEventHandler:
    """
    Обработчик событий логирования.
    
    Подписывается на:
    - LOG_INFO → INFO в файл
    - LOG_DEBUG → DEBUG в файл
    - LOG_WARNING → WARNING в консоль + файл
    - LOG_ERROR → ERROR в консоль + файл
    """

    def __init__(self, log_file: str = "logs/agent.log"):
        """
        Инициализация обработчика.

        ARGS:
            log_file: путь к файлу логов
        """
        self.log_file = log_file
        self._setup_file_handler()

    def _setup_file_handler(self):
        """Настройка файлового обработчика."""
        import os
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        self.file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        self.file_handler.setLevel(logging.DEBUG)
        self.file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        ))

    async def on_log_info(self, event: Event):
        """Обработка события LOG_INFO."""
        data = event.data
        message = data.get('message', '')
        log_name = data.get('logger', 'unknown')
        
        # Пишем только в файл
        file_logger = logging.getLogger(f"file.{log_name}")
        file_logger.addHandler(self.file_handler)
        file_logger.setLevel(logging.DEBUG)
        file_logger.propagate = False
        file_logger.info(f"[{log_name}] {message}")

    async def on_log_debug(self, event: Event):
        """Обработка события LOG_DEBUG."""
        data = event.data
        message = data.get('message', '')
        log_name = data.get('logger', 'unknown')
        
        # Пишем только в файл
        file_logger = logging.getLogger(f"file.{log_name}")
        file_logger.addHandler(self.file_handler)
        file_logger.setLevel(logging.DEBUG)
        file_logger.propagate = False
        file_logger.debug(f"[{log_name}] {message}")

    async def on_log_warning(self, event: Event):
        """Обработка события LOG_WARNING."""
        data = event.data
        message = data.get('message', '')
        log_name = data.get('logger', 'unknown')
        
        # Пишем в консоль и файл
        logger.warning(f"[{log_name}] {message}")
        file_logger = logging.getLogger(f"file.{log_name}")
        file_logger.addHandler(self.file_handler)
        file_logger.setLevel(logging.DEBUG)
        file_logger.propagate = False
        file_logger.warning(f"[{log_name}] {message}")

    async def on_log_error(self, event: Event):
        """Обработка события LOG_ERROR."""
        data = event.data
        message = data.get('message', '')
        log_name = data.get('logger', 'unknown')
        exc_info = data.get('exc_info')
        
        # Пишем в консоль и файл
        logger.error(f"[{log_name}] {message}")
        if exc_info:
            logger.error(exc_info)
        
        file_logger = logging.getLogger(f"file.{log_name}")
        file_logger.addHandler(self.file_handler)
        file_logger.setLevel(logging.DEBUG)
        file_logger.propagate = False
        file_logger.error(f"[{log_name}] {message}")
        if exc_info:
            file_logger.error(exc_info)

    def subscribe(self, event_bus: EventBus):
        """
        Подписка на события логирования.

        ARGS:
            event_bus: шина событий
        """
        event_bus.subscribe(EventType.LOG_INFO, self.on_log_info)
        event_bus.subscribe(EventType.LOG_DEBUG, self.on_log_debug)
        event_bus.subscribe(EventType.LOG_WARNING, self.on_log_warning)
        event_bus.subscribe(EventType.LOG_ERROR, self.on_log_error)
        logger.info(f"LogEventHandler подписан на события логирования (файл: {self.log_file})")
