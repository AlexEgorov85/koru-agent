"""
Хранилище контрактов - только загрузка из файловой системы.
НЕ содержит кэширования - кэширование происходит в прикладном слое.
"""
from pathlib import Path
from typing import Optional
import json
import logging
from core.models.contract import Contract
from core.errors.version_not_found import VersionNotFoundError


class ContractStorage:
    """
    Хранилище контрактов БЕЗ кэширования.
    Единственный источник истины для контрактов.
    Создаётся ОДИН раз в InfrastructureContext.
    """
    
    def __init__(self, contracts_dir: Path):
        self.contracts_dir = contracts_dir.resolve()
        self._validate_directory()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info(f"ContractStorage инициализировано: {self.contracts_dir}")
    
    def _validate_directory(self):
        if not self.contracts_dir.exists():
            self.contracts_dir.mkdir(parents=True, exist_ok=True)
        if not self.contracts_dir.is_dir():
            raise ValueError(f"Путь не является директорией: {self.contracts_dir}")
    
    async def load(self, capability_name: str, version: str, direction: str) -> Contract:
        """
        Загружает контракт из файловой системы.
        Вызывается ТОЛЬКО при инициализации ApplicationContext.
        """
        # Формат файла: {capability}_{direction}_{version}.json
        filename = f"{capability_name.replace('.', '_')}_{direction}_{version}.json"
        contract_file = self.contracts_dir / filename
        
        if not contract_file.exists():
            raise VersionNotFoundError(
                f"Контракт не найден: capability={capability_name}, version={version}, "
                f"direction={direction}, path={contract_file}"
            )
        
        try:
            with open(contract_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Проверяем, является ли файл новым форматом (с полной информацией) или старым (только схема)
            if isinstance(data, dict) and all(key in data for key in ['capability_name', 'version', 'direction', 'schema']):
                # Новый формат: файл содержит полный объект Contract
                return Contract(
                    capability_name=data['capability_name'],
                    version=data['version'],
                    direction=data['direction'],
                    schema_data=data['schema']
                )
            else:
                # Старый формат: файл содержит только схему
                return Contract(
                    capability_name=capability_name,
                    version=version,
                    direction=direction,
                    schema_data=data
                )
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ошибка парсинга JSON контракта {capability_name}@{version} ({direction}): {e}")
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки контракта {capability_name}@{version} ({direction}): {e}")
    
    async def exists(self, capability_name: str, version: str, direction: str) -> bool:
        """Проверяет существование контракта без загрузки содержимого."""
        filename = f"{capability_name.replace('.', '_')}_{direction}_{version}.json"
        contract_file = self.contracts_dir / filename
        return contract_file.exists()