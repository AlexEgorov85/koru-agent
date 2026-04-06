"""
Хранилище контекстов — глобальные переменные для Streamlit приложения.

Контексты создаются один раз при поднятии и живут в памяти
пока работает сервер. Каждый запрос создаёт новый Agent из app_ctx.
"""

from typing import Optional
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext

_infra_ctx: Optional[InfrastructureContext] = None
_app_ctx: Optional[ApplicationContext] = None
_is_ready: bool = False


def get_status() -> dict:
    return {
        "infra_ready": _infra_ctx is not None,
        "app_ready": _app_ctx is not None,
        "is_ready": _is_ready
    }


async def init_contexts(profile: str = "sandbox", data_dir: str = "data"):
    global _infra_ctx, _app_ctx, _is_ready

    from core.config import get_config
    from core.config.app_config import AppConfig

    config = get_config(profile=profile, data_dir=data_dir)
    _infra_ctx = InfrastructureContext(config)
    await _infra_ctx.initialize()

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


async def shutdown_contexts():
    global _infra_ctx, _app_ctx, _is_ready

    if _app_ctx:
        await _app_ctx.shutdown()
        _app_ctx = None

    if _infra_ctx:
        await _infra_ctx.shutdown()
        _infra_ctx = None

    _is_ready = False


def is_ready() -> bool:
    return _is_ready and _app_ctx is not None


def get_app_context() -> Optional[ApplicationContext]:
    return _app_ctx