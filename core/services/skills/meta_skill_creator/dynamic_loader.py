"""
Динамический загрузчик навыков: запись файлов на диск и регистрация в рантайме.

АРХИТЕКТУРА:
- DynamicSkillLoader записывает сгенерированные артефакты в файловую систему
- Регистрация в ApplicationContext — отдельный шаг, требует подтверждения человека
- Поддержка hot-reload через importlib.reload
"""
import importlib
import sys
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from core.application_context.application_context import ApplicationContext


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILLS_DIR = PROJECT_ROOT / "core" / "services" / "skills"
PROMPTS_DIR = PROJECT_ROOT / "data" / "prompts" / "skill"
CONTRACTS_DIR = PROJECT_ROOT / "data" / "contracts" / "skill"


class DeploymentManifest:
    """Манифест развёртывания навыка."""

    def __init__(
        self,
        skill_name: str,
        skill_class_name: str,
        python_files: Dict[str, str],
        yaml_files: Dict[str, str],
    ):
        self.skill_name = skill_name
        self.skill_class_name = skill_class_name
        self.python_files = python_files
        self.yaml_files = yaml_files
        self.written_files: List[str] = []
        self.module_name = f"core.services.skills.{skill_name}.skill"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "skill_class_name": self.skill_class_name,
            "module_name": self.module_name,
            "written_files": self.written_files,
        }


class DynamicSkillLoader:
    """Запись артефактов на диск и регистрация навыка в рантайме."""

    def __init__(self, application_context: Optional["ApplicationContext"] = None):
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
        """Запись Python-файлов навыка."""
        written: List[str] = []
        skill_dir = SKILLS_DIR / manifest.skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        for filename, content in manifest.python_files.items():
            target = skill_dir / filename
            target.write_text(content, encoding="utf-8")
            written.append(str(target))

        return written

    def _write_yaml_files(self, manifest: DeploymentManifest) -> List[str]:
        """Запись YAML-файлов (промпты и контракты)."""
        written: List[str] = []
        skill_name = manifest.skill_name

        for filename, content in manifest.yaml_files.items():
            is_contract = "contract" in filename.lower() or "_input_" in filename.lower() or "_output_" in filename.lower()

            if is_contract:
                target_dir = CONTRACTS_DIR / skill_name
            else:
                target_dir = PROMPTS_DIR / skill_name

            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / filename
            target.write_text(content, encoding="utf-8")
            written.append(str(target))

        return written

    async def register_skill(self, manifest: DeploymentManifest) -> Dict[str, Any]:
        """
        Регистрация навыка в рантайме: hot-reload + обновление реестра.

        ТРЕБУЕТ: чтобы файлы уже были записаны через write_artifacts().
        ТРЕБУЕТ: подтверждения оператора (вызывается только после одобрения).

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
            skill_class = self._resolve_skill_class(module, manifest)
            component = await self._register_in_context(skill_class, manifest)

            return {
                "success": True,
                "component_id": component.name if hasattr(component, "name") else manifest.skill_name,
                "errors": [],
            }

        except ImportError as e:
            errors.append(f"Ошибка импорта модуля: {e}")
        except AttributeError as e:
            errors.append(f"Класс навыка не найден: {e}")
        except Exception as e:
            errors.append(f"Ошибка регистрации: {e}")

        return {"success": False, "errors": errors}

    def _hot_reload_module(self, manifest: DeploymentManifest):
        """Hot-reload модуля навыка."""
        module_name = manifest.module_name

        if module_name in sys.modules:
            module = importlib.reload(sys.modules[module_name])
        else:
            module = importlib.import_module(module_name)

        return module

    def _resolve_skill_class(self, module, manifest: DeploymentManifest):
        """Поиск класса навыка в модуле."""
        candidates = [
            manifest.skill_class_name,
            f"{manifest.skill_name.title().replace('_', '')}Skill",
        ]

        for class_name in candidates:
            if hasattr(module, class_name):
                return getattr(module, class_name)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and attr_name.endswith("Skill"):
                return attr

        raise AttributeError(
            f"Не удалось найти класс навыка в модуле {manifest.module_name}. "
            f"Ожидался один из: {candidates}"
        )

    async def _register_in_context(self, skill_class, manifest: DeploymentManifest):
        """Регистрация навыка в ApplicationContext."""
        from core.agent.components.component_factory import ComponentFactory
        from core.config.component_config import ComponentConfig
        from core.infrastructure.discovery.resource_discovery import ResourceDiscovery

        app_ctx = self.application_context
        infra = app_ctx.infrastructure_context

        discovery = ResourceDiscovery(
            base_dir=str(PROJECT_ROOT / "data"),
            profile=getattr(app_ctx, "profile", "dev"),
            event_bus=infra.event_bus,
        )
        await discovery.discover_prompts()
        await discovery.discover_contracts()

        factory = ComponentFactory(infra)

        component_config = ComponentConfig(
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            variant_id=f"{manifest.skill_name}@dynamic",
        )

        component = await factory.create_and_initialize(
            component_class=skill_class,
            name=manifest.skill_name,
            application_context=app_ctx,
            component_config=component_config,
            executor=app_ctx.executor,
        )

        from core.application_context.application_context import ComponentType
        app_ctx.components.register(ComponentType.SKILL, manifest.skill_name, component)

        await component.initialize()

        return component
