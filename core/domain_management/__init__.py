"""
Domain Management Module for Agent Architecture.

This module contains components for managing domains and adapting prompts
based on the domain context.
"""

from .domain_manager import DomainManager
from .prompt_adapter import PromptAdapter

__all__ = [
    'DomainManager',
    'PromptAdapter'
]