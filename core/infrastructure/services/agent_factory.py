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
        correlation_id: Optional[str] = None
    ) -> 'AgentRuntime':
        """
        Создание агента с фиксированной конфигурацией.

        Если конфигурация не указана — автоматически разрешается из активных версий.
        """
        # 1. Проверка готовности системы ДО создания агента
        if not self.system_context.is_fully_initialized():
            raise RuntimeError(
                "Система не готова: не все ресурсы предзагружены. "
                "Выполните инициализацию системного контекста с предзагрузкой ресурсов."
            )

        # 2. Разрешение конфигурации (если не указана явно)
        if agent_config is None:
            agent_config = AgentConfig.auto_resolve(self.system_context)
            self.system_context.logger.info(
                f"Автоматически разрешена конфигурация агента: {agent_config.config_id}"
            )

        # 3. Создание агента с привязкой конфигурации
        agent = await self._create_agent_with_config(
            goal=goal,
            agent_config=agent_config,
            correlation_id=correlation_id
        )

        # 4. Инициализация ВСЕХ компонентов с загрузкой промптов/контрактов
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
        correlation_id: Optional[str]
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
            correlation_id=correlation_id or f"agent_{uuid.uuid4().hex[:8]}"
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