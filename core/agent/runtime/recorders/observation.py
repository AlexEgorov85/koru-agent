"""
Рекордеры для записи наблюдений агента.
"""
from typing import Protocol, runtime_checkable

from core.session_context.session_context import SessionContext
from core.models.data.execution import ExecutionResult
from core.agent.behaviors.base import Decision


@runtime_checkable
class IObservationRecorder(Protocol):
    """
    Протокол рекордера для записи наблюдений.
    
    Отвечает за пост-обработку результата выполнения:
    - Сохранение в data_context
    - Обновление step_context
    - Обновление agent_state
    - Анализ через Observer
    - Обновление метрик
    
    Изолирован от pattern, policy и executor.
    """
    
    async def record(
        self,
        result: ExecutionResult,
        decision: Decision,
        context: SessionContext
    ) -> None:
        """
        Записать результат выполнения шага.
        
        Args:
            result: Результат выполнения действия
            decision: Решение которое привело к выполнению
            context: Контекст сессии для обновления состояния
        """
        ...


class DefaultObservationRecorder:
    """
    Рекордер наблюдений по умолчанию.
    
    Выполняет полную пост-обработку результата:
    1. Создаёт ContextItem (OBSERVATION или ERROR_LOG)
    2. Добавляет в data_context
    3. Регистрирует шаг в step_context
    4. Обновляет agent_state
    5. Вызывает Observer.analyze()
    6. Обновляет AgentMetrics
    """
    
    def __init__(self, observer=None, metrics=None):
        """
        Инициализировать рекордер.
        
        Args:
            observer: Компонент Observer для анализа результатов
            metrics: Компонент AgentMetrics для обновления статистики
        """
        self.observer = observer
        self.metrics = metrics
    
    async def record(
        self,
        result: ExecutionResult,
        decision: Decision,
        context: SessionContext
    ) -> None:
        """
        Записать результат выполнения шага.
        
        Создаёт observation/error_log item, обновляет контексты и метрики.
        """
        from core.infrastructure.logging.event_types import LogEventType
        from core.session_context.model import ContextItem, ContextItemType, ContextItemMetadata
        import logging
        
        log = logging.getLogger(__name__)
        
        # Определяем тип элемента и создаём observation
        observation_item_ids = []
        
        if result.status.value == "failed":
            # Создаём ERROR_LOG при ошибке
            error_details = {
                "error": result.error or "Неизвестная ошибка",
                "status": "FAILED",
                "capability": decision.action,
                "parameters": decision.parameters or {},
            }
            
            # Добавляем stack trace если есть
            if hasattr(result, "traceback") and result.traceback:
                error_details["traceback"] = result.traceback[:2000]
            
            observation_item = ContextItem(
                item_id="",
                session_id=context.session_id,
                item_type=ContextItemType.ERROR_LOG,
                content=error_details,
                quick_content=f"❌ {result.error or 'Неизвестная ошибка'}"[:200],
                metadata=ContextItemMetadata(
                    source=decision.action,
                    step_number=context.step_context.count() + 1,
                    capability_name=decision.action,
                    additional_data={
                        "is_error": True,
                        "error_type": type(result.error).__name__ if result.error else "Unknown",
                    },
                ),
            )
            
            observation_item_id = context.data_context.add_item(observation_item)
            observation_item_ids = [observation_item_id]
            
            log.info(
                f"📝 Сохранена ошибка: item_id={observation_item_id}",
                extra={"event_type": LogEventType.STEP_COMPLETED}
            )
            
        elif result.data is not None:
            # Создаём OBSERVATION при успешном результате
            from core.agent.observation_formatter import format_observation, smart_format_observation
            
            # Проверяем, нужно ли использовать smart_format или полный формат
            is_data_analysis = decision.action and "data_analysis" in decision.action
            
            if is_data_analysis:
                # Для data_analysis - используем полный формат
                quick_content = format_observation(
                    result_data=result.data,
                    capability_name=decision.action,
                    parameters=decision.parameters,
                )
            else:
                # Для остальных - smart_format с усечением
                quick_content = smart_format_observation(
                    result_data=result.data,
                    capability_name=decision.action,
                    parameters=decision.parameters,
                )
            
            observation_item = ContextItem(
                item_id="",
                session_id=context.session_id,
                item_type=ContextItemType.OBSERVATION,
                content=result.data,
                quick_content=quick_content,
                metadata=ContextItemMetadata(
                    source=decision.action,
                    step_number=context.step_context.count() + 1,
                    capability_name=decision.action,
                    additional_data=None,
                ),
            )
            
            observation_item_id = context.data_context.add_item(observation_item)
            observation_item_ids = [observation_item_id]
            
            log.debug(
                f"📝 Сохранено observation: item_id={observation_item_id}",
                extra={"event_type": LogEventType.STEP_COMPLETED}
            )
            
            # Логируем наблюдение в формате промта
            if quick_content:
                log.info(
                    f"[OBSERVATION] step={context.step_context.count()} | capability={decision.action}\n{quick_content}",
                    extra={"event_type": LogEventType.STEP_COMPLETED}
                )
        
        # Получаем доступ к event_bus через application_context если есть
        event_bus = None
        if hasattr(context, 'application_context') and context.application_context:
            event_bus = context.application_context.infrastructure_context.event_bus
        
        # Observer анализирует результат
        if self.observer:
            log.info(
                f"👁️ Observer.analyze({decision.action})...",
                extra={"event_type": LogEventType.INFO}
            )
            
            observation = await self.observer.analyze(
                action_name=decision.action,
                parameters=decision.parameters or {},
                result=result.data if hasattr(result, 'data') else result,
                error=result.error if result.status.value == "failed" else None,
                session_id=context.session_id,
                agent_id=context.agent_id if hasattr(context, 'agent_id') else "unknown",
                step_number=context.step_context.count() + 1
            )
            
            # Публикуем событие OBSERVATION
            if event_bus:
                from core.infrastructure.event_bus.unified_event_bus import EventType
                await event_bus.publish(
                    EventType.DEBUG,
                    {"event": "OBSERVATION", "status": observation.get("status"), "quality": observation.get("data_quality")},
                    session_id=context.session_id,
                    agent_id=context.agent_id if hasattr(context, 'agent_id') else "unknown"
                )
            
            # Обновляем метрики на основе наблюдения
            if self.metrics:
                status = observation.get("status", "unknown")
                self.metrics.add_step(
                    action_name=decision.action,
                    status=status,
                    error=observation.get("errors", [None])[0] if observation.get("errors") else None
                )
                self.metrics.update_observation(observation)
                
                # Логируем результат наблюдения
                log.info(
                    f"📊 Observation: status={status}, quality={observation.get('data_quality', {})}",
                    extra={"event_type": LogEventType.INFO}
                )
                
                # Проверяем рекомендации Observer для следующего шага
                if observation.get("requires_additional_action") and status in ["empty", "error"]:
                    log.warning(
                        f"⚠️ Observer рекомендует сменить стратегию: {observation.get('next_step_suggestion', '')}",
                        extra={"event_type": LogEventType.INFO}
                    )
        else:
            # Если нет observer, создаём базовое observation
            observation = {
                "status": "success" if result.status.value != "failed" else "error",
                "data_quality": "high" if result.data else "low",
                "errors": [result.error] if result.error else [],
            }
        
        # Регистрируем шаг в step_context
        from core.models.enums.common_enums import ExecutionStatus
        context.register_step(
            step_number=context.step_context.count() + 1,
            capability_name=decision.action or "unknown",
            skill_name=(decision.action or "unknown").split(".")[0] if decision.action else "unknown",
            action_item_id="",
            observation_item_ids=observation_item_ids,
            summary=decision.reasoning,
            status=result.status,
            parameters=decision.parameters or {},
        )
        
        # Обновляем agent_state
        if hasattr(context, 'agent_state'):
            # Создаём observation signal
            observation_signal = self._build_observation_signal(result, decision.action, decision.parameters or {})
            context.agent_state.add_step(
                action_name=decision.action or "unknown",
                status=result.status.value,
                parameters=decision.parameters or {},
                observation=observation_signal,
            )
            context.agent_state.register_observation(observation_signal)
            
            # Публикуем события
            if event_bus:
                from core.infrastructure.event_bus.unified_event_bus import EventType
                await event_bus.publish(
                    EventType.SESSION_STEP,
                    {
                        "step": context.step_context.count(),
                        "action": decision.action,
                        "status": result.status.value,
                    },
                    session_id=context.session_id,
                    agent_id=context.agent_id if hasattr(context, 'agent_id') else "unknown"
                )
                await event_bus.publish(
                    EventType.TOOL_RESULT,
                    {
                        "step": context.step_context.count(),
                        "action": decision.action,
                        "observation": observation_signal,
                    },
                    session_id=context.session_id,
                    agent_id=context.agent_id if hasattr(context, 'agent_id') else "unknown"
                )
    
    def _build_observation_signal(
        self,
        result: ExecutionResult,
        action_name: str | None = None,
        parameters: dict | None = None,
    ) -> dict:
        """Построить observation-сигнал из результата выполнения."""
        if result.status.value == "failed":
            return {
                "status": "error",
                "quality": "low",
                "issues": [result.error or "unknown_error"],
                "insight": result.error or "Ошибка выполнения действия",
                "next_step_hint": "Измени стратегию и выбери альтернативное действие",
            }
        
        if result.data in (None, {}, [], ""):
            hint = "Уточни параметры или выбери другой инструмент"
            issues = ["empty_result"]
            
            # Проверяем SQL actions
            if self._is_sql_action(action_name):
                sql_analysis = self._analyze_sql_empty_result(parameters)
                issues.extend(sql_analysis.get("issues", []))
                hint = sql_analysis.get("next_step_hint", hint)
            
            return {
                "status": "empty",
                "quality": "useless",
                "issues": issues,
                "insight": "Действие завершилось без полезных данных",
                "next_step_hint": hint,
            }
        
        return {
            "status": "success",
            "quality": "high",
            "issues": [],
            "insight": "Получен полезный результат",
            "next_step_hint": "Продолжай по текущему плану",
        }
    
    def _is_sql_action(self, action_name: str | None) -> bool:
        """Проверить, является ли действие SQL-запросом."""
        if not action_name:
            return False
        sql_keywords = ["sql", "query", "select", "database"]
        return any(keyword in action_name.lower() for keyword in sql_keywords)
    
    def _analyze_sql_empty_result(self, parameters: dict | None) -> dict:
        """Анализировать пустой результат SQL-запроса."""
        return {
            "issues": ["empty_sql_result"],
            "next_step_hint": "Проверь условия запроса или попробуй другую выборку",
        }
