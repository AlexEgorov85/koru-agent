"""
Мета-навык для создания, исправления и ревью всех типов компонентов.

АРХИТЕКТУРА:
- Наследует BaseSkill, использует ActionExecutor для всех внешних вызовов
- Генерирует Python/YAML артефакты через LLM со структурированным выводом
- Поддержка типов: skill, tool, service, behavior
- Валидирует через AST/YAML анализатор
- Записывает файлы на диск автоматически
- Регистрация в контексте — только после подтверждения человека

CAPABILITIES:
- meta_component_creator.create — создать новый компонент
- meta_component_creator.fix — исправить существующий компонент
- meta_component_creator.review — код-ревью существующего компонента
"""
from typing import Dict, Any, List, Optional

from core.components.skills.base_skill import BaseSkill
from core.components.skills.meta_component_creator.validator import ComponentValidator
from core.components.skills.meta_component_creator.dynamic_loader import (
    DynamicComponentLoader,
    DeploymentManifest,
    TYPE_DIRECTORIES,
)
from core.components.skills.meta_component_creator.contracts.meta_component import (
    VALID_COMPONENT_TYPES,
    TYPE_SUFFIXES,
)
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionStatus
from core.agent.components.action_executor import ExecutionContext
from core.application_context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig


class MetaComponentCreator(BaseSkill):
    """Мета-навык для создания, исправления и ревью компонентов любого типа."""

    def __init__(
        self,
        name: str,
        application_context: ApplicationContext,
        component_config: ComponentConfig,
        executor: Any,
        event_bus: Any = None,
    ):
        super().__init__(
            name=name,
            application_context=application_context,
            component_config=component_config,
            executor=executor,
            event_bus=event_bus,
        )
        self._validator = ComponentValidator()
        self._loader: Optional[DynamicComponentLoader] = None

    @property
    def description(self) -> str:
        return "Генерация, валидация, исправление и ревью компонентов (skill/tool/service/behavior)."

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="meta_component_creator.create",
                description="Создать новый компонент (skill/tool/service/behavior): генерирует Python, YAML, валидирует и записывает. Требует подтверждения оператора.",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=False,
                meta={"requires_llm": True, "execution_type": "generation", "requires_approval": True},
            ),
            Capability(
                name="meta_component_creator.fix",
                description="Исправить существующий компонент: анализирует проблему, генерирует патч, валидирует и записывает. Требует подтверждения оператора.",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=False,
                meta={"requires_llm": True, "execution_type": "refactor", "requires_approval": True},
            ),
            Capability(
                name="meta_component_creator.review",
                description="Код-ревью компонента: проверка безопасности, архитектуры, стиля.",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=False,
                meta={"requires_llm": True, "execution_type": "review", "requires_approval": True},
            ),
        ]

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: ExecutionContext,
    ) -> Dict[str, Any]:
        if capability.name == "meta_component_creator.create":
            return await self._create_component(parameters, execution_context)
        elif capability.name == "meta_component_creator.fix":
            return await self._fix_component(parameters, execution_context)
        elif capability.name == "meta_component_creator.review":
            return await self._review_component(parameters, execution_context)

        return {
            "success": False,
            "error": f"Неизвестная capability: {capability.name}",
        }

    async def _create_component(
        self,
        parameters: Dict[str, Any],
        execution_context: ExecutionContext,
    ) -> Dict[str, Any]:
        description = parameters.get("description", "")
        component_type = parameters.get("component_type", "skill")
        capabilities_list = parameters.get("capabilities", [])
        dependencies = parameters.get("dependencies", [])
        has_prompts = parameters.get("has_prompts", True)
        has_contracts = parameters.get("has_contracts", True)
        register_after = parameters.get("register_after", False)

        if not description:
            return {"success": False, "error": "Параметр 'description' обязателен"}

        if component_type not in VALID_COMPONENT_TYPES:
            return {
                "success": False,
                "error": f"Неизвестный тип компонента: {component_type}. Допустимые: {VALID_COMPONENT_TYPES}",
            }

        await self._publish_with_context(
            event_type="meta_component.creation_started",
            data={"description": description, "component_type": component_type},
            source=self.name,
            execution_context=execution_context,
        )

        prompt_obj = self.get_prompt("meta_component_creator.create")
        prompt_text = prompt_obj.content if prompt_obj else self._default_create_prompt()

        output_contract = self.get_output_contract("meta_component_creator.create")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": prompt_text,
                "system_prompt": self._build_system_prompt(
                    "create", description, capabilities_list,
                    component_type=component_type,
                    dependencies=dependencies,
                    has_prompts=has_prompts,
                    has_contracts=has_contracts,
                ),
                "structured_output": {
                    "output_model": "MetaComponentCreateOutput",
                    "schema_def": output_contract,
                    "max_retries": 3,
                    "strict_mode": True,
                },
                "temperature": 0.1,
                "max_tokens": 8000,
            },
            context=execution_context,
        )

        if llm_result.status != ExecutionStatus.COMPLETED:
            return {"success": False, "error": f"LLM вернул ошибку: {llm_result.error}"}

        llm_data = llm_result.data
        if hasattr(llm_data, "model_dump"):
            llm_data = llm_data.model_dump()

        python_files = self._extract_python_files(llm_data)
        yaml_files = self._extract_yaml_files(llm_data)
        component_name = llm_data.get("component_name", "")
        class_name = llm_data.get("class_name", "")

        if not python_files:
            return {"success": False, "error": "LLM не сгенерировал Python-файлы"}

        if not component_name:
            component_name = self._infer_component_name(description, component_type)

        validation = self._validator.validate_artifacts(
            python_files=python_files,
            yaml_files=yaml_files,
            component_name=component_name,
            component_type=component_type,
        )

        manifest = DeploymentManifest(
            component_name=component_name,
            component_type=component_type,
            class_name=class_name or f"{component_name.title().replace('_', '')}{TYPE_SUFFIXES.get(component_type, 'Component')}",
            python_files=python_files,
            yaml_files=yaml_files,
        )

        loader = self._get_loader()
        write_result = loader.write_artifacts(manifest)

        if write_result["success"]:
            await self._publish_with_context(
                event_type="meta_component.files_written",
                data={
                    "component_name": component_name,
                    "component_type": component_type,
                    "files_count": len(write_result["written_files"]),
                    "register_after": register_after,
                },
                source=self.name,
                execution_context=execution_context,
            )

        return {
            "success": True,
            "component_name": component_name,
            "component_type": component_type,
            "class_name": manifest.class_name,
            "validation": validation,
            "deployment": write_result,
            "files_written": write_result.get("written_files", []),
            "register_after": register_after,
            "message": (
                f"Компонент '{component_name}' ({component_type}) сгенерирован и записан на диск. "
                f"Для регистрации в контексте подтвердите: register_after=True"
                if write_result["success"]
                else f"Компонент '{component_name}' сгенерирован, но запись файлов не удалась: {write_result.get('errors', [])}"
            ),
        }

    async def _fix_component(
        self,
        parameters: Dict[str, Any],
        execution_context: ExecutionContext,
    ) -> Dict[str, Any]:
        component_name = parameters.get("component_name", "")
        component_type = parameters.get("component_type", "skill")
        issue_description = parameters.get("issue_description", "")

        if not component_name:
            return {"success": False, "error": "Параметр 'component_name' обязателен"}
        if not issue_description:
            return {"success": False, "error": "Параметр 'issue_description' обязателен"}

        original_files = self._read_existing_files(component_name, component_type)

        if not original_files:
            return {
                "success": False,
                "error": f"Файлы компонента '{component_name}' ({component_type}) не найдены",
            }

        await self._publish_with_context(
            event_type="meta_component.fix_started",
            data={"component_name": component_name, "component_type": component_type, "issue": issue_description},
            source=self.name,
            execution_context=execution_context,
        )

        prompt_obj = self.get_prompt("meta_component_creator.fix")
        prompt_text = prompt_obj.content if prompt_obj else self._default_fix_prompt()

        output_contract = self.get_output_contract("meta_component_creator.fix")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": prompt_text,
                "system_prompt": self._build_system_prompt(
                    "fix", issue_description, [],
                    component_type=component_type,
                    component_name=component_name,
                    original_files=original_files,
                ),
                "structured_output": {
                    "output_model": "MetaComponentFixOutput",
                    "schema_def": output_contract,
                    "max_retries": 3,
                    "strict_mode": True,
                },
                "temperature": 0.1,
                "max_tokens": 8000,
            },
            context=execution_context,
        )

        if llm_result.status != ExecutionStatus.COMPLETED:
            return {"success": False, "error": f"LLM вернул ошибку: {llm_result.error}"}

        llm_data = llm_result.data
        if hasattr(llm_data, "model_dump"):
            llm_data = llm_data.model_dump()

        patched_files = llm_data.get("patched_files", {})
        if not patched_files:
            patched_files = self._extract_python_files(llm_data)
            patched_files.update(self._extract_yaml_files(llm_data))

        validation = self._validator.validate_artifacts(
            python_files=patched_files,
            yaml_files={},
            component_name=component_name,
            component_type=component_type,
        )

        loader = self._get_loader()
        manifest = DeploymentManifest(
            component_name=component_name,
            component_type=component_type,
            class_name=f"{component_name.title().replace('_', '')}{TYPE_SUFFIXES.get(component_type, 'Component')}",
            python_files=patched_files,
            yaml_files={},
        )

        write_result = loader.write_artifacts(manifest)
        change_summary = llm_data.get("change_summary", "")

        return {
            "success": True,
            "component_name": component_name,
            "component_type": component_type,
            "validation": validation,
            "deployment": write_result,
            "change_summary": change_summary,
            "files_written": write_result.get("written_files", []),
            "message": (
                f"Компонент '{component_name}' исправлен и записан на диск."
                if write_result["success"]
                else f"Компонент '{component_name}' исправлен, но запись не удалась."
            ),
        }

    async def _review_component(
        self,
        parameters: Dict[str, Any],
        execution_context: ExecutionContext,
    ) -> Dict[str, Any]:
        component_name = parameters.get("component_name", "")
        component_type = parameters.get("component_type", "skill")
        review_focus = parameters.get("review_focus", ["security", "architecture", "style"])

        if not component_name:
            return {"success": False, "error": "Параметр 'component_name' обязателен"}

        component_files = self._read_existing_files(component_name, component_type)

        if not component_files:
            return {
                "success": False,
                "error": f"Файлы компонента '{component_name}' ({component_type}) не найдены",
            }

        await self._publish_with_context(
            event_type="meta_component.review_started",
            data={"component_name": component_name, "component_type": component_type, "focus": review_focus},
            source=self.name,
            execution_context=execution_context,
        )

        prompt_obj = self.get_prompt("meta_component_creator.review")
        prompt_text = prompt_obj.content if prompt_obj else self._default_review_prompt()

        output_contract = self.get_output_contract("meta_component_creator.review")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": prompt_text,
                "system_prompt": self._build_system_prompt(
                    "review", "", [],
                    component_type=component_type,
                    component_name=component_name,
                    review_focus=review_focus,
                    component_files=component_files,
                ),
                "structured_output": {
                    "output_model": "MetaComponentReviewOutput",
                    "schema_def": output_contract,
                    "max_retries": 3,
                    "strict_mode": True,
                },
                "temperature": 0.1,
                "max_tokens": 6000,
            },
            context=execution_context,
        )

        if llm_result.status != ExecutionStatus.COMPLETED:
            return {"success": False, "error": f"LLM вернул ошибку: {llm_result.error}"}

        llm_data = llm_result.data
        if hasattr(llm_data, "model_dump"):
            llm_data = llm_data.model_dump()

        return {
            "success": True,
            "component_name": component_name,
            "component_type": component_type,
            "review": llm_data,
            "message": f"Ревью компонента '{component_name}' ({component_type}) завершено.",
        }

    def _extract_python_files(self, llm_data: Dict[str, Any]) -> Dict[str, str]:
        python_files: Dict[str, str] = {}

        files_list = llm_data.get("python_files", [])
        if isinstance(files_list, list):
            for item in files_list:
                if isinstance(item, dict) and "filename" in item and "content" in item:
                    python_files[item["filename"]] = item["content"]
        elif isinstance(files_list, dict):
            python_files = files_list

        if "code" in llm_data and not python_files:
            python_files["main.py"] = llm_data["code"]

        return python_files

    def _extract_yaml_files(self, llm_data: Dict[str, Any]) -> Dict[str, str]:
        yaml_files: Dict[str, str] = {}

        files_list = llm_data.get("yaml_files", [])
        if isinstance(files_list, list):
            for item in files_list:
                if isinstance(item, dict) and "filename" in item and "content" in item:
                    yaml_files[item["filename"]] = item["content"]
        elif isinstance(files_list, dict):
            yaml_files = files_list

        return yaml_files

    def _read_existing_files(self, component_name: str, component_type: str) -> Dict[str, str]:
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[4]
        dir_info = TYPE_DIRECTORIES.get(component_type, TYPE_DIRECTORIES["skill"])

        directories = []

        if component_type == "tool":
            base_dir = dir_info["python"]
            for f in base_dir.iterdir():
                if f.is_file() and component_name in f.stem and f.suffix == ".py":
                    directories.append(f.parent)
                    break
        elif component_type == "service":
            svc_dir = dir_info["python"] / component_name
            if svc_dir.is_dir():
                directories.append(svc_dir)
            else:
                svc_file = dir_info["python"] / f"{component_name}_service.py"
                if svc_file.is_file():
                    directories.append(svc_file.parent)
        else:
            comp_dir = dir_info["python"] / component_name
            if comp_dir.is_dir():
                directories.append(comp_dir)

        if dir_info["prompts"]:
            prompts_dir = dir_info["prompts"] / component_name
            if prompts_dir.is_dir():
                directories.append(prompts_dir)

        if dir_info["contracts"]:
            contracts_dir = dir_info["contracts"] / component_name
            if contracts_dir.is_dir():
                directories.append(contracts_dir)

        result: Dict[str, str] = {}

        for directory in directories:
            if directory.exists():
                for f in directory.rglob("*"):
                    if f.is_file() and f.suffix in (".py", ".yaml", ".yml"):
                        try:
                            result[str(f.relative_to(project_root))] = f.read_text(encoding="utf-8")
                        except Exception:
                            pass

        return result

    def _infer_component_name(self, description: str, component_type: str) -> str:
        import re
        words = re.findall(r"[a-zA-Z]+", description)
        if not words:
            return f"new_{component_type}"
        base = "_".join(w.lower() for w in words[:3])
        suffix = {"tool": "_tool", "service": "_service"}.get(component_type, "")
        return f"{base}{suffix}"

    def _get_loader(self) -> DynamicComponentLoader:
        if self._loader is None:
            self._loader = DynamicComponentLoader(self.application_context)
        return self._loader

    def _build_system_prompt(
        self,
        mode: str,
        description: str,
        capabilities_list: List[str],
        component_type: str = "skill",
        component_name: str = "",
        dependencies: Optional[List[str]] = None,
        has_prompts: bool = True,
        has_contracts: bool = True,
        original_files: Optional[Dict[str, str]] = None,
        review_focus: Optional[List[str]] = None,
        component_files: Optional[Dict[str, str]] = None,
    ) -> str:
        parts = [f"Режим: {mode}"]
        parts.append(f"Тип компонента: {component_type}")

        type_instructions = {
            "skill": (
                "Навык (Skill): наследуй BaseSkill из core.services.skills.base_skill. "
                "Файл: skill.py в core/services/skills/{name}/. "
                "Используй self.executor.execute_action для внешних вызовов. "
                "Возвращай Dict из _execute_impl."
            ),
            "tool": (
                "Инструмент (Tool): наследуй BaseTool из core.services.tools.base_tool. "
                "Файл: {name}_tool.py в core/services/tools/. "
                "Определи {Name}ToolInput(ToolInput) и {Name}ToolOutput(ToolOutput). "
                "_execute_impl — синхронный. Прямая работа с инфраструктурой."
            ),
            "service": (
                "Сервис (Service): наследуй BaseService из core.services.base_service. "
                "Файл: service.py в core/services/{name}/. "
                "Может иметь DEPENDENCIES = [...]. "
                "Определи {Name}ServiceInput(ServiceInput) и {Name}ServiceOutput(ServiceOutput)."
            ),
            "behavior": (
                "Поведение (Behavior): наследуй BaseBehaviorPattern из core.agent.behaviors.base_behavior_pattern. "
                "Файл: pattern.py в core/agent/behaviors/{name}/. "
                "Главный метод: async decide(session_context, available_capabilities) -> Decision. "
                "Используй self.llm_orchestrator для LLM-вызовов."
            ),
        }

        if mode == "create":
            parts.append(f"Описание: {description}")
            if capabilities_list:
                parts.append(f"Требуемые capabilities: {', '.join(capabilities_list)}")
            if dependencies:
                parts.append(f"Зависимости: {', '.join(dependencies)}")

            parts.append(type_instructions.get(component_type, ""))
            parts.append(
                "Архитектурные правила koru-agent:\n"
                "- Все компоненты наследуют BaseComponent\n"
                "- Взаимодействие ТОЛЬКО через ActionExecutor\n"
                "- event_bus — обязательный параметр конструктора\n"
                "- _execute_impl возвращает Dict, НЕ ExecutionResult\n"
                "- Используй typing: Dict, Any, List, Optional, TYPE_CHECKING\n"
                "- Русские docstrings, английские идентификаторы\n"
                "- Type hints на всех сигнатурах\n"
                "- Логируй через _publish_with_context(), НЕ через logging.getLogger()\n"
                "- НЕ используй import os, sys, subprocess, eval, exec"
            )

            if has_prompts:
                parts.append(f"Создай промпты system и user для каждой capability.")
            if has_contracts:
                parts.append(f"Создай контракты input и output для каждой capability.")

        elif mode == "fix":
            parts.append(f"Компонент: {component_name}")
            parts.append(f"Проблема: {description}")
            if original_files:
                parts.append(f"\nОригинальные файлы ({len(original_files)}):")
                for fname, content in list(original_files.items())[:5]:
                    preview = content
                    parts.append(f"\n--- {fname} ---\n{preview}")

        elif mode == "review":
            parts.append(f"Компонент: {component_name}")
            if review_focus:
                parts.append(f"Фокус ревью: {', '.join(review_focus)}")
            if component_files:
                parts.append(f"\nФайлы компонента ({len(component_files)}):")
                for fname, content in list(component_files.items())[:5]:
                    preview = content
                    parts.append(f"\n--- {fname} ---\n{preview}")

        return "\n".join(parts)

    def _default_create_prompt(self) -> str:
        return (
            "Сгенерируй новый компонент для koru-agent. "
            "Верни результат в виде структурированного JSON с полями: "
            "component_name, component_type, class_name, "
            "python_files (dict filename->content), "
            "yaml_files (dict filename->content)."
        )

    def _default_fix_prompt(self) -> str:
        return (
            "Проанализируй оригинальный код компонента и предложи исправление. "
            "Верни результат с полями: component_name, component_type, "
            "patched_files (dict filename->content), "
            "change_summary, validation_errors."
        )

    def _default_review_prompt(self) -> str:
        return (
            "Проведи код-ревью компонента. Оцени безопасность, архитектуру, стиль. "
            "Верни результат с полями: overall_score (0-100), findings (список проблем), "
            "summary, passed (bool)."
        )
