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

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.session_context.base_session_context import BaseSessionContext
from core.services.skills.base_skill import BaseSkill
from core.config.component_config import ComponentConfig
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()


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
        executor: Any,
        event_bus = None
    ):
        super().__init__(
            name,
            application_context,
            component_config=component_config,
            executor=executor,
            event_bus=event_bus
        )

        # Кэш для скриптов реестра
        self._scripts_registry = None
        # event_bus_logger будет инициализирован в BaseComponent.__init__()

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

        # Проверяем промпт и схемы (без логирования - только ошибки)
        if capability_name not in self.prompts:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Критический промпт {capability_name} не загружен")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                return False

        if capability_name not in self.input_contracts:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Входная схема {capability_name} не загружена")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                return False

        if capability_name not in self.output_contracts:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Выходная схема {capability_name} не загружена")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                return False

        return True

    def _get_event_type_for_success(self) -> EventType:
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
        Реализация бизнес-логики навыка финального ответа (ASYNC).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.

        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: Данные результата (не ExecutionResult!)
        """
        if capability.name != "final_answer.generate":
            raise ValueError(f"Неподдерживаемая capability: {capability.name}")

        # Извлечение контекста сессии
        session_context = execution_context.session_context if hasattr(execution_context, 'session_context') else execution_context

        # Генерация финального ответа (async вызов)
        result = await self._generate_final_answer(session_context, parameters, execution_context)

        # Извлекаем данные из ExecutionResult если нужно
        if isinstance(result, dict):
            return result
        elif hasattr(result, 'data') and result.data:
            return result.data
        
        # ❌ Не возвращаем {} — это маскирует ошибку!
        if self.event_bus_logger:
            await self.event_bus_logger.error(
              # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                "❌ _generate_final_answer вернул ExecutionResult с пустым data. "
                "Это указывает на ошибку генерации финального ответа."
            )
        
        # Возвращаем явный fallback с предупреждением
        return {
            "final_answer": "Не удалось сгенерировать финальный ответ",
            "error": "Пустой результат от _generate_final_answer",
            "warning": "FINAL_ANSWER_GENERATION_FAILED"
        }

    async def _generate_final_answer(
        self,
        context: BaseSessionContext,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> ExecutionResult:
        """
        Генерация финального ответа на основе контекста сессии (ASYNC).

        ПАРАМЕТРЫ:
        - context: контекст сессии (только для get_goal())
        - parameters: параметры генерации
        - execution_context: контекст выполнения для доступа к данным

        ВОЗВРАЩАЕТ:
        - ExecutionResult: результат генерации
        """
        # Извлечение цели
        goal = context.get_goal() or "Не указана цель"

        # Обработка параметров (могут быть Pydantic моделью или dict)
        from pydantic import BaseModel
        if isinstance(parameters, BaseModel):
            # Pydantic модель — используем атрибуты
            include_steps = getattr(parameters, 'include_steps', True)
            include_evidence = getattr(parameters, 'include_evidence', True)
            format_type = getattr(parameters, 'format_type', 'detailed')
            confidence_threshold = getattr(parameters, 'confidence_threshold', 0.7)
            max_sources = getattr(parameters, 'max_sources', 10)
        elif isinstance(parameters, dict):
            # dict — используем .get()
            include_steps = parameters.get("include_steps", True)
            include_evidence = parameters.get("include_evidence", True)
            format_type = parameters.get("format_type", "detailed")
            confidence_threshold = parameters.get("confidence_threshold", 0.7)
            max_sources = parameters.get("max_sources", 10)
        else:
            # Fallback
            include_steps = True
            include_evidence = True
            format_type = "detailed"
            confidence_threshold = 0.7
            max_sources = 10

        # Сбор всей информации из контекста ЧЕРЕЗ EXECUTOR
        observations = []
        thoughts = []
        actions = []

        # Получаем все items из контекста через executor
        try:
            from core.models.data.execution import ExecutionStatus
            import json
            from datetime import date, datetime

            def serialize_for_prompt(obj):
                """Сериализация объекта для промпта — datetime → строки."""
                if isinstance(obj, (date, datetime)):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: serialize_for_prompt(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [serialize_for_prompt(item) for item in obj]
                elif hasattr(obj, 'model_dump'):
                    return serialize_for_prompt(obj.model_dump())
                elif hasattr(obj, 'dict'):
                    return serialize_for_prompt(obj.dict())
                elif hasattr(obj, '__dict__'):
                    return serialize_for_prompt(obj.__dict__)
                else:
                    return obj

            def format_book_data(row):
                """Форматирование данных книги для промпта."""
                if isinstance(row, dict):
                    title = row.get('book_title', row.get('title', 'Без названия'))
                    author = row.get('last_name', row.get('author', 'Без автора'))
                    year = row.get('publication_date', '')
                    if year:
                        year = str(year)[:4]  # Только год
                    return f"'{title}' ({author}, {year})" if year else f"'{title}' ({author})"
                return str(row)

            all_items_result = await self.executor.execute_action(
                action_name="context.get_all_items",
                parameters={},
                context=execution_context
            )

            # DEBUG: check what's in execution_context
            print(f"[DEBUG final_answer] execution_context.session_context={getattr(execution_context, 'session_context', 'None')}")
            if execution_context and hasattr(execution_context, 'session_context') and execution_context.session_context:
                sc = execution_context.session_context
                print(f"[DEBUG final_answer] sc.session_id={getattr(sc, 'session_id', 'unknown')}, items={sc.data_context.count() if hasattr(sc, 'data_context') else 'N/A'}")

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
                        # Сериализуем данные наблюдения в JSON-подобный формат
                        if isinstance(item_content, str):
                            observations.append(item_content)
                        elif isinstance(item_content, dict):
                            # Специальная обработка для book_library.execute_script
                            if 'rows' in item_content and isinstance(item_content['rows'], list):
                                # Форматируем каждую строку как книгу
                                rows = item_content['rows']
                                for row in rows:
                                    formatted = format_book_data(row)
                                    observations.append(formatted)
                            else:
                                # Сериализуем dict/объект с конвертацией datetime → строки
                                serialized = serialize_for_prompt(item_content)
                                if isinstance(serialized, dict):
                                    observations.append(json.dumps(serialized, ensure_ascii=False, indent=1))
                                else:
                                    observations.append(str(serialized))
                        else:
                            observations.append(str(item_content))
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
                self.event_bus_logger.warning(f"Не удалось получить items из контекста: {e}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            # Продолжаем с пустыми списками

        # Получаем шаги выполнения через executor
        steps_taken = []
        try:
            from core.models.data.execution import ExecutionStatus
            import json
            from datetime import date, datetime
            
            def serialize_for_prompt(obj):
                """Сериализация объекта для промпта — datetime → строки."""
                if isinstance(obj, (date, datetime)):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: serialize_for_prompt(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [serialize_for_prompt(item) for item in obj]
                elif hasattr(obj, 'model_dump'):
                    return serialize_for_prompt(obj.model_dump())
                elif hasattr(obj, 'dict'):
                    return serialize_for_prompt(obj.dict())
                elif hasattr(obj, '__dict__'):
                    return serialize_for_prompt(obj.__dict__)
                else:
                    return obj

            steps_result = await self.executor.execute_action(
                action_name="context.get_step_history",
                parameters={},
                context=execution_context
            )

            if steps_result.status == ExecutionStatus.COMPLETED and steps_result.result:
                steps_list = steps_result.result.get("steps", [])
                for step in steps_list[-10:]:  # Последние 10 шагов
                    if isinstance(step, dict):
                        # Извлекаем данные из AgentStep dict (новый формат)
                        capability = step.get("capability_name", "неизвестно")
                        summary = step.get("summary", "")
                        status = step.get("status", "")
                        
                        # Получаем данные наблюдения
                        result_data = step.get("observation", "") or step.get("result", "")
                        
                        steps_taken.append({
                            "action": capability,
                            "summary": summary,
                            "status": status.value if hasattr(status, 'value') else str(status),
                            "result": serialize_for_prompt(result_data) if result_data else ""
                        })
                    else:
                        # Объект AgentStep
                        capability = getattr(step, 'capability_name', 'неизвестно')
                        summary = getattr(step, 'summary', '')
                        status = getattr(step, 'status', '')
                        result_data = getattr(step, 'observation', '') or getattr(step, 'result', '')
                        
                        steps_taken.append({
                            "action": capability,
                            "summary": summary,
                            "status": status.value if hasattr(status, 'value') else str(status),
                            "result": serialize_for_prompt(result_data) if result_data else ""
                        })
        except Exception as e:
            if self.event_bus_logger:
                self.event_bus_logger.warning(f"Не удалось получить step history: {e}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            # Продолжаем с пустыми шагами

        # Получение промпта из кэша (через BaseComponent.get_prompt)
        capability_name = "final_answer.generate"
        prompt_obj = self.get_prompt(capability_name)

        if not prompt_obj:
            if self.event_bus_logger:
                self.event_bus_logger.error(f"Промпт для {capability_name} не найден в кэше")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return self._build_fallback_response(goal, observations, steps_taken, format_type)

        # Рендеринг промпта с переменными (используем метод из BaseComponent)
        try:
            # Преобразуем списки в строки для рендеринга промпта
            observations_str = "\n".join([f"{i}. {obs}" for i, obs in enumerate(observations[-max_sources:], 1)]) if observations else "Наблюдения отсутствуют."
            steps_str = "\n".join([f"{i}. {step.get('action', 'неизвестно')}" for i, step in enumerate(steps_taken[-10:], 1)]) if steps_taken else "Шаги не выполнены."

            # Преобразуем булевы значения в строки
            format_type_str = str(format_type)
            include_steps_str = str(include_steps).lower()
            include_evidence_str = str(include_evidence).lower()

            rendered_prompt = self.render_prompt(
                capability_name,
                goal=goal,
                observations=observations_str,
                steps_taken=steps_str,
                format_type=format_type_str,
                include_steps=include_steps_str,
                include_evidence=include_evidence_str
            )
        except Exception as e:
            if self.event_bus_logger:
                self.event_bus_logger.warning(f"Ошибка рендеринга промпта: {e}, используем fallback")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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
        # Увеличенный timeout для сложных запросов (600 секунд = 10 минут)
        try:
            # Получаем схему выхода для structured output
            output_schema = self.get_output_contract("final_answer.generate")

            if self.event_bus_logger:
                await self.event_bus_logger.info(f"FinalAnswerSkill: генерация ответа | observations={len(observations)}, steps={len(steps_taken)}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

            # Вызов LLM С STRUCTURED OUTPUT через executor (напрямую, без _call_llm)
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": rendered_prompt,
                    "structured_output": {
                        "output_model": "final_answer.generate.output",
                        "schema_def": output_schema if output_schema else {},
                        "max_retries": 2,  # Уменьшим количество попыток
                        "strict_mode": True
                    },
                    "temperature": 0.1,  # Низкая температура для точности
                    "max_tokens": 1500,
                    "total_timeout": 600.0,  # Общий timeout на все попытки (10 минут)
                    "attempt_timeout": 300.0  # Timeout на одну попытку (5 минут)
                },
                context=execution_context
            )

            # Проверка на ошибку
            from core.models.data.execution import ExecutionStatus
            if llm_result.status != ExecutionStatus.COMPLETED:
                error_msg = llm_result.error
                if self.event_bus_logger:
                    self.event_bus_logger.error(f"LLM structured output ошибка: {error_msg}")
                      # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                raise RuntimeError(f"Ошибка LLM: {error_msg}")

            # Получаем структурированные данные
            llm_result_data = llm_result.data
            
            # Пытаемся извлечь parsed_content
            if hasattr(llm_result_data, 'parsed_content'):
                parsed_response = llm_result_data.parsed_content
            elif isinstance(llm_result_data, dict):
                # Если есть ключ 'parsed_content' - используем его
                if "parsed_content" in llm_result_data:
                    parsed_response = llm_result_data.get("parsed_content", {})
                else:
                    # Данные уже в корне dict - используем сам dict
                    parsed_response = llm_result_data
            else:
                parsed_response = llm_result_data if llm_result_data else {}

            # Логирование успешного structured output
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Финальный ответ сгенерирован с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
                )

            # Формирование финального результата
            # ✅ ИСПРАВЛЕНО: Работаем с Pydantic моделью или dict
            from pydantic import BaseModel
            if isinstance(parsed_response, BaseModel):
                # Pydantic модель — используем атрибуты согласно контракту
                final_answer_val = getattr(parsed_response, 'final_answer', '')
                confidence_val = getattr(parsed_response, 'confidence_score', 0.8)
                sources_val = getattr(parsed_response, 'sources', [])
                summary_val = getattr(parsed_response, 'summary_of_steps', '')
                remaining_questions_val = getattr(parsed_response, 'remaining_questions', [])
                metadata_val = getattr(parsed_response, 'metadata', {})
            else:
                # dict — используем .get() согласно контракту
                final_answer_val = parsed_response.get("final_answer", "")
                confidence_val = parsed_response.get("confidence_score", 0.8)
                sources_val = parsed_response.get("sources", [])
                summary_val = parsed_response.get("summary_of_steps", "")
                remaining_questions_val = parsed_response.get("remaining_questions", [])
                metadata_val = parsed_response.get("metadata", {})

            # 🔧 FALLBACK: Если final_answer пустой, но sources есть — генерируем ответ
            if not final_answer_val and sources_val:
                if self.event_bus_logger:
                    await self.event_bus_logger.debug(f"FALLBACK: final_answer пустой, sources={len(sources_val)}")
                # Извлекаем названия книг из sources
                book_titles = []
                for source in sources_val:
                    # Формат: "'Название' (Автор, Год)" или просто "Название"
                    if isinstance(source, str) and source.startswith("'") and ")" in source:
                        # Извлекаем название между кавычками
                        end_quote = source.find("'", 1)
                        if end_quote > 0:
                            book_titles.append(source[1:end_quote])
                    elif source:
                        book_titles.append(str(source))
                
                # Генерируем ответ из списка книг
                if book_titles:
                    count = len(book_titles)
                    count_word = self._declension(count, ['книга', 'книги', 'книг'])
                    final_answer_val = f"Найдено {count} {count_word}: {', '.join(book_titles)}."
                    if self.event_bus_logger:
                        await self.event_bus_logger.info(f"FALLBACK: сгенерирован ответ: {final_answer_val[:100]}")
            elif not final_answer_val:
                if self.event_bus_logger:
                    await self.event_bus_logger.warning(f"FALLBACK: final_answer пустой, sources={sources_val}")

            result_data = {
                "final_answer": final_answer_val,
                "sources": sources_val if sources_val else (observations[-max_sources:] if include_evidence else []),
                "confidence_score": confidence_val,
                "remaining_questions": remaining_questions_val,
                "summary_of_steps": summary_val if summary_val else (self._build_steps_summary(steps_taken) if include_steps else ""),
                "metadata": {
                    **metadata_val,
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
                self.event_bus_logger.error(f"Ошибка вызова LLM: {str(e)}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            # ❌ УДАЛЕНО: Fallback ответ при ошибке генерации
            # ✅ ТЕПЕРЬ: Выбрасываем SkillExecutionError
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Не удалось сгенерировать финальный ответ: {str(e)}. "
                f"Проверьте что LLM провайдер доступен и промпт загружен.",
                component="final_answer"
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
        # Преобразуем списки в строки
        observations_str = "\n".join([f"{i}. {obs[:300]}" for i, obs in enumerate(observations[-max_sources:], 1)]) if observations else "Наблюдения отсутствуют."
        
        steps_parts = []
        if steps_taken:
            for i, step in enumerate(steps_taken[-10:], 1):
                summary = step.get('summary', '')
                if summary:
                    steps_parts.append(f"{i}. {summary}")
                else:
                    action = step.get('action', 'неизвестно')
                    result_part = f" → {step.get('result', '')[:100]}" if step.get('result') else ""
                    steps_parts.append(f"{i}. {action}{result_part}")
        steps_str = "\n".join(steps_parts) if steps_parts else "Шаги не выполнены."
        
        prompt_parts = [
            "Ты — интеллектуальный ассистент, который генерирует финальный ответ на основе всего контекста сессии.",
            f"\n## Исходная цель\n{goal}",
            f"\n## Собранная информация (наблюдения)\n{observations_str}",
            f"\n## Выполненные шаги\n{steps_str}",
            f"\n## Требования к ответу",
            f"- **Формат вывода**: {format_type}",
            f"- **Включать шаги выполнения**: {include_steps}",
            f"- **Включать источники (доказательства)**: {include_evidence}",
            f"\nСгенерируй финальный ответ согласно требованиям."
        ]

        return "\n".join(prompt_parts)

    def _declension(self, number: int, words: List[str]) -> str:
        """
        Склонение слов по числу (для русского языка).
        
        ARGS:
        - number: число
        - words: три формы слова [один, два, пять] например ['книга', 'книги', 'книг']
        
        RETURNS:
        - Правильная форма слова
        """
        cases = [2, 0, 1, 1, 1, 2]
        if number % 100 in [11, 12, 13, 14]:
            return words[2]
        return words[cases[number % 10]]

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
            # Используем summary если есть, иначе формируем из action + result
            summary = step.get('summary', '')
            if summary:
                summary_parts.append(f"{i}. {summary}")
            else:
                action = step.get('action', 'неизвестно')
                result_part = f" → {step.get('result', '')[:100]}" if step.get('result') else ""
                summary_parts.append(f"{i}. {action}{result_part}")

        return "\n".join(summary_parts)

    # ❌ УДАЛЕНО: _build_fallback_response
    # ✅ ТЕПЕРЬ: Выбрасываем SkillExecutionError вместо fallback ответа

