"""
Хранилище контекстов — глобальные переменные для Streamlit приложения.

Контексты создаются один раз при поднятии и живут в памяти
пока работает сервер. Каждый запрос создаёт новый Agent из app_ctx.

МЕХАНИЗМ ЛОГИРОВ ДЛЯ UI:
- UI читает лог-файл агента в реальном времени (tail-подобно)
- Парсит строки вида: "TIMESTAMP | LEVEL    | EVENT_TYPE | COMPONENT | MESSAGE"
- Фильтрует по LogEventType для отображения thinking/progress/tool_call и т.д.
"""

import asyncio
import threading
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

_infra_ctx: Optional[InfrastructureContext] = None
_app_ctx: Optional[ApplicationContext] = None
_is_ready: bool = False

# НОВОЕ: Глобальная DialogueHistory — хранится между запросами
_dialogue_history: Optional[Any] = None  # DialogueHistory (ленивый импорт)

# НОВОЕ: Путь к лог-файлу последнего агента
_agent_log_path: Optional[Path] = None
_log_file_lock = threading.Lock()

# НОВОЕ: Позиция чтения (для tail-режима — не читать заново)
_last_log_position: int = 0
_position_lock = threading.Lock()

# НОВОЕ: Детальная история шагов агента
_agent_steps: List[Dict[str, Any]] = []
_steps_lock = threading.Lock()


def get_status() -> dict:
    return {
        "infra_ready": _infra_ctx is not None,
        "app_ready": _app_ctx is not None,
        "is_ready": _is_ready
    }


def get_event_bus():
    if _infra_ctx:
        return _infra_ctx.event_bus
    return None


def get_agent_log_path() -> Optional[Path]:
    """Получить путь к лог-файлу текущего агента."""
    with _log_file_lock:
        return _agent_log_path


def set_agent_log_path(path: Path):
    """Установить путь к лог-файлу агента."""
    global _agent_log_path, _last_log_position
    with _log_file_lock:
        _agent_log_path = path
    with _position_lock:
        _last_log_position = 0


def get_logs() -> List[Dict[str, Any]]:
    """
    Прочитать новые записи из лог-файла агента (tail-режим).

    Возвращает список записей с полями:
    - time: timestamp строка
    - level: DEBUG/INFO/WARNING/ERROR
    - event_type: LogEventType value (например "AGENT_THINKING")
    - component: имя компонента
    - message: текст сообщения
    - raw: полная строка (для fallback)
    """
    log_path = get_agent_log_path()
    if not log_path or not log_path.exists():
        return []

    entries = []
    global _last_log_position

    with _position_lock:
        start_pos = _last_log_position

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            # Если файл меньше чем start_pos — значит это новый файл
            f.seek(0, 2)  # seek to end
            file_size = f.tell()
            if file_size < start_pos:
                start_pos = 0

            f.seek(start_pos)
            new_content = f.read()
            end_pos = f.tell()

            if not new_content:
                return []

            # Парсим строки
            for line in new_content.splitlines():
                entry = _parse_log_line(line)
                if entry:
                    entries.append(entry)

            with _position_lock:
                _last_log_position = end_pos

    except (FileNotFoundError, IOError):
        return []

    return entries


# Формат лога: "2026-04-12 14:30:00,123456 | INFO     | AGENT_THINKING     | agent.agent_001          | Сообщение"
_LOG_LINE_RE = re.compile(
    r'^(?P<time>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+)\s*\|\s*'
    r'(?P<level>\w+)\s*\|\s*'
    r'(?P<event_type>[^|]+?)\s*\|\s*'
    r'(?P<component>[^|]+?)\s*\|\s*'
    r'(?P<message>.+)$'
)


