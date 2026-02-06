from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from domain.models.prompt.prompt_version import PromptUsageMetrics, PromptVersion, PromptStatus, PromptExecutionSnapshot


class IPromptRepository(ABC):
    """Абстракция для хранилища версий промтов (инверсия зависимостей)"""
    
    @abstractmethod
    def get_active_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить активную версию промта по адресу"""
        pass
    
    @abstractmethod
    def get_shadow_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить теневую (shadow) версию для A/B тестирования"""
        pass
    
    @abstractmethod
    def get_version_by_id(self, version_id: str) -> Optional[PromptVersion]:
        """Получить версию промта по ID"""
        pass
    
    @abstractmethod
    def save_version(self, version: PromptVersion) -> None:
        """Сохранить новую версию промта (не поддерживается в file-only режиме)"""
        pass
    
    @abstractmethod
    def update_version_status(self, version_id: str, status: PromptStatus) -> None:
        """Обновить статус версии промта (не поддерживается в file-only режиме)"""
        pass
    
    @abstractmethod
    def activate_version(self, version_id: str) -> None:
        """Активировать версию промта (и деактивировать текущую активную) (не поддерживается в file-only режиме)"""
        pass
    
    @abstractmethod
    def archive_version(self, version_id: str) -> None:
        """Архивировать версию промта (не поддерживается в file-only режиме)"""
        pass
    
    @abstractmethod
    def list_versions(self, capability_name: str) -> List[PromptVersion]:
        """Получить все версии для конкретной capability"""
        pass
    
    @abstractmethod
    def list_versions_by_address(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> List[PromptVersion]:
        """Получить все версии по адресу"""
        pass
    
    @abstractmethod
    def update_usage_metrics(
        self,
        version_id: str,
        metrics_update: PromptUsageMetrics
    ) -> None:
        """Обновить метрики использования версии промта (не поддерживается в file-only режиме)"""
        pass


class ISnapshotManager(ABC):
    """Интерфейс для управления снапшотами выполнения промтов"""
    
    @abstractmethod
    async def save_snapshot(self, snapshot: PromptExecutionSnapshot) -> None:
        """Сохранить снапшот выполнения промта"""
        pass
    
    @abstractmethod
    async def get_snapshots_by_prompt_id(self, prompt_id: str, limit: int = 100) -> List[PromptExecutionSnapshot]:
        """Получить снапшоты для конкретного промта"""
        pass
    
    @abstractmethod
    async def get_snapshots_by_session_id(self, session_id: str) -> List[PromptExecutionSnapshot]:
        """Получить снапшоты для конкретной сессии"""
        pass
    
    @abstractmethod
    async def calculate_rejection_rate(self, prompt_id: str) -> float:
        """Вычислить процент отклонений для промта"""
        pass