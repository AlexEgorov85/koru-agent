"""Навык для генерации финального ответа агента.

Этот навык анализирует весь контекст сессии и формирует
комплексный финальный ответ на основе всех собранных данных.

АРХИТЕКТУРА:
- Использует ComponentConfig для конфигурации
- Промпты и контракты загружаются через сервисы при инициализации
- Валидация через кэшированные YAML-схемы
- Никаких Pydantic-моделей в коде — только YAML-контракты
"""
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.session_context.base_session_context import BaseSessionContext
from core.application.skills.base_skill import BaseSkill
from core.config.component_config import ComponentConfig
from core.models.data.capability import Capability
from core.infrastructure.logging import EventBusLogger


class FinalAnswerSkill(BaseSkill):
    """
    Навык для генерации финального ответа на основе всего контекста сессии.

    ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ:
    - concise: краткий и точный ответ без излишних деталей
    - detailed: развёрнутый ответ с полным объяснением и контекстом
    - structured: ответ с чёткой структурой (резюме, выводы, доказательства)

    АРХИТЕКТУРНЫЕ ГАРАНТИИ:
    - Все ресурсы (промты, контракты) предзагружены при initialize()
    - Валидация через кэшированные YAML-схемы
    - Взаимодействие через ActionExecutor
    """

    # Явная декларация зависимостей
    DEPENDENCIES = ["prompt_service", "contract_service"]

    name = "final_answer"
    supported_strategies = ["react", "planning", "evaluation", "plan_and_execute", "chain_of_thought"]

    def __init__(
        self,
        name: str,
        application_context: Any,
        component_config: ComponentConfig,
        executor: Any
    ):
        super().__init__(name, application_context, component_config=component_config, executor=executor)

        # Кэш для скриптов реестра
        self._scripts_registry = None
        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        # event_bus_logger будет инициализирован в BaseComponent._init_event_bus_logger()
        # Этот метод оставлен для совместимости но не делает ничего
        pass

    def get_capabilities(self) -> List[Capability]:
        """
        Возвращает список поддерживаемых capability для генерации финального ответа.
        
        ВОЗВРАЩАЕТ:
        - List[Capability]: Список capability с метаданными
        """
        return [
            Capability(
                name="final_answer.generate",
                description="Генерация финального ответа на основе всего контекста сессии с поддержкой различных форматов вывода",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True,
                meta={
                    "contract_version": "v1.0.0",
                    "prompt_version": "v1.0.0",
                    "requires_llm": True,
                    "execution_type": "llm-powered",
                    "formats": ["concise", "detailed", "structured"]
                }
            )
        ]

    async def initialize(self) -> bool:
        """
        Инициализация навыка с предзагрузкой всех ресурсов.
        
        ВОЗВРАЩАЕТ:
        - bool: True если инициализация успешна
        """
        success = await super().initialize()
        if not success:
            return False

        # Проверяем наличие необходимых ресурсов для capability
        capability_name = "final_answer.generate"

        # Проверяем промпт
        if capability_name not in self.prompts:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Промпт для {capability_name} не загружен")
        else:
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Промпт для {capability_name} загружен: {self.prompts[capability_name].version}")

        # Проверяем входную схему
        if capability_name not in self.input_contracts:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Входная схема для {capability_name} не загружена")
        else:
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Входная схема для {capability_name} загружена")

        # Проверяем выходную схему
        if capability_name not in self.output_contracts:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Выходная схема для {capability_name} не загружена")
        else:
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Выходная схема для {capability_name} загружена")

        if self.event_bus_logger:
            await self.event_bus_logger.info(f"FinalAnswerSkill инициализирован с capability: {list(self.get_capability_names())}")
        return True

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения навыка финального ответа."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.SKILL_EXECUTED

    async def _execute_impl(
        self,
        capability: str,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики навыка финального ответа.

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.

        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: Данные результата (не ExecutionResult!)
        """
        if capability.name != "final_answer.generate":
            raise ValueError(f"Неподдерживаемая capability: {capability.name}")

        # Извлечение контекста сессии
        session_context = execution_context.session_context if hasattr(execution_context, 'session_context') else execution_context

        # Генерация финального ответа
        result = await self._generate_final_answer(session_context, parameters, execution_context)

        # Извлекаем данные из ExecutionResult если нужно
        if isinstance(result, dict):
            return result
        elif hasattr(result, 'data') and result.data:
            return result.data
        return {}

    async def _generate_final_answer(
        self,
        context: BaseSessionContext,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> ExecutionResult:
        """
        Генерация финального ответа на основе контекста сессии.

        ПАРАМЕТРЫ:
        - context: контекст сессии (только для get_goal())
        - parameters: параметры генерации
        - execution_context: контекст выполнения для доступа к данным

        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: результат генерации
        """
        # Извлечение цели
        goal = context.get_goal() or "Не указана цель"

        # Сбор всей информации из контекста ЧЕРЕЗ EXECUTOR (не напрямую!)
        observations = []
        thoughts = []
        actions = []

        # Получаем все items из контекста через executor
        try:
            from core.models.data.execution import ExecutionStatus
            all_items_result = await self.executor.execute_action(
                action_name="context.get_all_items",
                parameters={},
                context=execution_context
            )

            if all_items_result.status == ExecutionStatus.COMPLETED and all_items_result.result:
                all_items = all_items_result.result.get("items", {})

                # Классификация элементов контекста
                for item_id, item in all_items.items():
                    # item может быть dict или объектом
                    if isinstance(item, dict):
                        item_type = item.get("item_type", "")
                        item_content = item.get("content", {})
                    else:
                        item_type = item.item_type.value if hasattr(item.item_type, 'value') else str(item.item_type)
                        item_content = item.content

                    if item_type == "OBSERVATION":
                        observations.append(item_content if isinstance(item_content, str) else str(item_content))
                    elif item_type in ["THOUGHT", "DECISION"]:
                        thoughts.append(item_content if isinstance(item_content, str) else str(item_content))
                    elif item_type == "ACTION":
                        if isinstance(item_content, dict):
                            actions.append({
                                "action": item_content.get("capability", "неизвестно"),
                                "result": str(item_content.get("result", ""))[:200] if item_content.get("result") else ""
                            })
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Не удалось получить items из контекста: {e}")
            # Продолжаем с пустыми списками

        # Получаем шаги выполнения через executor
        steps_taken = []
        try:
            from core.models.data.execution import ExecutionStatus
            steps_result = await self.executor.execute_action(
                action_name="context.get_step_history",
                parameters={},
                context=execution_context
            )

            if steps_result.status == ExecutionStatus.COMPLETED and steps_result.result:
                steps_list = steps_result.result.get("steps", [])
                for step in steps_list[-10:]:  # Последние 10 шагов
                    if isinstance(step, dict):
                        steps_taken.append({
                            "action": step.get("action", "неизвестно"),
                            "result": str(step.get("result", ""))[:200] if step.get("result") else ""
                        })
                    else:
                        steps_taken.append({
                            "action": getattr(step, 'action', 'неизвестно'),
                            "result": getattr(step, 'result', '')[:200] if getattr(step, 'result') else ''
                        })
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Не удалось получить step history: {e}")
            # Продолжаем с пустыми шагами

        # Параметры форматирования
        include_steps = parameters.get("include_steps", True)
        include_evidence = parameters.get("include_evidence", True)
        format_type = parameters.get("format_type", "detailed")
        confidence_threshold = parameters.get("confidence_threshold", 0.7)
        max_sources = parameters.get("max_sources", 10)

        # Получение промпта С КОНТРАКТАМИ из кэша (через BaseComponent.get_prompt_with_contract)
        capability_name = "final_answer.generate"
        prompt_with_contract = self.get_prompt_with_contract(capability_name)

        if not prompt_with_contract:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Промпт для {capability_name} не найден в кэше")
            return self._build_fallback_response(goal, observations, steps_taken, format_type)

        # Рендеринг промпта с переменными (используем метод из BaseComponent)
        try:
            rendered_prompt = self.render_prompt(
                capability_name,
                goal=goal,
                observations=observations[-max_sources:],
                steps_taken=steps_taken[-10:],
                format_type=format_type,
                include_steps=include_steps,
                include_evidence=include_evidence,
                confidence_threshold=confidence_threshold,
                max_sources=max_sources
            )
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Ошибка рендеринга промпта: {e}, используем fallback")
            rendered_prompt = self._render_prompt_fallback(
                goal=goal,
                observations=observations,
                steps_taken=steps_taken,
                format_type=format_type,
                include_steps=include_steps,
                include_evidence=include_evidence,
                confidence_threshold=confidence_threshold,
                max_sources=max_sources
            )

        # Вызов LLM для генерации ответа С STRUCTURED OUTPUT
        try:
            # Получаем схему выхода для structured output
            output_schema = self.get_output_contract("final_answer.generate")

            # Вызов LLM С STRUCTURED OUTPUT через executor (напрямую, без _call_llm)
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": rendered_prompt,
                    "structured_output": {
                        "output_model": "final_answer.generate.output",
                        "schema_def": output_schema if output_schema else {},
                        "max_retries": 3,
                        "strict_mode": True
                    },
                    "temperature": 0.3,
                    "max_tokens": 1500
                },
                context=execution_context
            )

            # Проверка на ошибку
            from core.models.data.execution import ExecutionStatus
            if llm_result.status != ExecutionStatus.COMPLETED:
                error_msg = llm_result.error
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"LLM structured output ошибка: {error_msg} (тип: {error_type})")
                raise RuntimeError(f"Ошибка LLM: {error_msg}")

            # Получаем структурированные данные
            # ✅ ИСПРАВЛЕНО: Работаем с Pydantic моделью или dict
            llm_result_data = llm_result.result
            if hasattr(llm_result_data, 'parsed_content'):
                # StructuredLLMResponse — извлекаем parsed_content
                parsed_response = llm_result_data.parsed_content
            elif isinstance(llm_result_data, dict):
                parsed_response = llm_result_data.get("parsed_content", {})
            else:
                parsed_response = llm_result_data if llm_result_data else {}

            # Логирование успешного structured output
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                    f"Финальный ответ сгенерирован с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
                )

            # Формирование финального результата
            # ✅ ИСПРАВЛЕНО: Работаем с Pydantic моделью или dict
            from pydantic import BaseModel
            if isinstance(parsed_response, BaseModel):
                # Pydantic модель — используем атрибуты
                final_answer_val = getattr(parsed_response, 'answer', '')
                confidence_val = getattr(parsed_response, 'confidence', 0.8)
                remaining_questions_val = getattr(parsed_response, 'remaining_questions', [])
            else:
                # dict — используем .get()
                final_answer_val = parsed_response.get("answer", "")
                confidence_val = parsed_response.get("confidence", 0.8)
                remaining_questions_val = parsed_response.get("remaining_questions", [])

            result_data = {
                "final_answer": final_answer_val,
                "sources": observations[-max_sources:] if include_evidence else [],
                "confidence_score": confidence_val,
                "remaining_questions": remaining_questions_val,
                "summary_of_steps": self._build_steps_summary(steps_taken) if include_steps else "",
                "metadata": {
                    "total_observations": len(observations),
                    "total_steps": len(steps_taken),
                    "generation_time_ms": 0,
                    "format_type": format_type,
                    "structured_output": True
                }
            }

            return ExecutionResult.success(
                data=result_data,
                metadata={
                    "observations_count": len(observations),
                    "steps_count": len(steps_taken),
                    "format_type": format_type,
                    "structured_output": True
                },
                side_effect=False
            )

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка вызова LLM: {str(e)}")
            fallback_result = self._build_fallback_response(goal, observations, steps_taken, format_type)
            return ExecutionResult.failure(
                error=str(e),
                metadata=fallback_result
            )

    def _render_prompt_fallback(
        self,
        goal: str,
        observations: List[str],
        steps_taken: List[Dict],
        format_type: str,
        include_steps: bool,
        include_evidence: bool,
        confidence_threshold: float,
        max_sources: int
    ) -> str:
        """Fallback-рендеринг промпта без использования сервиса."""
        prompt_parts = [
            "Ты — интеллектуальный ассистент, который генерирует финальный ответ на основе всего контекста сессии.",
            f"\n## Исходная цель\n{goal}",
            f"\n## Собранная информация (наблюдения)\n"
        ]
        
        if observations:
            for i, obs in enumerate(observations[-max_sources:], 1):
                prompt_parts.append(f"{i}. {obs[:300]}")
        else:
            prompt_parts.append("Наблюдения отсутствуют.")
        
        prompt_parts.append(f"\n## Выполненные шаги\n")
        if steps_taken:
            for i, step in enumerate(steps_taken[-10:], 1):
                result_part = f" → {step['result'][:100]}" if step.get('result') else ""
                prompt_parts.append(f"{i}. {step['action']}{result_part}")
        else:
            prompt_parts.append("Шаги выполнения не зафиксированы.")
        
        prompt_parts.extend([
            f"\n## Требования к ответу",
            f"- **Формат вывода**: {format_type}",
            f"- **Включать шаги выполнения**: {include_steps}",
            f"- **Включать источники (доказательства)**: {include_evidence}",
            f"\nСгенерируй финальный ответ согласно требованиям."
        ])
        
        return "\n".join(prompt_parts)

    def _build_steps_summary(self, steps_taken: List[Dict]) -> str:
        """
        Построение краткого резюме выполненных шагов.
        
        ПАРАМЕТРЫ:
        - steps_taken: список выполненных шагов
        
        ВОЗВРАЩАЕТ:
        - str: резюме шагов
        """
        if not steps_taken:
            return "Шаги выполнения не зафиксированы."
        
        summary_parts = []
        for i, step in enumerate(steps_taken[-10:], 1):
            result_part = f" → {step['result'][:100]}" if step.get('result') else ""
            summary_parts.append(f"{i}. {step['action']}{result_part}")
        
        return "\n".join(summary_parts)

    def _build_fallback_response(
        self,
        goal: str,
        observations: List[str],
        steps_taken: List[Dict],
        format_type: str
    ) -> Dict[str, Any]:
        """
        Построение резервного ответа при ошибке генерации.
        
        ПАРАМЕТРЫ:
        - goal: цель сессии
        - observations: список наблюдений
        - steps_taken: список шагов
        - format_type: тип формата
        
        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: резервный ответ
        """
        fallback_answer = (
            f"На основе проведённого анализа, цель '{goal}' была обработана.\n\n"
            f"Обработано наблюдений: {len(observations)}\n"
            f"Выполнено шагов: {len(steps_taken)}\n\n"
            f"К сожалению, произошла ошибка при генерации развёрнутого ответа. "
            f"Пожалуйста, попробуйте повторить запрос."
        )
        
        return {
            "final_answer": fallback_answer,
            "sources": observations[:5],
            "confidence_score": 0.5,
            "remaining_questions": [],
            "summary_of_steps": self._build_steps_summary(steps_taken),
            "metadata": {
                "total_observations": len(observations),
                "total_steps": len(steps_taken),
                "generation_time_ms": 0,
                "format_type": format_type
            }
        }

    def get_cached_input_contract_safe(self, capability: str) -> Optional[Any]:
        """
        Безопасное получение кэшированного входного контракта.

        ПАРАМЕТРЫ:
        - capability: имя capability

        ВОЗВРАЩАЕТ:
        - Схема валидации или None
        """
        return self.input_contracts.get(capability)

    def get_cached_output_contract_safe(self, capability: str) -> Optional[Any]:
        """
        Безопасное получение кэшированного выходного контракта.

        ПАРАМЕТРЫ:
        - capability: имя capability

        ВОЗВРАЩАЕТ:
        - Схема валидации или None
        """
        return self.output_contracts.get(capability)

    def get_cached_prompt_safe(self, capability: str) -> Optional[Prompt]:
        """
        Безопасное получение кэшированного промпта.
        
        ПАРАМЕТРЫ:
        - capability: имя capability
        
        ВОЗВРАЩАЕТ:
        - Prompt объект или None
        """
        return self.prompts.get(capability)
