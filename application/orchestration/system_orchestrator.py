"""
SystemOrchestrator - единая точка инициализации системы.

АРХИТЕКТУРА:
- Pattern: Orchestrator/Facade
- Инкапсулирует сложность инициализации и координации системных компонентов
- Предоставляет единую точку доступа к общей инфраструктуре системы
"""
from typing import Optional
from domain.models.system.config import SystemConfig
from application.context.system.system_context import SystemContext
from domain.abstractions.event_types import IEventPublisher
from domain.abstractions.event_factory import IEventPublisherFactory
from application.gateways.execution.execution_gateway import ExecutionGateway
from application.context.session.session_context import SessionContext
from domain.abstractions.prompt_repository import IPromptRepository, ISnapshotManager


class SystemOrchestrator:
    """
    Оркестратор системы - управляет инициализацией и координацией системных компонентов.
    
    ОТВЕТСТВЕННОСТЬ:
    - Инициализация системного контекста (только реестры)
    - Управление общей шиной событий (один экземпляр на систему)
    - Создание сессионных контекстов с корректной инъекцией зависимостей
    - Управление шлюзами выполнения (один на сессию)
    """
    
    def __init__(self,
                 config: Optional[SystemConfig] = None,
                 event_publisher: Optional[IEventPublisher] = None,
                 event_publisher_factory: Optional[IEventPublisherFactory] = None,
                 prompt_repository: Optional[IPromptRepository] = None,
                 snapshot_manager: Optional[ISnapshotManager] = None):
        """
        Инициализация оркестратора системы.

        ПАРАМЕТРЫ:
        - config: Конфигурация приложения (опционально)
        - event_publisher: Издатель событий (опционально, если не указан, будет использован глобальный)
        - prompt_repository: Репозиторий промтов (опционально)
        - snapshot_manager: Менеджер снапшотов (опционально)
        """
        # Создаем чистый системный контекст (только реестры)
        self.system_context = SystemContext(config)

        # Используем переданного издателя событий или создаем глобальный через фабрику
        if event_publisher:
            self.event_system = event_publisher
        elif event_publisher_factory:
            self.event_system = event_publisher_factory.get_global_event_publisher()
        else:
            # В идеале, здесь должен быть способ получения глобального издателя событий
            # через фабрику, но мы не можем импортировать инфраструктуру напрямую
            # Поэтому оставим как есть, но отметим, что это место требует архитектурного решения
            # В продакшене это должно быть решено через DI-контейнер
            self.event_system = None  # будет установлен позже через DI

        # Компоненты управления промтами и снапшотами
        self.prompt_repository = prompt_repository
        self.snapshot_manager = snapshot_manager

        # Агент фабрика будет создаваться при необходимости
        self._agent_factory = None
    
    @property
    def agent_factory(self):
        """Ленивая инициализация фабрики агентов."""
        if self._agent_factory is None:
            from application.factories.agent_factory import AgentFactory
            self._agent_factory = AgentFactory(
                system_context=self.system_context,
                event_publisher=self.event_system
            )
        return self._agent_factory
    
    async def create_session(self, session_id: str) -> SessionContext:
        """
        Создание сессионного контекста с корректной инъекцией зависимостей.
        
        ПАРАМЕТРЫ:
        - session_id: Уникальный идентификатор сессии
        
        ВОЗВРАЩАЕТ:
        - SessionContext с инъекцией зависимостей через координацию
        """
        # Создаем сессионный шлюз с доступом к общим компонентам
        execution_gateway = ExecutionGateway(
            skill_registry=self.system_context.skill_registry,
            prompt_repository=self.prompt_repository,  # Используем репозиторий промтов из оркестратора
            event_publisher=self.event_system
        )
        
        # Создаем сессионный контекст
        session_context = SessionContext(session_id=session_id)
        
        # Инъекция зависимостей через атрибуты сессии
        # Это позволяет агенту получить доступ к нужным компонентам через сессию
        session_context.system_context = self.system_context  # read-only
        session_context.event_publisher = self.event_system  # общая шина
        session_context.execution_gateway = execution_gateway  # сессионный шлюз
        session_context.snapshot_manager = self.snapshot_manager  # добавляем менеджер снапшотов
        
        return session_context
    
    async def create_agent(
        self,
        session_id: str,
        thinking_pattern_name: str = "react",  # ← правильная терминология
        max_steps: int = 10
    ):  # ← правильная терминология
        """Создание агента с правильными зависимостями через порты."""
        # 1. Создаём сессию
        session = await self.create_session(session_id)
        
        # 2. Выбираем паттерн мышления
        thinking_pattern = await self._create_thinking_pattern(thinking_pattern_name, session)
        
        # 3. Создаём агента с ПОРТАМИ вместо контекстов
        from application.agent.runtime.runtime import AgentRuntime
        
        agent = AgentRuntime(
            session_context=session,
            thinking_pattern=thinking_pattern,      # ← правильная терминология
            execution_gateway=session.execution_gateway,      # ← ПОРТ
            skill_registry=self.system_context.skill_registry,  # ← ПОРТ
            event_publisher=self.event_system,                        # ← ПОРТ
            max_steps=max_steps
        )
        
        return agent
    
    async def _create_thinking_pattern(
        self,
        pattern_name: str,
        session: SessionContext
    ):
        """Фабричный метод создания паттерна мышления."""
        from domain.abstractions.thinking_pattern import IThinkingPattern
        from application.agent.thinking_patterns.react_pattern import ReActThinkingPattern, CodeAnalysisThinkingPattern, PlanningThinkingPattern, PlanExecutionThinkingPattern, EvaluationThinkingPattern, FallbackThinkingPattern
        
        # Получаем LLM провайдер из сессии, оркестратора или из системного контекста
        llm_provider = getattr(session, 'llm_provider', None) or getattr(self, 'llm_provider', None)
        prompt_renderer = getattr(session, 'prompt_renderer', None) or getattr(self, 'prompt_renderer', None)
        prompt_repository = getattr(self, 'prompt_repository', None)  # Получаем репозиторий из оркестратора
        
        # Возвращаем экземпляры классических паттернов мышления с провайдерами
        classic_patterns = {
            "react": ReActThinkingPattern(llm_provider=llm_provider, prompt_renderer=prompt_renderer, prompt_repository=prompt_repository),
            "code_analysis": CodeAnalysisThinkingPattern(llm_provider=llm_provider, prompt_renderer=prompt_renderer, prompt_repository=prompt_repository),
            "planning": PlanningThinkingPattern(llm_provider=llm_provider, prompt_renderer=prompt_renderer, prompt_repository=prompt_repository),
            "plan_execution": PlanExecutionThinkingPattern(llm_provider=llm_provider, prompt_renderer=prompt_renderer, prompt_repository=prompt_repository),
            "evaluation": EvaluationThinkingPattern(llm_provider=llm_provider, prompt_renderer=prompt_renderer, prompt_repository=prompt_repository),
            "fallback": FallbackThinkingPattern(llm_provider=llm_provider, prompt_renderer=prompt_renderer, prompt_repository=prompt_repository)
        }
        
        if pattern_name in classic_patterns:
            return classic_patterns[pattern_name]
        else:
            # По умолчанию используем ReAct
            return ReActThinkingPattern(llm_provider=llm_provider, prompt_renderer=prompt_renderer, prompt_repository=prompt_repository)
    
    async def initialize(self) -> bool:
        """
        Асинхронная инициализация системы.
        
        ВОЗВРАЩАЕТ:
        - bool: Успешность инициализации
        """
        # Валидация системного контекста
        try:
            self.system_context.validate()
        except Exception as e:
            print(f"Ошибка валидации системного контекста: {e}")
            return False
        
        return True
    
    async def shutdown(self) -> None:
        """
        Асинхронное завершение работы системы.
        """
        # Закрываем ресурсы при необходимости
        pass
    
    def get_system_context(self) -> SystemContext:
        """
        Получение системного контекста (read-only).
        
        ВОЗВРАЩАЕТ:
        - SystemContext: Чистый реестр компонентов
        """
        return self.system_context
    
    def get_event_publisher(self) -> IEventPublisher:
        """
        Получение издателя событий.

        ВОЗВРАЩАЕТ:
        - IEventPublisher: Интерфейс издателя событий
        """
        return self.event_system


class AgentFactory:
    """
    Фабрика агентов - создает экземпляры агентов с инъекцией зависимостей.

    ОТВЕТСТВЕННОСТЬ:
    - Создание агентов с нужными зависимостями
    - Инъекция системного контекста, шины событий и других компонентов
    """

    def __init__(self, system_context: SystemContext, event_publisher: IEventPublisher):
        """
        Инициализация фабрики агентов.

        ПАРАМЕТРЫ:
        - system_context: Системный контекст (реестр компонентов)
        - event_publisher: Издатель событий (один экземпляр на систему)
        """
        self.system_context = system_context
        self.event_publisher = event_publisher
    
    def create_agent(self, agent_type: str, **kwargs):
        """
        Создание агента с инъекцией зависимостей.
        
        ПАРАМЕТРЫ:
        - agent_type: Тип создаваемого агента
        - **kwargs: Дополнительные параметры
        
        ВОЗВРАЩАЕТ:
        - Экземпляр агента с инъекцией зависимостей
        """
        # В реальной реализации здесь будет создание конкретного типа агента
        # с инъекцией нужных зависимостей через конструктор или методы
        raise NotImplementedError("Создание агентов будет реализовано в рамках другой задачи")