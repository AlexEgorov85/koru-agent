"""
LogComponentMixin - базовый класс для логирования в компонентах.

FEATURES:
- Методы log_start(), log_success(), log_error()
- Интеграция со стандартным logging
"""
import logging
import time
from typing import Any, Dict, Optional


class LogComponentMixin:
    """
    Миксин для добавления логирования в компоненты.

    USAGE:
        class MyComponent(LogComponentMixin):
            def __init__(self):
                self._logger = logging.getLogger(__name__)
                self.logger = self._logger

            def execute(self):
                self.log_start("execute")
                try:
                    # логика
                    self.log_success("execute")
                except Exception as e:
                    self.log_error("execute", e)
    """

    def __init__(self, *args, **kwargs):
        """Инициализация логгера."""
        super().__init__(*args, **kwargs)
        if not hasattr(self, '_logger'):
            name = getattr(self, 'name', self.__class__.__name__)
            self._logger = logging.getLogger(f"{self.__class__.__module__}.{name}")
            self.logger = self._logger

    def log_start(self, method_name: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Логирование начала выполнения метода.

        ARGS:
        - method_name: имя метода
        - params: параметры метода (опционально)
        """
        self.logger.debug(f"▶️ {method_name} started{f' with params: {params}' if params else ''}")

    def log_success(self, method_name: str, result: Optional[Any] = None, 
                    execution_time_ms: Optional[float] = None) -> None:
        """
        Логирование успешного выполнения метода.

        ARGS:
        - method_name: имя метода
        - result: результат выполнения (опционально)
        - execution_time_ms: время выполнения в мс (опционально)
        """
        msg = f"✅ {method_name} completed"
        if execution_time_ms is not None:
            msg += f" in {execution_time_ms:.2f}ms"
        self.logger.debug(msg)

    def log_error(self, method_name: str, error: Exception, 
                  execution_time_ms: Optional[float] = None) -> None:
        """
        Логирование ошибки выполнения метода.

        ARGS:
        - method_name: имя метода
        - error: исключение
        - execution_time_ms: время выполнения в мс (опционально)
        """
        msg = f"❌ {method_name} failed: {error}"
        if execution_time_ms is not None:
            msg += f" after {execution_time_ms:.2f}ms"
        self.logger.error(msg, exc_info=True)
