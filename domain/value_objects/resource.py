from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict

class ResourceType(str, Enum):
    """
    Типы ресурсов системы.
    
    КАТЕГОРИИ РЕСУРСОВ:
    - LLM_PROVIDER: Провайдеры языковых моделей
    - SKILL: Навыки агента (логика принятия решений)
    - TOOL: Инструменты для выполнения конкретных задач
    - DATABASE: Базы данных для хранения контекста и знаний
    - CACHE: Кэши для ускорения работы
    - CONFIG: Конфигурационные параметры
    
    ИСПОЛЬЗОВАНИЕ:
    resource = ResourceInfo(
        name="primary_llm",
        resource_type=ResourceType.LLM_PROVIDER,
        instance=llm_provider
    )
    
    ВАЖНО:
    - Классификация ресурсов позволяет гибко управлять жизненным циклом
    - Разные типы ресурсов могут требовать разной логики инициализации/завершения
    """
    LLM_PROVIDER = "llm_provider"
    SKILL = "skill"
    TOOL = "tool"
    DATABASE = "database"
    CACHE = "cache"
    CONFIG = "config"
    SERVICE = "service"


class Resource:
    """
    Value object для представления ресурса системы.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (domain)
    - Ответственность: представление информации о ресурсе
    - Зависимости: только от доменных моделей
    - Принципы: инверсия зависимостей (DIP)
    
    ПОЛЯ:
    - name: Имя ресурса
    - resource_type: Тип ресурса
    - instance: Экземпляр ресурса
    - metadata: Дополнительные метаданные
    """
    def __init__(
        self,
        name: str,
        resource_type: ResourceType,
        instance: Any,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.resource_type = resource_type
        self.instance = instance
        self.metadata = metadata or {}

    def __eq__(self, other):
        if not isinstance(other, Resource):
            return False
        return (self.name == other.name and 
                self.resource_type == other.resource_type and
                self.instance == other.instance)

    def __hash__(self):
        return hash((self.name, self.resource_type, self.instance))

    def __repr__(self):
        return f"Resource(name='{self.name}', type='{self.resource_type}')"