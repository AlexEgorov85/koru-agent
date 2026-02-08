# application/agent/runtime.py

from typing import Any, Dict, List, Optional
from application.agent.pattern_selector import IPatternSelector
from domain.abstractions.agent import IAgent
from domain.abstractions.event_types import EventType, IEventPublisher
from domain.abstractions.gateways.i_execution_gateway import IExecutionGateway
from domain.abstractions.system.base_session_context import BaseSessionContext
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.abstractions.prompt_repository import IPromptRepository
from domain.models.agent.agent_state import AgentState
from domain.models.domain_type import DomainType

class AgentRuntime(IAgent):
    """
    ЕДИНСТВЕННЫЙ АГЕНТ системы.
    
    Архитектурный контракт:
    - СОДЕРЖИТ: мета-когницию (выбор паттерна/домена), оркестрацию жизненного цикла
    - ДЕЛЕГИРУЕТ: выполнение задачи → паттерн мышления
    - ИНТЕГРИРУЕТ: доменную адаптацию → загрузку промтов из репозитория
    """
    
    def __init__(
        self,
        session_context: BaseSessionContext,
        pattern_selector: IPatternSelector,          # выбор паттерна
        prompt_repository: IPromptRepository,        # загрузка промтов
        execution_gateway: IExecutionGateway,
        skill_registry: ISkillRegistry,
        event_publisher: IEventPublisher,
        max_steps: int = 100
    ):
        self.session_context = session_context
        self.pattern_selector = pattern_selector
        self.prompt_repository = prompt_repository
        self.execution_gateway = execution_gateway
        self.skill_registry = skill_registry
        self.event_publisher = event_publisher
        self.max_steps = max_steps
        
        self.state = AgentState()
        self._current_pattern: Optional[IThinkingPattern] = None
        self._current_domain: Optional[DomainType] = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Инициализация агента (загрузка базовых ресурсов)"""
        if self._initialized:
            return True
        
        # Загрузка базовых промтов для инициализации
        try:
            await self._load_system_prompts()
            self._initialized = True
            return True
        except Exception as e:
            await self.event_publisher.publish(
                event_type=EventType.ERROR,
                source="AgentRuntime",
                data={"error": str(e), "stage": "initialization"}
            )
            return False
    
    async def execute_task(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ЕДИНСТВЕННАЯ точка входа для пользователя.
        
        Логика выполнения:
        1. Определить домен задачи
        2. Выбрать подходящий паттерн мышления
        3. Адаптировать паттерн к домену (загрузить промты)
        4. Выполнить задачу через паттерн
        5. Вернуть результат
        """
        if not self._initialized:
            if not await self.initialize():
                return {
                    "success": False,
                    "error": "Инициализация агента не удалась"
                }
        
        # 1. Определить домен задачи
        domain = await self._determine_domain(task_description, context)
        self._current_domain = domain
        
        # 2. Выбрать паттерн мышления на основе домена и задачи
        pattern = await self.pattern_selector.select_pattern(
            task_description=task_description,
            domain=domain,
            available_patterns=self.pattern_selector.get_available_patterns()
        )
        self._current_pattern = pattern
        
        # 3. Адаптировать паттерн к домену (загрузить промты)
        await self._adapt_pattern_to_domain(pattern, domain, context)
        
        # 4. Выполнить задачу через паттерн
        try:
            result = await self._execute_with_pattern(
                pattern=pattern,
                task_description=task_description,
                context=context
            )
            return result
        except Exception as e:
            await self.event_publisher.publish(
                event_type=EventType.ERROR,
                source="AgentRuntime",
                data={
                    "error": str(e),
                    "pattern": pattern.name,
                    "domain": domain.value if domain else "unknown"
                }
            )
            return {
                "success": False,
                "error": f"Ошибка выполнения задачи: {str(e)}",
                "pattern": pattern.name,
                "domain": domain.value if domain else "unknown"
            }
    
    async def _determine_domain(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> DomainType:
        """
        Определить домен задачи на основе описания и контекста.
        Использует как ключевые слова, так и анализ через LLM при необходимости.
        """
        # Базовая эвристика по ключевым словам
        task_lower = task_description.lower()
        
        if any(kw in task_lower for kw in ["код", "code", "python", "javascript", "java", "security", "уязвимост"]):
            return DomainType.CODE_ANALYSIS
        elif any(kw in task_lower for kw in ["тест", "test", "qa", "quality"]):
            return DomainType.TESTING
        elif any(kw in task_lower for kw in ["документ", "док", "doc", "documentation"]):
            return DomainType.DOCUMENTATION
        elif any(kw in task_lower for kw in ["планирование", "план", "плана", "планиров", "plan"]):
            return DomainType.PLANNING
        else:
            # По умолчанию — общий домен
            return DomainType.GENERAL
    
    async def _adapt_pattern_to_domain(
        self,
        pattern: IThinkingPattern,
        domain: DomainType,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Адаптировать паттерн к домену:
        1. Загрузить промты из репозитория по домену/паттерну
        2. Передать промты паттерну через его метод адаптации
        """
        # Загрузка промтов для домена и паттерна
        prompts = await self.prompt_repository.get_active_prompts(
            domain=domain,
            capability=pattern.name,
            provider="openai"  # или из конфигурации
        )
        
        # Адаптация паттерна к задаче (паттерн сам решает, как использовать промты)
        adaptation_result = await pattern.adapt_to_task(
            task_description=f"Domain: {domain.value}, Pattern: {pattern.name}"
        )
        
        # Публикация события адаптации
        await self.event_publisher.publish(
            event_type=EventType.INFO,
            source="AgentRuntime",
            data={
                "event": "pattern_adapted",
                "pattern": pattern.name,
                "domain": domain.value,
                "confidence": adaptation_result.get("confidence", 0.0),
                "prompts_loaded": len(prompts)
            }
        )
    
    async def _execute_with_pattern(
        self,
        pattern: IThinkingPattern,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Выполнить задачу через паттерн мышления.
        Управляет жизненным циклом: инициализация → выполнение → завершение.
        """
        # Инициализация состояния для новой задачи
        self.state = AgentState()
        self.state.history.append(f"Task: {task_description}")

        # Основной цикл выполнения через паттерн
        iteration = 0
        while iteration < self.max_steps and not self._should_stop():
            # Выполнение одного шага паттерна
            result = await pattern.execute(
                state=self.state,
                context={
                    "goal": task_description,
                    "session_context": self.session_context,
                    **(context or {})
                },
                available_capabilities=self._get_available_capabilities()
            )

            # Публикация событий, возвращенных паттерном
            await self._publish_events_from_result(result)

            # Обновление состояния на основе результата
            self._update_state_from_result(result)

            # Проверка завершения
            if result.get("finished", False) or result.get("action") == "FINISH":
                break

            iteration += 1

        # Формирование финального результата
        return {
            "success": True,
            "pattern": pattern.name,
            "domain": self._current_domain.value if self._current_domain else "unknown",
            "iterations": iteration + 1,
            "result": self._build_final_result(),
            "history": self.state.history[-5:]  # Последние 5 шагов для отладки
        }

    async def _publish_events_from_result(self, result):
        """
        Публикация событий, возвращенных из результата выполнения паттерна.
        """
        # Проверяем, есть ли в результате события для публикации
        if hasattr(result, 'events_to_publish') and result.events_to_publish:
            for event_data in result.events_to_publish:
                try:
                    await self.event_publisher.publish(
                        event_type=event_data["event_type"],
                        source=event_data["source"],
                        data=event_data["data"]
                    )
                except Exception as e:
                    # Логируем ошибку, но не прерываем выполнение
                    await self.event_publisher.publish(
                        event_type=EventType.ERROR,
                        source="AgentRuntime",
                        data={
                            "error": f"Failed to publish event: {str(e)}",
                            "event_data": event_data
                        }
                    )
        elif isinstance(result, dict) and "events_to_publish" in result:
            # Если результат - словарь с событиями для публикации
            for event_data in result["events_to_publish"]:
                try:
                    await self.event_publisher.publish(
                        event_type=event_data["event_type"],
                        source=event_data["source"],
                        data=event_data["data"]
                    )
                except Exception as e:
                    # Логируем ошибку, но не прерываем выполнение
                    await self.event_publisher.publish(
                        event_type=EventType.ERROR,
                        source="AgentRuntime",
                        data={
                            "error": f"Failed to publish event: {str(e)}",
                            "event_data": event_data
                        }
                    )
    
    def _should_stop(self) -> bool:
        """Условия остановки выполнения"""
        return (
            self.state.finished or
            self.state.error_count >= 3 or
            self.state.no_progress_steps >= 5
        )
    
    def _get_available_capabilities(self) -> List[str]:
        """Получить доступные возможности из реестра навыков"""
        skills = self.skill_registry.get_all_skills()
        return list(skills.keys())
    
    def _update_state_from_result(self, result: Dict[str, Any]):
        """Обновить состояние агента на основе результата паттерна"""
        if result.get("error"):
            self.state.error_count += 1
            self.state.history.append(f"Error: {result['error']}")
        elif result.get("progressed", True):
            self.state.no_progress_steps = 0
            self.state.history.append(f"Progress: {result.get('observation', 'step completed')}")
        else:
            self.state.no_progress_steps += 1
        
        self.state.step += 1
        
        if result.get("finished") or result.get("action") == "FINISH":
            self.state.finished = True
    
    def _build_final_result(self) -> str:
        """Сформировать финальный результат из истории"""
        # В реальной реализации — анализ истории для генерации итога через LLM
        return "Task completed successfully" if self.state.finished else "Task partially completed"
    
    async def _load_system_prompts(self):
        """Загрузка системных промтов для инициализации"""
        # Загрузка базовых промтов для мета-когниции
        _ = await self.prompt_repository.get_active_prompts(
            domain=DomainType.GENERAL,
            capability="meta_cognition",
            provider="openai"
        )