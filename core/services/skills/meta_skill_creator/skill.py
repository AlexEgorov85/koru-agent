"""
Мета-навык для создания, исправления и ревью других навыков.

АРХИТЕКТУРА:
- Наследует BaseSkill, использует ActionExecutor для всех внешних вызовов
- Генерирует Python/YAML артефакты через LLM со структурированным выводом
- Валидирует через AST/YAML анализатор
- Записывает файлы на диск автоматически
- Регистрация в контексте — только после подтверждения человека

CAPABILITIES:
- meta_skill_creator.create — создать новый навык по описанию
- meta_skill_creator.fix — исправить существующий навык
- meta_skill_creator.review — код-ревью существующего навыка
"""
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from core.services.skills.base_skill import BaseSkill
from core.services.skills.meta_skill_creator.validator import SkillValidator
from core.services.skills.meta_skill_creator.dynamic_loader import (
    DynamicSkillLoader,
    DeploymentManifest,
)
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionStatus

if TYPE_CHECKING:
    from core.agent.components.action_executor import ExecutionContext
    from core.application_context.application_context import ApplicationContext
    from core.config.component_config import ComponentConfig


class MetaSkillCreator(BaseSkill):
    """Мета-навык для создания, исправления и ревью навыков."""

    def __init__(
        self,
        name: str,
        application_context: "ApplicationContext",
        component_config: "ComponentConfig",
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
        self._validator = SkillValidator()
        self._loader: Optional[DynamicSkillLoader] = None

    @property
    def description(self) -> str:
        return "Генерация, валидация, исправление и ревью навыков с записью на диск."

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="meta_skill_creator.create",
                description="Создать новый навык по описанию: генерирует Python, YAML, валидирует и записывает на диск. Требует подтверждения оператора.",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=False,
                meta={"requires_llm": True, "execution_type": "generation", "requires_approval": True},
            ),
            Capability(
                name="meta_skill_creator.fix",
                description="Исправить существующий навык: анализирует проблему, генерирует патч, валидирует и записывает. Требует подтверждения оператора.",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=False,
                meta={"requires_llm": True, "execution_type": "refactor", "requires_approval": True},
            ),
            Capability(
                name="meta_skill_creator.review",
                description="Код-ревью существующего навыка: проверка безопасности, архитектуры, стиля.",
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
        execution_context: "ExecutionContext",
    ) -> Dict[str, Any]:
        if capability.name == "meta_skill_creator.create":
            return await self._create_skill(parameters, execution_context)
        elif capability.name == "meta_skill_creator.fix":
            return await self._fix_skill(parameters, execution_context)
        elif capability.name == "meta_skill_creator.review":
            return await self._review_skill(parameters, execution_context)

        return {
            "success": False,
            "error": f"Неизвестная capability: {capability.name}",
        }

    async def _create_skill(
        self,
        parameters: Dict[str, Any],
        execution_context: "ExecutionContext",
    ) -> Dict[str, Any]:
        description = parameters.get("description", "")
        capabilities_list = parameters.get("capabilities", [])
        register_after = parameters.get("register_after", False)

        if not description:
            return {
                "success": False,
                "error": "Параметр 'description' обязателен",
            }

        await self._publish_with_context(
            event_type="meta_skill.creation_started",
            data={"description": description[:100]},
            source=self.name,
            execution_context=execution_context,
        )

        prompt_obj = self.get_prompt("meta_skill_creator.create")
        prompt_text = prompt_obj.content if prompt_obj else self._default_create_prompt()

        output_contract = self.get_output_contract("meta_skill_creator.create")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": prompt_text,
                "system_prompt": self._build_system_prompt("create", description, capabilities_list),
                "structured_output": {
                    "output_model": "MetaSkillCreateOutput",
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
            return {
                "success": False,
                "error": f"LLM вернул ошибку: {llm_result.error}",
            }

        llm_data = llm_result.data
        if hasattr(llm_data, "model_dump"):
            llm_data = llm_data.model_dump()

        python_files = self._extract_python_files(llm_data)
        yaml_files = self._extract_yaml_files(llm_data)
        skill_name = llm_data.get("skill_name", "")
        skill_class_name = llm_data.get("skill_class_name", "")

        if not python_files:
            return {
                "success": False,
                "error": "LLM не сгенерировал Python-файлы",
            }

        if not skill_name:
            skill_name = self._infer_skill_name(description)

        validation = self._validator.validate_artifacts(
            python_files=python_files,
            yaml_files=yaml_files,
            skill_name=skill_name,
        )

        manifest = DeploymentManifest(
            skill_name=skill_name,
            skill_class_name=skill_class_name or f"{skill_name.title().replace('_', '')}Skill",
            python_files=python_files,
            yaml_files=yaml_files,
        )

        write_result = self._loader.write_artifacts(manifest) if self._loader else {"success": False, "errors": ["Loader not initialized"], "written_files": []}

        if write_result["success"]:
            await self._publish_with_context(
                event_type="meta_skill.files_written",
                data={
                    "skill_name": skill_name,
                    "files_count": len(write_result["written_files"]),
                    "register_after": register_after,
                },
                source=self.name,
                execution_context=execution_context,
            )

        return {
            "success": True,
            "skill_name": skill_name,
            "skill_class_name": manifest.skill_class_name,
            "validation": validation,
            "deployment": write_result,
            "files_written": write_result.get("written_files", []),
            "register_after": register_after,
            "message": (
                f"Навык '{skill_name}' сгенерирован и записан на диск. "
                f"Для регистрации в контексте подтвердите: register_after=True"
                if write_result["success"]
                else f"Навык '{skill_name}' сгенерирован, но запись файлов не удалась: {write_result.get('errors', [])}"
            ),
        }

    async def _fix_skill(
        self,
        parameters: Dict[str, Any],
        execution_context: "ExecutionContext",
    ) -> Dict[str, Any]:
        skill_name = parameters.get("skill_name", "")
        issue_description = parameters.get("issue_description", "")

        if not skill_name:
            return {"success": False, "error": "Параметр 'skill_name' обязателен"}
        if not issue_description:
            return {"success": False, "error": "Параметр 'issue_description' обязателен"}

        original_files = self._read_existing_skill_files(skill_name)

        if not original_files:
            return {
                "success": False,
                "error": f"Файлы навыка '{skill_name}' не найдены",
            }

        await self._publish_with_context(
            event_type="meta_skill.fix_started",
            data={"skill_name": skill_name, "issue": issue_description[:100]},
            source=self.name,
            execution_context=execution_context,
        )

        prompt_obj = self.get_prompt("meta_skill_creator.fix")
        prompt_text = prompt_obj.content if prompt_obj else self._default_fix_prompt()

        output_contract = self.get_output_contract("meta_skill_creator.fix")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": prompt_text,
                "system_prompt": self._build_system_prompt("fix", issue_description, [], skill_name=skill_name, original_files=original_files),
                "structured_output": {
                    "output_model": "MetaSkillFixOutput",
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
            return {
                "success": False,
                "error": f"LLM вернул ошибку: {llm_result.error}",
            }

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
            skill_name=skill_name,
        )

        manifest = DeploymentManifest(
            skill_name=skill_name,
            skill_class_name=f"{skill_name.title().replace('_', '')}Skill",
            python_files=patched_files,
            yaml_files={},
        )

        write_result = self._loader.write_artifacts(manifest) if self._loader else {"success": False, "errors": ["Loader not initialized"], "written_files": []}

        change_summary = llm_data.get("change_summary", "")

        return {
            "success": True,
            "skill_name": skill_name,
            "validation": validation,
            "deployment": write_result,
            "change_summary": change_summary,
            "files_written": write_result.get("written_files", []),
            "message": (
                f"Навык '{skill_name}' исправлен и записан на диск."
                if write_result["success"]
                else f"Навык '{skill_name}' исправлен, но запись не удалась."
            ),
        }

    async def _review_skill(
        self,
        parameters: Dict[str, Any],
        execution_context: "ExecutionContext",
    ) -> Dict[str, Any]:
        skill_name = parameters.get("skill_name", "")
        review_focus = parameters.get("review_focus", ["security", "architecture", "style"])

        if not skill_name:
            return {"success": False, "error": "Параметр 'skill_name' обязателен"}

        skill_files = self._read_existing_skill_files(skill_name)

        if not skill_files:
            return {
                "success": False,
                "error": f"Файлы навыка '{skill_name}' не найдены",
            }

        await self._publish_with_context(
            event_type="meta_skill.review_started",
            data={"skill_name": skill_name, "focus": review_focus},
            source=self.name,
            execution_context=execution_context,
        )

        prompt_obj = self.get_prompt("meta_skill_creator.review")
        prompt_text = prompt_obj.content if prompt_obj else self._default_review_prompt()

        output_contract = self.get_output_contract("meta_skill_creator.review")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": prompt_text,
                "system_prompt": self._build_system_prompt("review", "", [], skill_name=skill_name, review_focus=review_focus, skill_files=skill_files),
                "structured_output": {
                    "output_model": "MetaSkillReviewOutput",
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
            return {
                "success": False,
                "error": f"LLM вернул ошибку: {llm_result.error}",
            }

        llm_data = llm_result.data
        if hasattr(llm_data, "model_dump"):
            llm_data = llm_data.model_dump()

        return {
            "success": True,
            "skill_name": skill_name,
            "review": llm_data,
            "message": f"Ревью навыка '{skill_name}' завершено.",
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
            python_files["skill.py"] = llm_data["code"]

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

    def _read_existing_skill_files(self, skill_name: str) -> Dict[str, str]:
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[4]
        skills_dir = project_root / "core" / "services" / "skills" / skill_name
        prompts_dir = project_root / "data" / "prompts" / "skill" / skill_name
        contracts_dir = project_root / "data" / "contracts" / "skill" / skill_name

        result: Dict[str, str] = {}

        for directory in [skills_dir, prompts_dir, contracts_dir]:
            if directory.exists():
                for f in directory.rglob("*"):
                    if f.is_file() and f.suffix in (".py", ".yaml", ".yml"):
                        try:
                            result[str(f.relative_to(project_root))] = f.read_text(encoding="utf-8")
                        except Exception:
                            pass

        return result

    def _infer_skill_name(self, description: str) -> str:
        import re
        words = re.findall(r"[a-zA-Z]+", description)
        if not words:
            return "new_skill"
        return "_".join(w.lower() for w in words[:3]) + "_skill"

    def _get_loader(self) -> DynamicSkillLoader:
        if self._loader is None:
            self._loader = DynamicSkillLoader(self.application_context)
        return self._loader

    def _build_system_prompt(
        self,
        mode: str,
        description: str,
        capabilities_list: List[str],
        skill_name: str = "",
        original_files: Optional[Dict[str, str]] = None,
        review_focus: Optional[List[str]] = None,
        skill_files: Optional[Dict[str, str]] = None,
    ) -> str:
        parts = [f"Режим: {mode}"]

        if mode == "create":
            parts.append(f"Описание навыка: {description}")
            if capabilities_list:
                parts.append(f"Требуемые capabilities: {', '.join(capabilities_list)}")
            parts.append(
                "Сгенерируй полный набор файлов: skill.py, промпты (system/user), контракты (input/output). "
                "Строго следуй архитектуре koru-agent: наследуй BaseSkill, используй self.executor.execute_action, "
                "возвращай Dict из _execute_impl, логируй через _publish_with_context."
            )

        elif mode == "fix":
            parts.append(f"Навык: {skill_name}")
            parts.append(f"Проблема: {description}")
            if original_files:
                parts.append(f"\nОригинальные файлы ({len(original_files)}):")
                for fname, content in list(original_files.items())[:5]:
                    preview = content[:500] + ("..." if len(content) > 500 else "")
                    parts.append(f"\n--- {fname} ---\n{preview}")

        elif mode == "review":
            parts.append(f"Навык: {skill_name}")
            if review_focus:
                parts.append(f"Фокус ревью: {', '.join(review_focus)}")
            if skill_files:
                parts.append(f"\nФайлы навыка ({len(skill_files)}):")
                for fname, content in list(skill_files.items())[:5]:
                    preview = content[:500] + ("..." if len(content) > 500 else "")
                    parts.append(f"\n--- {fname} ---\n{preview}")

        return "\n".join(parts)

    def _default_create_prompt(self) -> str:
        return (
            "Сгенерируй новый навык для koru-agent. "
            "Верни результат в виде структурированного JSON с полями: "
            "skill_name, skill_class_name, python_files (dict filename->content), "
            "yaml_files (dict filename->content)."
        )

    def _default_fix_prompt(self) -> str:
        return (
            "Проанализируй оригинальный код навыка и предложи исправление. "
            "Верни результат с полями: skill_name, patched_files (dict filename->content), "
            "change_summary, validation_errors."
        )

    def _default_review_prompt(self) -> str:
        return (
            "Проведи код-ревью навыка. Оцени безопасность, архитектуру, стиль. "
            "Верни результат с полями: overall_score (0-100), findings (список проблем), "
            "summary, passed (bool)."
        )
