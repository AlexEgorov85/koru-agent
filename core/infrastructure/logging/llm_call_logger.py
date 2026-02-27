"""
Отдельное логирование LLM вызовов.

Каждый вызов LLM (промпт + ответ) записывается в отдельный файл:
logs/llm_calls/{session_id}_{timestamp}_{component}_{phase}.log

USAGE:
    from core.infrastructure.logging.llm_call_logger import LLMCallLogger
    
    logger = LLMCallLogger("logs/llm_calls")
    await logger.log_prompt(session_id, component, phase, prompt_data)
    await logger.log_response(session_id, component, phase, response_data)
"""
import os
import logging
import logging.handlers
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class LLMCallLogger:
    """
    Логгер для отдельных LLM вызовов.
    
    Создаёт отдельный файл для каждого вызова LLM:
    - Промпт → записывается при генерации
    - Ответ → дописывается при получении
    """

    def __init__(self, log_dir: str = "logs/llm_calls", max_files: int = 100):
        """
        Инициализация логгера.

        ARGS:
            log_dir: директория для логов LLM вызовов
            max_files: максимальное количество файлов логов (для ротации)
        """
        self.log_dir = log_dir
        self.max_files = max_files
        self._active_files: Dict[str, logging.Logger] = {}
        
        # Создаём директорию
        Path(log_dir).mkdir(parents=True, exist_ok=True)

    def _get_filename(self, session_id: str, component: str, phase: str, timestamp: datetime) -> str:
        """
        Генерация имени файла.

        ARGS:
            session_id: ID сессии
            component: компонент
            phase: фаза (think/act/observe)
            timestamp: временная метка

        RETURNS:
            имя файла
        """
        ts = timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # микросекунды → миллисекунды
        safe_component = component.replace("/", "_").replace("\\", "_")
        return f"{session_id}_{ts}_{safe_component}_{phase}.log"

    def _get_logger(self, filename: str) -> logging.Logger:
        """
        Получение или создание логгера для файла.

        ARGS:
            filename: имя файла

        RETURNS:
            логгер
        """
        if filename in self._active_files:
            return self._active_files[filename]

        filepath = os.path.join(self.log_dir, filename)
        
        # Создаём логгер
        logger = logging.getLogger(f"llm_call.{filename}")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []  # Очищаем обработчики
        
        # Файловый обработчик
        file_handler = logging.FileHandler(filepath, encoding='utf-8', mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(file_handler)
        
        # Отключаем распространение
        logger.propagate = False
        
        self._active_files[filename] = logger
        
        # Ротация: удаляем старые файлы если превышен лимит
        self._rotate_files()
        
        return logger

    def _rotate_files(self):
        """Удаление старых файлов логов."""
        try:
            files = sorted(
                Path(self.log_dir).glob("*.log"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            # Удаляем файлы сверх лимита
            for old_file in files[self.max_files:]:
                old_file.unlink()
        except Exception:
            pass

    async def log_prompt(self, session_id: str, component: str, phase: str, data: Dict[str, Any]):
        """
        Логирование промпта.

        ARGS:
            session_id: ID сессии
            component: компонент
            phase: фаза
            data: данные промпта
        """
        timestamp = datetime.now()
        filename = self._get_filename(session_id, component, phase, timestamp)
        logger = self._get_logger(filename)
        
        logger.info("=" * 80)
        logger.info(f"LLM PROMPT | Session: {session_id} | Component: {component} | Phase: {phase}")
        logger.info("=" * 80)
        logger.info(f"Timestamp: {timestamp.isoformat()}")
        logger.info(f"Component: {component}")
        logger.info(f"Phase: {phase}")
        logger.info(f"Session ID: {session_id}")
        
        if data.get('goal'):
            logger.info(f"Goal: {data['goal']}")
        
        logger.info("-" * 80)
        logger.info(f"System prompt ({len(data.get('system_prompt', ''))} chars):")
        logger.info(data.get('system_prompt', '')[:500] + "..." if len(data.get('system_prompt', '')) > 500 else data.get('system_prompt', ''))
        logger.info("-" * 80)
        
        if data.get('user_prompt'):
            logger.info(f"User prompt ({len(data.get('user_prompt', ''))} chars):")
            logger.info(data.get('user_prompt', ''))
        
        logger.info("-" * 80)
        logger.info(f"Temperature: {data.get('temperature', 0.0)}")
        logger.info(f"Max tokens: {data.get('max_tokens', 1000)}")
        logger.info("=" * 80)

    async def log_response(self, session_id: str, component: str, phase: str, data: Dict[str, Any]):
        """
        Логирование ответа.

        ARGS:
            session_id: ID сессии
            component: компонент
            phase: фаза
            data: данные ответа
        """
        timestamp = datetime.now()
        filename = self._get_filename(session_id, component, phase, timestamp)
        logger = self._get_logger(filename)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"LLM RESPONSE | Session: {session_id} | Component: {component} | Phase: {phase}")
        logger.info("=" * 80)
        logger.info(f"Timestamp: {timestamp.isoformat()}")
        
        response = data.get('response', {})
        if isinstance(response, dict):
            import json
            logger.info(f"Response (JSON):")
            logger.info(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            logger.info(f"Response ({type(response).__name__}):")
            logger.info(str(response))
        
        logger.info("=" * 80)
        logger.info("")

    def cleanup(self):
        """Очистка активных логгеров."""
        for logger in self._active_files.values():
            for handler in logger.handlers:
                handler.close()
        self._active_files.clear()


# Глобальный экземпляр
_global_llm_logger: Optional[LLMCallLogger] = None


def get_llm_call_logger() -> LLMCallLogger:
    """Получение глобального логгера LLM вызовов."""
    global _global_llm_logger
    if _global_llm_logger is None:
        _global_llm_logger = LLMCallLogger()
    return _global_llm_logger


def init_llm_call_logger(log_dir: str = "logs/llm_calls", max_files: int = 100) -> LLMCallLogger:
    """Инициализация глобального логгера LLM вызовов."""
    global _global_llm_logger
    _global_llm_logger = LLMCallLogger(log_dir, max_files)
    return _global_llm_logger
