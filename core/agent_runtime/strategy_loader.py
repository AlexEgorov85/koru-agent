"""Загрузчик паттернов мышления для агента."""
import yaml
import importlib
from typing import Dict, Type, Any
from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface
from core.agent_runtime.thinking_patterns.code_analysis.strategy import CodeAnalysisThinkingPattern
from core.agent_runtime.thinking_patterns.evaluation import EvaluationThinkingPattern
from core.agent_runtime.thinking_patterns.fallback import FallbackThinkingPattern
from core.agent_runtime.thinking_patterns.plan_execution.strategy import PlanExecutionThinkingPattern
from core.agent_runtime.thinking_patterns.planning.strategy import PlanningThinkingPattern
from core.agent_runtime.thinking_patterns.react.strategy import ReActThinkingPattern


class ThinkingPatternLoader:
    """
    ThinkingPatternLoader - загрузчик паттернов мышления для агента.
    
    НАЗНАЧЕНИЕ:
    - Обеспечивает динамическую загрузку паттернов мышления выполнения агента
    - Позволяет регистрировать паттерны мышления из конфигурационных файлов
    - Обеспечивает централизованное управление паттернами мышления
    
    ВОЗМОЖНОСТИ:
    - Загрузка паттернов мышления из YAML-конфигурационных файлов
    - Регистрация паттернов мышления по умолчанию
    - Создание экземпляров паттернов мышления
    - Регистрация новых паттернов мышления во время выполнения
    - Проверка соответствия интерфейсу паттерна мышления
    
    ПРИМЕРЫ РАБОТЫ:
    # Создание загрузчика
    loader = ThinkingPatternLoader()
    
    # Создание экземпляра паттерна мышления
    pattern = loader.create_pattern("react")
    
    # Загрузка из конфигурационного файла
    loader = ThinkingPatternLoader(config_path="config/thinking_patterns.yaml")
    
    # Регистрация нового паттерна мышления
    loader.register_pattern("custom", CustomThinkingPattern)
    
    # Получение класса паттерна мышления
    pattern_class = loader.get_pattern_class("planning")
    """
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self._patterns: Dict[str, Type[AgentThinkingPatternInterface]] = {}
        
        if config_path:
            self.load_from_config(config_path)
        else:
            # Загружаем паттерны мышления по умолчанию
            self._register_default_patterns()
    
    def _register_default_patterns(self):
        """Регистрация паттернов мышления по умолчанию."""
        self._patterns = {
            "react": ReActThinkingPattern,
            "planning": PlanningThinkingPattern,
            "plan_execution": PlanExecutionThinkingPattern,
            "code_analysis": CodeAnalysisThinkingPattern,
            "evaluation": EvaluationThinkingPattern,
            "fallback": FallbackThinkingPattern
        }
    
    def load_from_config(self, config_path: str):
        """Запись паттернов мышления из YAML-конфига."""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        patterns_config = config.get('thinking_patterns', {})
        
        for pattern_name, pattern_config in patterns_config.items():
            module_path = pattern_config['module']
            class_name = pattern_config['class']
            
            # Импортируем модуль
            module = importlib.import_module(module_path)
            
            # Получаем класс паттерна мышления
            pattern_class = getattr(module, class_name)
            
            # Проверяем, что класс реализует интерфейс паттерна мышления
        if not issubclass(pattern_class, AgentThinkingPatternInterface):
            raise ValueError(f"Класс {pattern_class} не реализует AgentThinkingPatternInterface")
        
            self._patterns[pattern_name] = pattern_class
    
    def get_pattern_class(self, pattern_name: str) -> Type[AgentThinkingPatternInterface]:
        """Получить класс паттерна мышления по имени."""
        if pattern_name not in self._patterns:
            raise ValueError(f"Паттерн мышления '{pattern_name}' не найден. Доступные: {list(self._patterns.keys())}")
        
        return self._patterns[pattern_name]
    
    def create_pattern(self, pattern_name: str, **kwargs) -> AgentThinkingPatternInterface:
        """Создать экземпляр паттерна мышления."""
        pattern_class = self.get_pattern_class(pattern_name)
        
        # Создаем экземпляр класса с переданными аргументами
        return pattern_class(**kwargs)
    
    def register_pattern(self, pattern_name: str, pattern_class: Type[AgentThinkingPatternInterface]):
        """Зарегистрировать новый паттерн мышления."""
        if not issubclass(pattern_class, AgentThinkingPatternInterface):
            raise ValueError(f"Класс {pattern_class} не реализует AgentThinkingPatternInterface")
        
        self._patterns[pattern_name] = pattern_class
