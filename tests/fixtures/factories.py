"""Фабрики объектов для тестов"""
from domain.models.code.code_unit import CodeUnit
from domain.models.project.project_structure import ProjectStructure
from domain.models.session.context_item import ContextItem


class CodeUnitFactory:
    """Фабрика для создания объектов CodeUnit"""
    
    @staticmethod
    def create_sample_code_unit(name="test_unit", path="test/path.py", content="def test(): pass", signatures=None):
        """Создает экземпляр CodeUnit с тестовыми данными"""
        if signatures is None:
            signatures = []
        
        return CodeUnit(
            name=name,
            path=path,
            content=content,
            signatures=signatures
        )
    
    @staticmethod
    def create_multiple_code_units(count=3):
        """Создает несколько экземпляров CodeUnit"""
        units = []
        for i in range(count):
            unit = CodeUnitFactory.create_sample_code_unit(
                name=f"test_unit_{i}",
                path=f"test/path_{i}.py",
                content=f"def test_{i}(): pass"
            )
            units.append(unit)
        return units


class ProjectStructureFactory:
    """Фабрика для создания объектов ProjectStructure"""
    
    @staticmethod
    def create_sample_project_structure(name="test_project", root_path="./test_project"):
        """Создает экземпляр ProjectStructure с тестовыми данными"""
        return ProjectStructure(
            name=name,
            root_path=root_path,
            files=["file1.py", "file2.py", "file3.py"],
            directories=["dir1", "dir2"]
        )
    
    @staticmethod
    def create_complex_project_structure():
        """Создает экземпляр ProjectStructure со сложной структурой"""
        return ProjectStructure(
            name="complex_test_project",
            root_path="./complex_test_project",
            files=[
                "src/main.py",
                "src/utils/helper.py",
                "src/models/user.py",
                "tests/test_main.py",
                "docs/readme.md"
            ],
            directories=["src", "src/utils", "src/models", "tests", "docs"]
        )


class ContextItemFactory:
    """Фабрика для создания объектов ContextItem"""
    
    @staticmethod
    def create_sample_context_item(key="test_key", value="test_value", metadata=None):
        """Создает экземпляр ContextItem с тестовыми данными"""
        if metadata is None:
            metadata = {}
        
        return ContextItem(
            key=key,
            value=value,
            metadata=metadata
        )
    
    @staticmethod
    def create_multiple_context_items(count=3):
        """Создает несколько экземпляров ContextItem"""
        items = []
        for i in range(count):
            item = ContextItemFactory.create_sample_context_item(
                key=f"test_key_{i}",
                value=f"test_value_{i}"
            )
            items.append(item)
        return items