"""
Упрощенный системный контекст (SystemContext).
ОСОБЕННОСТИ:
- Минимальная сложность
- Отсутствие циклических зависимостей
- Явный порядок инициализации
- Простота понимания и поддержки
"""
import uuid
import logging
import os
from typing import Any, Dict, List, Optional

from core.agent_runtime.runtime import AgentRuntime
from core.config.models import SystemConfig
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.session_context import SessionContext
from core.system_context.base_system_contex import BaseSystemContext
from core.system_context.execution_gateway import ExecutionGateway
from core.system_context.resource_registry import ResourceRegistry, ResourceInfo
from core.system_context.capability_registry import CapabilityRegistry
from core.system_context.lifecycle_manager import LifecycleManager

from core.infrastructure.providers.factory import ProviderFactory
from models.capability import Capability
from models.llm_types import LLMRequest, LLMResponse
from models.resource import ResourceType

logger = logging.getLogger(__name__)

class SystemContext(BaseSystemContext):
    """
    Cистемный контекст - центральный фасад системы.
    
    АРХИТЕКТУРА:
    - Pattern: Facade
    - Инкапсулирует сложность внутренних подсистем
    - Предоставляет единую точку доступа ко всей системе
    
    ВНУТРЕННИЕ КОМПОНЕНТЫ:
    - registry: Реестр ресурсов
    - capabilities: Реестр capability
    - lifecycle: Менеджер жизненного цикла
    - config: Конфигурация
    - agents: Фабрика агентов
    - provider_factory: Фабрика провайдеров
    
    ИНИЦИАЛИЗАЦИЯ:
    1. Создание всех компонентов
    2. Регистрация стандартных ресурсов
    3. Инициализация через lifecycle manager
    """
    
    def __init__(self, config: Optional[SystemConfig] = None):
        """
        Инициализация системного контекста.
        
        ПАРАМЕТРЫ:
        - config: Конфигурация приложения (опционально)
        
        СОЗДАВАЕМЫЕ КОМПОНЕНТЫ:
        - registry: Реестр ресурсов
        - capabilities: Реестр capability
        - lifecycle: Менеджер жизненного цикла
        - config: Конфигурация
        - provider_factory: Фабрика провайдеров
        
        ОСОБЕННОСТИ:
        - Создает все необходимые внутренние компоненты
        - Не выполняет их инициализацию (только создание)
        - Готов к регистрации ресурсов сразу после создания
        """
        self.id = str(uuid.uuid4())
        self.config = config or SystemConfig()
        self.registry = ResourceRegistry()
        self.capabilities = CapabilityRegistry()
        self.lifecycle = LifecycleManager(self.registry, self.capabilities)
        self.initialized = False
        self.execution_gateway = ExecutionGateway()
        
        # Инициализация фабрики провайдеров
        self.provider_factory = ProviderFactory(self)
        
        # Настройка логирования
        self._setup_logging()
        
        logger.info(f"SystemContext создан (ID: {self.id})")
    
    def _setup_logging(self):
        """
        Настройка логирования на основе конфигурации.
        
        ОСОБЕННОСТИ:
        - Установка уровня логирования
        - Настройка форматирования
        - Добавление обработчиков
        """
        # Создание директории для логов если не существует
        log_dir = self.config.log_dir or "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # Установка уровня логирования
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logging.basicConfig(level=log_level, encoding='utf-8')

        
        # Создание обработчика для файла
        log_file = os.path.join(log_dir, f"system_{self.id[:8]}.log")
        file_handler = logging.FileHandler(
            filename=log_file,
            encoding='utf-8',
            mode='a'
            )
        
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logging.getLogger().addHandler(file_handler)
    

    async def initialize(self) -> bool:
        """Инициализация системы."""
        try:
            logger.info(f"Инициализация системы (ID: {self.id}) с профилем: {self.config.profile}")
            
            # 1. Автоматическая регистрация провайдеров из конфигурации
            await self._register_providers_from_config()
            
            # 2. Автоматическая регистрация инструментов из директории
            await self.provider_factory.discover_and_create_all_tools()
            
            # 3. Автоматическая регистрация навыков из директории
            await self.provider_factory.discover_and_create_all_skills()
            
            # 4. Инициализация всех компонентов
            initialization_success = await self.lifecycle.initialize()
            if not initialization_success:
                logger.warning("Не все компоненты были успешно инициализированы")
            
            # 5. Проверка здоровья системы
            health_report = await self.lifecycle.check_health()
            if health_report["status"] == "unhealthy":
                logger.error("Система не прошла проверку здоровья")
                return False
            
            self.initialized = True
            logger.info("Система успешно инициализирована")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации системы: {str(e)}", exc_info=True)
            return False
        
    async def shutdown(self) -> None:
        """
        Завершение работы системы.
        
        ПРОЦЕСС:
        1. Корректное завершение работы всех ресурсов
        2. Установка флага initialized в False
        3. Логирование завершения работы
        
        ОСОБЕННОСТИ:
        - Метод безопасен для повторного вызова
        - Ошибки при завершении отдельных ресурсов не прерывают процесс
        - Все ресурсы получают шанс корректно завершить работу
        """
        if not self.initialized:
            return
        
        logger.info("Завершение работы системы...")
        await self.lifecycle.shutdown()
        self.initialized = False
        logger.info("Система успешно завершила работу")
    
    async def _register_providers_from_config(self) -> None:
        """
        Автоматическая регистрация провайдеров из конфигурации.
        
        ЛОГИКА:
        1. Регистрация LLM провайдеров
        2. Регистрация DB провайдеров
        
        ОБРАБОТКА ОШИБОК:
        - Пропуск некорректных конфигураций
        - Логирование ошибок создания провайдеров
        """
       # 1. Регистрация LLM провайдеров
        for provider_name, provider_config in self.config.llm_providers.items():
            if provider_config.enabled:
                try:
                    provider = await self.provider_factory.create_llm_provider_from_config(
                        provider_config,
                        provider_name
                    )
                    if provider:
                        # Регистрация LLM провайдера в системе
                        info_llm = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.LLM_PROVIDER,
                            instance=provider
                        )
                        info_llm.is_default=True # Нужно добавить проверку что именно первая LLM загружена
                        self.registry.register(info_llm)
                        logger.info(f"LLM провайдер '{provider_name}' успешно зарегистрирован")
                except Exception as e:
                    logger.error(f"Ошибка регистрации LLM провайдера '{provider_name}': {str(e)}")
        
        # 2. Регистрация DB провайдеров
        for provider_name, provider_config in self.config.db_providers.items():
            if provider_config.enabled:
                try:
                    provider = await self.provider_factory.create_db_provider_from_config(
                        provider_config,
                        provider_name
                    )
                    if provider:
                        # Регистрация DB провайдера в системе
                        info_db = ResourceInfo(
                            name=provider_name,
                            resource_type=ResourceType.DATABASE,
                            instance=provider
                        )
                        info_db.is_default=True

                        self.registry.register(info_db)
                        logger.info(f"DB провайдер '{provider_name}' успешно зарегистрирован")
                except Exception as e:
                    logger.error(f"Ошибка регистрации DB провайдера '{provider_name}': {str(e)}")
    
    def _get_resources_by_type(self, resource_type: ResourceType) -> Dict[str, ResourceInfo]:
        """
        Получение ресурсов заданного типа.
        
        ПАРАМЕТРЫ:
        - resource_type: Тип ресурсов для получения
        
        ВОЗВРАЩАЕТ:
        - Словарь {имя_ресурса: ResourceInfo} для ресурсов заданного типа
        """
        resources = {}
        all_resources = self.registry.all()
        
        for name, info in all_resources.items():
            if info.resource_type == resource_type:
                resources[name] = info
        
        return resources
    
    def get_resource(self, name: str) -> Optional[Any]:
        """
        Получение ресурса по имени.
        
        ПАРАМЕТРЫ:
        - name: Имя ресурса
        
        ВОЗВРАЩАЕТ:
        - Экземпляр ресурса если найден
        - None если ресурс не найден
        
        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        llm_provider = system.get_resource("primary_llm")
        if llm_provider:
            response = await llm_provider.generate(request)
        """
        info = self.registry.get(name)
        return info.instance if info else None
    
    def get_capability(self, name: str) -> Optional[Capability]:
        """
        Получение capability по имени.
        
        ПАРАМЕТРЫ:
        - name: Имя capability
        
        ВОЗВРАЩАЕТ:
        - Capability объект если найден
        - None если capability не найдена
        
        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        cap = system.get_capability("planning.create_plan")
        if cap:
            print(f"Описание: {cap.description}")
        """
        return self.capabilities.get(name)
    
    def list_capabilities(self) -> List[str]:
        """
        Получение списка всех доступных capability.
        
        ВОЗВРАЩАЕТ:
        - Список имен capability
        
        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        caps = system.list_capabilities()
        print(f"Доступные capability: {caps}")
        """
        return [cap.name for cap in self.capabilities.all()]
    
    async def call_llm(self, prompt: str) -> str:
        """
        Вызов LLM для генерации текста.
        
        ПАРАМЕТРЫ:
        - prompt: Промпт для генерации
        
        ВОЗВРАЩАЕТ:
        - Сгенерированный текст
        
        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
        response = await system.call_llm("Привет! Как дела?")
        """
        default_llm = None
        for info in self.registry.all():
            if info.resource_type == ResourceType.LLM_PROVIDER and info.is_default:
                default_llm = info.instance
                break
        
        if default_llm is None:
            # Используем первый доступный LLM провайдер
            for info in self.registry.all():
                if info.resource_type == ResourceType.LLM_PROVIDER:
                    default_llm = info.instance
                    break
        
        if default_llm is None:
            raise ValueError("Нет доступных LLM провайдеров")
        
        return await default_llm.generate({"prompt": prompt})
    

    async def create_agent(self, **kwargs):
        """
        Асинхронное создание агента.
        
        ПАРАМЕТРЫ:
        - **kwargs: Дополнительные параметры для AgentRuntime
        
        ВОЗВРАЩАЕТ:
        - Экземпляр AgentRuntime
        
        ПРИМЕР:
        # Создание агента с настройками по умолчанию
        agent = await factory.create()
        
        # Создание агента с кастомными параметрами
        agent = await factory.create(
            max_steps=20,
            temperature=0.5,
            session_context=existing_session
        )
        
        ОСОБЕННОСТИ:
        - Динамический импорт AgentRuntime для избежания циклических зависимостей
        - Создание SessionContext по умолчанию
        - Передача всех параметров напрямую в конструктор AgentRuntime
        
        ЗАМЕЧАНИЕ:
        - Метод всегда асинхронный, даже если создание агента синхронное
        - Не выполняет инициализацию агента, только создает экземпляр
        """

        return AgentRuntime(self, SessionContext(), **kwargs)

    
    async def create_agent_for_question(self, question: str, **kwargs):
        """
        Создает агента, настроенного под конкретный вопрос.
        
        Параметры:
        - question: вопрос/цель, которую должен решить агент
        - **kwargs: дополнительные параметры агента (max_steps, temperature и т.д.)
        
        Возвращает:
        - Экземпляр агента, готовый к выполнению
        """
        # Выбор стратегии на основе типа вопроса
        strategy = await self._select_strategy_for_question(question)
        
        # Создание сессии с сохранением вопроса
        session_context = SessionContext()
        session_context.set_goal(question)
        
        # Настройка параметров агента
        agent_params = {
            "max_steps": kwargs.get("max_steps", self.config.agent.get("max_steps", 10)),
            "strategy": strategy,
            **{k: v for k, v in kwargs.items() if k not in ["max_steps"]}
        }
        
        # Создание агента
        return AgentRuntime(
            system=self,
            session_context=session_context,
            **agent_params
        )
    
    async def execute_sql_query(self, query: str, params: dict = {}, db_provider_name: str = "default_db"):
        """
        Выполняет SQL-запрос к базе данных.
        
        Параметры:
        - query: SQL-запрос
        - params: параметры запроса
        - db_provider_name: имя провайдера БД
        
        Возвращает:
        - Результат выполнения в формате DBQueryResult
        """
        db_provider = self.get_resource(db_provider_name)
        if not db_provider:
            raise ValueError(f"DB провайдер '{db_provider_name}' не найден")
        
        if not hasattr(db_provider, "execute"):
            raise ValueError(f"Провайдер '{db_provider_name}' не поддерживает выполнение запросов")
        
        try:
            result = await db_provider.execute(query, params or {})
            logger.info(f"SQL запрос выполнен успешно. Затронуто строк: {result.rowcount}")
            return result
        except Exception as e:
            logger.error(f"Ошибка выполнения SQL запроса: {str(e)}")
            raise
    
    async def call_llm_with_params(
        self,
        user_prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        llm_provider_name: str = "default_llm",
        output_format: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Выполняет запрос к LLM с заданными параметрами.
        
        Параметры:
        - prompt: основной промпт
        - system_prompt: системный промпт
        - temperature: температура генерации
        - max_tokens: максимальное количество токенов
        - llm_provider_name: имя LLM провайдера
        - output_format: формат выходных данных (например, "json")
        - output_schema: JSON Schema для структурирования выходных данных
        - **kwargs: дополнительные параметры генерации
        
        Возвращает:
        - Результат генерации в формате LLMResponse
        """
        llm_provider = self.get_resource(llm_provider_name)
        if not llm_provider:
            raise ValueError(f"LLM провайдер '{llm_provider_name}' не найден")
        
        # Получаем параметры по умолчанию из конфигурации провайдера
        default_temperature = 0.7
        default_max_tokens = 2048
        
        if hasattr(llm_provider, "_config"):
            config = llm_provider._config
            default_temperature = getattr(config, "temperature", default_temperature)
            default_max_tokens = getattr(config, "max_tokens", default_max_tokens)
        elif hasattr(llm_provider, "config"):
            config = llm_provider.config
            default_temperature = config.get("temperature", default_temperature)
            default_max_tokens = config.get("max_tokens", default_max_tokens)
        
        temperature = temperature or default_temperature
        max_tokens = max_tokens or default_max_tokens
        
        try:
            if output_format == "json" and output_schema:
                
                # Определяем тип провайдера для правильного вызова метода
                provider_type = type(llm_provider).__name__
                logger.debug(f"Тип LLM провайдера: {provider_type}")
                
                # Выполняем структурированную генерацию в зависимости от типа провайдера
                if provider_type == "LlamaCppProvider":
                    # Для LlamaCppProvider используем user_prompt
                    return await llm_provider.generate_structured(
                        user_prompt=user_prompt,
                        output_schema=output_schema,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
                else:
                    # Для остальных провайдеров (VLLMProvider) используем prompt
                    return await llm_provider.generate_structured(
                        user_prompt=user_prompt,
                        output_schema=output_schema,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )
            else:
                # Стандартная генерация текста
                request = LLMRequest(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                response = await llm_provider.generate(request)
                logger.debug(f"LLM запрос выполнен за {response.generation_time:.2f} секунд")
                return response
                
        except Exception as e:
            logger.error(f"Ошибка выполнения LLM запроса: {str(e)}", exc_info=True)
            raise

    async def run_capability(
        self, 
        capability_name: str, 
        parameters: dict,
        session_context: BaseSessionContext = None
    ):
        """
        Выполняет конкретный навык с заданными параметрами.
        
        Параметры:
        - capability_name: имя capability для выполнения
        - parameters: параметры для capability
        - session_context: контекст сессии (если нет, создается новый)
        
        Возвращает:
        - Результат выполнения capability
        """
        
        # Создаем контекст сессии при необходимости
        if session_context is None:
            raise ValueError(f"Ошибка запуска умения '{capability_name}', непередан контекст.")
        
        # Используем ExecutionGateway для выполнения capability
        # step_number = session_context.step_context.get_current_step_number() + 1
        
        result = await self.execution_gateway.execute_capability(
            capability_name = capability_name,
            parameters = parameters,
            system_context = self,
            session_context = session_context
            )
        
        return result
    
    async def _select_strategy_for_question(self, question: str) -> str:
        """
        Выбирает стратегию выполнения на основе типа вопроса.
        """
        # Анализируем вопрос для определения типа
        question_lower = question.lower()
        
        # Правила выбора стратегии
        if any(keyword in question_lower for keyword in ["запланировать", "план", "шаги", "этапы"]):
            return "hierarchical_planning"
        elif any(keyword in question_lower for keyword in ["анализ", "данные", "таблица", "sql", "база"]):
            return "react"  # или специальная стратегия для работы с данными
        elif any(keyword in question_lower for keyword in ["оценить", "проверить", "результат"]):
            return "evaluation"
        
        # Стратегия по умолчанию
        return self.config.agent.get("default_strategy", "react")