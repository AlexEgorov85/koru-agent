"""
Хранилище контрактов - только загрузка из файловой системы.
НЕ содержит кэширования - кэширование происходит в прикладном слое.
"""
import asyncio
from pathlib import Path
from typing import Optional
import json
import yaml
import logging
from core.models.data.contract import Contract
from core.models.errors.version_not_found import VersionNotFoundError
from core.infrastructure.interfaces.storage_interfaces import IContractStorage, ComponentType
from core.infrastructure.storage.base.versioned_storage import VersionedStorage
from core.infrastructure.logging.event_bus_log_handler import EventBusLogger


class ContractStorage(VersionedStorage[Contract], IContractStorage):
    """
    Хранилище контрактов БЕЗ кэширования.
    Единственный источник истины для контрактов.
    Создаётся ОДИН раз в InfrastructureContext.

    INHERITS: VersionedStorage[Contract]
    """

    def __init__(self, contracts_dir: Path):
        super().__init__(contracts_dir)
        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        # ContractStorage не имеет application_context, поэтому event_bus_logger не инициализируется
        pass
    
    @property
    def contracts_dir(self) -> Path:
        """Свойство для обратной совместимости."""
        return self.storage_dir

    async def load(self, capability_name: str, version: str, direction: str, component_type: Optional['ComponentType'] = None) -> Contract:
        """
        Загружает контракт из файловой системы.
        Вызывается ТОЛЬКО при инициализации ApplicationContext.
        """
        # Построение списка путей для поиска с учётом direction
        files_to_check = self._build_contract_search_paths(
            capability_name=capability_name,
            version=version,
            direction=direction,
            component_type=component_type
        )

        # Поиск существующего файла
        contract_file, file_format = self._find_existing_file(files_to_check)

        if contract_file is None:
            raise self._create_file_not_found_error(
                capability_name=capability_name,
                version=version,
                files_to_check=files_to_check,
                component_type=component_type,
                direction=direction,
                item_type="Контракт"
            )

        # Загрузка и парсинг файла
        data = self._load_file(contract_file, file_format)
        return self._parse_contract_data(data, capability_name, version, direction)

    def _build_contract_search_paths(
        self,
        capability_name: str,
        version: str,
        direction: str,
        component_type: Optional[ComponentType] = None
    ) -> list[Path]:
        """
        Построение списка путей для поиска контракта.

        CONTRACTS имеют дополнительный параметр direction (input/output).
        """
        files_to_check = []
        capability_path = capability_name.replace(".", "/")
        parts = capability_name.split('.')
        category = parts[0] if parts else capability_name
        specific = parts[1] if len(parts) >= 2 else ""

        # 1. Основной путь: {capability_path}/{version}_{direction}.ext
        for ext in ['.json', '.yaml', '.yml']:
            files_to_check.append(self.storage_dir / capability_path / f"{version}_{direction}{ext}")

        # 2. Плоская структура: {capability_name}_{direction}_{version}.ext
        flat_name = capability_name.replace('.', '_')
        for ext in ['.json', '.yaml', '.yml']:
            files_to_check.append(self.storage_dir / f"{flat_name}_{direction}_{version}{ext}")

        # 3. Компонент-специфичные подкаталоги
        standard_subdirs = self._get_subdirs_for_component(component_type)

        for subdir in standard_subdirs:
            subdir_path = self.storage_dir / subdir / capability_path
            for ext in ['.json', '.yaml', '.yml']:
                files_to_check.append(subdir_path / f"{version}_{direction}{ext}")

            # Если есть specific часть
            if specific:
                for ext in ['.json', '.yaml', '.yml']:
                    # Формат с direction
                    files_to_check.append(
                        self.storage_dir / subdir / category / f"{specific}_{direction}_{version}{ext}"
                    )
                    files_to_check.append(
                        self.storage_dir / subdir / category / f"{category}_{specific}_{direction}_{version}{ext}"
                    )
                    # Формат без direction (старый)
                    files_to_check.append(
                        self.storage_dir / subdir / category / f"{specific}_{version}{ext}"
                    )

        # 4. Структура по категориям
        if specific:
            for ext in ['.json', '.yaml', '.yml']:
                files_to_check.append(
                    self.storage_dir / category / f"{specific}_{direction}_{version}{ext}"
                )
                files_to_check.append(
                    self.storage_dir / category / f"{direction}_{version}{ext}"
                )
        else:
            for ext in ['.json', '.yaml', '.yml']:
                files_to_check.append(
                    self.storage_dir / category / f"{direction}_{version}{ext}"
                )

        return files_to_check

    def _parse_contract_data(self, data: dict, capability_name: str, version: str, direction: str) -> Contract:
        """
        Парсинг данных контракта.

        ARGS:
        - data: данные из файла
        - capability_name: имя capability
        - version: версия
        - direction: направление (input/output)

        RETURNS:
        - Contract: объект контракта
        """
        # Проверяем, является ли файл новым форматом (с полной информацией) или старым
        if isinstance(data, dict) and all(key in data for key in ['capability_name', 'version', 'direction', 'schema']):
            # Новый формат: файл содержит полный объект Contract
            return Contract(
                capability_name=data['capability_name'],
                version=data['version'],
                direction=data['direction'],
                schema_data=data['schema']
            )
        else:
            # Старый формат: файл содержит метаданные и схему
            schema_data = data.get('schema', data) if isinstance(data, dict) else data
            return Contract(
                capability_name=capability_name,
                version=version,
                direction=direction,
                schema_data=schema_data
            )

    async def exists(self, capability_name: str, version: str, direction: str, component_type: Optional['ComponentType'] = None) -> bool:
        """Проверяет существование контракта без загрузки содержимого."""
        files_to_check = self._build_contract_search_paths(
            capability_name=capability_name,
            version=version,
            direction=direction,
            component_type=component_type
        )
        contract_file, _ = self._find_existing_file(files_to_check)
        return contract_file is not None

    async def save(self, capability_name: str, version: str, direction: str, contract: Contract, component_type: Optional['ComponentType'] = None) -> None:
        """Сохраняет контракт в файловую систему."""
        parts = capability_name.split('.')
        category = parts[0] if parts else capability_name
        specific = parts[1] if len(parts) >= 2 else ""

        # Определяем директорию для сохранения
        if component_type:
            if component_type == ComponentType.SKILL:
                save_dir = self.storage_dir / 'skills'
            elif component_type == ComponentType.SERVICE:
                save_dir = self.storage_dir / 'services'
            elif component_type == ComponentType.TOOL:
                save_dir = self.storage_dir / 'tools'
            elif component_type == ComponentType.SQL_GENERATION:
                save_dir = self.storage_dir / 'sql_generation'
            elif component_type == ComponentType.CONTRACT:
                save_dir = self.storage_dir / 'contracts'
            else:
                save_dir = self.storage_dir / category
        else:
            save_dir = self.storage_dir / category

        # Создаём директорию
        capability_dir = save_dir / category if specific else save_dir
        capability_dir.mkdir(parents=True, exist_ok=True)

        # Определяем путь к файлу
        if specific:
            contract_file = capability_dir / f"{specific}_{direction}_{version}.yaml"
        else:
            contract_file = capability_dir / f"{direction}_{version}.yaml"

        # Сохраняем в YAML формате
        contract_dict = contract.model_dump()
        self._save_file(contract_file, contract_dict, 'yaml')

        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Контракт сохранен: {capability_name}@{version} ({direction}) ({component_type}) -> {contract_file}")
        else:
            self.logger.info(f"Контракт сохранен: {capability_name}@{version} ({direction}) ({component_type}) -> {contract_file}")
