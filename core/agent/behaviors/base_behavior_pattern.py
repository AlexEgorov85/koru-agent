"""
Базовый класс для всех паттернов поведения (Behavior Patterns).

АРХИТЕКТУРА:
- Наследуется от BaseComponent для единого интерфейса
- Использует методы BaseComponent.get_prompt/get_input_contract/get_output_contract
- Все паттерны (ReAct, Planning, Evaluation, Fallback) наследуются от этого класса
- Предоставляет общие сервисы: PromptBuilderService, CapabilityResolverService
"""
import typing
from typing import Dict, Any, Optional, List, Type

from pydantic import BaseModel

from core.agent.behaviors.base import BehaviorPatternInterface, Decision, DecisionType
from core.models.data.capability import Capability
from core.models.data.prompt import Prompt
from core.session_context.session_context import SessionContext
from core.agent.components.base_component import BaseComponent
from core.config.component_config import ComponentConfig
from core.utils.async_utils import safe_async_call

if typing.TYPE_CHECKING:
    from core.application_context.application_context import ApplicationContext
    from core.agent.components.action_executor import ActionExecutor
    from core.models.data.capability import Capability


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
        'max_rows_display': 10,      # Сколько строк показывать
        'max_chars_display': 500,    # Макс символов в промпте
        'max_observations': 3,       # Макс наблюдений в истории
    }

    def build_reasoning_prompt(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        templates: Dict[str, str],
        schema_validator: Optional[Any] = None,
        session_context=None
    ) -> str:
        """Строит полный промпт для рассуждения."""
        variables = {
            "input": self._build_input_context(context_analysis, available_capabilities),
            "goal": context_analysis.get("goal", "Неизвестная цель"),
            "step_history": self._build_step_history(
                context_analysis.get("last_steps", []),
                session_context=session_context
            ),
            # ❌ УБРАНО: "observation" — чтобы избежать дублирования
            # Данные уже включены в step_history через _extract_observations_from_step
            "available_tools": self._format_available_tools(available_capabilities, schema_validator),
            "no_progress_steps": context_analysis.get("no_progress_steps", 0),
            "consecutive_errors": context_analysis.get("consecutive_errors", 0)
        }
        return self._render_prompt(templates.get("user", ""), variables)
    
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
    
    def _build_step_history(
        self, 
        last_steps: list, 
        session_context=None
    ) -> str:
        """Формирует читаемую историю шагов с реальными данными."""
        if not last_steps:
            return "Шаги не выполнены"
        
        print(f"[DEBUG _build_step_history] last_steps count: {len(last_steps)}")
        
        step_lines = []
        for i, step in enumerate(last_steps[-5:], 1):  # Последние 5 шагов
            if hasattr(step, 'capability_name'):
                # Это объект AgentStep
                capability = step.capability_name
                summary = step.summary or "Без описания"
                status = step.status.value if hasattr(step.status, 'value') else str(step.status)
                
                # КРИТИЧНО: Получаем реальные данные из observation_item_ids
                observation_text = self._extract_observations_from_step(
                    session_context, 
                    step.observation_item_ids if hasattr(step, 'observation_item_ids') else []
                )
                
                # Формируем читаемую строку
                step_text = f"{i}. {capability}\n"
                step_text += f"   Результат: {observation_text}\n"
                step_text += f"   Статус: {status}"
                
            elif isinstance(step, dict):
                # Это словарь (новый формат)
                capability = step.get('capability_name', step.get('capability', 'unknown'))
                summary = step.get('summary', '')
                
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
                step_text += f"   Результат: {observation[:500] if observation else 'Нет данных'}\n"
                step_text += f"   Статус: {status}"
            else:
                # Fallback для строки
                step_text = f"{i}. {str(step)[:200]}"
            
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
        print(f"[DEBUG _extract_observations_from_step] observation_item_ids={observation_item_ids}")
        if not observation_item_ids:
            return "Нет наблюдений"
        
        if not session_context or not hasattr(session_context, 'data_context'):
            return f"ID наблюдений: {observation_item_ids[:2]}..."
        
        observations = []
        total_rows = 0
        
        for obs_id in observation_item_ids[:self.DISPLAY_LIMITS['max_observations']]:
            try:
                item = session_context.data_context.get_item(
                    obs_id, 
                    raise_on_missing=False
                )
                
                if item and hasattr(item, 'content'):
                    content = item.content
                    
                    # Извлекаем полезную информацию
                    if isinstance(content, dict):
                        # Для book_library и подобных: извлекаем rows
                        if 'rows' in content:
                            rows = content['rows']
                            total_rows += len(rows)
                            
                            # УМНАЯ ОБРАБОТКА ПО РАЗМЕРУ
                            if len(rows) <= self.DATA_SIZE_LIMITS['small']:
                                # Маленькие данные → показываем всё
                                observations.extend(self._format_small_data(rows))
                            elif len(rows) <= self.DATA_SIZE_LIMITS['medium']:
                                # Средние данные → статистика + первые N
                                observations.append(f"📊 Найдено {len(rows)} записей")
                                observations.append("📋 Первые 5:")
                                observations.extend(self._format_small_data(rows[:5]))
                                observations.append(f"... и ещё {len(rows) - 5} записей")
                            elif len(rows) <= self.DATA_SIZE_LIMITS['large']:
                                # Большие данные → только статистика
                                observations.append(f"📊 Найдено {len(rows)} записей (большие данные)")
                                observations.append("⚠️ Для полного анализа используйте data_analysis.analyze_step_data")
                                observations.append("📋 Пример (3 записи):")
                                observations.extend(self._format_small_data(rows[:3]))
                            else:
                                # Очень большие данные → только мета
                                observations.append(f"📊 Найдено {len(rows)} записей (очень большие данные)")
                                observations.append("💡 Вызовите data_analysis.analyze_step_data для суммаризации")
                        
                        elif 'result' in content:
                            result_str = str(content['result'])[:self.DISPLAY_LIMITS['max_chars_display']]
                            observations.append(f"- {result_str}")
                        elif 'data' in content:
                            data_str = str(content['data'])[:self.DISPLAY_LIMITS['max_chars_display']]
                            observations.append(f"- {data_str}")
                        else:
                            content_str = str(content)[:self.DISPLAY_LIMITS['max_chars_display']]
                            observations.append(f"- {content_str}")
                    else:
                        content_str = str(content)[:self.DISPLAY_LIMITS['max_chars_display']]
                        observations.append(f"- {content_str}")
                        
            except Exception as e:
                observations.append(f"- [Ошибка чтения {obs_id}: {e}]")
        
        # Добавляем итоговую статистику если данных много
        if total_rows > self.DATA_SIZE_LIMITS['medium']:
            observations.append(f"\n⚠️ ОБЩИЙ ОБЪЁМ: {total_rows} строк")
            observations.append("💡 Рекомендация: Используйте data_analysis.analyze_step_data")
        
        if observations:
            return "\n".join(observations)
        return "Нет доступных данных"

    def _format_small_data(self, rows: list) -> list:
        """Форматирование небольших данных для отображения."""
        formatted = []
        for row in rows[:self.DISPLAY_LIMITS['max_rows_display']]:
            if isinstance(row, dict):
                # Форматируем как читаемую строку
                row_parts = []
                for k, v in list(row.items())[:5]:  # Макс 5 полей
                    row_parts.append(f"{k}: {v}")
                row_str = ", ".join(row_parts)
                formatted.append(f"   - {row_str}")
            else:
                formatted.append(f"   - {str(row)[:150]}")
        return formatted
    
    def _format_available_tools(self, available_capabilities: List[Capability], schema_validator: Optional[Any] = None) -> str:
        """Форматирует список инструментов с параметрами."""
        lines = []
        for cap in available_capabilities:
            name = cap.name if hasattr(cap, 'name') else cap.get('name', 'unknown')
            description = cap.description if hasattr(cap, 'description') else cap.get('description', 'no description')
            params_schema = None
            if schema_validator:
                schema_obj = schema_validator.get_capability_schema(name)
                if schema_obj and hasattr(schema_obj, 'to_dict'):
                    params_schema = schema_obj.to_dict()
                else:
                    params_schema = schema_obj
            line = f"- {name}: {description}"
            if params_schema and isinstance(params_schema, dict):
                params_list = []
                for param_name, param_info in params_schema.items():
                    param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else 'string'
                    required = param_info.get('required', False) if isinstance(param_info, dict) else False
                    req_mark = "(required)" if required else "(optional)"
                    params_list.append(f"{param_name}: {param_type} {req_mark}")
                if params_list:
                    line += "\n    Параметры:"
                    for p in params_list:
                        line += f"\n      - {p}"
            lines.append(line)
        return "\n".join(lines)
    
    def _render_prompt(self, template: str, variables: Dict[str, Any]) -> str:
        """Рендерит шаблон с подстановкой переменных."""
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered


