"""
Базовый класс для всех паттернов поведения (Behavior Patterns).

АРХИТЕКТУРА:
- Наследуется от BehaviorPatternInterface
- Предоставляет унифицированный доступ к промптам/контрактам из component_config
- Все паттерны (ReAct, Planning, Evaluation, Fallback) наследуются от этого класса
"""
import logging
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel

from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.session_context.session_context import SessionContext


class BaseBehaviorPattern(BehaviorPatternInterface):
    """
    БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ПОВЕДЕНЧЕСКИХ ПАТТЕРНОВ.
    
    ПРЕДОСТАВЛЯЕТ:
    - component_name для идентификации
    - component_config с resolved_prompts/contracts
    - Унифицированные методы доступа к ресурсам
    """
    
    def __init__(self, component_name: str, component_config = None, application_context = None):
        """
        Инициализация базового паттерна.
        
        ПАРАМЕТРЫ:
        - component_name: Имя компонента (ОБЯЗАТЕЛЬНО)
        - component_config: ComponentConfig с resolved_prompts/contracts
        - application_context: Прикладной контекст
        """
        if not component_name:
            raise ValueError("component_name обязателен для инициализации паттерна")
        
        self.pattern_id = component_name
        self.component_name = component_name
        self._component_config = component_config
        self._application_context = application_context
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Кэши для быстрого доступа (загружаются из component_config)
        self._prompts: Dict[str, str] = {}
        self._input_contracts: Dict[str, Dict] = {}
        self._output_contracts: Dict[str, Dict] = {}
        
        # Загружаем ресурсы из component_config при инициализации
        if self._component_config:
            self._load_resources_from_config()
    
    def _load_resources_from_config(self):
        """
        Загружает промпты и контракты из component_config.
        
        Вызывается автоматически в __init__.
        """
        if not self._component_config:
            return
        
        # Загружаем промпты из resolved_prompts
        resolved_prompts = getattr(self._component_config, 'resolved_prompts', {})
        for key, prompt_obj in resolved_prompts.items():
            # prompt_obj может быть Prompt объектом или строкой
            if hasattr(prompt_obj, 'content'):
                self._prompts[key] = prompt_obj.content
            else:
                self._prompts[key] = str(prompt_obj)
        
        # Загружаем input контракты из resolved_input_contracts
        resolved_input = getattr(self._component_config, 'resolved_input_contracts', {})
        for key, schema in resolved_input.items():
            self._input_contracts[key] = schema
        
        # Загружаем output контракты из resolved_output_contracts
        resolved_output = getattr(self._component_config, 'resolved_output_contracts', {})
        for key, schema in resolved_output.items():
            self._output_contracts[key] = schema
    
    def get_prompt(self, key: str) -> str:
        """
        Получает промпт из кэша.
        
        ПАРАМЕТРЫ:
        - key: Ключ промпта (обычно capability_name)
        
        ВОЗВРАЩАЕТ:
        - str: Текст промпта или пустая строка если не найден
        """
        if key not in self._prompts:
            self.logger.warning(f"Промпт '{key}' не найден в кэше паттерна {self.component_name}")
            return ""
        return self._prompts[key]
    
    def get_input_contract(self, key: str) -> Dict:
        """
        Получает input контракт из кэша.
        
        ПАРАМЕТРЫ:
        - key: Ключ контракта (обычно capability_name)
        
        ВОЗВРАЩАЕТ:
        - Dict: Схема контракта или пустой словарь если не найден
        """
        if key not in self._input_contracts:
            self.logger.warning(f"Input контракт '{key}' не найден в кэше паттерна {self.component_name}")
            return {}
        return self._input_contracts[key]
    
    def get_output_contract(self, key: str) -> Dict:
        """
        Получает output контракт из кэша.
        
        ПАРАМЕТРЫ:
        - key: Ключ контракта (обычно capability_name)
        
        ВОЗВРАЩАЕТ:
        - Dict: Схема контракта или пустой словарь если не найден
        """
        if key not in self._output_contracts:
            self.logger.warning(f"Output контракт '{key}' не найден в кэше паттерна {self.component_name}")
            return {}
        return self._output_contracts[key]
    
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
    
    # === BehaviorPatternInterface methods (abstract) ===
    
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
