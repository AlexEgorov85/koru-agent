"""
Модуль загрузки ресурсов.

ЕДИНЫЙ источник для всех ресурсов (промпты, контракты).
Заменяет: ResourceDiscovery, FileSystemDataSource, DataRepository, ResourcePreloader.
"""
from core.infrastructure.loading.resource_loader import ResourceLoader

__all__ = ["ResourceLoader"]
