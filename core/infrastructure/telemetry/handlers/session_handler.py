"""
Session Log Handler — запись логов сессии в файлы.

СТРУКТУРА:
logs/sessions/
└── YYYY-MM-DD_HH-MM-SS/
    └── session.jsonl  ← ВСЕ события в одном файле
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

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
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ):
        self.event_bus = event_bus
        self.base_log_dir = base_log_dir or Path("logs/sessions")
        self.session_id = session_id
        self.agent_id = agent_id

        # Папка сессии
        self.session_folder = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_path = self.base_log_dir / self.session_folder
        self.session_log_path = self.session_path / "session.jsonl"

        # Создание директории
        self.session_path.mkdir(parents=True, exist_ok=True)

        # Lock для асинхронной записи
        self._lock = asyncio.Lock()

        # Подписка на события
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """Подписка на все события для логирования."""
        events = [
            # Сессии
            EventType.SESSION_STARTED,
            EventType.SESSION_COMPLETED,
            EventType.SESSION_FAILED,
            # Агенты
            EventType.AGENT_STARTED,
            EventType.AGENT_COMPLETED,
            # Логи
            EventType.LOG_INFO,
            EventType.LOG_DEBUG,
            EventType.LOG_WARNING,
            EventType.LOG_ERROR,
            # Прямые события (для совместимости)
            EventType.INFO,
            EventType.DEBUG,
            EventType.WARNING,
            EventType.ERROR_OCCURRED,
            # LLM
            EventType.LLM_CALL_STARTED,
            EventType.LLM_CALL_COMPLETED,
            EventType.LLM_CALL_FAILED,
            EventType.LLM_PROMPT_GENERATED,
            EventType.LLM_RESPONSE_RECEIVED,
            # Выполнение
            EventType.CAPABILITY_SELECTED,
            EventType.SKILL_EXECUTED,
            EventType.ACTION_PERFORMED,
            # Метрики
            EventType.METRIC_COLLECTED,
        ]

        for event_type in events:
            self.event_bus.subscribe(event_type, self._on_event)

    async def _on_event(self, event: Event):
        """Обработка любого события."""
        await self._write_to_file(event)

    async def _write_to_file(self, event: Event):
        """Запись события в файл."""
        async with self._lock:
            try:
                session_id = getattr(event, 'session_id', None) or self.session_id
                agent_id = getattr(event, 'agent_id', None) or self.agent_id

                event_data = {
                    "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                    "event_type": event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
                    "session_id": session_id,
                    "agent_id": agent_id,
                }

                # Добавление данных из event.data
                if event.data:
                    for key, value in event.data.items():
                        if key not in event_data and isinstance(value, (str, int, float, bool, type(None))):
                            event_data[key] = value

                # Запись
                with open(self.session_log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(event_data, ensure_ascii=False) + '\n')

            except Exception as e:
                # Временное логирование для отладки — удалить после фиксации проблемы
                import sys
                print(f"[SessionLogHandler] Ошибка записи события {event.event_type}: {e}", file=sys.stderr, flush=True)

    async def shutdown(self):
        """Завершение работы."""
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
        - Список записей лога
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

                        # Фильтрация
                        if event_types:
                            event_type = record.get('event_type', '')
                            if not any(et in event_type for et in event_types):
                                continue

                        if capability and record.get('capability') != capability:
                            continue

                        logs.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return logs

    async def get_error_logs(self, capability: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Получение логов ошибок."""
        return await self.get_logs(
            event_types=['error', 'failed', 'ERROR', 'FAILED'],
            capability=capability,
            limit=limit
        )

    def get_session_info(self) -> Dict[str, Any]:
        """Информация о сессии."""
        return {
            "session_folder": str(self.session_path),
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "created_at": self.session_folder,
            "session_log": str(self.session_log_path),
        }


__all__ = ['SessionLogHandler']
