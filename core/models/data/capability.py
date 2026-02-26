from typing import Dict, Any, Optional, Type, List
from pydantic import BaseModel, Field

class Capability(BaseModel):
    """
    Capability — единица выбора для LLM.

    ПРИНЦИПЫ:
    - Capability = ДЕКЛАРАЦИЯ (ЧТО можно сделать) → только метаданные
    - Contract = ДАННЫЕ (какие параметры нужны) → версионируемые ресурсы
    - Skill = РЕАЛИЗАЦИЯ (КАК это сделать) → бизнес-логика без прямого доступа к хранилищу
    """
    #: Уникальное имя capability (используется LLM)
    name: str = Field(..., description="Уникальное имя capability")

    #: Человекочитаемое описание
    description: str = Field(..., description="Описание возможности")

    #: Имя навыка, которому принадлежит capability
    skill_name: str = Field(..., description="Имя навыка")

    # Видимость возможности для включения в промт
    visiable: bool = Field(True, description="Видимость возможности")

    #: Список стратегий, для которых доступна эта capability
    supported_strategies: List[str] = Field(
        default=["react"],
        description="Список стратегий, для которых доступна эта capability"
    )

    #: Метаданные для отладки и версионирования
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Метаданные capability для отладки и версионирования"
    )