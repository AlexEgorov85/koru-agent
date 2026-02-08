"""
DEPRECATED: This factory is no longer needed as we now use EventSystem directly.
This interface is kept for backward compatibility during migration and will be removed.
"""
import warnings
from abc import ABC, abstractmethod
from typing import Protocol
from domain.abstractions.event_types import IEventPublisher


class IEventPublisherFactory(ABC):
    """DEPRECATED: This factory is no longer needed as we now use EventSystem directly."""
    
    def __init__(self):
        warnings.warn(
            "IEventPublisherFactory is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )

    @abstractmethod
    def create_event_publisher(self) -> IEventPublisher:
        """
        DEPRECATED: Create new event publisher instance.
        Use EventSystem directly instead.

        Returns:
            IEventPublisher: Новый экземпляр издателя событий
        """
        warnings.warn(
            "IEventPublisherFactory.create_event_publisher is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        pass

    @abstractmethod
    def get_global_event_publisher(self) -> IEventPublisher:
        """
        DEPRECATED: Get global event publisher instance.
        Use EventSystem directly instead.

        Returns:
            IEventPublisher: Глобальный экземпляр издателя событий
        """
        warnings.warn(
            "IEventPublisherFactory.get_global_event_publisher is deprecated. Use EventSystem directly.",
            DeprecationWarning,
            stacklevel=2
        )
        pass