def _parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Парсинг одной строки лога."""
    line = line.strip()
    if not line:
        return None

    m = _LOG_LINE_RE.match(line)
    if not m:
        # Fallback: просто строка без структуры
        return {
            "time": "",
            "level": "info",
            "event_type": "",
            "component": "",
            "message": line,
            "raw": line,
        }

    event_type = m.group("event_type").strip()
    level_raw = m.group("level").strip().upper()

    # Нормализация уровня
    level = "info"
    if "ERROR" in level_raw or "CRITICAL" in level_raw:
        level = "error"
    elif "WARNING" in level_raw:
        level = "warning"
    elif "DEBUG" in level_raw:
        level = "debug"

    # Специальные event_type для UI
    if event_type == "-":
        ui_level = level
    elif "THINKING" in event_type:
        level = "thinking"
    elif "ERROR" in event_type:
        level = "error"
    elif "WARNING" in event_type:
        level = "warning"

    return {
        "time": m.group("time"),
        "level": level,
        "event_type": event_type,
        "component": m.group("component").strip(),
        "message": m.group("message").strip(),
        "raw": line,
    }


def clear_logs():
    """Сброс позиции чтения лога."""
    with _position_lock:
        global _last_log_position
        _last_log_position = 0
    global _agent_steps
    with _steps_lock:
        _agent_steps = []


def add_log(message: str, level: str = "info"):
    """
    Добавление записи в _event_logs (устаревший метод, для обратной совместимости).
    Больше не используется — логи читаются из файла.
    """
    pass  # stub для обратной совместимости


def populate_agent_steps():
    """
    Заполнить _agent_steps из лог-файла.

    Парсит лог-файл и извлекает события AGENT_DECISION, TOOL_RESULT, TOOL_ERROR
    для отображения хода мышления агента в UI.
    """
    log_path = get_agent_log_path()
    if not log_path or not log_path.exists():
        return

    steps = []
    step_counter = 0

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                entry = _parse_log_line(line)
                if not entry:
                    continue

                evt = entry.get("event_type", "")
                msg = entry.get("message", "")
                time_str = entry.get("time", "")

                #capability selection (ШАГ N + AGENT_DECISION)
                if "AGENT_DECISION" in evt and "Capability:" in msg:
                    step_counter += 1
                    # Парсим: "🎯 Capability: check_result.execute_script | reasoning"
                    cap_name = ""
                    reasoning = ""
                    if "|" in msg:
                        parts = msg.split("|", 1)
                        cap_part = parts[0].replace("🎯 Capability:", "").strip()
                        cap_name = cap_part
                        reasoning = parts[1].strip() if len(parts) > 1 else ""
                    else:
                        cap_name = msg.replace("🎯 Capability:", "").strip()

                    steps.append({
                        "type": "capability_selected",
                        "capability": cap_name,
                        "reasoning": reasoning,
                        "step": step_counter,
                        "timestamp": time_str,
                    })

                # tool result
                elif "TOOL_RESULT" in evt:
                    # Парсим: "✅ check_result.execute_script → COMPLETED"
                    action = ""
                    status = ""
                    if "→" in msg:
                        parts = msg.split("→", 1)
                        action = parts[0].replace("✅", "").strip()
                        status = parts[1].strip()
                    else:
                        action = msg.replace("✅", "").strip()
                        status = "COMPLETED"

                    steps.append({
                        "type": "action_performed",
                        "action": action,
                        "parameters": {},
                        "status": status,
                        "error": None,
                        "step": step_counter,
                        "timestamp": time_str,
                    })

                # tool error
                elif "TOOL_ERROR" in evt:
                    # Парсим: "❌ check_result.execute_script → FAILED: error msg"
                    action = ""
                    error = ""
                    if "→" in msg:
                        parts = msg.split("→", 1)
                        action = parts[0].replace("❌", "").strip()
                        error = parts[1].strip()
                    else:
                        action = msg.replace("❌", "").strip()
                        error = msg

                    steps.append({
                        "type": "action_performed",
                        "action": action,
                        "parameters": {},
                        "status": "FAILED",
                        "error": error,
                        "step": step_counter,
                        "timestamp": time_str,
                    })

        with _steps_lock:
            _agent_steps.clear()
            _agent_steps.extend(steps)

    except (FileNotFoundError, IOError):
        pass


def add_agent_step(step_data: Dict[str, Any]):
    """Добавить детальную информацию о шаге агента."""
    _agent_steps.append(step_data)


def get_agent_steps() -> List[Dict[str, Any]]:
    """Получить полную историю шагов агента."""
    return _agent_steps.copy()


async def init_contexts(profile: str = "prod", data_dir: str = "data"):
    global _infra_ctx, _app_ctx, _is_ready

    from core.config import get_config
    from core.config.app_config import AppConfig

    config = get_config(profile=profile, data_dir=data_dir)
    _infra_ctx = InfrastructureContext(config)
    await _infra_ctx.initialize()

    # Проверка session_handler
    if _infra_ctx.session_handler:
        session_info = _infra_ctx.session_handler.get_session_info()
        print(f"[agent_holder] SessionLogHandler инициализирован: {session_info['session_log']}")
    else:
        print("[agent_holder] WARNING: SessionLogHandler НЕ найден!")

    app_config = AppConfig.from_discovery(
        profile=profile,
        data_dir=data_dir
    )
    _app_ctx = ApplicationContext(
        infrastructure_context=_infra_ctx,
        config=app_config,
        profile=profile
    )
    await _app_ctx.initialize()

    # Проверка LLMOrchestrator
    if _app_ctx.llm_orchestrator:
        print(f"[agent_holder] LLMOrchestrator инициализирован: {type(_app_ctx.llm_orchestrator)}")
    else:
        print("[agent_holder] WARNING: LLMOrchestrator НЕ инициализирован!")

    _is_ready = True


async def shutdown_contexts():
    global _infra_ctx, _app_ctx, _is_ready, _dialogue_history

    if _app_ctx:
        await _app_ctx.shutdown()
        _app_ctx = None

    if _infra_ctx:
        await _infra_ctx.shutdown()
        _infra_ctx = None

    # Сбрасываем историю при остановке системы
    _dialogue_history = None
    _is_ready = False

    # Сбрасываем флаг обработки
    import streamlit as st
    if "processing" in st.session_state:
        st.session_state.processing = False


def is_ready() -> bool:
    return _is_ready and _app_ctx is not None


def get_app_context() -> Optional[ApplicationContext]:
    return _app_ctx


def get_shared_dialogue_history() -> Any:
    """
    Получить общую DialogueHistory, которая сохраняется между запросами.
    
    Каждый новый агент копирует эту историю в свой SessionContext.
    """
    global _dialogue_history
    if _dialogue_history is None:
        from core.session_context.dialogue_context import DialogueHistory
        _dialogue_history = DialogueHistory(max_rounds=10)
    return _dialogue_history


def reset_dialogue_history():
    """Сбросить историю диалога (начать чистый разговор)."""
    global _dialogue_history
    _dialogue_history = None


def get_system_info() -> dict:
    """Получение информации о системе для админки через LifecycleManager."""
    if not _infra_ctx:
        return {"error": "InfrastructureContext not initialized"}

    try:
        # Используем новый метод get_dashboard_info()
        if hasattr(_infra_ctx, "lifecycle_manager"):
            return _infra_ctx.lifecycle_manager.get_dashboard_info()
        else:
            return {"error": "LifecycleManager not available"}
    except Exception as e:
        return {"error": str(e)}