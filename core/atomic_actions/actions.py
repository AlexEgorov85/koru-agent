"""
Реализация атомарных действий для архитектуры агента.
"""

import logging
from typing import Any, Dict, Optional
from core.atomic_actions.base import AtomicAction, AtomicActionType
from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType


logger = logging.getLogger(__name__)


class THINK(AtomicAction):
    """Атомарное действие размышления - выполняет рассуждение и анализ."""
    
    def __init__(self):
        super().__init__(
            name="think",
            description="Выполняет рассуждение и анализ для понимания текущей ситуации и определения следующих шагов"
        )
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет действие размышления.
        
        ПАРАМЕТРЫ:
            runtime: Интерфейс выполнения агента
            context: Контекст выполнения
            parameters: Необязательные параметры, включая цель, наблюдения и текущее состояние
            
        ВОЗВРАЩАЕТ:
            StrategyDecision с рассуждением и следующим действием
        """
        session = context if hasattr(context, 'get_goal') else runtime.session
        goal = session.get_goal() or ""
        parameters = parameters or {}
        
        # Gather context for reasoning
        context_summary = self._gather_context_for_reasoning(session, parameters)
        
        # Perform reasoning using LLM
        reasoning_result = await self._perform_reasoning(runtime, goal, context_summary, parameters)
        
        # Return decision based on reasoning
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={
                "reasoning": reasoning_result,
                "next_action": parameters.get("next_action", "continue")
            }
        )
    
    def _gather_context_for_reasoning(self, session: Any, parameters: Dict[str, Any]) -> str:
        """Собирает актуальный контекст для рассуждения."""
        # Получаем недавние наблюдения
        last_items = session.data_context.get_last_items(10)
        observations = []
        for item in last_items:
            if item.item_type.name == "OBSERVATION":
                content = item.content
                if isinstance(content, dict):
                    if "result_summary" in content:
                        observations.append(f"- {content['result_summary'][:100]}")
                    elif "thought" in content:
                        thought = content["thought"]
                        if isinstance(thought, dict) and "reasoning" in thought:
                            observations.append(f"- Reasoning: {thought['reasoning'][:80]}")
        
        return "\n".join(observations[-5:]) if observations else "No prior context"
    
    async def _perform_reasoning(
        self,
        runtime: AgentRuntimeInterface,
        goal: str,
        context_summary: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Выполняет рассуждение с использованием LLM."""
        prompt = f"""
        You are an intelligent agent analyzing the current situation to achieve the goal: "{goal}".
        
        Current context:
        {context_summary}
        
        Please provide your reasoning about:
        1. Current situation assessment
        2. What needs to be done next
        3. Confidence level in your assessment (0.0 to 1.0)
        4. Recommended next action
        """
        
        try:
            response = await runtime.system.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="You are an analytical agent that provides clear reasoning about the current situation and next steps.",
                output_schema={
                    "type": "object",
                    "properties": {
                        "situation_assessment": {"type": "string"},
                        "next_steps": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "recommended_action": {"type": "string"}
                    },
                    "required": ["situation_assessment", "next_steps", "confidence", "recommended_action"]
                },
                output_format="json",
                temperature=0.3,
                max_tokens=500
            )
            
            return response.content if hasattr(response, 'content') else response
        except Exception as e:
            logger.error(f"Error during reasoning: {str(e)}")
            return {
                "situation_assessment": "Unable to assess situation due to error",
                "next_steps": "Continue with basic action",
                "confidence": 0.5,
                "recommended_action": "continue"
            }


