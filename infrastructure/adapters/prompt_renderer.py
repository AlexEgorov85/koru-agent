from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import re
from domain.models.capability import Capability
from domain.models.prompt.prompt_version import PromptRole, PromptExecutionSnapshot
from domain.abstractions.prompt_repository import IPromptRepository, ISnapshotManager
from domain.value_objects.provider_type import LLMProviderType
from infrastructure.gateways.event_system import EventSystem, EventType


class PromptRenderer:
    """Рендеринг промтов из версий с подстановкой переменных и валидацией"""
    
    def __init__(self, prompt_repository: IPromptRepository, snapshot_manager: ISnapshotManager = None, event_system: EventSystem = None):
        self._prompt_repository = prompt_repository
        self._snapshot_manager = snapshot_manager
        self._event_system = event_system or EventSystem()
        self._max_render_size = 1024 * 1024  # 1 MB максимум для результата рендеринга
    
    def _validate_recursive_substitution(self, content: str) -> bool:
        """
        Проверяет наличие рекурсивной подстановки вида {{{{variable}}}} (вложенность более 1 уровня)
        """
        # Используем регулярное выражение для поиска потенциальных случаев рекурсивной подстановки
        # Проверяем вхождения {{ }} которые содержат внутри другие {{ }}
        # Улучшенная версия: ищем любые вложенные конструкции {{...{{...}}...}}
        pattern = r'\{\{[^{}]*\{\{[^{}]*\}\}[^{}]*\}\}'
        matches = re.findall(pattern, content)
        return len(matches) > 0

    def _render_single_attempt(self, version, template_context: Dict[str, Any]) -> str:
        """Выполняет одиночную попытку рендеринга промта"""
        # Проверяем рекурсивную подстановку
        if self._validate_recursive_substitution(version.content):
            raise ValueError("Рекурсивная подстановка переменных обнаружена")
            
        # Проверяем размер результата рендеринга
        content = version.content
        
        # Подстановка переменных в шаблон
        for var_schema in version.variables_schema:
            var_name = var_schema.name
            if var_name in template_context:
                # Защита от инъекций - подставляем только те переменные, которые определены в схеме
                content = content.replace(f"{{{{{var_name}}}}}", str(template_context[var_name]))
        
        # Проверяем размер результата рендеринга
        rendered_size = len(content.encode('utf-8'))
        if rendered_size > self._max_render_size:
            raise ValueError(f"Размер отрендеренного промта превышает допустимый лимит {self._max_render_size} байт. "
                           f"Текущий размер: {rendered_size} байт")
                           
        return content

    def _render_with_retry(self, capability, provider_type, template_context: Dict[str, Any], session_id: str, max_retries: int = 3):
        """Выполняет рендеринг с возможностью повторных попыток при ошибках валидации"""
        last_error = None
        
        for attempt_num in range(max_retries):
            try:
                rendered_prompts = {}
                all_errors = []
                
                for role in [PromptRole.SYSTEM, PromptRole.USER]:
                    key = f"{provider_type.value}:{role.value}"
                    version_id = capability.prompt_versions.get(key)
                    
                    if not version_id:
                        continue
                    
                    version = self._prompt_repository.get_version_by_id(version_id)
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
                        
                        # Если есть ошибки валидации, пробуем следующую попытку
                        raise Exception(f"Ошибки валидации: {'; '.join(error_messages)}")
                    
                    # Выполняем рендеринг с защитой от рекурсивной подстановки
                    content = self._render_single_attempt(version, template_context)
                    rendered_prompts[role] = content
                
                # Если все роли успешно отрендерены, возвращаем результат
                return rendered_prompts, all_errors
                
            except Exception as e:
                last_error = e
                if attempt_num < max_retries - 1:  # Не ждем после последней попытки
                    # Экспоненциальная задержка: 0.1 * (2^attempt_num)
                    delay = 0.1 * (2 ** attempt_num)
                    # В синхронном варианте не используем asyncio.sleep, а используем time.sleep
                    import time
                    time.sleep(delay)
                else:
                    # Последняя попытка - возвращаем ошибки
                    error_message = f"Валидация не пройдена после {max_retries} попыток: {str(e)}"
                    return {}, [error_message]
        
        return {}, [str(last_error)]

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
        rendered_prompts, all_errors = self._render_with_retry(
            capability, 
            provider_type, 
            template_context, 
            session_id, 
            max_retries=3
        )
        
        # Публикуем событие в шину событий
        success = len(all_errors) == 0
        # Для синхронной версии вызываем публикацию без ожидания и ловим RuntimeError для корректной обработки асинхронных вызовов
        try:
            import asyncio
            try:
                # Пробуем вызвать асинхронный метод
                loop = asyncio.get_running_loop()
                # Если уже есть запущенный цикл, используем run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(
                    self._event_system.publish_simple(
                        event_type=EventType.INFO if success else EventType.ERROR,
                        source="PromptRenderer",
                        data={
                            "capability": capability.name,
                            "provider_type": provider_type.value,
                            "session_id": session_id,
                            "success": success,
                            "error_count": len(all_errors),
                            "errors": all_errors
                        }
                    ), loop)
                # Не ждем результат, чтобы не блокировать основной поток
            except RuntimeError:
                # Если нет запущенного цикла, запускаем его краткосрочно
                asyncio.run(self._event_system.publish_simple(
                    event_type=EventType.INFO if success else EventType.ERROR,
                    source="PromptRenderer",
                    data={
                        "capability": capability.name,
                        "provider_type": provider_type.value,
                        "session_id": session_id,
                        "success": success,
                        "error_count": len(all_errors),
                        "errors": all_errors
                    }
                ))
        except Exception:
            # Игнорируем ошибки публикации событий, чтобы не ломать основной процесс
            pass
        
        return rendered_prompts, all_errors

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
            capability=capability,
            provider_type=provider_type,
            template_context=template_context,
            session_id=session_id
        )
        
        snapshot = None
        if self._snapshot_manager:  # Проверяем, что менеджер снапшотов доступен
            try:
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
                    # Вызываем метод менеджера снапшотов с await
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
                    # Вызываем метод менеджера снапшотов с await
                    await self._snapshot_manager.save_snapshot(snapshot)
            except Exception as e:
                # Логируем ошибку сохранения снапшота, но не блокируем основной поток
                print(f"Не удалось сохранить снапшот: {e}")
                # Продолжаем выполнение основной логики - ошибка не блокирует основной поток
                
        return rendered_prompts, snapshot, validation_errors