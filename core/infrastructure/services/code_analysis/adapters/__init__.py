"""
Адаптеры языков программирования для мультиязычной поддержки.
"""
from .base_adapter import BaseLanguageAdapter
from .python_adapter import PythonLanguageAdapter


__all__ = [
    'BaseLanguageAdapter',
    'PythonLanguageAdapter'
]