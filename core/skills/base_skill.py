"""
Базовый класс навыка (Skill) с поддержкой архитектуры портов и адаптеров.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Полная инверсия зависимостей через порты
2. Устранение дублирования метода run()
3. Использование портов вместо прямых зависимостей
4. Четкое разделение ответственности

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Навык зависит ТОЛЬКО от абстракций (портов), а не от конкретных реализаций
- Все внешние зависимости инжектируются через конструктор
- Бизнес-логика полностью отделена от инфраструктуры
- Поддержка тестирования через моки портов
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemType
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from models.execution import ExecutionResult

class BaseSkill(ABC):
    """
    Базовый класс для всех навыков агента с поддержкой архитектуры портов.
    
    Архитектурная роль:
    - Skill = "как думать и что делать"
    - Capability = "что именно можно сделать"
    - Порты = "как взаимодействовать с внешним миром"
    
    Один Skill может иметь несколько Capability.
    """
    #: Человекочитаемое имя навыка
    name: str = "base_skill"
    
    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        self.name = name
        self.system_context = system_context
        self.config = kwargs
    
    # --------------------------------------------------
    # Capability API
    # --------------------------------------------------
    @abstractmethod
    def get_capabilities(self) -> List[Capability]:
        """
        Возвращает список возможностей, которые предоставляет навык.
        
        Пример:
        PlanningSkill:
            - planning.create_plan
            - planning.update_plan
        
        ВАЖНО:
        - Метод должен быть реализован в дочерних классах
        - Возвращаемые capability должны быть валидными для системы
        - Имена capability должны быть уникальными в рамках системы
        """
        raise NotImplementedError
    
    def get_capability_by_name(self, capability_name: str) -> Capability:
        """
        Поиск capability по имени.
        
        Используется ExecutionGateway для маршрутизации запросов.
        
        ПАРАМЕТРЫ:
        - capability_name: Имя capability для поиска
        
        ВОЗВРАЩАЕТ:
        - Capability объект если найден
        
        ИСКЛЮЧЕНИЯ:
        - ValueError если capability не найдена
        
        ОСОБЕННОСТИ:
        - Регистронезависимый поиск
        - Быстрый поиск через итерацию списка
        """
        for cap in self.get_capabilities():
            if cap.name.lower() == capability_name.lower():
                return cap
        raise ValueError(f"Capability '{capability_name}' не найдена в skill '{self.name}'")
    
    # --------------------------------------------------
    # Execution API
    # --------------------------------------------------
    @abstractmethod
    async def execute(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        context: BaseSessionContext,
    ) -> ExecutionResult:
        """
        Выполнение конкретной capability навыка.
        
        ПАРАМЕТРЫ:
        - capability: выбранная возможность для выполнения
        - parameters: параметры от LLM или runtime
        - context: порт для работы с контекстом сессии
        
        ВОЗВРАЩАЕТ:
        - Результат выполнения capability
        
        ИСПОЛЬЗОВАНИЕ:
        - Вызывается ExecutionGateway после валидации параметров
        - Результат будет сохранен в контексте как observation_item
        
        ПРИМЕР:
        result = await skill.execute(
            capability=create_plan_cap,
            parameters={"goal": "Найти информацию"},
            context=session_context
        )
        """
        raise NotImplementedError