from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class AgentState:
    """
    Явное состояние агента.
    Не содержит логики — только данные.
    """

    step: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    no_progress_steps: int = 0
    finished: bool = False

    history: List[str] = field(default_factory=list)
    
    # НОВЫЕ метрики для стратегического управления
    strategy_switches: int = 0
    plan_corrections: int = 0
    strategy_effectiveness: Dict[str, float] = field(default_factory=dict)  # {strategy_name: success_rate}
    last_strategy_switch_step: int = 0
    strategy_confidence: float = 1.0  # Уверенность в текущей стратегии

    def register_error(self):
        self.error_count += 1
        self.consecutive_errors += 1

    def reset_consecutive_errors(self):
        """Сброс счетчика последовательных ошибок"""
        self.consecutive_errors = 0

    def register_progress(self, progressed: bool):
        if progressed:
            self.no_progress_steps = 0
        else:
            self.no_progress_steps += 1

    def increment_strategy_switches(self):
        """Увеличение счетчика переключений стратегии"""
        self.strategy_switches += 1
        self.last_strategy_switch_step = self.step

    def increment_plan_corrections(self):
        """Увеличение счетчика коррекций плана"""
        self.plan_corrections += 1

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
        
        # Обновление уверенности в текущей стратегии
        self.strategy_confidence = self.strategy_effectiveness.get(strategy_name, 0.5)
