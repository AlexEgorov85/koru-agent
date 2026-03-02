"""
Менеджер жизненного цикла провайдеров.

АРХИТЕКТУРА:
- Централизованное управление lifecycle провайдеров
- Группировка провайдеров по типам (llm, db, vector, embedding)
- Автоматическая проверка здоровья
- Корректное завершение работы в правильном порядке
- Интеграция с Event Bus для событий lifecycle

ПРЕИМУЩЕСТВА:
- ✅ Единая точка управления провайдерами
- ✅ Автоматический health check всех провайдеров
- ✅ Корректный shutdown в обратном порядке регистрации
- ✅ События lifecycle для наблюдаемости
- ✅ Статистика и мониторинг состояния
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Type, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from core.infrastructure.providers.base_provider import (
    IProvider,
    BaseProvider,
    ProviderHealthStatus,
)
from core.infrastructure.event_bus import (
    EventDomain,
    EventType,
)


logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Типы провайдеров."""
    LLM = "llm"
    DATABASE = "database"
    VECTOR = "vector"
    EMBEDDING = "embedding"
    CACHE = "cache"
    STORAGE = "storage"
    OTHER = "other"


@dataclass
class ProviderInfo:
    """Информация о провайдере."""
    name: str
    provider_type: ProviderType
    provider: IProvider
    registered_at: datetime = field(default_factory=datetime.now)
    initialized: bool = False
    health_status: str = ProviderHealthStatus.UNKNOWN
    last_health_check: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "name": self.name,
            "provider_type": self.provider_type.value,
            "initialized": self.initialized,
            "health_status": self.health_status,
            "registered_at": self.registered_at.isoformat(),
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "metadata": self.metadata,
        }


@dataclass
class HealthCheckResult:
    """Результат проверки здоровья."""
    provider_name: str
    status: str
    is_healthy: bool
    details: Dict = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "provider_name": self.provider_name,
            "status": self.status,
            "is_healthy": self.is_healthy,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


