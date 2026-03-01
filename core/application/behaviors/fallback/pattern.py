from core.application.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
from core.session_context.session_context import SessionContext
import logging
from typing import List, Dict, Any


class FallbackPattern(BaseBehaviorPattern):
    """
    Паттерн интеллектуального восстановления.
    Используется при ошибках для диагностики и восстановления.
    
    АРХИТЕКТУРА:
    - component_name используется для получения config из AppConfig
    - pattern_id генерируется из component_name для совместимости
    """

    def __init__(self, component_name: str, component_config = None, application_context = None, executor = None):
        """Инициализация паттерна.
        
        ПАРАМЕТРЫ:
        - component_name: Имя компонента (ОБЯЗАТЕЛЬНО, например "fallback_pattern")
        - component_config: ComponentConfig с resolved_prompts/contracts (из AppConfig)
        - application_context: Прикладной контекст
        - executor: ActionExecutor для взаимодействия
        """
        super().__init__(component_name, component_config, application_context, executor)

    async def analyze_context(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        return {
            "recent_errors": session_context.get_recent_errors(limit=3) if hasattr(session_context, 'get_recent_errors') else [],
            "available_capabilities": available_capabilities,
            "session_summary": session_context.get_summary()
        }

    async def generate_decision(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        # Анализ последних ошибок
        recent_errors = context_analysis["recent_errors"]

        # Версии паттернов из конфигурации (ПРАВИЛЬНО)
        default_fallback_pattern = self.component_config.parameters.get(
            "default_fallback_pattern",
            "react_pattern"
        ) if self.component_config else "react_pattern"

        if self._is_transient_error(recent_errors):
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern=default_fallback_pattern,  # Из конфига
                reason="fallback_transient_error"
            )
        elif self._is_capability_error(recent_errors):
            # Попытка найти альтернативный инструмент
            alt_cap = await self._find_alternative_capability(session_context, available_capabilities, recent_errors)
            if alt_cap:
                return BehaviorDecision(
                    action=BehaviorDecisionType.ACT,
                    capability_name=alt_cap.name,
                    reason="fallback_alternative_capability"
                )
        elif self._is_planning_error(recent_errors):
            # Ошибка планирования - переключение на реактивный режим
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern=default_fallback_pattern,  # Из конфига
                reason="fallback_planning_error_use_react"
            )
        else:
            # Критическая ошибка → безопасная остановка с отчётом
            failure_report = self._generate_failure_report(session_context)
            return BehaviorDecision(
                action=BehaviorDecisionType.STOP,
                reason="critical_failure",
                parameters={"failure_report": failure_report}
            )

    def _is_transient_error(self, recent_errors) -> bool:
        """Проверка на временные ошибки (сетевые, таймауты и т.д.)"""
        if not recent_errors:
            return False

        transient_keywords = ["timeout", "network", "connection", "temporarily unavailable"]
        for error in recent_errors:
            error_str = str(error).lower()
            if any(keyword in error_str for keyword in transient_keywords):
                return True
        return False

    def _is_capability_error(self, recent_errors) -> bool:
        """Проверка на ошибки конкретных capability"""
        if not recent_errors:
            return False

        capability_keywords = ["capability", "not found", "not available", "missing", "unavailable"]
        for error in recent_errors:
            error_str = str(error).lower()
            if any(keyword in error_str for keyword in capability_keywords):
                return True
        return False

    def _is_planning_error(self, recent_errors) -> bool:
        """Проверка на ошибки планирования"""
        if not recent_errors:
            return False

        planning_keywords = ["planning", "plan", "step", "dependency", "sequence"]
        for error in recent_errors:
            error_str = str(error).lower()
            if any(keyword in error_str for keyword in planning_keywords):
                return True
        return False

    async def _find_alternative_capability(self, session_context: SessionContext, available_capabilities: List[Capability], recent_errors):
        """Поиск альтернативной capability для выполнения"""
        try:
            # Попробовать найти подходящую альтернативу
            # На основе типа последней ошибки
            if recent_errors:
                last_error = str(recent_errors[0]).lower()

                # Попробовать найти capability с похожей функциональностью
                for cap in available_capabilities:
                    if "search" in cap.name.lower() or "query" in cap.name.lower() or "find" in cap.name.lower():
                        return cap

            return None
        except Exception as e:
            self.event_bus_logger.error(f"Ошибка при поиске альтернативной capability: {str(e)}")
            return None

    def _generate_failure_report(self, session_context: SessionContext):
        """Генерация отчета о сбое"""
        try:
            summary = session_context.get_summary() if session_context and hasattr(session_context, 'get_summary') else {}
            return {
                "status": "failed",
                "failure_type": "critical",
                "session_summary": summary,
                "recommendation": "Manual intervention required"
            }
        except Exception:
            return {
                "status": "failed",
                "failure_type": "critical",
                "session_summary": "Unable to generate summary",
                "recommendation": "Manual intervention required"
            }