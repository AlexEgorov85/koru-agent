"""
Утилита для разделения пользовательских и технических логов.

USAGE:
    from core.utils.logger import AgentLogger
    
    logger = AgentLogger("agent.runtime")
    
    # Пользователь видит (только консоль)
    logger.user_message("🚀 Начинаю выполнение")
    
    # Техническая информация (в файл)
    logger.debug("Инициализация контекста: ctx_123")
    
    # Ошибка (пользователь кратко + тех. детали в файл)
    logger.error("Ошибка выполнения", exc_info=True)
"""
import logging
import sys
from typing import Optional


class AgentLogger:
    """
    Разделение пользовательских и технических логов.
    
    FEATURES:
    - user_message() → только консоль (INFO)
    - info() → консоль + файл (INFO)
    - debug() → только файл (DEBUG)
    - error() → консоль + файл с exc_info (ERROR)
    """

    def __init__(self, name: str):
        """
        Инициализация логгера.

        ARGS:
            name: имя логгера (будет преобразовано в koru.{name})
        """
        self.name = name
        self.logger = logging.getLogger(f"koru.{name}")
        self.logger.setLevel(logging.DEBUG)

    def info(self, message: str, technical: bool = False):
        """
        Информационное сообщение.

        ARGS:
            message: сообщение
            technical: если True → только в файл (DEBUG), иначе → консоль + файл (INFO)
        """
        if technical:
            self.logger.debug(message)
        else:
            self.logger.info(message)

    def error(self, message: str, exc_info: bool = False):
        """
        Ошибка (всегда в оба лога).

        ARGS:
            message: сообщение об ошибке
            exc_info: включать ли traceback
        """
        self.logger.error(message, exc_info=exc_info)

    def debug(self, message: str):
        """
        Отладка (только в тех. лог/файл).

        ARGS:
            message: отладочное сообщение
        """
        self.logger.debug(message)

    def user_message(self, message: str):
        """
        Сообщение для пользователя (только консоль, INFO уровень).

        ARGS:
            message: пользовательское сообщение
        """
        self.logger.info(message)

    def warning(self, message: str):
        """
        Предупреждение.

        ARGS:
            message: сообщение предупреждения
        """
        self.logger.warning(message)

    def critical(self, message: str, exc_info: bool = False):
        """
        Критическая ошибка.

        ARGS:
            message: сообщение
            exc_info: включать ли traceback
        """
        self.logger.critical(message, exc_info=exc_info)


def get_logger(name: str) -> AgentLogger:
    """
    Фабричная функция для создания логгера.

    ARGS:
        name: имя логгера

    RETURNS:
        экземпляр AgentLogger

    EXAMPLE:
        logger = get_logger("agent.runtime")
        logger.user_message("Запуск агента")
    """
    return AgentLogger(name)