class CapabilityResolverService:
    """Сервис для разрешения и валидации capability."""
    
    def find_capability(self, available_capabilities: List[Capability], capability_name: str) -> Optional[Capability]:
        """Ищет capability по имени."""
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
                    if '.' in cap.skill_name and cap.skill_name.split('.')[0] == prefix:
                        return cap
        # 3. Частичное совпадение
        for cap in available_capabilities:
            if capability_name.lower() in cap.name.lower():
                return cap
        # 4. Поиск по supported_strategies
        for cap in available_capabilities:
            supported = [s.lower() for s in (cap.supported_strategies or [])]
            if 'react' in supported or 'planning' in supported:
                return cap
        return None
    
    def validate_parameters(self, capability: Capability, parameters: Dict[str, Any], schema_validator: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Валидирует параметры capability."""
        if not schema_validator:
            return parameters
        try:
            validated = schema_validator.validate_parameters(
                capability=capability,
                raw_params=parameters,
                context=str(context)
            )
            return validated if validated else parameters
        except Exception:
            return {"input": parameters.get("input", "Продолжить выполнение задачи")}
    
    def register_capability_schemas(
        self,
        available_capabilities: List[Capability],
        schema_validator: Any,
        input_contracts: Dict[str, Any],
        data_repository: Optional[Any] = None
    ) -> None:
        """Регистрирует схемы входных параметров для всех capability."""
        for cap in available_capabilities:
            schema = None
            if input_contracts and cap.name in input_contracts:
                schema = input_contracts[cap.name]
            elif data_repository:
                try:
                    contract_version = cap.meta.get('contract_version', 'v1.0.0')
                    schema = data_repository.get_contract_schema(cap.name, contract_version, "input")
                except Exception:
                    pass
            if schema:
                params_schema = {}
                if hasattr(schema, 'to_dict'):
                    to_dict_result = schema.to_dict()
                    if isinstance(to_dict_result, dict):
                        params_schema = to_dict_result
                elif hasattr(schema, 'model_json_schema'):
                    schema_dict = schema.model_json_schema()
                    properties = schema_dict.get('properties', {})
                    required = schema_dict.get('required', [])
                    for prop_name, prop_info in properties.items():
                        params_schema[prop_name] = {'type': prop_info.get('type', 'string'), 'required': prop_name in required}
                elif isinstance(schema, dict):
                    properties = schema.get('properties', {})
                    required = schema.get('required', [])
                    if isinstance(properties, dict):
                        for prop_name, prop_info in properties.items():
                            params_schema[prop_name] = {'type': prop_info.get('type', 'string') if isinstance(prop_info, dict) else 'string', 'required': prop_name in required}
                if params_schema:
                    schema_validator.register_capability_schema(cap.name, params_schema)
    
    def filter_capabilities(self, capabilities: List[Capability], pattern_id: str) -> List[Capability]:
        """Фильтрует capability по supported_strategies."""
        pattern_prefix = pattern_id.split('.')[0]
        if "_pattern" in pattern_prefix:
            pattern_prefix = pattern_prefix.replace("_pattern", "")
        return [cap for cap in capabilities if pattern_prefix.lower() in [s.lower() for s in (cap.supported_strategies or [])]]
    
    def exclude_capability(self, capabilities: List[Capability], exclude_name: str) -> List[Capability]:
        """Исключает capability по имени."""
        return [cap for cap in capabilities if cap.name != exclude_name]


class BaseBehaviorPattern(BaseComponent, BehaviorPatternInterface):
    """
    БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ПОВЕДЕНЧЕСКИХ ПАТТЕРНОВ.

    НАСЛЕДУЕТСЯ ОТ BaseComponent ДЛЯ:
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
        application_context: ApplicationContext = None,
        executor: 'ActionExecutor' = None,
        event_bus = None  # ← Только для логирования
    ):
        """
        Инициализация базового паттерна.
        """
        if not component_name:
            raise ValueError("component_name обязателен для инициализации паттерна")

        BaseComponent.__init__(
            self,
            name=component_name,
            application_context=application_context,
            component_config=component_config,
            executor=executor,
            event_bus=event_bus
        )

        # pattern_id для совместимости
        self.pattern_id = component_name
        self.component_name = component_name
        
        # === ОБЩИЕ СЕРВИСЫ ===
        self.prompt_builder = PromptBuilderService()
        self.capability_resolver = CapabilityResolverService()
    
    def get_prompt(self, key: str) -> Prompt:
        """
        Получает промпт из кэша BaseComponent.

        ДЕЛЕГИРУЕТ: BaseComponent.get_prompt()
        """
        return super().get_prompt(key)

    def get_input_contract(self, key: str) -> Type[BaseModel]:
        """
        Получает input контракт из кэша BaseComponent.

        ДЕЛЕГИРУЕТ: BaseComponent.get_input_contract()
        """
        return super().get_input_contract(key)

    def get_output_contract(self, key: str) -> Type[BaseModel]:
        """
        Получает output контракт из кэша BaseComponent.

        ДЕЛЕГИРУЕТ: BaseComponent.get_output_contract()
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
        rendered = prompt_template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered
    
    async def initialize(self) -> bool:
        """
        Инициализация паттерна.

        Промпты/контракты уже загружены в component_config.resolved_* на уровне ApplicationContext.
        """
        # Вызываем инициализацию BaseComponent (загружает из component_config.resolved_*)
        success = await BaseComponent.initialize(self)
        return success
    
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

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения паттерна."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.AGENT_STARTED

    def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики паттерна поведения (СИНХРОННАЯ).

        ПАТТЕРНЫ НЕ ВЫПОЛНЯЮТ ДЕЙСТВИЯ напрямую — они генерируют решения через generate_decision().
        Этот метод предоставляет интерфейс для BaseComponent.execute().

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        # Паттерны поведения работают через generate_decision()
        # Этот метод предоставляет совместимость с интерфейсом BaseComponent

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
