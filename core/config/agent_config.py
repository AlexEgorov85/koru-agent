from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
import uuid

from core.agent.models import StepConfig


class AgentConfig(BaseModel):
    """
    Конфигурация агента с фиксированными версиями промптов и контрактов.
    Создаётся ОДИН РАЗ при запуске агента и не изменяется во время выполнения.
    
    ВАЖНО: Это тонкая проекция AppConfig для runtime-параметров.
    Параметры max_steps, temperature, max_retries берутся из AppConfig.agent_defaults.
    """
    model_config = ConfigDict(frozen=True)  # Неизменяемая конфигурация
    
    # Идентификатор и метаданные
    config_id: str = Field(default_factory=lambda: f"cfg_{uuid.uuid4().hex[:8]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: Literal["explicit", "auto_resolved"] = Field("auto_resolved")
    
    # Версии промптов: {capability_name: version}
    prompt_versions: Dict[str, str] = Field(default_factory=dict)
    
    # Версии контрактов: {contract_name: version}
    contract_versions: Dict[str, str] = Field(default_factory=dict)
    
    # Конфигурация шагов: {step_id: StepConfig}
    steps: Dict[str, StepConfig] = Field(default_factory=dict)
    
    # Runtime-параметры (не дублируются, берутся из AppConfig)
    goal: Optional[str] = Field(default=None, description="Цель агента (runtime)")
    session_id: Optional[str] = Field(default=None, description="ID сессии (runtime)")
    parent_trace_id: Optional[str] = Field(default=None, description="ID родительского трейса (runtime)")
    
    # Бюджет токенов (Фаза 3)
    max_total_tokens: int = Field(50000, description="Максимальное количество токенов на сессию")
    context_token_threshold: int = Field(8000, description="Порог для сжатия контекста")
    
    # Флаги для тестирования
    allow_inactive_resources: bool = Field(False)
    
    # Фильтрация capability для промта размышлений
    capability_filter: Dict[str, Any] = Field(
        default_factory=lambda: {
            "include_hidden": False,
            "component_types": ["skill"],
        }
    )
    
    @classmethod
    def from_app_config(cls, app_config: 'AppConfig', **runtime_params) -> 'AgentConfig':
        """
        Создать AgentConfig из AppConfig (тонкая проекция).
        
        ARGS:
        - app_config: Исходная конфигурация приложения
        - runtime_params: Runtime-параметры (goal, session_id, parent_trace_id)
        
        RETURNS:
        - AgentConfig: Конфигурация агента
        """
        return cls(
            source="explicit",
            **runtime_params
        )
    
    @classmethod
    def auto_resolve(cls, system_context: Any) -> 'AgentConfig':
        """
        Автоматическое разрешение конфигурации на основе активных версий.
        Вызывается при отсутствии явной конфигурации.
        """
        # Получаем реестр активных версий из существующего механизма
        # В проекте используется файловая структура с метаданными в промптах
        prompt_service = system_context.get_resource("prompt_service")
        if not prompt_service:
            raise RuntimeError("PromptService не зарегистрирован в системном контексте")
        
        # Сканируем директорию промптов и определяем активные версии
        # Логика: файлы НЕ в папке archived/ + статус 'active' в метаданных
        active_prompts = prompt_service.scan_active_prompts()
        
        # Формируем конфигурацию
        return cls(
            prompt_versions={
                cap: info["version"] 
                for cap, info in active_prompts.items() 
                if info.get("status") == "active"
            },
            source="auto_resolved"
        )
    
    @classmethod
    def from_yaml(cls, yaml_path: str, capability_registry: Optional[set] = None) -> 'AgentConfig':
        """
        Загрузка конфигурации из YAML файла.
        
        ПАРАМЕТРЫ:
        - yaml_path: путь к YAML файлу
        - capability_registry: множество зарегистрированных capability для валидации
        
        ВОЗВРАЩАЕТ:
        - AgentConfig: загруженная конфигурация
        
        ИСКЛЮЧЕНИЯ:
        - ValueError: если шаг ссылается на несуществующую capability
        - FileNotFoundError: если файл не найден
        """
        import yaml
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            raise ValueError(f"YAML должен содержать объект, получен: {type(data)}")
        
        # Преобразуем шаги из YAML в StepConfig
        steps_data = data.pop('steps', {})
        steps = {}
        
        for step_id, step_config in steps_data.items():
            if not isinstance(step_config, dict):
                raise ValueError(f"Шаг '{step_id}' должен быть объектом")
            
            # Создаём StepConfig
            step = StepConfig(**step_config)
            
            # Валидация: capability должен существовать в реестре
            if capability_registry is not None:
                if step.capability not in capability_registry:
                    raise ValueError(
                        f"Шаг '{step_id}' ссылается на несуществующую capability: {step.capability}. "
                        f"Доступные: {sorted(capability_registry)[:10]}..."
                    )
                
                # Валидация fallback_capability
                if step.fallback_capability and step.fallback_capability not in capability_registry:
                    raise ValueError(
                        f"Шаг '{step_id}' имеет несуществующий fallback_capability: {step.fallback_capability}"
                    )
                
                # Проверка на циклическую зависимость A → A
                if step.fallback_capability == step.capability:
                    raise ValueError(
                        f"Шаг '{step_id}': fallback_capability не может указывать на себя"
                    )
            
            steps[step_id] = step
        
        # Создаём конфигурацию
        config = cls(steps=steps, **data)
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для сохранения в отчёт бенчмарка"""
        return self.model_dump(mode='json')