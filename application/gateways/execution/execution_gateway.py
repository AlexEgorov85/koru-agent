from typing import Dict, Any
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.abstractions.system.i_tool_registry import IToolRegistry
from domain.abstractions.system.i_config_manager import IConfigManager
from domain.abstractions.system.base_session_context import BaseSessionContext
from domain.abstractions.event_system import IEventPublisher
from domain.models.capability import Capability
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus
from application.services.prompt_renderer import PromptRenderer
from domain.models.prompt.prompt_version import PromptUsageMetrics
from datetime import datetime

from domain.value_objects.provider_type import LLMProviderType


class ExecutionGateway:
    """
    Шлюз выполнения capability.
    
    Отвечает за:
    1. Поиск навыка по capability
    2. Выполнение capability через навык
    3. Базовую обработку исключений
    """
    
    def __init__(self, skill_registry: ISkillRegistry, prompt_repository=None, event_publisher: IEventPublisher = None):
        self._skill_registry = skill_registry
        self._prompt_repository = prompt_repository
        self._event_publisher = event_publisher

    @staticmethod
    def _create_failed_result(error: str, summary: str) -> ExecutionResult:
        """Создание результата с ошибкой."""
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            result=None,
            observation_item_id=None,
            summary=summary,
            error=error
        )

    @staticmethod
    def _create_success_result(result: Any, summary: str) -> ExecutionResult:
        """Создание успешного результата."""
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result=result,
            observation_item_id=None,  # ID будет установлен в сессии
            summary=summary,
            error=None
        )

    async def execute_capability(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        session: BaseSessionContext,
        step_number: int = 0
    ) -> ExecutionResult:
        """
        Выполнение capability через соответствующий навык.
        Включает предварительную валидацию решения от LLM.
        Использует систему версионности промтов при наличии репозитория.
        
        Args:
            capability: Объект capability для выполнения
            parameters: Параметры для выполнения (может содержать LLMResponse)
            session: Контекст сессии
            step_number: Номер шага (для отслеживания)
            
        Returns:
            ExecutionResult с результатом выполнения
        """
        # Проверяем, является ли parameters объектом LLMResponse (или содержит его)
        from infrastructure.gateways.llm_providers.base_provider import LLMResponse
        llm_response = None
        actual_params = parameters

        if isinstance(parameters, dict):
            # Проверяем, есть ли в параметрах объект LLMResponse
            if 'llm_response' in parameters:
                llm_response = parameters['llm_response']
            elif isinstance(parameters.get('raw_text'), str):  # Вероятно, это сам LLMResponse
                # Извлекаем только нужные поля, учитывая порядок в определении LLMResponse
                llm_data = {k: v for k, v in parameters.items() if k in ['raw_text', 'model', 'tokens_used', 'generation_time', 'parsed', 'validation_error', 'validation_attempts', 'validation_chain', 'finish_reason', 'is_truncated', 'metadata']}
                # Убедимся, что обязательные поля присутствуют
                if 'raw_text' in llm_data and 'model' in llm_data and 'tokens_used' in llm_data and 'generation_time' in llm_data:
                    llm_response = LLMResponse(**llm_data)
                    actual_params = {}
                else:
                    actual_params = parameters
            else:
                actual_params = parameters
        elif isinstance(parameters, LLMResponse):
            llm_response = parameters
            actual_params = {}

        # Если есть ответ от LLM, выполняем валидацию
        if llm_response and hasattr(llm_response, 'raw_text'):
            # Проверяем, содержит ли ответ ошибку валидации
            if hasattr(llm_response, 'validation_error') and llm_response.validation_error:
                # Логируем ошибку валидации
                self._log_validation_error(llm_response.validation_error, llm_response.raw_text)
                
                # В зависимости от типа ошибки принимаем решение
                if self._is_critical_validation_error(llm_response.validation_error):
                    return self._create_failed_result(
                        error=f"Критическая ошибка валидации: {llm_response.validation_error}",
                        summary="Невозможно обработать решение от LLM"
                    )
                else:
                    # Пробуем fallback стратегию
                    return await self._handle_fallback_execution(capability, actual_params, session, llm_response)
            else:
                # Если валидация прошла успешно, используем parsed данные
                if llm_response.parsed:
                    actual_params = llm_response.parsed

        # Определение провайдера из контекста (по умолчанию используем LOCAL_LLAMA)
        provider_type = LLMProviderType.LOCAL_LLAMA  # В реальной системе определяется из контекста сессии

        # Рендеринг промтов через сервис, если доступен репозиторий
        rendered_prompts = {}
        system_version_id = None
        user_version_id = None

        if self._prompt_repository:
            prompt_renderer = PromptRenderer(self._prompt_repository)
            rendered_prompts, errors = await prompt_renderer.render_for_request(
                capability=capability,
                provider_type=provider_type,
                template_context={
                    "goal": session.get_goal() if hasattr(session, 'get_goal') and callable(getattr(session, 'get_goal')) else "",
                    "context": session.get_last_steps(3) if hasattr(session, 'get_last_steps') and callable(getattr(session, 'get_last_steps')) else [],
                    "tools": self._get_available_tools(),
                    **parameters
                },
                session_id=session.session_id if hasattr(session, 'session_id') else f"session_{datetime.utcnow().isoformat()}"
            )
            # Сохраняем ID версий для аудита
            system_key = f"{provider_type.value}:system"
            user_key = f"{provider_type.value}:user"
            system_version_id = capability.prompt_versions.get(system_key)
            user_version_id = capability.prompt_versions.get(user_key)

        # 1. Получение навыка для capability
        skill = self._skill_registry.get_skill(capability.skill_name)
        if not skill:
            return self._create_failed_result(
                error=f"Skill for capability '{capability.name}' not found",
                summary=f"Cannot execute capability '{capability.name}'"
            )
        
        # 2. Выполнение через навык
        try:
            result = await skill.execute(actual_params, session)
            
            # Обновление метрик использования промтов, если доступен репозиторий
            if self._prompt_repository:
                await self._update_prompt_metrics(
                    system_version_id=system_version_id,
                    user_version_id=user_version_id,
                    success=True,
                    generation_time=0  # В реальной системе получается из ответа LLM
                )
            
            return self._create_success_result(
                result=result,
                summary=f"Capability '{capability.name}' executed successfully"
            )
        except Exception as e:
            # Обновление метрик при ошибке выполнения
            if self._prompt_repository:
                await self._update_prompt_metrics(
                    system_version_id=system_version_id,
                    user_version_id=user_version_id,
                    success=False,
                    generation_time=0  # В реальной системе получается из ответа LLM
                )
            return self._create_failed_result(
                error=str(e),
                summary=f"Error executing capability '{capability.name}': {str(e)}"
            )
    
    
    def _get_available_tools(self) -> list:
        """Получение списка доступных инструментов"""
        # В реальной системе этот метод должен возвращать актуальный список инструментов
        # Здесь возвращаем пустой список как заглушку
        return []
    
    
    async def _update_prompt_metrics(
        self,
        system_version_id: str,
        user_version_id: str,
        success: bool,
        generation_time: float
    ) -> None:
        """Обновление метрик использования версий промтов"""
        if not self._prompt_repository:
            return
        
        # Подготовка обновления метрик
        metrics_update = PromptUsageMetrics(
            usage_count=1,
            success_count=1 if success else 0,
            avg_generation_time=generation_time,
            last_used_at=datetime.utcnow(),
            error_rate=0.0 if success else 1.0
        )
        
        # Обновление метрик для системного промта
        if system_version_id:
            await self._prompt_repository.update_usage_metrics(system_version_id, metrics_update)
        
        # Обновление метрик для пользовательского промта
        if user_version_id:
            await self._prompt_repository.update_usage_metrics(user_version_id, metrics_update)
    
    
    def _log_validation_error(self, validation_error: str, raw_text: str) -> None:
        """Логирование ошибки валидации"""
        print(f"Валидация LLM ответа не удалась: {validation_error}")
        print(f"Сырой ответ: {raw_text[:200]}...")
    
    def _is_critical_validation_error(self, validation_error: str) -> bool:
        """Проверяет, является ли ошибка критической"""
        # Критические ошибки - это те, которые указывают на серьезные проблемы
        critical_indicators = [
            "empty response",  # Пустой ответ
            "JSONDecodeError",  # Не удалось распарсить JSON
        ]
        return any(indicator in validation_error.lower() for indicator in critical_indicators)
    
    async def _handle_fallback_execution(self, capability: Capability, parameters: Dict[str, Any], 
                                      session: BaseSessionContext, llm_response) -> ExecutionResult:
        """Обработка выполнения с fallback стратегией"""
        # Пока используем стандартную логику, но в будущем можно добавить более сложную логику
        return await self.execute_capability(capability, parameters, session)
    
