"""
Менеджер стратегического управления для агента.
Содержит логику выбора и переключения стратегий на основе метрик и контекста.
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from core.agent_runtime.model import StrategyDecision, StrategyDecisionType


class StrategyName(str, Enum):
    REACT = "react"
    PLANNING = "planning"
    EVALUATION = "evaluation"
    FALLBACK = "fallback"


@dataclass
class StrategySwitchRecord:
    """Запись о переключении стратегии"""
    from_strategy: str
    to_strategy: str
    reason: str
    timestamp: datetime
    confidence: float
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategySwitchDecision:
    """Решение о переключении стратегии"""
    to_strategy: str
    reason: str
    confidence: float
    parameters: Optional[Dict[str, Any]] = None


class StrategyManager:
    """Менеджер стратегического управления"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.strategy_history: List[StrategySwitchRecord] = []
        self.progress_metrics = ProgressMetrics()
    
    async def select_initial_strategy(self, goal: str) -> str:
        """Интеллектуальный выбор первичной стратегии"""
        # 1. Анализ сложности через эвристики
        complexity = self._analyze_goal_complexity(goal)
        
        # 2. Анализ доступных инструментов
        # Note: В реальном приложении здесь будет доступ к runtime.system
        # has_planning_tools = any(c.skill_name == "planning" for c in available_tools)
        has_planning_tools = True  # предполагаем, что планировочные инструменты доступны
        
        # 3. Принятие решения
        if complexity >= 0.7 and has_planning_tools:
            return "planning"
        elif complexity >= 0.4:
            return "react"  # Для средней сложности — реактивный режим с возможностью апгрейда
        else:
            return "react"
    
    def _analyze_goal_complexity(self, goal: str) -> float:
        """Анализ сложности цели (0.0 - простая, 1.0 - сложная)"""
        # Эвристика: длинные цели с несколькими действиями - более сложные
        length_factor = min(len(goal.split()), 50) / 50  # до 50 слов
        action_words = ["и затем", "после этого", "в итоге", "затем", "сначала", "далее", "потом"]
        sequential_actions = sum(1 for word in action_words if word in goal.lower())
        sequential_factor = min(sequential_actions, 5) / 5  # до 5 последовательных действий
        
        # Комбинируем факторы
        complexity = (length_factor * 0.3 + sequential_factor * 0.7)
        return min(complexity, 1.0)  # ограничиваем значением 1.0
    
    async def should_switch_strategy(
        self, 
        current_strategy: str, 
        state_metrics: Dict[str, Any]
    ) -> Optional[StrategySwitchDecision]:
        """Оценка необходимости переключения во время выполнения"""
        # Критерий 1: Последовательные ошибки
        consecutive_errors = state_metrics.get('consecutive_errors', 0)
        if consecutive_errors >= 2:
            return StrategySwitchDecision(
                to_strategy="fallback",
                reason="consecutive_errors",
                confidence=0.9
            )
        
        # Критерий 2: Отсутствие прогресса
        no_progress_steps = state_metrics.get('no_progress_steps', 0)
        if no_progress_steps >= 3 and current_strategy == "react":
            # Апгрейд до планирования
            return StrategySwitchDecision(
                to_strategy="planning",
                reason="no_progress_in_react",
                confidence=0.75
            )
        
        # Критерий 3: Завершение плана
        if current_strategy == "planning" and state_metrics.get('plan_completed', False):
            return StrategySwitchDecision(
                to_strategy="evaluation",
                reason="plan_completed",
                confidence=0.95
            )
        
        # Критерий 4: Низкая эффективность текущей стратегии
        strategy_effectiveness = state_metrics.get('strategy_effectiveness', {})
        current_efficiency = strategy_effectiveness.get(current_strategy, 1.0)
        if current_efficiency < 0.3:  # Если эффективность ниже 30%
            # Попробуем другую стратегию
            alternative_strategy = self._suggest_alternative_strategy(current_strategy)
            if alternative_strategy:
                return StrategySwitchDecision(
                    to_strategy=alternative_strategy,
                    reason="low_strategy_effectiveness",
                    confidence=max(0.6, 1.0 - current_efficiency)
                )
        
        # Критерий 5: Достижение промежуточной цели в планировании
        if current_strategy == "planning" and state_metrics.get('current_step_completed', False):
            # После выполнения шага плана может потребоваться оценка
            return StrategySwitchDecision(
                to_strategy="evaluation",
                reason="step_completed_evaluation_needed",
                confidence=0.7
            )
        
        return None
    
    def _suggest_alternative_strategy(self, current_strategy: str) -> Optional[str]:
        """Предложить альтернативную стратегию"""
        alternatives = {
            "react": ["planning", "evaluation"],
            "planning": ["react", "evaluation"],
            "evaluation": ["react", "planning"],
            "fallback": ["react"]
        }
        return alternatives.get(current_strategy, [])[0] if alternatives.get(current_strategy) else None
    
    def record_strategy_switch(self, decision: StrategySwitchDecision, from_strategy: str, context: Dict[str, Any] = None):
        """Запись переключения стратегии в историю"""
        record = StrategySwitchRecord(
            from_strategy=from_strategy,
            to_strategy=decision.to_strategy,
            reason=decision.reason,
            timestamp=datetime.now(),
            confidence=decision.confidence,
            context=context or {}
        )
        self.strategy_history.append(record)
        self.logger.info(f"Переключение стратегии: {from_strategy} → {decision.to_strategy}, причина: {decision.reason}")


class ProgressMetrics:
    """Класс для отслеживания метрик прогресса"""
    
    def __init__(self):
        self.step: int = 0
        self.error_count: int = 0
        self.consecutive_errors: int = 0
        self.no_progress_steps: int = 0
        
        # НОВЫЕ метрики для стратегического управления
        self.strategy_switches: int = 0
        self.plan_corrections: int = 0
        self.strategy_effectiveness: Dict[str, float] = {}  # {strategy_name: success_rate}
        self.last_strategy_switch_step: Optional[int] = None
        self.strategy_confidence: float = 1.0  # Уверенность в текущей стратегии
    
    def update_strategy_effectiveness(self, strategy_name: str, success: bool):
        """Обновление метрик эффективности стратегии"""
        if strategy_name not in self.strategy_effectiveness:
            self.strategy_effectiveness[strategy_name] = 0.5
        
        # Экспоненциальное сглаживание
        alpha = 0.3
        current = self.strategy_effectiveness[strategy_name]
        self.strategy_effectiveness[strategy_name] = (
            alpha * (1.0 if success else 0.0) + (1 - alpha) * current
        )
    
    def get_state_metrics(self) -> Dict[str, Any]:
        """Получить словарь с текущими метриками состояния"""
        return {
            "step": self.step,
            "error_count": self.error_count,
            "consecutive_errors": self.consecutive_errors,
            "no_progress_steps": self.no_progress_steps,
            "strategy_switches": self.strategy_switches,
            "plan_corrections": self.plan_corrections,
            "strategy_effectiveness": self.strategy_effectiveness.copy(),
            "last_strategy_switch_step": self.last_strategy_switch_step,
            "strategy_confidence": self.strategy_confidence
        }