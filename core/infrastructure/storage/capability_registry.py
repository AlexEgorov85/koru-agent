"""
Реестр возможностей (capabilities) - хранит метаданные о возможностях системы.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging


class CapabilityRegistry:
    """Реестр возможностей (capabilities) - хранит метаданные о возможностях системы."""

    def __init__(self):
        """Инициализация реестра возможностей."""
        self.capabilities_dir = Path("contracts")
        self._capabilities: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def initialize(self):
        """Инициализация реестра возможностей."""
        if not self.capabilities_dir.exists():
            self.logger.warning(f"Директория контрактов не существует: {self.capabilities_dir}")
            return

        # Загрузка метаданных возможностей из файлов контрактов
        await self._load_capabilities_from_contracts()

    async def _load_capabilities_from_contracts(self):
        """Загрузка возможностей из файлов контрактов."""
        for capability_dir in self.capabilities_dir.iterdir():
            if capability_dir.is_dir():
                capability_name = capability_dir.name
                capability_meta = {
                    "name": capability_name,
                    "versions": {},
                    "has_input_contract": False,
                    "has_output_contract": False
                }

                # Проверим наличие контрактов
                input_contract_path = capability_dir / "input_contract.json"
                output_contract_path = capability_dir / "output_contract.json"

                if input_contract_path.exists():
                    capability_meta["has_input_contract"] = True
                    # Загрузим информацию о версиях
                    try:
                        with open(input_contract_path, 'r', encoding='utf-8') as f:
                            input_contract = json.load(f)
                        if "version" in input_contract:
                            version = input_contract["version"]
                            if version not in capability_meta["versions"]:
                                capability_meta["versions"][version] = {"input": True, "output": False}
                            else:
                                capability_meta["versions"][version]["input"] = True
                    except Exception as e:
                        self.logger.warning(f"Ошибка чтения входного контракта для {capability_name}: {str(e)}")

                if output_contract_path.exists():
                    capability_meta["has_output_contract"] = True
                    # Загрузим информацию о версиях
                    try:
                        with open(output_contract_path, 'r', encoding='utf-8') as f:
                            output_contract = json.load(f)
                        if "version" in output_contract:
                            version = output_contract["version"]
                            if version not in capability_meta["versions"]:
                                capability_meta["versions"][version] = {"input": False, "output": True}
                            else:
                                capability_meta["versions"][version]["output"] = True
                    except Exception as e:
                        self.logger.warning(f"Ошибка чтения выходного контракта для {capability_name}: {str(e)}")

                # Также проверим поддиректории с версиями
                for version_dir in capability_dir.iterdir():
                    if version_dir.is_dir():
                        version = version_dir.name
                        if version not in capability_meta["versions"]:
                            capability_meta["versions"][version] = {"input": False, "output": False}

                        # Проверим контракты в директории версии
                        version_input_contract = version_dir / f"input_contract_{version}.json"
                        version_output_contract = version_dir / f"output_contract_{version}.json"

                        if version_input_contract.exists():
                            capability_meta["versions"][version]["input"] = True
                            try:
                                with open(version_input_contract, 'r', encoding='utf-8') as f:
                                    input_contract = json.load(f)
                                if "version" in input_contract:
                                    version_from_file = input_contract["version"]
                                    if version_from_file not in capability_meta["versions"]:
                                        capability_meta["versions"][version_from_file] = {"input": True, "output": False}
                                    else:
                                        capability_meta["versions"][version_from_file]["input"] = True
                            except Exception as e:
                                self.logger.warning(f"Ошибка чтения входного контракта версии {version} для {capability_name}: {str(e)}")

                        if version_output_contract.exists():
                            capability_meta["versions"][version]["output"] = True
                            try:
                                with open(version_output_contract, 'r', encoding='utf-8') as f:
                                    output_contract = json.load(f)
                                if "version" in output_contract:
                                    version_from_file = output_contract["version"]
                                    if version_from_file not in capability_meta["versions"]:
                                        capability_meta["versions"][version_from_file] = {"input": False, "output": True}
                                    else:
                                        capability_meta["versions"][version_from_file]["output"] = True
                            except Exception as e:
                                self.logger.warning(f"Ошибка чтения выходного контракта версии {version} для {capability_name}: {str(e)}")

                self._capabilities[capability_name] = capability_meta

    def get_capability(self, name: str) -> Optional[Dict[str, Any]]:
        """Получение информации о возможности."""
        return self._capabilities.get(name)

    def get_all_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Получение всех возможностей."""
        return self._capabilities.copy()

    def has_capability(self, name: str) -> bool:
        """Проверка наличия возможности."""
        return name in self._capabilities

    def get_capability_versions(self, name: str) -> Dict[str, Any]:
        """Получение доступных версий возможности."""
        capability = self.get_capability(name)
        return capability["versions"] if capability else {}

    def has_input_contract(self, name: str) -> bool:
        """Проверка наличия входного контракта."""
        capability = self.get_capability(name)
        return capability["has_input_contract"] if capability else False

    def has_output_contract(self, name: str) -> bool:
        """Проверка наличия выходного контракта."""
        capability = self.get_capability(name)
        return capability["has_output_contract"] if capability else False

    async def shutdown(self):
        """Завершение работы реестра."""
        self.logger.info("Реестр возможностей завершает работу")