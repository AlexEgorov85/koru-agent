"""
Модели ресурсов для инфраструктурного контекста.
"""
from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime

from core.models.enums.common_enums import ResourceType



@dataclass
class ResourceInfo:
    """
    Информация о зарегистрированном ресурсе.

    ATTRIBUTES:
    - name: имя ресурса
    - resource_type: тип ресурса
    - instance: экземпляр ресурса
    - created_at: время создания
    - is_default: является ли ресурс ресурсом по умолчанию
    - metadata: дополнительные метаданные
    """
    name: str
    resource_type: ResourceType
    instance: Any
    created_at: datetime = None
    is_default: bool = False
    metadata: dict = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}

    def get_health_status(self) -> str:
        """
        Получение статуса здоровья ресурса.

        RETURNS:
        - статус здоровья ('healthy', 'degraded', 'unhealthy', 'unknown')
        """
        if self.instance is None:
            return 'unhealthy'

        # Проверяем наличие метода проверки здоровья
        if hasattr(self.instance, 'health_check'):
            try:
                result = self.instance.health_check()
                return result.get('status', 'unknown')
            except:
                return 'unhealthy'

        # По умолчанию считаем, что ресурс здоров, если он существует
        return 'healthy'