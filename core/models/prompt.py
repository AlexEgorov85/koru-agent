"""
Типизированная модель промпта с полной валидацией.
"""
from pydantic import BaseModel, Field, validator, root_validator, ConfigDict
from typing import List, Optional, Dict
from enum import Enum
import re


class PromptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ComponentType(str, Enum):
    SKILL = "skill"
    TOOL = "tool"
    SERVICE = "service"
    BEHAVIOR = "behavior"


class PromptVariable(BaseModel):
    """Метаданные переменной промпта"""
    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str = Field(..., min_length=5)
    required: bool = Field(default=True)
    default_value: Optional[str] = None


class Prompt(BaseModel):
    """
    Полноценный типизированный объект промпта.
    Все поля валидируются при создании объекта.
    """
    model_config = ConfigDict(frozen=True)  # Иммутабельность для безопасности кэширования

    capability: str = Field(
        ...,
        description="Имя capability (например, 'planning.create_plan')",
        min_length=3,
        pattern=r"^[a-z_]+(\.[a-z_]+)*$"  # Allow single names or compound names with dots (e.g., behavior or behavior.planning.decompose)
    )

    version: str = Field(
        ...,
        description="Семантическая версия",
        pattern=r"^v\d+\.\d+\.\d+$"  # v1.0.0
    )

    status: PromptStatus = Field(
        ...,
        description="Статус версии (только 'active' разрешён в prod)"
    )

    component_type: ComponentType = Field(
        ...,
        description="Тип компонента (явно объявлен в конфигурации)"
    )

    content: str = Field(
        ...,
        description="Текст промпта с шаблонными переменными",
        min_length=20
    )

    variables: List[PromptVariable] = Field(
        default_factory=list,
        description="Список переменных, используемых в шаблоне"
    )

    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Дополнительные метаданные (автор, дата создания и т.д.)"
    )

    # === Валидация шаблона ===
    @root_validator(skip_on_failure=True)
    def validate_template_variables(cls, values):
        """Проверяем, что все переменные в шаблоне объявлены в списке variables"""
        content = values.get('content', '')
        declared_vars = {v.name for v in values.get('variables', [])}

        # Извлекаем переменные из шаблона: {variable_name}
        template_vars = set(re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', content))

        # Проверяем необъявленные переменные
        undeclared = template_vars - declared_vars
        if undeclared:
            raise ValueError(
                f"Необъявленные переменные в шаблоне: {sorted(undeclared)}\n"
                f"Объявленные переменные: {sorted(declared_vars)}\n"
                f"Шаблон: {content[:100]}..."
            )

        # Проверяем объявленные, но неиспользуемые переменные (предупреждение)
        unused = declared_vars - template_vars
        if unused:
            print(f"⚠️  Предупреждение: объявленные, но неиспользуемые переменные: {sorted(unused)}")

        return values

    def render(self, **kwargs) -> str:
        """Безопасный рендеринг шаблона с валидацией переменных"""
        # Проверяем обязательные переменные
        required_vars = {v.name for v in self.variables if v.required}
        missing = required_vars - set(kwargs.keys())
        if missing:
            raise ValueError(f"Отсутствуют обязательные переменные: {missing}")

        # Рендерим шаблон
        try:
            return self.content.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Ошибка рендеринга: неизвестная переменная {e}")