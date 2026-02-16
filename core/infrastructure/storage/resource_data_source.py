"""
Абстрактный интерфейс для источника данных ресурсов (промптов, контрактов и манифестов).
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from core.models.data.prompt import Prompt
from core.models.data.contract import Contract
from core.models.data.manifest import Manifest  # ← Добавить


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
    
    # === НОВЫЕ МЕТОДЫ ДЛЯ МАНИФЕСТОВ ===
    @abstractmethod
    def load_manifest(self, component_type: str, component_name: str) -> Manifest:
        """Загрузка конкретного манифеста"""
        pass
    
    @abstractmethod
    def list_manifests(self, component_type: Optional[str] = None) -> List[Manifest]:
        """Список всех манифестов (опционально по типу)"""
        pass
    
    @abstractmethod
    def manifest_exists(self, component_type: str, component_name: str, version: str) -> bool:
        """Проверка существования манифеста"""
        pass