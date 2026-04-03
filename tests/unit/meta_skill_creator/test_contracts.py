"""
Юнит-тесты для контрактов мета-навыка.
"""
import pytest
from pydantic import ValidationError
from core.services.skills.meta_skill_creator.contracts.meta_skill import (
    MetaSkillCreateInput,
    MetaSkillCreateOutput,
    MetaSkillFixInput,
    MetaSkillFixOutput,
    MetaSkillReviewInput,
    MetaSkillReviewOutput,
    GeneratedPythonFile,
    GeneratedYamlFile,
    ReviewFinding,
)


class TestMetaSkillCreateInput:
    def test_minimal_valid(self):
        inp = MetaSkillCreateInput(description="Создать навык для поиска")
        assert inp.description == "Создать навык для поиска"
        assert inp.dry_run is True
        assert inp.capabilities == []

    def test_full_valid(self):
        inp = MetaSkillCreateInput(
            description="Навык для парсинга",
            capabilities=["parse.url", "parse.extract"],
            dry_run=False,
        )
        assert inp.dry_run is False
        assert len(inp.capabilities) == 2

    def test_missing_description(self):
        with pytest.raises(ValidationError):
            MetaSkillCreateInput()


class TestMetaSkillCreateOutput:
    def test_valid_output(self):
        out = MetaSkillCreateOutput(
            skill_name="test_skill",
            skill_class_name="TestSkillSkill",
            is_valid=True,
        )
        assert out.skill_name == "test_skill"
        assert out.python_files == []

    def test_with_files(self):
        out = MetaSkillCreateOutput(
            skill_name="test_skill",
            skill_class_name="TestSkillSkill",
            python_files=[
                GeneratedPythonFile(filename="skill.py", content="pass"),
            ],
            yaml_files=[
                GeneratedYamlFile(filename="prompt.yaml", content="content: hi"),
            ],
            is_valid=True,
        )
        assert len(out.python_files) == 1
        assert len(out.yaml_files) == 1


class TestMetaSkillFixInput:
    def test_minimal_valid(self):
        inp = MetaSkillFixInput(
            skill_name="existing_skill",
            issue_description="Ошибка валидации",
        )
        assert inp.dry_run is True

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            MetaSkillFixInput(skill_name="test")


class TestMetaSkillReviewInput:
    def test_minimal_valid(self):
        inp = MetaSkillReviewInput(skill_name="some_skill")
        assert inp.review_focus is None

    def test_with_focus(self):
        inp = MetaSkillReviewInput(
            skill_name="some_skill",
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
