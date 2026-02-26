"""
Модуль безопасности.

КОМПОНЕНТЫ:
- security_manager: централизованная система безопасности
- authorizer: RBAC авторизация
- user_context: контекст пользователя
- validators: валидаторы для разных типов ресурсов

USAGE:
```python
from core.security import (
    SecurityManager,
    SecurityValidator,
    SQLSecurityValidator,
    FileSecurityValidator,
    SecurityResourceType,
    get_security_manager,
)

# Валидация SQL
security_manager = get_security_manager()
await security_manager.validate(
    resource_type=SecurityResourceType.SQL,
    operation="execute_query",
    data={"sql": "SELECT * FROM users"}
)

# Аудит
await security_manager.audit(
    action="execute_query",
    user_id="user123",
    resource="users_table",
    success=True
)

# Валидация с аудитом
await security_manager.validate_and_audit(
    resource_type=SecurityResourceType.FILE,
    operation="read",
    data={"path": "/data/file.txt"},
    user_id="user123"
)
```
"""
from .security_manager import (
    SecurityManager,
    SecurityValidator,
    SQLSecurityValidator,
    FileSecurityValidator,
    SecurityResourceType,
    SecurityAction,
    SecurityAuditEvent,
    SecurityError,
    get_security_manager,
    create_security_manager,
    reset_security_manager,
)
from .authorizer import (
    RoleBasedAuthorizer,
    PermissionDeniedError,
)
from .user_context import UserContext

__all__ = [
    # Security manager
    'SecurityManager',
    'SecurityValidator',
    'SQLSecurityValidator',
    'FileSecurityValidator',
    'SecurityResourceType',
    'SecurityAction',
    'SecurityAuditEvent',
    'SecurityError',
    'get_security_manager',
    'create_security_manager',
    'reset_security_manager',
    
    # Authorizer
    'RoleBasedAuthorizer',
    'PermissionDeniedError',
    
    # User context
    'UserContext',
]
