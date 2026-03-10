"""
Базовый класс для всех паттернов поведения (Behavior Patterns).

АРХИТЕКТУРА:
- Наследуется от BaseComponent для единого интерфейса
- Использует методы BaseComponent.get_prompt/get_input_contract/get_output_contract
- Все паттерны (ReAct, Planning, Evaluation, Fallback) наследуются от этого класса
- Предоставляет общие сервисы: PromptBuilderService, CapabilityResolverService
"""
import typing
from typing import Dict, Any, Optional, List

from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.session_context.session_context import SessionContext
from core.components.base_component import BaseComponent
from core.config.component_config import ComponentConfig

if typing.TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.executor import ActionExecutor
    from core.models.data.capability import Capability


# ============================================================================
# ОБЩИЕ СЕРВИСЫ ДЛЯ ВСЕХ ПАТТЕРНОВ
# ============================================================================

class PromptBuilderService:
    """Сервис для построения структурированных промптов."""
    
    def build_reasoning_prompt(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        templates: Dict[str, str],
        schema_validator: Optional[Any] = None
    ) -> str:
        """Строит полный промпт для рассуждения."""
        variables = {
            "input": self._build_input_context(context_analysis, available_capabilities),
            "goal": context_analysis.get("goal", "Неизвестная цель"),
            "step_history": self._build_step_history(context_analysis.get("last_steps", [])),
            "observation": self._extract_last_observation(context_analysis.get("last_steps", [])),
            "available_tools": self._format_available_tools(available_capabilities, schema_validator),
            "no_progress_steps": context_analysis.get("no_progress_steps", 0),
            "consecutive_errors": context_analysis.get("consecutive_errors", 0)
        }
        return self._render_prompt(templates.get("user", ""), variables)
    
    def _build_input_context(self, context_analysis: Dict[str, Any], available_capabilities: List[Capability]) -> str:
        """Формирует секцию {input} для промпта."""
        goal = context_analysis.get("goal", "Неизвестная цель")
        last_steps = context_analysis.get("last_steps", [])
        parts = [
            f"ЦЕЛЬ: {goal}",
            f"Шагов выполнено: {len(last_steps)}",
            f"Шагов без прогресса: {context_analysis.get('no_progress_steps', 0)}",
            f"Ошибок подряд: {context_analysis.get('consecutive_errors', 0)}"
        ]
        if last_steps:
            parts.append("\nПОСЛЕДНИЕ ШАГИ:")
            for i, step in enumerate(last_steps[-3:], 1):
                parts.append(f"  {i}. {step}")
        return "\n".join(parts)
    
    def _build_step_history(self, last_steps: list) -> str:
        """Формирует читаемую историю шагов."""
        if not last_steps:
            return "Шаги не выполнены"
        step_lines = []
        for i, step in enumerate(last_steps[-3:], 1):
            if isinstance(step, dict):
                capability = step.get('capability', 'unknown')
                summary = step.get('summary', '')
                obs = step.get('observation', '')
                step_text = f"{capability}: {summary}"
                if obs:
                    step_text += f" → {obs[:100]}"
                step_lines.append(f"{i}. {step_text}")
            else:
                step_lines.append(f"{i}. {step}")
        return "\n".join(step_lines)
    
    def _extract_last_observation(self, last_steps: list) -> str:
        """Извлекает последнее наблюдение."""
        if not last_steps:
            return "Нет наблюдений"
        last_step = last_steps[-1]
        if isinstance(last_step, dict):
            obs = last_step.get('observation', '')
            if obs:
                return obs
        summary = last_step.get('summary', '') if isinstance(last_step, dict) else str(last_step)
        return summary if summary else "Нет наблюдений"
    
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
        application_context: 'ApplicationContext' = None,
        executor: 'ActionExecutor' = None
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
            executor=executor
        )

        # pattern_id для совместимости
        self.pattern_id = component_name
        self.component_name = component_name
        
        # === ОБЩИЕ СЕРВИСЫ ===
        self.prompt_builder = PromptBuilderService()
        self.capability_resolver = CapabilityResolverService()
    
    def get_prompt(self, key: str) -> str:
        """
        Получает промпт из кэша BaseComponent.
        
        ДЕЛЕГИРУЕТ: BaseComponent.get_prompt()
        """
        return super().get_prompt(key)
    
    def get_input_contract(self, key: str) -> Dict:
        """
        Получает input контракт из кэша BaseComponent.
        
        ДЕЛЕГИРУЕТ: BaseComponent.get_input_contract()
        """
        return super().get_input_contract(key)
    
    def get_output_contract(self, key: str) -> Dict:
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
    ) -> BehaviorDecision:
        """Генерация решения на основе анализа."""
        raise NotImplementedError("Subclasses must implement generate_decision")

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения паттерна."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.AGENT_STARTED

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики паттерна поведения.

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
        
        # Анализируем контекст и генерируем решение
        context_analysis = await self.analyze_context(session_context, available_capabilities)
        decision = await self.generate_decision(session_context, available_capabilities, context_analysis)
        
        # Возвращаем решение в виде словаря
        return {
            "decision_type": decision.decision_type.value if hasattr(decision.decision_type, 'value') else str(decision.decision_type),
            "capability_name": decision.capability_name,
            "parameters": decision.parameters,
            "reasoning": decision.reasoning
        }
