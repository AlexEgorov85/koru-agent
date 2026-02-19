"""
Утилиты для Agent_v5.

Импортируйте отсюда все утилиты:
    from core.utils import LifecycleManager, handle_errors
"""

from .lifecycle import LifecycleManager, DependencyResolver, InputValidator, RestartableComponent
from .error_handling import (
    handle_errors,
    log_errors,
    safe_execute,
    safe_execute_async,
    ErrorContext,
    ErrorCollector
)
from .module_reloader import safe_reload_component, safe_reload_component_with_module_reload

__all__ = [
    # Lifecycle
    "LifecycleManager",
    "DependencyResolver",
    "InputValidator",
    "RestartableComponent",
    
    # Error handling
    "handle_errors",
    "log_errors",
    "safe_execute",
    "safe_execute_async",
    "ErrorContext",
    "ErrorCollector",
    
    # Module reloader
    "safe_reload_component",
    "safe_reload_component_with_module_reload",
]
