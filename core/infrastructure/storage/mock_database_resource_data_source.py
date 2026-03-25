"""
Mock-реализация ResourceDataSource с использованием базы данных для проверки замещаемости.
"""
from typing import List, Optional
from core.infrastructure.storage.resource_data_source import ResourceDataSource
from core.models.data.prompt import Prompt
from core.models.data.contract import Contract


class MockDatabaseResourceDataSource(ResourceDataSource):
    """
    Заглушка для демонстрации возможности замены реализации на базу данных.
    """

    def __init__(self):
        self._initialized = False
        self._prompts = {}
        self._contracts = {}

    def initialize(self):
        """
        Имитация инициализации подключения к базе данных.
        """
        # Здесь могло бы быть подключение к базе данных
        self._initialized = True

    def _assert_initialized(self):
        """Проверяет, что DataSource инициализирован."""
        if not self._initialized:
            raise RuntimeError("MockDatabaseResourceDataSource не инициализирован. Вызовите initialize() перед использованием.")

    def load_all_prompts(self) -> List[Prompt]:
        """
        Загрузка всех промптов из "базы данных".
        """
        self._assert_initialized()
        return list(self._prompts.values())

    def load_all_contracts(self) -> List[Contract]:
        """
        Загрузка всех контрактов из "базы данных".
        """
        self._assert_initialized()
        return list(self._contracts.values())

    def save_prompt(self, prompt: Prompt):
        """
        Сохранение промпта в "базу данных".
        """
        self._assert_initialized()

        # Проверить конфликт имени
        prompt_key = f"{prompt.capability}:{prompt.version}"
        if prompt_key in self._prompts:
            raise ValueError(f"Промпт с именем {prompt_key} уже существует")

        # Сохранить в "базу данных"
        self._prompts[prompt_key] = prompt

    def save_contract(self, contract: Contract):
        """
        Сохранение контракта в "базу данных".
        """
        self._assert_initialized()

        # Проверить конфликт имени
        contract_key = f"{contract.capability}:{contract.version}:{contract.direction}"
        if contract_key in self._contracts:
            raise ValueError(f"Контракт с именем {contract_key} уже существует")

        # Сохранить в "базу данных"
        self._contracts[contract_key] = contract

    def delete_prompt(self, name: str):
        """
        Удаление промпта из "базы данных".
        """
        self._assert_initialized()

        if name not in self._prompts:
            raise ValueError(f"Промпт с именем {name} не существует")

        del self._prompts[name]

    def delete_contract(self, name: str):
        """
        Удаление контракта из "базы данных".
        """
        self._assert_initialized()

        if name not in self._contracts:
            raise ValueError(f"Контракт с именем {name} не существует")

        del self._contracts[name]