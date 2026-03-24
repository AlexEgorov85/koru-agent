"""
Обработчик логов для сессий.

СТРУКТУРА:
logs/sessions/
└── YYYY-MM-DD_HH-MM-SS/     ← Дата и время старта агента
    └── session.jsonl        ← ВСЕ события в одном файле (JSONL)

Поля:
- timestamp: время события
- event_type: тип события
- session_id: ID сессии
- agent_id: ID агента
- capability: название способности (если есть)
- data: произвольные данные события
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from core.infrastructure.event_bus.unified_event_bus import Event, EventType, UnifiedEventBus


class SessionLogHandler:
    """
    Обработчик для записи логов сессии в один файл.

    FEATURES:
    - Папка с датой/временем
    - Один файл session.jsonl для всех событий
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

        # Один файл для всех событий
        self.session_log_path = self.session_path / "session.jsonl"

        # Создаём директорию
        self.session_path.mkdir(parents=True, exist_ok=True)
        
        # Флаги инициализации
        self._initialized = False
        self._lock = asyncio.Lock()
        
        # Подписка на события
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """Подписка на все события для логирования в один файл."""
        # События сессии и агента
        self.event_bus.subscribe(EventType.SESSION_STARTED, self._on_any_event)
        self.event_bus.subscribe(EventType.SESSION_COMPLETED, self._on_any_event)
        self.event_bus.subscribe(EventType.SESSION_FAILED, self._on_any_event)
        
        self.event_bus.subscribe(EventType.AGENT_STARTED, self._on_any_event)
        self.event_bus.subscribe(EventType.AGENT_COMPLETED, self._on_any_event)
        
        # Общие логи
        self.event_bus.subscribe(EventType.LOG_INFO, self._on_any_event)
        self.event_bus.subscribe(EventType.LOG_DEBUG, self._on_any_event)
        self.event_bus.subscribe(EventType.LOG_WARNING, self._on_any_event)
        self.event_bus.subscribe(EventType.LOG_ERROR, self._on_any_event)

        # LLM события
        self.event_bus.subscribe(EventType.LLM_PROMPT_GENERATED, self._on_any_event)
        self.event_bus.subscribe(EventType.LLM_RESPONSE_RECEIVED, self._on_any_event)
        self.event_bus.subscribe(EventType.LLM_CALL_STARTED, self._on_any_event)
        self.event_bus.subscribe(EventType.LLM_CALL_COMPLETED, self._on_any_event)
        self.event_bus.subscribe(EventType.LLM_CALL_FAILED, self._on_any_event)

        # Capability события
        self.event_bus.subscribe(EventType.CAPABILITY_SELECTED, self._on_any_event)
        self.event_bus.subscribe(EventType.SKILL_EXECUTED, self._on_any_event)
        self.event_bus.subscribe(EventType.ACTION_PERFORMED, self._on_any_event)

        # Метрики
        self.event_bus.subscribe(EventType.METRIC_COLLECTED, self._on_any_event)

        # Self-improvement события
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_STARTED, self._on_any_event)
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_THINKING_STARTED, self._on_any_event)
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_THINKING_COMPLETED, self._on_any_event)
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_DECISION, self._on_any_event)
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_ACTION_STARTED, self._on_any_event)
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_ACTION_COMPLETED, self._on_any_event)
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_REPORT, self._on_any_event)
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_COMPLETED, self._on_any_event)
        self.event_bus.subscribe(EventType.SELF_IMPROVEMENT_FAILED, self._on_any_event)

        # Оптимизация
        self.event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_STARTED, self._on_any_event)
        self.event_bus.subscribe(EventType.OPTIMIZATION_CYCLE_COMPLETED, self._on_any_event)
        self.event_bus.subscribe(EventType.OPTIMIZATION_FAILED, self._on_any_event)

        # Бенчмарки
        self.event_bus.subscribe(EventType.BENCHMARK_STARTED, self._on_any_event)
        self.event_bus.subscribe(EventType.BENCHMARK_COMPLETED, self._on_any_event)
        self.event_bus.subscribe(EventType.BENCHMARK_FAILED, self._on_any_event)

    async def _on_any_event(self, event: Event):
        """Обработка любого события - запись в один файл."""
        await self._write_to_file(self.session_log_path, event)

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
                    "session_id": session_id,
                    "agent_id": agent_id,
                }
                
                # Добавляем данные из event.data
                if event.data:
                    for key, value in event.data.items():
                        if key not in event_data and isinstance(value, (str, int, float, bool, type(None))):
                            event_data[key] = value
                
                # Извлекаем capability из source если есть
                if event.source and '.' in event.source:
                    parts = event.source.split('.')
                    if len(parts) >= 2:
                        event_data['capability'] = event.source
                
                # Запись в файл
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(event_data, ensure_ascii=False) + '\n')
                    
            except Exception:
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
        }

    async def shutdown(self):
        """Завершение работы обработчика."""
        # Можно добавить финализацию если нужно
        pass

    async def get_logs(
        self,
        event_types: Optional[List[str]] = None,
        capability: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Чтение логов из session.jsonl.

        ARGS:
        - event_types: фильтр по типам событий
        - capability: фильтр по способности
        - limit: максимальное количество записей

        RETURNS:
        - List[Dict]: список записей лога
        """
        logs = []
        if not self.session_log_path.exists():
            return logs

        try:
            with open(self.session_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if len(logs) >= limit:
                        break
                    try:
                        record = json.loads(line.strip())
                        
                        # Фильтрация по event_type
                        if event_types:
                            event_type = record.get('event_type', '')
                            if not any(et in event_type for et in event_types):
                                continue
                        
                        # Фильтрация по capability
                        if capability:
                            if record.get('capability') != capability:
                                continue
                        
                        logs.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return logs

    async def get_error_logs(
        self,
        capability: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получение логов ошибок.

        ARGS:
        - capability: фильтр по способности
        - limit: максимальное количество записей

        RETURNS:
        - List[Dict]: список записей с ошибками
        """
        # Фильтр по event_type: содержит 'error', 'failed' или level='ERROR'
        return await self.get_logs(
            event_types=['error', 'failed', 'ERROR', 'FAILED'],
            capability=capability,
            limit=limit
        )


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
