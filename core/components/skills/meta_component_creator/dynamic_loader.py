"""
Динамический загрузчик компонентов: запись файлов на диск и регистрация в рантайме.

АРХИТЕКТУРА:
- Записывает артефакты в правильные директории в зависимости от типа
- Регистрация в ApplicationContext — отдельный шаг, требует подтверждения человека
- Поддержка hot-reload через importlib.reload
"""
import importlib
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.application_context.application_context import ApplicationContext


PROJECT_ROOT = Path(__file__).resolve().parents[4]

TYPE_DIRECTORIES = {
    "skill": {
        "python": PROJECT_ROOT / "core" / "components" / "skills",
        "prompts": PROJECT_ROOT / "data" / "prompts" / "skill",
        "contracts": PROJECT_ROOT / "data" / "contracts" / "skill",
        "main_file": "skill.py",
        "module_template": "core.components.skills.{name}.skill",
    },
    "tool": {
        "python": PROJECT_ROOT / "core" / "components" / "tools",
        "prompts": None,
        "contracts": PROJECT_ROOT / "data" / "contracts" / "tool",
        "main_file": None,
        "module_template": "core.components.tools.{name}",
    },
    "service": {
        "python": PROJECT_ROOT / "core" / "components" / "services",
        "prompts": PROJECT_ROOT / "data" / "prompts" / "service",
        "contracts": PROJECT_ROOT / "data" / "contracts" / "service",
        "main_file": "service.py",
        "module_template": "core.components.services.{name}.service",
    },
    "behavior": {
        "python": PROJECT_ROOT / "core" / "agent" / "behaviors",
        "prompts": PROJECT_ROOT / "data" / "prompts" / "behavior",
        "contracts": PROJECT_ROOT / "data" / "contracts" / "behavior",
        "main_file": "pattern.py",
        "module_template": "core.agent.behaviors.{name}.pattern",
    },
}

TYPE_REGISTRY_MAP = {
    "skill": "SKILL",
    "tool": "TOOL",
    "service": "SERVICE",
    "behavior": "BEHAVIOR",
}


class DeploymentManifest:
    """Манифест развёртывания компонента."""

    def __init__(
        self,
        component_name: str,
        component_type: str,
        class_name: str,
        python_files: Dict[str, str],
        yaml_files: Dict[str, str],
    ):
        self.component_name = component_name
        self.component_type = component_type
        self.class_name = class_name
        self.python_files = python_files
        self.yaml_files = yaml_files
        self.written_files: List[str] = []
        dir_info = TYPE_DIRECTORIES.get(component_type, TYPE_DIRECTORIES["skill"])
        self.module_name = dir_info["module_template"].format(name=component_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_name": self.component_name,
            "component_type": self.component_type,
            "class_name": self.class_name,
            "module_name": self.module_name,
            "written_files": self.written_files,
        }


