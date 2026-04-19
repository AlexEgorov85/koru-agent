"""Сервис построения observation-сигналов для AgentRuntime.

АРХИТЕКТУРА:
- Выделен из AgentRuntime для соблюдения SRP.
- Runtime оркестрирует цикл, а сервис формирует доменные сигналы качества шага.
"""

from typing import Optional, Dict, Any, List, Literal

from pydantic import BaseModel, Field

from core.agent.components.sql_recovery import SQLRecoveryAnalyzer
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus


class ObservationSignalService:
    """Формирует унифицированный observation-сигнал по результату действия."""

    def __init__(self, sql_recovery_analyzer: Optional[SQLRecoveryAnalyzer] = None):
        self.sql_recovery_analyzer = sql_recovery_analyzer or SQLRecoveryAnalyzer()

    def build_signal(
        self,
        result: ExecutionResult,
        action_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Построить observation-сигнал для state/policy/prompt."""
        if result.status == ExecutionStatus.FAILED:
            return self._to_payload(
                status="error",
                quality="low",
                issues=[result.error or "unknown_error"],
                insight=result.error or "Ошибка выполнения действия",
                hint="Измени стратегию и выбери альтернативное действие",
            )

        if result.data in (None, {}, [], ""):
            hint = "Уточни параметры или выбери другой инструмент"
            issues = ["empty_result"]

            if self.sql_recovery_analyzer.is_sql_action(action_name):
                sql_analysis = self.sql_recovery_analyzer.analyze_empty_result(parameters)
                issues.extend(sql_analysis.get("issues", []))
                hint = sql_analysis.get("next_step_hint", hint)

            return self._to_payload(
                status="empty",
                quality="useless",
                issues=issues,
                insight="Действие завершилось без полезных данных",
                hint=hint,
            )

        return self._to_payload(
            status="success",
            quality="high",
            issues=[],
            insight="Получен полезный результат",
            hint="Продолжай по текущему плану",
        )

    def _to_payload(
        self,
        status: str,
        quality: str,
        issues: List[str],
        insight: str,
        hint: str,
    ) -> Dict[str, Any]:
        """Провалидировать и вернуть унифицированный payload сигнала."""
        signal = ObservationSignal(
            status=status,
            quality=quality,
            issues=issues,
            insight=insight,
            hint=hint,
        )
        payload = signal.model_dump()
        # Обратная совместимость со старым полем.
        payload["next_step_hint"] = signal.hint
        return payload


class ObservationSignal(BaseModel):
    """Контракт observation-сигнала для Runtime/Policy/Prompt."""

    status: Literal["error", "empty", "success"] = Field(
        ..., description="Результат шага в терминах сигнала."
    )
    quality: Literal["low", "useless", "high"] = Field(
        ..., description="Оценка полезности результата шага."
    )
    issues: List[str] = Field(
        default_factory=list, description="Список диагностических тегов."
    )
    insight: str = Field(..., description="Краткая интерпретация результата.")
    hint: str = Field(..., description="Рекомендация для следующего шага.")
