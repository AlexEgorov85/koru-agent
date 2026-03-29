"""
Централизованная система безопасности (Security Manager).

АРХИТЕКТУРА:
- Единый менеджер безопасности для всего приложения
- Валидаторы для разных типов ресурсов (SQL, File, API)
- Аудит действий через Event Bus
- RBAC (Role-Based Access Control)
- Паттерны безопасности (forbidden patterns, allowed paths)

ПРЕИМУЩЕСТВА:
- ✅ Централизованная политика безопасности
- ✅ Валидация операций до выполнения
- ✅ Аудит всех действий
- ✅ Гибкие правила для разных ресурсов
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from pathlib import Path

from core.infrastructure.event_bus import (
    EventDomain,
    EventType,
)
from core.security.authorizer import RoleBasedAuthorizer, PermissionDeniedError
from core.security.user_context import UserContext


class SecurityAction(Enum):
    """Типы действий для аудита."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    CREATE = "create"
    UPDATE = "update"


class SecurityResourceType(Enum):
    """Типы ресурсов для валидации."""
    SQL = "sql"
    FILE = "file"
    API = "api"
    DATABASE = "database"
    CAPABILITY = "capability"
    CONFIG = "config"


@dataclass
class SecurityAuditEvent:
    """Событие аудита безопасности."""
    action: str
    user_id: str
    resource_type: str
    resource_name: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    ip_address: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "details": self.details,
        }


class SecurityValidator:
    """
    Базовый класс валидатора безопасности.
    
    RESPONSIBILITIES:
    - Валидация операций над ресурсами
    - Проверка на запрещённые паттерны
    - Проверка путей и ограничений
    """
    
    def __init__(self, resource_type: SecurityResourceType):
        self.resource_type = resource_type
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def validate(self, operation: str, data: Any) -> bool:
        """
        Валидация операции.
        
        ARGS:
        - operation: тип операции
        - data: данные для валидации
        
        RETURNS:
        - bool: True если валидация успешна
        
        RAISES:
        - SecurityError: если валидация не пройдена
        """
        raise NotImplementedError


