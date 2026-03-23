"""
Обработчик логов для сессий с новой структурой.

СТРУКТУРА:
logs/sessions/
└── YYYY-MM-DD_HH-MM-SS/     ← Дата и время старта агента
    ├── session.log          ← Все общие логи сессии (JSONL)
    ├── llm.jsonl            ← LLM промпты/ответы
    └── metrics.jsonl        ← Метрики
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from core.infrastructure.event_bus.unified_event_bus import Event, EventType, UnifiedEventBus


class SessionLogHandler:
    """
    Обработчик для записи логов сессии в файлы.

    FEATURES:
    - Папка с датой/временем вместо session_id
    - Разделение на session.log, llm.jsonl, metrics.jsonl
    - Автоматическое создание структуры
    - Асинхронная запись
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        base_log_dir: Path = None,
        session_id: str = None,
        agent_id: str = None
    ):
        self.event_bus = event_bus
        self.base_log_dir = base_log_dir or Path("logs/sessions")
        self.session_id = session_id
        self.agent_id = agent_id
        
        # Создаём имя папки на основе текущего времени
        self.session_folder = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_path = self.base_log_dir / self.session_folder

        # Пути к файлам
        self.session_log_path = self.session_path / "session.log"
        self.llm_log_path = self.session_path / "llm.jsonl"
        self.metrics_log_path = self.session_path / "metrics.jsonl"

        # Создаём директорию
        self.session_path.mkdir(parents=True, exist_ok=True)
        
        # Флаги инициализации
        self._initialized = False
        self._lock = asyncio.Lock()
        
        # Подписка на события
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """Подписка на события для логирования."""
        # Подписка на события БЕЗ фильтрации по session_id (получать из ВСЕХ сессий)
        
        # Общие логи
        self.event_bus.subscribe(EventType.LOG_INFO, self._on_log_event)
        self.event_bus.subscribe(EventType.LOG_DEBUG, self._on_log_event)
        self.event_bus.subscribe(EventType.LOG_WARNING, self._on_log_event)
        self.event_bus.subscribe(EventType.LOG_ERROR, self._on_log_event)

        # LLM события (все типы!)
        self.event_bus.subscribe(EventType.LLM_PROMPT_GENERATED, self._on_llm_prompt)
        self.event_bus.subscribe(EventType.LLM_RESPONSE_RECEIVED, self._on_llm_response)
        self.event_bus.subscribe(EventType.LLM_CALL_STARTED, self._on_llm_call)
        self.event_bus.subscribe(EventType.LLM_CALL_COMPLETED, self._on_llm_call)

        # Метрики
        self.event_bus.subscribe(EventType.METRIC_COLLECTED, self._on_metric)

    async def _on_log_event(self, event: Event):
        """Обработка логов (INFO, DEBUG, WARNING, ERROR)."""
        await self._write_to_file(self.session_log_path, event)

    async def _on_llm_prompt(self, event: Event):
        """Обработка LLM промптов."""
        await self._write_to_file(self.llm_log_path, event)

    async def _on_llm_response(self, event: Event):
        """Обработка LLM ответов."""
        await self._write_to_file(self.llm_log_path, event)

    async def _on_llm_call(self, event: Event):
        """Обработка LLM вызовов (STARTED/COMPLETED)."""
        await self._write_to_file(self.llm_log_path, event)

    async def _on_metric(self, event: Event):
        """Обработка метрик."""
        await self._write_to_file(self.metrics_log_path, event)

    async def _write_to_file(self, file_path: Path, event: Event):
        """Асинхронная запись события в файл."""
        async with self._lock:
            try:
                # Создаём файл если не существует
                if not file_path.exists():
                    file_path.touch()
                
                # Используем session_id из события если есть, иначе из self
                session_id = getattr(event, 'session_id', None) or self.session_id
                agent_id = getattr(event, 'agent_id', None) or self.agent_id
                
                event_data = {
                    "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                    "event_type": event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
                    "source": event.source,
                    "message": event.data.get("message", "") if event.data else "",
                    "level": event.data.get("level", "INFO") if event.data else "INFO",
                    "session_id": session_id,
                    "agent_id": agent_id,
                }
                
                # Добавляем дополнительные данные из event.data
                if event.data:
                    for key, value in event.data.items():
                        if key not in event_data and isinstance(value, (str, int, float, bool, type(None))):
                            event_data[key] = value
                
                # Запись в файл
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(event_data, ensure_ascii=False) + '\n')
                    
            except Exception as e:
                # Тихая ошибка чтобы не ломать основную систему
                pass

    def get_session_info(self) -> Dict[str, Any]:
        """Информация о сессии."""
        return {
            "session_folder": str(self.session_path),
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "created_at": self.session_folder,
            "session_log": str(self.session_log_path),
            "llm_log": str(self.llm_log_path),
            "metrics_log": str(self.metrics_log_path),
        }

    async def shutdown(self):
        """Завершение работы обработчика."""
        # Можно добавить финализацию если нужно
        pass


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_session_log_handler(
    event_bus: UnifiedEventBus,
    session_id: str = None,
    agent_id: str = None,
    base_log_dir: Path = None
) -> SessionLogHandler:
    """
    Создание обработчика логов для сессии.

    ARGS:
    - event_bus: шина событий
    - session_id: ID сессии (опционально)
    - agent_id: ID агента (опционально)
    - base_log_dir: базовая директория для логов

    RETURNS:
    - SessionLogHandler для записи логов
    """
    return SessionLogHandler(
        event_bus=event_bus,
        session_id=session_id,
        agent_id=agent_id,
        base_log_dir=base_log_dir
    )
