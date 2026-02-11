from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.agent_runtime.interfaces import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision
from core.config.agent_config import AgentConfig


class AgentStrategyInterface(ABC):
    """
    Базовый интерфейс стратегии.

    Стратегия:
    - анализирует состояние
    - принимает решение
    - НЕ исполняет действия
    """
    
    name: str

    def __init__(self, system_context: Any):
        self.system_context = system_context
        self.prompt_service = system_context.get_resource("prompt_service")
        self._cached_prompts: Dict[str, str] = {}
        self._agent_config: Optional[AgentConfig] = None

    async def initialize(self, agent_config: AgentConfig) -> bool:
        """
        Инициализация стратегии с загрузкой промптов согласно конфигурации.
        После этого метода все промпты доступны из кэша.
        """
        self._agent_config = agent_config
        
        # Загрузка промптов специфичных для стратегии
        # Пример для ReAct: промпт для рассуждений
        strategy_prompts = await self._load_strategy_prompts()
        self._cached_prompts.update(strategy_prompts)
        
        return True

    async def _load_strategy_prompts(self) -> Dict[str, str]:
        """Загрузка промптов, специфичных для стратегии"""
        prompts = {}
        
        # Пример для ReAct: промпт рассуждений
        reasoning_cap = f"strategies.{self.name}.reasoning"
        version = self._agent_config.prompt_versions.get(reasoning_cap)
        
        if version:
            prompt = await self.prompt_service.get_prompt(
                capability_name=reasoning_cap,
                version=version,
                allow_inactive=self._agent_config.allow_inactive_resources
            )
            prompts["reasoning"] = prompt
        
        return prompts

    def get_prompt(self, prompt_key: str) -> str:
        """Получение промпта из кэша"""
        if prompt_key not in self._cached_prompts:
            raise RuntimeError(
                f"Промпт '{prompt_key}' не загружен в стратегии '{self.name}'. "
                f"Вызовите initialize(agent_config) перед использованием."
            )
        return self._cached_prompts[prompt_key]

    @abstractmethod
    async def next_step(
        self,
        runtime: AgentRuntimeInterface
    ) -> StrategyDecision:
        """
        Вернуть решение на текущем шаге.
        """
        pass
