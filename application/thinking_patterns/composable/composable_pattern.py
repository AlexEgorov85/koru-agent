"""
Реализации компонуемых паттернов через атомарные действия.
"""
from typing import Any, Dict, List, Optional
from application.agent.composable_patterns.base import ComposablePattern
from domain.models.agent.agent_state import AgentState
from domain.models.provider_type import LLMResponse
from domain.models.react_state import ReActState


class ReActPattern(ComposablePattern):
    """Паттерн ReAct (Reasoning and Acting) - чередование рассуждения и действия через атомарные действия."""

    @property
    def name(self) -> str:
        return "react"

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.current_state = None  # Будет инициализировано при первом использовании
        self.self_assessment = None  # Результат саморефлексии
        self.current_iteration = 0  # Текущая итерация рефлексии

    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str],
        llm_response: Optional[LLMResponse] = None
    ):
        """Выполнить паттерн ReAct - ЧИСТАЯ ДОМЕННАЯ ЛОГИКА."""
        # ЧИСТАЯ ДОМЕННАЯ ЛОГИКА — НЕТ вызовов инфраструктуры!
        
        if llm_response is None:
            # Запросить рассуждение у оркестратора
            return {
                "requires_reasoning": True,
                "reason": "Требуется анализ текущей ситуации для принятия решения"
            }

        # Валидация через существующий механизм (НЕ создаем новый валидатор!)
        if llm_response.validation_error:
            return self._handle_validation_error(llm_response.validation_error)

        # Инициализируем состояние, если оно еще не создано
        if self.current_state is None:
            goal = getattr(context, 'goal', 'Неизвестная цель') if hasattr(context, 'goal') else 'Неизвестная цель'
            self.current_state = ReActState(goal=goal, steps=[])

        # Проверяем лимит итераций
        if len(self.current_state.steps) >= self.max_iterations:
            self.current_state.mark_completed("Достигнуто максимальное количество итераций")
            return {
                "action": "STOP",
                "thought": "Достигнуто максимальное количество итераций ReAct цикла",
                "result": "Задача не решена за отведенное количество итераций",
                "completed": True
            }

        # Доменная логика принятия решения
        parsed = llm_response.parsed or {}
        decision_type = parsed.get("decision_type", "THINK")
        
        if decision_type == "ACT" and "action" in parsed:
            return {
                "decision_type": decision_type,
                "action": parsed["action"],
                "parameters": parsed.get("parameters", {}),
                "requires_action": True
            }

        return {
            "decision_type": decision_type,
            "reasoning": parsed.get("reasoning", "Без рассуждений"),
            "requires_action": False
        }

    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче."""
        # Определяем домен задачи на основе описания
        task_lower = task_description.lower()

        if any(keyword in task_lower for keyword in ["code", "program", "python", "javascript", "java", "c++", "algorithm"]):
            domain = "code_analysis"
            confidence = 0.9
        elif any(keyword in task_lower for keyword in ["plan", "organize", "schedule", "manage"]):
            domain = "planning"
            confidence = 0.85
        elif any(keyword in task_lower for keyword in ["research", "find", "search", "information"]):
            domain = "research"
            confidence = 0.8
        elif any(keyword in task_lower for keyword in ["calculate", "math", "compute", "analyze data"]):
            domain = "data_analysis"
            confidence = 0.85
        else:
            domain = "general"
            confidence = 0.7

        return {
            "domain": domain,
            "confidence": confidence,
            "parameters": {
                "max_iterations": 10
            }
        }

    def _handle_validation_error(self, validation_error: str):
        """Обработка ошибки валидации."""
        return {
            "action": "ERROR",
            "thought": f"Ошибка валидации: {validation_error}",
            "error": validation_error,
            "status": "VALIDATION_FAILED"
        }


class PlanAndExecutePattern(ComposablePattern):
    """Паттерн PlanAndExecute - сначала планирование, затем выполнение через атомарные действия."""

    @property
    def name(self) -> str:
        return "plan_and_execute"

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.current_state = None  # Будет инициализировано при первом использовании
        self.self_assessment = None  # Результат саморефлексии
        self.current_iteration = 0  # Текущая итерация рефлексии

    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str],
        llm_response: Optional[LLMResponse] = None
    ):
        """Выполнить паттерн PlanAndExecute - ЧИСТАЯ ДОМЕННАЯ ЛОГИКА."""
        # ЧИСТАЯ ДОМЕННАЯ ЛОГИКА — НЕТ вызовов инфраструктуры!
        
        if llm_response is None:
            # Запросить рассуждение у оркестратора
            return {
                "requires_reasoning": True,
                "reason": "Требуется планирование для достижения цели"
            }

        # Валидация через существующий механизм (НЕ создаем новый валидатор!)
        if llm_response.validation_error:
            return self._handle_validation_error(llm_response.validation_error)

        # Инициализируем состояние, если оно еще не создано
        if self.current_state is None:
            goal = getattr(context, 'goal', 'Неизвестная цель') if hasattr(context, 'goal') else 'Неизвестная цель'
            self.current_state = ReActState(goal=goal, steps=[])

        # Проверяем лимит итераций
        if len(self.current_state.steps) >= self.max_iterations:
            self.current_state.mark_completed("Достигнуто максимальное количество итераций")
            return {
                "action": "STOP",
                "thought": "Достигнуто максимальное количество итераций PlanAndExecute цикла",
                "result": "Задача не решена за отведенное количество итераций",
                "completed": True
            }

        # Доменная логика принятия решения
        parsed = llm_response.parsed or {}
        decision_type = parsed.get("decision_type", "PLAN")
        
        if decision_type == "PLAN" and "plan" in parsed:
            # Если получен план, сохраняем его
            self.plan = parsed["plan"]
            return {
                "decision_type": decision_type,
                "plan": self.plan,
                "requires_action": False,
                "status": "PLANNING_COMPLETED"
            }
        elif decision_type == "EXECUTE" and hasattr(self, 'plan') and self.plan:
            # Выполняем следующий шаг плана
            current_step = self.plan[getattr(self, 'current_step_index', 0)]
            setattr(self, 'current_step_index', getattr(self, 'current_step_index', 0) + 1)
            
            return {
                "decision_type": decision_type,
                "executed_step": current_step,
                "remaining_steps": len(self.plan) - getattr(self, 'current_step_index', 0),
                "requires_action": False,
                "status": "EXECUTION_IN_PROGRESS"
            }
        else:
            # Если нет плана или нужно продолжить рассуждение
            return {
                "decision_type": decision_type,
                "reasoning": parsed.get("reasoning", "Без рассуждений"),
                "requires_action": False
            }

    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче."""
        return {
            "domain": "planning",
            "confidence": 0.8,
            "parameters": {
                "max_iterations": 10
            }
        }

    def _handle_validation_error(self, validation_error: str):
        """Обработка ошибки валидации."""
        return {
            "action": "ERROR",
            "thought": f"Ошибка валидации: {validation_error}",
            "error": validation_error,
            "status": "VALIDATION_FAILED"
        }


