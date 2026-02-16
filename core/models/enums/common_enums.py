"""
Общие перечисления (Enums) для всей системы.

Содержит Enum'ы, которые используются в разных частях системы.
"""
from enum import Enum
from typing import Union


class ComponentType(str, Enum):
    """
    Типы компонентов системы.

    ИСПОЛЬЗОВАНИЕ:
    component_type = ComponentType.SKILL
    if component_type == ComponentType.TOOL:
        # обработка инструмента
    """
    SKILL = "skill"
    TOOL = "tool"
    SERVICE = "service"
    BEHAVIOR = "behavior"


class ComponentStatus(str, Enum):
    """
    Статусы компонентов системы.

    ИСПОЛЬЗОВАНИЕ:
    status = ComponentStatus.ACTIVE
    if status == ComponentStatus.ARCHIVED:
        # обработка архивного компонента
    """
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


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
    - PENDING: Ресурс создан, но ожидает инициализации

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
    PENDING = "pending"


class ExecutionStatus(Enum):
    """
    Статусы выполнения задачи.
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorCategory(str, Enum):
    """
    Классификация типов ошибок для принятия решений о повторных попытках.

    КАТЕГОРИИ:
    - TRANSIENT: временные ошибки (сеть, таймауты, rate limit)
    - INVALID_INPUT: ошибки валидации входных данных (ошибки агента)
    - TOOL_FAILURE: ошибки внешних инструментов или баги
    - FATAL: критические ошибки, при которых продолжение бессмысленно

    ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:
    # Сетевая ошибка
    error = ExecutionErrorInfo(
        category=ErrorCategory.TRANSIENT,
        message="Connection timeout"
    )

    # Ошибка валидации
    error = ExecutionErrorInfo(
        category=ErrorCategory.INVALID_INPUT,
        message="Missing required parameter 'query'"
    )

    ВАЖНО:
    - Классификация ошибок критически важна для правильной стратегии повторных попыток
    - TRANSIENT ошибки обычно можно повторять
    - INVALID_INPUT ошибки обычно нельзя исправить повторными попытками
    """
    TRANSIENT = "transient"      # сеть, таймауты, rate limit
    INVALID_INPUT = "invalid_input"  # ошибка агента
    TOOL_FAILURE = "tool_failure"    # баг или внешняя система
    FATAL = "fatal"                  # продолжать бессмысленно


class RetryDecision(str, Enum):
    """
    Возможные решения при обработке ошибки.

    РЕШЕНИЯ:
    - RETRY: повторить операцию после задержки
    - ABORT: отменить текущую операцию, но продолжить работу агента
    - FAIL: полностью прекратить выполнение

    ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:
    if result.decision == RetryDecision.RETRY:
        await apply_retry_delay(result)
        # повторить операцию
    elif result.decision == RetryDecision.ABORT:
        # пропустить текущую операцию, но продолжить работу
        return ExecutionResult(status=ExecutionStatus.ABORTED)
    else:  # FAIL
        # полностью прекратить выполнение
        raise RuntimeError(f"Критическая ошибка: {result.reason}")

    СТРАТЕГИИ:
    - RETRY: для временных ошибок (сеть, таймауты)
    - ABORT: для ошибок валидации, когда действие агента некорректно
    - FAIL: для критических ошибок, делающих дальнейшую работу невозможной
    """
    RETRY = "retry"
    ABORT = "abort"
    FAIL = "fail"


class ContractDirection(str, Enum):
    """
    Направления контрактов.
    """
    INPUT = "input"
    OUTPUT = "output"


class PromptStatus(str, Enum):
    """
    Статусы промптов.
    """
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"