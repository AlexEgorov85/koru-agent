

from enum import Enum

# ==========================================================
# Конфигурация и enum
# ==========================================================

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

class ResourceHealth(str, Enum):
    """
    Состояния здоровья ресурсов.
    
    СОСТОЯНИЯ:
    - HEALTHY: Ресурс работает нормально
    - DEGRADED: Ресурс работает с ограничениями
    - UNHEALTHY: Ресурс не функционирует
    - INITIALIZING: Ресурс находится в процессе инициализации
    
    ИСПОЛЬЗОВАНИЕ:
    if resource.health == ResourceHealth.HEALTHY:
        proceed_with_operation()
    elif resource.health == ResourceHealth.DEGRADED:
        use_fallback_strategy()
    
    ПРИМЕЧАНИЕ:
    - Состояние здоровья используется для принятия решений о маршрутизации запросов
    - Может влиять на стратегии повторных попыток и отказоустойчивости
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    INITIALIZING = "initializing"