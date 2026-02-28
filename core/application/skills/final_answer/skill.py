"""Навык для генерации финального ответа агента.

Этот навык анализирует весь контекст сессии и формирует
комплексный финальный ответ на основе всех собранных данных.

АРХИТЕКТУРА:
- Использует ComponentConfig для конфигурации
- Промпты и контракты загружаются через сервисы при инициализации
- Валидация через кэшированные YAML-схемы
- Никаких Pydantic-моделей в коде — только YAML-контракты
"""
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.session_context.base_session_context import BaseSessionContext
from core.application.skills.base_skill import BaseSkill
from core.config.component_config import ComponentConfig
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.data.prompt import Prompt

logger = logging.getLogger(__name__)


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
            self.logger.warning(f"Промпт для {capability_name} не загружен")
        else:
            self.logger.info(f"Промпт для {capability_name} загружен: {self.prompts[capability_name].version}")

        # Проверяем входную схему
        if capability_name not in self.input_contracts:
            self.logger.warning(f"Входная схема для {capability_name} не загружена")
        else:
            self.logger.info(f"Входная схема для {capability_name} загружена")

        # Проверяем выходную схему
        if capability_name not in self.output_contracts:
            self.logger.warning(f"Выходная схема для {capability_name} не загружена")
        else:
            self.logger.info(f"Выходная схема для {capability_name} загружена")

        self.logger.info(f"FinalAnswerSkill инициализирован с capability: {list(self.get_capability_names())}")
        return True

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения навыка финального ответа."""
        from core.infrastructure.event_bus.event_bus import EventType
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
        """
        if capability.name != "final_answer.generate":
            raise ValueError(f"Неподдерживаемая capability: {capability.name}")

        # Извлечение контекста сессии
        session_context = execution_context.session_context if hasattr(execution_context, 'session_context') else execution_context

        # Генерация финального ответа
        result = await self._generate_final_answer(session_context, parameters)
        return result

    async def _generate_final_answer(
        self,
        context: BaseSessionContext,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Генерация финального ответа на основе контекста сессии.
        
        ПАРАМЕТРЫ:
        - context: контекст сессии
        - parameters: параметры генерации
        
        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: результат генерации
        """
        # Извлечение цели
        goal = context.get_goal() or "Не указана цель"

        # Сбор всей информации из контекста
        all_items = context.data_context.items if hasattr(context, 'data_context') and hasattr(context.data_context, 'items') else {}
        observations = []
        thoughts = []
        actions = []

        # Классификация элементов контекста
        for item_id, item in all_items.items():
            item_type = item.item_type.value if hasattr(item.item_type, 'value') else str(item.item_type)
            if item_type == "OBSERVATION":
                observations.append(item.content)
            elif item_type in ["THOUGHT", "DECISION"]:
                thoughts.append(item.content)
            elif item_type == "ACTION":
                actions.append({
                    "action": item.content.get("capability", "неизвестно"),
                    "result": str(item.content.get("result", ""))[:200] if item.content.get("result") else ""
                })

        # Подготовка шагов выполнения
        steps_taken = []
        if hasattr(context, 'step_context') and hasattr(context.step_context, 'steps'):
            for step in context.step_context.steps:
                steps_taken.append({
                    "action": getattr(step, 'action', 'неизвестно'),
                    "result": getattr(step, 'result', '')[:200] if getattr(step, 'result') else ''
                })

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
            self.logger.error(f"Промпт для {capability_name} не найден в кэше")
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
            self.logger.warning(f"Ошибка рендеринга промпта: {e}, используем fallback")
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
            llm_response = await self._call_llm(rendered_prompt, execution_context)

            # Получаем структурированные данные (уже parsed_content из structured output)
            # _parse_llm_response больше не нужен, так как LLM вернул валидную структуру
            parsed_response = llm_response if isinstance(llm_response, dict) else self._parse_llm_response(str(llm_response), format_type)

            # Формирование финального результата
            result = {
                "final_answer": parsed_response.get("answer", ""),
                "sources": observations[-max_sources:] if include_evidence else [],
                "confidence_score": parsed_response.get("confidence", 0.8),
                "remaining_questions": parsed_response.get("remaining_questions", []),
                "summary_of_steps": self._build_steps_summary(steps_taken) if include_steps else "",
                "metadata": {
                    "total_observations": len(observations),
                    "total_steps": len(steps_taken),
                    "generation_time_ms": 0,  # Будет установлено в execute()
                    "format_type": format_type,
                    "structured_output": True
                }
            }

            return result

        except Exception as e:
            self.logger.error(f"Ошибка вызова LLM: {str(e)}")
            return self._build_fallback_response(goal, observations, steps_taken, format_type)

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

    async def _call_llm(self, prompt: str, execution_context=None) -> Dict[str, Any]:
        """
        Вызов LLM для генерации ответа С STRUCTURED OUTPUT.

        ПАРАМЕТРЫ:
        - prompt: отрендеренный промпт
        - execution_context: контекст выполнения (опционально)

        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: структурированный ответ от LLM (parsed_content)
        """
        try:
            from core.models.types.llm_types import StructuredOutputConfig

            # Получаем схему выхода для structured output
            output_schema = self.get_output_contract("final_answer.generate")

            # Вызов LLM С STRUCTURED OUTPUT через executor
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": prompt,
                    "structured_output": {
                        "output_model": "final_answer.generate.output",
                        "schema_def": output_schema if output_schema else {},
                        "max_retries": 3,
                        "strict_mode": True
                    },
                    "temperature": 0.3,
                    "max_tokens": 1500
                },
                context=execution_context if execution_context else ExecutionContext()
            )

            # Проверка на ошибку
            if not llm_result.success:
                error_msg = llm_result.error
                error_type = llm_result.metadata.get("error_type", "unknown")
                self.logger.error(f"LLM structured output ошибка при формировании ответа: {error_msg} (тип: {error_type})")
                raise RuntimeError(f"Ошибка LLM: {error_msg}")

            # Логирование успешного structured output
            self.logger.info(
                f"Финальный ответ сгенерирован с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1)})"
            )

            # Возвращаем структурированные данные (Pydantic model_dump())
            return llm_result.data.get("parsed_content", {})

        except Exception as e:
            self.logger.error(f"Ошибка вызова LLM: {str(e)}")
            raise

    def _parse_llm_response(self, llm_response: str, format_type: str) -> Dict[str, Any]:
        """
        Парсинг ответа LLM в структурированный формат.
        
        ПАРАМЕТРЫ:
        - llm_response: сырой ответ от LLM
        - format_type: тип формата
        
        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: структурированный ответ
        """
        # Простой парсинг — в продакшене можно использовать более сложную логику
        confidence = 0.8  # Значение по умолчанию
        
        # Попытка извлечь уровень уверенности из ответа
        import re
        confidence_match = re.search(r'[Уу]веренность[:\s]*([0-9.]+)', llm_response)
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
            except ValueError:
                pass
        
        # Извлечение нерешённых вопросов
        remaining_questions = []
        questions_section = llm_response.split("Нерешённые вопросы")[-1] if "Нерешённые вопросы" in llm_response else ""
        if questions_section:
            for line in questions_section.split("\n"):
                line = line.strip()
                if line.startswith("-") and len(line) > 2:
                    remaining_questions.append(line[1:].strip())
        
        return {
            "answer": llm_response,
            "confidence": confidence,
            "remaining_questions": remaining_questions[:5]  # Максимум 5 вопросов
        }

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