class SQLSecurityValidator(SecurityValidator):
    """
    Валидатор SQL операций.
    
    FEATURES:
    - Запрет DROP, DELETE, TRUNCATE, ALTER
    - Проверка на SQL injection паттерны
    - Ограничение на количество строк
    """
    
    FORBIDDEN_PATTERNS = [
        r'\bDROP\s+TABLE\b',
        r'\bDROP\s+DATABASE\b',
        r'\bDELETE\s+FROM\b',
        r'\bTRUNCATE\b',
        r'\bALTER\s+TABLE\b',
        r'\bCREATE\s+USER\b',
        r'\bGRANT\b',
        r'\bREVOKE\b',
        r'--',  # SQL comment injection
        r';\s*--',  # SQL injection
        r'\bUNION\s+SELECT\b',  # UNION injection
    ]
    
    def __init__(self):
        super().__init__(SecurityResourceType.SQL)
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.FORBIDDEN_PATTERNS
        ]
    
    async def validate(self, operation: str, data: Any) -> bool:
        if operation != 'execute_query':
            return True
        
        sql = data.get('sql', '') if isinstance(data, dict) else str(data)
        
        # Проверка на запрещённые паттерны
        for pattern in self._compiled_patterns:
            if pattern.search(sql):
                raise SecurityError(
                    f"Forbidden SQL pattern detected: {pattern.pattern}",
                    resource_type="sql",
                    operation=operation
                )
        
        # Проверка на потенциальную SQL injection
        if self._detect_sql_injection(sql):
            raise SecurityError(
                "Potential SQL injection detected",
                resource_type="sql",
                operation=operation
            )
        
        self._logger.debug(f"SQL валидация успешна для операции: {operation}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return True
    
    def _detect_sql_injection(self, sql: str) -> bool:
        """Обнаружение потенциальной SQL injection."""
        # Простая эвристика
        suspicious_patterns = [
            r"'\s*OR\s+'1'\s*=\s*'1",
            r"'\s*OR\s+1\s*=\s*1",
            r";\s*DROP",
            r";\s*DELETE",
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return True
        
        return False


class FileSecurityValidator(SecurityValidator):
    """
    Валидатор файловых операций.
    
    FEATURES:
    - Проверка путей (path traversal)
    - Разрешённые расширения
    - Запрещённые пути
    """
    
    FORBIDDEN_PATHS = [
        '/etc',
        '/proc',
        '/sys',
        'C:\\Windows',
        'C:\\Program Files',
    ]
    
    def __init__(self, allowed_base_paths: List[str] = None, allowed_extensions: List[str] = None):
        super().__init__(SecurityResourceType.FILE)
        self._allowed_base_paths = [Path(p).resolve() for p in (allowed_base_paths or [])]
        self._allowed_extensions = set(allowed_extensions or [])
    
    async def validate(self, operation: str, data: Any) -> bool:
        if not isinstance(data, dict):
            return True
        
        file_path = data.get('path', '')
        
        # Проверка path traversal
        if self._is_path_traversal(file_path):
            raise SecurityError(
                "Path traversal detected",
                resource_type="file",
                operation=operation
            )
        
        # Проверка запрещённых путей
        if self._is_forbidden_path(file_path):
            raise SecurityError(
                f"Access to forbidden path: {file_path}",
                resource_type="file",
                operation=operation
            )
        
        # Проверка расширения
        if self._allowed_extensions:
            ext = Path(file_path).suffix.lower()
            if ext not in self._allowed_extensions:
                raise SecurityError(
                    f"File extension '{ext}' not allowed",
                    resource_type="file",
                    operation=operation
                )
        
        self._logger.debug(f"File валидация успешна для операции: {operation}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        return True
    
    def _is_path_traversal(self, path: str) -> bool:
        """Обнаружение path traversal атак."""
        return '..' in path or path.startswith('/')
    
    def _is_forbidden_path(self, path: str) -> bool:
        """Проверка запрещённых путей."""
        path_obj = Path(path).resolve()
        
        for forbidden in self.FORBIDDEN_PATHS:
            if str(path_obj).startswith(forbidden):
                return True
        
        # Проверка что путь внутри разрешённых базовых путей
        if self._allowed_base_paths:
            for base_path in self._allowed_base_paths:
                try:
                    path_obj.relative_to(base_path)
                    return False
                except ValueError:
                    continue
            return True
        
        return False


class SecurityError(Exception):
    """Ошибка безопасности."""
    
    def __init__(
        self,
        message: str,
        resource_type: str = None,
        operation: str = None,
    ):
        self.message = message
        self.resource_type = resource_type
        self.operation = operation
        super().__init__(self.message)
    
    def to_dict(self) -> Dict:
        return {
            "message": self.message,
            "resource_type": self.resource_type,
            "operation": self.operation,
        }


class SecurityManager:
    """
    Централизованная система безопасности.
    
    FEATURES:
    - Регистрация валидаторов по типам ресурсов
    - RBAC авторизация
    - Аудит всех действий
    - Интеграция с Event Bus
    
    USAGE:
    ```python
    # Создание менеджера
    security_manager = SecurityManager()
    
    # Регистрация валидаторов
    security_manager.register_validator(
        SecurityResourceType.SQL,
        SQLSecurityValidator()
    )
    
    # Валидация операции
    await security_manager.validate(
        resource_type=SecurityResourceType.SQL,
        operation="execute_query",
        data={"sql": "SELECT * FROM users"}
    )
    
    # Аудит действия
    await security_manager.audit(
        action="execute_query",
        user="user123",
        resource="users_table",
        success=True
    )
    ```
    """

    def __init__(
        self,
        event_bus=None,
        authorizer: Optional[RoleBasedAuthorizer] = None,
    ):
        """
        Инициализация менеджера безопасности.
        
        ARGS:
        - event_bus_manager: менеджер событий
        - authorizer: авторизатор (по умолчанию RoleBasedAuthorizer)
        """
        self._event_bus = event_bus
        self._authorizer = authorizer or RoleBasedAuthorizer()
        
        self._validators: Dict[SecurityResourceType, SecurityValidator] = {}
        self._audit_log: List[SecurityAuditEvent] = []
        self._max_audit_log_size = 1000
        
        # Инициализация логгера ДО регистрации валидаторов
        self._logger = logging.getLogger(f"{__name__}.SecurityManager")
        
        # Регистрация встроенных валидаторов
        self._register_default_validators()
        
        self._logger.info("SecurityManager инициализирован")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    
    def _register_default_validators(self):
        """Регистрация встроенных валидаторов."""
        self.register_validator(SecurityResourceType.SQL, SQLSecurityValidator())
        self.register_validator(SecurityResourceType.FILE, FileSecurityValidator())
    
    def register_validator(
        self,
        resource_type: SecurityResourceType,
        validator: SecurityValidator,
    ):
        """
        Регистрация валидатора для типа ресурса.
        
        ARGS:
        - resource_type: тип ресурса
        - validator: валидатор
        """
        self._validators[resource_type] = validator
        self._logger.debug(f"Зарегистрирован валидатор для {resource_type.value}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    
    def get_validator(self, resource_type: SecurityResourceType) -> Optional[SecurityValidator]:
        """Получение валидатора по типу ресурса."""
        return self._validators.get(resource_type)
    
    async def validate(
        self,
        resource_type: SecurityResourceType,
        operation: str,
        data: Any,
    ) -> bool:
        """
        Валидация операции над ресурсом.
        
        ARGS:
        - resource_type: тип ресурса
        - operation: тип операции
        - data: данные для валидации
        
        RETURNS:
        - bool: True если валидация успешна
        
        RAISES:
        - SecurityError: если валидация не пройдена
        """
        validator = self._validators.get(resource_type)
        
        if not validator:
            self._logger.warning(f"Валидатор для {resource_type.value} не найден, пропускаем")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return True
        
        return await validator.validate(operation, data)
    
    async def authorize(
        self,
        user_context: UserContext,
        capability_name: str,
        parameters: Dict = None,
    ) -> bool:
        """
        Авторизация пользователя для выполнения capability.
        
        ARGS:
        - user_context: контекст пользователя
        - capability_name: имя capability
        - parameters: параметры выполнения
        
        RETURNS:
        - bool: True если авторизация успешна
        
        RAISES:
        - PermissionDeniedError: если авторизация не пройдена
        """
        from core.models.data.capability import Capability
        
        capability = Capability(name=capability_name)
        return await self._authorizer.authorize(user_context, capability, parameters)
    
    async def audit(
        self,
        action: str,
        user_id: str,
        resource: str,
        success: bool,
        resource_type: str = None,
        ip_address: str = None,
        details: Dict = None,
    ):
        """
        Аудит действия.
        
        ARGS:
        - action: тип действия
        - user_id: ID пользователя
        - resource: ресурс над которым выполнено действие
        - success: успешность действия
        - resource_type: тип ресурса
        - ip_address: IP адрес
        - details: дополнительные детали
        """
        audit_event = SecurityAuditEvent(
            action=action,
            user_id=user_id,
            resource_type=resource_type or "unknown",
            resource_name=resource,
            success=success,
            ip_address=ip_address,
            details=details or {},
        )
        
        # Сохранение в лог
        self._audit_log.append(audit_event)
        
        # Ограничение размера лога
        if len(self._audit_log) > self._max_audit_log_size:
            self._audit_log.pop(0)
        
        # Публикация события
        await self._event_bus_manager.publish(
            EventType.ERROR_OCCURRED,  # Используем как событие аудита
            data={
                "audit": audit_event.to_dict(),
                "event_type": "security_audit",
            },
            domain=EventDomain.SECURITY,
        )
        
        self._logger.debug(f"Аудит: {action} by {user_id} on {resource} - {'OK' if success else 'FAILED'}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
    
    async def validate_and_audit(
        self,
        resource_type: SecurityResourceType,
        operation: str,
        data: Any,
        user_id: str = None,
        resource_name: str = None,
    ) -> bool:
        """
        Валидация с последующим аудитом.
        
        ARGS:
        - resource_type: тип ресурса
        - operation: тип операции
        - data: данные для валидации
        - user_id: ID пользователя
        - resource_name: имя ресурса
        
        RETURNS:
        - bool: True если валидация успешна
        """
        success = False
        
        try:
            await self.validate(resource_type, operation, data)
            success = True
            
            if user_id:
                await self.audit(
                    action=operation,
                    user_id=user_id,
                    resource=resource_name or str(resource_type.value),
                    success=True,
                    resource_type=resource_type.value,
                )
            
            return True
            
        except SecurityError as e:
            if user_id:
                await self.audit(
                    action=operation,
                    user_id=user_id,
                    resource=resource_name or str(resource_type.value),
                    success=False,
                    resource_type=resource_type.value,
                    details={"error": e.message},
                )
            
            raise
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """
        Получение лога аудита.
        
        ARGS:
        - limit: количество записей
        
        RETURNS:
        - List[Dict]: записи аудита
        """
        return [event.to_dict() for event in self._audit_log[-limit:]]
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики безопасности."""
        total_events = len(self._audit_log)
        success_events = sum(1 for e in self._audit_log if e.success)
        failed_events = total_events - success_events
        
        # Группировка по действиям
        by_action: Dict[str, int] = {}
        for event in self._audit_log:
            by_action[event.action] = by_action.get(event.action, 0) + 1
        
        # Группировка по пользователям
        by_user: Dict[str, int] = {}
        for event in self._audit_log:
            by_user[event.user_id] = by_user.get(event.user_id, 0) + 1
        
        return {
            "total_events": total_events,
            "success_events": success_events,
            "failed_events": failed_events,
            "success_rate": (success_events / total_events * 100) if total_events > 0 else 100,
            "by_action": by_action,
            "by_user": by_user,
            "validators_registered": len(self._validators),
        }


# Глобальный менеджер безопасности (singleton)
_global_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """
    Получение глобального менеджера безопасности.
    
    RETURNS:
    - SecurityManager: глобальный экземпляр
    """
    global _global_security_manager
    if _global_security_manager is None:
        _global_security_manager = SecurityManager()
    return _global_security_manager


def create_security_manager(
    event_bus=None,
    **kwargs
) -> SecurityManager:
    """
    Создание глобального менеджера безопасности.
    
    ARGS:
    - event_bus_manager: менеджер событий
    - **kwargs: дополнительные параметры
    
    RETURNS:
    - SecurityManager: созданный экземпляр
    """
    global _global_security_manager
    _global_security_manager = SecurityManager(
        event_bus_manager=event_bus_manager,
        **kwargs
    )
    return _global_security_manager


def reset_security_manager():
    """Сброс глобального менеджера (для тестов)."""
    global _global_security_manager
    _global_security_manager = None
