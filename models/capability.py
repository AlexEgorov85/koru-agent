from typing import Dict, Any, Optional, Type, List
from pydantic import BaseModel, Field

class Capability(BaseModel):
    """
    Capability — единица выбора для LLM.

    ПРИНЦИПЫ:
    - Capability знает о типе своих параметров
    - Валидация выполняется на уровне ExecutionGateway
    - Навыки работают с объектами вместо словарей
    """
    #: Уникальное имя capability (используется LLM)
    name: str = Field(..., description="Уникальное имя capability")

    #: Человекочитаемое описание
    description: str = Field(..., description="Описание возможности")

    #: JSON Schema / Pydantic schema параметров (для обратной совместимости)
    parameters_schema: Dict[str, Any] = Field(..., description="Схема входных параметров")

    #: Класс параметров для валидации (новое поле)
    parameters_class: Optional[Type[BaseModel]] = Field(
        None,
        description="Класс Pydantic модели для валидации параметров"
    )

    #: Имя навыка, которому принадлежит capability
    skill_name: str = Field(..., description="Имя навыка")

    # Видимость возможности для включения в промт
    visiable: bool = Field(True, description="Видимость возможности")
    
    #: Список стратегий, для которых доступна эта capability
    supported_strategies: List[str] = Field(
        default=["react"], 
        description="Список стратегий, для которых доступна эта capability"
    )