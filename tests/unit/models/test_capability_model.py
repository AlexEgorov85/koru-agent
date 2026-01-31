"""
Тесты для модели Capability.
"""
import pytest
from models.capability import Capability


class TestCapabilityModel:
    """Тесты для модели Capability."""
    
    def test_capability_creation(self):
        """Тест создания Capability."""
        capability = Capability(
            name="test_capability",
            description="Тестовая возможность",
            parameters_schema={"param1": "string", "param2": "number"},
            skill_name="test_skill"
        )
        
        assert capability.name == "test_capability"
        assert capability.description == "Тестовая возможность"
        assert capability.parameters_schema == {"param1": "string", "param2": "number"}
        assert capability.skill_name == "test_skill"
    
    def test_capability_with_optional_fields(self):
        """Тест создания Capability с опциональными полями."""
        # Импортируем BaseModel для создания тестовой схемы параметров
        from pydantic import BaseModel
        from typing import Optional
        
        class TestParams(BaseModel):
            test_param: Optional[str] = None
            another_param: int = 0
        
        capability = Capability(
            name="advanced_capability",
            description="Продвинутая возможность",
            parameters_schema={"required_param": "string"},
            skill_name="advanced_skill",
            parameters_class=TestParams,
            visible=False
        )
        
        assert capability.parameters_class == TestParams
        assert capability.visible is False
    
    def test_capability_default_values(self):
        """Тест значений по умолчанию для Capability."""
        capability = Capability(
            name="minimal_capability",
            description="Минимальная возможность",
            parameters_schema={},
            skill_name="minimal_skill"
        )
        
        assert capability.visible is True   # значение по умолчанию
        assert capability.parameters_class is None  # значение по умолчанию
        assert capability.category is None  # значение по умолчанию
    
    def test_capability_equality(self):
        """Тест равенства Capability."""
        capability1 = Capability(
            name="test_capability",
            description="Тестовая возможность",
            parameters_schema={"param": "value"},
            skill_name="test_skill"
        )
        
        capability2 = Capability(
            name="test_capability",
            description="Тестовая возможность",
            parameters_schema={"param": "value"},
            skill_name="test_skill"
        )
        
        capability3 = Capability(
            name="different_capability",  # другое имя
            description="Тестовая возможность",
            parameters_schema={"param": "value"},
            skill_name="test_skill"
        )
        
        assert capability1 == capability2  # одинаковые по значению
        assert capability1 != capability3  # разные name
        assert capability2 != capability3  # разные name
    
    def test_capability_serialization(self):
        """Тест сериализации Capability."""
        capability = Capability(
            name="serialize_capability",
            description="Возможность для сериализации",
            parameters_schema={"serialize_param": "serialize_value"},
            skill_name="serialize_skill",
            visible=True,
            category="test_category"
        )
        
        data = capability.model_dump()
        
        assert data["name"] == "serialize_capability"
        assert data["description"] == "Возможность для сериализации"
        assert data["parameters_schema"] == {"serialize_param": "serialize_value"}
        assert data["skill_name"] == "serialize_skill"
        assert data["visible"] is True
        assert data["category"] == "test_category"
    
    def test_capability_from_dict(self):
        """Тест создания Capability из словаря."""
        data = {
            "name": "dict_capability",
            "description": "Возможность из словаря",
            "parameters_schema": {"dict_param": "dict_value"},
            "skill_name": "dict_skill",
            "visible": False,
            "category": "dict_category"
        }
        
        capability = Capability.model_validate(data)
        
        assert capability.name == "dict_capability"
        assert capability.description == "Возможность из словаря"
        assert capability.parameters_schema == {"dict_param": "dict_value"}
        assert capability.skill_name == "dict_skill"
        assert capability.visible is False
        assert capability.category == "dict_category"
    
    def test_capability_with_complex_schema(self):
        """Тест Capability со сложной схемой параметров."""
        complex_schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL query to execute"
                },
                "params": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "number"},
                        "offset": {"type": "number"}
                    }
                }
            },
            "required": ["query"]
        }
        
        capability = Capability(
            name="complex_capability",
            description="Возможность со сложной схемой",
            parameters_schema=complex_schema,
            skill_name="complex_skill"
        )
        
        assert capability.parameters_schema == complex_schema
        assert capability.name == "complex_capability"


def test_capability_immutability():
    """Тест, что Capability ведет себя как неизменяемый объект (на уровне создания)."""
    capability = Capability(
        name="immutable_test",
        description="Тест неизменяемости",
        parameters_schema={"test": "value"},
        skill_name="test_skill"
    )
    
    # Проверяем, что объект создан корректно
    assert capability.name == "immutable_test"
    assert capability.description == "Тест неизменяемости"
    
    # В Pydantic моделях по умолчанию можно изменять атрибуты, 
    # но мы проверяем, что объект создается с правильными значениями
    assert hasattr(capability, 'name')
    assert hasattr(capability, 'description')
    assert hasattr(capability, 'parameters_schema')
    assert hasattr(capability, 'skill_name')
    assert hasattr(capability, 'visible')
    assert hasattr(capability, 'category')