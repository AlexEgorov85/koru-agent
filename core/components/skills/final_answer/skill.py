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
from core.components.skills.skill import Skill
from core.config.component_config import ComponentConfig
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.infrastructure.logging.event_types import LogEventType


class FinalAnswerSkill(Skill):
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

    @property
    def description(self) -> str:
        return "Навык генерации финального ответа на основе контекста сессии"

    name = "final_answer"
    supported_strategies = ["react", "planning", "evaluation", "plan_and_execute", "chain_of_thought"]

    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor: Any,
        application_context: Any = None,
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )

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
                visiable=False,
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
            self._log_error(f"Критический промпт {capability_name} не загружен", event_type=LogEventType.ERROR)
            return False

        if capability_name not in self.input_contracts:
            self._log_error(f"Входная схема {capability_name} не загружена", event_type=LogEventType.ERROR)
            return False

        if capability_name not in self.output_contracts:
            self._log_error(f"Выходная схема {capability_name} не загружена", event_type=LogEventType.ERROR)
            return False

        return True

    def _get_event_type_for_success(self) -> str:
        """Возвращает тип события для успешного выполнения навыка финального ответа."""
        return "skill.final_answer.executed"

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

        # Извлечение контекста сессии с защитой от неправильных типов
        raw_session_context = execution_context.session_context if hasattr(execution_context, 'session_context') else execution_context
        # Проверяем что это действительно SessionContext
        from core.session_context.session_context import SessionContext
        if isinstance(raw_session_context, SessionContext):
            session_context = raw_session_context
        elif hasattr(raw_session_context, 'session_context'):
            # Вложенный ExecutionContext - извлекаем дальше
            session_context = getattr(raw_session_context, 'session_context', raw_session_context)
        else:
            session_context = raw_session_context

        # Генерация финального ответа (async вызов)
        result = await self._generate_final_answer(session_context, parameters, execution_context)

        # Извлекаем данные из ExecutionResult если нужно
        if isinstance(result, dict):
            return result
        elif hasattr(result, 'data') and result.data:
            return result.data
        
        # ❌ Не возвращаем {} — это маскирует ошибку!
        self._log_error(
            "❌ _generate_final_answer вернул ExecutionResult с пустым data. "
            "Это указывает на ошибку генерации финального ответа.",
            event_type=LogEventType.ERROR
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
        # Извлечение цели с защитой
        from core.session_context.session_context import SessionContext
        raw_context = context.session_context if hasattr(context, 'session_context') else context
        if isinstance(raw_context, SessionContext):
            session_context = raw_context
        elif hasattr(raw_context, 'session_context'):
            session_context = getattr(raw_context, 'session_context', raw_context)
        else:
            session_context = raw_context
        goal = session_context.get_goal() if session_context and hasattr(session_context, 'get_goal') else "Не указана цель"

        # Получаем историю диалога из session_context (если доступна)
        dialogue_history_str = ""
        if session_context and hasattr(session_context, 'dialogue_history'):
            dialogue_history_str = session_context.dialogue_history.format_for_prompt()
            if dialogue_history_str:
                self._log_debug(
                    f"[DEBUG final_answer] dialogue_history загружен: {len(dialogue_history_str)} символов",
                    event_type=LogEventType.DEBUG
                )
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
            from core.agent.components.action_executor import ExecutionContext as ExecCtx
            from core.session_context.session_context import SessionContext as SessCtx
            sc = getattr(execution_context, 'session_context', None)
            debug_msg = f"[DEBUG final_answer] session_context type: {type(sc).__name__ if sc else 'None'}"
            if sc is None:
                debug_msg += " - IS NONE"
            elif isinstance(sc, ExecCtx):
                debug_msg += " - IS NESTED ExecutionContext!"
            self._log_debug(debug_msg, event_type=LogEventType.DEBUG)
            if execution_context and hasattr(execution_context, 'session_context') and execution_context.session_context:
                sc = execution_context.session_context
                self._log_debug(
                    f"session_id={getattr(sc, 'session_id', 'unknown')}, "
                    f"items={sc.data_context.count() if hasattr(sc, 'data_context') else 'N/A'}"
                )
            if all_items_result.status == ExecutionStatus.COMPLETED and all_items_result.data:
                all_items = all_items_result.data.get("items", {})
                
                self._log_info(f"[DEBUG] all_items count: {len(all_items)}, items: {list(all_items.keys())}", event_type=LogEventType.DEBUG)

                # Классификация элементов контекста
                for item_id, item in all_items.items():
                    # item может быть dict или объектом ContextItem
                    if isinstance(item, dict):
                        item_type_raw = item.get("item_type", "")
                        item_content = item.get("content", {})
                    else:
                        # Это объект ContextItem
                        item_type_raw = item.item_type
                        item_content = item.content
                    
                    # Нормализация item_type до строки
                    if hasattr(item_type_raw, 'value'):
                        # Это Enum (ContextItemType)
                        item_type = item_type_raw.value
                    elif isinstance(item_type_raw, str):
                        item_type = item_type_raw
                    else:
                        item_type = str(item_type_raw)
                    
                    self._log_info(f"[DEBUG] item_id={item_id}, item_type={item_type}, is_OBSERVATION: {item_type == 'OBSERVATION'}", event_type=LogEventType.DEBUG)

                    if item_type == "OBSERVATION":
                        # Используем content напрямую - там ВСЕ данные!
                        if isinstance(item_content, str):
                            observations.append(item_content)
                        elif isinstance(item_content, dict):
                            # Если это наш формат observation с данными - используем данные
                            if "data" in item_content:
                                rows = item_content.get("data", [])
                                if rows:
                                    from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
                                    # Форматируем в Markdown таблицу
                                    md_table = BaseBehaviorPattern(None)._format_table_markdown(rows, 10)
                                    if md_table:
                                        observations.append(f"📊 Данные ({len(rows)} строк):\n{md_table}")
                                    else:
                                        observations.append(json.dumps(rows[:5], ensure_ascii=False))
                                observations.append(f"answer: {item_content.get('answer', 'n/a')}")
                            # Проверяем новый формат observation
                            elif "type" in item_content and item_content.get("type") in ("raw_data", "summary"):
                                from core.components.skills.utils.observation_formatter import ObservationFormatter
                                obs_type = item_content.get("type")
                                if obs_type == "raw_data" and "data" in item_content:
                                    rows = item_content["data"]
                                    from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
                                    md_table = BaseBehaviorPattern(None)._format_table_markdown(rows, 10)
                                    if md_table:
                                        observations.append(f"📊 raw_data ({len(rows)} строк):\n{md_table}")
                                else:
                                    observations.append(ObservationFormatter.render_for_prompt(item_content))
                            else:
                                serialized = serialize_for_prompt(item_content)
                                if isinstance(serialized, dict):
                                    observations.append(json.dumps(serialized, ensure_ascii=False, indent=1))
                                else:
                                    observations.append(str(serialized))
                        elif hasattr(item_content, 'model_dump'):
                            content_dict = serialize_for_prompt(item_content)
                            if isinstance(content_dict, dict):
                                observations.append(json.dumps(content_dict, ensure_ascii=False, indent=1))
                            else:
                                observations.append(str(content_dict))
                        else:
                            observations.append(str(item_content))
                    elif item_type in ["THOUGHT", "DECISION"]:
                        thoughts.append(item_content if isinstance(item_content, str) else str(item_content))
                    elif item_type == "ACTION":
                        if isinstance(item_content, dict):
                            actions.append({
                                "action": item_content.get("capability", "неизвестно"),
                                "result": str(item_content.get("result", "")) if item_content.get("result") else ""
                            })
        except Exception as e:
            self._log_warning(f"Не удалось получить items из контекста: {e}", event_type=LogEventType.WARNING)
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
                        parameters = step.get("parameters", {})

                        # Получаем данные наблюдения (observation содержит сырые данные)
                        result_data = step.get("observation", "")

                        step_entry = {
                            "action": capability,
                            "summary": summary,
                            "status": status.value if hasattr(status, 'value') else str(status),
                            "result": serialize_for_prompt(result_data) if result_data else ""
                        }

                        # Добавляем параметры если есть
                        if parameters:
                            step_entry["parameters"] = serialize_for_prompt(parameters)

                        steps_taken.append(step_entry)
                    else:
                        # Объект AgentStep
                        capability = getattr(step, 'capability_name', 'неизвестно')
                        summary = getattr(step, 'summary', '')
                        status = getattr(step, 'status', '')
                        parameters = getattr(step, 'parameters', {})
                        result_data = getattr(step, 'observation', '')

                        step_entry = {
                            "action": capability,
                            "summary": summary,
                            "status": status.value if hasattr(status, 'value') else str(status),
                            "result": serialize_for_prompt(result_data) if result_data else ""
                        }

                        # Добавляем параметры если есть
                        if parameters:
                            step_entry["parameters"] = serialize_for_prompt(parameters)

                        steps_taken.append(step_entry)
        except Exception as e:
            self._log_warning(f"Не удалось получить step history: {e}", event_type=LogEventType.WARNING)
            # Продолжаем с пустыми шагами

        # Получение промпта из кэша (через BaseComponent.get_prompt)
        capability_name = "final_answer.generate"
        prompt_obj = self.get_prompt(capability_name)

        # Загрузка системного промпта
        system_prompt_obj = self.get_prompt("final_answer.generate.system")

        # DEBUG: Проверяем что загруено в компонент
        all_prompt_keys = list(self.prompts.keys())
        self._log_debug(
            f"[DEBUG final_answer] Загруженные промпты: {all_prompt_keys}",
            event_type=LogEventType.DEBUG
        )
        self._log_debug(
            f"[DEBUG final_answer] prompt_obj: {'НАЙДЕН' if prompt_obj else 'НЕ НАЙДЕН'}",
            event_type=LogEventType.DEBUG
        )
        self._log_debug(
            f"[DEBUG final_answer] system_prompt_obj: {'НАЙДЕН' if system_prompt_obj else 'НЕ НАЙДЕН'}",
            event_type=LogEventType.DEBUG
        )
        if system_prompt_obj:
            self._log_debug(
                f"[DEBUG final_answer] system_prompt_obj.content (первые 100 символов): {system_prompt_obj.content}...",
                event_type=LogEventType.DEBUG
            )
        else:
            self._log_warning(
                "[DEBUG final_answer] СИСТЕМНЫЙ ПРОМПТ НЕ ЗАГРУЖЕН!",
                event_type=LogEventType.WARNING
            )
        if not prompt_obj:
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Промпт для {capability_name} не загружен! Проверьте YAML в data/prompts/skill/final_answer/",
                component="final_answer"
            )

        # Формирование строковых переменных для промпта
        observations_str = "\n".join(observations) if observations else "Нет наблюдений"
        steps_str = "\n".join([f"- {s['action']}: {s['status']}" for s in steps_taken]) if steps_taken else "Шаги не выполнены"
        format_type_str = str(format_type)
        include_steps_str = str(include_steps)
        include_evidence_str = str(include_evidence)

        # Рендеринг промпта с переменными
        prompt_obj = self.get_prompt(capability_name)
        if not prompt_obj or not hasattr(prompt_obj, 'content'):
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Промпт для {capability_name} не загружен! Проверьте YAML в data/prompts/skill/final_answer/",
                component="final_answer"
            )
        
        prompt_template = prompt_obj.content
        prompt_vars = {
            "goal": goal,
            "dialogue_history": dialogue_history_str,
            "observations": observations_str,
            "steps_taken": steps_str,
            "format_type": format_type_str,
            "include_steps": include_steps_str,
            "include_evidence": include_evidence_str
        }
        
        try:
            rendered_prompt = self._render_prompt(prompt_template, prompt_vars)
        except Exception as e:
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Ошибка рендеринга промпта {capability_name}: {e}",
                component="final_answer"
            )

        # Вызов LLM для генерации ответа С STRUCTURED OUTPUT
        # Увеличенный timeout для сложных запросов (600 секунд = 10 минут)
        try:
            # Получаем схему выхода для structured output
            output_schema = self.get_output_contract("final_answer.generate")

            self._log_info(f"FinalAnswerSkill: генерация ответа | observations={len(observations)}, steps={len(steps_taken)}", event_type=LogEventType.INFO)

            # Вызов LLM С STRUCTURED OUTPUT через executor (напрямую, без _call_llm)
            # Используем системный промпт из файла
            if system_prompt_obj and system_prompt_obj.content:
                system_prompt = system_prompt_obj.content
                self._log_info(
                        f"[DEBUG final_answer] ИСПОЛЬЗУЕТСЯ системный промпт из файла (длина: {len(system_prompt)})",
                        event_type=LogEventType.INFO
                    )
            else:
                import json
                system_prompt = (
                    "Ты — интеллектуальный ассистент. Верни ответ СТРОГО в формате JSON согласно схеме ниже.\n"
                    "Никакого текста до или после JSON.\n"
                    f"Ожидаемая схема: {json.dumps(output_schema, ensure_ascii=False, indent=2) if output_schema else '{}'}"
                )
                self._log_warning(
                        f"[DEBUG final_answer] ИСПОЛЬЗУЕТСЯ FALLBACK системный промпт! "
                        f"system_prompt_obj={system_prompt_obj}, "
                        f"has_content={bool(system_prompt_obj and system_prompt_obj.content)}",
                        event_type=LogEventType.WARNING
                    )
            self._log_debug(
                    f"[DEBUG final_answer] system_prompt передаётся в LLM (первые 100 символов): {system_prompt}...",
                    event_type=LogEventType.DEBUG
                )
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": rendered_prompt,
                    "system_prompt": system_prompt,
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
                self._log_error(f"LLM structured output ошибка: {error_msg}", event_type=LogEventType.ERROR)
                raise RuntimeError(f"Ошибка LLM: {error_msg}")

            # Получаем структурированные данные
            llm_result_data = llm_result.data
            
            # Пытаемся извлечь parsed_content
            if llm_result_data is None:
                parsed_response = {}
            elif hasattr(llm_result_data, 'parsed_content'):
                parsed_response = llm_result_data.parsed_content
            elif isinstance(llm_result_data, dict):
                if "parsed_content" in llm_result_data:
                    parsed_response = llm_result_data.get("parsed_content", {})
                else:
                    parsed_response = llm_result_data
            else:
                parsed_response = llm_result_data if llm_result_data else {}

            # Логирование успешного structured output
            self._log_info(
                    f"Финальный ответ сгенерирован с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})",
                    event_type=LogEventType.INFO
                )

            # Формирование финального результата через динамическую Pydantic модель из контракта
            from pydantic import BaseModel
            output_schema = self.get_output_contract("final_answer.generate")
            
            if isinstance(parsed_response, BaseModel):
                final_answer_val = getattr(parsed_response, 'final_answer', '')
                confidence_val = getattr(parsed_response, 'confidence_score', 0.8)
                sources_val = getattr(parsed_response, 'sources', [])
                summary_val = getattr(parsed_response, 'summary_of_steps', '')
                remaining_questions_val = getattr(parsed_response, 'remaining_questions', [])
            else:
                final_answer_val = parsed_response.get("final_answer", "")
                confidence_val = parsed_response.get("confidence_score", 0.8)
                sources_val = parsed_response.get("sources", [])
                summary_val = parsed_response.get("summary_of_steps", "")
                remaining_questions_val = parsed_response.get("remaining_questions", [])

            # 🔧 FALLBACK: Если final_answer пустой, но sources есть — генерируем ответ
            if not final_answer_val and sources_val:
                self._log_debug(f"FALLBACK: final_answer пустой, sources={len(sources_val)}", event_type=LogEventType.DEBUG)
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
                    self._log_info(f"FALLBACK: сгенерирован ответ: {final_answer_val}", event_type=LogEventType.INFO)
            elif not final_answer_val:
                self._log_warning(f"FALLBACK: final_answer пустой, sources={sources_val}", event_type=LogEventType.WARNING)
            # Формируем результат через динамическую Pydantic модель из контракта
            result_dict = {
                "final_answer": final_answer_val,
                "sources": sources_val if sources_val else (observations[-max_sources:] if include_evidence else []),
                "confidence_score": confidence_val,
                "remaining_questions": remaining_questions_val,
                "summary_of_steps": summary_val if summary_val else (self._build_steps_summary(steps_taken) if include_steps else ""),
                "metadata": {
                    "total_observations": len(observations),
                    "total_steps": len(steps_taken),
                    "generation_time_ms": 0,
                    "format_type": format_type
                }
            }
            
            if output_schema and output_schema != BaseModel:
                try:
                    result_data = output_schema(**result_dict)
                except Exception as e:
                    self._log_warning(f"Ошибка создания Pydantic модели: {e}, используем dict", event_type=LogEventType.WARNING)
                    result_data = result_dict
            else:
                result_data = result_dict

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
            self._log_error(f"Ошибка вызова LLM: {str(e)}", event_type=LogEventType.ERROR)
            # ❌ УДАЛЕНО: Fallback ответ при ошибке генерации
            # ✅ ТЕПЕРЬ: Выбрасываем SkillExecutionError
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Не удалось сгенерировать финальный ответ: {str(e)}. "
                f"Проверьте что LLM провайдер доступен и промпт загружен.",
                component="final_answer"
            )

    # ❌ УДАЛЕНО: _render_prompt_fallback — теперь выбрасываем SkillExecutionError
    # ❌ УДАЛЕНО: _build_fallback_response

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
                result_part = f" → {step.get('result', '')}" if step.get('result') else ""
                summary_parts.append(f"{i}. {action}{result_part}")

        return "\n".join(summary_parts)

    # ❌ УДАЛЕНО: _build_fallback_response
    # ✅ ТЕПЕРЬ: Выбрасываем SkillExecutionError вместо fallback ответа

    def _render_prompt(self, prompt: str, variables: Dict[str, Any]) -> str:
        """Рендеринг промпта с подстановкой переменных.

        СТАНДАРТ: {key} (одинарные скобки) — единообразно с base_behavior_pattern.
        """
        import re
        result = prompt
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            if isinstance(value, list):
                formatted = "\n\n".join(str(v) for v in value)
                result = result.replace("{% if " + key + " %}" + placeholder + "{% endif %}", formatted)
                result = result.replace(placeholder, formatted)
            elif isinstance(value, dict):
                formatted = "\n".join(f"{k}: {v}" for k, v in value.items())
                result = result.replace(placeholder, formatted)
            else:
                result = result.replace(placeholder, str(value))

        result = re.sub(r'\{%.*?%\}', '', result)
        return result

