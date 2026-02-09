

# ==========================================================
# Resource Registry
# ==========================================================

from datetime import datetime
import threading
from typing import Any, Dict, List, Optional, Set

from models.resource import ResourceHealth, ResourceType
from core.system_context.capability_registry import CapabilityRegistry
from models.capability import Capability


class ResourceInfo:
    """
    Контейнер информации о ресурсе.

    ПОЛЯ:
    - name: Уникальное имя ресурса в системе
    - type: Тип ресурса (ResourceType)
    - instance: Экземпляр ресурса
    - health: Текущее состояние здоровья (ResourceHealth)
    - created_at: Время создания ресурса
    - access_count: Количество обращений к ресурсу
    - error_count: Количество ошибок при работе с ресурсом

    ОСОБЕННОСТИ:
    - Содержит метрики использования для мониторинга
    - Отслеживает зависимости для правильного порядка инициализации
    - Хранит состояние здоровья для отказоустойчивости
    """
    def __init__(self, name: str, resource_type: ResourceType, instance: Any):
        self.name = name
        self.resource_type = resource_type
        self.instance = instance
        self.health = ResourceHealth.INITIALIZING
        self.created_at = datetime.now()
        self.access_count = 0
        self.error_count = 0
        self.is_default=False

class ResourceRegistry:
    """
    Единый реестр ресурсов и возможностей системы.

    НАЗНАЧЕНИЕ:
    - Централизованное хранение информации о всех ресурсах (инстансы)
    - Централизованное хранение информации о всех возможностях (декларации)
    - Потокобезопасный доступ к данным о ресурсах и возможностях
    - Группировка ресурсов по типам

    МЕТОДЫ:
    - register_resource(): Регистрация нового ресурса (инстанса)
    - register_capability(): Регистрация новой возможности (декларации)
    - register_from_skill(): Регистрация навыка и всех его возможностей
    - unregister(): Удаление ресурса из реестра
    - get_resource(): Получение инстанса ресурса по имени
    - get_capability(): Получение декларации возможности по имени
    - list_by_type(): Получение списка ресурсов заданного типа
    - list_capabilities(): Получение всех возможностей
    - all(): Получение всех ресурсов

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    registry = ResourceRegistry()
    registry.register_resource(ResourceInfo("llm1", ResourceType.LLM_PROVIDER, llm_instance))
    registry.register_capability(Capability(name="llm.generate", ...))

    llm_resource = registry.get_resource("llm1")
    llm_providers = registry.list_by_type(ResourceType.LLM_PROVIDER)
    generate_capability = registry.get_capability("llm.generate")

    АРХИТЕКТУРНЫЕ ОСОБЕННОСТИ:
    - Использует RLock для потокобезопасности
    - Хранит индексы по типам ресурсов для быстрого доступа
    - Внутренне содержит CapabilityRegistry для деклараций возможностей
    - Сохраняет архитектурный паттерн «декларация ≠ реализация»
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._resources: Dict[str, ResourceInfo] = {}
        self._by_type: Dict[ResourceType, Set[str]] = {t: set() for t in ResourceType}
        # === НОВОЕ: Внутренний реестр capability ===
        self._capabilities: CapabilityRegistry = CapabilityRegistry()  # ВНУТРЕННИЙ компонент

    def register_resource(self, info: ResourceInfo, override: bool = False) -> None:
        """
        Регистрация инстанса ресурса (провайдер, навык, инструмент).

        ПАРАМЕТРЫ:
        - info: Информация о ресурсе
        - override: Флаг разрешения перезаписи существующего ресурса

        ИСКЛЮЧЕНИЯ:
        - ValueError: Если ресурс с таким именем уже существует и override=False

        ПРИМЕР:
        registry.register_resource(
            ResourceInfo("main_db", ResourceType.DATABASE, db_instance),
            override=False
        )

        ВАЖНО:
        - По умолчанию запрещено перезаписывать существующие ресурсы
        - Потокобезопасная реализация гарантирует целостность данных
        """
        with self._lock:
            if info.name in self._resources and not override:
                raise ValueError(f"Resource {info.name} already exists")
            self._resources[info.name] = info
            self._by_type[info.resource_type].add(info.name)

    def register_capability(self, capability: Capability) -> None:
        """
        Регистрация декларации возможности (делегирование внутреннему реестру).

        ПАРАМЕТРЫ:
        - capability: Объект возможности для регистрации

        ПРИМЕР:
        registry.register_capability(
            Capability(name="planning.create_plan", ...)
        )

        ВАЖНО:
        - Делегирует регистрацию внутреннему CapabilityRegistry
        - Сохраняет архитектурный паттерн «декларация ≠ реализация»
        """
        self._capabilities.register(capability)

    def register_from_skill(self, skill) -> None:
        """
        Единая точка регистрации навыка + всех его capability.
        Устраняет необходимость отдельного вызова в SystemContext.

        ПАРАМЕТРЫ:
        - skill: Экземпляр навыка для регистрации

        ПРИМЕР:
        registry.register_from_skill(PlanningSkill())

        ВАЖНО:
        - Сначала регистрирует инстанс навыка
        - Затем регистрирует все его capability
        - Обеспечивает согласованность между навыком и его возможностями
        """
        # 1. Регистрируем инстанс навыка
        info = ResourceInfo(
            name=skill.name,
            resource_type=ResourceType.SKILL,
            instance=skill
        )
        self.register_resource(info)

        # 2. Регистрируем все его capability
        for cap in skill.get_capabilities():
            self.register_capability(cap)

    def unregister(self, name: str) -> None:
        """
        Удаление ресурса из реестра.

        ПАРАМЕТРЫ:
        - name: Имя ресурса для удаления

        ПРИМЕР:
        registry.unregister("temp_resource")

        ЗАМЕЧАНИЕ:
        - Метод не вызывает shutdown() для ресурса
        - Ответственность за корректное завершение работы ресурса лежит на вызывающем коде
        """
        with self._lock:
            info = self._resources.pop(name)
            self._by_type[info.resource_type].discard(name)

    def get_resource(self, name: str) -> Optional[Any]:
        """
        Получение инстанса ресурса по имени.

        ПАРАМЕТРЫ:
        - name: Имя ресурса

        ВОЗВРАЩАЕТ:
        - Инстанс ресурса если найден
        - None если ресурс не найден

        ПРИМЕР:
        resource = registry.get_resource("primary_llm")
        if resource:
            use_resource(resource)

        ОСОБЕННОСТИ:
        - Потокобезопасная реализация
        - Не изменяет состояние ресурса
        """
        with self._lock:
            info = self._resources.get(name)
            return info.instance if info else None

    def get_capability(self, name: str) -> Optional[Capability]:
        """
        Получение декларации возможности (делегирование внутреннему реестру).

        ПАРАМЕТРЫ:
        - name: Имя возможности

        ВОЗВРАЩАЕТ:
        - Объект Capability если найден
        - None если возможность не найдена

        ПРИМЕР:
        capability = registry.get_capability("planning.create_plan")
        if capability:
            print(f"Найдена возможность: {capability.description}")

        ПРОИЗВОДИТЕЛЬНОСТЬ:
        - O(1) благодаря внутреннему CapabilityRegistry
        """
        return self._capabilities.get(name)

    def list_capabilities(self) -> List[Capability]:
        """
        Список всех зарегистрированных capability.

        ВОЗВРАЩАЕТ:
        - Список всех объектов Capability

        ПРИМЕР:
        all_caps = registry.list_capabilities()
        print(f"Всего возможностей: {len(all_caps)}")

        ИСПОЛЬЗОВАНИЕ:
        - Отладка и интроспекция системы
        - Построение UI для выбора действий
        - Генерация документации по возможностям системы
        """
        return self._capabilities.all()

    def list_by_type(self, resource_type: ResourceType) -> List[str]:
        """
        Получение списка имен ресурсов заданного типа.

        ПАРАМЕТРЫ:
        - rtype: Тип ресурсов (ResourceType)

        ВОЗВРАЩАЕТ:
        - Список имен ресурсов указанного типа

        ПРИМЕР:
        llm_providers = registry.list_by_type(ResourceType.LLM_PROVIDER)
        for provider_name in llm_providers:
            provider = registry.get_resource(provider_name)
            # использование провайдера

        ЗАМЕЧАНИЕ:
        - Возвращается копия списка для безопасности
        """
        with self._lock:
            return list(self._by_type.get(resource_type, []))

    def all(self) -> List[ResourceInfo]:
        """
        Получение информации о всех ресурсах.

        ВОЗВРАЩАЕТ:
        - Список объектов ResourceInfo для всех зарегистрированных ресурсов

        ПРИМЕР:
        all_resources = registry.all()
        healthy_resources = [r for r in all_resources if r.health == ResourceHealth.HEALTHY]

        ВАЖНО:
        - Возвращается копия списка для сохранения потокобезопасности
        """
        with self._lock:
            return list(self._resources.values())