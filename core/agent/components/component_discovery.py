"""
Динамическое обнаружение компонентов: сканирование файловой системы
для автоматической регистрации навыков, инструментов, сервисов и поведений.

АРХИТЕКТУРА:
- ComponentDiscovery сканирует директории и возвращает маппинг {type: {name: class}}
- ComponentFactory использует discovery вместо хардкода
- Поддержка hot-reload: повторный scan обновляет кэш

СТРУКТУРА ОБНАРУЖЕНИЯ:
- Skills: core/components/skills/{name}/skill.py -> {Name}Skill(Skill)
- Tools: core/components/tools/{name}_tool.py -> {Name}Tool(Tool)
- Services (dir): core/components/services/{name}/service.py -> {Name}Service(Service)
- Services (file): core/components/services/{name}.py -> {Name}Service(Service)
- Behaviors: core/agent/behaviors/{name}/pattern.py -> {Name}Pattern(Component)
"""
import importlib
import sys
from pathlib import Path
from typing import Dict, Type, Any, Optional, Set
from dataclasses import dataclass, field

from core.agent.components.component import Component


BASE_CLASS_NAMES: Set[str] = {
    "Component",
    "Skill",
    "Tool",
    "Service",
    "BaseBehaviorPattern",
}


@dataclass
class ComponentEntry:
    """Запись обнаруженного компонента."""
    component_type: str
    name: str
    module_name: str
    class_name: str
    class_ref: Type[Component]
    file_path: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_type": self.component_type,
            "name": self.name,
            "module_name": self.module_name,
            "class_name": self.class_name,
            "file_path": self.file_path,
        }


