"""
Логирование сессий агента.

Каждая сессия (запуск агента) записывается в отдельный файл:
logs/sessions/{session_id}.log

Содержит:
- Все LLM вызовы (промпты + ответы)
- Техническую информацию (ошибки, предупреждения, этапы выполнения)

USAGE:
    from core.infrastructure.logging.session_logger import SessionLogger, get_session_logger
    
    # При запуске агента
    logger = get_session_logger(session_id)
    await logger.log_llm_prompt(...)
    await logger.log_llm_response(...)
    logger.info("Техническое сообщение")
"""
import os
import logging
import logging.handlers
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class SessionLogger:
    """
    Логгер сессии агента.
    
    Все логи сессии пишутся в один файл:
    logs/sessions/{session_id}.log
    """

    def __init__(self, session_id: str, log_dir: str = "logs/sessions"):
        """
        Инициализация логгера сессии.

        ARGS:
            session_id: ID сессии
            log_dir: директория для логов сессий
        """
        self.session_id = session_id
        self.log_dir = log_dir
        self._logger: Optional[logging.Logger] = None
        self._file_handler: Optional[logging.FileHandler] = None
        
        # Создаём директорию
        Path(log_dir).mkdir(parents=True, exist_ok=True)

    def _setup_logger(self):
        """Настройка логгера."""
        if self._logger is not None:
            return
        
        filename = f"{self.session_id}.log"
        filepath = os.path.join(self.log_dir, filename)
        
        # Создаём логгер
        self._logger = logging.getLogger(f"session.{self.session_id}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers = []  # Очищаем обработчики
        
        # Файловый обработчик с ротацией
        self._file_handler = logging.handlers.RotatingFileHandler(
            filepath,
            maxBytes=52428800,  # 50MB
            backupCount=10,
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self._logger.addHandler(self._file_handler)
        
        # Отключаем распространение
        self._logger.propagate = False
        
        # Заголовок сессии
        self._logger.info("=" * 80)
        self._logger.info(f"AGENT SESSION STARTED | Session ID: {self.session_id}")
        self._logger.info(f"Timestamp: {datetime.now().isoformat()}")
        self._logger.info("=" * 80)

    def info(self, message: str, **kwargs):
        """Логирование INFO сообщения."""
        self._setup_logger()
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self._logger.info(f"{message} {extra}".strip())

    def debug(self, message: str, **kwargs):
        """Логирование DEBUG сообщения."""
        self._setup_logger()
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self._logger.debug(f"{message} {extra}".strip())

    def warning(self, message: str, **kwargs):
        """Логирование WARNING сообщения."""
        self._setup_logger()
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self._logger.warning(f"{message} {extra}".strip())

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Логирование ERROR сообщения."""
        self._setup_logger()
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self._logger.error(f"{message} {extra}".strip(), exc_info=exc_info)

    async def log_llm_prompt(self, component: str, phase: str, data: Dict[str, Any]):
        """
        Логирование LLM промпта.

        ARGS:
            component: компонент
            phase: фаза (think/act/observe)
            data: данные промпта
        """
        self._setup_logger()

        self._logger.debug("-" * 80)
        self._logger.debug(f"LLM PROMPT | Component: {component} | Phase: {phase}")
        self._logger.debug("-" * 80)
        self._logger.debug(f"Timestamp: {datetime.now().isoformat()}")
        self._logger.debug(f"Component: {component}")
        self._logger.debug(f"Phase: {phase}")

        if data.get('goal'):
            self._logger.debug(f"Goal: {data['goal']}")

        self._logger.debug(f"System prompt ({len(data.get('system_prompt', ''))} chars):")
        system_prompt = data.get('system_prompt', '')
        if len(system_prompt) > 500:
            self._logger.debug(system_prompt[:500] + "...")
        else:
            self._logger.debug(system_prompt)

        user_prompt = data.get('user_prompt', '')
        self._logger.debug(f"User prompt ({len(user_prompt)} chars):")
        # Логируем только первые 1000 символов чтобы не блокировать
        if len(user_prompt) > 1000:
            self._logger.debug(user_prompt[:1000] + f"... [ещё {len(user_prompt) - 1000} символов]")
        else:
            self._logger.debug(user_prompt)

        self._logger.debug(f"Temperature: {data.get('temperature', 0.0)} | Max tokens: {data.get('max_tokens', 1000)}")
        self._logger.debug("-" * 80)

    async def log_llm_response(self, component: str, phase: str, data: Dict[str, Any]):
        """
        Логирование LLM ответа.

        ARGS:
            component: компонент
            phase: фаза
            data: данные ответа
        """
        self._setup_logger()
        
        self._logger.info("-" * 80)
        self._logger.info(f"LLM RESPONSE | Component: {component} | Phase: {phase}")
        self._logger.info("-" * 80)
        self._logger.info(f"Timestamp: {datetime.now().isoformat()}")
        
        response = data.get('response', {})
        if isinstance(response, dict):
            import json
            self._logger.info("Response (JSON):")
            self._logger.info(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            self._logger.info(f"Response ({type(response).__name__}):")
            self._logger.info(str(response))
        
        self._logger.info("-" * 80)

    def log_event(self, event_type: str, message: str, **kwargs):
        """
        Логирование произвольного события.

        ARGS:
            event_type: тип события (COMPONENT_INIT, SKILL_EXEC, OBSERVATION, и т.д.)
            message: сообщение
            **kwargs: дополнительные данные
        """
        self._setup_logger()
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        self._logger.info(f"[{event_type}] {message} {extra}".strip())

    def log_component_init(self, component_type: str, component_name: str, **kwargs):
        """Логирование инициализации компонента."""
        self.log_event("COMPONENT_INIT", f"{component_type}.{component_name}", **kwargs)

    def log_component_result(self, component_type: str, component_name: str, result: Any, **kwargs):
        """Логирование результата компонента."""
        self._setup_logger()
        if isinstance(result, dict):
            import json
            self._logger.info(f"[COMPONENT_RESULT] {component_type}.{component_name}")
            self._logger.info(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:2000])
        else:
            self.log_event("COMPONENT_RESULT", f"{component_type}.{component_name}", result=str(result)[:500], **kwargs)

    def log_observation(self, observation: str, **kwargs):
        """Логирование наблюдения."""
        self._setup_logger()
        self._logger.info(f"[OBSERVATION] {observation[:1000]}")
        if kwargs:
            self._logger.info(f"Details: {kwargs}")

    def log_action(self, action: str, parameters: Dict[str, Any], **kwargs):
        """Логирование действия."""
        self._setup_logger()
        self._logger.info(f"[ACTION] {action}")
        if parameters:
            import json
            self._logger.info(f"Parameters: {json.dumps(parameters, ensure_ascii=False, indent=2, default=str)[:1000]}")

    def close(self):
        """Завершение сессии."""
        if self._logger:
            self._logger.info("=" * 80)
            self._logger.info(f"AGENT SESSION ENDED | Session ID: {self.session_id}")
            self._logger.info("=" * 80)
            
            for handler in self._logger.handlers:
                handler.close()
            self._logger.handlers = []

    @property
    def filepath(self) -> Optional[str]:
        """Путь к файлу лога."""
        if self._logger:
            return os.path.join(self.log_dir, f"{self.session_id}.log")
        return None


# Глобальные сессии
_active_sessions: Dict[str, SessionLogger] = {}


def get_session_logger(session_id: str) -> SessionLogger:
    """
    Получение или создание логгера сессии.

    ARGS:
        session_id: ID сессии

    RETURNS:
        логгер сессии
    """
    if session_id not in _active_sessions:
        _active_sessions[session_id] = SessionLogger(session_id)
    return _active_sessions[session_id]


def close_session_logger(session_id: str):
    """
    Закрытие логгера сессии.

    ARGS:
        session_id: ID сессии
    """
    if session_id in _active_sessions:
        _active_sessions[session_id].close()
        del _active_sessions[session_id]


def cleanup_old_sessions(max_sessions: int = 100, log_dir: str = "logs/sessions"):
    """
    Очистка старых сессий.

    ARGS:
        max_sessions: максимальное количество хранимых сессий
        log_dir: директория логов
    """
    try:
        files = sorted(
            Path(log_dir).glob("*.log"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        # Удаляем файлы сверх лимита
        for old_file in files[max_sessions:]:
            old_file.unlink()
    except Exception:
        pass
