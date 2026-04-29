"""
Базовый класс для всех паттернов поведения (Behavior Patterns).

АРХИТЕКТУРА:
- Наследуется от Component для единого интерфейса
- Использует методы Component.get_prompt/get_input_contract/get_output_contract
- Все паттерны (ReAct, Planning, Evaluation, Fallback) наследуются от этого класса
- Предоставляет общие сервисы: PromptBuilderService, CapabilityResolverService
- Логирование через стандартный logging + EventType (НЕ через EventBus)
"""

import json
import logging
import typing
from typing import Dict, Any, Optional, List, Type

from pydantic import BaseModel

from core.agent.behaviors.base import BehaviorPatternInterface, Decision, DecisionType
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.models.data.prompt import Prompt
from core.session_context.session_context import SessionContext
from core.components.component import Component
from core.config.component_config import ComponentConfig
from core.utils.async_utils import safe_async_call


# ============================================================================
# ОБЩИЕ СЕРВИСЫ ДЛЯ ВСЕХ ПАТТЕРНОВ
# ============================================================================


class PromptContextBuilder:
    """Собирает контекст промпта из состояния сессии и последних шагов."""

    def __init__(self, prompt_builder: "PromptBuilderService"):
        self._prompt_builder = prompt_builder

    def build_input_context(
        self, context_analysis: Dict[str, Any], available_capabilities: List[Capability]
    ) -> str:
        """Сформировать секцию input для рассуждающего промпта."""
        return self._prompt_builder._build_input_context(
            context_analysis, available_capabilities
        )

    def build_dialogue_history(self, session_context: Optional[SessionContext]) -> str:
        """Сформировать секцию истории диалога."""
        return self._prompt_builder._build_dialogue_history(session_context)


class ObservationFormatter:
    """Форматирует наблюдения и историю шагов для промпта."""

    def __init__(self, prompt_builder: "PromptBuilderService"):
        self._prompt_builder = prompt_builder

    def build_step_history(self, last_steps: list, session_context=None) -> str:
        """Сформировать человекочитаемую историю шагов."""
        return self._prompt_builder._build_step_history(last_steps, session_context)


class CapabilityResolver:
    """Разрешает и форматирует capability-контекст для LLM."""

    def __init__(self, prompt_builder: "PromptBuilderService"):
        self._prompt_builder = prompt_builder

    def filter_capabilities(
        self, capabilities: List[Capability], pattern_id: str
    ) -> List[Capability]:
        """Отфильтровать capability по поддерживаемым стратегиям паттерна."""
        return self._prompt_builder._filter_capabilities(capabilities, pattern_id)

    def format_available_tools_with_params(
        self,
        available_capabilities: List[Capability],
        schema_validator: Optional[Any] = None,
        application_context=None,
    ) -> str:
        """Сформировать markdown-контекст инструментов с параметрами."""
        return self._prompt_builder._format_available_tools_with_params(
            available_capabilities,
            schema_validator,
            application_context,
        )


