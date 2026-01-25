

# ==========================================================
# Resource Registry
# ==========================================================

from datetime import datetime
import threading
from typing import Any, Dict, List, Optional, Set

from models.resource import ResourceHealth, ResourceType



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
    Реестр ресурсов системы.
    
    НАЗНАЧЕНИЕ:
    - Централизованное хранение информации о всех ресурсах
    - Потокобезопасный доступ к данным о ресурсах
    - Группировка ресурсов по типам
    
    МЕТОДЫ:
    - register(): Регистрация нового ресурса
    - unregister(): Удаление ресурса из реестра
    - get(): Получение информации о ресурсе по имени
    - list_by_type(): Получение списка ресурсов заданного типа
    - all(): Получение всех ресурсов
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    registry = ResourceRegistry()
    registry.register(ResourceInfo("llm1", ResourceType.LLM_PROVIDER, llm_instance))
    
    llm_resource = registry.get("llm1")
    llm_providers = registry.list_by_type(ResourceType.LLM_PROVIDER)
    
    АРХИТЕКТУРНЫЕ ОСОБЕННОСТИ:
    - Использует RLock для потокобезопасности
    - Хранит индексы по типам ресурсов для быстрого доступа
    - Не управляет жизненным циклом ресурсов, только хранит информацию
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._resources: Dict[str, ResourceInfo] = {}
        self._by_type: Dict[ResourceType, Set[str]] = {t: set() for t in ResourceType}

    def register(self, info: ResourceInfo, override: bool = False) -> None:
        """
        Регистрация ресурса в реестре.
        
        ПАРАМЕТРЫ:
        - info: Информация о ресурсе
        - override: Флаг разрешения перезаписи существующего ресурса
        
        ИСКЛЮЧЕНИЯ:
        - ValueError: Если ресурс с таким именем уже существует и override=False
        
        ПРИМЕР:
        registry.register(
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

    def get(self, name: str) -> Optional[ResourceInfo]:
        """
        Получение информации о ресурсе по имени.
        
        ПАРАМЕТРЫ:
        - name: Имя ресурса
        
        ВОЗВРАЩАЕТ:
        - ResourceInfo если ресурс найден
        - None если ресурс не найден
        
        ПРИМЕР:
        resource = registry.get("primary_llm")
        if resource and resource.health == ResourceHealth.HEALTHY:
            use_resource(resource.instance)
        
        ОСОБЕННОСТИ:
        - Потокобезопасная реализация
        - Не изменяет состояние ресурса
        """
        with self._lock:
            return self._resources.get(name)

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
            provider = registry.get(provider_name).instance
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