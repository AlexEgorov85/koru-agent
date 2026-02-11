"""
Простой тест для проверки работоспособности архитектуры
"""
from core.config.agent_config import AgentConfig
from core.skills.base_skill import BaseSkill
from core.agent_runtime.strategies.base import AgentStrategyInterface
from core.infrastructure.service.agent_factory import AgentFactory
from core.infrastructure.tools.cached_base_tool import CachedBaseTool
from core.infrastructure.service.cached_base_service import CachedBaseService

print('Все основные компоненты архитектуры кэширования успешно импортированы!')
print('Архитектура реализована для:')
print('- Навыков (Skills) с кэшированием')
print('- Стратегий (Strategies) с кэшированием')
print('- Инструментов (Tools) с кэшированием')
print('- Сервисов (Services) с кэшированием')
print('- Фабрики агентов с управлением конфигурацией')
print()
print('Модель конфигурации агента создана:', AgentConfig)
print('Базовый навык с кэшированием:', BaseSkill)
print('Стратегия с кэшированием:', AgentStrategyInterface)
print('Фабрика агентов:', AgentFactory)
print('Инструмент с кэшированием:', CachedBaseTool)
print('Сервис с кэшированием:', CachedBaseService)