"""
Типизированная модель промпта с полной валидацией.
"""
from pydantic import BaseModel, Field, validator, root_validator, ConfigDict
from typing import List, Optional, Dict

from core.models.data.base_template_validator import TemplateValidatorMixin
from core.models.enums.common_enums import ComponentType, PromptStatus


class PromptVariable(BaseModel):
    """Метаданные переменной промпта"""
    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str = Field(..., min_length=5)
    required: bool = Field(default=True)
    default_value: Optional[str] = None


class Prompt(TemplateValidatorMixin, BaseModel):
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

        # Используем унифицированный метод валидации
        _, warnings = cls.validate_jinja_template(
            template_content=content,
            declared_variables=declared_vars,
            component_info=f"prompt {values.get('capability', 'unknown')}@{values.get('version', 'unknown')}",
            template_field="template"
        )

        # Выводим предупреждения
        for warning in warnings:
            print(warning.encode('ascii', 'replace').decode('ascii') if isinstance(warning, str) else warning)

        return values

    def validate_templates(self) -> List[str]:
        """
        Валидация всех шаблонов в промпте.
        
        Returns:
            list: список предупреждений
        """
        warnings = []
        declared_vars = {v.name for v in self.variables}
        
        _, template_warnings = self.validate_jinja_template(
            template_content=self.content,
            declared_variables=declared_vars,
            component_info=f"prompt {self.capability}@{self.version}",
            template_field="template"
        )
        
        warnings.extend(template_warnings)
        return warnings

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