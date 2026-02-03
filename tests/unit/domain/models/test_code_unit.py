"""Тесты для модели CodeUnit"""
import pytest
from domain.models.code.code_unit import CodeSpan, CodeUnit, CodeUnitType, Location


class TestCodeUnit:
    """Тесты для модели CodeUnit"""
    
    def test_create_code_unit_with_valid_data(self):
        """Тест создания CodeUnit с валидными данными"""
        code_unit = CodeUnit(
            id="test_id",
            name="test_unit",
            type=CodeUnitType.FUNCTION,
            location=Location(
                file_path="test/path.py",
                start_line=1,
                end_line=10,
                start_column=1,
                end_column=10
            ),
            code_span=CodeSpan(source_code="def test(): pass")
        )
        
        assert code_unit.name == "test_unit"
        assert code_unit.id == "test_id"
        assert code_unit.type == CodeUnitType.FUNCTION
        assert code_unit.code_span.source_code == "def test(): pass"
    
    def test_code_unit_str_representation(self):
        """Тест строкового представления CodeUnit"""
        from domain.models.code.code_unit import CodeUnit, CodeUnitType, Location, CodeSpan
        code_unit = CodeUnit(
            id="test_id",
            name="test_unit",
            type=CodeUnitType.FUNCTION,
            location=Location(
                file_path="test/path.py",
                start_line=1,
                end_line=10,
                start_column=1,
                end_column=10
            ),
            code_span=CodeSpan(source_code="def test(): pass")
        )
        
        # Проверяем, что строковое представление содержит тип и имя юнита
        assert "function" in str(code_unit)  # тип в нижнем регистре
        assert "test_unit" in str(code_unit)
    
    def test_code_unit_repr_contains_essential_fields(self):
        """Тест repr содержит основные поля"""
        from domain.models.code.code_unit import CodeUnit, CodeUnitType, Location, CodeSpan
        code_unit = CodeUnit(
            id="test_id",
            name="test_unit",
            type=CodeUnitType.FUNCTION,
            location=Location(
                file_path="test/path.py",
                start_line=1,
                end_line=10,
                start_column=1,
                end_column=10
            ),
            code_span=CodeSpan(source_code="def test(): pass")
        )
        
        repr_str = repr(code_unit)
        assert "test_id" in repr_str
        assert "test_unit" in repr_str
