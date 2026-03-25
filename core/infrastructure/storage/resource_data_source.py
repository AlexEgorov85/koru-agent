"""
Абстрактный интерфейс для источника данных ресурсов (промптов и контрактов).
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from core.models.data.prompt import Prompt
from core.models.data.contract import Contract


class ResourceDataSource(ABC):
    """Интерфейс для источника данных с строгой архитектурой."""

    # === СУЩЕСТВУЮЩИЕ МЕТОДЫ ===
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def load_all_prompts(self) -> List[Prompt]:
        pass

    @abstractmethod
    def load_all_contracts(self) -> List[Contract]:
        pass

    @abstractmethod
    def save_prompt(self, prompt: Prompt) -> None:
        pass

    @abstractmethod
    def save_contract(self, contract: Contract) -> None:
        pass

    @abstractmethod
    def delete_prompt(self, name: str) -> None:
        pass

    @abstractmethod
    def delete_contract(self, name: str) -> None:
        pass
