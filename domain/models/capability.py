from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
import importlib


class Capability(BaseModel):
    """Единая модель возможности для всего приложения"""
    name: str = Field(..., description="Уникальное имя capability")
    description: str = Field(..., description="Человекочитаемое описание")
    parameters_schema: Optional[Dict[str, Any]] = Field(None, description="JSON Schema параметров")
    skill_name: str = Field(..., description="Имя навыка-владельца")
    
    # НОВОЕ: поддержка валидации через Pydantic
    parameters_class: Optional[str] = Field(  # Храним имя класса, а не сам класс!
        None,
        description="Полное имя класса параметров (для десериализации)"
    )
    
    model_config = ConfigDict(frozen=True)  # Иммутабельность для безопасности
    
    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """Валидация параметров через динамическую загрузку класса"""
        if not self.parameters_class:
            return True  # Нет схемы валидации — пропускаем
        
        # Динамическая загрузка класса параметров
        try:
            module_path, class_name = self.parameters_class.rsplit('.', 1)
            module = importlib.import_module(module_path)
            param_class = getattr(module, class_name)
            param_class(**params)  # Попытка валидации
            return True
        except (ImportError, AttributeError, ValueError, TypeError) as e:
            raise ValueError(f"Ошибка валидации параметров: {e}")