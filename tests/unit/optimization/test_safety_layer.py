"""
Тесты для SafetyLayer.
"""
import pytest
from unittest.mock import AsyncMock

from core.models.data.benchmark import EvaluationResult
from core.application.components.optimization.safety_layer import (
    SafetyLayer,
    SafetyConfig,
    SafetyCheckType,
)


class TestSafetyLayer:
    """Тесты для SafetyLayer"""

    @pytest.fixture
    def event_bus(self):
        """Mock event bus"""
        mock = AsyncMock()
        mock.publish = AsyncMock()
        return mock

    @pytest.fixture
    def safety_layer(self, event_bus):
        """Создание SafetyLayer"""
        return SafetyLayer(event_bus)

    def create_evaluation(
        self,
        success_rate=0.8,
        error_rate=0.2,
        latency=100,
        score=0.75
    ):
        """Хелпер для создания EvaluationResult"""
        return EvaluationResult(
            version_id="test",
            success_rate=success_rate,
            error_rate=error_rate,
            latency=latency,
            execution_success=1.0 - error_rate,
            sql_validity=1.0,
            score=score
        )

    @pytest.mark.asyncio
    async def test_check_safe_candidate(self, safety_layer):
        """Проверка безопасного кандидата"""
        baseline = self.create_evaluation(success_rate=0.8, error_rate=0.2, latency=100)
        candidate = self.create_evaluation(success_rate=0.85, error_rate=0.15, latency=110)

        is_safe, checks = await safety_layer.check(candidate, baseline)

        assert is_safe is True
        assert all(c.passed for c in checks)

    @pytest.mark.asyncio
    async def test_check_degraded_success_rate(self, safety_layer):
        """Проверка ухудшения success_rate"""
        baseline = self.create_evaluation(success_rate=0.8, error_rate=0.2)
        candidate = self.create_evaluation(success_rate=0.7, error_rate=0.3)  # Ухудшение на 10%

        is_safe, checks = await safety_layer.check(candidate, baseline)

        assert is_safe is False
        
        sr_check = next(c for c in checks if c.check_type == SafetyCheckType.SUCCESS_RATE)
        assert sr_check.passed is False
        assert "ухудшился" in sr_check.message.lower()

    @pytest.mark.asyncio
    async def test_check_increased_error_rate(self, safety_layer):
        """Проверка увеличения error_rate"""
        baseline = self.create_evaluation(success_rate=0.8, error_rate=0.1)
        candidate = self.create_evaluation(success_rate=0.8, error_rate=0.2)  # Увеличение на 10%

        is_safe, checks = await safety_layer.check(candidate, baseline)

        assert is_safe is False
        
        er_check = next(c for c in checks if c.check_type == SafetyCheckType.ERROR_RATE)
        assert er_check.passed is False

    @pytest.mark.asyncio
    async def test_check_latency_spike(self, safety_layer):
        """Проверка скачка latency"""
        baseline = self.create_evaluation(success_rate=0.8, latency=100)
        candidate = self.create_evaluation(success_rate=0.85, latency=200)  # Увеличение в 2 раза

        is_safe, checks = await safety_layer.check(candidate, baseline)

        assert is_safe is False
        
        lat_check = next(c for c in checks if c.check_type == SafetyCheckType.LATENCY_SPIKE)
        assert lat_check.passed is False
        assert "увеличился" in lat_check.message.lower()

    @pytest.mark.asyncio
    async def test_check_low_score(self, safety_layer):
        """Проверка низкого score"""
        baseline = self.create_evaluation(success_rate=0.8, score=0.75)
        candidate = self.create_evaluation(success_rate=0.7, score=0.5)  # Score ниже минимума

        is_safe, checks = await safety_layer.check(candidate, baseline)

        assert is_safe is False

    @pytest.mark.asyncio
    async def test_check_empty_result(self, safety_layer):
        """Проверка пустых результатов"""
        baseline = self.create_evaluation(success_rate=0.8)
        candidate = EvaluationResult(
            version_id="test",
            success_rate=0.0,
            execution_success=0.0,
            error_rate=1.0
        )

        is_safe, checks = await safety_layer.check(candidate, baseline)

        assert is_safe is False
        
        empty_check = next(c for c in checks if c.check_type == SafetyCheckType.EMPTY_RESULT)
        assert empty_check.passed is False

    @pytest.mark.asyncio
    async def test_has_critical_failures(self, safety_layer):
        """Проверка критических провалов"""
        from core.application.components.optimization.safety_layer import SafetyCheck

        checks = [
            SafetyCheck(
                check_type=SafetyCheckType.SUCCESS_RATE,
                passed=False,
                message="Success rate degraded"
            ),
            SafetyCheck(
                check_type=SafetyCheckType.LATENCY_SPIKE,
                passed=True,
                message="Latency OK"
            )
        ]

        has_critical = safety_layer.has_critical_failures(checks)
        assert has_critical is True

    @pytest.mark.asyncio
    async def test_no_critical_failures(self, safety_layer):
        """Проверка отсутствия критических провалов"""
        from core.application.components.optimization.safety_layer import SafetyCheck

        checks = [
            SafetyCheck(
                check_type=SafetyCheckType.LATENCY_SPIKE,
                passed=False,
                message="Latency high"
            )
        ]

        has_critical = safety_layer.has_critical_failures(checks)
        # LATENCY_SPIKE не в critical_types
        assert has_critical is False

    @pytest.mark.asyncio
    async def test_get_safety_report(self, safety_layer):
        """Получение отчёта о безопасности"""
        baseline = self.create_evaluation(success_rate=0.8, error_rate=0.2, score=0.75)
        candidate = self.create_evaluation(success_rate=0.85, error_rate=0.15, score=0.80)

        is_safe, checks = await safety_layer.check(candidate, baseline)
        report = safety_layer.get_safety_report(candidate, baseline, checks)

        assert report['is_safe'] is True
        assert report['candidate_version'] == candidate.version_id
        assert report['baseline_version'] == baseline.version_id
        assert 'metrics_comparison' in report

    @pytest.mark.asyncio
    async def test_get_stats(self, safety_layer):
        """Получение статистики"""
        baseline = self.create_evaluation(success_rate=0.8)
        candidate = self.create_evaluation(success_rate=0.85)

        # Несколько проверок
        await safety_layer.check(candidate, baseline)
        await safety_layer.check(candidate, baseline)

        stats = safety_layer.get_stats()

        assert stats['total_checks'] == 2
        assert stats['passed'] == 2
        assert stats['regression_rate'] == 0.0

    @pytest.mark.asyncio
    async def test_custom_config(self, event_bus):
        """Проверка пользовательской конфигурации"""
        config = SafetyConfig(
            max_success_rate_degradation=0.01,  # 1% вместо 5%
            min_acceptable_score=0.9
        )
        safety_layer = SafetyLayer(event_bus, config)

        baseline = self.create_evaluation(success_rate=0.9, score=0.85)
        candidate = self.create_evaluation(success_rate=0.88, score=0.83)  # Ухудшение на 2%

        is_safe, checks = await safety_layer.check(candidate, baseline)

        # Должно быть отклонено из-за более строгого порога
        assert is_safe is False


class TestSafetyCheckType:
    """Тесты для SafetyCheckType"""

    def test_all_check_types(self):
        """Проверка всех типов проверок"""
        types = [
            SafetyCheckType.SUCCESS_RATE,
            SafetyCheckType.ERROR_RATE,
            SafetyCheckType.SQL_INJECTION,
            SafetyCheckType.EMPTY_RESULT,
            SafetyCheckType.LATENCY_SPIKE
        ]

        assert len(types) == 5
        assert SafetyCheckType.SQL_INJECTION.value == "sql_injection"
        assert SafetyCheckType.EMPTY_RESULT.value == "empty_result"
