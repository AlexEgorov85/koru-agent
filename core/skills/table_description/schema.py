from pydantic import BaseModel, Field

class TableDescriptionParams(BaseModel):
    """
    Параметры для получения описания таблицы.
    """
    schema_name: str = Field("Lib", description="Имя схемы БД")
    table_name: str = Field(..., description="Название таблицы")
    format: str = Field("text", enum=["text", "json", "markdown"], description="Формат вывода")
    include_examples: bool = Field(True, description="Включать примеры данных")
    max_examples: int = Field(3, ge=1, le=10, description="Максимальное количество примеров")