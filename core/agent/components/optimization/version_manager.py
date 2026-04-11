"""
VersionManager - управление версиями промптов.

ОТВЕТСТВЕННОСТЬ:
- Хранение истории версий
- Управление статусами (candidate, active, rejected)
- Гарантия наличия только 1 active версии
- Поддержка parent_id для всех версий
- Возможность отката к предыдущим версиям
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from core.components.benchmarks.benchmark_models import PromptVersion, MutationType
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType
from core.infrastructure.logging.event_types import LogEventType

_logger = logging.getLogger(__name__)


@dataclass
class VersionRegistry:
    """Реестр версий для capability"""
    capability: str
    versions: Dict[str, PromptVersion] = field(default_factory=dict)
    active_version_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class VersionManager:
    """
    Менеджер версий промптов.

    RESPONSIBILITIES:
    - Регистрация новых версий
    - Управление статусами версий
    - Гарантия единственной active версии
    - Хранение истории (100% версий имеют parent_id)
    - Поддержка отката к предыдущим версиям

    VERSION STATES:
    - candidate: новая версия, ожидает оценки
    - active: текущая активная версия
    - rejected: отклонённая версия

    USAGE:
    ```python
    manager = VersionManager(event_bus)
    await manager.register(version)
    await manager.promote(version_id)
    await manager.reject(version_id)
    active = await manager.get_active(capability)
    ```
    """

    def __init__(self, event_bus: UnifiedEventBus):
        """
        Инициализация VersionManager.

        ARGS:
        - event_bus: шина событий
        """
        self.event_bus = event_bus

        # Реестры по capability
        self._registries: Dict[str, VersionRegistry] = {}

    async def register(self, version: PromptVersion) -> bool:
        """
        Регистрация новой версии.

        ARGS:
        - version: версия для регистрации

        RETURNS:
        - bool: успешно ли зарегистрирована
        """
        # Валидация parent_id (кроме первой версии)
        if not version.parent_id:
            # Проверка есть ли уже версии для этого capability
            registry = self._get_registry(version.capability)
            if registry.versions:
                _logger.warning(
                    f"Версия {version.id} не имеет parent_id, "
                    f"но существуют другие версии",
                    extra={"event_type": LogEventType.WARNING}
                )

        # Получение или создание реестра
        registry = self._get_registry(version.capability)

        # Регистрация
        registry.versions[version.id] = version

        _logger.info(
            f"Зарегистрирована версия {version.id} "
            f"для {version.capability}",
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )

        # Публикация события
        await self._publish_version_registered(version)

        return True

    async def promote(self, version_id: str, capability: str) -> bool:
        """
        Продвижение версии в active.

        ARGS:
        - version_id: ID версии для продвижения
        - capability: название способности

        RETURNS:
        - bool: успешно ли продвижение
        """
        registry = self._get_registry(capability)

        if version_id not in registry.versions:
            _logger.error(
                f"Версия {version_id} не найдена для {capability}",
                extra={"event_type": LogEventType.ERROR}
            )
            return False

        version = registry.versions[version_id]

        # Снятие статуса active с текущей версии
        if registry.active_version_id:
            old_active = registry.versions.get(registry.active_version_id)
            if old_active:
                old_active.status = 'candidate'  # Возвращаем в candidate

        # Установка новой active версии
        version.status = 'active'
        registry.active_version_id = version_id

        _logger.info(
            f"Версия {version_id} продвинута в active для {capability}",
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )

        # Публикация события
        await self._publish_version_promoted(version)

        return True

    async def reject(self, version_id: str, capability: str, reason: str = "") -> bool:
        """
        Отклонение версии.

        ARGS:
        - version_id: ID версии для отклонения
        - capability: название способности
        - reason: причина отклонения

        RETURNS:
        - bool: успешно ли отклонение
        """
        registry = self._get_registry(capability)

        if version_id not in registry.versions:
            _logger.error(
                f"Версия {version_id} не найдена для {capability}",
                extra={"event_type": LogEventType.ERROR}
            )
            return False

        version = registry.versions[version_id]

        # Нельзя отклонить active версию
        if version.status == 'active':
            _logger.warning(
                f"Нельзя отклонить active версию {version_id}",
                extra={"event_type": LogEventType.WARNING}
            )
            return False

        version.status = 'rejected'
        version.metadata = version.metadata or {}
        version.metadata['rejection_reason'] = reason
        version.metadata['rejected_at'] = datetime.now().isoformat()

        _logger.info(
            f"Версия {version_id} отклонена: {reason}",
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )

        # Публикация события
        await self._publish_version_rejected(version, reason)

        return True

    async def get_active(self, capability: str) -> Optional[PromptVersion]:
        """
        Получение активной версии.

        ARGS:
        - capability: название способности

        RETURNS:
        - Optional[PromptVersion]: активная версия или None
        """
        registry = self._get_registry(capability)

        if registry.active_version_id:
            return registry.versions.get(registry.active_version_id)

        return None

    async def get_version(
        self,
        capability: str,
        version_id: str
    ) -> Optional[PromptVersion]:
        """
        Получение версии по ID.

        ARGS:
        - capability: название способности
        - version_id: ID версии

        RETURNS:
        - Optional[PromptVersion]: версия или None
        """
        registry = self._get_registry(capability)
        return registry.versions.get(version_id)

    async def get_history(self, capability: str) -> List[PromptVersion]:
        """
        Получение истории версий.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[PromptVersion]: список версий (от новых к старым)
        """
        registry = self._get_registry(capability)

        versions = list(registry.versions.values())

        # Сортировка по времени создания (новые первые)
        versions.sort(key=lambda v: v.created_at, reverse=True)

        return versions

    async def get_parent(
        self,
        capability: str,
        version_id: str
    ) -> Optional[PromptVersion]:
        """
        Получение родительской версии.

        ARGS:
        - capability: название способности
        - version_id: ID версии

        RETURNS:
        - Optional[PromptVersion]: родительская версия или None
        """
        version = await self.get_version(capability, version_id)

        if version and version.parent_id:
            return await self.get_version(capability, version.parent_id)

        return None

    async def rollback(
        self,
        capability: str,
        target_version_id: str
    ) -> bool:
        """
        Откат к предыдущей версии.

        ARGS:
        - capability: название способности
        - target_version_id: ID версии для отката

        RETURNS:
        - bool: успешно ли откат
        """
        registry = self._get_registry(capability)

        if target_version_id not in registry.versions:
            _logger.error(
                f"Версия {target_version_id} не найдена для {capability}",
                extra={"event_type": LogEventType.ERROR}
            )
            return False

        target = registry.versions[target_version_id]

        # Проверка что версия не rejected
        if target.status == 'rejected':
            _logger.warning(
                f"Нельзя откатиться к rejected версии {target_version_id}",
                extra={"event_type": LogEventType.WARNING}
            )
            return False

        # Продвижение целевой версии
        return await self.promote(target_version_id, capability)

    def _get_registry(self, capability: str) -> VersionRegistry:
        """
        Получение или создание реестра для capability.

        ARGS:
        - capability: название способности

        RETURNS:
        - VersionRegistry: реестр
        """
        if capability not in self._registries:
            self._registries[capability] = VersionRegistry(capability=capability)

        return self._registries[capability]

    async def _publish_version_registered(self, version: PromptVersion) -> None:
        """Публикация события регистрации версии"""
        await self.event_bus.publish(
            EventType.CAPABILITY_SELECTED,  # Используем существующий тип
            data={
                'version_id': version.id,
                'capability': version.capability,
                'parent_id': version.parent_id,
                'status': version.status,
                'mutation_type': version.mutation_type.value if version.mutation_type else None,
                'timestamp': datetime.now().isoformat()
            }
        )

    async def _publish_version_promoted(self, version: PromptVersion) -> None:
        """Публикация события продвижения версии"""
        await self.event_bus.publish(
            EventType.OPTIMIZATION_CYCLE_COMPLETED,  # Используем существующий тип
            data={
                'version_id': version.id,
                'capability': version.capability,
                'status': 'active',
                'timestamp': datetime.now().isoformat()
            }
        )

    async def _publish_version_rejected(
        self,
        version: PromptVersion,
        reason: str
    ) -> None:
        """Публикация события отклонения версии"""
        await self.event_bus.publish(
            EventType.ERROR_OCCURRED,  # Используем существующий тип
            data={
                'version_id': version.id,
                'capability': version.capability,
                'status': 'rejected',
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }
        )

    def get_stats(self, capability: str) -> Dict[str, Any]:
        """
        Получение статистики версий.

        ARGS:
        - capability: название способности

        RETURNS:
        - Dict[str, Any]: статистика
        """
        registry = self._get_registry(capability)

        versions = list(registry.versions.values())

        status_counts = {
            'candidate': 0,
            'active': 0,
            'rejected': 0
        }

        mutation_counts = {}

        for version in versions:
            status_counts[version.status] = status_counts.get(version.status, 0) + 1

            if version.mutation_type:
                mt = version.mutation_type.value
                mutation_counts[mt] = mutation_counts.get(mt, 0) + 1

        # Проверка что все версии имеют parent_id (кроме первой)
        versions_with_parent = sum(
            1 for v in versions if v.parent_id is not None
        )
        first_version = len(versions) > 0 and versions[-1].parent_id is None

        all_have_parent = (
            versions_with_parent == len(versions) or
            (versions_with_parent == len(versions) - 1 and first_version)
        )

        return {
            'total_versions': len(versions),
            'status_distribution': status_counts,
            'mutation_type_distribution': mutation_counts,
            'active_version_id': registry.active_version_id,
            'all_versions_have_parent': all_have_parent,
            'meets_requirement': all_have_parent
        }

    async def get_lineage(self, capability: str, version_id: str) -> List[PromptVersion]:
        """
        Получение линии наследования версии.

        ARGS:
        - capability: название способности
        - version_id: ID версии

        RETURNS:
        - List[PromptVersion]: цепочка версий от корня до указанной
        """
        lineage = []
        current_id = version_id

        while current_id:
            version = await self.get_version(capability, current_id)
            if not version:
                break

            lineage.append(version)
            current_id = version.parent_id

        # Разворот (от корня к текущей)
        lineage.reverse()
        return lineage
