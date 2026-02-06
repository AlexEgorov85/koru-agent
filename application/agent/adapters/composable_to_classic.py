"""
Адаптер для преобразования ComposablePattern в IThinkingPattern.
"""
from typing import List, Dict, Any
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState
from application.agent.composable_patterns.base import ComposablePattern


class ComposablePatternAdapter(IThinkingPattern):
    """Адаптер для преобразования ComposablePattern в IThinkingPattern."""
    
    def __init__(self, composable_pattern: ComposablePattern):
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
        
        result = self.composable_pattern.execute(composable_context)
        
        # Преобразуем результат компонуемого паттерна в формат IThinkingPattern
        return {
            "status": result.get("status", "SUCCESS"),
            "result": result.get("result", "Pattern executed successfully"),
            "pattern": result.get("pattern", self.name),
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
