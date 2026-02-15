import os
import yaml
from typing import Dict, Optional, List
from pathlib import Path

class BehaviorStorage:
    def __init__(self, data_dir: str, prompt_service: 'PromptService'):
        self._data_dir = data_dir
        self._prompt_service = prompt_service
        self._cache: Dict[str, 'BehaviorPattern'] = {}
    
    async def load_pattern(self, pattern_id: str) -> 'BehaviorPattern':
        if pattern_id in self._cache:
            return self._cache[pattern_id]
        
        # Загрузка из data/behaviors/{type}/{pattern_id}.yaml
        pattern = await self._load_from_fs(pattern_id)
        self._cache[pattern_id] = pattern
        return pattern
    
    async def _load_from_fs(self, pattern_id: str) -> 'BehaviorPattern':
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
        # В реальной реализации здесь будет динамический импорт
        # В зависимости от типа паттерна
        pattern_class = self._get_pattern_class(pattern_type, version)
        
        # Создание экземпляра паттерна
        pattern_instance = pattern_class(
            pattern_id=pattern_id,
            metadata=metadata,
            prompt_service=self._prompt_service
        )
        
        return pattern_instance
    
    def _get_pattern_class(self, pattern_type: str, version: str):
        """Возвращает класс паттерна по его типу и версии"""
        # В реальной реализации будет динамический импорт
        # Здесь упрощенная реализация для демонстрации
        if pattern_type == "react":
            from core.application.behaviors.react.pattern import ReActPattern
            return ReActPattern
        elif pattern_type == "planning":
            from core.application.behaviors.planning.pattern import PlanningPattern
            return PlanningPattern
        elif pattern_type == "evaluation":
            from core.application.behaviors.evaluation.pattern import EvaluationPattern
            return EvaluationPattern
        elif pattern_type == "fallback":
            from core.application.behaviors.fallback.pattern import FallbackPattern
            return FallbackPattern
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