class ACT(AtomicAction):
    """Атомарное действие действия - выполняет определенную возможность."""
    
    def __init__(self):
        super().__init__(
            name="act",
            description="Выполняет определенную возможность для взаимодействия с окружающей средой"
        )
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет действие выполнения.
        
        ПАРАМЕТРЫ:
            runtime: Интерфейс выполнения агента
            context: Контекст выполнения
            parameters: Параметры, включая название возможности и параметры выполнения
            
        ВОЗВРАЩАЕТ:
            StrategyDecision с результатом действия
        """
        parameters = parameters or {}
        capability_name = parameters.get("capability_name")
        action_parameters = parameters.get("parameters", {})
        
        if not capability_name:
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="missing_capability_name",
                payload={"error": "Capability name is required for ACT action"}
            )
        
        # Get capability
        capability = runtime.system.get_capability(capability_name)
        if not capability:
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="capability_not_found",
                payload={"error": f"Capability '{capability_name}' not found"}
            )
        
        # Get skill
        skill = runtime.system.get_resource(capability.skill_name)
        if not skill:
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="skill_not_found",
                payload={"error": f"Skill '{capability.skill_name}' not found for capability '{capability_name}'"}
            )
        
        # Execute capability
        try:
            result = await skill.execute(
                capability=capability,
                parameters=action_parameters,
                context=context
            )
            
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "capability_name": capability_name,
                    "result": result,
                    "status": result.status.value if hasattr(result.status, 'value') else str(result.status)
                }
            )
        except Exception as e:
            logger.error(f"Error executing capability '{capability_name}': {str(e)}")
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="execution_failed",
                payload={"error": str(e)}
            )


class OBSERVE(AtomicAction):
    """Атомарное действие наблюдения - собирает информацию из окружающей среды."""
    
    def __init__(self):
        super().__init__(
            name="observe",
            description="Собирает информацию из окружающей среды или внутреннего состояния"
        )
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет действие наблюдения.
        
        ПАРАМЕТРЫ:
            runtime: Интерфейс выполнения агента
            context: Контекст выполнения
            parameters: Необязательные параметры, определяющие, что наблюдать
            
        ВОЗВРАЩАЕТ:
            StrategyDecision с результатами наблюдения
        """
        session = context if hasattr(context, 'get_goal') else runtime.session
        parameters = parameters or {}
        
        # Get recent items from context
        count = parameters.get("count", 5)
        item_type_filter = parameters.get("item_type", None)
        
        last_items = session.data_context.get_last_items(count)
        
        # Filter by type if specified
        if item_type_filter:
            filtered_items = [
                item for item in last_items
                if item.item_type.name == item_type_filter
            ]
        else:
            filtered_items = last_items
        
        observations = []
        for item in filtered_items:
            observations.append({
                "id": item.item_id,
                "type": item.item_type.name,
                "content": item.content,
                "timestamp": item.created_at.isoformat() if hasattr(item.created_at, 'isoformat') else str(item.created_at)
            })
        
        return StrategyDecision(
            action=StrategyDecisionType.ACT,
            payload={
                "observations": observations,
                "count": len(observations)
            }
        )


class PLAN(AtomicAction):
    """Атомарное действие планирования - создает или обновляет план."""
    
    def __init__(self):
        super().__init__(
            name="plan",
            description="Создает или обновляет план действий для достижения цели"
        )
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет действие планирования.
        
        ПАРАМЕТРЫ:
            runtime: Интерфейс выполнения агента
            context: Контекст выполнения
            parameters: Параметры, включая цель и ограничения для планирования
            
        ВОЗВРАЩАЕТ:
            StrategyDecision с планом
        """
        session = context if hasattr(context, 'get_goal') else runtime.session
        goal = session.get_goal() or ""
        parameters = parameters or {}
        
        # Get planning skill
        planning_skill = runtime.system.get_resource("planning")
        if not planning_skill:
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="planning_skill_not_found",
                payload={"error": "Planning skill not available"}
            )
        
        # Get planning capability
        planning_capability = runtime.system.get_capability("planning.create_plan")
        if not planning_capability:
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="planning_capability_not_found",
                payload={"error": "Planning capability not available"}
            )
        
        # Prepare planning parameters
        plan_params = {
            "goal": goal,
            "max_steps": parameters.get("max_steps", 10),
            "context": parameters.get("context", {})
        }
        
        # Execute planning
        try:
            result = await planning_skill.execute(
                capability=planning_capability,
                parameters=plan_params,
                context=session
            )
            
            # Store plan in session
            if result.status.name == "SUCCESS":  # Assuming SUCCESS is the status name
                plan_data = result.result if result.result else {}
                session.plan = {
                    "steps": plan_data.get("steps", []),
                    "current_step": 0,
                    "total_steps": len(plan_data.get("steps", [])),
                    "goal": goal,
                    "source": "atomic_plan"
                }
                
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "plan": session.plan if hasattr(session, 'plan') else plan_data,
                    "result": result
                }
            )
        except Exception as e:
            logger.error(f"Error during planning: {str(e)}")
            return StrategyDecision(
                action=StrategyDecisionType.RETRY,
                reason="planning_failed",
                payload={"error": str(e)}
            )


class REFLECT(AtomicAction):
    """Атомарное действие рефлексии - анализирует прошлые действия и результаты."""
    
    def __init__(self):
        super().__init__(
            name="reflect",
            description="Анализирует прошлые действия и результаты для улучшения будущей производительности"
        )
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет действие рефлексии.
        
        ПАРАМЕТРЫ:
            runtime: Интерфейс выполнения агента
            context: Контекст выполнения
            parameters: Необязательные параметры для рефлексии
            
        ВОЗВРАЩАЕТ:
            StrategyDecision с инсайтами рефлексии
        """
        session = context if hasattr(context, 'get_goal') else runtime.session
        parameters = parameters or {}
        
        # Get recent steps and observations
        recent_steps = session.step_context.steps[-5:] if hasattr(session.step_context, 'steps') else []
        recent_observations = session.data_context.get_last_items(10)
        
        # Prepare reflection prompt
        reflection_prompt = f"""
        Please analyze the recent actions and outcomes to identify patterns, successes, and areas for improvement.
        
        Recent steps:
        {len(recent_steps)} steps completed
        
        Recent observations:
        {[{'type': item.item_type.name, 'summary': str(item.content)[:100]} for item in recent_observations]}
        
        Provide insights about:
        1. What has been working well
        2. What could be improved
        3. Any patterns noticed
        4. Recommendations for future actions
        """
        
        try:
            response = await runtime.system.call_llm_with_params(
                user_prompt=reflection_prompt,
                system_prompt="You are a reflective agent that analyzes past performance to improve future actions.",
                output_schema={
                    "type": "object",
                    "properties": {
                        "working_well": {"type": "array", "items": {"type": "string"}},
                        "improvements": {"type": "array", "items": {"type": "string"}},
                        "patterns": {"type": "array", "items": {"type": "string"}},
                        "recommendations": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["working_well", "improvements", "patterns", "recommendations"]
                },
                output_format="json",
                temperature=0.5,
                max_tokens=600
            )
            
            reflection_result = response.content if hasattr(response, 'content') else response
            
            # Record reflection in context
            session.record_observation(
                {
                    "action": "reflection",
                    "insights": reflection_result,
                    "timestamp": "datetime.utcnow().isoformat()"  # Note: This is a placeholder - needs proper import
                },
                source="reflection",
                step_number=session.step_context.get_current_step_number()
            )
            
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "reflection": reflection_result
                }
            )
        except Exception as e:
            logger.error(f"Error during reflection: {str(e)}")
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "reflection": {
                        "working_well": [],
                        "improvements": ["Need to improve error handling"],
                        "patterns": [],
                        "recommendations": ["Implement better error handling"]
                    }
                }
            )


