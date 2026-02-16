"""
Реализация источника данных с файловой системой и явными типами компонентов.
"""
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from core.infrastructure.storage.data_source import IDataSource
from core.models.prompt import Prompt, PromptStatus, ComponentType
from core.models.contract import Contract, ContractDirection
from core.config.models import RegistryConfig
import yaml
import re


class FileSystemDataSource(IDataSource):
    """
    Реализация источника данных с КАНОНИЧЕСКОЙ структурой путей.
    Тип компонента получается ЯВНО из конфигурации, НЕ через инференс.
    """
    
    # Маппинг типа компонента → имя каталога
    TYPE_TO_DIR = {
        ComponentType.SKILL: "skill",
        ComponentType.TOOL: "tool", 
        ComponentType.SERVICE: "service",
        ComponentType.BEHAVIOR: "behavior"
    }
    
    def __init__(self, base_dir: Path, registry_config: RegistryConfig):
        self.base_dir = base_dir.resolve()
        self.prompts_dir = self.base_dir / "prompts"
        self.contracts_dir = self.base_dir / "contracts"
        self.registry_config = registry_config  # ← Единый источник маппинга типов
    
    def _get_component_type(self, capability: str) -> ComponentType:
        """
        Получает тип компонента ИЗ КОНФИГУРАЦИИ.
        Никакого инференса по префиксу!
        """
        if capability not in self.registry_config.capability_types:
            raise ConfigurationError(
                f"Тип компонента для capability '{capability}' не объявлен в конфигурации.\n"
                f"Добавьте запись в data/registry.yaml -> capability_types:\n"
                f"  {capability}: skill|tool|service|behavior"
            )
        
        type_str = self.registry_config.capability_types[capability]
        try:
            return ComponentType(type_str)
        except ValueError:
            raise ConfigurationError(
                f"Неверный тип компонента '{type_str}' для capability '{capability}'. "
                f"Допустимые значения: {', '.join(t.value for t in ComponentType)}"
            )
    
    def _build_prompt_path(self, capability: str, version: str) -> Path:
        """
        Строит КАНОНИЧЕСКИЙ путь к файлу промпта.
        Формат: prompts/{type}/{capability_base}/{capability}_v{version}.yaml
        Пример: prompts/skill/planning/planning.create_plan_v1.0.0.yaml
        """
        component_type = self._get_component_type(capability)
        type_dir = self.TYPE_TO_DIR[component_type]
        
        # Разбиваем capability на части: "planning.create_plan" -> "planning", "create_plan"
        capability_parts = capability.split('.')
        if len(capability_parts) >= 2:
            capability_base = capability_parts[0]  # "planning"
        else:
            capability_base = capability  # fallback на случай, если capability не содержит точки
            
        # Обработка версии: если начинается с 'v', используем как есть, иначе добавляем 'v'
        if version.startswith('v'):
            version_part = version[1:]  # Убираем 'v' из начала версии для формата
        else:
            version_part = version
        filename = f"{capability}_v{version_part}.yaml"
        return self.prompts_dir / type_dir / capability_base / filename
    
    async def load_prompt(self, capability: str, version: str) -> Prompt:
        """Загружает промпт как полноценный объект"""
        path = self._build_prompt_path(capability, version)
        
        if not path.exists():
            # Чёткая ошибка вместо перебора 10 путей
            expected_dirs = [self.prompts_dir / d for d in self.TYPE_TO_DIR.values()]
            raise FileNotFoundError(
                f"Промпт не найден по КАНОНИЧЕСКОМУ пути:\n"
                f"  {path}\n\n"
                f"Проверьте:\n"
                f"  1. Существует ли файл?\n"
                f"  2. Объявлен ли тип компонента для '{capability}' в registry.yaml?\n"
                f"  3. Лежит ли файл в правильном каталоге: {self.prompts_dir}/<type>/\n"
                f"     Допустимые каталоги: {', '.join(self.TYPE_TO_DIR.values())}"
            )
        
        # Загружаем и парсим как объект Prompt
        with open(path, encoding='utf-8') as f:
            raw = yaml.safe_load(f)
        
        # Добавляем тип компонента из конфигурации (если отсутствует в файле)
        if 'component_type' not in raw:
            raw['component_type'] = self._get_component_type(capability).value
        
        # Валидация через Pydantic
        try:
            return Prompt(**raw)
        except Exception as e:
            raise ValueError(f"Ошибка валидации промпта {capability}@{version} из {path}: {e}")
    
    async def list_prompts(self) -> List[Prompt]:
        """
        Сканирует ВСЮ директорию prompts/ и возвращает список объектов Prompt.
        Выполняется ОДИН РАЗ при старте системы.
        """
        prompts = []
        errors = []
        
        # Сканируем все каталоги типов
        for component_type, type_dir_name in self.TYPE_TO_DIR.items():
            type_dir = self.prompts_dir / type_dir_name
            if not type_dir.exists():
                continue
            
            # Ищем файлы по шаблону: {capability}_v{version}.yaml
            for file_path in type_dir.glob("*.yaml"):
                try:
                    # Парсим имя файла
                    match = re.match(r'^(.+)_v(\d+\.\d+\.\d+)\.yaml$', file_path.name)
                    if not match:
                        errors.append(f"Пропущен файл с неверным именем: {file_path.name}")
                        continue
                    
                    capability = match.group(1)
                    version = f"v{match.group(2)}"
                    
                    # Загружаем как объект
                    prompt = await self.load_prompt(capability, version)
                    prompts.append(prompt)
                    
                except Exception as e:
                    errors.append(f"Ошибка загрузки {file_path}: {e}")
        
        if errors:
            print("[WARN] Ошибки при сканировании промптов:")
            for err in errors[:5]:  # Показываем первые 5 ошибок
                print(f"  - {err}")
            if len(errors) > 5:
                print(f"  ... и ещё {len(errors) - 5} ошибок")
        
        return prompts
    
    # === Аналогично для контрактов ===
    def _build_contract_path(self, capability: str, version: str, direction: str) -> Path:
        component_type = self._get_component_type(capability)
        type_dir = self.TYPE_TO_DIR[component_type]
        
        # Формат: contracts/{type}/{capability_base}/{capability}_{direction}_v{version}.yaml
        capability_parts = capability.split('.')
        if len(capability_parts) >= 2:
            capability_base = capability_parts[0]  # "planning.create_plan" → "planning"
        else:
            capability_base = capability  # fallback на случай, если capability не содержит точки
            
        # Обработка версии: если начинается с 'v', используем как есть, иначе добавляем 'v'
        if version.startswith('v'):
            version_part = version[1:]  # Убираем 'v' из начала версии для формата
        else:
            version_part = version
        filename = f"{capability}_{direction}_v{version_part}.yaml"  # Убираем 'v' из начала версии
        
        return self.contracts_dir / type_dir / capability_base / filename
    
    async def load_contract(self, capability: str, version: str, direction: str) -> Contract:
        path = self._build_contract_path(capability, version, direction)
        
        if not path.exists():
            raise FileNotFoundError(
                f"Контракт не найден по КАНОНИЧЕСКОМУ пути:\n"
                f"  {path}\n\n"
                f"Проверьте:\n"
                f"  1. Существует ли файл?\n"
                f"  2. Объявлен ли тип компонента для '{capability}' в registry.yaml?"
            )
        
        with open(path, encoding='utf-8') as f:
            raw = yaml.safe_load(f)
        
        if 'component_type' not in raw:
            raw['component_type'] = self._get_component_type(capability).value
        
        if 'direction' not in raw:
            raw['direction'] = direction
        
        try:
            return Contract(**raw)
        except Exception as e:
            raise ValueError(f"Ошибка валидации контракта {capability}@{version} ({direction}) из {path}: {e}")
    
    async def list_contracts(self) -> List[Contract]:
        contracts = []
        errors = []
        
        for component_type, type_dir_name in self.TYPE_TO_DIR.items():
            type_dir = self.contracts_dir / type_dir_name
            if not type_dir.exists():
                continue
            
            # Рекурсивно сканируем подкаталоги capability_base
            for file_path in type_dir.rglob("*.yaml"):
                try:
                    # Парсим имя файла: {capability}_{direction}_v{version}.yaml
                    match = re.match(r'^(.+)_([a-z]+)_v(\d+\.\d+\.\d+)\.yaml$', file_path.name)
                    if not match:
                        errors.append(f"Пропущен файл с неверным именем: {file_path.name}")
                        continue
                    
                    capability = match.group(1)
                    direction = match.group(2)
                    version = f"v{match.group(3)}"
                    
                    # Загружаем как объект
                    contract = await self.load_contract(capability, version, direction)
                    contracts.append(contract)
                    
                except Exception as e:
                    errors.append(f"Ошибка загрузки {file_path}: {e}")
        
        if errors:
            print("[WARN] Ошибки при сканировании контрактов:")
            for err in errors[:5]:
                print(f"  - {err}")
        
        return contracts


class ConfigurationError(Exception):
    """Ошибка конфигурации (например, отсутствует объявление типа компонента)"""
    pass