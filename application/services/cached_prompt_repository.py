from typing import Optional, Dict, List
from collections import defaultdict
import asyncio
from domain.models.prompt.prompt_version import PromptVersion, PromptStatus, PromptRole, PromptUsageMetrics
from domain.abstractions.prompt_repository import IPromptRepository
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType

# Глобальный реестр для очистки кэшей в тестах
_all_instances = []


class CachedPromptRepository(IPromptRepository):
    """Обертка репозитория с in-memory кэшированием"""
    
    def __init__(self, underlying_repo: IPromptRepository):
        self._underlying_repo = underlying_repo
        self._cache: Dict[str, PromptVersion] = {}
        self._address_index: Dict[str, str] = {}  # address_key -> version_id
        self._capability_index: Dict[str, List[str]] = defaultdict(list)  # capability -> [version_ids]
        self._lock = asyncio.Lock()
        # Добавляем экземпляр в глобальный реестр
        _all_instances.append(self)
    
    async def get_active_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить активную версию промта по адресу (с кэшированием)"""
        address_key = f"{domain}:{provider_type}:{capability_name}:{role}"
        
        # Проверяем кэш
        version_id = self._address_index.get(address_key)
        if version_id and version_id in self._cache:
            cached_version = self._cache[version_id]
            if cached_version.status == PromptStatus.ACTIVE:
                return cached_version
        
        # Запрашиваем из underlying repo
        version = await self._underlying_repo.get_active_version(domain, capability_name, provider_type, role)
        
        if version:
            # Обновляем кэш
            async with self._lock:
                self._cache[version.id] = version
                self._address_index[address_key] = version.id
                self._capability_index[capability_name].append(version.id)
        
        return version
    
    async def get_shadow_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить теневую (shadow) версию для A/B тестирования (с кэшированием)"""
        address_key = f"{domain}:{provider_type}:{capability_name}:{role}_shadow"
        
        # Проверяем кэш
        version_id = self._address_index.get(address_key)
        if version_id and version_id in self._cache:
            cached_version = self._cache[version_id]
            if cached_version.status == PromptStatus.SHADOW:
                return cached_version
        
        # Запрашиваем из underlying repo
        version = await self._underlying_repo.get_shadow_version(domain, capability_name, provider_type, role)
        
        if version:
            # Обновляем кэш
            async with self._lock:
                self._cache[version.id] = version
                self._address_index[address_key] = version.id
                self._capability_index[capability_name].append(version.id)
        
        return version
    
    async def get_version_by_id(self, version_id: str) -> Optional[PromptVersion]:
        """Получить версию промта по ID (с кэшированием)"""
        # Проверяем кэш
        if version_id in self._cache:
            return self._cache[version_id]
        
        # Запрашиваем из underlying repo
        version = await self._underlying_repo.get_version_by_id(version_id)
        
        if version:
            # Обновляем кэш
            async with self._lock:
                self._cache[version_id] = version
        
        return version
    
    async def save_version(self, version: PromptVersion) -> None:
        """Сохранить версию и обновить кэш"""
        await self._underlying_repo.save_version(version)
        
        # Обновляем кэш
        async with self._lock:
            self._cache[version.id] = version
            self._capability_index[version.capability_name].append(version.id)
    
    async def update_version_status(self, version_id: str, status: PromptStatus) -> None:
        """Обновить статус версии и кэш"""
        await self._underlying_repo.update_version_status(version_id, status)
        
        # Обновляем кэш
        version = await self.get_version_by_id(version_id)
        if version:
            updated_version = version.model_copy(update={'status': status})
            async with self._lock:
                self._cache[version_id] = updated_version
    
    async def activate_version(self, version_id: str) -> None:
        """Активировать версию и обновить кэш"""
        await self._underlying_repo.activate_version(version_id)
        
        # Обновляем кэш - получаем напрямую из underlying repo, чтобы получить актуальный статус
        new_version = await self._underlying_repo.get_version_by_id(version_id)
        if new_version:
            # Обновляем кэш
            async with self._lock:
                self._cache[version_id] = new_version
                # Обновляем индекс адреса
                new_address_key = new_version.get_address_key()
                self._address_index[new_address_key] = version_id
    
    async def archive_version(self, version_id: str) -> None:
        """Архивировать версию и обновить кэш"""
        await self._underlying_repo.archive_version(version_id)
        
        # Обновляем кэш
        version = await self.get_version_by_id(version_id)
        if version:
            updated_version = version.model_copy(update={'status': PromptStatus.ARCHIVED})
            async with self._lock:
                self._cache[version_id] = updated_version
    
    async def list_versions(self, capability_name: str) -> List[PromptVersion]:
        """Получить все версии для capability (с кэшированием)"""
        cached_ids = self._capability_index.get(capability_name, [])
        result = []
        
        # Проверяем кэш
        for version_id in cached_ids:
            if version_id in self._cache:
                result.append(self._cache[version_id])
        
        # Если в кэше нет всех версий, запрашиваем из underlying repo
        if len(result) != len(cached_ids):
            db_versions = await self._underlying_repo.list_versions(capability_name)
            result = db_versions
            
            # Обновляем кэш
            async with self._lock:
                for version in db_versions:
                    self._cache[version.id] = version
                self._capability_index[capability_name] = [v.id for v in db_versions]
        
        return result
    
    async def list_versions_by_address(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> List[PromptVersion]:
        """Получить все версии по адресу (с кэшированием)"""
        # Проверяем кэш
        cached_ids = self._capability_index.get(capability_name, [])
        result = []
        
        for version_id in cached_ids:
            if version_id in self._cache:
                version = self._cache[version_id]
                if (version.domain.value == domain and 
                    version.capability_name == capability_name and
                    version.provider_type.value == provider_type and
                    version.role.value == role):
                    result.append(version)
        
        # Если в кэше нет всех версий, запрашиваем из underlying repo
        if len(result) == 0:
            db_versions = await self._underlying_repo.list_versions_by_address(
                domain, capability_name, provider_type, role
            )
            result = db_versions
            
            # Обновляем кэш
            async with self._lock:
                for version in db_versions:
                    self._cache[version.id] = version
                    self._capability_index[capability_name].append(version.id)
        
        return result
    
    async def update_usage_metrics(
        self,
        version_id: str,
        metrics_update: PromptUsageMetrics
    ) -> None:
        """Обновить метрики использования версии промта"""
        await self._underlying_repo.update_usage_metrics(version_id, metrics_update)
        
        # Обновляем кэш
        version = await self.get_version_by_id(version_id)
        if version:
            updated_metrics = version.usage_metrics.model_copy(update={
                'usage_count': version.usage_metrics.usage_count + metrics_update.usage_count,
                'success_count': version.usage_metrics.success_count + metrics_update.success_count,
                'avg_generation_time': (
                    (version.usage_metrics.avg_generation_time * version.usage_metrics.usage_count + 
                     metrics_update.avg_generation_time * metrics_update.usage_count) /
                    max(version.usage_metrics.usage_count + metrics_update.usage_count, 1)
                ),
                'last_used_at': metrics_update.last_used_at or version.usage_metrics.last_used_at,
                'error_rate': (
                    (version.usage_metrics.error_rate * version.usage_metrics.usage_count + 
                     metrics_update.error_rate * metrics_update.usage_count) /
                    max(version.usage_metrics.usage_count + metrics_update.usage_count, 1)
                ),
                'rejection_count': version.usage_metrics.rejection_count + metrics_update.rejection_count
            })
            
            updated_version = version.model_copy(update={'usage_metrics': updated_metrics})
            async with self._lock:
                self._cache[version_id] = updated_version
    
    async def refresh_cache(self) -> None:
        """Полностью обновить кэш из underlying репозитория"""
        async with self._lock:
            self._cache.clear()
            self._address_index.clear()
            self._capability_index.clear()

    @classmethod
    def clear_all_caches(cls) -> None:
        """Очистить кэши ВСЕХ экземпляров (для тестов)"""
        global _all_instances
        for instance in _all_instances:
            instance._cache.clear()
            instance._address_index.clear()
            instance._capability_index.clear()
        # Очищаем сам список экземпляров
        _all_instances.clear()
