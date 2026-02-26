"""
Динамическое обнаружение компонентов (Component Discovery).

АРХИТЕКТУРА:
- Сканирование директорий с манифестами
- Автоматическое обнаружение компонентов
- Загрузка компонентов по ID
- Кэширование обнаруженных компонентов
- Интеграция с registry.yaml

ПРЕИМУЩЕСТВА:
- ✅ Автоматическое обнаружение новых компонентов
- ✅ Поддержка плагинов/расширений
- ✅ Динамическая загрузка без перезапуска
- ✅ Валидация манифестов
"""
import asyncio
import logging
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
from enum import Enum

from core.models.enums.common_enums import ComponentType


logger = logging.getLogger(__name__)


class ComponentStatus(Enum):
    """Статус компонента."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


@dataclass
class ComponentInfo:
    """
    Информация о компоненте из манифеста.
    
    ATTRIBUTES:
    - id: уникальный идентификатор компонента
    - name: отображаемое имя
    - component_type: тип компонента
    - version: версия компонента
    - manifest_path: путь к манифесту
    - status: статус компонента
    - dependencies: зависимости
    - capabilities: предоставляемые возможности
    - metadata: дополнительные метаданные
    - discovered_at: время обнаружения
    """
    id: str
    name: str
    component_type: ComponentType
    version: str = "1.0.0"
    manifest_path: Optional[Path] = None
    status: ComponentStatus = ComponentStatus.ACTIVE
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.now)
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "id": self.id,
            "name": self.name,
            "component_type": self.component_type.value,
            "version": self.version,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "discovered_at": self.discovered_at.isoformat(),
            "config": self.config,
        }
    
    @classmethod
    def from_manifest(cls, manifest_path: Path, manifest_data: Dict) -> 'ComponentInfo':
        """
        Создание ComponentInfo из манифеста.
        
        ARGS:
        - manifest_path: путь к файлу манифеста
        - manifest_data: данные манифеста
        
        RETURNS:
        - ComponentInfo: информация о компоненте
        """
        component_id = manifest_data.get("component", {}).get("id", manifest_path.stem)
        component_name = manifest_data.get("component", {}).get("name", component_id)
        component_type_str = manifest_data.get("component", {}).get("type", "skill")
        version = manifest_data.get("component", {}).get("version", "1.0.0")
        status_str = manifest_data.get("component", {}).get("status", "active")
        
        try:
            component_type = ComponentType(component_type_str)
        except ValueError:
            component_type = ComponentType.SKILL
            logger.warning(f"Неизвестный тип компонента '{component_type_str}', используем SKILL")
        
        try:
            status = ComponentStatus(status_str)
        except ValueError:
            status = ComponentStatus.ACTIVE
        
        dependencies = []
        for dep_section in ["dependencies", "requires"]:
            deps = manifest_data.get(dep_section, [])
            if isinstance(deps, list):
                dependencies.extend(deps)
            elif isinstance(deps, dict):
                dependencies.extend(deps.keys())
        
        capabilities = []
        for cap_section in ["capabilities", "provides"]:
            caps = manifest_data.get(cap_section, [])
            if isinstance(caps, list):
                capabilities.extend(caps)
            elif isinstance(caps, dict):
                capabilities.extend(caps.keys())
        
        return cls(
            id=component_id,
            name=component_name,
            component_type=component_type,
            version=version,
            manifest_path=manifest_path,
            status=status,
            dependencies=dependencies,
            capabilities=capabilities,
            metadata=manifest_data.get("metadata", {}),
            config=manifest_data.get("config", {}),
        )


class ComponentDiscovery:
    """
    Динамическое обнаружение компонентов.
    
    FEATURES:
    - Сканирование директорий с манифестами
    - Автоматическое обнаружение новых компонентов
    - Загрузка компонентов по ID
    - Кэширование обнаруженных компонентов
    - Валидация зависимостей
    - Фильтрация по типу и статусу
    
    USAGE:
    ```python
    # Создание обнаружителя
    discovery = ComponentDiscovery(
        search_paths=[Path("data/manifests")]
    )
    
    # Обнаружение всех компонентов
    components = await discovery.discover()
    
    # Получение компонента по ID
    component_info = discovery.get_component("planning")
    
    # Загрузка компонента
    component = await discovery.load_component("planning", application_context)
    
    # Фильтрация по типу
    skills = discovery.get_by_type(ComponentType.SKILL)
    ```
    """
    
    def __init__(
        self,
        search_paths: Optional[List[Path]] = None,
        manifest_filename: str = "manifest.yaml",
    ):
        """
        Инициализация обнаружителя компонентов.
        
        ARGS:
        - search_paths: пути для поиска манифестов
        - manifest_filename: имя файла манифеста
        """
        self._search_paths = search_paths or [Path("data/manifests")]
        self._manifest_filename = manifest_filename
        
        self._components: Dict[str, ComponentInfo] = {}
        self._components_by_type: Dict[ComponentType, List[str]] = {
            ct: [] for ct in ComponentType
        }
        self._component_classes: Dict[str, Type] = {}
        
        self._logger = logging.getLogger(f"{__name__}.ComponentDiscovery")
        self._logger.info(f"ComponentDiscovery создан (search_paths={self._search_paths})")
    
    async def discover(self) -> Dict[str, ComponentInfo]:
        """
        Обнаружение всех доступных компонентов.
        
        RETURNS:
        - Dict[str, ComponentInfo]: обнаруженные компоненты
        """
        self._logger.info("Начало обнаружения компонентов")
        
        for search_path in self._search_paths:
            if not search_path.exists():
                self._logger.warning(f"Путь не найден: {search_path}")
                continue
            
            await self._scan_directory(search_path)
        
        self._logger.info(f"Обнаружено {len(self._components)} компонентов")
        return self._components.copy()
    
    async def _scan_directory(self, path: Path):
        """
        Сканирование директории на наличие манифестов.
        
        ARGS:
        - path: директория для сканирования
        """
        self._logger.debug(f"Сканирование директории: {path}")
        
        # Поиск всех manifest.yaml файлов
        for manifest_file in path.rglob(self._manifest_filename):
            try:
                component_info = await self._load_manifest(manifest_file)
                if component_info:
                    self._register_component(component_info)
            except Exception as e:
                self._logger.error(f"Ошибка загрузки манифеста {manifest_file}: {e}")
    
    async def _load_manifest(self, manifest_path: Path) -> Optional[ComponentInfo]:
        """
        Загрузка манифеста компонента.
        
        ARGS:
        - manifest_path: путь к манифесту
        
        RETURNS:
        - ComponentInfo или None
        """
        if not manifest_path.exists():
            return None
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = yaml.safe_load(f)
        
        if not manifest_data:
            self._logger.warning(f"Пустой манифест: {manifest_path}")
            return None
        
        component_info = ComponentInfo.from_manifest(manifest_path, manifest_data)
        
        self._logger.debug(
            f"Загружен компонент: {component_info.id} "
            f"(type={component_info.component_type.value}, status={component_info.status.value})"
        )
        
        return component_info
    
    def _register_component(self, component_info: ComponentInfo):
        """
        Регистрация обнаруженного компонента.
        
        ARGS:
        - component_info: информация о компоненте
        """
        component_id = component_info.id
        
        if component_id in self._components:
            self._logger.warning(f"Компонент '{component_id}' уже зарегистрирован, пропускаем")
            return
        
        self._components[component_id] = component_info
        
        component_type = component_info.component_type
        if component_type in self._components_by_type:
            self._components_by_type[component_type].append(component_id)
        
        self._logger.debug(f"Зарегистрирован компонент: {component_id}")
    
    def register_component_class(self, component_id: str, component_class: Type):
        """
        Регистрация класса компонента для динамической загрузки.
        
        ARGS:
        - component_id: идентификатор компонента
        - component_class: класс компонента
        """
        self._component_classes[component_id] = component_class
        self._logger.debug(f"Зарегистрирован класс для компонента: {component_id}")
    
    def get_component(self, component_id: str) -> Optional[ComponentInfo]:
        """
        Получение информации о компоненте по ID.
        
        ARGS:
        - component_id: идентификатор компонента
        
        RETURNS:
        - ComponentInfo или None
        """
        return self._components.get(component_id)
    
    def get_all_components(self) -> Dict[str, ComponentInfo]:
        """Получение всех обнаруженных компонентов."""
        return self._components.copy()
    
    def get_by_type(self, component_type: ComponentType) -> List[ComponentInfo]:
        """
        Получение компонентов по типу.
        
        ARGS:
        - component_type: тип компонентов
        
        RETURNS:
        - List[ComponentInfo]: список компонентов
        """
        component_ids = self._components_by_type.get(component_type, [])
        return [
            self._components[component_id]
            for component_id in component_ids
            if component_id in self._components
        ]
    
    def get_by_status(self, status: ComponentStatus) -> List[ComponentInfo]:
        """
        Получение компонентов по статусу.
        
        ARGS:
        - status: статус компонентов
        
        RETURNS:
        - List[ComponentInfo]: список компонентов
        """
        return [
            component
            for component in self._components.values()
            if component.status == status
        ]
    
    def has_component(self, component_id: str) -> bool:
        """Проверка наличия компонента."""
        return component_id in self._components
    
    def has_component_class(self, component_id: str) -> bool:
        """Проверка наличия зарегистрированного класса."""
        return component_id in self._component_classes
    
    async def load_component(self, component_id: str, application_context: Any = None):
        """
        Загрузка экземпляра компонента.
        
        ARGS:
        - component_id: идентификатор компонента
        - application_context: контекст приложения
        
        RETURNS:
        - Экземпляр компонента или None
        
        RAISES:
        - ComponentNotFoundError: если компонент не найден
        - ComponentLoadError: если ошибка загрузки
        """
        component_info = self.get_component(component_id)
        if not component_info:
            raise ComponentNotFoundError(component_id)
        
        # Проверка наличия зарегистрированного класса
        if component_id not in self._component_classes:
            self._logger.warning(
                f"Класс для компонента '{component_id}' не зарегистрирован. "
                f"Используйте register_component_class() для регистрации."
            )
            return None
        
        component_class = self._component_classes[component_id]
        
        try:
            # Создание экземпляра компонента
            if application_context:
                component = component_class(
                    name=component_info.id,
                    application_context=application_context,
                    component_config=None,  # Будет создана из config
                    executor=None,  # Будет injected
                )
            else:
                component = component_class()
            
            self._logger.info(f"Компонент '{component_id}' загружен")
            return component
            
        except Exception as e:
            raise ComponentLoadError(component_id, str(e))
    
    def validate_dependencies(self, component_id: str) -> List[str]:
        """
        Валидация зависимостей компонента.
        
        ARGS:
        - component_id: идентификатор компонента
        
        RETURNS:
        - List[str]: список отсутствующих зависимостей
        """
        component_info = self.get_component(component_id)
        if not component_info:
            return []
        
        missing = []
        for dependency in component_info.dependencies:
            if not self.has_component(dependency):
                missing.append(dependency)
        
        if missing:
            self._logger.warning(
                f"Компонент '{component_id}' имеет отсутствующие зависимости: {missing}"
            )
        
        return missing
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """Получение статистики обнаружения."""
        by_type = {
            ct.value: len(self._components_by_type.get(ct, []))
            for ct in ComponentType
        }
        
        by_status = {}
        for status in ComponentStatus:
            count = len([
                c for c in self._components.values()
                if c.status == status
            ])
            if count > 0:
                by_status[status.value] = count
        
        return {
            "total_components": len(self._components),
            "by_type": by_type,
            "by_status": by_status,
            "registered_classes": len(self._component_classes),
            "search_paths": [str(p) for p in self._search_paths],
        }
    
    async def refresh(self):
        """Пересканирование и обновление списка компонентов."""
        self._logger.info("Обновление списка компонентов")
        
        # Очистка кэша
        self._components.clear()
        for ct in self._components_by_type:
            self._components_by_type[ct] = []
        
        # Повторное обнаружение
        await self.discover()


class ComponentNotFoundError(Exception):
    """Компонент не найден."""
    def __init__(self, component_id: str):
        self.component_id = component_id
        super().__init__(f"Component '{component_id}' not found")


class ComponentLoadError(Exception):
    """Ошибка загрузки компонента."""
    def __init__(self, component_id: str, message: str):
        self.component_id = component_id
        self.message = message
        super().__init__(f"Failed to load component '{component_id}': {message}")


# Глобальный обнаружитель компонентов (singleton)
_global_component_discovery: Optional[ComponentDiscovery] = None


def get_component_discovery() -> ComponentDiscovery:
    """
    Получение глобального обнаружителя компонентов.
    
    RETURNS:
    - ComponentDiscovery: глобальный экземпляр
    """
    global _global_component_discovery
    if _global_component_discovery is None:
        _global_component_discovery = ComponentDiscovery()
    return _global_component_discovery


def create_component_discovery(
    search_paths: List[Path] = None,
    **kwargs
) -> ComponentDiscovery:
    """
    Создание глобального обнаружителя компонентов.
    
    ARGS:
    - search_paths: пути для поиска
    - **kwargs: дополнительные параметры
    
    RETURNS:
    - ComponentDiscovery: созданный экземпляр
    """
    global _global_component_discovery
    _global_component_discovery = ComponentDiscovery(
        search_paths=search_paths,
        **kwargs
    )
    return _global_component_discovery


def reset_component_discovery():
    """Сброс глобального обнаружителя (для тестов)."""
    global _global_component_discovery
    _global_component_discovery = None
