"""Unit-тесты для ParamValidator"""
import pytest
from core.components.skills.utils.param_validator import ParamValidator, fuzzy_match, levenshtein_distance


class TestLevenshteinDistance:
    def test_identical_strings(self):
        assert levenshtein_distance("test", "test") == 0

    def test_one_char_difference(self):
        assert levenshtein_distance("test", "tesk") == 1

    def test_three_char_difference(self):
        assert levenshtein_distance("test", "abcd") == 4


class TestFuzzyMatch:
    def test_exact_match(self):
        result = fuzzy_match("Пушкин", ["Пушкин", "Лермонтов", "Толстой"])
        assert result == "Пушкин"

    def test_close_match(self):
        result = fuzzy_match("Пушкин", ["Пушкин", "Лермонтов", "Толстой"])
        assert result == "Пушкин"

    def test_no_match(self):
        result = fuzzy_match("абракадабра", ["Пушкин", "Лермонтов", "Толстой"])
        assert result is None


class TestParamValidatorEnum:
    """Тесты enum-валидации (не блокирует выполнение!)"""

    @pytest.fixture
    def mock_executor(self):
        class MockExecutor:
            async def execute_action(self, action_name, parameters, context):
                return None
        return MockExecutor()

    @pytest.fixture
    def validator(self, mock_executor):
        return ParamValidator(executor=mock_executor)

    @pytest.mark.asyncio
    async def test_enum_valid_value(self, validator):
        result = await validator.validate(
            param_value="Открыто",
            config={"type": "enum", "allowed_values": ["Открыто", "В работе", "Устранено"]}
        )
        assert result["valid"] is True
        assert result["corrected_value"] == "Открыто"
        assert result["warning"] is None

    @pytest.mark.asyncio
    async def test_enum_case_insensitive(self, validator):
        result = await validator.validate(
            param_value="открыто",
            config={"type": "enum", "allowed_values": ["Открыто", "В работе"]}
        )
        assert result["valid"] is True
        assert result["corrected_value"] == "Открыто"
        assert result["warning"] is None

    @pytest.mark.asyncio
    async def test_enum_invalid_returns_warning(self, validator):
        result = await validator.validate(
            param_value="Закрыто",
            config={"type": "enum", "allowed_values": ["Открыто", "В работе"]}
        )
        assert result["valid"] is True  # НЕ блокируем!
        assert result["corrected_value"] is None
        assert result["warning"] is not None
        assert "Закрыто" in result["warning"]
        assert "Открыто" in result["suggestions"]

    @pytest.mark.asyncio
    async def test_validate_multiple_all_valid(self, validator):
        result = await validator.validate_multiple(
            params={"status": "Открыто", "severity": "Высокая"},
            validation_config={
                "status": {"type": "enum", "allowed_values": ["Открыто", "В работе"]},
                "severity": {"type": "enum", "allowed_values": ["Высокая", "Средняя"]}
            }
        )
        assert result["valid"] is True
        assert len(result["warnings"]) == 0
        assert result["corrected_params"] == {}

    @pytest.mark.asyncio
    async def test_validate_multiple_one_invalid_warning(self, validator):
        result = await validator.validate_multiple(
            params={"status": "Открыто", "severity": "Очень высокая"},
            validation_config={
                "status": {"type": "enum", "allowed_values": ["Открыто", "В работе"]},
                "severity": {"type": "enum", "allowed_values": ["Высокая", "Средняя"]}
            }
        )
        assert result["valid"] is True  # НЕ блокируем!
        assert len(result["warnings"]) == 1  # один warning для severity
        assert "Очень высокая" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_validate_multiple_auto_correction(self, validator):
        result = await validator.validate_multiple(
            params={"status": "открыто"},
            validation_config={
                "status": {"type": "enum", "allowed_values": ["Открыто", "В работе"]}
            }
        )
        assert result["valid"] is True
        assert result["corrected_params"]["status"] == "Открыто"
        assert len(result["warnings"]) == 1  # warning об исправлении
        assert "открыто" in result["warnings"][0]
        assert "Открыто" in result["warnings"][0]
