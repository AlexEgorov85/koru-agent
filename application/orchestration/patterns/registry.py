"""
Pattern registry for managing composable thinking patterns.
"""

import importlib
from typing import Dict, Type, Optional, List
from application.orchestration.patterns.base import ComposablePattern


class PatternRegistry:
    """
    Registry for managing composable thinking patterns.
    
    Supports registration, retrieval, and dynamic loading of patterns.
    """
    
    def __init__(self):
        self._patterns: Dict[str, Type[ComposablePattern]] = {}
        self._instances: Dict[str, ComposablePattern] = {}
    
    def register_pattern(self, name: str, pattern_class: Type[ComposablePattern]):
        """
        Register a pattern class by name.
        
        Args:
            name: Name of the pattern
            pattern_class: Class of the pattern to register
        """
        if not issubclass(pattern_class, ComposablePattern):
            raise ValueError(f"{pattern_class} is not a subclass of ComposablePattern")
        
        self._patterns[name] = pattern_class
    
    def unregister_pattern(self, name: str):
        """
        Unregister a pattern by name.
        
        Args:
            name: Name of the pattern to unregister
        """
        if name in self._patterns:
            del self._patterns[name]
        
        if name in self._instances:
            del self._instances[name]
    
    def get_pattern_class(self, name: str) -> Optional[Type[ComposablePattern]]:
        """
        Get a pattern class by name.
        
        Args:
            name: Name of the pattern
            
        Returns:
            Pattern class or None if not found
        """
        return self._patterns.get(name)
    
    def create_pattern(self, name: str, **kwargs) -> Optional[ComposablePattern]:
        """
        Create an instance of a pattern.
        
        Args:
            name: Name of the pattern
            **kwargs: Arguments to pass to the pattern constructor
            
        Returns:
            Pattern instance or None if not found
        """
        pattern_class = self._patterns.get(name)
        if not pattern_class:
            return None
        
        instance = pattern_class(**kwargs)
        self._instances[name] = instance
        return instance
    
    def get_pattern(self, name: str) -> Optional[ComposablePattern]:
        """
        Get an existing instance of a pattern or create a new one.
        
        Args:
            name: Name of the pattern
            
        Returns:
            Pattern instance or None if not found
        """
        if name in self._instances:
            return self._instances[name]
        
        return self.create_pattern(name)
    
    def list_patterns(self) -> List[str]:
        """
        List all registered pattern names.
        
        Returns:
            List of pattern names
        """
        return list(self._patterns.keys())
    
    def load_pattern_from_module(self, name: str, module_path: str, class_name: str):
        """
        Dynamically load a pattern from a module.
        
        Args:
            name: Name to register the pattern under
            module_path: Path to the module containing the pattern
            class_name: Name of the pattern class in the module
        """
        module = importlib.import_module(module_path)
        pattern_class = getattr(module, class_name)
        
        if not issubclass(pattern_class, ComposablePattern):
            raise ValueError(f"{pattern_class} is not a subclass of ComposablePattern")
        
        self.register_pattern(name, pattern_class)
    
    def register_domain_pattern(self, domain: str, pattern_name: str, pattern_class: Type[ComposablePattern]):
        """
        Register a domain-specific pattern.
        
        Args:
            domain: Domain name (e.g., 'code_analysis', 'database_query', 'research')
            pattern_name: Name of the pattern
            pattern_class: Class of the pattern to register
        """
        full_name = f"{domain}.{pattern_name}"
        self.register_pattern(full_name, pattern_class)
    
    def get_domain_patterns(self, domain: str) -> List[str]:
        """
        Get all patterns for a specific domain.
        
        Args:
            domain: Domain name
            
        Returns:
            List of pattern names for the domain
        """
        return [name for name in self.list_patterns() if name.startswith(f"{domain}.")]
    
    def get_universal_patterns(self) -> List[str]:
        """
        Get all universal patterns (not tied to a specific domain).
        
        Returns:
            List of universal pattern names
        """
        return [name for name in self.list_patterns() if '.' not in name]