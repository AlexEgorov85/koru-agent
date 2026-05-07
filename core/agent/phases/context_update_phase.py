"""
Фаза обновления контекста: регистрация в SessionContext и обновление состояния.

Ответственность:
- Сохранять данные наблюдения/ошибки в data_context
- Регистрировать шаг в контексте сессии
- Обновлять состояние агента сигналом наблюдения
- Обрабатывать пустые SQL-результаты с диагностикой

Эта фаза инкапсулирует всю логику мутации контекста.
Вся логика форматирования наблюдения — в ObservationPhase.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.agent.state import ObservationResult
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.session_context.model import ContextItem, ContextItemType, ContextItemMetadata


class ContextUpdatePhase:
    """Оркестрирует этап обновления контекста в цикле агента."""

    def __init__(
        self,
        log: logging.Logger,
        event_bus: Any,
        error_recovery_handler: Optional[Any] = None,
    ):
        self.log = log
        self.event_bus = event_bus
        self.error_recovery_handler = error_recovery_handler

    async def save_and_register(
        self,
        result: ExecutionResult,
        observation: Optional[ObservationResult] = None,
        decision_action: str = "",
        decision_parameters: Dict[str, Any] = {},
        session_context: Any = None,
        executed_steps: int = 0,
        error_recovery_handler: Optional[Any] = None,
        decision_reasoning_detail: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Сохранить результат выполнения в data_context и зарегистрировать шаг.

        АРГУМЕНТЫ:
            result: ExecutionResult от исполнителя
            observation: ObservationResult из ObservationPhase (Pydantic)
            decision_action: Имя действия
            decision_parameters: Параметры действия
            session_context: Контекст сессии
            executed_steps: Количество выполненных шагов
            decision_reasoning: Обоснование решения
            error_recovery_handler: Обработчик восстановления после ошибок

        ВОЗВРАЩАЕТ:
            Список ID элементов наблюдений
        """
        # Сохраняем данные результата (возвращает observation_item_ids)
        observation_item_ids = self.save_result_data(
            result=result,
            decision_action=decision_action,
            decision_parameters=decision_parameters,
            session_context=session_context,
            executed_steps=executed_steps,
            observation=observation,
        )

        # Обрабатываем пустые SQL-результаты
        if result.data in (None, {}, [], "") and error_recovery_handler:
            await self.handle_empty_sql_result(
                decision_action=decision_action,
                decision_parameters=decision_parameters,
                session_context=session_context,
                agent_state=session_context.agent_state,
                error_recovery_handler=error_recovery_handler,
            )

        # Регистрируем шаг в контексте сессии
        # Используем переменные напрямую (decision_action, decision_parameters)
        self.register_step(
            session_context=session_context,
            executed_steps=executed_steps,
            decision_action=decision_action,
            observation_item_ids=observation_item_ids,
            result_status=result.status,
            decision_parameters=decision_parameters or {},
            observation=observation,
            decision_reasoning_detail=decision_reasoning_detail,
        )

        return observation_item_ids

    def save_result_data(
        self,
        result: ExecutionResult,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        session_context: Any,
        executed_steps: int,
        observation: Optional[ObservationResult] = None,
    ) -> List[str]:
        """
        Сохранить результат выполнения в data_context.

        АРГУМЕНТЫ:
            result: ExecutionResult от исполнителя
            decision_action: Название действия
            decision_parameters: Параметры действия
            session_context: Контекст сессии
            executed_steps: Количество выполненных шагов
            observation: ObservationResult (опционально)

        ВОЗВРАЩАЕТ:
            Список ID элементов наблюдений
        """
        observation_item_ids = []
        items_count_before = (
            session_context.data_context.count()
            if hasattr(session_context, "data_context")
            else -1
        )

        if result.status == ExecutionStatus.FAILED:
            # Сохраняем наблюдение об ошибке
            error_details = {
                "error": result.error or "Неизвестная ошибка",
                "status": "FAILED",
                "capability": decision_action,
                "parameters": decision_parameters or {},
            }

            # Добавляем стек вызовов если доступен
            if hasattr(result, "traceback") and result.traceback:
                error_details["traceback"] = result.traceback[:2000]

            observation_item = ContextItem(
                item_id="",
                session_id=session_context.session_id,
                item_type=ContextItemType.OBSERVATION,
                content=result.error or "Неизвестная ошибка",
                metadata=ContextItemMetadata(
                    source=decision_action,
                    step_number=executed_steps + 1,
                    capability_name=decision_action,
                    additional_data={
                        "error_type": (
                            type(result.error).__name__
                            if result.error
                            else "Unknown"
                        ),
                    },
                ),
            )
            item_id = session_context.data_context.add_item(observation_item)
            observation_item_ids.append(item_id)

        else:
            # Сохраняем успешный результат
            observation_item = ContextItem(
                item_id="",
                session_id=session_context.session_id,
                item_type=ContextItemType.OBSERVATION,
                content=result.data,
                metadata=ContextItemMetadata(
                    source=decision_action,
                    step_number=executed_steps + 1,
                    capability_name=decision_action,
                    additional_data={
                        "truncated_warning": False,
                        "truncated_message": "",
                    },
                ),
            )
            item_id = session_context.data_context.add_item(observation_item)
            observation_item_ids.append(item_id)

        return observation_item_ids

    async def handle_empty_sql_result(
        self,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        session_context: Any,
        agent_state: Any,
        error_recovery_handler: Any,
    ) -> None:
        """
        Обработать пустой SQL-результат с диагностикой.
        """
        # Получаем таблицы из параметров SQL-запроса
        tables = []
        if "sql_query" in decision_parameters:
            sql = decision_parameters["sql_query"]
            # Простое извлечение имён таблиц из SQL
            import re
            table_matches = re.findall(r'FROM\s+(\w+\.\w+|\w+)', sql, re.IGNORECASE)
            tables = [m.split('.')[-1] for m in table_matches]

        columns_used = []
        if isinstance(result_data := getattr(session_context, '_last_result_data', None), dict):
            if "rows" in result_data and result_data["rows"]:
                columns_used = list(result_data["rows"][0].keys())[:10]

        session_context.record_empty_result(
            tool=decision_action,
            tables=tables,
            filters=decision_parameters,
            columns_used=columns_used,
        )

        # Запускаем диагностику если есть обработчик
        if error_recovery_handler and hasattr(error_recovery_handler, 'handle_empty_result'):
            await error_recovery_handler.handle_empty_result(
                session_context=session_context,
                sql_query=decision_parameters.get("sql_query", ""),
                tables=tables,
            )

    def register_step(
        self,
        session_context: Any,
        executed_steps: int,
        decision_action: str,
        observation_item_ids: List[str],
        result_status: ExecutionStatus,
        decision_parameters: Dict[str, Any],
        observation: Optional[ObservationResult] = None,
        decision_reasoning_detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Зарегистрировать шаг в контексте сессии и обновить состояние агента.

        АРХИТЕКТУРНОЕ ПРАВИЛО:
        ⚠️ Данные хранятся ТОЛЬКО в data_context!
        ⚠️ observation_item_ids содержит ссылки на ContextItem с данными

        АРГУМЕНТЫ:
            session_context: Контекст сессии для обновления
            executed_steps: Количество выполненных шагов
            decision_action: Название действия
            observation_item_ids: ID элементов наблюдений
            result_status: Статус выполнения
            decision_parameters: Параметры действия
            observation: ObservationResult из ObservationPhase
            decision_reasoning_detail: Полное структурированное рассуждение (10 полей)
        """
        # Извлекаем краткое текстовое наблюдение для отображения в истории шагов
        obs_text = ""
        if observation:
            obs_text = observation.observation or ""
        
        # Регистрируем шаг (данные хранятся в data_context, шаг содержит только ссылки)
        # Используем executed_steps + 1 для синхронизации с observation_phase
        session_context.register_step(
            step_number=executed_steps + 1,
            capability_name=decision_action or "unknown",
            skill_name=(decision_action or "unknown").split(".")[0],
            action_item_id="",
            observation_item_ids=observation_item_ids,
            status=result_status,
            parameters=decision_parameters or {},
            obs_text=obs_text,
            reasoning_detail=decision_reasoning_detail,
        )
        
        # Обновляем состояние агента наблюдением (напрямую ObservationResult)
        if observation:
            session_context.agent_state.add_step(
                action_name=decision_action or "unknown",
                status=result_status.value if hasattr(result_status, 'value') else str(result_status),
                parameters=decision_parameters or {},
                observation=observation,
            )
            session_context.agent_state.register_observation(observation)
            session_context.agent_state.push_observation(observation)

    def save_observation_analysis(
        self,
        session_context: Any,
        observation_data: ObservationResult,
        action_name: str,
        step_number: int,
    ) -> None:
        """
        Сохранить результат анализа наблюдения в историю AgentState.

        АРХИТЕКТУРА:
        - Использует push_observation для сохранения
        """
        session_context.agent_state.push_observation(observation_data)

    def get_truncation_warning(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: Any,
    ) -> Optional[str]:
        """
        Проверяет, не обрезаны ли результаты из-за лимита.

        Если количество результатов >= лимиту (top_k, limit, max_results),
        возвращает предупреждение.
        """
        # Ищем лимит в параметрах (учитываем что значение может быть строкой)
        limit = None
        for key in ['top_k', 'limit', 'max_results', 'max_rows', 'n_results']:
            if key in parameters:
                try:
                    limit = int(parameters[key])  # int() корректно преобразует строку '5' в 5
                    break
                except (ValueError, TypeError):
                    pass

        if limit is None or limit <= 0:
            return None

        # Считаем количество результатов
        count = 0
        if isinstance(result, list):
            count = len(result)
        elif isinstance(result, dict):
            if 'rows' in result and isinstance(result['rows'], list):
                count = len(result['rows'])
            elif 'results' in result and isinstance(result['results'], list):
                count = len(result['results'])
            elif 'data' in result and isinstance(result['data'], list):
                count = len(result['data'])
            elif 'result' in result and isinstance(result['result'], list):
                count = len(result['result'])

        # КРИТИЧНО: если count == limit, результаты могли быть обрезаны!
        if count > 0 and count >= limit:
            new_limit = limit + 10 if limit < 100 else 0
            return (
                f"[ПРЕДУПРЕЖДЕНИЕ ОБ ОБРЕЗАНИИ] Получено результатов ({count}) >= лимиту ({limit}). "
                f"Возможно, данные обрезаны. Для полных данных увеличьте top_k={new_limit} или 0 для безлимитно. "
                f"Или используйте data_analysis.analyze_step_data."
            )
        return None

    def should_call_llm(self, result: Any, error: Optional[str], status: Optional[str] = None) -> bool:
        """
        Определение необходимости вызова LLM на основе trigger_mode.

        ПАРАМЕТРЫ:
            result: результат выполнения
            error: ошибка (если есть)
            status: статус выполнения (если известен заранее)

        ВОЗВРАЩАЕТ:
            True если нужно вызвать LLM, False для rule-based fallback
        """
        # Определяем статус если не передан
        if status is None:
            if error:
                status = "error"
            elif result is None or (isinstance(result, (list, dict)) and len(result) == 0):
                status = "empty"
            else:
                status = "success"

        # Режимы trigger_mode
        trigger_mode = "always"  # Default, can be configured
        if trigger_mode == "always":
            return True
        elif trigger_mode == "on_error":
            return status in ("error", "empty")
        elif trigger_mode == "on_empty":
            return status == "empty"

        return True
