"""
Абстракции для рендера промтов (инверсия зависимостей)
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from domain.models.prompt.prompt_version import PromptVersion
from domain.models.domain_type import DomainType
from domain.models.provider_type import LLMProviderType


class IPromptRenderer(ABC):
    """Интерфейс для рендера промтов"""

    @abstractmethod
    async def render_prompt(
        self,
        prompt_version: PromptVersion,
        template_context: Dict[str, Any]
    ) -> str:
        """
        Рендерить промт с заданным контекстом
        
        Args:
            prompt_version: Версия промта для рендера
            template_context: Контекст для подстановки в шаблон
            
        Returns:
            Готовый промт для отправки LLM
        """
        pass

    @abstractmethod
    async def render_for_capability(
        self,
        domain: DomainType,
        capability_name: str,
        provider_type: LLMProviderType,
        role: str,
        template_context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Рендерить промт для конкретной capability
        
        Args:
            domain: Домен capability
            capability_name: Имя capability
            provider_type: Тип LLM провайдера
            role: Роль (system/user/assistant)
            template_context: Контекст для подстановки в шаблон
            
        Returns:
            Готовый промт или None если не найден
        """
        pass

    @abstractmethod
    async def batch_render(
        self,
        prompts: List[PromptVersion],
        template_context: Dict[str, Any]
    ) -> List[str]:
        """
        Рендерить несколько промтов за раз
        
        Args:
            prompts: Список версий промтов
            template_context: Контекст для подстановки в шаблоны
            
        Returns:
            Список готовых промтов
        """
        pass