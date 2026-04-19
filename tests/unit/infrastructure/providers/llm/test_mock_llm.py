"""
Тесты MockLLM из tests.mocks.interfaces.

ПРОВЕРЯЕТ:
1. MockLLM соответствует LLMInterface
2. generate() возвращает правильные ответы по ключевым фразам
3. generate_structured() парсит JSON ответы
4. health_check() работает
5. call_count и prompt_history отслеживаются
"""
import pytest
import json
import asyncio

from tests.mocks.interfaces import MockLLM, create_audit_mock_llm


class TestMockLLMInterface:
    """Тесты соответствия MockLLM интерфейсу LLMInterface."""

    @pytest.mark.asyncio
    async def test_generate_with_prompt_and_system(self):
        """generate() принимает prompt и system_prompt строками."""
        mock = MockLLM(default_response="default")
        mock.register_response("вопрос", "ответ на вопрос")

        result = await mock.generate(
            prompt="это вопрос пользователя",
            system_prompt="ты — ассистент",
            temperature=0.5
        )

        assert result == "ответ на вопрос"
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_fallback_to_default(self):
        """Если ключ не найден — возвращает default_response."""
        mock = MockLLM(default_response="дефолтный ответ")
        mock.register_response("специфичный", "специфичный ответ")

        result = await mock.generate(prompt="какой-то другой вопрос")

        assert result == "дефолтный ответ"
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_structured_parses_json(self):
        """generate_structured() парсит JSON ответ."""
        mock = MockLLM()
        mock.register_response(
            " ReasoningResult",
            '{"stop_condition": false, "decision": {"next_action": "tool"}, "analysis_progress": "test"}'
        )

        schema = {
            "type": "object",
            "properties": {
                "stop_condition": {"type": "boolean"},
                "decision": {"type": "object"},
                "analysis_progress": {"type": "string"}
            }
        }

        result = await mock.generate_structured(
            prompt=" ReasoningResult запрос",
            response_schema=schema
        )

        assert result["stop_condition"] is False
        assert result["analysis_progress"] == "test"

    @pytest.mark.asyncio
    async def test_health_check_returns_status(self):
        """health_check() возвращает статус."""
        from core.models.types.llm_types import LLMHealthStatus

        mock = MockLLM()

        status = await mock.health_check()

        assert status == LLMHealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_prompt_history_tracks_prompts(self):
        """prompt_history сохраняет все промпты."""
        mock = MockLLM(default_response="ok")
        mock.register_response("a", "result A")

        await mock.generate(prompt="запрос A")
        await mock.generate(prompt="запрос B")

        assert len(mock.prompt_history) == 2
        assert "запрос A" in mock.prompt_history


class TestCreateAuditMockLLM:
    """Тесты фабрики create_audit_mock_llm()."""

    @pytest.mark.asyncio
    async def test_reasoning_result_response(self):
        """ReAct решения возвращают correct decision."""
        mock = create_audit_mock_llm()

        response = await mock.generate(
            prompt="Цель: Сколько проверок было проведено? ReasoningResult",
            system_prompt="ты — ReAct контроллер"
        )

        data = json.loads(response)

        assert data["stop_condition"] is False
        assert data["decision"]["next_action"] == "check_result.generate_script"
        assert "query" in data["decision"]["parameters"]

    @pytest.mark.asyncio
    async def test_sql_generation_response(self):
        """SQLGenerationOutput возвращает корректный SQL."""
        mock = create_audit_mock_llm()

        response = await mock.generate(
            prompt="=== ЗАПРОС ПОЛЬЗОВАТЕЛЯ ===\nсколько проверок\nSQLGenerationOutput",
            system_prompt="ты — эксперт по SQL"
        )

        data = json.loads(response)

        assert "generated_sql" in data
        assert "oarb.audits" in data["generated_sql"]
        assert data["confidence_score"] == 0.98

    @pytest.mark.asyncio
    async def test_final_answer_response(self):
        """final_answer возвращает текстовый ответ."""
        mock = create_audit_mock_llm()

        response = await mock.generate(
            prompt="=== final_answer.generate",
            system_prompt="ты — финальный ответ"
        )

        assert "проверок" in response.lower() or "данных" in response.lower()

    @pytest.mark.asyncio
    async def test_mock_counts_calls(self):
        """call_count увеличивается при каждом вызове."""
        mock = create_audit_mock_llm()

        await mock.generate(prompt=" ReasoningResult")
        await mock.generate(prompt="SQLGenerationOutput")
        await mock.generate(prompt="final_answer")

        assert mock.call_count == 3


class TestMockLLMFailures:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_should_fail_raises_timeout(self):
        """should_fail=True выбрасывает TimeoutError."""
        mock = MockLLM(should_fail=True)

        with pytest.raises(TimeoutError):
            await mock.generate(prompt="test")

    @pytest.mark.asyncio
    async def test_delay_simulates_slow_llm(self):
        """delay_seconds имитирует медленный LLM."""
        mock = MockLLM(delay_seconds=0.01, default_response="slow")

        start = asyncio.get_event_loop().time()
        await mock.generate(prompt="test")
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed >= 0.01

    @pytest.mark.asyncio
    async def test_invalid_json_returns_mock_values(self):
        """Невалидный JSON — возврат значений по схеме."""
        mock = MockLLM()
        mock.register_response("test", "not valid json")

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"}
            }
        }

        result = await mock.generate_structured(prompt="test", response_schema=schema)

        assert result["name"] == "Mock value"
        assert result["count"] == 0