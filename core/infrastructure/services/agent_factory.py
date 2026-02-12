from typing import Optional, Any
from core.config.agent_config import AgentConfig
from core.session_context.session_context import SessionContext
import uuid


class AgentFactory:
    """
    Фабрика создания агентов с гарантией однократной загрузки промптов/контрактов.
    """

    def __init__(self, system_context: Any):
        self.system_context = system_context

    async def create_agent(
        self,
        goal: str,
        agent_config: Optional[AgentConfig] = None,
        correlation_id: Optional[str] = None,
        user_context: Optional['UserContext'] = None  # Добавляем контекст пользователя
    ) -> 'AgentRuntime':
        """
        Создание агента с фиксированной конфигурацией.

        Если конфигурация не указана — автоматически разрешается из активных версий.
        """
        # 1. СТРОГАЯ проверка готовности системы
        if not self.system_context.is_fully_initialized():
            raise RuntimeError(
                "Система не готова к созданию агента:\n"
                f"  • Инициализирована: {self.system_context.initialized}\n"
                f"  • Промпты загружены: {self.system_context.registry.are_prompts_preloaded()}\n"
                f"  • Контракты загружены: {self.system_context.registry.are_contracts_preloaded()}\n"
                "Выполните полную инициализацию SystemContext перед созданием агента."
            )

        # 2. Проверка критических сервисов
        required_services = [
            "prompt_service", "contract_service",
            "table_description_service", "sql_query_service"
        ]
        missing = []
        for svc in required_services:
            if not await self.system_context.get_service(svc):
                missing.append(svc)

        if missing:
            raise RuntimeError(
                f"Отсутствуют критические сервисы для работы агента: {missing}\n"
                "Возможно, ошибка в конфигурации или инициализации системы."
            )

        # 3. Разрешение конфигурации (если не указана явно)
        if agent_config is None:
            agent_config = AgentConfig.auto_resolve(self.system_context)
            self.system_context.logger.info(
                f"Автоматически разрешена конфигурация агента: {agent_config.config_id}"
            )

        # 4. Создание агента (теперь безопасно)
        agent = await self._create_agent_with_config(
            goal=goal,
            agent_config=agent_config,
            correlation_id=correlation_id,
            user_context=user_context  # Передаем контекст пользователя
        )

        # 5. Инициализация ВСЕХ компонентов с загрузкой промптов/контрактов
        # Это ЕДИНСТВЕННЫЙ момент загрузки ресурсов за жизненный цикл агента
        await self._initialize_agent_components(agent, agent_config)

        self.system_context.logger.info(
            f"Агент создан (correlation_id={correlation_id}). "
            f"Загружено промптов: {len(agent_config.prompt_versions)}, "
            f"контрактов: {len(agent_config.contract_versions)}"
        )

        return agent
    
    async def _create_agent_with_config(
        self,
        goal: str,
        agent_config: AgentConfig,
        correlation_id: Optional[str],
        user_context: Optional['UserContext'] = None  # Добавляем контекст пользователя
    ) -> 'AgentRuntime':
        """Создание экземпляра агента с привязкой конфигурации"""
        # Динамический импорт для избежания циклических зависимостей
        from core.agent_runtime.runtime import AgentRuntime

        agent = AgentRuntime(
            system_context=self.system_context,
            session_context=SessionContext(),
            max_steps=agent_config.max_steps,
            strategy_name=agent_config.default_strategy,
            agent_config=agent_config,  # ← Ключевая привязка конфигурации
            correlation_id=correlation_id or f"agent_{uuid.uuid4().hex[:8]}",
            user_context=user_context  # Передаем контекст пользователя
        )
        return agent
    
    async def _initialize_agent_components(self, agent: 'AgentRuntime', agent_config: AgentConfig):
        """
        Инициализация компонентов агента с ОДНОКРАТНОЙ загрузкой промптов/контрактов.
        После этого метода компоненты используют ТОЛЬКО кэш — обращений к хранилищу нет.
        """
        # 1. Инициализация стратегий (только компоненты агента)
        for strategy_name, strategy in agent._strategy_registry.items():
            if not await strategy.initialize(agent_config=agent_config):
                raise RuntimeError(f"Ошибка инициализации стратегии '{strategy_name}'")
        
        # 2. Сохранение конфигурации в агенте для аудита
        agent._agent_config = agent_config