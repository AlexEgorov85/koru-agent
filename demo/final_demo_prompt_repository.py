#!/usr/bin/env python3
"""
Финальная демонстрация работы production-ready PromptRepository
"""
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Добавляем текущую директорию в путь Python для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from domain.models.prompt.prompt_version import (
    PromptVersion, PromptStatus, PromptRole, VariableSchema, PromptUsageMetrics
)
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from domain.models.capability import Capability
from application.services.prompt_renderer import PromptRenderer
from application.services.cached_prompt_repository import CachedPromptRepository
from infrastructure.repositories.prompt_repository import DatabasePromptRepository, DatabaseSnapshotManager


async def demo_prompt_repository_architecture():
    """Демонстрация архитектуры PromptRepository"""
    print("=== Концептуальная демонстрация Production-Ready PromptRepository ===\n")
    
    print("1. Архитектурные компоненты системы:")
    print("   - PromptVersion: Модель данных версии промта")
    print("   - PromptRepository: Абстракция репозитория промтов")
    print("   - DatabasePromptRepository: Реализация с использованием DBProvider")
    print("   - CachedPromptRepository: Кэширующая обертка")
    print("   - PromptRenderer: Рендерер с валидацией переменных")
    print("   - PromptExecutionSnapshot: Снапшоты выполнения")
    
    print("\n2. Демонстрация модели PromptVersion с полным жизненным циклом:")
    
    # Создаем пример версии промта
    test_version = PromptVersion(
        id="prod_example_version_001",
        semantic_version="1.0.0",
        domain=DomainType.PROBLEM_SOLVING,
        provider_type=LLMProviderType.OPENAI,
        capability_name="code_analysis",
        role=PromptRole.SYSTEM,
        content="You are an expert code analyst. Analyze: {{code_snippet}} with goal {{analysis_goal}}",
        variables_schema=[
            VariableSchema(name="code_snippet", type="string", required=True, description="Code snippet for analysis"),
            VariableSchema(name="analysis_goal", type="string", required=True, description="Goal of analysis"),
            VariableSchema(name="context", type="string", required=False, description="Additional context")
        ],
        status=PromptStatus.ACTIVE,
        version_notes="Initialization of production prompt version for code analysis"
    )
    
    print(f"   - ID: {test_version.id}")
    print(f"   - Semantic version: {test_version.semantic_version}")
    print(f"   - Domain: {test_version.domain}")
    print(f"   - Provider: {test_version.provider_type}")
    print(f"   - Capability: {test_version.capability_name}")
    print(f"   - Role: {test_version.role}")
    print(f"   - Status: {test_version.status}")
    print(f"   - Address: {test_version.get_address_key()}")
    print(f"   - Content: {test_version.content}")
    print(f"   - Variables: {[(v.name, v.type, v.required) for v in test_version.variables_schema]}")
    print(f"   - Notes: {test_version.version_notes}")
    
    print("\n3. Demonstration of variable validation:")
    
    # Check validation with correct variables
    validation_result = test_version.validate_variables({
        "code_snippet": "def hello(): pass",
        "analysis_goal": "finding bugs"
    })
    print(f"   - Validation with correct variables: {len(validation_result)} errors")
    
    # Check validation without required variable
    validation_result = test_version.validate_variables({
        "code_snippet": "def hello(): pass"
        # analysis_goal is missing
    })
    print(f"   - Validation without required variable: {len(validation_result)} errors")
    if validation_result:
        for var_name, errors in validation_result.items():
            print(f"     - Variable '{var_name}' error: {errors[0]}")
    
    print("\n4. Schema variables demonstration:")
    
    print("   - Variable schema:")
    for var_schema in test_version.variables_schema:
        required_status = "required" if var_schema.required else "optional"
        print(f"     * {var_schema.name}: {var_schema.type} ({required_status}) - {var_schema.description}")
    
    print("\n5. Lifecycle status demonstration:")
    status_descriptions = {
        PromptStatus.DRAFT: "Draft, not ready for use",
        PromptStatus.ACTIVE: "Active version, used in system",
        PromptStatus.SHADOW: "Shadow version for A/B testing",
        PromptStatus.DEPRECATED: "Deprecated, but still works",
        PromptStatus.ARCHIVED: "Archived, no longer used"
    }
    
    for status, description in status_descriptions.items():
        print(f"   - {status.value}: {description}")
    
    print("\n6. Capability structure demonstration:")
    
    # Create example capability
    example_capability = Capability(
        name="code_analysis",
        description="Code analysis",
        skill_name="code_analysis_skill",
        prompt_versions={
            "openai:system": "prod_example_version_001",
            "openai:user": "user_version_002"
        }
    )
    
    print(f"   - Name: {example_capability.name}")
    print(f"   - Description: {example_capability.description}")
    print(f"   - Skill: {example_capability.skill_name}")
    print(f"   - Version mappings: {example_capability.prompt_versions}")
    
    print("\n7. Execution snapshot demonstration:")
    
    # Create example snapshot
    from domain.models.prompt.prompt_execution_snapshot import PromptExecutionSnapshot
    example_snapshot = PromptExecutionSnapshot(
        id="snapshot_001",
        prompt_id="prod_example_version_001",
        session_id="session_001",
        rendered_prompt="You are an expert code analyst. Analyze: def hello(): pass with goal finding bugs",
        variables={
            "code_snippet": "def hello(): pass",
            "analysis_goal": "finding bugs"
        },
        response="Code looks correct...",
        execution_time=1.25,
        timestamp=datetime.utcnow(),
        success=True,
        error_message=None,
        rejection_reason=None,
        provider_response_time=1.2
    )
    
    print(f"   - Prompt ID: {example_snapshot.prompt_id}")
    print(f"   - Session ID: {example_snapshot.session_id}")
    print(f"   - Rendered prompt: {example_snapshot.rendered_prompt[:100]}...")
    print(f"   - Variables: {list(example_snapshot.variables.keys())}")
    print(f"   - Execution time: {example_snapshot.execution_time}s")
    print(f"   - Success: {example_snapshot.success}")
    print(f"   - Provider response time: {example_snapshot.provider_response_time}s")
    
    print("\n8. Usage metrics demonstration:")
    
    example_metrics = PromptUsageMetrics(
        usage_count=150,
        success_count=142,
        avg_generation_time=1.35,
        last_used_at=datetime.utcnow(),
        error_rate=0.05,
        rejection_count=3
    )
    
    print(f"   - Usage count: {example_metrics.usage_count}")
    print(f"   - Success count: {example_metrics.success_count}")
    print(f"   - Average generation time: {example_metrics.avg_generation_time}s")
    print(f"   - Last used at: {example_metrics.last_used_at}")
    print(f"   - Error rate: {example_metrics.error_rate * 100}%")
    print(f"   - Rejection count: {example_metrics.rejection_count}")
    
    print("\n9. Repository hierarchy:")
    print("   - IPromptRepository (abstraction)")
    print("     + DatabasePromptRepository (implementation with DBProvider)")
    print("       + CachedPromptRepository (caching wrapper)")
    
    print("\n10. Request execution flow:")
    print("   1. Agent -> Capability")
    print("   2. PromptRenderer <- Capability (gets prompt by ID)")
    print("   3. CachedPromptRepository <- Version ID (checks cache)")
    print("   4. DatabasePromptRepository <- Version ID (if not in cache)")
    print("   5. PromptVersion.validate_variables(context)")
    print("   6. Variable substitution in template")
    print("   7. Creation of PromptExecutionSnapshot")
    print("   8. Result -> Agent -> LLM")
    
    print("\n=== Architecture demonstration completed ===")
    print("\nKey features of production-ready PromptRepository:")
    print("  + Full lifecycle (draft -> active -> shadow -> deprecated -> archived)")
    print("  + Strict variable validation by schema")
    print("  + Injection protection via variable checking")
    print("  + Snapshots for debugging and monitoring")
    print("  + Memory caching for high performance")
    print("  + Integration with file system and database")
    print("  + Compatibility with GreenPlum/PostgreSQL")
    print("  + Error handling and fallback mechanisms")
    print("  + Usage metrics and performance tracking")


async def main():
    await demo_prompt_repository_architecture()


if __name__ == "__main__":
    asyncio.run(main())