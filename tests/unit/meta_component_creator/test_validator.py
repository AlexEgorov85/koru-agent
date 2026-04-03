"""
Юнит-тесты для ComponentValidator — AST/YAML валидатора артефактов.
"""
import pytest
from core.services.skills.meta_component_creator.validator import ComponentValidator, SkillValidator


@pytest.fixture
def validator():
    return ComponentValidator()


class TestValidateSkill:
    """Тесты валидации навыков."""

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
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is True
        assert result["error_count"] == 0

    def test_missing_base_skill(self, validator):
        code = (
            "class TestSkill:\n"
            "    pass\n"
        )
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is False


class TestValidateTool:
    """Тесты валидации инструментов."""

    def test_valid_tool_file(self, validator):
        code = (
            "from core.services.tools.base_tool import BaseTool, ToolInput, ToolOutput\n"
            "from typing import Dict, Any\n"
            "\n"
            "class TestTool(BaseTool):\n"
            "    def get_capabilities(self):\n"
            "        return []\n"
            "\n"
            "    def _execute_impl(self, capability, parameters, execution_context):\n"
            "        return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"test_tool.py": code},
            yaml_files={},
            component_name="test",
            component_type="tool",
        )
        assert result["is_valid"] is True

    def test_missing_base_tool(self, validator):
        code = (
            "class TestTool:\n"
            "    pass\n"
        )
        result = validator.validate_artifacts(
            python_files={"test_tool.py": code},
            yaml_files={},
            component_name="test",
            component_type="tool",
        )
        assert result["is_valid"] is False


class TestValidateService:
    """Тесты валидации сервисов."""

    def test_valid_service_file(self, validator):
        code = (
            "from core.services.base_service import BaseService\n"
            "from typing import Dict, Any\n"
            "\n"
            "class TestService(BaseService):\n"
            "    def get_capabilities(self):\n"
            "        return []\n"
            "\n"
            "    def _execute_impl(self, capability, parameters, execution_context):\n"
            "        return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"service.py": code},
            yaml_files={},
            component_name="test",
            component_type="service",
        )
        assert result["is_valid"] is True

    def test_missing_base_service(self, validator):
        code = (
            "class TestService:\n"
            "    pass\n"
        )
        result = validator.validate_artifacts(
            python_files={"service.py": code},
            yaml_files={},
            component_name="test",
            component_type="service",
        )
        assert result["is_valid"] is False


class TestValidateBehavior:
    """Тесты валидации поведений."""

    def test_valid_behavior_file(self, validator):
        code = (
            "from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern\n"
            "from typing import Dict, Any\n"
            "\n"
            "class TestPattern(BaseBehaviorPattern):\n"
            "    def get_capabilities(self):\n"
            "        return []\n"
            "\n"
            "    def _execute_impl(self, capability, parameters, execution_context):\n"
            "        return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"pattern.py": code},
            yaml_files={},
            component_name="test",
            component_type="behavior",
        )
        assert result["is_valid"] is True

    def test_missing_base_behavior(self, validator):
        code = (
            "class TestPattern:\n"
            "    pass\n"
        )
        result = validator.validate_artifacts(
            python_files={"pattern.py": code},
            yaml_files={},
            component_name="test",
            component_type="behavior",
        )
        assert result["is_valid"] is False


class TestDangerousImports:
    """Тесты на запрещённые импорты."""

    def test_dangerous_import_rejected(self, validator):
        code = "import os\nimport subprocess\n"
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            component_name="test",
            component_type="skill",
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
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is False

    def test_syntax_error_detected(self, validator):
        code = "def broken(:\n    pass\n"
        result = validator.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is False
        assert any("SyntaxError" in e["message"] for e in result["errors"])

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
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is True


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
            component_name="test",
            component_type="skill",
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
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is True

    def test_invalid_yaml_rejected(self, validator):
        yaml_content = "invalid: yaml: [unclosed"
        result = validator.validate_artifacts(
            python_files={},
            yaml_files={"test.user_v1.0.0.yaml": yaml_content},
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is False

    def test_empty_yaml_rejected(self, validator):
        yaml_content = "# just a comment"
        result = validator.validate_artifacts(
            python_files={},
            yaml_files={"test.user_v1.0.0.yaml": yaml_content},
            component_name="test",
            component_type="skill",
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
            component_name="test",
            component_type="skill",
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
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is False
        assert any("schema_data" in e["message"] for e in result["errors"])


class TestCrossArtifactValidation:
    """Кросс-проверки между артефактами."""

    def test_missing_python_files(self, validator):
        result = validator.validate_artifacts(
            python_files={},
            yaml_files={},
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is False

    def test_missing_main_file_skill(self, validator):
        result = validator.validate_artifacts(
            python_files={"helper.py": "pass"},
            yaml_files={},
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is False

    def test_missing_main_file_service(self, validator):
        result = validator.validate_artifacts(
            python_files={"helper.py": "pass"},
            yaml_files={},
            component_name="test",
            component_type="service",
        )
        assert result["is_valid"] is False

    def test_missing_main_file_behavior(self, validator):
        result = validator.validate_artifacts(
            python_files={"helper.py": "pass"},
            yaml_files={},
            component_name="test",
            component_type="behavior",
        )
        assert result["is_valid"] is False

    def test_tool_no_main_file_required(self, validator):
        code = (
            "from core.services.tools.base_tool import BaseTool\n"
            "class TestTool(BaseTool):\n"
            "    def get_capabilities(self): return []\n"
            "    def _execute_impl(self, c, p, e): return {}\n"
        )
        result = validator.validate_artifacts(
            python_files={"test_tool.py": code},
            yaml_files={},
            component_name="test",
            component_type="tool",
        )
        assert result["is_valid"] is True


class TestSkillValidatorAlias:
    """Тест обратной совместимости: SkillValidator = ComponentValidator."""

    def test_alias_works(self):
        v = SkillValidator()
        code = (
            "from core.services.skills.base_skill import BaseSkill\n"
            "class TestSkill(BaseSkill):\n"
            "    def get_capabilities(self): return []\n"
            "    async def _execute_impl(self, c, p, e): return {}\n"
        )
        result = v.validate_artifacts(
            python_files={"skill.py": code},
            yaml_files={},
            component_name="test",
            component_type="skill",
        )
        assert result["is_valid"] is True
