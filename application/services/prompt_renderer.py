from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from domain.models.capability import Capability
from domain.models.prompt.prompt_version import PromptRole, PromptExecutionSnapshot
from domain.abstractions.prompt_repository import IPromptRepository, ISnapshotManager
from domain.value_objects.provider_type import LLMProviderType


class PromptRenderer:
    """Рендеринг промтов из версий с подстановкой переменных и валидацией"""
    
    def __init__(self, prompt_repository: IPromptRepository, snapshot_manager: ISnapshotManager = None):
        self._prompt_repository = prompt_repository
        self._snapshot_manager = snapshot_manager
    
    async def render_for_request(
        self,
        capability: Capability,
        provider_type: LLMProviderType,
        template_context: Dict[str, Any],
        session_id: str
    ) -> Tuple[Dict[PromptRole, str], List[str]]:
        """
        Возвращает отрендеренные промты для всех ролей и список ошибок валидации.
        Пример результата:
        ({
            PromptRole.SYSTEM: "Ты — агент для анализа кода...",
            PromptRole.USER: "Проанализируй структуру проекта в /src"
        }, [])
        """
        rendered = {}
        all_errors = []
        
        for role in [PromptRole.SYSTEM, PromptRole.USER]:
            key = f"{provider_type.value}:{role.value}"
            version_id = capability.prompt_versions.get(key)
            
            if not version_id:
                continue
            
            version = await self._prompt_repository.get_version_by_id(version_id)
            if not version:
                all_errors.append(f"Версия промта {version_id} не найдена для {key}")
                continue
            
            # Валидация переменных ДО подстановки
            validation_errors = version.validate_variables(template_context)
            if validation_errors:
                error_messages = []
                for var_name, errors in validation_errors.items():
                    for error in errors:
                        error_msg = f"Ошибка валидации переменной '{var_name}': {error}"
                        error_messages.append(error_msg)
                        all_errors.append(error_msg)
                
                # Если есть ошибки валидации, не рендерим промт
                continue
            
            # Подстановка переменных в шаблон
            content = version.content
            for var_schema in version.variables_schema:
                var_name = var_schema.name
                if var_name in template_context:
                    # Защита от инъекций - подставляем только те переменные, которые определены в схеме
                    content = content.replace(f"{{{{{var_name}}}}}", str(template_context[var_name]))
            
            rendered[role] = content
        
        return rendered, all_errors    
    
    async def render_and_create_snapshot(
        self,
        capability: Capability,
        provider_type: LLMProviderType,
        template_context: Dict[str, Any],
        session_id: str
    ) -> Tuple[Dict[PromptRole, str], Optional[PromptExecutionSnapshot], List[str]]:
        """
        Рендерит промты и создает снапшот выполнения
        """
        rendered_prompts, validation_errors = await self.render_for_request(
            capability, provider_type, template_context, session_id
        )
        
        snapshot = None
        if self._snapshot_manager:  # Проверяем, что менеджер снапшотов доступен
            if validation_errors:
                # Создаем снапшот с ошибками валидации
                # Получаем хотя бы один ID промта для снапшота
                prompt_id = ""
                for role in [PromptRole.SYSTEM, PromptRole.USER]:
                    key = f"{provider_type.value}:{role.value}"
                    version_id = capability.prompt_versions.get(key)
                    if version_id:
                        prompt_id = version_id
                        break
                
                snapshot = PromptExecutionSnapshot(
                    prompt_id=prompt_id,
                    session_id=session_id,
                    rendered_prompt="",
                    variables=template_context,
                    success=False,
                    error_message="; ".join(validation_errors),
                    timestamp=datetime.utcnow()
                )
                await self._snapshot_manager.save_snapshot(snapshot)
            elif rendered_prompts:
                # Создаем снапшот с отрендеренными промтами
                first_role = next(iter(rendered_prompts.keys()), PromptRole.SYSTEM)
                prompt_id = ""
                for role in [PromptRole.SYSTEM, PromptRole.USER]:
                    key = f"{provider_type.value}:{role.value}"
                    version_id = capability.prompt_versions.get(key)
                    if version_id:
                        prompt_id = version_id
                        break
                
                snapshot = PromptExecutionSnapshot(
                    prompt_id=prompt_id,
                    session_id=session_id,
                    rendered_prompt=rendered_prompts.get(first_role, ""),
                    variables=template_context,
                    success=len(validation_errors) == 0,
                    timestamp=datetime.utcnow()
                )
                await self._snapshot_manager.save_snapshot(snapshot)
        
        return rendered_prompts, snapshot, validation_errors