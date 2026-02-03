from typing import Optional, List, Dict, Any
from domain.abstractions.prompt_repository import IPromptRepository
from domain.models.prompt.prompt_version import PromptVersion, PromptStatus, PromptRole, PromptUsageMetrics
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from datetime import datetime


class InMemoryPromptRepository(IPromptRepository):
    """
    Репозиторий промтов в памяти для тестирования.
    """
    
    def __init__(self):
        self._versions: Dict[str, PromptVersion] = {}
        self._address_index: Dict[str, List[str]] = {}  # индекс по адресам
    
    def _get_address_key(self, domain: str, capability_name: str, provider_type: str, role: str) -> str:
        """Получить ключ адреса для индекса"""
        return f"{domain}:{capability_name}:{provider_type}:{role}"
    
    async def get_active_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить активную версию промта по адресу"""
        address_key = self._get_address_key(domain, capability_name, provider_type, role)
        
        if address_key not in self._address_index:
            return None
            
        for version_id in self._address_index[address_key]:
            version = self._versions[version_id]
            if version.status == PromptStatus.ACTIVE:
                return version
        
        return None
    
    async def get_shadow_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить теневую (shadow) версию для A/B тестирования"""
        address_key = self._get_address_key(domain, capability_name, provider_type, role)
        
        if address_key not in self._address_index:
            return None
            
        for version_id in self._address_index[address_key]:
            version = self._versions[version_id]
            if version.status == PromptStatus.SHADOW:
                return version
        
        return None
    
    async def get_version_by_id(self, version_id: str) -> Optional[PromptVersion]:
        """Получить версию промта по ID"""
        return self._versions.get(version_id)
    
    async def save_version(self, version: PromptVersion) -> None:
        """Сохранить новую версию промта"""
        # Сохраняем версию
        self._versions[version.id] = version
        
        # Обновляем индекс по адресу
        address_key = self._get_address_key(
            version.domain.value,
            version.capability_name,
            version.provider_type.value,
            version.role.value
        )
        
        if address_key not in self._address_index:
            self._address_index[address_key] = []
        
        # Добавляем в начало списка, чтобы самые новые были первыми
        self._address_index[address_key].insert(0, version.id)
    
    async def update_version_status(self, version_id: str, status: PromptStatus) -> None:
        """Обновить статус версии промта"""
        if version_id in self._versions:
            version = self._versions[version_id]
            # Создаем обновленную версию с новым статусом
            updated_version = version.model_copy(update={'status': status})
            self._versions[version_id] = updated_version
    
    async def activate_version(self, version_id: str) -> None:
        """Активировать версию промта (и деактивировать текущую активную)"""
        target_version = await self.get_version_by_id(version_id)
        if not target_version:
            raise ValueError(f"Version with ID {version_id} not found")
        
        # Деактивировать текущую активную версию для этого адреса
        address_key = self._get_address_key(
            target_version.domain.value,
            target_version.capability_name,
            target_version.provider_type.value,
            target_version.role.value
        )
        
        if address_key in self._address_index:
            for vid in self._address_index[address_key]:
                existing_version = self._versions[vid]
                if existing_version.status == PromptStatus.ACTIVE:
                    await self.update_version_status(vid, PromptStatus.DEPRECATED)
        
        # Активировать новую версию
        await self.update_version_status(version_id, PromptStatus.ACTIVE)
    
    async def archive_version(self, version_id: str) -> None:
        """Архивировать версию промта"""
        await self.update_version_status(version_id, PromptStatus.ARCHIVED)
    
    async def list_versions(self, capability_name: str) -> List[PromptVersion]:
        """Получить все версии для конкретной capability"""
        versions = []
        for version in self._versions.values():
            if version.capability_name == capability_name:
                versions.append(version)
        
        # Сортируем по дате создания (предполагаем, что более поздние даты означают более новые версии)
        versions.sort(key=lambda v: v.created_at or datetime.min, reverse=True)
        return versions
    
    async def list_versions_by_address(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> List[PromptVersion]:
        """Получить все версии по адресу"""
        address_key = self._get_address_key(domain, capability_name, provider_type, role)
        
        if address_key not in self._address_index:
            return []
        
        versions = []
        for version_id in self._address_index[address_key]:
            version = self._versions[version_id]
            versions.append(version)
        
        return versions
    
    async def update_usage_metrics(
        self,
        version_id: str,
        metrics_update: PromptUsageMetrics
    ) -> None:
        """Обновить метрики использования версии промта"""
        if version_id in self._versions:
            version = self._versions[version_id]
            current_metrics = version.usage_metrics
            new_metrics = PromptUsageMetrics(
                usage_count=current_metrics.usage_count + metrics_update.usage_count,
                success_count=current_metrics.success_count + metrics_update.success_count,
                avg_generation_time=(
                    (current_metrics.avg_generation_time * current_metrics.usage_count + 
                     metrics_update.avg_generation_time * metrics_update.usage_count) /
                    max(1, current_metrics.usage_count + metrics_update.usage_count)
                ),
                last_used_at=metrics_update.last_used_at or current_metrics.last_used_at,
                error_rate=(
                    (current_metrics.error_rate * current_metrics.usage_count + 
                     metrics_update.error_rate * metrics_update.usage_count) /
                    max(1, current_metrics.usage_count + metrics_update.usage_count)
                ),
                rejection_count=current_metrics.rejection_count + metrics_update.rejection_count
            )
            
            # Создаем обновленную версию с новыми метриками
            updated_version = version.model_copy(update={
                'usage_metrics': new_metrics
            })
            self._versions[version_id] = updated_version