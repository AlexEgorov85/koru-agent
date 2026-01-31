"""
Interface for the agent runtime.
"""

from typing import Any, Dict, Optional, Protocol


class AgentRuntimeInterface(Protocol):
    """
    Interface for the agent runtime.
    """
    session: Any  # SessionContext
    system: Any   # SystemContext
    
    async def call_llm_with_params(
        self,
        user_prompt: str,
        system_prompt: str,
        output_schema: Optional[Dict[str, Any]] = None,
        output_format: str = "text",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0
    ):
        """
        Call LLM with specified parameters.
        """
        ...