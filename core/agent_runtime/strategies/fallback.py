from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from .base import AgentStrategyInterface
import logging


class FallbackStrategy(AgentStrategyInterface):
    """
    Стратегия интеллектуального восстановления.
    Используется при ошибках для диагностики и восстановления.
    """

    name = "fallback"
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def next_step(self, runtime):
        # Анализ последних ошибок
        recent_errors = runtime.session.get_recent_errors(limit=3) if hasattr(runtime.session, 'get_recent_errors') else []
        
        if self._is_transient_error(recent_errors):
            return StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                next_strategy="react",  # Повторить с простой стратегией
                reason="fallback_transient_error"
            )
        elif self._is_capability_error(recent_errors):
            # Попытка найти альтернативный инструмент
            alt_cap = await self._find_alternative_capability(runtime, recent_errors)
            if alt_cap:
                return StrategyDecision(
                    action=StrategyDecisionType.ACT,
                    capability=alt_cap,
                    reason="fallback_alternative_capability"
                )
        elif self._is_planning_error(recent_errors):
            # Ошибка планирования - переключение на реактивный режим
            return StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                next_strategy="react",
                reason="fallback_planning_error_use_react"
            )
        else:
            # Критическая ошибка → безопасная остановка с отчётом
            failure_report = self._generate_failure_report(runtime.session)
            return StrategyDecision(
                action=StrategyDecisionType.STOP,
                reason="critical_failure",
                payload={"failure_report": failure_report}
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

    async def _find_alternative_capability(self, runtime, recent_errors):
        """Поиск альтернативной capability для выполнения"""
        try:
            # Получить список всех доступных capability
            all_caps = runtime.system.list_capabilities()
            
            # Попробовать найти подходящую альтернативу
            # На основе типа последней ошибки
            if recent_errors:
                last_error = str(recent_errors[0]).lower()

                # Попробовать найти capability с похожей функциональностью
                for cap_name in all_caps:
                    if "search" in cap_name.lower() or "query" in cap_name.lower() or "find" in cap_name.lower():
                        cap = runtime.system.get_capability(cap_name)
                        if cap:
                            return cap
            
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при поиске альтернативной capability: {str(e)}")
            return None

    def _generate_failure_report(self, session):
        """Генерация отчета о сбое"""
        try:
            summary = session.get_summary() if session and hasattr(session, 'get_summary') else {}
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
