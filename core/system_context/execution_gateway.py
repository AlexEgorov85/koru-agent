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
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemMetadata, ContextItemType
from core.skills.base_skill import BaseSkill
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus

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
        system_context: Optional[BaseSystemContext] = None,
        retry_policy: Optional[RetryPolicy] = None,
        action_validator=None  # Добавляем параметр для валидации действий
    ):
        self.system_context = system_context
        self.retry_policy = retry_policy
        self.action_validator = action_validator
        logger.info("ExecutionGateway инициализирован")

    async def execute_capability(
        self,
        capability: Capability,  # Изменяем параметры на те, что используются в тестах
        action_payload: Dict[str, Any],
        session: BaseSessionContext,
        step_number: int
    ) -> ExecutionResult:
        """
        Выполнение capability через соответствующий навык.
        ПРОЦЕДУРА:
        1. Найти навык по capability
        2. Вызвать execute() навыка
        3. Вернуть результат
        ВОЗВРАЩАЕТ:
        - ExecutionResult с результатом выполнения
        ИСКЛЮЧЕНИЯ:
        - Передает все исключения вызывающему коду
        - Не обрабатывает ошибки, не логирует детали
        """

        # 1. Получаем навык для выполнения capability
        skill = self.system_context.get_resource(capability.skill_name)
        
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

        # 2. Валидируем параметры действия, если есть валидатор
        validated_payload = action_payload
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

        # 3. Записываем действие в контекст
        action_item_id = session.record_action(
            action_data=validated_payload,
            step_number=step_number,
            metadata=ContextItemMetadata(source=skill.name)
        )

        # 4. Выполняем capability через навык
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

            # Регистрируем шаг
            session.register_step(
                step_number=step_number,
                capability_name=capability.name,
                skill_name=skill.name,
                action_item_id=action_item_id,
                observation_item_ids=[observation_id],
                summary=capability.description
            )

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