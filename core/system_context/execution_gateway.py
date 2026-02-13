"""
Простой ExecutionGateway, который только выполняет capability через навыки.
НАЗНАЧЕНИЕ:
- Найти навык по capability
- Выполнить capability через навык
- Вернуть результат
ОСОБЕННОСТИ:
- Минимальная ответственность
- Никакой работы с контекстом
- Никакой обработки ошибок (только базовое логирование)
- Никакой записи в контекст сессии
"""
from datetime import datetime
import logging
from typing import Any, Dict, Optional


from core.retry_policy.retry_and_error_policy import RetryPolicy
from core.session.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemMetadata, ContextItemType
from core.application.skills.base_skill import BaseSkill
from core.application.context.application_context import ApplicationContext
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus
from core.security.user_context import UserContext
from core.security.authorizer import RoleBasedAuthorizer, PermissionDeniedError

logger = logging.getLogger(__name__)

class ExecutionGateway:
    """
    Минималистичный шлюз выполнения capability.
    Отвечает ТОЛЬКО за:
    1. Поиск навыка по capability
    2. Выполнение capability через навык
    3. Базовую обработку исключений
    ВСЕ ОСТАЛЬНОЕ:
    - Работа с контекстом
    - Регистрация шагов
    - Обработка ошибок с политиками
    - Валидация параметров
    ... должны выполняться на других уровнях системы
    """
    def __init__(
        self,
        application_context: Optional[ApplicationContext] = None,
        retry_policy: Optional[RetryPolicy] = None,
        action_validator=None,  # Добавляем параметр для валидации действий
        authorizer=None  # Добавляем параметр для авторизации
    ):
        self.application_context = application_context
        self.retry_policy = retry_policy
        self.action_validator = action_validator
        self.authorizer = authorizer or RoleBasedAuthorizer()  # Используем RoleBasedAuthorizer по умолчанию

    async def execute_capability(
        self,
        capability: Capability,
        action_payload: Dict[str, Any],
        session: BaseSessionContext,
        step_number: int,
        user_context: Optional[UserContext] = None  # Добавляем контекст пользователя
    ) -> ExecutionResult:
        """
        Выполнение capability через соответствующий навык.
        ПРОЦЕДУРА:
        1. Проверить права доступа (если предоставлен user_context)
        2. Найти навык по capability
        3. Вызвать execute() навыка
        4. Вернуть результат
        ВОЗВРАЩАЕТ:
        - ExecutionResult с результатом выполнения
        ИСКЛЮЧЕНИЯ:
        - Передает все исключения вызывающему коду
        - Не обрабатывает ошибки, не логирует детали
        """

        # 1. Проверяем права доступа (если предоставлен user_context)
        if user_context:
            try:
                await self.authorizer.authorize(user_context, capability, action_payload)
            except PermissionDeniedError as e:
                logger.error(f"Отказ в доступе для пользователя '{user_context.user_id}': {str(e)}")
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=str(e),
                    error="PERMISSION_DENIED"
                )

        # 2. Проверяем, что application_context доступен
        if self.application_context is None:
            error_msg = f"Application context недоступен для выполнения capability {capability.name}"
            logger.error(error_msg)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=error_msg,
                error="APPLICATION_CONTEXT_NOT_AVAILABLE"
            )

        # Получаем навык для выполнения capability
        skill = self.application_context.get_resource(capability.skill_name)

        # Проверяем, что навык найден
        if skill is None:
            error_msg = f"Skill not found for capability {capability.name}"
            logger.error(error_msg)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=error_msg,
                error="SKILL_NOT_FOUND"
            )

        # 3. Валидируем параметры действия через ContractService (новое)
        validated_payload = action_payload
        contract_service = getattr(self.application_context, 'get_service', lambda name: None) and self.application_context.get_service("contract_service")
        if contract_service:
            try:
                validation_result = await contract_service.validate(
                    capability_name=capability.name,
                    data=action_payload,
                    direction="input"
                )
                if not validation_result["is_valid"]:
                    error_msg = f"Validation failed for {capability.name}: {validation_result['errors']}"
                    logger.error(error_msg)
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        result=None,
                        observation_item_id=None,
                        summary=error_msg,
                        error="VALIDATION_ERROR"
                    )
                validated_payload = validation_result["validated_data"]
            except Exception as e:
                logger.warning(f"Ошибка валидации через ContractService: {str(e)}, используем fallback")
                # Fallback: используем старый валидатор, если есть
                if self.action_validator:
                    try:
                        validated_payload = self.action_validator.validate(action_payload)
                    except Exception as fallback_error:
                        logger.error(f"Fallback validation also failed: {str(fallback_error)}")
                        return ExecutionResult(
                            status=ExecutionStatus.FAILED,
                            result=None,
                            observation_item_id=None,
                            summary=f"Validation failed: {str(fallback_error)}",
                            error="VALIDATION_ERROR"
                        )
        else:
            # Fallback: используем старый валидатор, если ContractService недоступен
            if self.action_validator:
                try:
                    validated_payload = self.action_validator.validate(action_payload)
                except Exception as e:
                    logger.error(f"Ошибка валидации параметров действия: {str(e)}")
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        result=None,
                        observation_item_id=None,
                        summary=f"Invalid action payload: {str(e)}",
                        error="INVALID_INPUT"
                    )

        # 4. Записываем действие в контекст
        action_item_id = session.record_action(
            action_data=validated_payload,
            step_number=step_number,
            metadata=ContextItemMetadata(source=skill.name)
        )

        # 5. Выполняем capability через навык
        logger.debug(f"Выполнение capability '{capability.name}' через навык '{skill.name}'")
        try:
            execution_result = await skill.execute(
                capability=capability,
                parameters=validated_payload,
                context=session
            )

            # Запись наблюдения
            observation_id = session.record_observation(
                observation_data=execution_result,
                source=skill.name,
                step_number=step_number
            )

            # Примечание: регистрация шага происходит на уровне runtime,
            # чтобы обеспечить правильную нумерацию и обработку ошибок
            # session.register_step(
            #     step_number=step_number,
            #     capability_name=capability.name,
            #     skill_name=skill.name,
            #     action_item_id=action_item_id,
            #     observation_item_ids=[observation_id],
            #     summary=capability.description
            # )

            # Убедимся, что observation_item_id установлен в результате
            execution_result.observation_item_id = observation_id
            return execution_result
        except Exception as e:
            logger.error(f"Ошибка выполнения capability '{capability.name}': {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Error executing capability {capability.name}: {str(e)}",
                error="EXECUTION_ERROR"
            )