class ProviderLifecycleManager:
    """
    Централизованное управление жизненным циклом провайдеров.
    
    FEATURES:
    - Регистрация провайдеров с типизацией
    - Поэтапная инициализация (по типам)
    - Массовая проверка здоровья
    - Корректный shutdown в обратном порядке
    - Интеграция с Event Bus
    - Статистика и мониторинг
    
    USAGE:
    ```python
    # Создание менеджера
    lifecycle_manager = ProviderLifecycleManager()
    
    # Регистрация провайдера
    llm_provider = LlamaCppProvider(name="default_llm", config={...})
    await lifecycle_manager.register(
        name="default_llm",
        provider=llm_provider,
        provider_type=ProviderType.LLM
    )
    
    # Инициализация всех провайдеров
    await lifecycle_manager.initialize_all()
    
    # Проверка здоровья
    health_results = await lifecycle_manager.health_check_all()
    
    # Завершение работы
    await lifecycle_manager.shutdown_all()
    ```
    """

    def __init__(self, event_bus=None):
        """
        Инициализация менеджера lifecycle.

        ARGS:
        - event_bus: шина событий (опционально)
        """
        self._providers: Dict[str, ProviderInfo] = {}
        self._providers_by_type: Dict[ProviderType, List[str]] = {
            pt: [] for pt in ProviderType
        }
        self._event_bus = event_bus
        self._initialized = False
        self._shutdown_in_progress = False

        self._logger = logging.getLogger(f"{__name__}.LifecycleManager")
        self._logger.info("ProviderLifecycleManager создан")
    
    async def register(
        self,
        name: str,
        provider: IProvider,
        provider_type: ProviderType = ProviderType.OTHER,
        metadata: Dict = None
    ) -> None:
        """
        Регистрация провайдера в менеджере.
        
        ARGS:
        - name: уникальное имя провайдера
        - provider: экземпляр провайдера
        - provider_type: тип провайдера
        - metadata: дополнительные метаданные
        
        RAISES:
        - ValueError: если провайдер с таким именем уже зарегистрирован
        """
        if name in self._providers:
            raise ValueError(f"Провайдер '{name}' уже зарегистрирован")
        
        provider_info = ProviderInfo(
            name=name,
            provider_type=provider_type,
            provider=provider,
            metadata=metadata or {},
        )
        
        self._providers[name] = provider_info
        self._providers_by_type[provider_type].append(name)
        
        self._self.event_bus_logger.info(f"Зарегистрирован провайдер '{name}' типа {provider_type.value}")
        
        # Событие регистрации
        await self._event_bus.publish(
            EventType.PROVIDER_REGISTERED,
            data={
                "provider_name": name,
                "provider_type": provider_type.value,
            },
            domain=EventDomain.INFRASTRUCTURE,
        )
    
    async def unregister(self, name: str) -> bool:
        """
        Удаление провайдера из менеджера.
        
        ARGS:
        - name: имя провайдера
        
        RETURNS:
        - bool: True если провайдер удален, False если не найден
        """
        if name not in self._providers:
            self._self.event_bus_logger.warning(f"Провайдер '{name}' не найден")
            return False
        
        provider_info = self._providers[name]
        
        # Shutdown если провайдер инициализирован
        if provider_info.initialized:
            await self._shutdown_provider(provider_info)
        
        # Удаление из реестров
        del self._providers[name]
        provider_type = provider_info.provider_type
        if name in self._providers_by_type[provider_type]:
            self._providers_by_type[provider_type].remove(name)
        
        self._self.event_bus_logger.info(f"Удален провайдер '{name}'")
        
        # Событие удаления
        await self._event_bus.publish(
            EventType.PROVIDER_UNREGISTERED,
            data={"provider_name": name},
            domain=EventDomain.INFRASTRUCTURE,
        )
        
        return True
    
    async def initialize_all(self) -> Dict[str, bool]:
        """
        Инициализация всех зарегистрированных провайдеров.
        
        RETURNS:
        - Dict[str, bool]: результаты инициализации по каждому провайдеру
        """
        if self._shutdown_in_progress:
            self._self.event_bus_logger.warning("Инициализация во время shutdown запрещена")
            return {}
        
        results = {}
        
        self._self.event_bus_logger.info(f"Начало инициализации {len(self._providers)} провайдеров")
        
        # Инициализация по типам (сначала基础设施, потом остальные)
        init_order = [
            ProviderType.DATABASE,
            ProviderType.CACHE,
            ProviderType.VECTOR,
            ProviderType.EMBEDDING,
            ProviderType.LLM,
            ProviderType.STORAGE,
            ProviderType.OTHER,
        ]
        
        for provider_type in init_order:
            provider_names = self._providers_by_type[provider_type]
            if not provider_names:
                continue
            
            self._self.event_bus_logger.debug(f"Инициализация провайдеров типа {provider_type.value}: {provider_names}")
            
            for name in provider_names:
                provider_info = self._providers[name]
                result = await self._initialize_provider(provider_info)
                results[name] = result
        
        self._initialized = True
        self._self.event_bus_logger.info(f"Инициализация завершена: {sum(results.values())}/{len(results)} успешно")
        
        # Событие инициализации
        await self._event_bus.publish(
            EventType.SYSTEM_INITIALIZED,
            data={
                "component": "ProviderLifecycleManager",
                "providers_count": len(results),
                "success_count": sum(results.values()),
            },
            domain=EventDomain.INFRASTRUCTURE,
        )
        
        return results
    
    async def _initialize_provider(self, provider_info: ProviderInfo) -> bool:
        """
        Инициализация одного провайдера.
        
        ARGS:
        - provider_info: информация о провайдере
        
        RETURNS:
        - bool: True если инициализация успешна
        """
        name = provider_info.name
        provider = provider_info.provider
        
        try:
            self._self.event_bus_logger.debug(f"Инициализация провайдера '{name}'")
            
            result = await provider.initialize()
            
            if result:
                provider_info.initialized = True
                provider_info.health_status = ProviderHealthStatus.HEALTHY
                self._self.event_bus_logger.info(f"Провайдер '{name}' успешно инициализирован")
            else:
                provider_info.health_status = ProviderHealthStatus.UNHEALTHY
                self._self.event_bus_logger.error(f"Провайдер '{name}' вернул False при инициализации")
            
            return result
            
        except Exception as e:
            provider_info.health_status = ProviderHealthStatus.UNHEALTHY
            self._self.event_bus_logger.error(f"Ошибка инициализации провайдера '{name}': {e}", exc_info=True)
            
            # Событие ошибки
            await self._event_bus.publish(
                EventType.SYSTEM_ERROR,
                data={
                    "component": "ProviderLifecycleManager",
                    "provider_name": name,
                    "error": str(e),
                    "stage": "initialization",
                },
                domain=EventDomain.INFRASTRUCTURE,
            )
            
            return False
    
    async def shutdown_all(self) -> Dict[str, bool]:
        """
        Корректное завершение работы всех провайдеров.
        
        RETURNS:
        - Dict[str, bool]: результаты shutdown по каждому провайдеру
        """
        self._shutdown_in_progress = True
        results = {}
        
        self._self.event_bus_logger.info("Начало завершения работы провайдеров")
        
        # Shutdown в обратном порядке инициализации
        # Инициализация: DATABASE -> CACHE -> VECTOR -> EMBEDDING -> LLM -> STORAGE -> OTHER
        # Shutdown: OTHER -> STORAGE -> LLM -> EMBEDDING -> VECTOR -> CACHE -> DATABASE
        shutdown_order = list(reversed([
            ProviderType.DATABASE,
            ProviderType.CACHE,
            ProviderType.VECTOR,
            ProviderType.EMBEDDING,
            ProviderType.LLM,
            ProviderType.STORAGE,
            ProviderType.OTHER,
        ]))
        
        for provider_type in shutdown_order:
            provider_names = self._providers_by_type[provider_type]
            if not provider_names:
                continue
            
            for name in provider_names:
                if name not in self._providers:
                    continue
                    
                provider_info = self._providers[name]
                result = await self._shutdown_provider(provider_info)
                results[name] = result
        
        self._initialized = False
        self._shutdown_in_progress = False
        
        self._self.event_bus_logger.info(f"Завершение работы провайдеров: {sum(results.values())}/{len(results)} успешно")
        
        # Событие shutdown
        await self._event_bus.publish(
            EventType.SYSTEM_SHUTDOWN,
            data={
                "component": "ProviderLifecycleManager",
                "providers_count": len(results),
                "success_count": sum(results.values()),
            },
            domain=EventDomain.INFRASTRUCTURE,
        )
        
        return results
    
    async def _shutdown_provider(self, provider_info: ProviderInfo) -> bool:
        """
        Завершение работы одного провайдера.
        
        ARGS:
        - provider_info: информация о провайдере
        
        RETURNS:
        - bool: True если shutdown успешен
        """
        name = provider_info.name
        provider = provider_info.provider
        
        if not provider_info.initialized:
            self._self.event_bus_logger.debug(f"Провайдер '{name}' не инициализирован, пропускаем shutdown")
            return True
        
        try:
            self._self.event_bus_logger.debug(f"Завершение работы провайдера '{name}'")
            
            await provider.shutdown()
            
            provider_info.initialized = False
            provider_info.health_status = ProviderHealthStatus.UNKNOWN
            self._self.event_bus_logger.info(f"Провайдер '{name}' корректно завершен")
            
            return True
            
        except Exception as e:
            self._self.event_bus_logger.error(f"Ошибка при завершении провайдера '{name}': {e}", exc_info=True)
            return False
    
    async def health_check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Проверка здоровья всех провайдеров.
        
        RETURNS:
        - Dict[str, HealthCheckResult]: результаты проверки по каждому провайдеру
        """
        results = {}
        
        for name, provider_info in self._providers.items():
            result = await self._health_check_provider(provider_info)
            results[name] = result
        
        return results
    
    async def _health_check_provider(self, provider_info: ProviderInfo) -> HealthCheckResult:
        """
        Проверка здоровья одного провайдера.
        
        ARGS:
        - provider_info: информация о провайдере
        
        RETURNS:
        - HealthCheckResult: результат проверки
        """
        name = provider_info.name
        provider = provider_info.provider
        
        try:
            health_data = await provider.health_check()
            
            status = health_data.get("status", ProviderHealthStatus.UNKNOWN)
            is_healthy = status == ProviderHealthStatus.HEALTHY
            
            provider_info.health_status = status
            provider_info.last_health_check = datetime.now()
            
            return HealthCheckResult(
                provider_name=name,
                status=status,
                is_healthy=is_healthy,
                details=health_data,
            )
            
        except Exception as e:
            provider_info.health_status = ProviderHealthStatus.UNHEALTHY
            self._self.event_bus_logger.error(f"Health check провайдера '{name}' не удался: {e}")
            
            return HealthCheckResult(
                provider_name=name,
                status=ProviderHealthStatus.UNHEALTHY,
                is_healthy=False,
                details={"error": str(e)},
            )
    
    def get_provider(self, name: str) -> Optional[IProvider]:
        """
        Получение провайдера по имени.
        
        ARGS:
        - name: имя провайдера
        
        RETURNS:
        - IProvider или None если не найден
        """
        provider_info = self._providers.get(name)
        return provider_info.provider if provider_info else None
    
    def get_provider_info(self, name: str) -> Optional[ProviderInfo]:
        """
        Получение информации о провайдере.
        
        ARGS:
        - name: имя провайдера
        
        RETURNS:
        - ProviderInfo или None если не найден
        """
        return self._providers.get(name)
    
    def get_providers_by_type(self, provider_type: ProviderType) -> List[IProvider]:
        """
        Получение всех провайдеров определенного типа.
        
        ARGS:
        - provider_type: тип провайдеров
        
        RETURNS:
        - List[IProvider]: список провайдеров
        """
        names = self._providers_by_type.get(provider_type, [])
        return [
            self._providers[name].provider
            for name in names
            if name in self._providers
        ]
    
    def get_all_stats(self) -> Dict[str, any]:
        """
        Получение статистики по всем провайдерам.
        
        RETURNS:
        - Dict[str, Any]: статистика
        """
        health_results = {}
        for name, provider_info in self._providers.items():
            health_results[name] = {
                "type": provider_info.provider_type.value,
                "initialized": provider_info.initialized,
                "health_status": provider_info.health_status,
                "uptime": time.time() - provider_info.registered_at.timestamp(),
            }
        
        return {
            "total_providers": len(self._providers),
            "initialized_count": sum(1 for p in self._providers.values() if p.initialized),
            "healthy_count": sum(1 for p in self._providers.values() if p.health_status == ProviderHealthStatus.HEALTHY),
            "degraded_count": sum(1 for p in self._providers.values() if p.health_status == ProviderHealthStatus.DEGRADED),
            "unhealthy_count": sum(1 for p in self._providers.values() if p.health_status == ProviderHealthStatus.UNHEALTHY),
            "providers": health_results,
        }
    
    @property
    def providers_count(self) -> int:
        """Количество зарегистрированных провайдеров."""
        return len(self._providers)
    
    @property
    def initialized_count(self) -> int:
        """Количество инициализированных провайдеров."""
        return sum(1 for p in self._providers.values() if p.initialized)
    
    @property
    def is_initialized(self) -> bool:
        """Статус инициализации менеджера."""
        return self._initialized


# Глобальный менеджер lifecycle (singleton)
_global_lifecycle_manager: Optional[ProviderLifecycleManager] = None


def get_lifecycle_manager() -> ProviderLifecycleManager:
    """
    Получение глобального менеджера lifecycle.
    
    RETURNS:
    - ProviderLifecycleManager: глобальный экземпляр
    """
    global _global_lifecycle_manager
    if _global_lifecycle_manager is None:
        _global_lifecycle_manager = ProviderLifecycleManager()
    return _global_lifecycle_manager


def reset_lifecycle_manager():
    """Сброс глобального менеджера (для тестов)."""
    global _global_lifecycle_manager
    _global_lifecycle_manager = None
