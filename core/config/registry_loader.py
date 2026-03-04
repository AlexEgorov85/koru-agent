"""
Загрузчик конфигурации реестра с поддержкой миграции и валидации.
"""
import yaml
from pathlib import Path
from typing import Dict, Any
from core.config.models import RegistryConfig, ComponentType


class RegistryLoader:
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path

    def load(self, profile: str = "prod") -> RegistryConfig:
        with open(self.registry_path, encoding='utf-8') as f:
            raw = yaml.safe_load(f)

        # Поддержка старого формата (без capability_types) — для обратной совместимости
        if 'capability_types' not in raw:
            raw['capability_types'] = self._migrate_capability_types(raw)
            # Сохраняем мигрированную версию (опционально)
            # self._save_migrated_registry(raw)

        # Валидация через Pydantic
        return RegistryConfig(**raw)

    def _migrate_capability_types(self, raw: dict) -> dict:
        """
        Миграция старого формата в новый с явными типами.
        Использует ЭВРИСТИКУ только для миграции (не для рантайма!).
        """
        capability_types = {}

        # Эвристика ТОЛЬКО для миграции (не для рантайма!)
        heuristic_map = {
            'planning.': 'skill',
            'analysis.': 'skill',
            'reasoning.': 'skill',
            'sql_generation.': 'service',  # sql_generation_service is a service
            'file_tool.': 'tool',
            'book_library.': 'skill',  # book_library is a skill
            'llm.': 'service',
            'embedding.': 'service',
            'react.': 'behavior',
            'planning_pattern.': 'behavior',
            'behavior.': 'behavior'
        }

        # Собираем все capability из активных промптов
        capabilities = set(raw.get('active_prompts', {}).keys())
        
        # Собираем capability из активных контрактов (обрабатываем сложные структуры)
        for cap_dir in raw.get('active_contracts', {}).keys():
            # Если значение - словарь (например, {'input': 'v1.0.0', 'output': 'v1.0.0'})
            cap_dir_val = raw['active_contracts'][cap_dir]
            if isinstance(cap_dir_val, dict):
                # Это сложная структура, используем ключ как capability
                cap = cap_dir
            else:
                # Это простая строка, разделяем по последней точке
                cap = cap_dir.rsplit('.', 1)[0]
            capabilities.add(cap)

        # Также собираем capability из компонентных конфигураций
        sections = ['services', 'skills', 'tools', 'strategies', 'behaviors']
        for section in sections:
            if section in raw:
                for comp_name, comp_config in raw[section].items():
                    if isinstance(comp_config, dict):
                        # Собираем capability из prompt_versions
                        for cap in comp_config.get('prompt_versions', {}).keys():
                            capabilities.add(cap)

                        # Собираем capability из input_contract_versions
                        for cap in comp_config.get('input_contract_versions', {}).keys():
                            capabilities.add(cap)

                        # Собираем capability из output_contract_versions
                        for cap in comp_config.get('output_contract_versions', {}).keys():
                            capabilities.add(cap)

        # Применяем эвристику для миграции
        for cap in capabilities:
            matched = False
            for prefix, comp_type in heuristic_map.items():
                if cap.startswith(prefix):
                    try:
                        capability_types[cap] = ComponentType(comp_type)
                    except ValueError:
                        # Если тип компонента недопустим, используем 'skill' по умолчанию
                        capability_types[cap] = ComponentType.SKILL
                    matched = True
                    break
            if not matched:
                # Не удалось определить — помечаем как 'skill' по умолчанию
                capability_types[cap] = ComponentType.SKILL
                # Предупреждение выводится через print (конфигурация загружается до EventBus)
                print(f"[WARN] Предположен тип 'skill' для capability '{cap}'. Проверьте и исправьте вручную!")

        return capability_types