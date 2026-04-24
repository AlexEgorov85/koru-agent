"""
Централизованная конфигурация таймаутов.

ПРОБЛЕМА:
Таймауты были разбросаны по всему коду с разными значениями:
- LLM: 60s (action_executor), 600s (llama_cpp_provider)
- Database: 30s
- Vector Search: 30s
- Action Executor: 60s → 600s

РЕШЕНИЕ:
Единый источник истины для всех таймаутов системы.
"""
from pydantic import BaseModel, Field


class TimeoutConfig(BaseModel):
    """
    Конфигурация таймаутов для всех компонентов системы.
    
    Значения по умолчанию подобраны для локальной работы с LLM (Qwen 4B).
    Для production с облачными LLM значения могут быть уменьшены.
    """
    
    # ========================================================================
    # LLM ТАЙМАУТЫ
    # ========================================================================
    
    llm_attempt_timeout: float = Field(
        default=600.0,
        ge=10.0,
        le=3600.0,
        description="Таймаут на одну попытку LLM вызова (секунды). "
                    "Для локальных моделей (Qwen 4B) требуется 600s. "
                    "Для облачных API можно уменьшить до 30-60s."
    )
    
    llm_total_timeout: float = Field(
        default=1200.0,
        ge=60.0,
        le=7200.0,
        description="Общий таймаут на все попытки LLM вызова (секунды). "
                    "Рассчитывается как attempt_timeout * max_retries."
    )
    
    llm_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Максимальное количество попыток LLM вызова."
    )
    
    # ========================================================================
    # DATABASE ТАЙМАУТЫ
    # ========================================================================
    
    db_connection_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Таймаут подключения к базе данных (секунды)."
    )
    
    db_query_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        description="Таймаут выполнения SQL запроса (секунды)."
    )
    
    db_command_timeout: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        description="Таймаут выполнения SQL команды (секунды)."
    )
    
    # ========================================================================
    # VECTOR SEARCH ТАЙМАУТЫ
    # ========================================================================
    
    vector_search_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Таймаут поиска в векторной базе данных (секунды)."
    )
    
    vector_indexing_timeout: float = Field(
        default=300.0,
        ge=60.0,
        le=3600.0,
        description="Таймаут индексации векторов (секунды)."
    )
    
    # ========================================================================
    # ACTION EXECUTOR ТАЙМАУТЫ
    # ========================================================================
    
    action_default_timeout: float = Field(
        default=600.0,
        ge=60.0,
        le=3600.0,
        description="Таймаут по умолчанию для действий (секунды). "
                    "Используется если не указан специфичный таймаут."
    )
    
    action_context_timeout: float = Field(
        default=120.0,
        ge=30.0,
        le=600.0,
        description="Таймаут для действий контекста (секунды)."
    )
    
    action_validation_timeout: float = Field(
        default=30.0,
        ge=10.0,
        le=120.0,
        description="Таймаут для действий валидации (секунды)."
    )
    
    # ========================================================================
    # AGENT ТАЙМАУТЫ
    # ========================================================================
    
    agent_step_timeout: float = Field(
        default=1200.0,
        ge=300.0,
        le=7200.0,
        description="Таймаут на один шаг агента (секунды). "
                    "Включает LLM вызов + выполнение действия."
    )
    
    agent_total_timeout: float = Field(
        default=7200.0,
        ge=1800.0,
        le=86400.0,
        description="Общий таймаут выполнения агента (секунды). "
                    "По умолчанию 2 часа."
    )
    
    # ========================================================================
    # INFRASTRUCTURE ТАЙМАУТЫ
    # ========================================================================
    
    infrastructure_shutdown_timeout: float = Field(
        default=30.0,
        ge=10.0,
        le=300.0,
        description="Таймаут завершения работы инфраструктуры (секунды)."
    )
    
    event_bus_flush_timeout: float = Field(
        default=10.0,
        ge=5.0,
        le=60.0,
        description="Таймаут очистки шины событий (секунды)."
    )
    
    # ========================================================================
    # МЕТОДЫ
    # ========================================================================
    
    def resolve_for(self, component: str, action: str) -> float:
        """
        Единая точка резолвинга таймаутов для компонента и действия.
        
        ПАРАМЕТРЫ:
        - component: имя компонента (например, 'llm', 'db', 'vector', 'action')
        - action: имя действия (например, 'generate_structured', 'query', 'search')
        
        ВОЗВРАЩАЕТ:
        - float: таймаут в секундах
        
        ПРИМЕРЫ:
        - resolve_for('llm', 'generate_structured') -> llm_attempt_timeout
        - resolve_for('llm', 'generate') -> llm_attempt_timeout * 0.5
        - resolve_for('db', 'query') -> db_query_timeout
        - resolve_for('action', 'default') -> action_default_timeout
        """
        # LLM действия
        if component == 'llm':
            if action == 'generate_structured':
                return self.llm_attempt_timeout
            elif action == 'generate':
                return self.llm_attempt_timeout * 0.5
            elif action == 'classify':
                return self.llm_attempt_timeout * 0.3
            else:
                return self.llm_attempt_timeout
        
        # Database действия
        elif component == 'db':
            if action == 'query':
                return self.db_query_timeout
            elif action == 'command':
                return self.db_command_timeout
            else:
                return self.db_connection_timeout
        
        # Vector Search действия
        elif component == 'vector':
            if action == 'search':
                return self.vector_search_timeout
            elif action == 'indexing':
                return self.vector_indexing_timeout
            else:
                return self.vector_search_timeout
        
        # Action Executor действия
        elif component == 'action':
            if action == 'context':
                return self.action_context_timeout
            elif action == 'validation':
                return self.action_validation_timeout
            else:
                return self.action_default_timeout
        
        # Agent действия
        elif component == 'agent':
            if action == 'step':
                return self.agent_step_timeout
            else:
                return self.agent_total_timeout
        
        # Fallback: action_default_timeout
        return self.action_default_timeout
    
    @classmethod
    def for_local_llm(cls) -> 'TimeoutConfig':
        """
        Конфигурация для локальных LLM (Qwen 4B, Llama 3).

        Требуются большие таймауты из-за медленной генерации.
        """
        return cls(
            llm_attempt_timeout=600.0,  # 10 минут на попытку (было 180с)
            llm_total_timeout=1800.0,   # 30 минут всего (было 600с)
            llm_max_retries=3,
            action_default_timeout=600.0,
            agent_step_timeout=1800.0,
        )
    
    @classmethod
    def for_cloud_llm(cls) -> 'TimeoutConfig':
        """
        Конфигурация для облачных LLM (OpenAI, Anthropic).
        
        Можно использовать меньшие таймауты.
        """
        return cls(
            llm_attempt_timeout=60.0,
            llm_total_timeout=180.0,
            llm_max_retries=3,
            action_default_timeout=60.0,
            agent_step_timeout=120.0,
        )
    
    @classmethod
    def for_testing(cls) -> 'TimeoutConfig':
        """
        Конфигурация для тестов.
        
        Минимальные таймауты для быстрого выполнения тестов.
        """
        return cls(
            llm_attempt_timeout=30.0,
            llm_total_timeout=60.0,
            llm_max_retries=1,
            action_default_timeout=30.0,
            agent_step_timeout=60.0,
            db_connection_timeout=10.0,
            db_query_timeout=30.0,
        )
    
    def get_llm_timeout_for_action(self, action_name: str) -> float:
        """
        Получить таймаут LLM для конкретного действия.
        
        ПАРАМЕТРЫ:
        - action_name: имя действия (например, 'llm.generate_structured')
        
        ВОЗВРАЩАЕТ:
        - float: таймаут в секундах
        """
        # Специфичные таймауты для определённых действий
        action_timeouts = {
            'llm.generate_structured': self.llm_attempt_timeout,
            'llm.generate': self.llm_attempt_timeout * 0.5,  # Простая генерация быстрее
            'llm.classify': self.llm_attempt_timeout * 0.3,  # Классификация ещё быстрее
        }
        
        return action_timeouts.get(action_name, self.llm_attempt_timeout)


# Глобальный экземпляр по умолчанию
DEFAULT_TIMEOUT_CONFIG = TimeoutConfig.for_local_llm()


def get_timeout_config() -> TimeoutConfig:
    """
    Получить текущую конфигурацию таймаутов.
    
    В будущем может читать из environment variables или config файла.
    """
    return DEFAULT_TIMEOUT_CONFIG