class EVALUATE(AtomicAction):
    """Атомарное действие оценки - оценивает прогресс в направлении цели."""
    
    def __init__(self):
        super().__init__(
            name="evaluate",
            description="Оценивает прогресс в направлении цели и определяет, достигнуты ли цели"
        )
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет действие оценки.
        
        ПАРАМЕТРЫ:
            runtime: Интерфейс выполнения агента
            context: Контекст выполнения
            parameters: Необязательные параметры для оценки
            
        ВОЗВРАЩАЕТ:
            StrategyDecision с результатами оценки
        """
        session = context if hasattr(context, 'get_goal') else runtime.session
        goal = session.get_goal() or ""
        parameters = parameters or {}
        
        # Get recent observations and results
        recent_items = session.data_context.get_last_items(15)
        
        # Prepare evaluation prompt
        evaluation_prompt = f"""
        Evaluate the progress toward achieving the goal: "{goal}"
        
        Recent activity:
        {[{'type': item.item_type.name, 'summary': str(item.content)[:100]} for item in recent_items]}
        
        Please assess:
        1. Progress made toward the goal (0.0 to 1.0)
        2. Confidence in current approach
        3. Whether the goal has been achieved
        4. What remains to be done
        5. Recommendation: continue, modify approach, or conclude
        """
        
        try:
            response = await runtime.system.call_llm_with_params(
                user_prompt=evaluation_prompt,
                system_prompt="You are an evaluative agent that assesses progress toward goals and provides recommendations.",
                output_schema={
                    "type": "object",
                    "properties": {
                        "progress_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "goal_achieved": {"type": "boolean"},
                        "remaining_tasks": {"type": "array", "items": {"type": "string"}},
                        "recommendation": {"type": "string", "enum": ["continue", "modify", "conclude"]}
                    },
                    "required": ["progress_score", "confidence", "goal_achieved", "remaining_tasks", "recommendation"]
                },
                output_format="json",
                temperature=0.2,
                max_tokens=500
            )
            
            evaluation_result = response.content if hasattr(response, 'content') else response
            
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "evaluation": evaluation_result
                }
            )
        except Exception as e:
            logger.error(f"Error during evaluation: {str(e)}")
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "evaluation": {
                        "progress_score": 0.5,
                        "confidence": 0.5,
                        "goal_achieved": False,
                        "remaining_tasks": ["Error occurred during evaluation"],
                        "recommendation": "continue"
                    }
                }
            )


class VERIFY(AtomicAction):
    """Атомарное действие проверки - проверяет правильность результатов или предположений."""
    
    def __init__(self):
        super().__init__(
            name="verify",
            description="Проверяет правильность результатов, подтверждает предположения или утверждает результаты"
        )
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет действие проверки.
        
        ПАРАМЕТРЫ:
            runtime: Интерфейс выполнения агента
            context: Контекст выполнения
            parameters: Параметры, определяющие, что проверить
            
        ВОЗВРАЩАЕТ:
            StrategyDecision с результатами проверки
        """
        parameters = parameters or {}
        
        # Get item to verify
        item_to_verify = parameters.get("item")
        criteria = parameters.get("criteria", "correctness")
        
        if not item_to_verify:
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "verification": {
                        "verified": False,
                        "error": "No item provided for verification"
                    }
                }
            )
        
        # Prepare verification prompt
        verification_prompt = f"""
        Verify the following item according to {criteria} criteria:
        
        Item: {item_to_verify}
        
        Please check:
        1. Is it correct/valid?
        2. Are there any issues or problems?
        3. What is your confidence in the verification?
        """
        
        try:
            response = await runtime.system.call_llm_with_params(
                user_prompt=verification_prompt,
                system_prompt="You are a verification agent that checks correctness and validity of items.",
                output_schema={
                    "type": "object",
                    "properties": {
                        "verified": {"type": "boolean"},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "details": {"type": "string"}
                    },
                    "required": ["verified", "confidence"]
                },
                output_format="json",
                temperature=0.1,
                max_tokens=400
            )
            
            verification_result = response.content if hasattr(response, 'content') else response
            
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "verification": verification_result
                }
            )
        except Exception as e:
            logger.error(f"Error during verification: {str(e)}")
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "verification": {
                        "verified": False,
                        "issues": [f"Verification failed due to error: {str(e)}"],
                        "confidence": 0.0,
                        "details": "Error occurred during verification process"
                    }
                }
            )


