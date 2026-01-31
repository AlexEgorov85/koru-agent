"""
Prompt adapter for modifying prompts based on domain context.
"""

from typing import Dict, Any, Optional
import logging


logger = logging.getLogger(__name__)


class PromptAdapter:
    """
    Adapts prompts based on domain context and task requirements.
    
    The PromptAdapter handles:
    - Modifying system and user prompts based on domain
    - Injecting domain-specific context into prompts
    - Managing prompt templates for different scenarios
    """
    
    def __init__(self):
        self.domain_prompts: Dict[str, Dict[str, str]] = {}
        self.context_variables: Dict[str, Any] = {}
    
    def set_domain_prompts(self, domain: str, prompts: Dict[str, str]):
        """
        Set prompt templates for a specific domain.
        
        Args:
            domain: Domain name
            prompts: Dictionary of prompt templates (e.g., {"system": "...", "user": "..."})
        """
        self.domain_prompts[domain] = prompts
        logger.info(f"Set prompt templates for domain: {domain}")
    
    def get_domain_prompt(self, domain: str, prompt_type: str, default: str = "") -> str:
        """
        Get a specific prompt template for a domain.
        
        Args:
            domain: Domain name
            prompt_type: Type of prompt ("system", "user", etc.)
            default: Default value if prompt not found
            
        Returns:
            Prompt template for the domain
        """
        return self.domain_prompts.get(domain, {}).get(prompt_type, default)
    
    def adapt_prompt(self, prompt: str, domain: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Adapt a prompt by replacing placeholders with domain-specific values.
        
        Args:
            prompt: Original prompt with placeholders
            domain: Domain name to adapt for
            context: Additional context to inject
            
        Returns:
            Adapted prompt with placeholders replaced
        """
        adapted_prompt = prompt
        
        # Replace domain-specific variables if domain is provided
        if domain:
            # Get domain-specific context
            domain_context = self.get_domain_context(domain)
            if context:
                domain_context.update(context)
            
            # Replace variables in the prompt
            for key, value in domain_context.items():
                placeholder = f"{{{key}}}"
                if placeholder in adapted_prompt:
                    adapted_prompt = adapted_prompt.replace(placeholder, str(value))
        
        # Replace general context variables if provided
        if context:
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                if placeholder in adapted_prompt:
                    adapted_prompt = adapted_prompt.replace(placeholder, str(value))
        
        return adapted_prompt
    
    def adapt_system_prompt(self, domain: str, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Adapt the system prompt for a specific domain.
        
        Args:
            domain: Domain name
            additional_context: Additional context to inject into the prompt
            
        Returns:
            Adapted system prompt
        """
        system_prompt = self.get_domain_prompt(domain, "system", "You are an AI assistant.")
        
        # Add domain-specific instructions
        if domain == "code_analysis":
            system_prompt += "\n\nFocus on code structure, patterns, and potential issues. Provide specific examples and suggestions for improvement."
        elif domain == "database_query":
            system_prompt += "\n\nFocus on SQL best practices, query optimization, and database design principles."
        elif domain == "research":
            system_prompt += "\n\nFocus on gathering reliable information, citing sources, and providing comprehensive analysis."
        
        # Apply context adaptation
        context = additional_context or {}
        return self.adapt_prompt(system_prompt, domain, context)
    
    def adapt_user_prompt(self, user_input: str, domain: str, additional_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Adapt the user prompt for a specific domain.
        
        Args:
            user_input: Original user input
            domain: Domain name
            additional_context: Additional context to inject into the prompt
            
        Returns:
            Adapted user prompt
        """
        # Get domain-specific user prompt template
        user_prompt_template = self.get_domain_prompt(domain, "user", "{query}")
        
        # Format the template with user input
        if "{query}" in user_prompt_template:
            formatted_prompt = user_prompt_template.format(query=user_input)
        else:
            # If no {query} placeholder, append user input to template
            formatted_prompt = f"{user_prompt_template} {user_input}".strip()
        
        # Apply context adaptation
        context = additional_context or {}
        return self.adapt_prompt(formatted_prompt, domain, context)
    
    def get_domain_context(self, domain: str) -> Dict[str, Any]:
        """
        Get domain-specific context variables.
        
        Args:
            domain: Domain name
            
        Returns:
            Dictionary of context variables for the domain
        """
        context = {}
        
        # Add general domain information
        context["domain"] = domain
        context["domain_upper"] = domain.upper()
        context["domain_title"] = domain.replace("_", " ").title()
        
        # Add domain-specific variables
        if domain == "code_analysis":
            context.update({
                "focus_area": "code structure and quality",
                "output_style": "Provide specific examples and improvement suggestions",
                "important_aspects": "patterns, readability, maintainability"
            })
        elif domain == "database_query":
            context.update({
                "focus_area": "SQL queries and database operations",
                "output_style": "Provide optimized queries and best practices",
                "important_aspects": "performance, correctness, security"
            })
        elif domain == "research":
            context.update({
                "focus_area": "information gathering and analysis",
                "output_style": "Provide comprehensive analysis with sources",
                "important_aspects": "reliability, relevance, completeness"
            })
        
        return context
    
    def register_context_variable(self, name: str, value: Any):
        """
        Register a global context variable.
        
        Args:
            name: Name of the variable
            value: Value of the variable
        """
        self.context_variables[name] = value
    
    def get_context_variable(self, name: str, default: Any = None) -> Any:
        """
        Get a global context variable.
        
        Args:
            name: Name of the variable
            default: Default value if variable not found
            
        Returns:
            Value of the context variable
        """
        return self.context_variables.get(name, default)
    
    def create_adaptive_prompt(self, base_prompt: str, domain: str, 
                             user_input: str, 
                             additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Create a fully adaptive prompt pair for a specific domain and input.
        
        Args:
            base_prompt: Base prompt to adapt
            domain: Domain name
            user_input: User's input/query
            additional_context: Additional context to inject
            
        Returns:
            Dictionary with "system" and "user" keys containing adapted prompts
        """
        system_prompt = self.adapt_system_prompt(domain, additional_context)
        user_prompt = self.adapt_user_prompt(user_input, domain, additional_context)
        
        return {
            "system": system_prompt,
            "user": user_prompt
        }