import os
import yaml
from typing import Dict, Optional, List, TYPE_CHECKING, Any
from pathlib import Path

if TYPE_CHECKING:
    from core.application_context.application_context import ApplicationContext
    from core.agent.components.action_executor import ActionExecutor

class BehaviorStorage:
    def __init__(
        self, 
        data_dir: str, 
        prompt_service: 'PromptService', 
        application_context: Optional['ApplicationContext'] = None,
        executor: Optional['ActionExecutor'] = None  # ← Добавляем executor
    ):
        self._data_dir = data_dir
        self._prompt_service = prompt_service
        self._application_context = application_context
        self._executor = executor  # ← Сохраняем executor
        self._cache: Dict[str, 'BehaviorPattern'] = {}

    async def load_pattern(self, pattern_id: str) -> 'BehaviorPattern':
        """
        Загружает паттерн по pattern_id (для обратной совместимости).
        
        ПАРАМЕТРЫ:
        - pattern_id: ID паттерна (например "react.v1.0.0")
        
        ВОЗВРАЩАЕТ:
        - BehaviorPattern: Экземпляр паттерна
        """
        if pattern_id in self._cache:
            return self._cache[pattern_id]

        # Загрузка из data/behaviors/{type}/{pattern_id}.yaml
        pattern = await self._load_from_fs(pattern_id)
        self._cache[pattern_id] = pattern
        return pattern

    async def load_pattern_by_component(self, component_name: str) -> 'BehaviorPattern':
        """
        Загружает паттерн по component_name (новая архитектура).
        
        ПАРАМЕТРЫ:
        - component_name: Имя компонента (например "react_pattern")
        
        ВОЗВРАЩАЕТ:
        - BehaviorPattern: Экземпляр паттерна
        """
        if component_name in self._cache:
            return self._cache[component_name]

        # Извлекаем тип паттерна из component_name (react_pattern → react)
        pattern_type = component_name.replace("_pattern", "")
        
        # Загрузка из data/behaviors/{type}/{version}.yaml
        pattern = await self._load_from_component_name(component_name, pattern_type)
        self._cache[component_name] = pattern
        return pattern

    async def _load_from_component_name(self, component_name: str, pattern_type: str) -> 'BehaviorPattern':
        """
        Загружает паттерн из FS по component_name.

        ПАРАМЕТРЫ:
        - component_name: Имя компонента (например "react_pattern")
        - pattern_type: Тип паттерна (например "react")

        ВОЗВРАЩАЕТ:
        - BehaviorPattern: Экземпляр паттерна
        """
        # Находим активную версию из registry.yaml через application_context
        if not self._application_context:
            raise RuntimeError("ApplicationContext не доступен для загрузки паттерна")

        # Получаем behavior_configs из AppConfig
        behavior_configs = getattr(self._application_context.config, 'behavior_configs', {})
        component_config = behavior_configs.get(component_name)

        # Если component_config не найден (например, для fallback_pattern без промптов),
        # передаём None — паттерн должен работать без конфигурации
        # component_config = None означает что у паттерна нет промптов/контрактов

        # Получаем класс паттерна
        pattern_class = self._get_pattern_class(pattern_type, "v1.0.0")  # Версия не важна для новой архитектуры

        # Создание экземпляра паттерна с component_name и component_config (может быть None)
        # Передаём executor для совместимости с BaseComponent
        pattern_instance = pattern_class(
            component_name=component_name,
            component_config=component_config,  # ← Может быть None!
            application_context=self._application_context,
            executor=self._executor  # ← Передаём executor из behavior_manager
        )

        return pattern_instance

    async def _load_from_fs(self, pattern_id: str) -> 'BehaviorPattern':
        """
        Загружает паттерн из FS по pattern_id (для обратной совместимости).
        
        ПАРАМЕТРЫ:
        - pattern_id: ID паттерна (например "react.v1.0.0")
        
        ВОЗВРАЩАЕТ:
        - BehaviorPattern: Экземпляр паттерна
        """
        # Разбор ID паттерна на тип и версию
        parts = pattern_id.split('.')
        if len(parts) < 2:
            raise ValueError(f"Invalid pattern ID format: {pattern_id}")

        pattern_type = parts[0]  # react, planning, etc.
        version = '.'.join(parts[1:])  # v1.0.0

        # Путь к файлу метаданных
        pattern_file = os.path.join(self._data_dir, "behaviors", pattern_type, f"{version}.yaml")

        if not os.path.exists(pattern_file):
            raise FileNotFoundError(f"Pattern file not found: {pattern_file}")

        # Загрузка YAML файла
        with open(pattern_file, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)

        # Проверка статуса
        status = metadata.get('status', 'draft')
        if status != 'active':
            raise ValueError(f"Pattern {pattern_id} is not active (status: {status})")

        # Загрузка соответствующего класса паттерна
        pattern_class = self._get_pattern_class(pattern_type, version)

        # Получаем component_config и component_name из application_context
        component_config = None
        component_name = None
        if self._application_context:
            behavior_configs = getattr(self._application_context.config, 'behavior_configs', {})
            component_name = f"{pattern_type}_pattern"
            component_config = behavior_configs.get(component_name)
        
        # Создание экземпляра паттерна с component_name и component_config
        # executor=None так как паттерны генерируют решения, а не выполняют действия
        pattern_instance = pattern_class(
            component_name=component_name,
            component_config=component_config,
            application_context=self._application_context,
            executor=None  # Паттерны не используют executor напрямую
        )

        return pattern_instance
    
    def _get_pattern_class(self, pattern_type: str, version: str):
        """Возвращает класс паттерна по его типу и версии"""
        # В реальной реализации будет динамический импорт
        # Здесь упрощенная реализация для демонстрации
        if pattern_type == "react":
            from core.agent.behaviors.react.pattern import ReActPattern
            return ReActPattern
        elif pattern_type == "planning":
            from core.agent.behaviors.planning.pattern import PlanningPattern
            return PlanningPattern
        elif pattern_type == "evaluation":
            from core.agent.behaviors.evaluation.pattern import EvaluationPattern
            return EvaluationPattern
        else:
            raise ValueError(f"Unknown pattern type: {pattern_type}")
    
    def list_patterns_by_type(self, pattern_type: str) -> List[str]:
        """Возвращает список доступных паттернов заданного типа"""
        type_dir = os.path.join(self._data_dir, "behaviors", pattern_type)
        if not os.path.exists(type_dir):
            return []
        
        patterns = []
        for filename in os.listdir(type_dir):
            if filename.endswith('.yaml'):
                version = filename[:-5]  # Убираем .yaml
                pattern_id = f"{pattern_type}.{version}"
                
                # Проверяем статус паттерна
                filepath = os.path.join(type_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    metadata = yaml.safe_load(f)
                
                status = metadata.get('status', 'draft')
                if status == 'active':
                    patterns.append(pattern_id)
        
        return patterns