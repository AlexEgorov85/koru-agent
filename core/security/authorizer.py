"""
Базовый класс авторизатора для проверки прав доступа.
"""
from typing import List
from core.security.user_context import UserContext
from core.models.data.capability import Capability


class PermissionDeniedError(Exception):
    """Исключение, выбрасываемое при отсутствии прав доступа."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class RoleBasedAuthorizer:
    """
    Авторизатор на основе ролей пользователей.
    """
    def __init__(self):
        pass

    async def authorize(self, user_context: UserContext, capability: Capability, parameters: dict = None) -> bool:
        """
        Проверка прав доступа пользователя для выполнения capability.
        
        ARGS:
        - user_context: контекст пользователя
        - capability: capability для проверки
        - parameters: параметры выполнения (опционально)
        
        RETURNS:
        - True если пользователь имеет права, иначе False
        
        RAISES:
        - PermissionDeniedError: если у пользователя нет прав
        """
        capability_name = capability.name
        
        # Проверяем, есть ли у пользователя разрешение на выполнение этой capability
        if not user_context.has_permission(capability_name):
            raise PermissionDeniedError(
                f"Пользователь '{user_context.user_id}' с ролью '{user_context.role}' "
                f"не имеет прав на выполнение capability '{capability_name}'"
            )
        
        # Дополнительные проверки могут быть добавлены здесь
        # Например, проверка параметров для чувствительных операций
        
        return True