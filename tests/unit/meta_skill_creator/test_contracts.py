"""
Юнит-тесты для контрактов мета-навыка.
"""
import pytest
from pydantic import ValidationError
from core.services.skills.meta_skill_creator.contracts.meta_skill import (
    MetaComponentCreateInput,
    MetaComponentCreateOutput,
    MetaComponentFixInput,
    MetaComponentFixOutput,
    MetaComponentReviewInput,
    MetaComponentReviewOutput,
    GeneratedPythonFile,
    GeneratedYamlFile,
    ReviewFinding,
    VALID_COMPONENT_TYPES,
    TYPE_SUFFIXES,
    TYPE_FILE_NAMES,
)


class TestMetaComponentCreateInput:
    def test_minimal_valid(self):
        inp = MetaComponentCreateInput(description="Создать навык для поиска")
        assert inp.description == "Создать навык для поиска"
        assert inp.component_type == "skill"
        assert inp.has_prompts is True
        assert inp.has_contracts is True

    def test_full_valid(self):
        inp = MetaComponentCreateInput(
            description="Инструмент для HTTP-запросов",
            component_type="tool",
            capabilities=["http_tool.get", "http_tool.post"],
            has_prompts=False,
            has_contracts=True,
        )
        assert inp.component_type == "tool"
        assert inp.has_prompts is False
        assert len(inp.capabilities) == 2

    def test_missing_description(self):
        with pytest.raises(ValidationError):
            MetaComponentCreateInput()

    def test_invalid_component_type(self):
        inp = MetaComponentCreateInput(
            description="test",
            component_type="invalid_type",
        )
        assert inp.component_type == "invalid_type"


class TestMetaComponentCreateOutput:
    def test_valid_output(self):
        out = MetaComponentCreateOutput(
            component_name="test_skill",
            component_type="skill",
            class_name="TestSkillSkill",
            is_valid=True,
        )
        assert out.component_name == "test_skill"
        assert out.python_files == []

    def test_with_files(self):
        out = MetaComponentCreateOutput(
            component_name="test_tool",
            component_type="tool",
            class_name="TestToolTool",
            python_files=[
                GeneratedPythonFile(filename="test_tool.py", content="pass"),
            ],
            yaml_files=[
                GeneratedYamlFile(filename="test_tool.execute_input_v1.0.0.yaml", content="capability: test_tool.execute\ndirection: input\nschema_data:\n  type: object"),
            ],
            is_valid=True,
        )
        assert len(out.python_files) == 1
        assert len(out.yaml_files) == 1


class TestMetaComponentFixInput:
    def test_minimal_valid(self):
        inp = MetaComponentFixInput(
            component_name="existing_skill",
            issue_description="Ошибка валидации",
        )
        assert inp.component_type == "skill"

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            MetaComponentFixInput(component_name="test")


class TestMetaComponentReviewInput:
    def test_minimal_valid(self):
        inp = MetaComponentReviewInput(component_name="some_tool")
        assert inp.component_type == "skill"
        assert inp.review_focus is None

    def test_with_focus(self):
        inp = MetaComponentReviewInput(
            component_name="some_service",
            component_type="service",
            review_focus=["security", "performance"],
        )
        assert len(inp.review_focus) == 2


class TestReviewFinding:
    def test_valid_finding(self):
        f = ReviewFinding(
            category="security",
            severity="critical",
            file="skill.py",
            description="Опасный импорт",
            suggestion="Удалить import os",
        )
        assert f.severity == "critical"
        assert f.category == "security"


class TestConstants:
    def test_valid_component_types(self):
        assert "skill" in VALID_COMPONENT_TYPES
        assert "tool" in VALID_COMPONENT_TYPES
        assert "service" in VALID_COMPONENT_TYPES
        assert "behavior" in VALID_COMPONENT_TYPES
        assert len(VALID_COMPONENT_TYPES) == 4

    def test_type_suffixes(self):
        assert TYPE_SUFFIXES["skill"] == "Skill"
        assert TYPE_SUFFIXES["tool"] == "Tool"
        assert TYPE_SUFFIXES["service"] == "Service"
        assert TYPE_SUFFIXES["behavior"] == "Pattern"

    def test_type_file_names(self):
        assert TYPE_FILE_NAMES["skill"] == "skill.py"
        assert TYPE_FILE_NAMES["tool"] is None
        assert TYPE_FILE_NAMES["service"] == "service.py"
        assert TYPE_FILE_NAMES["behavior"] == "pattern.py"
