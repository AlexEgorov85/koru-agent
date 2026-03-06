"""
Mock-интерфейсы для тестирования.

Импортируйте отсюда mock-реализации интерфейсов для юнит-тестов.
"""
from tests.mocks.interfaces import (
    MockDatabase,
    MockLLM,
    MockVector,
    MockCache,
    MockEventBus,
    MockPromptStorage,
    MockContractStorage,
    MockMetricsStorage,
    MockLogStorage,
)

# Aliases для обратной совместимости
MockDatabasePort = MockDatabase
MockLLMPort = MockLLM
MockVectorPort = MockVector
MockCachePort = MockCache
MockEventPort = MockEventBus

__all__ = [
    "MockDatabase",
    "MockLLM",
    "MockVector",
    "MockCache",
    "MockEventBus",
    "MockPromptStorage",
    "MockContractStorage",
    "MockMetricsStorage",
    "MockLogStorage",
    # Aliases для обратной совместимости
    "MockDatabasePort",
    "MockLLMPort",
    "MockVectorPort",
    "MockCachePort",
    "MockEventPort",
]
