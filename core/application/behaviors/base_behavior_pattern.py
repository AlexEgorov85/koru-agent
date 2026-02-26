"""
Базовый класс для всех паттернов поведения (Behavior Patterns).

АРХИТЕКТУРА:
- Наследуется от BaseComponent для единого интерфейса
- Использует методы BaseComponent.get_prompt/get_input_contract/get_output_contract
- Все паттерны (ReAct, Planning, Evaluation, Fallback) наследуются от этого класса
"""
import logging
import typing
from typing import Dict, Any, Optional

from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.session_context.session_context import SessionContext
from core.components.base_component import BaseComponent
from core.config.component_config import ComponentConfig

if typing.TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.executor import ActionExecutor
    from core.models.data.capability import Capability


class BaseBehaviorPattern(BaseComponent, BehaviorPatternInterface):
    """
    БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ПОВЕДЕНЧЕСКИХ ПАТТЕРНОВ.
    
    НАСЛЕДУЕТСЯ ОТ BaseComponent ДЛЯ:
    - Единого кэша промптов/контрактов (self.prompts, self.input_contracts, self.output_contracts)
    - Единых методов доступа (self.get_prompt(), self.get_output_contract())
    - Единой инициализации через component_config.resolved_*
    
    ПРЕДОСТАВЛЯЕТ:
    - component_name для идентификации
    - pattern_id для совместимости с BehaviorPatternInterface
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
        
        ПАРАМЕТРЫ:
        - component_name: Имя компонента (ОБЯЗАТЕЛЬНО)
        - component_config: ComponentConfig с resolved_prompts/contracts
        - application_context: Прикладной контекст
        - executor: ActionExecutor для взаимодействия (требуется BaseComponent)
        """
        if not component_name:
            raise ValueError("component_name обязателен для инициализации паттерна")
        
        # Инициализируем BaseComponent (который загружает промпты/контракты из component_config)
        BaseComponent.__init__(
            self,
            name=component_name,
            application_context=application_context,
            component_config=component_config,
            executor=executor
        )
        
        # pattern_id для совместимости с BehaviorPatternInterface
        self.pattern_id = component_name
        self.component_name = component_name
    
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
    
    async def execute(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Any:
        """
        Заглушка execute для совместимости с BaseComponent.
        
        ПАТТЕРНЫ НЕ ВЫПОЛНЯЮТ ДЕЙСТВИЯ — они генерируют решения через generate_decision().
        Этот метод нужен только для совместимости с интерфейсом BaseComponent.
        
        RAISES:
        - NotImplementedError: Всегда, так как паттерны не выполняют действия напрямую
        """
        raise NotImplementedError(
            f"BehaviorPattern не выполняет действия напрямую. "
            f"Используйте generate_decision() для получения решения. "
            f"Component: {self.component_name}"
        )
