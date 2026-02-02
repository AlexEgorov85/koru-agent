"""
Чистые доменные модели для контекста сессии.
ОСОБЕННОСТИ:
- Полностью независимы от инфраструктуры
- Не содержат зависимостей от внешних библиотек
- Представляют бизнес-логику без технических деталей
- Легко тестируются изолированно
АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
1. Чистые модели не должны зависеть от инфраструктуры
2. Модели должны быть иммутабельными где это возможно
3. Каждая модель имеет единственную ответственность
4. Модели содержат только бизнес-логику
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from domain.models.execution.execution_status import ExecutionStatus


@dataclass
class AgentStep:
    """
    Шаг выполнения агента (контекст второго уровня).
    НАЗНАЧЕНИЕ:
    - Представление шагов агента в формате, безопасном для LLM
    - Координация действий и результатов
    - Трассировка поведения агента
    
    ПОЛЯ:
    - step_number: Порядковый номер шага
    - capability_name: Название capability, использованной на шаге
    - skill_name: Название навыка, выполнившего шаг
    - action_item_id: ID элемента с действием
    - observation_item_ids: Список ID элементов с результатами
    - summary: Краткое описание шага (без chain-of-thought)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    step = AgentStep(
        step_number=1,
        capability_name="planning.create_plan",
        skill_name="PlanningSkill",
        action_item_id="action_123",
        observation_item_ids=["obs_456"],
        summary="Создан первичный план для анализа данных"
    )
    
    ОСОБЕННОСТИ:
    - Содержит только ссылки на данные первого уровня
    - Безопасен для передачи в LLM
    - Не содержит сырых данных или внутренних деталей
    """
    step_number: int
    capability_name: str
    skill_name: str
    action_item_id: str
    observation_item_ids: List[str]
    summary: Optional[str] = None
    status: Optional[ExecutionStatus] = None