class ToolUsePattern(ComposablePattern):
    """Паттерн использования инструментов через атомарные действия."""

    @property
    def name(self) -> str:
        return "tool_use"

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.current_state = None  # Будет инициализировано при первом использовании
        self.self_assessment = None  # Результат саморефлексии
        self.current_iteration = 0  # Текущая итерация рефлексии

    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str],
        llm_response: Optional[LLMResponse] = None
    ):
        """Выполнить паттерн использования инструментов - ЧИСТАЯ ДОМЕННАЯ ЛОГИКА."""
        # ЧИСТАЯ ДОМЕННАЯ ЛОГИКА — НЕТ вызовов инфраструктуры!
        
        if llm_response is None:
            # Запросить рассуждение у оркестратора
            return {
                "requires_reasoning": True,
                "reason": "Требуется выбор инструмента для выполнения задачи"
            }

        # Валидация через существующий механизм (НЕ создаем новый валидатор!)
        if llm_response.validation_error:
            return self._handle_validation_error(llm_response.validation_error)

        # Инициализируем состояние, если оно еще не создано
        if self.current_state is None:
            goal = getattr(context, 'goal', 'Неизвестная цель') if hasattr(context, 'goal') else 'Неизвестная цель'
            self.current_state = ReActState(goal=goal, steps=[])

        # Проверяем лимит итераций
        if len(self.current_state.steps) >= self.max_iterations:
            self.current_state.mark_completed("Достигнуто максимальное количество итераций")
            return {
                "action": "STOP",
                "thought": "Достигнуто максимальное количество итераций ToolUse цикла",
                "result": "Задача не решена за отведенное количество итераций",
                "completed": True
            }

        # Доменная логика принятия решения
        parsed = llm_response.parsed or {}
        decision_type = parsed.get("decision_type", "SELECT_TOOL")
        
        if decision_type == "SELECT_TOOL" and "selected_tool" in parsed:
            selected_tool = parsed["selected_tool"]
            tool_parameters = parsed.get("parameters", {})
            
            # Проверяем, доступен ли выбранный инструмент
            if selected_tool and selected_tool in available_capabilities:
                return {
                    "decision_type": decision_type,
                    "selected_tool": selected_tool,
                    "tool_parameters": tool_parameters,
                    "requires_action": True
                }
            else:
                # Если выбранный инструмент недоступен, выбираем первый доступный
                if available_capabilities:
                    fallback_tool = available_capabilities[0]
                    return {
                        "decision_type": decision_type,
                        "selected_tool": fallback_tool,
                        "tool_parameters": {},
                        "requires_action": True
                    }
                else:
                    # Нет доступных инструментов
                    return {
                        "decision_type": decision_type,
                        "action": "NO_TOOLS_AVAILABLE",
                        "requires_action": False
                    }
        else:
            # Если нет результатов выбора инструмента или нужно продолжить рассуждение
            return {
                "decision_type": decision_type,
                "reasoning": parsed.get("reasoning", "Без рассуждений"),
                "requires_action": False
            }

    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче."""
        return {
            "domain": "tool_usage",
            "confidence": 0.85,
            "parameters": {
                "max_iterations": 10
            }
        }

    def _handle_validation_error(self, validation_error: str):
        """Обработка ошибки валидации."""
        return {
            "action": "ERROR",
            "thought": f"Ошибка валидации: {validation_error}",
            "error": validation_error,
            "status": "VALIDATION_FAILED"
        }


class ReflectionPattern(ComposablePattern):
    """Паттерн Reflection - выполнение с рефлексией и самоанализом через атомарные действия."""

    @property
    def name(self) -> str:
        return "reflection"

    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.current_state = None  # Будет инициализировано при первом использовании
        self.self_assessment = None  # Результат саморефлексии
        self.current_iteration = 0  # Текущая итерация рефлексии

    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str],
        llm_response: Optional[LLMResponse] = None
    ):
        """Выполнить паттерн Reflection - ЧИСТАЯ ДОМЕННАЯ ЛОГИКА."""
        # ЧИСТАЯ ДОМЕННАЯ ЛОГИКА — НЕТ вызовов инфраструктуры!
        
        if llm_response is None:
            # Запросить рассуждение у оркестратора
            return {
                "requires_reasoning": True,
                "reason": "Требуется анализ выполнения для саморефлексии"
            }

        # Валидация через существующий механизм (НЕ создаем новый валидатор!)
        if llm_response.validation_error:
            return self._handle_validation_error(llm_response.validation_error)

        # Инициализируем состояние, если оно еще не создано
        if self.current_state is None:
            goal = getattr(context, 'goal', 'Неизвестная цель') if hasattr(context, 'goal') else 'Неизвестная цель'
            self.current_state = ReActState(goal=goal, steps=[])

        # Проверяем лимит итераций
        if len(self.current_state.steps) >= self.max_iterations:
            self.current_state.mark_completed("Достигнуто максимальное количество итераций")
            return {
                "action": "STOP",
                "thought": "Достигнуто максимальное количество итераций Reflection цикла",
                "result": "Анализ завершен",
                "completed": True
            }

        # Доменная логика принятия решения
        parsed = llm_response.parsed or {}
        decision_type = parsed.get("decision_type", "ANALYZE")
        
        if decision_type == "ANALYZE" and "assessment" in parsed:
            # Сохраняем результат саморефлексии
            self.self_assessment = {
                "iteration": getattr(self, 'current_iteration', 0),
                "assessment": parsed["assessment"],
                "suggestions": parsed.get("suggestions", []),
                "effectiveness_score": parsed.get("effectiveness_score", 0.5)
            }

            return {
                "decision_type": decision_type,
                "assessment": parsed["assessment"],
                "suggestions": parsed.get("suggestions", []),
                "effectiveness_score": parsed.get("effectiveness_score", 0.5),
                "requires_action": False,
                "status": "REFLECTION_COMPLETED"
            }
        else:
            # Если нет результатов анализа или нужно продолжить рассуждение
            return {
                "decision_type": decision_type,
                "reasoning": parsed.get("reasoning", "Без рассуждений"),
                "requires_action": False
            }

    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче."""
        return {
            "domain": "reflection",
            "confidence": 0.9,
            "parameters": {
                "max_iterations": 5
            }
        }

    def _handle_validation_error(self, validation_error: str):
        """Обработка ошибки валидации."""
        return {
            "action": "ERROR",
            "thought": f"Ошибка валидации: {validation_error}",
            "error": validation_error,
            "status": "VALIDATION_FAILED"
        }