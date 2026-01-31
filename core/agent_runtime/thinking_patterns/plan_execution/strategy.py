"""
PlanExecutionStrategy — паттерн мышления для выполнения существующего плана шаг за шагом.
ОСОБЕННОСТИ:
- ЕДИНСТВЕННАЯ ответственность: выполнение плана без его модификации
- Читает план из контекста сессии (session.plan)
- Выполняет шаги последовательно через соответствующие навыки
- При ошибке переключается на корректировку плана или откат
"""
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from core.agent_runtime.interfaces import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface
from core.session_context.model import ContextItemMetadata
from models.execution import ExecutionStatus

logger = logging.getLogger(__name__)


class PlanExecutionThinkingPattern(AgentThinkingPatternInterface):
    """
    Паттерн мышления выполнения плана действий.
    
    ЖИЗНЕННЫЙ ЦИКЛ:
    1. Чтение плана из контекста сессии
    2. Выполнение текущего шага плана через соответствующий навык
    3. Обновление состояния плана (текущий шаг)
    4. Проверка завершения плана → переключение на оценку или завершение
    
    ПРИМЕР:
    План: [
      {"step": 1, "action": "navigate", "parameters": {...}},
      {"step": 2, "action": "analyze", "parameters": {...}},
      {"step": 3, "action": "fix", "parameters": {...}}
    ]
    
    Шаг 1: Выполнение действия "navigate" через ProjectNavigatorSkill
    Шаг 2: Обновление session.plan.current_step = 1
    Шаг 3: Проверка: текущий шаг < общее количество шагов → продолжение
    Шаг 4: При завершении всех шагов → переключение на evaluation
    """
    name = "plan_execution"
    
    def __init__(self):
        self._step_timeout = 60.0
        self._max_retries_per_step = 3
    
    async def next_step(self, runtime: AgentRuntimeInterface) -> StrategyDecision:
        """
        Основной метод — выполнение текущего шага плана.
        ВОЗВРАЩАЕТ: 
          - CONTINUE для следующего шага плана
          - SWITCH на evaluation при завершении плана
          - SWITCH на fallback при критической ошибке
        """
        session = runtime.session()
        current_step_num = session.step_context.get_current_step_number()
        
        # Получение плана из контекста
        plan = self._get_plan_from_session(session)
        if not plan:
            error_msg = "План не найден в контексте сессии для выполнения"
            logger.error(error_msg)
            return self._handle_missing_plan(runtime, session, error_msg)
        
        # Проверка завершения плана
        if self._is_plan_completed(plan):
            logger.info("План успешно выполнен, переключение на оценку результата")
            return await self._finalize_plan_execution(runtime, session, plan)
        
        # Выполнение текущего шага
        current_step_index = plan.get("current_step", 0)
        current_step_data = self._get_current_step(plan, current_step_index)
        
        if not current_step_data:
            error_msg = f"Шаг {current_step_index} не найден в плане"
            logger.error(error_msg)
            return self._handle_step_error(runtime, session, plan, current_step_index, error_msg)
        
        # Запись шага выполнения
        session.step_context.record_step(
            step_number=current_step_num + 1,
            capability_name=current_step_data.get("capability", "unknown"),
            skill_name=current_step_data.get("skill", "unknown"),
            status=ExecutionStatus.RUNNING,
            summary=f"Выполнение шага {current_step_index + 1}: {current_step_data.get('description', 'без описания')}",
            observation_item_ids=[]
        )
        
        # Выполнение шага через соответствующий навык
        execution_result = await self._execute_plan_step(
            runtime=runtime,
            session=session,
            step_data=current_step_data,
            step_number=current_step_num + 1
        )
        
        # Обработка результата выполнения
        if execution_result.get("success"):
            # Успешное выполнение — переход к следующему шагу
            plan["current_step"] = current_step_index + 1
            session.plan = plan  # Обновление плана в контексте
            
            # Запись успешного выполнения
            observation_id = session.record_observation(
                {
                    "action": "plan_step_completed",
                    "step_index": current_step_index,
                    "step_data": current_step_data,
                    "result": execution_result.get("result_summary"),
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=current_step_num + 1,
                metadata=ContextItemMetadata(
                    source="plan_execution_success",
                    confidence=1.0,
                    step_number=current_step_num + 1
                )
            )
            
            session.step_context.update_step_status(
                step_number=current_step_num + 1,
                status=ExecutionStatus.SUCCESS,
                summary=execution_result.get("result_summary", "Шаг плана выполнен"),
                observation_item_ids=[observation_id]
            )
            
            # Проверка завершения плана после обновления
            if self._is_plan_completed(plan):
                return await self._finalize_plan_execution(runtime, session, plan)
            
            # Продолжение выполнения плана
            return StrategyDecision(
                action=StrategyDecisionType.CONTINUE,
                next_strategy=None,
                reason=f"step_{current_step_index}_completed_proceed_to_next"
            )
        
        else:
            # Неудачное выполнение — обработка ошибки
            return await self._handle_step_failure(
                runtime=runtime,
                session=session,
                plan=plan,
                step_index=current_step_index,
                error_message=execution_result.get("error", "Неизвестная ошибка"),
                retry_count=execution_result.get("retry_count", 0)
            )
    
    def _get_plan_from_session(self, session: Any) -> Optional[Dict[str, Any]]:
        """Получение плана из контекста сессии."""
        # Приоритет 1: атрибут сессии
        if hasattr(session, 'plan') and session.plan:
            return session.plan
        
        # Приоритет 2: поиск в последних наблюдениях
        last_observations = session.data_context.get_last_items(10)
        for obs in last_observations:
            if obs.item_type.name == "OBSERVATION":
                content = obs.content
                if isinstance(content, dict) and content.get("plan_type") == "action_plan":
                    plan_data = content.get("plan_data")
                    if plan_data and isinstance(plan_data, dict):
                        return {
                            "steps": plan_data.get("steps", []),
                            "current_step": 0,
                            "total_steps": len(plan_data.get("steps", [])),
                            "goal": content.get("goal", ""),
                            "created_at": content.get("created_at", datetime.utcnow().isoformat()),
                            "source": "observation"
                        }
        
        return None
    
    def _is_plan_completed(self, plan: Dict[str, Any]) -> bool:
        """Проверка завершения плана."""
        current_step = plan.get("current_step", 0)
        total_steps = plan.get("total_steps", 0)
        return current_step >= total_steps
    
    def _get_current_step(self, plan: Dict[str, Any], step_index: int) -> Optional[Dict[str, Any]]:
        """Получение данных текущего шага плана."""
        steps = plan.get("steps", [])
        if 0 <= step_index < len(steps):
            step = steps[step_index]
            # Нормализация структуры шага (поддержка разных форматов)
            if isinstance(step, dict):
                return step
            elif isinstance(step, str):
                # Попытка парсинга JSON из строки
                try:
                    return json.loads(step)
                except json.JSONDecodeError:
                    return {"description": step, "raw": step}
        return None
    
    async def _execute_plan_step(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        step_data: Dict[str, Any],
        step_number: int
    ) -> Dict[str, Any]:
        """
        Выполнение одного шага плана через соответствующий навык.
        ВОЗВРАЩАЕТ: {
            "success": bool,
            "result": Any,
            "result_summary": str,
            "error": Optional[str],
            "skill_name": str,
            "capability_name": str,
            "retry_count": int
        }
        """
        try:
            # Извлечение параметров шага
            skill_name = step_data.get("skill") or step_data.get("target_skill")
            capability_name = step_data.get("capability") or step_data.get("action")
            parameters = step_data.get("parameters", {})
            description = step_data.get("description", "Шаг плана")
            
            if not skill_name or not capability_name:
                return {
                    "success": False,
                    "error": f"Недостаточно данных для выполнения шага: skill={skill_name}, capability={capability_name}",
                    "retry_count": 0
                }
            
            # Получение навыка
            skill = runtime.system.get_resource(skill_name)
            if not skill:
                return {
                    "success": False,
                    "error": f"Навык '{skill_name}' не найден в системном контексте",
                    "retry_count": 0
                }
            
            # Получение capability
            capability = runtime.system.get_capability(capability_name)
            if not capability:
                # Попытка найти capability по шаблону (для обратной совместимости)
                all_caps = runtime.system.list_capabilities()
                matching_caps = [c for c in all_caps if capability_name in c]
                if matching_caps:
                    capability = runtime.system.get_capability(matching_caps[0])
                
                if not capability:
                    return {
                        "success": False,
                        "error": f"Capability '{capability_name}' не найдена",
                        "retry_count": 0
                    }
            
            # Выполнение шага
            result = await skill.execute(capability, parameters, session)
            
            return {
                "success": result.status == ExecutionStatus.SUCCESS,
                "result": result.result,
                "result_summary": result.summary or description,
                "error": result.error,
                "skill_name": skill_name,
                "capability_name": capability_name,
                "retry_count": 0
            }
            
        except Exception as e:
            error_msg = f"Ошибка выполнения шага плана: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "retry_count": 0
            }
    
    async def _handle_step_failure(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        plan: Dict[str, Any],
        step_index: int,
        error_message: str,
        retry_count: int
    ) -> StrategyDecision:
        """Обработка неудачного выполнения шага плана."""
        # Запись ошибки
        observation_id = session.record_observation(
            {
                "action": "plan_step_failed",
                "step_index": step_index,
                "error": error_message,
                "retry_count": retry_count,
                "timestamp": datetime.utcnow().isoformat()
            },
            source=self.name,
            step_number=session.step_context.get_current_step_number() + 1,
            metadata=ContextItemMetadata(
                source="plan_execution_error",
                confidence=0.0,
                step_number=session.step_context.get_current_step_number() + 1
            )
        )
        
        session.step_context.update_step_status(
            step_number=session.step_context.get_current_step_number() + 1,
            status=ExecutionStatus.FAILED,
            summary=f"Ошибка выполнения шага {step_index + 1}: {error_message[:100]}",
            observation_item_ids=[observation_id]
        )
        
        # Проверка лимита повторных попыток
        if retry_count >= self._max_retries_per_step:
            logger.warning(
                f"Достигнут лимит повторных попыток ({self._max_retries_per_step}) "
                f"для шага {step_index + 1}, требуется корректировка плана"
            )
            # Переключение на планирование для корректировки
            return StrategyDecision(
                action=StrategyDecisionType.SWITCH,
                next_strategy="planning",
                reason=f"step_{step_index}_failed_max_retries",
                payload={"failed_step_index": step_index, "error": error_message}
            )
        
        # Повторная попытка выполнения шага
        logger.info(f"Повторная попытка выполнения шага {step_index + 1} (попытка {retry_count + 1})")
        return StrategyDecision(
            action=StrategyDecisionType.CONTINUE,
            next_strategy=None,
            reason=f"step_{step_index}_retry_{retry_count + 1}",
            payload={"retry_count": retry_count + 1}
        )
    
    async def _finalize_plan_execution(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        plan: Dict[str, Any]
    ) -> StrategyDecision:
        """Финализация выполнения плана."""
        # Запись завершения плана
        observation_id = session.record_observation(
            {
                "action": "plan_completed",
                "plan_goal": plan.get("goal", ""),
                "total_steps": plan.get("total_steps", 0),
                "completed_at": datetime.utcnow().isoformat(),
                "timestamp": datetime.utcnow().isoformat()
            },
            source=self.name,
            step_number=session.step_context.get_current_step_number() + 1,
            metadata=ContextItemMetadata(
                source="plan_execution_complete",
                confidence=1.0,
                step_number=session.step_context.get_current_step_number() + 1
            )
        )
        
        session.step_context.record_step(
            step_number=session.step_context.get_current_step_number() + 1,
            capability_name="plan_execution.finalize",
            skill_name=self.name,
            status=ExecutionStatus.SUCCESS,
            summary=f"План завершен: {plan.get('total_steps', 0)} шагов выполнено",
            observation_item_ids=[observation_id]
        )
        
        logger.info(f"План завершен успешно, всего шагов: {plan.get('total_steps', 0)}")
        
        # Переключение на оценку результата
        return StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy="evaluation",
            reason="plan_execution_completed",
            payload={"plan_observation_id": observation_id}
        )
    
    def _handle_missing_plan(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        error_message: str
    ) -> StrategyDecision:
        """Обработка отсутствия плана в контексте."""
        # Запись ошибки
        session.record_observation(
            {
                "action": "missing_plan_error",
                "error": error_message,
                "timestamp": datetime.utcnow().isoformat()
            },
            source=self.name,
            step_number=session.step_context.get_current_step_number() + 1,
            metadata=ContextItemMetadata(
                source="plan_execution_error",
                confidence=0.0,
                step_number=session.step_context.get_current_step_number() + 1
            )
        )
        
        # Переключение на планирование для создания нового плана
        return StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy="planning",
            reason="plan_missing_create_new"
        )