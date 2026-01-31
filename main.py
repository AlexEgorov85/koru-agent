"""
Main entry point for the agent with new architecture support.

This file demonstrates the new architecture with atomic actions and composable patterns.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from core.agent_runtime import ThinkingPatternLoader
from core.agent_runtime.model import StrategyDecisionType
from core.session_context.session_context import SessionContext
from core.system_context.system_context import SystemContext
from core.composable_patterns.base import PatternBuilder
from core.composable_patterns.registry import PatternRegistry


def setup_logging():
    """Setup basic logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def main():
    """Main entry point for the agent."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Initializing agent with new architecture...")
    
    # Initialize system context
    system_context = SystemContext()
    
    # Initialize session context
    session_context = SessionContext()
    
    # Initialize pattern loader with new architecture enabled
    pattern_loader = ThinkingPatternLoader(use_new_architecture=True)
    
    # Demonstrate the new architecture features
    
    # 1. Show available domains
    domain_manager = pattern_loader.get_domain_manager()
    available_domains = domain_manager.get_available_domains()
    logger.info(f"Available domains: {available_domains}")
    
    # 2. Show pattern registry
    pattern_registry = pattern_loader.get_pattern_registry()
    all_patterns = pattern_registry.list_patterns()
    logger.info(f"All registered patterns: {all_patterns}")
    
    # 3. Demonstrate dynamic pattern creation with PatternBuilder
    logger.info("\nCreating custom pattern with PatternBuilder...")
    builder = PatternBuilder("custom_analysis", "Custom analysis pattern")
    custom_pattern = (
        builder
        .add_think()
        .add_observe()
        .add_act()
        .add_reflect()
        .build()
    )
    
    logger.info(f"Created custom pattern with {len(custom_pattern.actions)} actions")
    
    # 4. Demonstrate domain adaptation
    sample_tasks = [
        "Analyze the code in file.py for potential bugs",
        "Write a SQL query to find users with pending orders",
        "Research best practices for Python async programming"
    ]
    
    for task in sample_tasks:
        logger.info(f"\nAdapting to task: {task}")
        adaptation_result = pattern_loader.adapt_to_task(task)
        logger.info(f"  Domain: {adaptation_result['domain']}")
        logger.info(f"  Pattern: {adaptation_result['pattern']}")
        
        # Show domain-specific tools
        domain_tools = domain_manager.get_domain_tools(adaptation_result['domain'])
        logger.info(f"  Available tools: {domain_tools}")
    
    # 5. Demonstrate using a composable pattern
    logger.info("\nUsing composable ReAct pattern...")
    react_pattern = pattern_registry.create_pattern("react_composable")
    if react_pattern:
        logger.info(f"Created {react_pattern.name}: {react_pattern.description}")
        logger.info(f"Number of actions in pattern: {len(react_pattern.actions)}")
    
    # 6. Demonstrate creating a domain-specific pattern
    logger.info("\nRegistering and using domain-specific pattern...")
    code_analysis_pattern = pattern_registry.get_pattern("code_analysis.default")
    if code_analysis_pattern:
        logger.info(f"Retrieved domain pattern: {code_analysis_pattern.name}")
    
    # 7. Backward compatibility: show traditional patterns still work
    logger.info("\nNew architecture initialized successfully!")
    logger.info("Key features demonstrated:")
    logger.info("  - Atomic actions (THINK, ACT, OBSERVE, PLAN, REFLECT, EVALUATE, VERIFY, ADAPT)")
    logger.info("  - Composable patterns built from atomic actions")
    logger.info("  - Pattern registry for management")
    logger.info("  - Domain management and adaptation")
    logger.info("  - Dynamic pattern creation with PatternBuilder")


if __name__ == "__main__":
    asyncio.run(main())