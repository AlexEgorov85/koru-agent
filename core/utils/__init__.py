"""
Утилиты для Agent_v5.

Импортируйте отсюда все утилиты:
    from core.utils import handle_errors

LIFECYCLE:
    Для управления жизненным циклом компонентов используйте:
    from core.components.lifecycle import LifecycleMixin, ComponentState
"""

from .error_handling import (
    handle_errors,
    log_errors,
    safe_execute,
    safe_execute_async,
    ErrorContext,
    ErrorCollector
)
from .module_reloader import safe_reload_component_with_module_reload

__all__ = [
    # Error handling
    "handle_errors",
    "log_errors",
    "safe_execute",
    "safe_execute_async",
    "ErrorContext",
    "ErrorCollector",

    # Module reloader
    "safe_reload_component_with_module_reload",
]
