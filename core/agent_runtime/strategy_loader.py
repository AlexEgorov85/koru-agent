"""Загрузчик паттернов мышления для агента с использованием новой архитектуры на основе атомарных действий и компонуемых паттернов."""

from typing import Dict, Type, Any
from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface

# Импорты для новой архитектуры
from core.composable_patterns.registry import PatternRegistry
from core.composable_patterns.patterns import (
    ReActPattern, PlanAndExecutePattern, ToolUsePattern, ReflectionPattern,
    CodeAnalysisPattern, DatabaseQueryPattern, ResearchPattern
)
from core.domain_management.domain_manager import DomainManager

# Импорты для работы с YAML и модулями
import yaml
import importlib

logger = __import__('logging').getLogger(__name__)


class ThinkingPatternLoader:
    """
    ThinkingPatternLoader - загрузчик паттернов мышления для агента.
    
    НАЗНАЧЕНИЕ:
    - Обеспечивает динамическую загрузку паттернов мышления выполнения агента
    - Позволяет регистрировать паттерны мышления из конфигурационных файлов
    - Обеспечивает централизованное управление паттернами мышления
    - Поддерживает новую архитектуру с атомарными действиями и компонуемыми паттернами
    
    ВОЗМОЖНОСТИ:
    - Загрузка паттернов мышления из YAML-конфигурационных файлов
    - Создание экземпляров паттернов мышления
    - Регистрация новых паттернов мышления во время выполнения
    - Проверка соответствия интерфейсу паттерна мышления
    - Регистрация компонуемых паттернов
    - Управление доменными паттернами
    """
    
    def __init__(self, config_path: str = None, use_new_architecture: bool = True):
        self.config_path = config_path
        self.use_new_architecture = use_new_architecture
        self._patterns: Dict[str, Type[AgentThinkingPatternInterface]] = {}
        self.pattern_registry = None
        self.domain_manager = DomainManager()
        
        if config_path:
            self.load_from_config(config_path)
        else:
            # Загружаем паттерны мышления по умолчанию
            self._register_default_patterns()
            
            if use_new_architecture:
                # Инициализируем новую архитектуру
                self._setup_new_architecture()
    
    def _setup_new_architecture(self):
        """Настройка новой архитектуры с компонуемыми паттернами."""
        self.pattern_registry = PatternRegistry()
        
        # Регистрация универсальных компонуемых паттернов
        self.pattern_registry.register_pattern("react_composable", ReActPattern)
        self.pattern_registry.register_pattern("plan_and_execute_composable", PlanAndExecutePattern)
        self.pattern_registry.register_pattern("tool_use_composable", ToolUsePattern)
        self.pattern_registry.register_pattern("reflection_composable", ReflectionPattern)
        
        # Регистрация доменных паттернов
        self.pattern_registry.register_domain_pattern("code_analysis", "default", CodeAnalysisPattern)
        self.pattern_registry.register_domain_pattern("database_query", "default", DatabaseQueryPattern)
        self.pattern_registry.register_domain_pattern("research", "default", ResearchPattern)
    
    def _register_default_patterns(self):
        """Регистрация паттернов мышления по умолчанию."""
        self._patterns = {}
    
    def load_from_config(self, config_path: str):
        """Загрузка паттернов мышления из YAML-конфига."""
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
    
    def get_pattern_registry(self) -> 'PatternRegistry':
        """Получить реестр компонуемых паттернов."""
        if self.pattern_registry is None:
            self._setup_new_architecture()
        return self.pattern_registry
    
    def get_domain_manager(self) -> 'DomainManager':
        """Получить менеджер доменов."""
        return self.domain_manager
    
    def get_pattern_for_domain(self, domain: str, task_description: str = "") -> str:
        """
        Получить подходящий паттерн для указанного домена и задачи.
        
        Args:
            domain: Домен задачи
            task_description: Описание задачи для более точного выбора паттерна
            
        Returns:
            Имя паттерна для использования
        """
        # Сначала пробуем найти специфичный паттерн для домена
        if self.pattern_registry:
            domain_patterns = self.pattern_registry.get_domain_patterns(domain)
            if domain_patterns:
                # Для простоты возвращаем первый найденный паттерн
                # В реальной реализации здесь может быть более сложная логика выбора
                return domain_patterns[0].split('.', 1)[1]  # Убираем префикс домена
        
        # Используем доменный менеджер для получения стандартного паттерна
        return self.domain_manager.get_domain_pattern(domain)
    
    def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """
        Адаптироваться к задаче: определить домен и выбрать подходящий паттерн.
        
        Args:
            task_description: Описание задачи
            
        Returns:
            Словарь с информацией о домене и паттерне
        """
        domain = self.domain_manager.classify_task(task_description)
        pattern = self.get_pattern_for_domain(domain, task_description)
        
        return {
            "domain": domain,
            "pattern": pattern,
            "domain_config": self.domain_manager.get_domain_config(domain)
        }