class ComponentDiscovery:
    """Сканер файловой системы для автоматического обнаружения компонентов."""

    # Глобальный кэш на уровне класса (не экземпляра!)
    _global_cache: Dict[str, Dict[str, ComponentEntry]] = {}
    _global_scanned: bool = False
    _global_logger: Optional[Any] = None

    def __init__(
        self,
        project_root: Optional[Path] = None,
        logger: Optional[Any] = None,
    ):
        if project_root is None:
            project_root = Path(__file__).resolve().parents[3]
        self._project_root = project_root
        self._logger = logger
        # Обновляем глобальный logger если передан
        if logger is not None:
            ComponentDiscovery._global_logger = logger

    def scan(self, force: bool = False) -> Dict[str, Dict[str, ComponentEntry]]:
        """
        Сканирование всех директорий компонентов.

        ARGS:
        - force: принудительное повторное сканирование

        RETURNS:
        - dict {component_type: {name: ComponentEntry}}
        """
        if ComponentDiscovery._global_scanned and not force and ComponentDiscovery._global_cache:
            return ComponentDiscovery._global_cache

        self._log("info", f"Начало сканирования компонентов (root={self._project_root})")

        total_start = __import__("time").time()
        result: Dict[str, Dict[str, ComponentEntry]] = {
            "skill": {},
            "tool": {},
            "service": {},
            "behavior": {},
        }

        for component_type, discover_fn in [
            ("skill", self._discover_skills),
            ("tool", self._discover_tools),
            ("service", self._discover_services),
            ("behavior", self._discover_behaviors),
        ]:
            start = __import__("time").time()
            entries = discover_fn()
            elapsed_ms = (__import__("time").time() - start) * 1000
            result[component_type] = entries
            names = list(entries.keys())
            self._log(
                "info",
                f"  {component_type}: найдено {len(entries)} — {', '.join(names) if names else 'нет'} "
                f"({elapsed_ms:.0f}ms)"
            )

        total_ms = (__import__("time").time() - total_start) * 1000
        total_count = sum(len(v) for v in result.values())
        self._log(
            "info",
            f"Сканирование завершено: всего {total_count} компонентов за {total_ms:.0f}ms"
        )

        ComponentDiscovery._global_cache = result
        ComponentDiscovery._global_scanned = True

        return result

    def find_component(
        self, component_type: str, name: str
    ) -> Optional[ComponentEntry]:
        """Поиск конкретного компонента по типу и имени."""
        if not ComponentDiscovery._global_scanned:
            self.scan()

        type_registry = ComponentDiscovery._global_cache.get(component_type, {})
        return type_registry.get(name)

    def get_names(self, component_type: str) -> list:
        """Список имён компонентов данного типа."""
        if not ComponentDiscovery._global_scanned:
            self.scan()
        return list(ComponentDiscovery._global_cache.get(component_type, {}).keys())

    def get_all_names(self) -> Dict[str, list]:
        """Список имён всех компонентов по типам."""
        if not ComponentDiscovery._global_scanned:
            self.scan()
        return {t: list(names.keys()) for t, names in ComponentDiscovery._global_cache.items()}

    def _discover_skills(self) -> Dict[str, ComponentEntry]:
        """Обнаружение навыков в core/components/skills/{name}/skill.py."""
        skills_dir = self._project_root / "core" / "components" / "skills"
        if not skills_dir.is_dir():
            self._log("warning", f"Директория навыков не найдена: {skills_dir}")
            return {}

        entries: Dict[str, ComponentEntry] = {}
        skipped: list = []

        for item in sorted(skills_dir.iterdir()):
            if not item.is_dir() or item.name.startswith("_"):
                skipped.append(f"{item.name} (не директория)")
                continue

            skill_file = item / "skill.py"
            if not skill_file.is_file():
                skipped.append(f"{item.name} (нет skill.py)")
                continue

            module_name = f"core.components.skills.{item.name}.skill"
            cls = self._load_class_from_module(
                module_name, item.name, "Skill"
            )
            if cls is None:
                skipped.append(f"{item.name} (класс не найден)")
                continue

            entry = ComponentEntry(
                component_type="skill",
                name=item.name,
                module_name=module_name,
                class_name=cls.__name__,
                class_ref=cls,
                file_path=str(skill_file),
            )
            entries[item.name] = entry
            self._log("debug", f"  skill: {item.name} -> {cls.__name__}")

        if skipped:
            self._log("debug", f"  skill: пропущено {len(skipped)} — {', '.join(skipped)}")

        return entries

    def _discover_tools(self) -> Dict[str, ComponentEntry]:
        """Обнаружение инструментов в core/components/tools/{name}_tool.py."""
        tools_dir = self._project_root / "core" / "components" / "tools"
        if not tools_dir.is_dir():
            self._log("warning", f"Директория инструментов не найдена: {tools_dir}")
            return {}

        entries: Dict[str, ComponentEntry] = {}
        skipped: list = []

        for item in sorted(tools_dir.iterdir()):
            if not item.is_file() or not item.name.endswith("_tool.py"):
                skipped.append(f"{item.name} (не *_tool.py)")
                continue

            name = item.name[: -len(".py")]
            module_name = f"core.components.tools.{name}"
            cls = self._load_class_from_module(module_name, name, "")
            if cls is None:
                skipped.append(f"{name} (класс не найден)")
                continue

            entry = ComponentEntry(
                component_type="tool",
                name=name,
                module_name=module_name,
                class_name=cls.__name__,
                class_ref=cls,
                file_path=str(item),
            )
            entries[name] = entry
            self._log("debug", f"  tool: {name} -> {cls.__name__}")

        if skipped:
            self._log("warning", f"  tool: пропущено {len(skipped)}: {', '.join(skipped)}")

        return entries

    def _discover_services(self) -> Dict[str, ComponentEntry]:
        """Обнаружение сервисов (dir-based и file-based)."""
        services_dir = self._project_root / "core" / "components" / "services"
        if not services_dir.is_dir():
            self._log("warning", f"Директория сервисов не найдена: {services_dir}")
            return {}

        entries: Dict[str, ComponentEntry] = {}
        skipped: list = []

        for item in sorted(services_dir.iterdir()):
            if item.name.startswith("_"):
                skipped.append(f"{item.name} (приватный)")
                continue

            if item.is_dir():
                entry = self._try_load_dir_service(item)
                if entry:
                    entries[entry.name] = entry
                else:
                    skipped.append(f"{item.name} (нет service.py или класс не найден)")

            elif item.is_file() and item.name.endswith("_service.py"):
                entry = self._try_load_file_service(item)
                if entry:
                    entries[entry.name] = entry
                else:
                    name = item.name[: -len("_service.py")]
                    skipped.append(f"{name} (класс не найден)")

        if skipped:
            self._log("debug", f"  service: пропущено {len(skipped)} — {', '.join(skipped)}")

        return entries

    def _try_load_dir_service(self, item: Path) -> Optional[ComponentEntry]:
        """Попытка загрузить сервис из директории {name}/service.py."""
        service_file = item / "service.py"
        if not service_file.is_file():
            return None

        name = item.name
        module_name = f"core.components.services.{name}.service"
        cls = self._load_class_from_module(
            module_name, name, "Service"
        )
        if cls is None:
            return None

        return ComponentEntry(
            component_type="service",
            name=name,
            module_name=module_name,
            class_name=cls.__name__,
            class_ref=cls,
            file_path=str(service_file),
        )

    def _try_load_file_service(self, item: Path) -> Optional[ComponentEntry]:
        """Попытка загрузить сервис из файла {name}_service.py."""
        name = item.name[: -len("_service.py")]
        module_name = f"core.components.services.{item.name[:-3]}"
        cls = self._load_class_from_module(
            module_name, name, "Service"
        )
        if cls is None:
            return None

        return ComponentEntry(
            component_type="service",
            name=name,
            module_name=module_name,
            class_name=cls.__name__,
            class_ref=cls,
            file_path=str(item),
        )

    def _discover_behaviors(self) -> Dict[str, ComponentEntry]:
        """Обнаружение поведений в core/agent/behaviors/{name}/pattern.py."""
        behaviors_dir = self._project_root / "core" / "agent" / "behaviors"
        if not behaviors_dir.is_dir():
            self._log("warning", f"Директория поведений не найдена: {behaviors_dir}")
            return {}

        entries: Dict[str, ComponentEntry] = {}
        skipped: list = []

        for item in sorted(behaviors_dir.iterdir()):
            if not item.is_dir() or item.name.startswith("_"):
                skipped.append(f"{item.name} (не директория)")
                continue

            pattern_file = item / "pattern.py"
            if not pattern_file.is_file():
                skipped.append(f"{item.name} (нет pattern.py)")
                continue

            name = item.name
            module_name = f"core.agent.behaviors.{name}.pattern"
            cls = self._load_class_from_module(
                module_name, name, "Pattern"
            )
            if cls is None:
                skipped.append(f"{name} (класс не найден)")
                continue

            entry = ComponentEntry(
                component_type="behavior",
                name=name,
                module_name=module_name,
                class_name=cls.__name__,
                class_ref=cls,
                file_path=str(pattern_file),
            )
            entries[name] = entry
            self._log("debug", f"  behavior: {name} -> {cls.__name__}")

        if skipped:
            self._log("debug", f"  behavior: пропущено {len(skipped)} — {', '.join(skipped)}")

        return entries

    def _load_class_from_module(
        self,
        module_name: str,
        name: str,
        suffix: str,
    ) -> Optional[Type[Component]]:
        """
        Загрузка класса компонента из модуля.

        Стратегия приоритетов:
        1. Точное имя: {PascalCaseName}{Suffix} (не базовый класс)
        2. Первый конкретный класс, наследующий Component
        """
        try:
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._log("warning", f"  Не удалось импортировать {module_name}: {e}")
            self._log_error(f"Не удалось загрузить компонент {module_name}: {e}", tb)
            return None

        pascal_name = "".join(part.title() for part in name.split("_")).replace("_", "")
        expected_class = f"{pascal_name}{suffix}"

        if hasattr(module, expected_class):
            cls = getattr(module, expected_class)
            if self._is_concrete_component(cls):
                return cls

        best_match = None
        best_score = -1

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            if attr_name in BASE_CLASS_NAMES:
                continue
            attr = getattr(module, attr_name)
            if not self._is_concrete_component(attr):
                continue

            score = self._score_class(attr, expected_class)
            if score > best_score:
                best_score = score
                best_match = attr

        if best_match is None:
            self._log("warning", f"  В модуле {module_name} не найден конкретный компонент")

        return best_match

    def _score_class(self, cls: Type, expected: str) -> int:
        """Оценка релевантности класса: чем выше, тем лучше."""
        score = 0
        name = cls.__name__

        # Case-insensitive exact match
        if name.lower() == expected.lower():
            score += 100

        # Check if the class name ends with the expected suffix (case-insensitive)
        expected_suffix = expected.split("_")[-1] if "_" in expected else expected
        if name.lower().endswith(expected_suffix.lower()):
            score += 50

        if expected.lower() in name.lower():
            score += 30

        if name.endswith(("Skill", "Tool", "Service", "Pattern")):
            score += 10

        return score

    def _is_concrete_component(self, cls: Any) -> bool:
        """Проверка, что класс — конкретный компонент (не базовый)."""
        try:
            if not isinstance(cls, type):
                return False
            if not issubclass(cls, Component):
                return False
            if cls is Component:
                return False
            if cls.__name__ in BASE_CLASS_NAMES:
                return False
            return True
        except TypeError:
            return False

    def _log(self, level: str, message: str) -> None:
        """Логирование через внешний logger или print."""
        if self._logger is not None:
            fn = getattr(self._logger, level, None)
            if fn:
                fn(message)
            else:
                fn = getattr(self._logger, "info", None)
                if fn:
                    fn(f"[{level.upper()}] {message}")

    def _log_error(self, message: str, exc_info: str = None) -> None:
        """Логирование ошибки с traceback."""
        if self._logger is not None:
            fn = getattr(self._logger, "error", None)
            if fn:
                full_msg = f"Ошибка загрузки компонента: {message}"
                if exc_info:
                    full_msg += f"\n{exc_info}"
                fn(full_msg)