class ADAPT(AtomicAction):
    """Атомарное действие адаптации - корректирует стратегию на основе контекста или обратной связи."""
    
    def __init__(self):
        super().__init__(
            name="adapt",
            description="Корректирует стратегию, поведение или подход на основе контекста или обратной связи"
        )
    
    async def execute(
        self,
        runtime: AgentRuntimeInterface,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет действие адаптации.
        
        ПАРАМЕТРЫ:
            runtime: Интерфейс выполнения агента
            context: Контекст выполнения
            parameters: Параметры, определяющие требования к адаптации
            
        ВОЗВРАЩАЕТ:
            StrategyDecision с планом адаптации
        """
        session = context if hasattr(context, 'get_goal') else runtime.session
        goal = session.get_goal() or ""
        parameters = parameters or {}
        
        # Get current context and challenges
        current_strategy = parameters.get("current_strategy", "unknown")
        challenges = parameters.get("challenges", [])
        feedback = parameters.get("feedback", "")
        
        # Prepare adaptation prompt
        adaptation_prompt = f"""
        The agent needs to adapt its approach for goal: "{goal}"
        
        Current strategy: {current_strategy}
        Challenges encountered: {challenges}
        Feedback received: {feedback}
        
        Please provide:
        1. Analysis of why current approach isn't working
        2. Alternative strategies to try
        3. Specific adaptations to make
        4. Expected benefits of adaptations
        """
        
        try:
            response = await runtime.system.call_llm_with_params(
                user_prompt=adaptation_prompt,
                system_prompt="You are an adaptive agent that modifies strategies based on context and feedback.",
                output_schema={
                    "type": "object",
                    "properties": {
                        "analysis": {"type": "string"},
                        "alternative_strategies": {"type": "array", "items": {"type": "string"}},
                        "specific_adaptations": {"type": "array", "items": {"type": "string"}},
                        "expected_benefits": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["analysis", "alternative_strategies", "specific_adaptations", "expected_benefits"]
                },
                output_format="json",
                temperature=0.4,
                max_tokens=600
            )
            
            adaptation_result = response.content if hasattr(response, 'content') else response
            
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "adaptation": adaptation_result
                }
            )
        except Exception as e:
            logger.error(f"Error during adaptation: {str(e)}")
            return StrategyDecision(
                action=StrategyDecisionType.ACT,
                payload={
                    "adaptation": {
                        "analysis": "Unable to analyze due to error",
                        "alternative_strategies": ["Fallback to default strategy"],
                        "specific_adaptations": ["Reduce complexity", "Increase verification steps"],
                        "expected_benefits": ["Improved reliability"]
                    }
                }
            )