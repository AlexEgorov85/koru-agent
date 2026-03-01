"""
Хранилище промптов - только загрузка из файловой системы.
НЕ содержит кэширования - кэширование происходит в прикладном слое.
"""
import asyncio
from pathlib import Path
from typing import Optional
import json
import yaml
import logging
from core.models.data.prompt import Prompt
from core.models.errors.version_not_found import VersionNotFoundError
from core.infrastructure.interfaces.storage_interfaces import IPromptStorage
from core.infrastructure.storage.base.versioned_storage import VersionedStorage
from core.models.enums.common_enums import ComponentType
from core.infrastructure.logging.event_bus_log_handler import EventBusLogger


class PromptStorage(VersionedStorage[Prompt], IPromptStorage):
    """
    Хранилище промптов БЕЗ кэширования.
    Единственный источник истины для промптов.
    Создаётся ОДИН раз в InfrastructureContext.

    INHERITS: VersionedStorage[Prompt]
    """

    def __init__(self, prompts_dir: Path):
        super().__init__(prompts_dir)
        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        # PromptStorage не имеет application_context, поэтому event_bus_logger не инициализируется
        pass
    
    @property
    def prompts_dir(self) -> Path:
        """Свойство для обратной совместимости."""
        return self.storage_dir

    async def load(self, capability_name: str, version: str, component_type: Optional['ComponentType'] = None) -> Prompt:
        """
        Загружает промпт из файловой системы.
        Вызывается ТОЛЬКО при инициализации ApplicationContext.
        """
        # Построение списка путей для поиска
        files_to_check = self._build_file_search_paths(
            capability_name=capability_name,
            version=version,
            extensions=['.json', '.yaml', '.yml'],
            component_type=component_type,
            include_flat=True,
            include_category=True
        )

        # Поиск существующего файла
        prompt_file, file_format = self._find_existing_file(files_to_check)

        if prompt_file is None:
            raise self._create_file_not_found_error(
                capability_name=capability_name,
                version=version,
                files_to_check=files_to_check,
                component_type=component_type,
                item_type="Промпт"
            )

        # Загрузка и парсинг файла
        data = self._load_file(prompt_file, file_format)
        return self._parse_prompt_data(data, capability_name, version)

    def _parse_prompt_data(self, data: dict, capability_name: str, version: str) -> Prompt:
        """
        Парсинг данных промпта.

        ARGS:
        - data: данные из файла
        - capability_name: имя capability
        - version: версия

        RETURNS:
        - Prompt: объект промпта
        """
        return Prompt(
            capability=data.get('capability', capability_name),
            version=data.get('version', version),
            status=data.get('status', 'draft'),
            component_type=data.get('component_type', 'service'),
            content=data.get('content', ''),
            variables=data.get('variables', []),
            metadata=data.get('metadata', {})
        )

    async def exists(self, capability_name: str, version: str, component_type: Optional['ComponentType'] = None) -> bool:
        """Проверяет существование промпта без загрузки содержимого."""
        files_to_check = self._build_file_search_paths(
            capability_name=capability_name,
            version=version,
            extensions=['.json', '.yaml', '.yml'],
            component_type=component_type,
            include_flat=True,
            include_category=True
        )
        prompt_file, _ = self._find_existing_file(files_to_check)
        return prompt_file is not None

    async def save(self, capability_name: str, version: str, prompt: Prompt, component_type: Optional['ComponentType'] = None) -> None:
        """Сохраняет промпт в файловую систему."""
        # Поддержка обоих форматов путей: точки → слэши
        capability_path = capability_name.replace(".", "/")

        # Определяем директорию для сохранения в зависимости от типа компонента
        if component_type:
            if component_type == ComponentType.SKILL:
                save_dir = self.prompts_dir / 'skills'
            elif component_type == ComponentType.SERVICE:
                save_dir = self.prompts_dir / 'services'
                save_dir = self.prompts_dir / 'strategies'
            elif component_type == ComponentType.TOOL:
                save_dir = self.prompts_dir / 'tools'
            elif component_type == ComponentType.SQL_GENERATION:
                save_dir = self.prompts_dir / 'sql_generation'
            elif component_type == ComponentType.CONTRACT:
                save_dir = self.prompts_dir / 'contracts'
            else:
                # DEFAULT или неизвестный тип - используем основной путь
                save_dir = self.prompts_dir
        else:
            # Если тип компонента не указан, используем основной путь
            save_dir = self.prompts_dir

        # Разбиваем capability_name на части для создания подкаталогов
        parts = capability_name.split('.')
        if len(parts) >= 2:
            category = parts[0]  # например, "planning"
            specific = parts[1]  # например, "create_plan"

            # Создаем подкаталог: save_dir/category/
            capability_dir = save_dir / category
        else:
            # Если только одна часть, используем как есть
            category = parts[0] if parts else capability_name
            capability_dir = save_dir / category

        capability_dir.mkdir(parents=True, exist_ok=True)

        # Определяем путь к файлу (по умолчанию используем YAML)
        # Формат: {specific}_{version}.yaml (например, create_plan_v1.0.0.yaml)
        if len(parts) >= 2:
            specific = parts[1]
            prompt_file = capability_dir / f"{specific}_{version}.yaml"
        else:
            # Если только одна часть, используем только версию
            prompt_file = capability_dir / f"{version}.yaml"

        # Подготовим данные для сохранения
        # Объединяем content и metadata в один словарь
        prompt_dict = prompt.model_dump()
        
        # Для YAML формата перемещаем content на верхний уровень
        content = prompt_dict.pop('content', '')
        metadata_dict = prompt_dict.get('metadata', {})
        
        # Объединяем метаданные с content
        yaml_data = {'content': content}
        yaml_data.update(metadata_dict)

        # Сохраняем в YAML формате
        import yaml
        with open(prompt_file, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, indent=2)

        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Промпт сохранен: {capability_name}@{version} ({component_type}) -> {prompt_file}")
        else:
            self.logger.info(f"Промпт сохранен: {capability_name}@{version} ({component_type}) -> {prompt_file}")