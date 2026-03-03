"""
Реализация источника данных с файловой системой и строгой архитектурой.
"""
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from core.infrastructure.storage.resource_data_source import ResourceDataSource
from core.models.data.prompt import Prompt, PromptStatus, ComponentType as PromptComponentType
from core.models.data.contract import Contract, ContractDirection
from core.models.enums.common_enums import ComponentType as ManifestComponentType
from core.config.models import ComponentType, RegistryConfig
import yaml
import re
import json
from core.infrastructure.logging import EventBusLogger


class FileSystemDataSource(ResourceDataSource):
    """
    Строгая реализация источника данных с файловой системой.
    Следует всем требованиям архитектурного улучшения.
    """

    # Маппинг типа компонента → имя каталога (для промптов и контрактов)
    TYPE_TO_DIR = {
        PromptComponentType.SKILL: "skill",
        PromptComponentType.TOOL: "tool",
        PromptComponentType.SERVICE: "service",
        PromptComponentType.BEHAVIOR: "behavior"
    }
    
    # Маппинг типа компонента → имя каталога (для манифестов)
    MANIFEST_TYPE_TO_DIR = {
        ManifestComponentType.SKILL: "skills",
        ManifestComponentType.TOOL: "tools",
        ManifestComponentType.SERVICE: "services",
        ManifestComponentType.BEHAVIOR: "behaviors"
    }

    def __init__(self, base_dir: Path, registry_config: RegistryConfig):
        self.base_dir = base_dir.resolve()
        self.prompts_dir = self.base_dir / "prompts"
        self.contracts_dir = self.base_dir / "contracts"
        self.manifests_dir = self.base_dir / "manifests"  # Добавляем директорию для манифестов
        self.registry_config = registry_config  # ← Единый источник маппинга типов
        self._initialized = False
        self._loaded_prompts = {}
        self._loaded_contracts = {}
        self._loaded_manifests = {}  # Добавляем кэш для манифестов
        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        # FileSystemDataSource не имеет application_context, поэтому event_bus_logger не инициализируется
        pass

    def _assert_initialized(self):
        """Проверяет, что DataSource инициализирован."""
        if not self._initialized:
            raise RuntimeError("FileSystemDataSource не инициализирован. Вызовите initialize() перед использованием.")

    def initialize(self):
        """
        Инициализация источника данных:
        1. Проверка существования базовой директории
        2. Создание директорий prompts/, contracts/ и manifests/, если отсутствуют
        3. Выполнение preload всех ресурсов
        4. Публикация события о загрузке ресурсов (не print/log!)
        5. Установка _initialized = True
        """
        from core.infrastructure.event_bus.unified_event_bus import get_event_bus, EventType
        import asyncio

        # Проверить существование базовой директории
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Создать директории prompts/, contracts/ и manifests/, если отсутствуют
        self.prompts_dir.mkdir(exist_ok=True)
        self.contracts_dir.mkdir(exist_ok=True)

        # Создание директорий для манифестов
        for type_dir in self.MANIFEST_TYPE_TO_DIR.values():
            (self.manifests_dir / type_dir).mkdir(parents=True, exist_ok=True)

        # Выполнить preload всех ресурсов
        self._preload_all_resources()

        # Установить флаг инициализации
        self._initialized = True

        # Публикация события о загрузке ресурсов (вместо print/log)
        event_bus = get_event_bus()
        if event_bus:
            # Создаём задачу для публикации события
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(event_bus.publish(EventType.SYSTEM_INITIALIZED, {
                        "component": "FileSystemDataSource",
                        "prompts_loaded": len(self._loaded_prompts),
                        "contracts_loaded": len(self._loaded_contracts),
                        "manifests_loaded": len(self._loaded_manifests),
                        "prompts": sorted(self._loaded_prompts.keys()),
                        "contracts": sorted(self._loaded_contracts.keys()),
                        "manifests": sorted(self._loaded_manifests.keys())
                    }, source="FileSystemDataSource"))
                else:
                    loop.run_until_complete(event_bus.publish(EventType.SYSTEM_INITIALIZED, {
                        "component": "FileSystemDataSource",
                        "prompts_loaded": len(self._loaded_prompts),
                        "contracts_loaded": len(self._loaded_contracts),
                        "manifests_loaded": len(self._loaded_manifests),
                        "prompts": sorted(self._loaded_prompts.keys()),
                        "contracts": sorted(self._loaded_contracts.keys()),
                        "manifests": sorted(self._loaded_manifests.keys())
                    }, source="FileSystemDataSource"))
            except RuntimeError:
                # Нет активного event loop - пропускаем
                pass

    def _get_component_type(self, capability: str) -> ManifestComponentType:
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

    def _preload_all_resources(self):
        """
        Выполняет детерминированный preload всех ресурсов:
        - Сканирует директорию
        - Читает ВСЕ файлы
        - Парсит их
        - Создает доменные объекты через Prompt.from_dict() / Contract.from_dict() / Manifest.from_dict()
        - Валидирует каждый объект через .validate()
        """
        # Загрузка промптов
        self._preload_prompts()

        # Загрузка контрактов
        self._preload_contracts()
        
        # Загрузка манифестов
        self._preload_manifests()

    def _preload_manifests(self):
        """Загрузка всех манифестов с валидацией."""
        for type_enum, type_dir_name in self.MANIFEST_TYPE_TO_DIR.items():
            type_dir = self.manifests_dir / type_dir_name
            if not type_dir.exists():
                continue
            
            for component_dir in type_dir.iterdir():
                if component_dir.is_dir():
                    manifest_file = component_dir / "manifest.yaml"
                    if manifest_file.exists():
                        try:
                            with open(manifest_file, 'r', encoding='utf-8') as f:
                                raw = yaml.safe_load(f)
                            manifest = Manifest(**raw)
                            key = f"{type_enum.value}.{manifest.component_id}"
                            self._loaded_manifests[key] = manifest
                        except Exception as e:
                            # All-or-nothing: падаем при ошибке
                            raise ValueError(f"Ошибка загрузки манифеста {manifest_file}: {e}")

    def _preload_prompts(self):
        """Загрузка всех промптов с валидацией."""
        # Сканируем все каталоги типов
        for component_type, type_dir_name in self.TYPE_TO_DIR.items():
            type_dir = self.prompts_dir / type_dir_name
            if not type_dir.exists():
                continue

            # Ищем файлы по шаблону: {capability}_v{version}.yaml или .json
            for file_path in type_dir.rglob("*"):
                if file_path.suffix.lower() in ['.yaml', '.yml', '.json']:
                    try:
                        # Парсим имя файла
                        match = re.match(r'^(.+)_v(\d+\.\d+\.\d+)(\.yaml|\.yml|\.json)$', file_path.name)
                        if not match:
                            continue

                        capability = match.group(1)
                        version = f"v{match.group(2)}"

                        # Загружаем и парсим файл
                        if file_path.suffix.lower() in ['.yaml', '.yml']:
                            with open(file_path, encoding='utf-8') as f:
                                raw = yaml.safe_load(f)
                        else:  # .json
                            with open(file_path, encoding='utf-8') as f:
                                raw = json.load(f)

                        # Добавляем тип компонента из конфигурации (если отсутствует в файле)
                        if 'component_type' not in raw:
                            raw['component_type'] = self._get_component_type(capability).value

                        # Создаем объект Prompt - валидация происходит автоматически при создании Pydantic модели
                        prompt = Prompt(**raw)

                        # Сохраняем в кэш
                        self._loaded_prompts[f"{capability}:{version}"] = prompt

                    except Exception as e:
                        # Если хотя бы один файл не читается/не парсится/не проходит валидацию
                        # → выбрасываем исключение и НЕ продолжаем загрузку
                        self.logger.error(f"Ошибка при загрузке промпта из {file_path}: {e}")
                        raise ValueError(f"Ошибка при загрузке промпта из {file_path}: {e}")

    def _preload_contracts(self):
        """Загрузка всех контрактов с валидацией."""
        for component_type, type_dir_name in self.TYPE_TO_DIR.items():
            type_dir = self.contracts_dir / type_dir_name
            if not type_dir.exists():
                continue

            # Рекурсивно сканируем подкаталоги capability_base
            for file_path in type_dir.rglob("*"):
                if file_path.suffix.lower() in ['.yaml', '.yml', '.json']:
                    try:
                        # Парсим имя файла: {capability}_{direction}_v{version}.(yaml|json)
                        match = re.match(r'^(.+)_([a-z]+)_v(\d+\.\d+\.\d+)(\.yaml|\.yml|\.json)$', file_path.name)
                        if not match:
                            continue

                        capability = match.group(1)
                        direction = match.group(2)
                        version = f"v{match.group(3)}"

                        # Загрузка и парсинг файла
                        if file_path.suffix.lower() in ['.yaml', '.yml']:
                            with open(file_path, encoding='utf-8') as f:
                                raw = yaml.safe_load(f)
                        else:  # .json
                            with open(file_path, encoding='utf-8') as f:
                                raw = json.load(f)

                        if 'component_type' not in raw:
                            raw['component_type'] = self._get_component_type(capability).value

                        if 'direction' not in raw:
                            raw['direction'] = direction

                        # Создаем объект Contract - валидация происходит автоматически при создании Pydantic модели
                        contract = Contract(**raw)

                        # Сохраняем в кэш
                        self._loaded_contracts[f"{capability}:{version}:{direction}"] = contract

                    except Exception as e:
                        # Если хотя бы один файл не читается/не парсится/не проходит валидацию
                        # → выбрасываем исключение и НЕ продолжаем загрузку
                        self.logger.error(f"Ошибка при загрузке контракта из {file_path}: {e}")
                        raise ValueError(f"Ошибка при загрузке контракта из {file_path}: {e}")

    def load_all_prompts(self) -> List[Prompt]:
        """
        Загрузка всех промптов из in-memory кэша.
        """
        self._assert_initialized()
        return list(self._loaded_prompts.values())

    def load_all_contracts(self) -> List[Contract]:
        """
        Загрузка всех контрактов из in-memory кэша.
        """
        self._assert_initialized()
        return list(self._loaded_contracts.values())

    def save_prompt(self, prompt: Prompt):
        """
        Сохранение промпта:
        1. Проверить initialize()
        2. Вызвать prompt.validate()
        3. Проверить отсутствие конфликта имени
        4. Сериализовать через to_dict()
        5. Сохранить в файл <name>.json
        6. Обновить in-memory cache
        """
        self._assert_initialized()
        
        # Валидация промпта (Pydantic делает это автоматически при создании объекта)
        # Но мы можем дополнительно проверить, что объект корректен
        if not isinstance(prompt, Prompt):
            raise TypeError("Объект должен быть экземпляром класса Prompt")
            
        # Проверить конфликт имени
        prompt_key = f"{prompt.capability}:{prompt.version}"
        if prompt_key in self._loaded_prompts:
            raise ValueError(f"Промпт с именем {prompt_key} уже существует")
        
        # Определить путь для сохранения
        component_type = prompt.component_type
        type_dir = self.prompts_dir / self.TYPE_TO_DIR[component_type]
        
        # Разбиваем capability на части: "planning.create_plan" -> "planning", "create_plan"
        capability_parts = prompt.capability.split('.')
        if len(capability_parts) >= 2:
            capability_base = capability_parts[0]  # "planning"
        else:
            capability_base = prompt.capability  # fallback на случай, если capability не содержит точки

        # Обработка версии: если начинается с 'v', используем как есть, иначе добавляем 'v'
        version_for_filename = prompt.version[1:] if prompt.version.startswith('v') else prompt.version
        filename = f"{prompt.capability}_v{version_for_filename}.json"
        file_path = type_dir / capability_base / filename
        
        # Создать директорию, если не существует
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Сериализовать и сохранить в файл
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(prompt.model_dump(), f, ensure_ascii=False, indent=2)
        
        # Обновить in-memory кэш
        self._loaded_prompts[prompt_key] = prompt

    def save_contract(self, contract: Contract):
        """
        Сохранение контракта:
        1. Проверить initialize()
        2. Вызвать contract.validate()
        3. Проверить отсутствие конфликта имени
        4. Сериализовать через to_dict()
        5. Сохранить в файл <name>.json
        6. Обновить in-memory cache
        """
        self._assert_initialized()
        
        # Валидация контракта (Pydantic делает это автоматически при создании объекта)
        if not isinstance(contract, Contract):
            raise TypeError("Объект должен быть экземпляром класса Contract")
            
        # Проверить конфликт имени
        contract_key = f"{contract.capability}:{contract.version}:{contract.direction}"
        if contract_key in self._loaded_contracts:
            raise ValueError(f"Контракт с именем {contract_key} уже существует")
        
        # Определить путь для сохранения
        component_type = contract.component_type
        type_dir = self.contracts_dir / self.TYPE_TO_DIR[component_type]
        
        # Разбиваем capability на части: "planning.create_plan" -> "planning", "create_plan"
        capability_parts = contract.capability.split('.')
        if len(capability_parts) >= 2:
            capability_base = capability_parts[0]  # "planning"
        else:
            capability_base = contract.capability  # fallback на случай, если capability не содержит точки

        # Обработка версии: если начинается с 'v', используем как есть, иначе добавляем 'v'
        version_for_filename = contract.version[1:] if contract.version.startswith('v') else contract.version
        filename = f"{contract.capability}_{contract.direction.value}_v{version_for_filename}.json"
        file_path = type_dir / capability_base / filename
        
        # Создать директорию, если не существует
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Сериализовать и сохранить в файл
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(contract.model_dump(), f, ensure_ascii=False, indent=2)
        
        # Обновить in-memory кэш
        self._loaded_contracts[contract_key] = contract

    def delete_prompt(self, name: str):
        """
        Удаление промпта:
        - Удалить файл
        - Удалить из кэша
        - Если не существует — выбросить ошибку
        """
        self._assert_initialized()
        
        # Проверить, существует ли промпт в кэше
        if name not in self._loaded_prompts:
            raise ValueError(f"Промпт с именем {name} не существует")
        
        # Получить объект промпта для определения пути к файлу
        prompt = self._loaded_prompts[name]
        
        # Построить путь к файлу
        component_type = prompt.component_type
        type_dir = self.prompts_dir / self.TYPE_TO_DIR[component_type]
        
        # Разбиваем capability на части: "planning.create_plan" -> "planning", "create_plan"
        capability_parts = prompt.capability.split('.')
        if len(capability_parts) >= 2:
            capability_base = capability_parts[0]  # "planning"
        else:
            capability_base = prompt.capability  # fallback на случай, если capability не содержит точки

        # Обработка версии: если начинается с 'v', используем как есть, иначе добавляем 'v'
        version_for_filename = prompt.version[1:] if prompt.version.startswith('v') else prompt.version
        filename = f"{prompt.capability}_v{version_for_filename}.json"
        file_path = type_dir / capability_base / filename
        
        # Удалить файл
        if file_path.exists():
            file_path.unlink()
        else:
            # Попробовать YAML файл, если JSON не найден
            yaml_filename = f"{prompt.capability}_v{version_for_filename}.yaml"
            yaml_file_path = type_dir / capability_base / yaml_filename
            if yaml_file_path.exists():
                yaml_file_path.unlink()
            else:
                # Если ни один файл не существует, выбросить ошибку
                raise FileNotFoundError(f"Файл промпта не найден: {file_path} или {yaml_file_path}")
        
        # Удалить из кэша
        del self._loaded_prompts[name]

    def delete_contract(self, name: str):
        """
        Удаление контракта:
        - Удалить файл
        - Удалить из кэша
        - Если не существует — выбросить ошибку
        """
        self._assert_initialized()
        
        # Проверить, существует ли контракт в кэше
        if name not in self._loaded_contracts:
            raise ValueError(f"Контракт с именем {name} не существует")
        
        # Получить объект контракта для определения пути к файлу
        contract = self._loaded_contracts[name]
        
        # Построить путь к файлу
        component_type = contract.component_type
        type_dir = self.contracts_dir / self.TYPE_TO_DIR[component_type]
        
        # Разбиваем capability на части: "planning.create_plan" -> "planning", "create_plan"
        capability_parts = contract.capability.split('.')
        if len(capability_parts) >= 2:
            capability_base = capability_parts[0]  # "planning"
        else:
            capability_base = contract.capability  # fallback на случай, если capability не содержит точки

        # Обработка версии: если начинается с 'v', используем как есть, иначе добавляем 'v'
        version_for_filename = contract.version[1:] if contract.version.startswith('v') else contract.version
        filename = f"{contract.capability}_{contract.direction.value}_v{version_for_filename}.json"
        file_path = type_dir / capability_base / filename
        
        # Удалить файл
        if file_path.exists():
            file_path.unlink()
        else:
            # Попробовать YAML файл, если JSON не найден
            yaml_filename = f"{contract.capability}_{contract.direction.value}_v{version_for_filename}.yaml"
            yaml_file_path = type_dir / capability_base / yaml_filename
            if yaml_file_path.exists():
                yaml_file_path.unlink()
            else:
                # Если ни один файл не существует, выбросить ошибку
                raise FileNotFoundError(f"Файл контракта не найден: {file_path} или {yaml_file_path}")

        # Удалить из кэша
        del self._loaded_contracts[name]

    # === Методы для манифестов удалены ===
    # Манифесты удалены из системы. Зависимости объявляются через DEPENDENCIES в коде компонентов.


class ConfigurationError(Exception):
    """Ошибка конфигурации (например, отсутствует объявление типа компонента)"""
    pass