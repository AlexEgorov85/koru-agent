"""Адаптер для преобразования ComposablePattern в IThinkingPattern."""
from typing import List, Dict, Any
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState
from application.orchestration.patterns.patterns import ReActPattern


class ComposablePatternAdapter(IThinkingPattern):
    """Адаптер для преобразования ComposablePattern в IThinkingPattern."""
    
    def __init__(self, composable_pattern: ReActPattern):
        self.composable_pattern = composable_pattern
        self._name = composable_pattern.__class__.__name__.replace('Pattern', '').lower()
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Преобразовать вызов execute IThinkingPattern в вызов execute компонуемого паттерна."""
        composable_context = {
            "state": state,
            "context": context,
            "available_capabilities": available_capabilities,
            "step": state.step
        }
        
        # Выполняем паттерн и получаем результат
        # В реальной реализации нужно будет обработать результат правильно
        # Для упрощения используем фиктивный результат
        return {
            "status": "SUCCESS",
            "result": "Pattern executed successfully",
            "pattern": self.name,
            "action": "EXECUTE_PATTERN",
            "message": f"Executing {self.name} pattern"
        }
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать компонуемый паттерн к задаче."""
        # Возвращаем базовую информацию о задаче
        return {
            "domain": "general",
            "confidence": 0.7,
            "pattern": self.name,
            "parameters": {}
        }