class PromptBuilderService:
    """Сервис для построения структурированных промптов."""

    # НАСТРАИВАЕМЫЕ ЛИМИТЫ ДЛЯ ОБРАБОТКИ ДАННЫХ
    DATA_SIZE_LIMITS = {
        "small": 50,  # Показываем полностью
        "medium": 500,  # Суммаризация + примеры
        "large": 1000,  # Только статистика
        "huge": 5000,  # Требуется data_analysis skill
    }

    DISPLAY_LIMITS = {
        "max_rows_display": 20,
        "max_chars_display": 1000,
    }

    def __init__(self):
        self.prompt_context_builder = PromptContextBuilder(self)
        self.observation_formatter = ObservationFormatter(self)
        self.capability_resolver = CapabilityResolver(self)

    def build_reasoning_prompt(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        templates: Dict[str, str],
        schema_validator: Optional[Any] = None,
        session_context=None,
        pattern_id: str = "react",
        application_context=None,
    ) -> str:
        """Строит полный промпт для рассуждения."""
        # Фильтруем capability по supported_strategies
        # Если вызывается на PromptBuilderService, используем available_capabilities напрямую
        filtered_caps = self.capability_resolver.filter_capabilities(
            available_capabilities, pattern_id
        )

        # Форматируем инструменты с параметрами - передаём application_context для доступа к контрактам
        tools_str = self.capability_resolver.format_available_tools_with_params(
            filtered_caps, schema_validator, application_context
        )

        variables = {
            "input": self.prompt_context_builder.build_input_context(
                context_analysis, filtered_caps
            ),
            "goal": context_analysis.get("goal", "Неизвестная цель"),
            "dialogue_history": self.prompt_context_builder.build_dialogue_history(
                session_context
            ),
            "step_history": self.observation_formatter.build_step_history(
                context_analysis.get("last_steps", []), session_context=session_context
            ),
            "available_tools": tools_str,
            "no_progress_steps": context_analysis.get("no_progress_steps", 0),
            "consecutive_errors": context_analysis.get("consecutive_errors", 0),
            "exploration_rules": self._build_exploration_rules(session_context),
        }
        return self._render_prompt(templates.get("user", ""), variables)

    def _format_tools_fallback(
        self,
        available_capabilities: List[Capability],
        schema_validator: Optional[Any] = None,
    ) -> str:
        """Fallback форматирование без параметров."""
        lines = []
        for cap in available_capabilities:
            name = cap.name if hasattr(cap, "name") else cap.get("name", "unknown")
            description = (
                cap.description
                if hasattr(cap, "description")
                else cap.get("description", "no description")
            )
            lines.append(f"- {name}: {description}")
        return "\n".join(lines)

    def _build_input_context(
        self, context_analysis: Dict[str, Any], available_capabilities: List[Capability]
    ) -> str:
        """Формирует секцию {input} для промпта - только мета-информация, без деталей шагов."""
        goal = context_analysis.get("goal", "Неизвестная цель")
        last_steps = context_analysis.get("last_steps", [])
        parts = [
            f"ЦЕЛЬ: {goal}",
            f"Шагов выполнено: {len(last_steps)}",
            f"Шагов без прогресса: {context_analysis.get('no_progress_steps', 0)}",
            f"Ошибок подряд: {context_analysis.get('consecutive_errors', 0)}",
            f"Ошибки state (последние): {context_analysis.get('state_errors', [])}",
            f"Пустых результатов: {context_analysis.get('empty_results_count', 0)}",
            f"Повторов действий: {context_analysis.get('repeated_actions_count', 0)}",
            f"Последнее наблюдение: {context_analysis.get('last_observation')}",
            self._build_adaptive_hints(context_analysis),
        ]
        return "\n".join(part for part in parts if part)

    def _build_adaptive_hints(self, context_analysis: Dict[str, Any]) -> str:
        """Собрать адаптивные подсказки для рассуждения на основе состояния сессии."""
        hints = []

        empty_results_count = context_analysis.get("empty_results_count", 0)
        if empty_results_count >= 1:
            hints.append(
                "- При пустом результате смени стратегию: уточни параметры или выбери другой инструмент."
            )

        repeated_actions_count = context_analysis.get("repeated_actions_count", 0)
        if repeated_actions_count >= 1:
            hints.append(
                "- Не повторяй недавнее действие с теми же параметрами без явной причины."
            )

        state_errors = context_analysis.get("state_errors", [])
        if state_errors:
            hints.append(
                f"- Учти последнюю ошибку state: {state_errors[-1]} и предложи обходной шаг."
            )

        last_observation = context_analysis.get("last_observation")
        if isinstance(last_observation, dict):
            observation_status = str(last_observation.get("status", "")).lower()
            if observation_status == "error":
                hints.append(
                    "- Последнее наблюдение содержит ошибку: проверь входные данные и выбери более безопасный шаг."
                )
            elif observation_status == "empty":
                hints.append(
                    "- Последнее наблюдение пустое: расширь поиск или измени источник данных."
                )

            observation_issues = last_observation.get("issues", [])
            if "sql_filter_mismatch" in observation_issues:
                hints.append(
                    "- Пустой SQL-результат: проверь селективность фильтров через GROUP BY/COUNT "
                    "и убедись, что значения фильтров реально присутствуют в БД."
                )
            if "sql_year_filter_mismatch" in observation_issues:
                hints.append(
                    "- Пустой SQL-результат по году: сначала проверь, за какие годы есть данные (SELECT DISTINCT year ...), "
                    "после этого скорректируй фильтр."
                )

        if not hints:
            return "АДАПТИВНЫЕ ПОДСКАЗКИ: стандартный режим рассуждения."

        hints_block = ["АДАПТИВНЫЕ ПОДСКАЗКИ:"]
        hints_block.extend(hints)
        return "\n".join(hints_block)

    def _build_dialogue_history(self, session_context) -> str:
        """
        Формирует блок истории диалога для вставки в промпт.

        ПАРАМЕТРЫ:
        - session_context: контекст сессии

        ВОЗВРАЩАЕТ:
        - str: отформатированная история диалога или пустая строка
        """
        if session_context and hasattr(session_context, "dialogue_history"):
            return session_context.dialogue_history.format_for_prompt()
        return ""

    def _format_table_markdown(self, rows: list, max_rows: int = 5) -> str:
        """Формирует Markdown таблицу из списка dict."""
        if not rows or not isinstance(rows, list):
            return ""

        if not rows or not isinstance(rows[0], dict):
            return str(rows)

        columns = list(rows[0].keys())

        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"

        table_rows = []
        for row in rows:
            values = []
            for col in columns:
                val = row.get(col, "")
                val_str = str(val).replace("|", "\\|")
                values.append(val_str)
            table_rows.append("| " + " | ".join(values) + " |")

        lines = [header, separator] + table_rows

        return "\n".join(lines)

    def _build_step_history(self, last_steps: list, session_context=None) -> str:
        """
        Формирует историю шагов в формате: Мысль → Действие → Параметры → Наблюдение.

        АРХИТЕКТУРА:
        - Нормализует все шаги в словари для единообразной обработки
        - Обрабатывает AgentStep объекты и словари
        - Без обращения к data_context
        """
        if not last_steps:
            return "Шаги не выполнены"

        lines = ["\n"]

        for i, step in enumerate(last_steps, 1):
            # Нормализация шага в словарь
            if isinstance(step, dict):
                step_dict = step
            elif hasattr(step, "capability_name"):  # AgentStep объект
                step_dict = {
                    "capability_name": getattr(step, "capability_name", "unknown"),
                    "summary": getattr(step, "summary", "") or "",
                    "status": (
                        step.status.value
                        if hasattr(step, "status") and hasattr(step.status, "value")
                        else str(getattr(step, "status", "unknown"))
                    ),
                    "parameters": getattr(step, "parameters", None) or {},
                    "obs_text": getattr(step, "obs_text", "Нет данных"),
                    "step_number": getattr(step, "step_number", getattr(step, "step", None)),
                }
            else:
                lines.append(f"[ШАГ {i}]\n{str(step)}\n")
                continue

            # Теперь обрабатываем step_dict единообразно
            capability = (
                step_dict.get("capability_name")
                or step_dict.get("capability")
                or step_dict.get("action", "unknown")
            )
            summary = step_dict.get("summary", "") or ""
            status = step_dict.get("status", "unknown")
            parameters = step_dict.get("parameters", None) or {}
            step_num = step_dict.get("step_number", step_dict.get("step"))

            # Читаем obs_text
            obs_text = step_dict.get("obs_text", "Нет данных")
            if not obs_text or obs_text.strip() == "Нет данных":
                obs_text = "Наблюдение недоступно или ожидает анализа"

            thought = summary.strip() if summary else "Не указано"

            # Обработка статусов
            if status == "FAILED":
                obs_text = f"❌ Ошибка: {obs_text}"
            elif status == "blocked":
                observation = step_dict.get("observation", {})
                if isinstance(observation, dict):
                    block_reason = observation.get("reason", "политика безопасности")
                else:
                    block_reason = "политика безопасности"
                obs_text = f"⛔ ЗАБЛОКИРОВАНО: {block_reason}. Выбери другое действие."

            # Формируем блок шага
            block = f"[ШАГ {i}]\n"

            if "\n" in thought:
                block += f"💭 Обоснование:\n{thought}\n"
            else:
                block += f"💭 Обоснование: {thought}\n"

            block += f"🛠️ Действие: {capability}\n"
            block += f"📥 Параметры: {parameters}\n"
            block += f"👁️ Наблюдение: {obs_text}\n"
            block += f"📊 Статус: {status}\n"
            lines.append(block)

        return "\n".join(lines)

    def _build_exploration_rules(self, session_context) -> str:
        """
        Генерирует универсальные правила зондирования на основе статистики пустых результатов.

        ВОЗВРАЩАЕТ:
        - str: markdown блок с правилами исследования данных или пустая строка
        """
        if not session_context or not hasattr(session_context, 'needs_exploration'):
            return ""

        if not session_context.needs_exploration(threshold=1):
            return ""

        last_empty = session_context.get_last_empty_query()
        if not last_empty:
            return ""

        tables = last_empty.get("tables", [])
        filters = last_empty.get("filters", {})

        if not tables:
            return ""

        table_names = ", ".join([f"`{t}`" for t in tables])
        filter_str = str(filters) if filters else "без фильтров"

        rules = [
            "\n🧭 **РЕЖИМ ИССЛЕДОВАНИЯ ДАННЫХ**",
            "Предыдущие запросы вернули 0 строк. НЕ повторяй фильтры.",
            f"Таблицы: {table_names}",
            f"Последний фильтр: {filter_str}",
            "",
            "Сгенерируй ЗАПРОС НА ЗОНДИРОВАНИЕ:",
            "1. 📅 Даты: `SELECT MIN(col), MAX(col), COUNT(*) FROM {table}`",
            "2. 🏷️ Категории: `SELECT DISTINCT col, COUNT(*) FROM {table} GROUP BY col ORDER BY 2 DESC LIMIT 10`",
            "3. 📊 Объём: `SELECT COUNT(*) FROM {table}`",
            "4. 🔍 NULL-анализ: `SELECT COUNT(*) FROM {table} WHERE col IS NULL`",
            "",
            "🎯 Цель: понять реальный диапазон данных. Верни результат зондирования, затем скорректируй запрос."
        ]

        return "\n".join(rules)

    def _extract_observations_from_step(
        self, session_context, observation_item_ids: list
    ) -> str:
        """
        Извлекает реальные данные наблюдений из контекста сессии.

        Поддерживает умную обработку по размеру данных:
        - < 50 строк: показываем полностью
        - 50-500 строк: статистика + первые 5 примеров
        - 500-1000 строк: только статистика + 3 примера
        - > 1000 строк: только мета + рекомендация использовать data_analysis
        """
        if not observation_item_ids:
            return "Нет наблюдений"

        if not session_context or not hasattr(session_context, "data_context"):
            return f"ID наблюдений: {observation_item_ids}"

        observations = []
        total_rows = 0

        for obs_id in observation_item_ids:
            try:
                item = session_context.data_context.get_item(
                    obs_id, raise_on_missing=False
                )

                if item and hasattr(item, "content"):
                    # Используем quick_content если есть (отформатированное наблюдение)
                    if hasattr(item, "quick_content") and item.quick_content:
                        observations.append(item.quick_content)
                        continue

                    content = item.content

                    # Проверяем, это observation с ошибкой?
                    is_error_observation = False
                    if hasattr(item, "item_type"):
                        from core.session_context.model import ContextItemType

                        is_error_observation = (
                            item.item_type == ContextItemType.ERROR_LOG
                        )

                    if is_error_observation:
                        # Обработка ошибки - показываем детали
                        if isinstance(content, dict):
                            error_msg = content.get("error", "Неизвестная ошибка")
                            capability = content.get("capability", "unknown")
                            parameters = content.get("parameters", {})
                            traceback = content.get("traceback", "")

                            observations.append(f"❌ ОШИБКА в {capability}")
                            observations.append(f"   Текст: {error_msg}")

                            # Показываем параметры вызова
                            if parameters:
                                params_str = ", ".join(
                                    [f"{k}={str(v)}" for k, v in parameters.items()]
                                )
                                observations.append(f"   Параметры: {params_str}")

                            # Показываем traceback если есть (сокращённо)
                            if traceback:
                                # Берём последние 5 строк traceback для компактности
                                tb_lines = traceback.strip().split("\n")[-5:]
                                tb_str = "\n   ".join(tb_lines)
                                observations.append(f"   Детали:\n   {tb_str}")

                            observations.append(
                                "💡 Возможно, нужно: проверить параметры, вызвать skill с другими параметрами, или использовать другой skill"
                            )
                        else:
                            observations.append(f"❌ ОШИБКА: {str(content)}")
                        continue

                    # Извлекаем полезную информацию
                    rows = None

                    # DBQueryResult object
                    if hasattr(content, "rows") and hasattr(content, "success"):
                        rows = content.rows
                    # Dict format
                    elif isinstance(content, dict):
                        if "rows" in content:
                            rows = content["rows"]
                        elif "result" in content:
                            result_str = str(content["result"])
                            observations.append(f"- {result_str}")
                        elif "data" in content:
                            data_str = str(content["data"])
                            observations.append(f"- {data_str}")
                        else:
                            content_str = str(content)
                            observations.append(f"- {content_str}")

                    # Обработка rows
                    if rows is not None:
                        total_rows += len(rows)

                        # Проверяем предупреждение об усечении данных
                        truncated_warning = False
                        truncated_message = ""
                        if hasattr(item, "metadata") and item.metadata:
                            if (
                                hasattr(item.metadata, "additional_data")
                                and item.metadata.additional_data
                            ):
                                truncated_warning = item.metadata.additional_data.get(
                                    "truncated_warning", False
                                )
                                truncated_message = item.metadata.additional_data.get(
                                    "truncated_message", ""
                                )

                        # Все данные показываем полностью
                        observations.extend(self._format_small_data(rows))
                        # Добавляем предупреждение об усечении
                        if truncated_warning:
                            observations.append(f"⚠️ {truncated_message}")
                    elif not observations:
                        # Fallback для других типов
                        content_str = str(content)
                        observations.append(f"- {content_str}")

            except Exception as e:
                observations.append(f"- [Ошибка чтения {obs_id}: {e}]")

        # Добавляем итоговую статистику если данных много (ИСКЛЮЧАЯ data_analysis результаты)
        # Проверяем, есть ли наблюдения от data_analysis - они уже полные и не требуют рекомендаций
        has_data_analysis_result = False
        for obs_id in observation_item_ids:
            try:
                if session_context and hasattr(session_context, "data_context"):
                    item = session_context.data_context.get_item(
                        obs_id, raise_on_missing=False
                    )
                    if item and hasattr(item, "metadata"):
                        if item.metadata.get(
                            "skill"
                        ) == "data_analysis" or "data_analysis" in str(item.metadata):
                            has_data_analysis_result = True
                            break
            except:
                pass

        # Только если нет результатов data_analysis и данные превышают лимит - добавляем рекомендацию
        if (
            total_rows > self.DATA_SIZE_LIMITS["medium"]
            and not has_data_analysis_result
        ):
            observations.append(f"\n⚠️ ОБЩИЙ ОБЪЁМ: {total_rows} строк")
            observations.append(
                "💡 Эти данные не доступны для final_answer. Рекомендация: Используйте data_analysis.analyze_step_data"
            )

        if observations:
            return "\n".join(observations)
        return "Нет доступных данных"

    def _format_small_data(self, rows: list, use_markdown: bool = True) -> list:
        """Форматирование данных для отображения."""
        if not rows:
            return []

        if use_markdown and rows and isinstance(rows[0], dict):
            return self._format_table_markdown(rows)

        formatted = []
        for row in rows:
            if isinstance(row, dict):
                row_parts = []
                for k, v in row.items():
                    row_parts.append(f"{k}: {v}")
                row_str = ", ".join(row_parts)
                formatted.append(f"   - {row_str}")
            else:
                formatted.append(f"   - {str(row)}")
        return formatted

    def _format_available_tools_with_params(
        self,
        available_capabilities: List[Capability],
        schema_validator: Optional[Any] = None,
        application_context=None,
    ) -> str:
        """Формирует структурированный контекст инструментов для LLM.

        ИСПОЛЬЗУЕТ:
        - get_tool_description() каждого компонента для получения полного описания
        - input_contracts для параметров каждой capability

        ARGS:
        - available_capabilities: список доступных capability
        - schema_validator: опциональный валидатор схем
        - application_context: контекст приложения

        RETURNS:
        - str: структурированный список инструментов
        """
        from core.models.enums.common_enums import ComponentType

        lines = ["## Доступные инструменты"]

        if not application_context or not hasattr(application_context, "components"):
            # Fallback: простой формат
            for cap in available_capabilities:
                lines.append(f"- {cap.name}: {cap.description}")
            return "\n".join(lines)

        # Получаем описания от компонентов через get_tool_description()
        component_descriptions: Dict[str, Dict[str, Any]] = {}

        for component in application_context.components.all_components():
            if hasattr(component, "get_tool_description"):
                try:
                    desc = component.get_tool_description()
                    if desc and hasattr(component, "name"):
                        component_descriptions[component.name] = desc
                except Exception:
                    pass

        # Группируем capabilities по skill
        skills_data: Dict[str, List[Dict[str, Any]]] = {}
        standalone_caps = []

        for cap in available_capabilities:
            skill_name = (
                cap.skill_name
                if hasattr(cap, "skill_name") and cap.skill_name
                else None
            )

            if skill_name:
                if skill_name not in skills_data:
                    skills_data[skill_name] = []
                skills_data[skill_name].append(
                    {"name": cap.name, "description": cap.description}
                )
            else:
                standalone_caps.append(cap)

        # Формируем секцию для каждого skill
        for skill_name, caps in sorted(skills_data.items()):
            skill_desc = component_descriptions.get(skill_name, {})
            lines.append(f"\n### {skill_name.upper()}")

            if skill_desc.get("description"):
                lines.append(f"{skill_desc['description']}")

            lines.append("\nРежимы работы:")

            for cap_info in caps:
                cap_name = cap_info["name"]
                cap_desc = cap_info["description"]

                # Пытаемся получить параметры из input_contracts
                params_info = ""
                for component in application_context.components.all_of_type(
                    ComponentType.SKILL
                ):
                    if hasattr(component, "name") and component.name == skill_name:
                        if (
                            hasattr(component, "input_contracts")
                            and cap_name in component.input_contracts
                        ):
                            contract_class = component.input_contracts[cap_name]
                            if hasattr(contract_class, "model_json_schema"):
                                schema = contract_class.model_json_schema()
                                props = schema.get("properties", {})
                                if props:
                                    params_info = self._format_params_from_schema(
                                        props, schema.get("required", [])
                                    )

                # Для execute_script добавляем детализацию скриптов (без примеров SQL для ReAct)
                if "execute_script" in cap_name:
                    lines.append(f"\n#### {cap_name}")
                    lines.append(f"{cap_desc}")

                    # Детализация скриптов (include_sql_examples=False для ReAct pattern)
                    for component in application_context.components.all_of_type(
                        ComponentType.SKILL
                    ):
                        if hasattr(component, "name") and component.name == skill_name:
                            if hasattr(component, "get_scripts_description"):
                                try:
                                    scripts_desc = component.get_scripts_description(include_sql_examples=False)
                                    if scripts_desc:
                                        lines.append(scripts_desc)
                                except Exception:
                                    pass

                    if params_info:
                        lines.append(params_info)
                else:
                    lines.append(f"\n#### {cap_name}")
                    lines.append(f"{cap_desc}")
                    if params_info:
                        lines.append(params_info)

        # Добавляем standalone capabilities (tools без skill_name)
        if standalone_caps:
            lines.append("\n### Другие инструменты")
            for cap in standalone_caps:
                cap_name = cap.name if hasattr(cap, "name") else "unknown"
                cap_desc = cap.description if hasattr(cap, "description") else ""

                lines.append(f"\n#### {cap_name}")
                lines.append(f"{cap_desc}")

                # Параметры из component
                tool_desc = component_descriptions.get(cap_name, {})
                caps_list = tool_desc.get("capabilities", [])
                if caps_list:
                    for cap_item in caps_list:
                        if cap_item.get("name") == cap_name:
                            params = cap_item.get("parameters", {})
                            if params:
                                lines.append("Параметры:")
                                for pname, pinfo in params.items():
                                    ptype = pinfo.get("type", "string")
                                    preq = pinfo.get("required", False)
                                    pdesc = pinfo.get("description", "")
                                    req_str = "обязательный" if preq else "опциональный"
                                    if pdesc:
                                        lines.append(
                                            f"  - `{pname}` ({ptype}, {req_str}): {pdesc}"
                                        )
                                    else:
                                        lines.append(
                                            f"  - `{pname}` ({ptype}, {req_str})"
                                        )

        return "\n".join(lines)

    def _format_params_from_schema(
        self, properties: Dict[str, Any], required: List[str]
    ) -> str:
        """Форматирует параметры из JSON Schema в читаемый текст."""
        if not properties:
            return ""

        lines = ["Параметры:"]
        for param_name, param_info in properties.items():
            param_type = param_info.get("type", "string")
            is_required = param_name in required
            req_str = "обязательный" if is_required else "опциональный"
            param_desc = param_info.get("description", "")

            if "enum" in param_info:
                enum_vals = ", ".join([str(e) for e in param_info["enum"]])
                param_desc += f" (варианты: {enum_vals})"

            if param_desc:
                lines.append(
                    f"  - `{param_name}` ({param_type}, {req_str}): {param_desc}"
                )
            else:
                lines.append(f"  - `{param_name}` ({param_type}, {req_str})")

        return "\n".join(lines)

    def _render_prompt(self, template: str, variables: Dict[str, Any]) -> str:
        """Рендерит шаблон с подстановкой переменных."""
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered

    # ========================================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С CAPABILITY (вместо CapabilityResolverService)
    # ========================================================================

    def _find_capability(
        self, available_capabilities: List[Capability], capability_name: str
    ) -> Optional[Capability]:
        """
        Ищет capability по имени.

        ПАРАМЕТРЫ:
        - available_capabilities: список доступных capability
        - capability_name: имя для поиска

        ВОЗВРАЩАЕТ:
        - Capability или None если не найдено
        """
        # 1. Прямое совпадение
        for cap in available_capabilities:
            if cap.name == capability_name:
                return cap

        # 2. Совпадение по префиксу
        if "." in capability_name:
            prefix = capability_name.split(".")[0]
            for cap in available_capabilities:
                if cap.name == prefix:
                    return cap
                if hasattr(cap, "skill_name") and cap.skill_name:
                    if cap.skill_name == prefix:
                        return cap

        # 3. Частичное совпадение
        for cap in available_capabilities:
            if capability_name.lower() in cap.name.lower():
                return cap

        return None

    def _validate_capability_parameters(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Валидирует параметры capability.

        ПАРАМЕТРЫ:
        - capability: capability для валидации
        - parameters: параметры для валидации
        - context: контекст выполнения

        ВОЗВРАЩАЕТ:
        - validated параметры или оригинальные если валидация не удалась
        """
        # Упрощённая валидация - если нет schema_validator, возвращаем как есть
        if not hasattr(self, "schema_validator") or self.schema_validator is None:
            return parameters

        try:
            validated = self.schema_validator.validate_parameters(
                capability=capability, raw_params=parameters, context=str(context)
            )
            return validated if validated else parameters
        except Exception:
            # Fallback: возвращаем input или оригинальные параметры
            return {"input": parameters.get("input", "Продолжить выполнение задачи")}

    def _filter_capabilities(
        self, capabilities: List[Capability], pattern_id: str
    ) -> List[Capability]:
        """Фильтрует capability по supported_strategies."""
        pattern_prefix = pattern_id.split(".")[0]
        if "_pattern" in pattern_prefix:
            pattern_prefix = pattern_prefix.replace("_pattern", "")
        return [
            cap
            for cap in capabilities
            if pattern_prefix.lower()
            in [s.lower() for s in (cap.supported_strategies or [])]
        ]

    def _generate_tools_selection_rules(
        self, available_capabilities: List[Capability], application_context=None
    ) -> str:
        """Генерирует унифицированные правила выбора инструментов на основе capabilities.

        ПРАВИЛА:
        - Группирует capabilities по skill
        - Для каждого skill с несколькими capability генерирует правила выбора
        - Для одиночных capabilities просто перечисляет их

        ВОЗВРАЩАЕТ:
        - str: markdown с правилами выбора
        """
        from collections import defaultdict

        # Группируем capabilities по skill
        skills_caps: Dict[str, List[Capability]] = defaultdict(list)
        standalone_caps = []

        for cap in available_capabilities:
            skill_name = (
                cap.skill_name
                if hasattr(cap, "skill_name") and cap.skill_name
                else "other"
            )
            if skill_name and skill_name != "other":
                skills_caps[skill_name].append(cap)
            else:
                standalone_caps.append(cap)

        lines = ["=== ПРАВИЛА ВЫБОРА ИНСТРУМЕНТОВ ==="]

        # Обрабатываем каждый skill с несколькими capabilities
        for skill_name, caps in skills_caps.items():
            if len(caps) > 1:
                # Skill с несколькими capabilities - генерируем правила выбора
                lines.append(f"\n🔷 **{skill_name.upper()}**")
                lines.append("Выбери подходящий режим:")

                # Сортируем: сначала execute, потом generate, потом другие
                sorted_caps = sorted(
                    caps,
                    key=lambda c: (
                        0
                        if "execute" in c.name
                        else (
                            1
                            if "generate" in c.name
                            else 2 if "search" in c.name else 3
                        )
                    ),
                )

                for i, cap in enumerate(sorted_caps, 1):
                    desc = cap.description if hasattr(cap, "description") else ""
                    lines.append(f"  {i}. `{cap.name}` - {desc}")

            elif len(caps) == 1:
                # Одиночная capability - просто добавляем в конец
                cap = caps[0]
                lines.append(f"\n- `{cap.name}`")

        # Добавляем standalone capabilities
        if standalone_caps:
            lines.append("\n📌 Другие инструменты:")
            for cap in standalone_caps:
                desc = cap.description if hasattr(cap, "description") else ""
                lines.append(f"- `{cap.name}` - {desc}")

        return "\n".join(lines)


class BaseBehaviorPattern(Component, BehaviorPatternInterface):
    """
    БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ПОВЕДЕНЧЕСКИХ ПАТТЕРНОВ.

    НАСЛЕДУЕТСЯ ОТ Component ДЛЯ:
    - Единого кэша промптов/контрактов
    - Единых методов доступа
    - Единой инициализации через component_config.resolved_*

    ПРЕДОСТАВЛЯЕТ:
    - component_name для идентификации
    - pattern_id для совместимости
    - prompt_builder: PromptBuilderService
    - capability_resolver: CapabilityResolverService
    """

    def __init__(
        self,
        component_name: str,
        component_config: Optional[ComponentConfig] = None,
        application_context: "ApplicationContext" = None,
        executor: "ActionExecutor" = None,
    ):
        """
        Инициализация базового паттерна.
        """
        if not component_name:
            raise ValueError("component_name обязателен для инициализации паттерна")

        Component.__init__(
            self,
            name=component_name,
            component_type="behavior",
            application_context=application_context,
            component_config=component_config,
            executor=executor,
        )

        # pattern_id для совместимости
        self.pattern_id = component_name
        self.component_name = component_name

        # === ОБЩИЕ СЕРВИСЫ ===
        self.prompt_builder = PromptBuilderService()
        # capability_resolver удалён - методы перенесены в BaseBehaviorPattern

    def get_prompt(self, key: str) -> Prompt:
        """
        Получает промпт из кэша Component.

        ДЕЛЕГИРУЕТ: Component.get_prompt()
        """
        return super().get_prompt(key)

    def get_input_contract(self, key: str) -> Type[BaseModel]:
        """
        Получает input контракт из кэша Component.

        ДЕЛЕГИРУЕТ: Component.get_input_contract()
        """
        return super().get_input_contract(key)

    def get_output_contract(self, key: str) -> Type[BaseModel]:
        """
        Получает output контракт из кэша Component.

        ДЕЛЕГИРУЕТ: Component.get_output_contract()
        """
        return super().get_output_contract(key)

    def _render_prompt(self, prompt_template: str, variables: Dict[str, Any]) -> str:
        """
        Рендерит шаблон промпта с подстановкой переменных.
        """

    def _render_prompt(self, prompt_template: str, variables: Dict[str, Any]) -> str:
        """Рендерит шаблон с подстановкой переменных."""
        rendered = prompt_template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered

    async def initialize(self) -> bool:
        """
        Инициализация паттерна.

        Промпты/контракты уже загружены в component_config.resolved_* на уровне ApplicationContext.
        """
        # Вызываем инициализацию Component (загружает из component_config.resolved_*)
        success = await Component.initialize(self)

        # Регистрируем схемы после загрузки контрактов
        self._register_all_schemas()

        return success

    def _register_all_schemas(self):
        """Регистрирует все схемы из input_contracts в validator."""
        if not hasattr(self, "schema_validator") or not self.schema_validator:
            return

        self._log_debug(f"input_contracts keys: {list(self.input_contracts.keys())}")

        registered = 0
        for cap_name, contract_class in self.input_contracts.items():
            try:
                if hasattr(contract_class, "model_json_schema"):
                    schema = contract_class.model_json_schema()
                    properties = schema.get("properties", {})
                    required = schema.get("required", [])
                    schema_dict = {}
                    for prop_name, prop_info in properties.items():
                        schema_dict[prop_name] = {
                            "type": prop_info.get("type", "string"),
                            "required": prop_name in required,
                            "description": prop_info.get("description", ""),
                        }
                    if schema_dict:
                        # Регистрируем по full key
                        self.schema_validator.register_capability_schema(
                            cap_name, schema_dict
                        )
                        # Убираем _input суффикс и регистрируем отдельно
                        if cap_name.endswith("_input"):
                            base_name = cap_name[:-6]
                            self.schema_validator.register_capability_schema(
                                base_name, schema_dict
                            )
                        registered += 1
            except Exception as e:
                self._log_error(f"Error registering {cap_name}: {e}", exc_info=True)
        self._log_debug(f"Total schemas registered: {registered}")

    async def analyze_context(
        self,
        session_context: SessionContext,
        available_capabilities: list[Capability],
        context_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений."""
        raise NotImplementedError("Subclasses must implement analyze_context")

    async def generate_decision(
        self,
        session_context: SessionContext,
        available_capabilities: list[Capability],
        context_analysis: Dict[str, Any],
    ) -> Decision:
        """Генерация решения на основе анализа."""
        raise NotImplementedError("Subclasses must implement generate_decision")

    def _get_event_type_for_success(self) -> EventType:
        """Возвращает тип события для успешного выполнения паттерна."""
        return EventType.AGENT_START

    def _execute_impl(
        self,
        capability: "Capability",
        parameters: Dict[str, Any],
        execution_context: Any,
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики паттерна поведения (СИНХРОННАЯ).

        ПАТТЕРНЫ НЕ ВЫПОЛНЯЮТ ДЕЙСТВИЯ напрямую - они генерируют решения через generate_decision().
        Этот метод предоставляет интерфейс для Component.execute().

        ВАЖНО: Валидация входа/выхода и метрики выполняются в Component.execute()
        Здесь только бизнес-логика.
        """
        # Паттерны поведения работают через generate_decision()
        # Этот метод предоставляет совместимость с интерфейсом Component

        # Извлекаем session_context из execution_context
        session_context = None
        if hasattr(execution_context, "session_context"):
            session_context = execution_context.session_context

        available_capabilities = (
            execution_context.available_capabilities
            if hasattr(execution_context, "available_capabilities")
            else []
        )

        # Анализируем контекст и генерируем решение (синхронное ожидание async методов)
        context_analysis = safe_async_call(
            self.analyze_context(session_context, available_capabilities)
        )
        decision = safe_async_call(
            self.generate_decision(
                session_context,
                available_capabilities,
                context_analysis,
                execution_context,
            )
        )

        # Возвращаем решение в виде словаря
        return {
            "decision_type": (
                decision.decision_type.value
                if hasattr(decision.decision_type, "value")
                else str(decision.decision_type)
            ),
            "capability_name": decision.capability_name,
            "parameters": decision.parameters,
            "reasoning": decision.reasoning,
        }
