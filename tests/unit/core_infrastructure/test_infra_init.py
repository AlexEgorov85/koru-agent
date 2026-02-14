#!/usr/bin/env python3
"""
Тестирование инициализации инфраструктурного контекста с конфигурацией
"""
import asyncio
from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext


async def test_infrastructure_initialization():
    """Тест инициализации инфраструктурного контекста"""
    print("Загрузка конфигурации из dev.yaml...")
    
    # Загрузка конфигурации из dev.yaml
    config_loader = ConfigLoader()
    config = config_loader.load()  # Загрузит dev.yaml по умолчанию
    
    print(f"Загружена конфигурация: {config.llm_providers}")
    print(f"LLM provider type: {config.llm_providers['default_llm'].provider_type}")
    print(f"DB provider type: {config.db_providers['default_db'].provider_type}")
    
    # Создание инфраструктурного контекста с загруженной конфигурацией
    infra = InfrastructureContext(config)
    print("Инициализация инфраструктурного контекста с параметрами из dev.yaml...")
    await infra.initialize()
    print("Инфраструктурный контекст успешно инициализирован!")
    
    # Проверим, что провайдеры зарегистрированы
    llm_provider = infra.get_provider("default_llm")
    db_provider = infra.get_provider("default_db")
    
    print(f"LLM провайдер: {llm_provider}")
    print(f"DB провайдер: {db_provider}")
    
    # Завершим работу
    await infra.shutdown()
    print("Инфраструктурный контекст завершил работу")


if __name__ == "__main__":
    asyncio.run(test_infrastructure_initialization())