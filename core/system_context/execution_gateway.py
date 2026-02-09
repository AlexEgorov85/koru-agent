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
        retry_policy: Optional[RetryPolicy] = None
    ):
        self.retry_policy = retry_policy
        logger.info("ExecutionGateway инициализирован")

    async def execute_capability(
        self,
        capability_name: str,
        parameters: Dict[str, Any],
        system_context: BaseSystemContext,
        session_context: BaseSessionContext
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

        # 1. Определяем навык и возможность
        capability = system_context.get_capability(capability_name)
        skill = system_context.get_resource(capability.skill_name)
        step_number = session_context.step_context.get_current_step_number() + 1


        # 2. Выполняем capability через навык
        logger.debug(f"Выполнение capability '{capability.name}' через навык '{skill.name}'")
        execution_result = await skill.execute(
            capability=capability,
            parameters=parameters,
            context=session_context
        )

        # Запись наблюдения
        observation_id = session_context.record_observation(
            execution_result,
            source=skill.name,
            step_number=step_number
        )

        execution_result.observation_item_id = observation_id

        
        return execution_result