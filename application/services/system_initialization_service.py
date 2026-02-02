from typing import Dict, Any, Callable
from config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from domain.abstractions.event_system import IEventPublisher, EventType
from domain.abstractions.system.base_system_context import IBaseSystemContext
import os


class SystemInitializationService:
    """
    Сервис инициализации системных компонентов.
    
    Этот сервис отвечает за:
    1. Загрузку и валидацию конфигурации
    2. Инициализацию провайдеров (LLM, DB и т.д.)
    3. Регистрацию ресурсов в системном контексте
    """
    
    def __init__(self, system_context: IBaseSystemContext, config: SystemConfig, event_publisher: IEventPublisher):
        self._system_context = system_context
        self._config = config
        self._event_publisher = event_publisher

    async def initialize_providers_from_config(self) -> None:
        """
        Инициализация провайдеров из конфигурации.
        """
        # 1. Регистрация LLM провайдеров
        for provider_name, provider_config in self._config.llm_providers.items():
            if provider_config.enabled:
                try:
                    # Создание провайдера на основе конфигурации
                    provider = await self._create_llm_provider_from_config(provider_config, provider_name)
                    if provider:
                        # Регистрация LLM провайдера в системе
                        self._system_context._resources[provider_name] = provider
                        
                        await self._event_publisher.publish(
                            EventType.INFO,
                            "SystemInitialization",
                            {"message": f"LLM провайдер '{provider_name}' успешно зарегистрирован"}
                        )
                except Exception as e:
                    await self._event_publisher.publish(
                        EventType.ERROR,
                        "SystemInitialization",
                        {"message": f"Ошибка регистрации LLM провайдера '{provider_name}': {str(e)}"}
                    )
        
        # 2. Регистрация DB провайдеров
        for provider_name, provider_config in self._config.db_providers.items():
            if provider_config.enabled:
                try:
                    provider = await self._create_db_provider_from_config(provider_config, provider_name)
                    if provider:
                        # Регистрация DB провайдера в системе
                        self._system_context._resources[provider_name] = provider
                        
                        await self._event_publisher.publish(
                            EventType.INFO,
                            "SystemInitialization",
                            {"message": f"DB провайдер '{provider_name}' успешно зарегистрирован"}
                        )
                except Exception as e:
                    await self._event_publisher.publish(
                        EventType.ERROR,
                        "SystemInitialization",
                        {"message": f"Ошибка регистрации DB провайдера '{provider_name}': {str(e)}"}
                    )

    async def _create_llm_provider_from_config(self, provider_config: LLMProviderConfig, provider_name: str):
        """
        Создание LLM провайдера из конфигурации.
        """
        # Это упрощенная реализация - в реальной системе здесь будет
        # более сложная логика для создания конкретных провайдеров
        # в зависимости от provider_config.type_provider
        if provider_config.type_provider == "llama_cpp":
            # Импорт происходит только при необходимости и не нарушает архитектурные границы
            # поскольку мы не храним конкретную реализацию в домене
            pass  # Здесь будет логика создания провайдера
        elif provider_config.type_provider == "vllm":
            pass  # Здесь будет логика создания провайдера
        # и т.д.
        
        # Возвращаем None, так как конкретные реализации провайдеров могут быть
        # недоступны или требовать дополнительные зависимости
        return None

    async def _create_db_provider_from_config(self, provider_config: DBProviderConfig, provider_name: str):
        """
        Создание DB провайдера из конфигурации.
        """
        # Аналогично LLM провайдеру
        return None

    async def setup_logging(self) -> None:
        """
        Настройка логирования на основе конфигурации.
        """
        # Создание директории для логов если не существует
        log_dir = self._config.log_dir or "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        await self._event_publisher.publish(
            EventType.INFO,
            "SystemInitialization",
            {"message": f"Логирование настроено, директория: {log_dir}"}
        )