"""
Хранилище контекстов — глобальные переменные для Streamlit приложения.

Контексты создаются один раз при поднятии и живут в памяти
пока работает сервер. Каждый запрос создаёт новый Agent из app_ctx.
"""

import asyncio
from typing import Optional, List, Dict, Any
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

_infra_ctx: Optional[InfrastructureContext] = None
_app_ctx: Optional[ApplicationContext] = None
_is_ready: bool = False

# НОВОЕ: Глобальный SessionContext для сохранения истории диалога между запросами
_session_ctx: Optional[Any] = None  # SessionContext (ленивый импорт)

_event_logs: List[Dict[str, Any]] = []
_log_lock = asyncio.Lock()


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


def get_logs() -> List[Dict[str, Any]]:
    return _event_logs.copy()


def clear_logs():
    global _event_logs
    _event_logs = []


def add_log(message: str, level: str = "info"):
    _event_logs.append({
        "time": asyncio.get_event_loop().time(),
        "level": level,
        "message": message
    })


async def init_contexts(profile: str = "prod", data_dir: str = "data"):
    global _infra_ctx, _app_ctx, _is_ready

    from core.config import get_config
    from core.config.app_config import AppConfig
    from core.infrastructure.event_bus.unified_event_bus import EventType

    config = get_config(profile=profile, data_dir=data_dir)
    _infra_ctx = InfrastructureContext(config)
    await _infra_ctx.initialize()

    _subscribe_to_events()

    app_config = AppConfig.from_discovery(
        profile=profile,
        data_dir=data_dir,
        discovery=_infra_ctx.resource_discovery
    )
    _app_ctx = ApplicationContext(
        infrastructure_context=_infra_ctx,
        config=app_config,
        profile=profile
    )
    await _app_ctx.initialize()

    _is_ready = True


def _subscribe_to_events():
    if not _infra_ctx or not _infra_ctx.event_bus:
        return

    from core.infrastructure.event_bus.unified_event_bus import EventType

    event_bus = _infra_ctx.event_bus

    async def on_log(event):
        msg = event.data.get("message", "") if event.data else ""
        level = "info"
        if "error" in str(event.event_type).lower():
            level = "error"
        elif "warning" in str(event.event_type).lower():
            level = "warning"
        add_log(msg, level)

    async def on_user_result(event):
        msg = event.data.get("message", "") if event.data else ""
        add_log(f"[RESULT] {msg}", "info")

    async def on_progress(event):
        msg = event.data.get("message", "") if event.data else ""
        add_log(f"[PROGRESS] {msg}", "info")

    async def on_skill(event):
        skill = event.data.get("skill_name", "") if event.data else ""
        add_log(f"[SKILL] {skill} выполнен", "info")

    async def on_tool(event):
        tool = event.data.get("tool_name", "") if event.data else ""
        add_log(f"[TOOL] {tool} вызван", "info")

    event_bus.subscribe(EventType.LOG_INFO, on_log)
    event_bus.subscribe(EventType.INFO, on_log)
    event_bus.subscribe(EventType.LOG_WARNING, on_log)
    event_bus.subscribe(EventType.WARNING, on_log)
    event_bus.subscribe(EventType.LOG_ERROR, on_log)
    event_bus.subscribe(EventType.ERROR_OCCURRED, on_log)
    event_bus.subscribe(EventType.USER_RESULT, on_user_result)
    event_bus.subscribe(EventType.USER_PROGRESS, on_progress)
    event_bus.subscribe(EventType.SKILL_EXECUTED, on_skill)
    event_bus.subscribe(EventType.TOOL_CALL, on_tool)


async def shutdown_contexts():
    global _infra_ctx, _app_ctx, _is_ready, _session_ctx

    if _app_ctx:
        await _app_ctx.shutdown()
        _app_ctx = None

    if _infra_ctx:
        await _infra_ctx.shutdown()
        _infra_ctx = None

    # Сбрасываем session context при остановке системы
    _session_ctx = None
    _is_ready = False


def is_ready() -> bool:
    return _is_ready and _app_ctx is not None


def get_app_context() -> Optional[ApplicationContext]:
    return _app_ctx


def get_or_create_session_context() -> Any:
    """
    Получить существующий SessionContext или создать новый.
    
    SessionContext хранит DialogueHistory, которая сохраняется между запросами.
    """
    global _session_ctx
    if _session_ctx is None:
        from core.session_context.session_context import SessionContext
        _session_ctx = SessionContext(session_id="web_ui_session", agent_id="agent_001")
    return _session_ctx


def reset_session_context():
    """Сбросить SessionContext (начать новый диалог с чистой историей)."""
    global _session_ctx
    _session_ctx = None


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