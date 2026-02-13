"""
Основной класс выполнения агента - runtime цикл рассуждений.

СОДЕРЖИТ:
- Цикл рассуждений (reasoning loop)
- Управление стратегией выполнения
- Обработку действий и результатов
- Интеграцию с инфраструктурными сервисами
"""
import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from core.application.context.application_context import ApplicationContext
from core.execution.gateway import ExecutionGateway
from core.session.step_context import StepContext
from core.models.execution import ExecutionResult, ExecutionStatus


class AgentRuntime:
    """Основной класс выполнения агента - runtime цикл рассуждений."""

    def __init__(self, application_context: ApplicationContext, goal: str):
        """
        Инициализация runtime агента.

        ПАРАМЕТРЫ:
        - application_context: Прикладной контекст агента
        - goal: Цель выполнения агента
        """
        self.application_context = application_context
        self.goal = goal
        self._running = False
        self._current_step = 0
        self._max_steps = 50  # по умолчанию
        self._result: Optional[ExecutionResult] = None

        # Шлюз выполнения для координации действий
        self.execution_gateway = ExecutionGateway(application_context)

        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def run(self, max_steps: Optional[int] = None) -> ExecutionResult:
        """
        Запуск выполнения агента.

        ПАРАМЕТРЫ:
        - max_steps: Максимальное количество шагов (опционально)

        ВОЗВРАЩАЕТ:
        - ExecutionResult: Результат выполнения
        """
        if self._running:
            raise RuntimeError("Агент уже выполняется")

        self._running = True
        self._current_step = 0
        self._max_steps = max_steps or self._max_steps

        self.logger.info(f"Запуск агента с целью: {self.goal[:100]}...")

        try:
            # Инициализация начального контекста выполнения
            initial_context = self.application_context.step_context
            if initial_context:
                initial_context.add_step({
                    "step": 0,
                    "action": "initialization",
                    "timestamp": datetime.now().isoformat(),
                    "goal": self.goal
                })

            # Цикл рассуждений
            while self._running and self._current_step < self._max_steps:
                step_result = await self._execute_single_step()
                
                # Проверка завершения
                if self._is_final_result(step_result):
                    self.logger.info(f"Агент завершил выполнение на шаге {self._current_step}")
                    break
                
                self._current_step += 1

            # Формирование результата
            self._result = ExecutionResult(
                status=ExecutionStatus.COMPLETED if self._current_step < self._max_steps else ExecutionStatus.TOO_MANY_STEPS,
                result=self._extract_final_result(),
                steps_executed=self._current_step,
                execution_time=datetime.now().timestamp(),
                metadata={
                    "goal": self.goal,
                    "max_steps": self._max_steps
                }
            )

        except Exception as e:
            self.logger.error(f"Ошибка выполнения агента: {str(e)}")
            self._result = ExecutionResult(
                status=ExecutionStatus.ERROR,
                result=str(e),
                steps_executed=self._current_step,
                execution_time=datetime.now().timestamp(),
                metadata={
                    "error": str(e),
                    "goal": self.goal
                }
            )
        finally:
            self._running = False

        return self._result

    async def _execute_single_step(self) -> Any:
        """Выполнение одного шага рассуждений."""
        self.logger.debug(f"Выполнение шага {self._current_step + 1}")

        # Здесь должна быть реализация стратегии выполнения
        # В зависимости от текущего состояния выбирается следующее действие
        # и выполняется через execution_gateway

        # Пока что просто возвращаем заглушку
        # В реальной реализации здесь будет вызов LLM для принятия решения
        # о следующем действии
        next_action = await self._decide_next_action()

        if next_action:
            # Выполнение действия через шлюз выполнения
            execution_result = await self.execution_gateway.execute(next_action)
            
            # Обновление контекста выполнения
            if self.application_context.step_context:
                self.application_context.step_context.add_step({
                    "step": self._current_step + 1,
                    "action": next_action,
                    "result": execution_result,
                    "timestamp": datetime.now().isoformat()
                })
            
            return execution_result

        return None

    async def _decide_next_action(self) -> Optional[Dict[str, Any]]:
        """Принятие решения о следующем действии."""
        # В реальной реализации здесь будет вызов LLM для планирования
        # или принятия решения о следующем действии
        # Пока что возвращаем заглушку
        return {
            "action_type": "continue",
            "description": "Продолжить выполнение задачи"
        }

    def _is_final_result(self, step_result: Any) -> bool:
        """Проверка, является ли результат финальным."""
        # В реальной реализации здесь будет проверка на достижение цели
        # или получение финального ответа
        if isinstance(step_result, dict) and step_result.get("action_type") == "final_answer":
            return True
        return False

    def _extract_final_result(self) -> Any:
        """Извлечение финального результата."""
        # В реальной реализации здесь будет извлечение результата
        # из контекста выполнения или последнего шага
        return {
            "final_goal": self.goal,
            "steps_completed": self._current_step,
            "summary": "Execution completed successfully"
        }

    async def stop(self):
        """Остановка выполнения агента."""
        self._running = False
        self.logger.info("Агент остановлен пользователем")

    def is_running(self) -> bool:
        """Проверка, выполняется ли агент."""
        return self._running