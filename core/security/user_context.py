"""
Класс для хранения контекста пользователя и его прав.
"""
from typing import List, Optional
from enum import Enum


class UserRole(str, Enum):
    """Роли пользователей в системе."""
    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"


class UserContext:
    """
    Класс для хранения контекста пользователя и его прав.
    
    ATTRIBUTES:
    - user_id: уникальный идентификатор пользователя
    - role: роль пользователя
    - permissions: список разрешенных действий
    """
    def __init__(self, user_id: str, role: UserRole, permissions: Optional[List[str]] = None):
        self.user_id = user_id
        self.role = role
        self.permissions = permissions or self._get_default_permissions(role)

    def _get_default_permissions(self, role: UserRole) -> List[str]:
        """Получение разрешений по умолчанию для роли."""
        role_permissions = {
            UserRole.GUEST: [
                "basic.query",
                "basic.read"
            ],
            UserRole.USER: [
                "basic.query",
                "basic.read",
                "basic.write",
                "planning.create_plan",
                "planning.execute_plan"
            ],
            UserRole.ADMIN: [
                "basic.query",
                "basic.read",
                "basic.write",
                "planning.create_plan",
                "planning.execute_plan",
                "sql_tool.execute_raw_query",  # Только администраторы могут выполнять произвольные SQL-запросы
                "system.manage",
                "admin.full_access"
            ]
        }
        return role_permissions.get(role, [])

    def has_permission(self, capability_name: str) -> bool:
        """
        Проверка, есть ли у пользователя разрешение на выполнение capability.
        
        ARGS:
        - capability_name: имя capability для проверки
        
        RETURNS:
        - True если у пользователя есть разрешение, иначе False
        """
        return capability_name in self.permissions