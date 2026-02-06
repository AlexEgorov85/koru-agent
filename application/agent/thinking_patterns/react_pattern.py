"""
Паттерн мышления ReAct (Reasoning + Acting).
"""
from typing import List, Dict, Any
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState


class ReActThinkingPattern(IThinkingPattern):
    """Паттерн мышления ReAct (Reasoning + Acting) — ЧИСТАЯ ЛОГИКА РЕШЕНИЙ."""
    
    @property
    def name(self) -> str:
        return "react"
    
    def __init__(self, llm_provider: Any = None, prompt_renderer: Any = None, prompt_repository: Any = None):
        from application.services.prompt_renderer import PromptRenderer
        self.llm_provider = llm_provider
        if prompt_renderer is None and prompt_repository is not None:
            # Если рендерер не передан, но есть репозиторий, создаем рендерер
            self.prompt_renderer = PromptRenderer(prompt_repository=prompt_repository)
        else:
            self.prompt_renderer = prompt_renderer
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить паттерн мышления."""
        # В реальной реализации здесь будет вызов LLM для принятия решения
        # Пока возвращаем заглушку
        
        # Для простоты возвращаем действие по умолчанию
        return {
            "action": "ACT",
            "capability": "basic_action",
            "parameters": {"message": "Выполняю действие"},
            "thought": "Анализирую текущую ситуацию и выбираю следующий шаг"
        }
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче (выбор домена, настройка параметров)."""
        return {
            "domain": "general",
            "confidence": 0.8,
            "parameters": {}
        }


class PlanningThinkingPattern(IThinkingPattern):
    """Паттерн мышления планирования."""
    
    @property
    def name(self) -> str:
        return "planning"
    
    def __init__(self, llm_provider: Any = None, prompt_renderer: Any = None, prompt_repository: Any = None):
        from application.services.prompt_renderer import PromptRenderer
        self.llm_provider = llm_provider
        if prompt_renderer is None and prompt_repository is not None:
            # Если рендерер не передан, но есть репозиторий, создаем рендерер
            self.prompt_renderer = PromptRenderer(prompt_repository=prompt_repository)
        else:
            self.prompt_renderer = prompt_renderer
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить паттерн мышления планирования."""
        return {
            "action": "THINK",
            "thought": "Создаю план выполнения задачи",
            "plan": ["шаг 1", "шаг 2", "шаг 3"]
        }
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче планирования."""
        return {
            "domain": "planning",
            "confidence": 0.9,
            "parameters": {}
        }


class PlanExecutionThinkingPattern(IThinkingPattern):
    """Паттерн мышления выполнения плана."""
    
    @property
    def name(self) -> str:
        return "plan_execution"
    
    def __init__(self, llm_provider: Any = None, prompt_renderer: Any = None, prompt_repository: Any = None):
        from application.services.prompt_renderer import PromptRenderer
        self.llm_provider = llm_provider
        if prompt_renderer is None and prompt_repository is not None:
            # Если рендерер не передан, но есть репозиторий, создаем рендерер
            self.prompt_renderer = PromptRenderer(prompt_repository=prompt_repository)
        else:
            self.prompt_renderer = prompt_renderer
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить паттерн мышления выполнения плана."""
        return {
            "action": "ACT",
            "capability": "execute_plan_step",
            "parameters": {"step_index": state.step},
            "thought": "Выполняю следующий шаг плана"
        }
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче выполнения плана."""
        return {
            "domain": "execution",
            "confidence": 0.85,
            "parameters": {}
        }


class CodeAnalysisThinkingPattern(IThinkingPattern):
    """Паттерн мышления анализа кода."""
    
    @property
    def name(self) -> str:
        return "code_analysis"
    
    def __init__(self, llm_provider: Any = None, prompt_renderer: Any = None, prompt_repository: Any = None):
        from application.services.prompt_renderer import PromptRenderer
        self.llm_provider = llm_provider
        if prompt_renderer is None and prompt_repository is not None:
            # Если рендерер не передан, но есть репозиторий, создаем рендерер
            self.prompt_renderer = PromptRenderer(prompt_repository=prompt_repository)
        else:
            self.prompt_renderer = prompt_renderer
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить паттерн мышления анализа кода."""
        return {
            "action": "ANALYZE_CODE",
            "capability": "code_analyzer",
            "parameters": {"target": "current_file"},
            "thought": "Анализирую структуру и логику кода"
        }
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче анализа кода."""
        return {
            "domain": "code_analysis",
            "confidence": 0.95,
            "parameters": {}
        }


class EvaluationThinkingPattern(IThinkingPattern):
    """Паттерн мышления оценки."""
    
    @property
    def name(self) -> str:
        return "evaluation"
    
    def __init__(self, llm_provider: Any = None, prompt_renderer: Any = None, prompt_repository: Any = None):
        from application.services.prompt_renderer import PromptRenderer
        self.llm_provider = llm_provider
        if prompt_renderer is None and prompt_repository is not None:
            # Если рендерер не передан, но есть репозиторий, создаем рендерер
            self.prompt_renderer = PromptRenderer(prompt_repository=prompt_repository)
        else:
            self.prompt_renderer = prompt_renderer
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить паттерн мышления оценки."""
        return {
            "action": "EVALUATE",
            "thought": "Оцениваю прогресс и эффективность текущего подхода",
            "progress": state.step / 10.0  # Пример оценки прогресса
        }
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче оценки."""
        return {
            "domain": "evaluation",
            "confidence": 0.7,
            "parameters": {}
        }


class FallbackThinkingPattern(IThinkingPattern):
    """Резервный паттерн мышления."""
    
    @property
    def name(self) -> str:
        return "fallback"
    
    def __init__(self, llm_provider: Any = None, prompt_renderer: Any = None, prompt_repository: Any = None):
        from application.services.prompt_renderer import PromptRenderer
        self.llm_provider = llm_provider
        if prompt_renderer is None and prompt_repository is not None:
            # Если рендерер не передан, но есть репозиторий, создаем рендерер
            self.prompt_renderer = PromptRenderer(prompt_repository=prompt_repository)
        else:
            self.prompt_renderer = prompt_renderer
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить резервный паттерн мышления."""
        return {
            "action": "THINK",
            "thought": "Использую резервный паттерн для продолжения работы",
            "suggestion": "Рекомендую перепроверить задачу или обратиться за помощью"
        }
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать резервный паттерн к задаче."""
        return {
            "domain": "general",
            "confidence": 0.5,
            "parameters": {}
        }