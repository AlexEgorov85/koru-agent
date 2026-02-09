# ==========================================================
# Capability Registry
# ==========================================================

from typing import Dict, List, Optional

from models.capability import Capability




class CapabilityRegistry:
    """
    Реестр возможностей (capabilities) системы.
    
    НАЗНАЧЕНИЕ:
    - Централизованное хранение всех доступных возможностей
    - Быстрый поиск capability по имени
    - Регистрация capability из навыков
    
    МЕТОДЫ:
    - register_from_skill(): Регистрация всех capability из навыка
    - get(): Получение capability по имени
    - all(): Получение всех capability
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    registry = CapabilityRegistry()
    planning_skill = PlanningSkill()
    registry.register_from_skill(planning_skill)
    
    create_plan_cap = registry.get("planning.create_plan")
    if create_plan_cap:
        # использование capability
        
    all_caps = registry.all()
    
    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    - Capability регистрируются навыками, а не создаются напрямую
    - Имя capability должно быть уникальным в рамках системы
    - Реестр служит точкой обнаружения capability для AgentRuntime
    """
    def __init__(self):
        self._caps: Dict[str, Capability] = {}

    def register_from_skill(self, skill):
        """
        Регистрация всех capability из навыка.

        ПАРАМЕТРЫ:
        - skill: Экземпляр навыка, реализующий get_capabilities()

        ПРИМЕР:
        registry = CapabilityRegistry()
        planning_skill = PlanningSkill()
        registry.register_from_skill(planning_skill)

        # Теперь доступны capability:
        # "planning.create_plan"
        # "planning.update_plan"

        МЕХАНИЗМ:
        - Вызывает skill.get_capabilities() для получения списка capability
        - Добавляет каждую capability в реестр с её именем в качестве ключа
        - Перезаписывает существующие capability с таким же именем

        ВАЖНО:
        - Метод не проверяет дубликаты имен capability
        - Последний зарегистрированный навык "победит" при конфликте имен
        """
        for cap in skill.get_capabilities():
            self._caps[cap.name] = cap

    def register(self, capability: Capability) -> None:
        """Регистрация capability в реестре."""
        self._caps[capability.name] = capability

    def get(self, name: str) -> Optional[Capability]:
        """
        Получение capability по имени.
        
        ПАРАМЕТРЫ:
        - name: Уникальное имя capability
        
        ВОЗВРАЩАЕТ:
        - Capability объект если найден
        - None если capability не найден
        
        ПРИМЕР:
        cap = registry.get("data.query_db")
        if cap:
            print(f"Найдена capability: {cap.description}")
            # использование capability
        else:
            print("Capability не найдена")
        
        ПРОИЗВОДИТЕЛЬНОСТЬ:
        - O(1) благодаря использованию словаря
        - Потокобезопасность не гарантируется (требуется внешняя синхронизация)
        """
        return self._caps.get(name)

    def all(self) -> List[Capability]:
        """
        Получение всех зарегистрированных capability.
        
        ВОЗВРАЩАЕТ:
        - Список всех объектов Capability
        
        ПРИМЕР:
        all_caps = registry.all()
        print(f"Всего capability: {len(all_caps)}")
        for cap in all_caps:
            print(f"- {cap.name}: {cap.description}")
        
        ИСПОЛЬЗОВАНИЕ:
        - Отладка и интроспекция системы
        - Построение UI для выбора действий
        - Генерация документации по возможностям системы
        
        ЗАМЕЧАНИЕ:
        - Возвращается копия списка для безопасности
        - Порядок capability не определен
        """
        return list(self._caps.values())


