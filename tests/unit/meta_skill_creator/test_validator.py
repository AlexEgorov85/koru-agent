"""
Юнит-тесты для SkillValidator — AST/YAML валидатора артефактов.
"""
import pytest
from core.services.skills.meta_skill_creator.validator import SkillValidator


@pytest.fixture
def validator():
    return SkillValidator()


class TestValidatePythonFile:
    """Тесты валидации Python-файлов."""

    def test_valid_skill_file(self, validator):
        code = (
            "from core.services.skills.base_skill import BaseSkill\n"
            "from typing import Dict, Any, List\n"
            "\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self):\n"
            "        return []\n"
            "\n"
            "    async def _execute_impl(self, capability, parameters, execution_context):\n"
            "        return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is True
        assert result["error_count"] == 0

    def test_dangerous_import_rejected(self, validator):
        code = "import os\nimport subprocess\n"
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is False
        assert result["error_count"] >= 1

    def test_eval_call_rejected(self, validator):
        code = (
            "from core.services.skills.base_skill import BaseSkill\n"
            "\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self):\n"
            "        return []\n"
            "\n"
            "    async def _execute_impl(self, capability, parameters, execution_context):\n"
            "        return eval(parameters['code'])\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is False

    def test_syntax_error_detected(self, validator):
        code = "def broken(:\n    pass\n"
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is False
        assert any("SyntaxError" in e["message"] for e in result["errors"])

    def test_missing_base_skill_inheritance(self, validator):
        code = (
            "class TestSkill:\n"
            "    pass\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is False

    def test_missing_execute_impl(self, validator):
        code = (
            "from core.services.skills.base_skill import BaseSkill\n"
            "\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self):\n"
            "        return []\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is False
        assert any("_execute_impl" in e["message"] for e in result["errors"])

    def test_safe_imports_accepted(self, validator):
        code = (
            "from typing import Dict, Any, List, Optional\n"
            "from datetime import datetime\n"
            "import json\n"
            "import re\n"
            "from core.services.skills.base_skill import BaseSkill\n"
            "from pydantic import BaseModel\n"
            "\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self):\n"
            "        return []\n"
            "\n"
            "    async def _execute_impl(self, capability, parameters, execution_context):\n"
            "        return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is True

    def test_unknown_import_is_warning_not_error(self, validator):
        code = (
            "import some_unknown_lib\n"
            "from core.services.skills.base_skill import BaseSkill\n"
            "\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self):\n"
            "        return []\n"
            "\n"
            "    async def _execute_impl(self, capability, parameters, execution_context):\n"
            "        return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is True
        assert result["warning_count"] >= 1


class TestValidateYamlFile:
    """Тесты валидации YAML-файлов."""

    def test_valid_prompt_yaml(self, validator):
        yaml_content = (
            "capability: test.create\n"
            "version: v1.0.0\n"
            "status: active\n"
            "content: |\n  Hello world\n"
        )
        code = (
            "from core.services.skills.base_skill import BaseSkill\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self): return []\n"
            "    async def _execute_impl(self, c, p, e): return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={"test.create.user_v1.0.0.yaml": yaml_content},
            skill_name="test",
        )
        assert result["is_valid"] is True

    def test_valid_contract_yaml(self, validator):
        yaml_content = (
            "capability: test.create\n"
            "direction: input\n"
            "version: v1.0.0\n"
            "schema_data:\n"
            "  type: object\n"
            "  properties:\n"
            "    query:\n"
            "      type: string\n"
            "status: active\n"
        )
        code = (
            "from core.services.skills.base_skill import BaseSkill\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self): return []\n"
            "    async def _execute_impl(self, c, p, e): return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={"test.create_input_v1.0.0.yaml": yaml_content},
            skill_name="test",
        )
        assert result["is_valid"] is True

    def test_invalid_yaml_rejected(self, validator):
        yaml_content = "invalid: yaml: [unclosed"
        result = validator.validate_artifacts(
            python_files={},
            yaml_files={"test.user_v1.0.0.yaml": yaml_content},
            skill_name="test",
        )
        assert result["is_valid"] is False

    def test_empty_yaml_rejected(self, validator):
        yaml_content = "# just a comment"
        result = validator.validate_artifacts(
            python_files={},
            yaml_files={"test.user_v1.0.0.yaml": yaml_content},
            skill_name="test",
        )
        assert result["is_valid"] is False

    def test_prompt_missing_content(self, validator):
        yaml_content = (
            "capability: test.create\n"
            "version: v1.0.0\n"
        )
        result = validator.validate_artifacts(
            python_files={},
            yaml_files={"test.create.user_v1.0.0.yaml": yaml_content},
            skill_name="test",
        )
        assert result["is_valid"] is False
        assert any("content" in e["message"] for e in result["errors"])

    def test_contract_missing_schema(self, validator):
        yaml_content = (
            "capability: test.create\n"
            "direction: input\n"
        )
        code = (
            "from core.services.skills.base_skill import BaseSkill\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self): return []\n"
            "    async def _execute_impl(self, c, p, e): return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={"test.create_input_v1.0.0.yaml": yaml_content},
            skill_name="test",
        )
        assert result["is_valid"] is False
        assert any("schema_data" in e["message"] for e in result["errors"])


class TestCrossArtifactValidation:
    """Кросс-проверки между артефактами."""

    def test_missing_python_files(self, validator):
        result = validator.validate_artifacts(
            python_files={},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is False

    def test_missing_skill_py(self, validator):
        result = validator.validate_artifacts(
            python_files={"helper.py": "pass"},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is False

    def test_missing_yaml_is_warning(self, validator):
        code = (
            "from core.services.skills.base_skill import BaseSkill\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self): return []\n"
            "    async def _execute_impl(self, c, p, e): return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            skill_name="test",
        )
        assert result["is_valid"] is True
        assert result["warning_count"] >= 1
