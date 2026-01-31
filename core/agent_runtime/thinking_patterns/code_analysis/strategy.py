"""
CodeAnalysisThinkingPattern — паттерн мышления для глубокого анализа кода с универсальным циклом.
АРХИТЕКТУРА:
1. ОБЯЗАТЕЛЬНЫЕ НАЧАЛЬНЫЕ ШАГИ:
   - Проверка наличия структуры проекта (ProjectMap)
   - Автоматическое построение карты при отсутствии
   - Инициализация состояния анализа в атрибутах сессии (НЕ через поиск в контексте)

2. УНИВЕРСАЛЬНЫЙ ЦИКЛ АНАЛИЗА:
   - Динамическое планирование через LLM на основе запроса пользователя
   - Вызов доступных навыков через их capability
   - Запись КАЖДОГО шага через стандартные методы сессии
   - Адаптивное принятие решений на основе результатов предыдущих шагов

3. ФИНАЛЬНЫЙ БЛОК:
   - Формирование структурированного отчета анализа
   - Сохранение полного контекста для последующих стратегий
   - Переключение на выполнение плана или завершение анализа

КРИТИЧЕСКИ ВАЖНО:
- НЕ используем несуществующие методы вроде data_context.get_last_items()
- Состояние анализа хранится в атрибутах сессии: session.code_analysis_state
- Все наблюдения получаются через шаги: step_context.get_last_steps() → observation_item_ids
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface
from core.session_context.model import ContextItemMetadata
from models.execution import ExecutionStatus


from .prompts import (
    build_analysis_planning_prompt,
    build_step_execution_prompt,
    build_final_report_prompt,
    SYSTEM_PROMPT_ANALYSIS_PLANNER,
    SYSTEM_PROMPT_STEP_EXECUTOR,
    SYSTEM_PROMPT_REPORT_GENERATOR
)
from .utils import extract_code_context_from_error

logger = logging.getLogger(__name__)


class CodeAnalysisThinkingPattern(AgentThinkingPatternInterface):
    """
    Паттерн мышления глубокого анализа кода с универсальным циклом выполнения.
    
    ЖИЗНЕННЫЙ ЦИКЛ АНАЛИЗА:
    ┌─────────────────────────────────────────────────────────────┐
    │  1. Инициализация (обязательные шаги)                       │
    │     - Проверка наличия ProjectMap                           │
    │     - Построение карты проекта при необходимости            │
    │     - Инициализация состояния анализа в атрибутах сессии    │
    └─────────────────────────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  2. Универсальный цикл анализа (макс. 10 итераций)          │
    │     Итерация:                                               │
    │     а) Планирование следующего шага через LLM               │
    │     б) Выполнение шага через навык/capability               │
    │     в) Запись результата в контекст                         │
    │     г) Оценка завершения анализа                            │
    └─────────────────────────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  3. Финальный блок                                           │
    │     - Генерация структурированного отчета                   │
    │     - Сохранение полного контекста                          │
    │     - Переключение на паттерн выполнения                    │
    └─────────────────────────────────────────────────────────────┘
    """
    name = "code_analysis"
    
    def __init__(self):
        self.max_analysis_steps = 10          # Максимальное количество шагов анализа
        self.max_total_steps = 15             # Общий лимит шагов (включая инициализацию и финал)
        self.timeout_per_step = 15.0          # Таймаут на один шаг анализа (секунды)
        self._analysis_start_time: Optional[float] = None
        self._current_step_number: int = 0
    
    async def next_step(self, runtime: AgentRuntimeInterface) -> StrategyDecision:
        """
        Основной метод стратегии — управление жизненным циклом анализа.
        РЕАЛИЗУЕТ АРХИТЕКТУРУ: обязательные шаги → универсальный цикл → финальный блок
        """
        session = runtime.session
        goal = session.get_goal() or ""
        current_step = session.step_context.get_current_step_number()
        
        # Инициализация анализа при первом шаге
        if current_step == 0:
            self._analysis_start_time = time.time()
            self._current_step_number = 0
            logger.info("Начало анализа кода через стратегию code_analysis")
            # Инициализация состояния анализа в атрибутах сессии
            session.code_analysis_state = None
            session.code_analysis_initialized = False
        
        # === ЭТАП 1: ОБЯЗАТЕЛЬНЫЕ НАЧАЛЬНЫЕ ШАГИ ===
        if not self._is_project_map_available(session):
            return await self._ensure_project_map(runtime, session, goal)
        
        if not getattr(session, 'code_analysis_initialized', False):
            return await self._initialize_analysis_state(runtime, session, goal)
        
        # === ЭТАП 2: УНИВЕРСАЛЬНЫЙ ЦИКЛ АНАЛИЗА ===
        analysis_state = getattr(session, 'code_analysis_state', None)
        
        # Защита от некорректного состояния
        if analysis_state is None:
            logger.warning("Состояние анализа отсутствует в сессии, повторная инициализация")
            return await self._initialize_analysis_state(runtime, session, goal)
        
        # Проверка завершения анализа
        if analysis_state.get("completed", False):
            return await self._finalize_analysis(runtime, session, analysis_state)
        
        # Проверка лимита шагов
        if self._current_step_number >= self.max_analysis_steps:
            logger.warning(f"Достигнут лимит шагов анализа ({self.max_analysis_steps}), завершение")
            analysis_state["completed"] = True
            analysis_state["completion_reason"] = "step_limit_reached"
            session.code_analysis_state = analysis_state
            return await self._finalize_analysis(runtime, session, analysis_state)
        
        # Выполнение одного шага универсального цикла
        return await self._execute_analysis_step(runtime, session, analysis_state, goal)
    
    # ==================== ЭТАП 1: ОБЯЗАТЕЛЬНЫЕ НАЧАЛЬНЫЕ ШАГИ ====================
    
    def _is_project_map_available(self, session: Any) -> bool:
        """Проверка наличия структуры проекта в контексте сессии."""
        # Приоритет 1: прямой доступ к атрибуту
        if hasattr(session, 'project_map') and session.project_map:
            return True
        
        # Приоритет 2: поиск в последних шагах контекста
        last_steps = session.step_context.get_last_steps(5)
        for step in reversed(last_steps):
            if step.observation_item_ids:
                # Получаем первое наблюдение из шага
                obs_id = step.observation_item_ids[0]
                observation = session.data_context.items.get(obs_id)
                if observation and observation.item_type.name == "OBSERVATION":
                    content = observation.content
                    if isinstance(content, dict) and content.get("source") == "project_map":
                        # Извлекаем карту проекта из наблюдения и сохраняем в сессию
                        session.project_map = content.get("project_map")
                        return True
        
        return False
    
    async def _ensure_project_map(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        goal: str
    ) -> StrategyDecision:
        """
        Обеспечение наличия структуры проекта.
        ДЕЙСТВИЯ:
        1. Запись шага инициализации в контекст
        2. Вызов ProjectMapSkill для построения карты проекта
        3. Сохранение результата в контекст сессии
        4. Возврат решения для продолжения анализа
        """
        # Запись шага инициализации
        step_number = session.step_context.get_current_step_number() + 1
        
        # Вызов навыка построения карты проекта
        project_map_skill = runtime.system.get_resource("project_map")
        if not project_map_skill:
            error_msg = "Навык project_map не найден в системном контексте"
            logger.error(error_msg)
            self._record_error_observation(session, error_msg, "initialization")
            return self._create_fallback_decision("project_map_skill_not_found")
        
        capability = runtime.system.get_capability("project_map.analyze_project")
        if not capability:
            error_msg = "Capability project_map.analyze_project не найдена"
            logger.error(error_msg)
            self._record_error_observation(session, error_msg, "initialization")
            return self._create_fallback_decision("analyze_project_capability_not_found")
        
        # Параметры для анализа проекта (ограничения для производительности)
        parameters = {
            "directory": ".",
            "max_items": 1000,
            "file_extensions": ["py"],
            "include_tests": False,
            "include_hidden": False,
            "include_code_units": True
        }
        
        # Выполнение анализа проекта
        start_time = time.time()
        result = await project_map_skill.execute(capability, parameters, session)
        duration = time.time() - start_time
        
        # Запись результата как наблюдения
        observation_id = session.record_observation(
            {
                "action": "project_map_analysis",
                "status": "success" if result.status == ExecutionStatus.SUCCESS else "failed",
                "duration_seconds": round(duration, 2),
                "file_count": getattr(result.result, 'total_files', 0) if result.result else 0,
                "code_unit_count": getattr(result.result, 'total_code_units', 0) if result.result else 0,
                "error": result.error if result.status != ExecutionStatus.SUCCESS else None,
                "project_map": result.result if result.status == ExecutionStatus.SUCCESS else None
            },
            source=self.name,
            step_number=step_number,
            metadata=ContextItemMetadata(
                source="code_analysis_initialization",
                confidence=1.0 if result.status == ExecutionStatus.SUCCESS else 0.0,
                step_number=step_number
            )
        )
        
        if result.status != ExecutionStatus.SUCCESS:
            error_msg = f"Не удалось построить карту проекта: {result.error or result.summary}"
            logger.error(error_msg)
            self._record_error_observation(session, error_msg, "initialization")
            return self._create_fallback_decision("project_map_analysis_failed")
        
        # Сохранение карты проекта в контекст сессии
        session.project_map = result.result
        logger.info(
            f"Карта проекта построена: {result.result.total_files} файлов, "
            f"{result.result.total_code_units} единиц кода"
        )
        
        # Продолжение анализа (следующий шаг будет инициализацией состояния)
        return StrategyDecision(
            action=StrategyDecisionType.CONTINUE,
            next_strategy=None,
            reason="project_map_built_proceed_to_initialization"
        )
    
    async def _initialize_analysis_state(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        goal: str
    ) -> StrategyDecision:
        """
        Инициализация состояния анализа.
        ДЕЙСТВИЯ:
        1. Парсинг цели пользователя для определения типа анализа
        2. Извлечение контекста ошибки (если присутствует)
        3. Сохранение состояния анализа в атрибутах сессии (НЕ в контексте наблюдений)
        """
        step_number = session.step_context.get_current_step_number() + 1
        
        # Определение типа анализа на основе цели
        analysis_type = self._determine_analysis_type(goal)
        
        # Извлечение контекста ошибки (если присутствует в цели)
        error_context = None
        if analysis_type == "error_diagnosis":
            error_context = extract_code_context_from_error(goal)
        
        # Формирование начального состояния анализа
        analysis_state = {
            "analysis_type": analysis_type,
            "error_context": error_context.model_dump() if error_context else None,
            "goal": goal[:500],  # Ограничение длины для контекста
            "completed": False,
            "completion_reason": None,
            "steps_executed": 0,
            "available_skills": self._get_available_skills_summary(runtime),
            "start_time": datetime.utcnow().isoformat(),
            "confidence": 0.0,
            "requires_human_review": False
        }
        
        # Сохранение состояния в АТРИБУТАХ СЕССИИ (надежно и просто)
        session.code_analysis_state = analysis_state
        session.code_analysis_initialized = True
        
        # Сохранение состояния как наблюдения (для аудита)
        observation_id = session.record_observation(
            {
                "analysis_state": "initialized",
                "state": analysis_state,
                "timestamp": datetime.utcnow().isoformat()
            },
            source=self.name,
            step_number=step_number,
            metadata=ContextItemMetadata(
                source="code_analysis_state",
                confidence=1.0,
                step_number=step_number
            )
        )
        
        logger.info(f"Состояние анализа инициализировано: тип={analysis_type}")
        self._current_step_number = 0  # Сброс счетчика шагов анализа
        
        # Переход к универсальному циклу анализа
        return StrategyDecision(
            action=StrategyDecisionType.CONTINUE,
            next_strategy=None,
            reason="analysis_state_initialized_proceed_to_cycle"
        )
    
    def _determine_analysis_type(self, goal: str) -> str:
        """
        Определение типа анализа на основе цели пользователя.
        ВОЗВРАЩАЕТ: "error_diagnosis", "code_review", "architecture_analysis", "dependency_analysis"
        """
        goal_lower = goal.lower()
        
        if any(kw in goal_lower for kw in ["ошибка", "error", "traceback", "stack trace", "sequence item", "expected str instance", "dict found"]):
            return "error_diagnosis"
        
        if any(kw in goal_lower for kw in ["review", "проверь", "анализ качества", "код смелл", "антипаттерн"]):
            return "code_review"
        
        if any(kw in goal_lower for kw in ["архитектура", "архитектур", "паттерн", "структура проекта"]):
            return "architecture_analysis"
        
        if any(kw in goal_lower for kw in ["зависимост", "зависимости", "импорт", "циклическ"]):
            return "dependency_analysis"
        
        return "general_analysis"  # Общий анализ по умолчанию
    
    def _get_available_skills_summary(self, runtime: AgentRuntimeInterface) -> List[Dict[str, Any]]:
        """Получение краткого списка доступных навыков и их capability."""
        skills_summary = []
        system_context = runtime.system
        
        # Список навыков, релевантных для анализа кода
        relevant_skills = ["project_navigator", "project_map", "planning"]
        
        for skill_name in relevant_skills:
            skill = system_context.get_resource(skill_name)
            if skill:
                capabilities = []
                for cap_name in system_context.list_capabilities():
                    cap = system_context.get_capability(cap_name)
                    if cap and cap.skill_name == skill_name and cap.visiable:
                        capabilities.append({
                            "name": cap.name,
                            "description": cap.description[:100]  # Ограничение длины
                        })
                
                if capabilities:
                    skills_summary.append({
                        "name": skill_name,
                        "capabilities": capabilities
                    })
        
        return skills_summary
    
    # ==================== ЭТАП 2: УНИВЕРСАЛЬНЫЙ ЦИКЛ АНАЛИЗА ====================
    
    async def _execute_analysis_step(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        analysis_state: Dict[str, Any],
        goal: str
    ) -> StrategyDecision:
        """
        Выполнение одного шага универсального цикла анализа.
        АЛГОРИТМ ШАГА:
        1. Планирование следующего действия через LLM
        2. Выбор навыка/capability для выполнения действия
        3. Выполнение действия через выбранный навык
        4. Запись результата в контекст сессии
        5. Оценка необходимости продолжения анализа
        """
        self._current_step_number += 1
        step_number = session.step_context.get_current_step_number() + 1
        
        logger.info(f"Шаг анализа #{self._current_step_number} из {self.max_analysis_steps}")
        
        # === ШАГ 2.1: ПЛАНИРОВАНИЕ СЛЕДУЮЩЕГО ДЕЙСТВИЯ ЧЕРЕЗ LLM ===
        planning_result = await self._plan_next_analysis_step(
            runtime=runtime,
            session=session,
            analysis_state=analysis_state,
            goal=goal,
            step_number=step_number
        )
        
        if not planning_result.get("success", False):
            error_msg = planning_result.get("error", "Неизвестная ошибка планирования")
            logger.error(f"Ошибка планирования шага анализа: {error_msg}")
            self._record_error_observation(session, error_msg, f"step_{self._current_step_number}_planning")
            return self._create_fallback_decision(f"step_{self._current_step_number}_planning_failed")
        
        action_plan = planning_result.get("action_plan", {})
        logger.debug(f"План действия для шага #{self._current_step_number}: {action_plan.get('description', 'без описания')}")
        
        # === ШАГ 2.2: ВЫПОЛНЕНИЕ ДЕЙСТВИЯ ЧЕРЕЗ НАВЫК ===
        execution_result = await self._execute_action_plan(
            runtime=runtime,
            session=session,
            action_plan=action_plan,
            analysis_state=analysis_state,
            step_number=step_number
        )
        
        # === ШАГ 2.3: ОЦЕНКА РЕЗУЛЬТАТА И ПРИНЯТИЕ РЕШЕНИЯ ===
        evaluation_result = await self._evaluate_step_result(
            runtime=runtime,
            session=session,
            action_plan=action_plan,
            execution_result=execution_result,
            analysis_state=analysis_state,
            step_number=step_number
        )
        
        # Обновление состояния анализа
        analysis_state["steps_executed"] = self._current_step_number
        analysis_state["last_step_result"] = evaluation_result
        analysis_state["confidence"] = max(
            analysis_state.get("confidence", 0.0),
            evaluation_result.get("confidence", 0.0)
        )
        analysis_state["requires_human_review"] = analysis_state.get("requires_human_review", False) or evaluation_result.get("requires_human_review", False)
        
        # Проверка завершения анализа
        if evaluation_result.get("analysis_complete", False):
            analysis_state["completed"] = True
            analysis_state["completion_reason"] = evaluation_result.get("completion_reason", "confidence_threshold_reached")
            session.code_analysis_state = analysis_state
            logger.info(f"Анализ завершен: {analysis_state['completion_reason']}")
            return await self._finalize_analysis(runtime, session, analysis_state)
        
        # Сохранение обновленного состояния в атрибутах сессии
        session.code_analysis_state = analysis_state
        
        # Продолжение цикла анализа
        return StrategyDecision(
            action=StrategyDecisionType.CONTINUE,
            next_strategy=None,
            reason=f"step_{self._current_step_number}_completed_proceed_to_next",
            payload={"step_number": self._current_step_number}
        )
    
    async def _plan_next_analysis_step(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        analysis_state: Dict[str, Any],
        goal: str,
        step_number: int
    ) -> Dict[str, Any]:
        """
        Планирование следующего шага анализа через структурированную генерацию.
        """
        try:
            # Формирование промпта для планирования
            prompt = build_analysis_planning_prompt(
                goal=goal,
                analysis_state=analysis_state,
                available_skills=self._get_available_skills_summary(runtime),
                step_number=self._current_step_number,
                max_steps=self.max_analysis_steps
            )
            
            # Структурированная генерация плана
            response = await runtime.system.call_llm_with_params(
                user_prompt=prompt,
                system_prompt=SYSTEM_PROMPT_ANALYSIS_PLANNER,
                output_schema={
                    "type": "object",
                    "properties": {
                        "action_type": {"type": "string", "enum": ["navigate", "search", "analyze_metadata", "generate_fix", "evaluate_completion"]},
                        "target_skill": {"type": "string"},
                        "capability_name": {"type": "string"},
                        "parameters": {"type": "object"},
                        "description": {"type": "string"},
                        "expected_outcome": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "requires_human_review": {"type": "boolean"}
                    },
                    "required": ["action_type", "target_skill", "capability_name", "parameters", "description", "confidence"]
                },
                output_format="json",
                temperature=0.3,
                max_tokens=800,
                timeout=self.timeout_per_step
            )
            
            # Обработка результата
            action_plan = response.content if hasattr(response, 'content') else response
            
            # Валидация плана
            if not isinstance(action_plan, dict):
                return {
                    "success": False,
                    "error": f"Некорректный формат плана: {action_plan}",
                    "confidence": 0.0
                }
            
            # Запись плана как наблюдения
            observation_id = session.record_observation(
                {
                    "action": "step_planning",
                    "step_number": self._current_step_number,
                    "plan": action_plan,
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=step_number,
                metadata=ContextItemMetadata(
                    source="code_analysis_planning",
                    confidence=action_plan.get("confidence", 0.5),
                    step_number=step_number
                )
            )
            
            logger.debug(f"План шага #{self._current_step_number} сформирован, observation_id={observation_id}")
            
            return {
                "success": True,
                "action_plan": action_plan,
                "confidence": action_plan.get("confidence", 0.5)
            }
            
        except Exception as e:
            error_msg = f"Ошибка планирования шага: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "confidence": 0.0
            }
    
    async def _execute_action_plan(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        action_plan: Dict[str, Any],
        analysis_state: Dict[str, Any],
        step_number: int
    ) -> Dict[str, Any]:
        """
        Выполнение запланированного действия через соответствующий навык.
        """
        start_time = time.time()
        action_type = action_plan.get("action_type")
        target_skill = action_plan.get("target_skill")
        capability_name = action_plan.get("capability_name")
        parameters = action_plan.get("parameters", {})
        
        try:
            # Получение навыка из системного контекста
            skill = runtime.system.get_resource(target_skill)
            if not skill:
                error_msg = f"Навык '{target_skill}' не найден в системном контексте"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "skill_name": target_skill,
                    "capability_name": capability_name,
                    "duration_seconds": time.time() - start_time
                }
            
            # Получение capability
            capability = runtime.system.get_capability(capability_name)
            if not capability:
                error_msg = f"Capability '{capability_name}' не найдена"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "skill_name": target_skill,
                    "capability_name": capability_name,
                    "duration_seconds": time.time() - start_time
                }

            # Выполнение действия через навык
            result = await skill.execute(capability, parameters, session)
            duration = time.time() - start_time
            
            # Запись результата как наблюдения
            observation_content = {
                "action": "step_execution",
                "step_number": self._current_step_number,
                "action_type": action_type,
                "skill": target_skill,
                "capability": capability_name,
                "parameters": parameters,
                "status": "success" if result.status == ExecutionStatus.SUCCESS else "failed",
                "result_summary": result.summary[:500] if result.summary else None,
                "error": result.error,
                "duration_seconds": round(duration, 3),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Добавляем результат только если это словарь или список (безопасно для сериализации)
            if result.result and isinstance(result.result, (dict, list)):
                observation_content["result_data"] = result.result
            
            observation_id = session.record_observation(
                observation_content,
                source=self.name,
                step_number=step_number,
                metadata=ContextItemMetadata(
                    source=f"code_analysis_execution_{action_type}",
                    confidence=1.0 if result.status == ExecutionStatus.SUCCESS else 0.0,
                    step_number=step_number
                )
            )
            
            logger.debug(
                f"Действие '{action_type}' выполнено за {duration:.3f}с, "
                f"статус={result.status.value}, observation_id={observation_id}"
            )
            
            return {
                "success": result.status == ExecutionStatus.SUCCESS,
                "result": result.result,
                "skill_name": target_skill,
                "capability_name": capability_name,
                "duration_seconds": duration,
                "observation_id": observation_id,
                "result_summary": result.summary
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Ошибка выполнения действия '{action_type}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Запись ошибки как наблюдения
            observation_id = session.record_observation(
                {
                    "action": "step_execution_error",
                    "step_number": self._current_step_number,
                    "action_type": action_type,
                    "error": error_msg,
                    "duration_seconds": round(duration, 3),
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=step_number,
                metadata=ContextItemMetadata(
                    source="code_analysis_execution_error",
                    confidence=0.0,
                    step_number=step_number
                )
            )
            
            return {
                "success": False,
                "error": error_msg,
                "skill_name": target_skill,
                "capability_name": capability_name,
                "duration_seconds": duration,
                "observation_id": observation_id
            }
    
    async def _evaluate_step_result(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        action_plan: Dict[str, Any],
        execution_result: Dict[str, Any],
        analysis_state: Dict[str, Any],
        step_number: int
    ) -> Dict[str, Any]:
        """
        Оценка результата шага и принятие решения о продолжении анализа.
        """
        try:
            # Формирование промпта для оценки
            prompt = build_step_execution_prompt(
                goal=analysis_state.get("goal", ""),
                analysis_type=analysis_state.get("analysis_type", "general_analysis"),
                action_plan=action_plan,
                execution_result=execution_result,
                previous_steps=self._current_step_number,
                max_steps=self.max_analysis_steps,
                current_confidence=analysis_state.get("confidence", 0.0)
            )
            
            # Структурированная генерация оценки
            response = await runtime.system.call_llm_with_params(
                user_prompt=prompt,
                system_prompt=SYSTEM_PROMPT_STEP_EXECUTOR,
                output_schema={
                    "type": "object",
                    "properties": {
                        "analysis_complete": {"type": "boolean"},
                        "completion_reason": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "next_action_suggestion": {"type": "string"},
                        "requires_human_review": {"type": "boolean"},
                        "key_findings": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["analysis_complete", "confidence", "requires_human_review"]
                },
                output_format="json",
                temperature=0.2,
                max_tokens=600,
                timeout=10.0
            )
            
            evaluation = response.content if hasattr(response, 'content') else response
            
            # Запись оценки как наблюдения
            observation_id = session.record_observation(
                {
                    "action": "step_evaluation",
                    "step_number": self._current_step_number,
                    "evaluation": evaluation,
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=step_number,
                metadata=ContextItemMetadata(
                    source="code_analysis_evaluation",
                    confidence=evaluation.get("confidence", 0.5),
                    step_number=step_number
                )
            )
            
            logger.debug(f"Оценка шага #{self._current_step_number} выполнена, observation_id={observation_id}")
            
            return evaluation
            
        except Exception as e:
            error_msg = f"Ошибка оценки шага: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Консервативная оценка при ошибке
            return {
                "analysis_complete": False,
                "confidence": max(0.0, analysis_state.get("confidence", 0.0) - 0.1),
                "requires_human_review": True,
                "next_action_suggestion": "Повторить анализ с другим подходом"
            }
    
    # ==================== ЭТАП 3: ФИНАЛЬНЫЙ БЛОК ====================
    
    async def _finalize_analysis(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        analysis_state: Dict[str, Any]
    ) -> StrategyDecision:
        """
        Финальный блок — формирование отчета и подготовка к переключению стратегии.
        """
        step_number = session.step_context.get_current_step_number() + 1
        
        # === ШАГ 3.1: ГЕНЕРАЦИЯ СТРУКТУРИРОВАННОГО ОТЧЕТА ===
        report_result = await self._generate_analysis_report(
            runtime=runtime,
            session=session,
            analysis_state=analysis_state,
            step_number=step_number
        )
        
        if not report_result.get("success", False):
            error_msg = report_result.get("error", "Неизвестная ошибка генерации отчета")
            logger.error(f"Ошибка генерации отчета: {error_msg}")
            self._record_error_observation(session, error_msg, "report_generation")
            return self._create_fallback_decision("report_generation_failed")
        
        analysis_report = report_result.get("report", {})
        
        # === ШАГ 3.2: СОХРАНЕНИЕ ПОЛНОГО ОТЧЕТА В КОНТЕКСТ ===
        report_observation_id = session.record_observation(
            {
                "action": "analysis_complete",
                "report": analysis_report,
                "analysis_state": analysis_state,
                "timestamp": datetime.utcnow().isoformat(),
                "duration_seconds": round(time.time() - self._analysis_start_time, 2) if self._analysis_start_time else None,
                "total_steps": self._current_step_number
            },
            source=self.name,
            step_number=step_number,
            metadata=ContextItemMetadata(
                source="code_analysis_final_report",
                confidence=analysis_state.get("confidence", 0.0),
                step_number=step_number
            )
        )
        
        logger.info(
            f"Анализ кода завершен за {self._current_step_number} шагов. "
            f"Уверенность: {analysis_state.get('confidence', 0.0):.2f}, "
            f"отчет сохранен с observation_id={report_observation_id}"
        )
        
        # === ШАГ 3.3: ПЕРЕКЛЮЧЕНИЕ НА СТРАТЕГИЮ ВЫПОЛНЕНИЯ ===
        # Определение следующей стратегии на основе типа анализа и результата
        next_strategy = "react"  # По умолчанию — выполнение через ReAct
        
        if analysis_state.get("requires_human_review", False):
            next_strategy = "evaluation"  # Требуется ручная оценка
        
        # Формирование решения для переключения
        # Если next_strategy по-прежнему старая стратегия, используем новую
        if next_strategy == "react":
            next_strategy = "react_composable"
        elif next_strategy == "evaluation":
            next_strategy = "evaluation_composable"  # если такая стратегия существует, иначе оставим как есть
        
        return StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy=next_strategy,
            reason="analysis_complete",
            payload={
                "analysis_report_id": report_observation_id,
                "confidence": analysis_state.get("confidence", 0.0),
                "completion_reason": analysis_state.get("completion_reason", "completed"),
                "requires_human_review": analysis_state.get("requires_human_review", False)
            }
        )
    
    async def _generate_analysis_report(
        self,
        runtime: AgentRuntimeInterface,
        session: Any,
        analysis_state: Dict[str, Any],
        step_number: int
    ) -> Dict[str, Any]:
        """
        Генерация структурированного отчета анализа через структурированную генерацию.
        """
        try:
            # Сбор всех наблюдений анализа из контекста через шаги
            analysis_observations = []
            last_steps = session.step_context.get_last_steps(30)  # Последние 30 шагов
            
            for step in reversed(last_steps):
                if step.observation_item_ids:
                    for obs_id in step.observation_item_ids[:2]:  # Берем максимум 2 наблюдения на шаг
                        observation = session.data_context.items.get(obs_id)
                        if observation and observation.item_type.name == "OBSERVATION":
                            content = observation.content
                            if isinstance(content, dict):
                                # Фильтрация релевантных наблюдений анализа
                                if any(key in content for key in ["action", "analysis_state", "step_number", "plan", "result_data"]):
                                    analysis_observations.append(content)
            
            # Ограничение объема данных для промпта
            analysis_observations = analysis_observations[:20]
            
            # Формирование промпта для генерации отчета
            prompt = build_final_report_prompt(
                goal=analysis_state.get("goal", ""),
                analysis_type=analysis_state.get("analysis_type", "general_analysis"),
                analysis_observations=analysis_observations,
                error_context=analysis_state.get("error_context"),
                confidence=analysis_state.get("confidence", 0.0),
                total_steps=self._current_step_number
            )
            
            # Структурированная генерация отчета
            response = await runtime.system.call_llm_with_params(
                user_prompt=prompt,
                system_prompt=SYSTEM_PROMPT_REPORT_GENERATOR,
                output_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "problem_description": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "recommendations": {"type": "array", "items": {"type": "string"}},
                        "requires_human_review": {"type": "boolean"},
                        "suggested_fix": {"type": "string"}
                    },
                    "required": ["summary", "problem_description", "confidence", "requires_human_review"]
                },
                output_format="json",
                temperature=0.2,
                max_tokens=1200,
                timeout=20.0
            )
            
            report = response.content if hasattr(response, 'content') else response
            
            # Валидация отчета
            if not isinstance(report, dict) or "summary" not in report:
                return {
                    "success": False,
                    "error": f"Некорректный формат отчета: {report}"
                }
            
            # Запись отчета как наблюдения (предварительно)
            observation_id = session.record_observation(
                {
                    "action": "report_generation",
                    "report": report,
                    "timestamp": datetime.utcnow().isoformat()
                },
                source=self.name,
                step_number=step_number,
                metadata=ContextItemMetadata(
                    source="code_analysis_report_draft",
                    confidence=report.get("confidence", 0.5),
                    step_number=step_number
                )
            )
            
            logger.debug(f"Отчет анализа сгенерирован, observation_id={observation_id}")
            
            return {
                "success": True,
                "report": report
            }
            
        except Exception as e:
            error_msg = f"Ошибка генерации отчета: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    def _record_error_observation(self, session: Any, error_message: str, phase: str):
        """Запись ошибки как наблюдения в контекст сессии."""
        step_number = session.step_context.get_current_step_number() + 1
        
        observation_id = session.record_observation(
            {
                "action": "error",
                "phase": phase,
                "error": error_message,
                "timestamp": datetime.utcnow().isoformat()
            },
            source=self.name,
            step_number=step_number,
            metadata=ContextItemMetadata(
                source="code_analysis_error",
                confidence=0.0,
                step_number=step_number
            )
        )
        logger.error(f"Ошибка записана в контекст: {error_message}, observation_id={observation_id}")
    
    def _create_fallback_decision(self, reason: str) -> StrategyDecision:
        """Создание решения для отката при ошибках."""
        logger.warning(f"Активация fallback в CodeAnalysisStrategy: {reason}")
        return StrategyDecision(
            action=StrategyDecisionType.SWITCH,
            next_strategy="fallback",
            reason=f"code_analysis_{reason}"
        )