class DynamicComponentLoader:
    """Запись артефактов на диск и регистрация компонента в рантайме."""

    def __init__(self, application_context: Optional[ApplicationContext] = None):
        self.application_context = application_context

    def write_artifacts(self, manifest: DeploymentManifest) -> Dict[str, Any]:
        """
        Запись всех артефактов на диск.

        ARGS:
        - manifest: манифест развёртывания

        RETURNS:
        - dict с полями: success, written_files, errors
        """
        errors: List[str] = []
        written: List[str] = []

        try:
            written.extend(self._write_python_files(manifest))
            written.extend(self._write_yaml_files(manifest))
        except Exception as e:
            errors.append(f"Ошибка записи файлов: {e}")

        manifest.written_files = written

        return {
            "success": len(errors) == 0,
            "written_files": written,
            "errors": errors,
        }

    def _write_python_files(self, manifest: DeploymentManifest) -> List[str]:
        """Запись Python-файлов компонента."""
        written: List[str] = []
        dir_info = TYPE_DIRECTORIES.get(manifest.component_type, TYPE_DIRECTORIES["skill"])
        base_dir = dir_info["python"]

        if manifest.component_type == "tool":
            for filename, content in manifest.python_files.items():
                target = base_dir / filename
                target.write_text(content, encoding="utf-8")
                written.append(str(target))
        elif manifest.component_type == "service":
            if "service.py" in manifest.python_files:
                target_dir = base_dir / manifest.component_name
                target_dir.mkdir(parents=True, exist_ok=True)
                for filename, content in manifest.python_files.items():
                    target = target_dir / filename
                    target.write_text(content, encoding="utf-8")
                    written.append(str(target))
            else:
                for filename, content in manifest.python_files.items():
                    target = base_dir / filename
                    target.write_text(content, encoding="utf-8")
                    written.append(str(target))
        else:
            target_dir = base_dir / manifest.component_name
            target_dir.mkdir(parents=True, exist_ok=True)
            for filename, content in manifest.python_files.items():
                target = target_dir / filename
                target.write_text(content, encoding="utf-8")
                written.append(str(target))

        return written

    def _write_yaml_files(self, manifest: DeploymentManifest) -> List[str]:
        """Запись YAML-файлов (промпты и контракты)."""
        written: List[str] = []
        dir_info = TYPE_DIRECTORIES.get(manifest.component_type, TYPE_DIRECTORIES["skill"])
        name = manifest.component_name

        for filename, content in manifest.yaml_files.items():
            is_contract = (
                "contract" in filename.lower()
                or "_input_" in filename.lower()
                or "_output_" in filename.lower()
            )

            if is_contract:
                target_dir = dir_info["contracts"]
            else:
                target_dir = dir_info["prompts"]

            if target_dir is None:
                continue

            target_dir = target_dir / name
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / filename
            target.write_text(content, encoding="utf-8")
            written.append(str(target))

        return written

    async def register_component(self, manifest: DeploymentManifest) -> Dict[str, Any]:
        """
        Регистрация компонента в рантайме: hot-reload + обновление реестра.

        ТРЕБУЕТ: чтобы файлы уже были записаны через write_artifacts().
        ТРЕБУЕТ: подтверждения оператора.

        ARGS:
        - manifest: манифест развёртывания

        RETURNS:
        - dict с полями: success, component_id, errors
        """
        if not self.application_context:
            return {
                "success": False,
                "errors": ["ApplicationContext не доступен для регистрации"],
            }

        errors: List[str] = []

        try:
            module = self._hot_reload_module(manifest)
            component_class = self._resolve_component_class(module, manifest)
            component = await self._register_in_context(component_class, manifest)

            return {
                "success": True,
                "component_id": component.name if hasattr(component, "name") else manifest.component_name,
                "errors": [],
            }

        except ImportError as e:
            errors.append(f"Ошибка импорта модуля: {e}")
        except AttributeError as e:
            errors.append(f"Класс компонента не найден: {e}")
        except Exception as e:
            errors.append(f"Ошибка регистрации: {e}")

        return {"success": False, "errors": errors}

    def _hot_reload_module(self, manifest: DeploymentManifest):
        """Hot-reload модуля компонента."""
        module_name = manifest.module_name

        if module_name in sys.modules:
            module = importlib.reload(sys.modules[module_name])
        else:
            module = importlib.import_module(module_name)

        return module

    def _resolve_component_class(self, module, manifest: DeploymentManifest):
        """Поиск класса компонента в модуле."""
        candidates = [
            manifest.class_name,
        ]

        for class_name in candidates:
            if hasattr(module, class_name):
                return getattr(module, class_name)

        suffix = {"skill": "Skill", "tool": "Tool", "service": "Service", "behavior": "Pattern"}.get(
            manifest.component_type, "Component"
        )

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and attr_name.endswith(suffix):
                return attr

        raise AttributeError(
            f"Не удалось найти класс компонента в модуле {manifest.module_name}. "
            f"Ожидался: {manifest.class_name}"
        )

    async def _register_in_context(self, component_class, manifest: DeploymentManifest):
        """Регистрация компонента в ApplicationContext."""
        from core.agent.components.component_factory import ComponentFactory
        from core.config.component_config import ComponentConfig

        app_ctx = self.application_context
        infra = app_ctx.infrastructure_context

        factory = ComponentFactory(infra)

        component_config = ComponentConfig(
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            variant_id=f"{manifest.component_name}@dynamic",
        )

        component = await factory.create_and_initialize(
            component_class=component_class,
            name=manifest.component_name,
            application_context=app_ctx,
            component_config=component_config,
            executor=app_ctx.executor,
        )

        from core.application_context.application_context import ComponentType
        type_map = {
            "skill": ComponentType.SKILL,
            "tool": ComponentType.TOOL,
            "service": ComponentType.SERVICE,
            "behavior": ComponentType.BEHAVIOR,
        }
        comp_type = type_map.get(manifest.component_type, ComponentType.SKILL)
        app_ctx.components.register(comp_type, manifest.component_name, component)

        await component.initialize()

        return component


DynamicSkillLoader = DynamicComponentLoader
