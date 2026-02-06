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
from enum import Enum
from datetime import datetime
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import uuid


class ContextItemType(str, Enum):
    """
    Типы элементов контекста сессии.
    КАТЕГОРИИ:
    - USER_QUERY: Исходный запрос пользователя
    - THOUGHT: Внутренние рассуждения агента (не для LLM)
    - ACTION: Действия, выполняемые агентом
    - OBSERVATION: Результаты выполнения действий
    - TASK: Задачи из плана
    - FINAL_RESPONSE: Финальный ответ агента
    - ERROR_LOG: Логи ошибок
    - EXECUTION_PLAN: План выполнения
    - PLAN_UPDATE: Обновление плана
    - SKILL_RESULT: Результат работы навыка
    - TOOL_RESULT: Результат работы инструмента
    - CAPABILITY_DECLARATION: Декларация capability
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    if item.item_type == ContextItemType.ACTION:
        process_action(item.content)
    elif item.item_type == ContextItemType.OBSERVATION:
        process_observation(item.content)
    """
    USER_QUERY = "USER_QUERY"
    THOUGHT = "THOUGHT"
    ACTION = "ACTION"
    OBSERVATION = "OBSERVATION"
    TASK = "TASK"
    FINAL_RESPONSE = "FINAL_RESPONSE"
    ERROR_LOG = "ERROR_LOG"
    EXECUTION_PLAN = "EXECUTION_PLAN"
    PLAN_UPDATE = "PLAN_UPDATE"
    SKILL_RESULT = "SKILL_RESULT"
    TOOL_RESULT = "TOOL_RESULT"
    CAPABILITY_DECLARATION = "CAPABILITY_DECLARATION"


class ContextItemMetadata(BaseModel):
    """
    Метаданные контекстного элемента.
    СОДЕРЖИТ:
    - Доверительную оценку источника
    - Время выполнения
    - Источник данных
    - Номер шага
    - Дополнительные данные
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    metadata = ContextItemMetadata(
        confidence=0.95,
        execution_time=0.125,
        source="SQLTool",
        step_number=3,
        additional_data={"query_type": "SELECT"}
    )
    
    ОСОБЕННОСТИ:
    - Иммутабельный класс (frozen=True)
    - Значения по умолчанию для всех полей
    - Валидация доверительной оценки (0.0-1.0)
    """
    source: Optional[str] = None
    step_number: Optional[int] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    additional_data: Optional[Dict[str, Any]] = None
    capability_name: Optional[str] = None
    summary: Optional[str] = None
    timestamp: Optional[datetime] = None


class ContextItem(BaseModel):
    """
    Базовый элемент контекста сессии.
    ПРЕДНАЗНАЧЕНИЕ:
    - Хранение сырых данных в контексте
    - Инкапсуляция метаданных и содержимого
    - Обеспечение целостности данных
    
    ПОЛЯ:
    - item_id: Уникальный идентификатор элемента
    - session_id: ID сессии, которой принадлежит элемент
    - item_type: Тип элемента (ContextItemType)
    - content: Содержимое элемента (любой тип)
    - quick_content: Краткое содержимое для быстрого просмотра
    - metadata: Метаданные элемента
    - created_at: Время создания
    - updated_at: Время последнего обновления
    
    ПРИМЕЧАНИЕ:
    Модель является иммутабельной (frozen=True) для обеспечения целостности данных.
    """
    item_id: str
    session_id: str
    item_type: ContextItemType
    content: Any
    quick_content: Optional[str] = None
    metadata: ContextItemMetadata = ContextItemMetadata()
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def model_post_init(self, __context: Any) -> None:
        """Инициализация значений по умолчанию."""
        if self.quick_content is None and isinstance(self.content, str):
            self.quick_content = self.content[:200] + "..." if len(self.content) > 200 else self.content


class AgentStep(BaseModel):
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
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: Optional[str] = None