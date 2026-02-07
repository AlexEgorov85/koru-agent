from typing import Optional, List, Dict
from domain.models.prompt.prompt_version import PromptVersion, PromptStatus, PromptUsageMetrics, PromptExecutionSnapshot
from domain.abstractions.prompt_repository import IPromptRepository, ISnapshotManager
from infrastructure.services.prompt_storage.prompt_loader import PromptLoader
import logging
from datetime import datetime
from collections import defaultdict

class FilePromptRepository(IPromptRepository):
    """
    Файловый репозиторий промтов, работающий только с файловой системой.
    Загружает промты из директории prompts/ и хранит в памяти.
    """
    
    def __init__(self, loader: Optional[PromptLoader] = None, base_path: str = "prompts"):
        self.loader = loader or PromptLoader(base_path)
        self.versions: List[PromptVersion] = []
        self._capability_indexes: Dict[str, List[PromptVersion]] = defaultdict(list)
        self._address_indexes: Dict[str, List[PromptVersion]] = defaultdict(list)
        self._version_lookup: Dict[str, PromptVersion] = {}
        self._logger = logging.getLogger(__name__)
        self._loaded = False
        
    def load_from_directory(self, path: str = "prompts") -> List[str]:
        """
        Загружает промты из указанной директории.
        
        Args:
            path: Путь к директории с промтами
            
        Returns:
            List[str]: Список ошибок загрузки
        """
        self.loader = PromptLoader(path)
        self.versions, errors = self.loader.load_all_prompts()
        
        # Создаем индексы для быстрого поиска
        self._build_indexes()
        self._loaded = True
        
        return errors
    
    def _build_indexes(self):
        """Создает индексы для быстрого поиска промтов"""
        self._capability_indexes.clear()
        self._address_indexes.clear()
        self._version_lookup.clear()
        
        for version in self.versions:
            # Индекс по capability
            capability_key = f"{version.domain.value}:{version.capability_name}"
            self._capability_indexes[capability_key].append(version)
            
            # Индекс по адресу (domain:capability:provider:role)
            address_key = f"{version.domain.value}:{version.capability_name}:{version.provider_type.value}:{version.role.value}"
            self._address_indexes[address_key].append(version)
            
            # Lookup по ID
            self._version_lookup[version.id] = version
    
    def _ensure_loaded(self):
        """Убеждается, что промты загружены"""
        if not self._loaded:
            self.load_from_directory()
    
    def get_active_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить активную версию промта по адресу"""
        self._ensure_loaded()
        
        address_key = f"{domain}:{capability_name}:{provider_type}:{role}"
        versions = self._address_indexes.get(address_key, [])
        
        # Найти активную версию (самую последнюю по семантической версии)
        active_versions = [v for v in versions if v.status == PromptStatus.ACTIVE]
        
        if not active_versions:
            return None
        
        # Сортируем по семантической версии (предполагаем формат X.Y.Z)
        def version_key(v):
            parts = v.semantic_version.split('.')
            return tuple(int(p) for p in parts)
        
        return sorted(active_versions, key=version_key, reverse=True)[0]
    
    def get_shadow_version(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> Optional[PromptVersion]:
        """Получить теневую (shadow) версию для A/B тестирования"""
        self._ensure_loaded()
        
        address_key = f"{domain}:{capability_name}:{provider_type}:{role}"
        versions = self._address_indexes.get(address_key, [])
        
        # Найти теневую версию
        shadow_versions = [v for v in versions if v.status == PromptStatus.SHADOW]
        
        if not shadow_versions:
            return None
        
        # Сортируем по семантической версии
        def version_key(v):
            parts = v.semantic_version.split('.')
            return tuple(int(p) for p in parts)
        
        return sorted(shadow_versions, key=version_key, reverse=True)[0]
    
    def get_version_by_id(self, version_id: str) -> Optional[PromptVersion]:
        """Получить версию промта по ID"""
        self._ensure_loaded()
        return self._version_lookup.get(version_id)
    
    def save_version(self, version: PromptVersion) -> None:
        """Сохранить новую версию промта (не поддерживается в файловом репозитории)"""
        raise NotImplementedError("FilePromptRepository не поддерживает сохранение версий в файлы")
    
    def update_version_status(self, version_id: str, status: PromptStatus) -> None:
        """Обновить статус версии промта (не поддерживается в файловом репозитории)"""
        raise NotImplementedError("FilePromptRepository не поддерживает обновление статуса версий")
    
    def activate_version(self, version_id: str) -> None:
        """Активировать версию промта (не поддерживается в файловом репозитории)"""
        raise NotImplementedError("FilePromptRepository не поддерживает активацию версий")
    
    def archive_version(self, version_id: str) -> None:
        """Архивировать версию промта (не поддерживается в файловом репозитории)"""
        raise NotImplementedError("FilePromptRepository не поддерживает архивацию версий")
    
    def list_versions(self, capability_name: str) -> List[PromptVersion]:
        """Получить все версии для конкретной capability"""
        self._ensure_loaded()
        return self._capability_indexes.get(f"*:{capability_name}", [])  # домен не важен для поиска по capability
    
    def list_versions_by_address(
        self,
        domain: str,
        capability_name: str,
        provider_type: str,
        role: str
    ) -> List[PromptVersion]:
        """Получить все версии по адресу"""
        self._ensure_loaded()
        address_key = f"{domain}:{capability_name}:{provider_type}:{role}"
        return self._address_indexes.get(address_key, [])
    
    def update_usage_metrics(
        self,
        version_id: str,
        metrics_update: PromptUsageMetrics
    ) -> None:
        """Обновить метрики использования версии промта (не поддерживается в файловом репозитории)"""
        # Не поддерживается в файловом репозитории
        pass


class FileSnapshotManager(ISnapshotManager):
    """
    Менеджер снапшотов для файлового репозитория.
    Хранит снапшоты в памяти (для production систем рекомендуется использовать БД).
    """
    
    def __init__(self):
        self.snapshots: List[PromptExecutionSnapshot] = []
        self._prompt_snapshots: Dict[str, List[PromptExecutionSnapshot]] = defaultdict(list)
        self._session_snapshots: Dict[str, List[PromptExecutionSnapshot]] = defaultdict(list)
        self._logger = logging.getLogger(__name__)
    
    async def save_snapshot(self, snapshot: PromptExecutionSnapshot) -> None:
        """Сохранить снапшот выполнения промта в память"""
        self.snapshots.append(snapshot)
        self._prompt_snapshots[snapshot.prompt_id].append(snapshot)
        self._session_snapshots[snapshot.session_id].append(snapshot)
    
    async def get_snapshots_by_prompt_id(self, prompt_id: str, limit: int = 100) -> List[PromptExecutionSnapshot]:
        """Получить снапшоты для конкретного промта"""
        snapshots = self._prompt_snapshots.get(prompt_id, [])
        return sorted(snapshots, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    async def get_snapshots_by_session_id(self, session_id: str) -> List[PromptExecutionSnapshot]:
        """Получить снапшоты для конкретной сессии"""
        return self._session_snapshots.get(session_id, [])
    
    async def calculate_rejection_rate(self, prompt_id: str) -> float:
        """Вычислить процент отклонений для промта"""
        snapshots = self._prompt_snapshots.get(prompt_id, [])
        if not snapshots:
            return 0.0
        
        total = len(snapshots)
        rejections = sum(1 for s in snapshots if s.rejection_reason is not None)
        return rejections / total if total > 0 else 0.0