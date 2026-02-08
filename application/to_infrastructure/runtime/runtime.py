"""
Чистый рантайм агента - только оркестрация.
"""
import asyncio
from typing import Optional, List, Dict, Any
from domain.abstractions.event_types import IEventPublisher, EventType
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.abstractions.system.base_session_context import BaseSessionContext
from domain.abstractions.gateways.i_execution_gateway import IExecutionGateway
from domain.models.agent.agent_state import AgentState
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus
from application.agent.pattern_state_manager import PatternStateManager


class AgentRuntime:
    """
    ЧИСТЫЙ ОРКЕСТРАТОР — только управление жизненным циклом и состоянием.
    
    АРХИТЕКТУРНЫЙ КОНТРАКТ:
    - СОДЕРЖИТ: состояние агента, управление шагами, координация выполнения
    - НЕ СОДЕРЖИТ: логику принятия решений (делегирует паттерну мышления)
    - НЕ СОДЕРЖИТ: прямой доступ к реестрам (только через порты)
    - ТЕРМИНОЛОГИЯ: 'паттерн мышления' вместо 'стратегия' во всём коде
    """
    
    def __init__(
        self,
        session_context: BaseSessionContext,          # ← координационная точка
        thinking_pattern: IThinkingPattern,        # ← ПОРТ паттерна мышления (было 'strategy')
        pattern_executor,                           # ← НОВЫЙ ПОРТ для выполнения рассуждений
        execution_gateway: IExecutionGateway,      # ← ПОРТ шлюза
        event_publisher: IEventPublisher,          # ← ПОРТ шины
        policy: Optional[Dict[str, Any]] = None,
        max_steps: int = 10
    ):
        self.session = session_context
        self.thinking_pattern = thinking_pattern   # ← переименовано из 'strategy'
        self.pattern_executor = pattern_executor   # ← НОВЫЙ порт для рассуждений
        self.execution_gateway = execution_gateway
        self.event_publisher = event_publisher
        self.policy = policy or {}
        self.max_steps = max_steps
        self.state = AgentState()
        self._initialized = False
        self._pattern_state_manager = PatternStateManager()
        self._current_pattern_state_id: Optional[str] = None
        self.recovery_manager = None  # Will be set via setter or dependency injection
    
    def set_recovery_manager(self, recovery_manager):
        """Setter for recovery manager dependency injection."""
        self.recovery_manager = recovery_manager
    
    async def initialize(self) -> bool:
        """Инициализация агента перед выполнением."""
        if self._initialized:
            return True
        
        # 1. Валидация доступных возможностей
        available = await self.execution_gateway.get_available_capabilities()
        if not available:
            await self.event_publisher.publish(
                event_type=EventType.WARNING,
                source="AgentRuntime",
                data={"message": "Нет доступных возможностей для выполнения задачи"}
            )
            return False
        
        # 2. Создание состояния для текущего паттерна мышления
        self._current_pattern_state_id = self._pattern_state_manager.create_state(
            pattern_name=self.thinking_pattern.name,
            pattern_description=f"Начало выполнения паттерна мышления: {self.thinking_pattern.name}"
        ).id
        
        self._initialized = True
        await self.event_publisher.publish(
            event_type=EventType.INFO,
            source="AgentRuntime",
            data={
                "session_id": getattr(self.session, 'session_id', 'unknown'),
                "max_steps": self.max_steps,
                "thinking_pattern": self.thinking_pattern.name  # ← правильная терминология
            }
        )
        return True
    
    async def run(self, goal: str) -> ExecutionResult:
        """Главный цикл выполнения — ЧИСТАЯ ОРКЕСТРАЦИЯ."""
        if not self._initialized:
            if not await self.initialize():
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result="Инициализация не удалась",
                    observation_item_id="initialization_failure",
                    summary="Инициализация агента не удалась"
                )
        
        # Устанавливаем цель в сессию
        if hasattr(self.session, 'set_session_data'):
            self.session.set_session_data('goal', goal)
        
        # Адаптируем паттерн мышления к задаче
        adaptation = await self.thinking_pattern.adapt_to_task(goal)
        await self.event_publisher.publish(
            event_type=EventType.INFO,
            source="AgentRuntime",
            data={
                "pattern_name": self.thinking_pattern.name,
                "domain": adaptation.get("domain", "unknown"),
                "confidence": adaptation.get("confidence", 0.0)
            }
        )
        
        try:
            # Основной цикл: выполнение паттерна мышления
            while not self._should_stop():
                # 1. ВЫПОЛНЕНИЕ ПАТТЕРНА МЫШЛЕНИЯ (сначала без LLM ответа)
                result = await self.thinking_pattern.execute(
                    state=self.state,
                    context=self.session,
                    available_capabilities=await self.execution_gateway.get_available_capabilities(),
                    llm_response=None  # ← Сначала без ответа от LLM
                )

                # 2. Если требуется рассуждение — оркестратор вызывает порт
                if result.get("requires_reasoning", False):
                    start_time = asyncio.get_event_loop().time()
                    
                    # ЕДИНСТВЕННЫЙ вызов инфраструктуры из оркестратора
                    llm_response = await self.pattern_executor.execute_thinking(
                        pattern_name=self.thinking_pattern.name,
                        session_id=getattr(self.session, 'session_id', 'unknown'),
                        context=await self._build_reasoning_context(result)
                    )
                    
                    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    # → ПУБЛИКАЦИЯ СОБЫТИЯ РАССУЖДЕНИЯ (правильное место!)
                    await self.event_publisher.publish(
                        event_type=EventType.INFO,  # ← Используй существующий тип события
                        source="AgentRuntime",  # ← ИСТОЧНИК: оркестратор, НЕ паттерн!
                        data={
                            "session_id": getattr(self.session, 'session_id', 'unknown'),
                            "pattern": self.thinking_pattern.name,
                            "duration_ms": duration_ms,
                            "tokens_used": getattr(llm_response, "tokens_used", 0),
                            "generation_time": getattr(llm_response, "generation_time", 0.0),
                            "confidence": getattr(llm_response, "confidence", 0.0)
                            # ← ЧУВСТВИТЕЛЬНЫЕ ДАННЫЕ АВТОМАТИЧЕСКИ САНИТИЗИРУЮТСЯ В АДАПТЕРЕ ШИНЫ
                        }
                    )
                    
                    # 3. Передаем СУЩЕСТВУЮЩИЙ LLMResponse обратно паттерну
                    result = await self.thinking_pattern.execute(
                        state=self.state,
                        context=self.session,
                        available_capabilities=await self.execution_gateway.get_available_capabilities(),
                        llm_response=llm_response  # ← Не создаем новые модели!
                    )
                
                # 2. ВАЛИДАЦИЯ: проверка результата политикой
                if not await self._validate_result(result):
                    await self.event_publisher.publish(
                        event_type=EventType.WARNING,
                        source="AgentRuntime",
                        data={
                            "result": result.get('action', 'unknown'),
                            "reason": "Политика отклонила результат"
                        }
                    )
                    self.state.register_error()
                    continue
                
                # 3. ВЫПОЛНЕНИЕ: оркестрация действия (КАК делать)
                execution_result = await self._execute_result(result)
                
                # 4. НАБЛЮДЕНИЕ: обновление состояния
                await self._observe_result(execution_result)
                
                # 5. ПРОГРЕС: оценка продвижения
                progressed = await self._evaluate_progress()
                self.state.register_progress(progressed)
                
                # 6. УВЕЛИЧЕНИЕ ШАГА: важно увеличивать шаг на каждой итерации
                self.state.step += 1
                
                # 7. СОБЫТИЯ: публикация прогресса
                await self.event_publisher.publish(
                    event_type=EventType.INFO,
                    source="AgentRuntime",
                    data={
                        "step": self.state.step,
                        "pattern": self.thinking_pattern.name,  # ← правильная терминология
                        "result": result.get('action', 'unknown'),
                        "progressed": progressed
                    }
                )
            
            return await self._finalize_execution()
        
        except Exception as e:
            # Обработка критической ошибки с возможностью восстановления
            await self.event_publisher.publish(
                event_type=EventType.ERROR,
                source="AgentRuntime",
                data={
                    "message": f"Критическая ошибка в агенте: {str(e)}",
                    "step": self.state.step,
                    "pattern": self.thinking_pattern.name  # ← правильная терминология
                }
            )
            
            # Попробуем восстановиться через recovery manager, если он доступен
            if self.recovery_manager:
                try:
                    recovery_success = await self._handle_critical_error(str(e), self.thinking_pattern.name)
                    if recovery_success:
                        # Если восстановление прошло успешно, возвращаем результат без рекурсивного вызова
                        # чтобы избежать бесконечной рекурсии
                        return ExecutionResult(
                            status=ExecutionStatus.SUCCESS,
                            result=f"Восстановление после ошибки: {str(e)}",
                            observation_item_id="recovery_observation",
                            summary=f"Успешное восстановление после ошибки: {str(e)}"
                        )
                except Exception as recovery_error:
                    await self.event_publisher.publish(
                        event_type=EventType.ERROR,
                        source="AgentRuntime",
                        data={
                            "message": f"Ошибка при попытке восстановления: {str(recovery_error)}",
                            "original_error": str(e)
                        }
                    )
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=f"Критическая ошибка: {str(e)}",
                observation_item_id="error_observation",
                summary=f"Ошибка выполнения: {str(e)}"
            )

    async def _handle_critical_error(self, error: str, current_pattern: str) -> bool:
        """Обработка критической ошибки с восстановлением."""
        if self.recovery_manager:
            # Попробуем восстановиться через механизм восстановления
            return await self.recovery_manager.fallback_to_safe_pattern(self, current_pattern)
        return False
    
    async def shutdown(self) -> None:
        """Корректное завершение работы агента."""
        if not self._initialized:
            return
        
        # 1. Завершение состояния текущего паттерна
        if self._current_pattern_state_id:
            self._pattern_state_manager.complete(self._current_pattern_state_id)
        
        # 2. Публикация события завершения
        await self.event_publisher.publish(
            event_type=EventType.INFO,
            source="AgentRuntime",
            data={
                "session_id": getattr(self.session, 'session_id', 'unknown'),
                "final_state": self.state.model_dump() if hasattr(self.state, 'model_dump') else {},
                "final_pattern": self.thinking_pattern.name  # ← правильная терминология
            }
        )
        
        self._initialized = False
    
    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ (приватные) ===
    def _should_stop(self) -> bool:
        """Проверка условий остановки по политике."""
        return (
            self.state.step >= self.max_steps or
            self.state.no_progress_steps >= 3 or  # Ограничение по бездействию
            self.state.finished
        )
    
    async def _execute_result(self, result: Dict[str, Any]) -> ExecutionResult:
        """Оркестрация выполнения результата через шлюз."""
        # В реальной реализации выполнение через шлюз
        # Вызов нужного навыка/инструмента через execution_gateway
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result="Выполнено",
            observation_item_id="default_observation",
            summary="Результат успешно выполнен"
        )
    
    async def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Валидация результата политикой."""
        # Проверка на допустимость действия
        action = result.get('action', '')
        return action in ['EXECUTE_PATTERN', 'THINK', 'OBSERVE', 'CONTINUE']
    
    async def _observe_result(self, result: ExecutionResult) -> None:
        """Наблюдение за результатом выполнения."""
        # Обновление состояния на основе результата
        if result.status == ExecutionStatus.FAILED:
            self.state.register_error()
        else:
            self.state.register_progress(True)
    
    async def _evaluate_progress(self) -> bool:
        """Оценка прогресса выполнения."""
        # В реальной реализации анализ прогресса
        return True
    
    async def _build_reasoning_context(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Построить контекст для рассуждения."""
        return {
            "goal": getattr(self.session, 'goal', ''),
            "current_state": self.state.model_dump() if hasattr(self.state, 'model_dump') else {},
            "available_capabilities": await self.execution_gateway.get_available_capabilities(),
            "reason": decision.get("reason", ""),
            "history": self.state.history[-5:],  # последние 5 шагов
            "max_tokens": 500,
            "temperature": 0.7
        }

    async def _finalize_execution(self) -> ExecutionResult:
        """Финализация выполнения задачи."""
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result="Задача выполнена успешно",
            observation_item_id="final_observation",
            summary="Выполнение задачи завершено успешно",
            execution_time=0.0
        )