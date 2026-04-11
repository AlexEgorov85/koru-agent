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

# НОВОЕ: Глобальная DialogueHistory — хранится между запросами
_dialogue_history: Optional[Any] = None  # DialogueHistory (ленивый импорт)

_event_logs: List[Dict[str, Any]] = []
_log_lock = asyncio.Lock()

# НОВОЕ: Детальная история шагов агента
_agent_steps: List[Dict[str, Any]] = []
_steps_lock = asyncio.Lock()


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
    global _event_logs, _agent_steps
    _event_logs = []
    _agent_steps = []


def add_log(message: str, level: str = "info"):
    _event_logs.append({
        "time": asyncio.get_event_loop().time(),
        "level": level,
        "message": message
    })


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
    from core.infrastructure.event_bus.unified_event_bus import EventType

    config = get_config(profile=profile, data_dir=data_dir)
    _infra_ctx = InfrastructureContext(config)
    await _infra_ctx.initialize()

    _subscribe_to_events()

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

    # НОВОЕ: Подписка на детали шагов агента
    async def on_capability_selected(event):
        """Сохраняем информацию о выбранном capability."""
        if event.data:
            add_agent_step({
                "type": "capability_selected",
                "capability": event.data.get("capability", ""),
                "timestamp": event.timestamp.isoformat() if hasattr(event, 'timestamp') else None
            })

    async def on_action_performed(event):
        """Сохраняем информацию о выполненном действии."""
        if event.data:
            add_agent_step({
                "type": "action_performed",
                "action": event.data.get("action", ""),
                "parameters": event.data.get("parameters", {}),
                "result": event.data.get("result", ""),
                "timestamp": event.timestamp.isoformat() if hasattr(event, 'timestamp') else None
            })

    # НОВОЕ: Подписка на мысли агента
    async def on_agent_thinking(event):
        """Мысли агента - одна строка которая меняется."""
        if event.data:
            msg = event.data.get("message", "")
            add_log(msg, "thinking")

    event_bus.subscribe(EventType.AGENT_THINKING, on_agent_thinking)
    
    # Подписка на финальный ответ
    async def on_session_answer(event):
        msg = event.data.get("answer", "") if event.data else ""
        add_log(f"[SESSION_ANSWER] {msg}", "info")
    
    event_bus.subscribe(EventType.SESSION_ANSWER, on_session_answer)
    
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
    # НОВОЕ: LLM события для полноты логов
    event_bus.subscribe(EventType.LLM_CALL_STARTED, on_log)
    event_bus.subscribe(EventType.LLM_CALL_COMPLETED, on_log)
    event_bus.subscribe(EventType.LLM_CALL_FAILED, on_log)
    event_bus.subscribe(EventType.LLM_PROMPT_GENERATED, on_log)
    event_bus.subscribe(EventType.LLM_RESPONSE_RECEIVED, on_log)
    # НОВОЕ: Детали шагов агента
    event_bus.subscribe(EventType.CAPABILITY_SELECTED, on_capability_selected)
    event_bus.subscribe(EventType.ACTION_PERFORMED, on_action_performed)


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