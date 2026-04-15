"""
Базовый класс для всех паттернов поведения (Behavior Patterns).

АРХИТЕКТУРА:
- Наследуется от Component для единого интерфейса
- Использует методы Component.get_prompt/get_input_contract/get_output_contract
- Все паттерны (ReAct, Planning, Evaluation, Fallback) наследуются от этого класса
- Предоставляет общие сервисы: PromptBuilderService, CapabilityResolverService
- Логирование через стандартный logging + LogEventType (НЕ через EventBus)
"""
import logging
import typing
from typing import Dict, Any, Optional, List, Type

from pydantic import BaseModel

from core.agent.behaviors.base import BehaviorPatternInterface, Decision, DecisionType
from core.infrastructure.logging.event_types import LogEventType
from core.models.data.capability import Capability
from core.models.data.prompt import Prompt
from core.session_context.session_context import SessionContext
from core.agent.components.component import Component
from core.config.component_config import ComponentConfig
from core.utils.async_utils import safe_async_call


# ============================================================================
# ОБЩИЕ СЕРВИСЫ ДЛЯ ВСЕХ ПАТТЕРНОВ
# ============================================================================

class PromptBuilderService:
    """Сервис для построения структурированных промптов."""

    # НАСТРАИВАЕМЫЕ ЛИМИТЫ ДЛЯ ОБРАБОТКИ ДАННЫХ
    DATA_SIZE_LIMITS = {
        'small': 50,       # Показываем полностью
        'medium': 500,     # Суммаризация + примеры
        'large': 1000,     # Только статистика
        'huge': 5000,      # Требуется data_analysis skill
    }
    
    DISPLAY_LIMITS = {
        'max_rows_display': 20,
        'max_chars_display': 1000,
    }

    def build_reasoning_prompt(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        templates: Dict[str, str],
        schema_validator: Optional[Any] = None,
        session_context=None,
        pattern_id: str = "react",
        application_context=None
    ) -> str:
        """Строит полный промпт для рассуждения."""
        # Фильтруем capability по supported_strategies
        # Если вызывается на PromptBuilderService, используем available_capabilities напрямую
        if hasattr(self, '_filter_capabilities'):
            filtered_caps = self._filter_capabilities(available_capabilities, pattern_id)
        else:
            filtered_caps = available_capabilities

        # Форматируем инструменты с параметрами — передаём application_context для доступа к контрактам
        if hasattr(self, '_format_available_tools_with_params'):
            tools_str = self._format_available_tools_with_params(
                filtered_caps, schema_validator, application_context
            )
        else:
            # Fallback для PromptBuilderService
            tools_str = self._format_tools_fallback(filtered_caps, schema_validator)
        
        variables = {
            "input": self._build_input_context(context_analysis, filtered_caps),
            "goal": context_analysis.get("goal", "Неизвестная цель"),
            "dialogue_history": self._build_dialogue_history(session_context),
            "step_history": self._build_step_history(
                context_analysis.get("last_steps", []),
                session_context=session_context
            ),
            "available_tools": tools_str,
            "no_progress_steps": context_analysis.get("no_progress_steps", 0),
            "consecutive_errors": context_analysis.get("consecutive_errors", 0)
        }
        return self._render_prompt(templates.get("user", ""), variables)
    
    def _format_tools_fallback(self, available_capabilities: List[Capability], schema_validator: Optional[Any] = None) -> str:
        """Fallback форматирование без параметров."""
        lines = []
        for cap in available_capabilities:
            name = cap.name if hasattr(cap, 'name') else cap.get('name', 'unknown')
            description = cap.description if hasattr(cap, 'description') else cap.get('description', 'no description')
            lines.append(f"- {name}: {description}")
        return "\n".join(lines)
    
    def _build_input_context(self, context_analysis: Dict[str, Any], available_capabilities: List[Capability]) -> str:
        """Формирует секцию {input} для промпта — только мета-информация, без деталей шагов."""
        goal = context_analysis.get("goal", "Неизвестная цель")
        last_steps = context_analysis.get("last_steps", [])
        parts = [
            f"ЦЕЛЬ: {goal}",
            f"Шагов выполнено: {len(last_steps)}",
            f"Шагов без прогресса: {context_analysis.get('no_progress_steps', 0)}",
            f"Ошибок подряд: {context_analysis.get('consecutive_errors', 0)}"
        ]
        return "\n".join(parts)

    def _build_dialogue_history(self, session_context) -> str:
        """
        Формирует блок истории диалога для вставки в промпт.

        ПАРАМЕТРЫ:
        - session_context: контекст сессии

        ВОЗВРАЩАЕТ:
        - str: отформатированная история диалога или пустая строка
        """
        if session_context and hasattr(session_context, 'dialogue_history'):
            return session_context.dialogue_history.format_for_prompt()
        return ""
    
    def _format_table_markdown(self, rows: list, max_rows: int = 5) -> str:
        """Формирует Markdown таблицу из списка dict."""
        if not rows or not isinstance(rows, list):
            return ""
        
        if not rows or not isinstance(rows[0], dict):
            return str(rows[:max_rows])[:500]
        
        # Берём все колонки из первой строки
        columns = list(rows[0].keys())[:10]  # Макс 10 колонок
        
        # Заголовок
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        
        # Строки
        table_rows = []
        for row in rows[:max_rows]:
            values = []
            for col in columns:
                val = row.get(col, "")
                val_str = str(val)[:50]  # Ограничиваем длину ячейки
                val_str = val_str.replace("|", "\\|")
                values.append(val_str)
            table_rows.append("| " + " | ".join(values) + " |")
        
        lines = [header, separator] + table_rows
        
        if len(rows) > max_rows:
            lines.append(f"| ... и ещё {len(rows) - max_rows} строк |")
        
        return "\n".join(lines)

    def _build_step_history(
        self,
        last_steps: list,
        session_context=None
    ) -> str:
        """Формирует читаемую историю шагов с реальными данными."""
        if not last_steps:
            return "Шаги не выполнены"

        step_lines = []
        for i, step in enumerate(last_steps, 1):  # Все шаги
            if hasattr(step, 'capability_name'):
                # Это объект AgentStep
                capability = step.capability_name
                summary = step.summary or "Без описания"
                status = step.status.value if hasattr(step.status, 'value') else str(step.status)

                # Извлекаем параметры
                parameters_str = ""
                if hasattr(step, 'parameters') and step.parameters:
                    params = step.parameters
                    if isinstance(params, dict):
                        # Форматируем параметры компактно
                        params_parts = []
                        for key, value in params.items():
                            val_str = str(value)[:200]  # Ограничиваем длину
                            params_parts.append(f"{key}={val_str}")
                        parameters_str = "\n   Параметры: " + ", ".join(params_parts)

                # Извлекаем результат
                result_str = ""
                if hasattr(step, 'result') and step.result is not None:
                    result_data = step.result
                    if isinstance(result_data, dict):
                        result_str = str(result_data)[:500]
                    else:
                        result_str = str(result_data)[:500]

                observation_text = self._extract_observations_from_step(
                    session_context,
                    step.observation_item_ids if hasattr(step, 'observation_item_ids') else []
                )

                step_text = f"{i}. {capability}\n"
                if parameters_str:
                    step_text += f"   {parameters_str}\n"
                step_text += f"   Результат: {result_str if result_str else (observation_text if observation_text else 'Нет данных')}\n"
                step_text += f"   Статус: {status}"

            elif isinstance(step, dict):
                # Это словарь (новый формат)
                capability = step.get('capability_name', step.get('capability', 'unknown'))
                summary = step.get('summary', '')

                # Извлекаем параметры
                parameters_str = ""
                if 'parameters' in step and step['parameters']:
                    params = step['parameters']
                    if isinstance(params, dict):
                        params_parts = []
                        for key, value in params.items():
                            val_str = str(value)[:200]
                            params_parts.append(f"{key}={val_str}")
                        parameters_str = "\n   Параметры: " + ", ".join(params_parts)

                # Извлекаем результат
                result_str = ""
                if 'result' in step and step['result'] is not None:
                    result_data = step['result']
                    if isinstance(result_data, dict):
                        result_str = str(result_data)[:500]
                    else:
                        result_str = str(result_data)[:500]

                # Пробуем получить observation из dict
                if 'observation' in step and step['observation']:
                    observation = step['observation']
                elif hasattr(session_context, 'data_context') and step.get('observation_item_ids'):
                    observation = self._extract_observations_from_step(
                        session_context,
                        step['observation_item_ids']
                    )
                else:
                    observation = summary

                status = step.get('status', 'unknown')

                step_text = f"{i}. {capability}\n"
                if parameters_str:
                    step_text += f"   {parameters_str}\n"
                step_text += f"   Результат: {result_str if result_str else (observation if observation else 'Нет данных')}\n"
                step_text += f"   Статус: {status}"
            else:
                # Fallback для строки или другого типа
                step_text = f"{i}. {str(step)}"

            step_lines.append(step_text)

        return "\n\n".join(step_lines)

    def _extract_observations_from_step(
        self, 
        session_context, 
        observation_item_ids: list
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
        
        if not session_context or not hasattr(session_context, 'data_context'):
            return f"ID наблюдений: {observation_item_ids[:20]}..."
        
        observations = []
        total_rows = 0
        
        for obs_id in observation_item_ids:
            try:
                item = session_context.data_context.get_item(
                    obs_id, 
                    raise_on_missing=False
                )
                
                if item and hasattr(item, 'content'):
                    # Используем quick_content если есть (отформатированное наблюдение)
                    if hasattr(item, 'quick_content') and item.quick_content:
                        observations.append(item.quick_content)
                        continue

                    content = item.content

                    # Проверяем, это observation с ошибкой?
                    is_error_observation = False
                    if hasattr(item, 'item_type'):
                        from core.session_context.model import ContextItemType
                        is_error_observation = (item.item_type == ContextItemType.ERROR_LOG)
                    
                    if is_error_observation:
                        # Обработка ошибки — показываем детали
                        if isinstance(content, dict):
                            error_msg = content.get('error', 'Неизвестная ошибка')
                            capability = content.get('capability', 'unknown')
                            parameters = content.get('parameters', {})
                            traceback = content.get('traceback', '')
                            
                            observations.append(f"❌ ОШИБКА в {capability}")
                            observations.append(f"   Текст: {error_msg}")
                            
                            # Показываем параметры вызова
                            if parameters:
                                params_str = ", ".join([f"{k}={str(v)[:100]}" for k, v in list(parameters.items())[:3]])
                                observations.append(f"   Параметры: {params_str}")
                            
                            # Показываем traceback если есть (сокращённо)
                            if traceback:
                                # Берём последние 5 строк traceback для компактности
                                tb_lines = traceback.strip().split('\n')[-5:]
                                tb_str = '\n   '.join(tb_lines)
                                observations.append(f"   Детали:\n   {tb_str}")
                            
                            observations.append("💡 Возможно, нужно: проверить параметры, вызвать skill с другими параметрами, или использовать другой skill")
                        else:
                            observations.append(f"❌ ОШИБКА: {str(content)[:500]}")
                        continue

                    # Извлекаем полезную информацию
                    rows = None
                    
                    # DBQueryResult object
                    if hasattr(content, 'rows') and hasattr(content, 'success'):
                        rows = content.rows
                    # Dict format
                    elif isinstance(content, dict):
                        if 'rows' in content:
                            rows = content['rows']
                        elif 'result' in content:
                            result_str = str(content['result'])[:self.DISPLAY_LIMITS['max_chars_display']]
                            observations.append(f"- {result_str}")
                        elif 'data' in content:
                            data_str = str(content['data'])[:self.DISPLAY_LIMITS['max_chars_display']]
                            observations.append(f"- {data_str}")
                        else:
                            content_str = str(content)[:self.DISPLAY_LIMITS['max_chars_display']]
                            observations.append(f"- {content_str}")
                    
                    # Обработка rows
                    if rows is not None:
                        total_rows += len(rows)

                        # Проверяем предупреждение об усечении данных
                        truncated_warning = False
                        truncated_message = ""
                        if hasattr(item, 'metadata') and item.metadata:
                            if hasattr(item.metadata, 'additional_data') and item.metadata.additional_data:
                                truncated_warning = item.metadata.additional_data.get('truncated_warning', False)
                                truncated_message = item.metadata.additional_data.get('truncated_message', '')

                        # УМНАЯ ОБРАБОТКА ПО РАЗМЕРУ
                        if len(rows) <= self.DATA_SIZE_LIMITS['small']:
                            # Маленькие данные → показываем всё
                            observations.extend(self._format_small_data(rows))
                            # Добавляем предупреждение об усечении
                            if truncated_warning:
                                observations.append(f"⚠️ {truncated_message}")
                        elif len(rows) <= self.DATA_SIZE_LIMITS['medium']:
                            # Средние данные → статистика + первые N
                            observations.append(f"📊 Найдено {len(rows)} записей")
                            observations.append("⚠️ Эти данные не доступны для final_answer, для полного анализа используйте data_analysis.analyze_step_data")
                            observations.append("📋 Первые 5:")
                            observations.extend(self._format_small_data(rows[:5]))
                            observations.append(f"... и ещё {len(rows) - 5} записей")
                        elif len(rows) <= self.DATA_SIZE_LIMITS['large']:
                            # Большие данные → только статистика
                            observations.append(f"📊 Найдено {len(rows)} записей (большие данные)")
                            observations.append("⚠️ Эти данные не доступны для final_answer, для полного анализа используйте data_analysis.analyze_step_data")
                            observations.append("📋 Пример (3 записи):")
                            observations.extend(self._format_small_data(rows[:3]))
                        else:
                            # Очень большие данные → только мета
                            observations.append(f"📊 Найдено {len(rows)} записей (очень большие данные)")
                            observations.append("💡 Эти данные не доступны для final_answer, вызовите data_analysis.analyze_step_data для суммаризации")
                    elif not observations:
                        # Fallback для других типов
                        content_str = str(content)[:self.DISPLAY_LIMITS['max_chars_display']]
                        observations.append(f"- {content_str}")
                        
            except Exception as e:
                observations.append(f"- [Ошибка чтения {obs_id}: {e}]")
        
        # Добавляем итоговую статистику если данных много
        if total_rows > self.DATA_SIZE_LIMITS['medium']:
            observations.append(f"\n⚠️ ОБЩИЙ ОБЪЁМ: {total_rows} строк")
            observations.append("💡 Эти данные не доступны для final_answer. Рекомендация: Используйте data_analysis.analyze_step_data")
        
        if observations:
            return "\n".join(observations)
        return "Нет доступных данных"

    def _format_small_data(self, rows: list, use_markdown: bool = True) -> list:
        """Форматирование небольших данных для отображения."""
        if not rows:
            return []
        
        if use_markdown and rows and isinstance(rows[0], dict):
            return self._format_table_markdown(rows, self.DISPLAY_LIMITS['max_rows_display'])
        
        formatted = []
        for row in rows[:self.DISPLAY_LIMITS['max_rows_display']]:
            if isinstance(row, dict):
                row_parts = []
                for k, v in list(row.items())[:5]:
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
        application_context=None
    ) -> str:
        """Форматирует список инструментов с параметрами из реальных контрактов компонентов.

        АРХИТЕКТУРА:
        - Берёт схемы напрямую из component.input_contracts (Pydantic модели)
        - Использует model_json_schema() для получения полного описания параметров
        - Включает description, type, required для каждого параметра

        ARGS:
        - available_capabilities: список доступных capability
        - schema_validator: опциональный валидатор схем (для обратной совместимости)
        - application_context: контекст приложения для доступа к компонентам

        RETURNS:
        - str: отформатированный список инструментов с параметрами
        """
        # Собираем все input_contracts от всех компонентов (tools + skills)
        all_contracts: Dict[str, Dict[str, Any]] = {}

        if application_context and hasattr(application_context, 'components'):
            from core.models.enums.common_enums import ComponentType

            for component in application_context.components.all_of_type(ComponentType.TOOL):
                if hasattr(component, 'input_contracts'):
                    for cap_name, contract_class in component.input_contracts.items():
                        if hasattr(contract_class, 'model_json_schema'):
                            all_contracts[cap_name] = contract_class.model_json_schema()

            for component in application_context.components.all_of_type(ComponentType.SKILL):
                if hasattr(component, 'input_contracts'):
                    for cap_name, contract_class in component.input_contracts.items():
                        if hasattr(contract_class, 'model_json_schema'):
                            all_contracts[cap_name] = contract_class.model_json_schema()

        # Fallback: пытаемся получить из schema_validator если нет application_context
        if not all_contracts and schema_validator:
            validator = schema_validator
            for cap in available_capabilities:
                cap_name = cap.name if hasattr(cap, 'name') else cap.get('name', '')
                schema_obj = validator.get_capability_schema(cap_name)
                if schema_obj and hasattr(schema_obj, 'to_dict'):
                    all_contracts[cap_name] = schema_obj.to_dict()

        lines = []
        for cap in available_capabilities:
            # Учитываем флаг видимости
            visiable = cap.visiable if hasattr(cap, 'visiable') else True
            if not visiable:
                continue

            name = cap.name if hasattr(cap, 'name') else cap.get('name', 'unknown')
            description = cap.description if hasattr(cap, 'description') else cap.get('description', 'no description')

            # Получаем схему из собранных контрактов
            params_schema = all_contracts.get(name)

            line = f"- {name}: {description}"
            if params_schema and isinstance(params_schema, dict):
                properties = params_schema.get('properties', {})
                required_fields = params_schema.get('required', [])

                params_list = []
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'string')
                    is_required = param_name in required_fields
                    req_mark = "(required)" if is_required else "(optional)"
                    param_desc = param_info.get('description', '')

                    # Раскрываем вложенные объекты
                    if param_type == 'object' and 'properties' in param_info:
                        # Это сложный объект — форматируем с вложенными полями
                        nested_props = param_info.get('properties', {})
                        nested_required = param_info.get('required', [])
                        nested_lines = []
                        for nested_name, nested_info in nested_props.items():
                            nested_type = nested_info.get('type', 'string')
                            nested_req = "(required)" if nested_name in nested_required else "(optional)"
                            nested_desc = nested_info.get('description', '')
                            default_val = nested_info.get('default')
                            default_str = f", default: {default_val}" if default_val is not None else ""
                            
                            # Добавляем enum если есть
                            if 'enum' in nested_info:
                                enum_vals = ', '.join([str(e) for e in nested_info['enum']])
                                nested_desc += f" (варианты: {enum_vals})"
                            
                            if nested_desc:
                                nested_lines.append(f"{nested_name}: {nested_type} {nested_req}{default_str} — {nested_desc}")
                            else:
                                nested_lines.append(f"{nested_name}: {nested_type} {nested_req}{default_str}")
                        
                        # Форматируем как блок с вложенностью
                        params_list.append(f"{param_name}: object {req_mark} — {param_desc}")
                        params_list.append(f"    Структура {param_name}:")
                        for nl in nested_lines:
                            params_list.append(f"      - {nl}")
                    else:
                        # Простой тип
                        default_val = param_info.get('default')
                        default_str = f", default: {default_val}" if default_val is not None else ""
                        
                        # Добавляем enum если есть
                        if 'enum' in param_info:
                            enum_vals = ', '.join([str(e) for e in param_info['enum']])
                            param_desc += f" (варианты: {enum_vals})"
                        
                        if param_desc:
                            params_list.append(f"{param_name}: {param_type} {req_mark}{default_str} — {param_desc}")
                        else:
                            params_list.append(f"{param_name}: {param_type} {req_mark}{default_str}")

                if params_list:
                    line += "\n    Параметры:"
                    for p in params_list:
                        line += f"\n      {p}"
            lines.append(line)
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
        self,
        available_capabilities: List[Capability],
        capability_name: str
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
        if '.' in capability_name:
            prefix = capability_name.split('.')[0]
            for cap in available_capabilities:
                if cap.name == prefix:
                    return cap
                if hasattr(cap, 'skill_name') and cap.skill_name:
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
        context: Dict[str, Any]
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
        # Упрощённая валидация — если нет schema_validator, возвращаем как есть
        if not hasattr(self, 'schema_validator') or self.schema_validator is None:
            return parameters
        
        try:
            validated = self.schema_validator.validate_parameters(
                capability=capability,
                raw_params=parameters,
                context=str(context)
            )
            return validated if validated else parameters
        except Exception:
            # Fallback: возвращаем input или оригинальные параметры
            return {"input": parameters.get("input", "Продолжить выполнение задачи")}

    def _filter_capabilities(
        self,
        capabilities: List[Capability],
        pattern_id: str
    ) -> List[Capability]:
        """Фильтрует capability по supported_strategies."""
        pattern_prefix = pattern_id.split('.')[0]
        if "_pattern" in pattern_prefix:
            pattern_prefix = pattern_prefix.replace("_pattern", "")
        return [
            cap for cap in capabilities
            if pattern_prefix.lower() in [s.lower() for s in (cap.supported_strategies or [])]
        ]


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
        application_context: 'ApplicationContext' = None,
        executor: 'ActionExecutor' = None,
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
        # capability_resolver удалён — методы перенесены в BaseBehaviorPattern
    
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

        ПАРАМЕТРЫ:
        - prompt_template: Шаблон промпта
        - variables: Переменные для подстановки

        ВОЗВРАЩАЕТ:
        - str: Отрендеренный промпт
        """
        if not prompt_template:
            return ""  # Пустой шаблон
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
        if not hasattr(self, 'schema_validator') or not self.schema_validator:
            return

        self._log_debug(f"input_contracts keys: {list(self.input_contracts.keys())}")

        registered = 0
        for cap_name, contract_class in self.input_contracts.items():
            try:
                if hasattr(contract_class, 'model_json_schema'):
                    schema = contract_class.model_json_schema()
                    properties = schema.get('properties', {})
                    required = schema.get('required', [])
                    schema_dict = {}
                    for prop_name, prop_info in properties.items():
                        schema_dict[prop_name] = {
                            'type': prop_info.get('type', 'string'),
                            'required': prop_name in required,
                            'description': prop_info.get('description', '')
                        }
                    if schema_dict:
                        # Регистрируем по full key
                        self.schema_validator.register_capability_schema(cap_name, schema_dict)
                        # Убираем _input суффикс и регистрируем отдельно
                        if cap_name.endswith('_input'):
                            base_name = cap_name[:-6]
                            self.schema_validator.register_capability_schema(base_name, schema_dict)
                        registered += 1
            except Exception as e:
                self._log_error(f"Error registering {cap_name}: {e}", exc_info=True)
        self._log_debug(f"Total schemas registered: {registered}")
    
    async def analyze_context(
        self,
        session_context: SessionContext,
        available_capabilities: list[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений."""
        raise NotImplementedError("Subclasses must implement analyze_context")
    
    async def generate_decision(
        self,
        session_context: SessionContext,
        available_capabilities: list[Capability],
        context_analysis: Dict[str, Any]
    ) -> Decision:
        """Генерация решения на основе анализа."""
        raise NotImplementedError("Subclasses must implement generate_decision")

    def _get_event_type_for_success(self) -> LogEventType:
        """Возвращает тип события для успешного выполнения паттерна."""
        return LogEventType.AGENT_START

    def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики паттерна поведения (СИНХРОННАЯ).

        ПАТТЕРНЫ НЕ ВЫПОЛНЯЮТ ДЕЙСТВИЯ напрямую — они генерируют решения через generate_decision().
        Этот метод предоставляет интерфейс для Component.execute().

        ВАЖНО: Валидация входа/выхода и метрики выполняются в Component.execute()
        Здесь только бизнес-логика.
        """
        # Паттерны поведения работают через generate_decision()
        # Этот метод предоставляет совместимость с интерфейсом Component

        # Извлекаем session_context из execution_context
        session_context = None
        if hasattr(execution_context, 'session_context'):
            session_context = execution_context.session_context

        available_capabilities = execution_context.available_capabilities if hasattr(execution_context, 'available_capabilities') else []

        # Анализируем контекст и генерируем решение (синхронное ожидание async методов)
        context_analysis = safe_async_call(self.analyze_context(session_context, available_capabilities))
        decision = safe_async_call(self.generate_decision(session_context, available_capabilities, context_analysis, execution_context))

        # Возвращаем решение в виде словаря
        return {
            "decision_type": decision.decision_type.value if hasattr(decision.decision_type, 'value') else str(decision.decision_type),
            "capability_name": decision.capability_name,
            "parameters": decision.parameters,
            "reasoning": decision.reasoning
        }
