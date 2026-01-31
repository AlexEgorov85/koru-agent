"""
Domain manager for handling different domains and adapting behavior accordingly.
"""

from typing import Dict, List, Optional, Any
import logging


logger = logging.getLogger(__name__)


class DomainManager:
    """
    Manages different domains and provides domain-specific configurations.
    
    The DomainManager handles:
    - Domain identification and classification
    - Domain-specific configurations and settings
    - Prompt adaptation based on domain
    - Tool selection based on domain
    """
    
    def __init__(self):
        self.domains: Dict[str, Dict[str, Any]] = {}
        self.current_domain: Optional[str] = None
        self.domain_context: Dict[str, Any] = {}
        
        # Initialize with default domains
        self._initialize_default_domains()
    
    def _initialize_default_domains(self):
        """Initialize default domains with their configurations."""
        default_domains = {
            "general": {
                "name": "General Purpose",
                "description": "Default domain for general tasks",
                "default_pattern": "react",
                "tools": ["file_reader", "file_writer", "project_navigator"],
                "prompt_templates": {
                    "system": "You are a general-purpose assistant.",
                    "user": "Help me with: {query}"
                }
            },
            "code_analysis": {
                "name": "Code Analysis",
                "description": "Domain for code-related tasks",
                "default_pattern": "code_analysis",
                "tools": ["file_reader", "file_writer", "ast_parser", "project_navigator"],
                "prompt_templates": {
                    "system": "You are a code analysis expert. Analyze the provided code focusing on structure, patterns, and potential issues.",
                    "user": "Analyze the following code: {query}"
                }
            },
            "database_query": {
                "name": "Database Query",
                "description": "Domain for database-related tasks",
                "default_pattern": "database_query",
                "tools": ["sql_tool", "file_reader", "project_navigator"],
                "prompt_templates": {
                    "system": "You are a database expert. Help with SQL queries and database operations.",
                    "user": "Help with database query: {query}"
                }
            },
            "research": {
                "name": "Research",
                "description": "Domain for research and information gathering",
                "default_pattern": "research",
                "tools": ["file_reader", "project_navigator", "web_search"],
                "prompt_templates": {
                    "system": "You are a research assistant. Gather and synthesize information from available sources.",
                    "user": "Research the following topic: {query}"
                }
            }
        }
        
        for domain_name, config in default_domains.items():
            self.register_domain(domain_name, config)
    
    def register_domain(self, name: str, config: Dict[str, Any]):
        """
        Register a new domain with its configuration.
        
        Args:
            name: Name of the domain
            config: Configuration dictionary for the domain
        """
        self.domains[name] = config
        logger.info(f"Registered domain: {name}")
    
    def unregister_domain(self, name: str):
        """
        Unregister a domain.
        
        Args:
            name: Name of the domain to unregister
        """
        if name in self.domains:
            del self.domains[name]
            if self.current_domain == name:
                self.current_domain = None
            logger.info(f"Unregistered domain: {name}")
    
    def set_current_domain(self, domain: str):
        """
        Set the current domain for the agent.
        
        Args:
            domain: Name of the domain to set as current
        """
        if domain not in self.domains:
            raise ValueError(f"Domain '{domain}' is not registered")
        
        self.current_domain = domain
        logger.info(f"Set current domain to: {domain}")
    
    def get_current_domain(self) -> Optional[str]:
        """
        Get the current domain.
        
        Returns:
            Current domain name or None if not set
        """
        return self.current_domain
    
    def get_domain_config(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific domain.
        
        Args:
            domain: Name of the domain
            
        Returns:
            Domain configuration or None if domain not found
        """
        return self.domains.get(domain)
    
    def get_available_domains(self) -> List[str]:
        """
        Get list of all available domains.
        
        Returns:
            List of domain names
        """
        return list(self.domains.keys())
    
    def classify_task(self, task_description: str) -> str:
        """
        Classify a task to the most appropriate domain.
        
        Args:
            task_description: Description of the task to classify
            
        Returns:
            Domain name that best fits the task
        """
        task_lower = task_description.lower()
        
        # Simple keyword-based classification
        if any(keyword in task_lower for keyword in ["code", "function", "class", "method", "variable", "debug", "refactor", "implement"]):
            return "code_analysis"
        elif any(keyword in task_lower for keyword in ["database", "sql", "query", "table", "schema", "db"]):
            return "database_query"
        elif any(keyword in task_lower for keyword in ["find", "research", "information", "learn", "study", "analyze"]):
            return "research"
        else:
            return "general"
    
    def get_domain_tools(self, domain: Optional[str] = None) -> List[str]:
        """
        Get tools available for a specific domain.
        
        Args:
            domain: Domain name (uses current domain if not specified)
            
        Returns:
            List of tool names for the domain
        """
        if domain is None:
            domain = self.current_domain
        
        if domain and domain in self.domains:
            return self.domains[domain].get("tools", [])
        else:
            return self.domains["general"]["tools"] if "general" in self.domains else []
    
    def get_domain_pattern(self, domain: Optional[str] = None) -> str:
        """
        Get default pattern for a specific domain.
        
        Args:
            domain: Domain name (uses current domain if not specified)
            
        Returns:
            Default pattern name for the domain
        """
        if domain is None:
            domain = self.current_domain
        
        if domain and domain in self.domains:
            return self.domains[domain].get("default_pattern", "react")
        else:
            return "react"  # Default pattern
    
    def set_domain_context(self, context: Dict[str, Any], domain: Optional[str] = None):
        """
        Set context for a specific domain.
        
        Args:
            context: Context dictionary to set
            domain: Domain name (uses current domain if not specified)
        """
        if domain is None:
            domain = self.current_domain
        
        if domain:
            self.domain_context[domain] = context
        else:
            # Use a default key if no domain is set
            self.domain_context["default"] = context
    
    def get_domain_context(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Get context for a specific domain.
        
        Args:
            domain: Domain name (uses current domain if not specified)
            
        Returns:
            Context dictionary for the domain
        """
        if domain is None:
            domain = self.current_domain
        
        if domain and domain in self.domain_context:
            return self.domain_context[domain]
        else:
            return self.domain_context.get("default", {})
    
    def adapt_to_task(self, task_description: str) -> str:
        """
        Automatically adapt to a task by setting the appropriate domain.
        
        Args:
            task_description: Description of the task to adapt to
            
        Returns:
            The domain that was set
        """
        domain = self.classify_task(task_description)
        self.set_current_domain(domain)
        return domain