"""
Test script to verify the atomic actions refactoring
"""
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

async def test_atomic_actions():
    print("Testing atomic actions refactoring...")
    
    # Test imports work correctly
    from application.orchestration.atomic_actions.executor import AtomicActionExecutor
    from application.orchestration.atomic_actions.react_actions import (
        ThinkAction, 
        ActAction, 
        ObserveAction
    )
    from domain.models.atomic_action.types import AtomicActionType
    from domain.abstractions.event_types import EventType
    
    # Create mock event publisher
    mock_event_publisher = AsyncMock()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        
        # Create executor
        executor = AtomicActionExecutor(event_publisher=mock_event_publisher)
        
        # Register actions
        executor.register_action(ThinkAction(event_publisher=mock_event_publisher))
        executor.register_action(ActAction(event_publisher=mock_event_publisher))
        executor.register_action(ObserveAction(event_publisher=mock_event_publisher))
        
        print("[OK] Actions registered successfully")
        
        # Test individual execution
        print("\n1. Testing ThinkAction execution...")
        think_result = await executor.execute(
            AtomicActionType.THINK, 
            {"goal": "Test goal", "history": [], "available_capabilities": []}
        )
        print(f"   Result: success={think_result.success}, type={think_result.action_type}")
        assert think_result.success is True
        print("   [OK] ThinkAction works correctly")
        
        print("\n2. Testing ActAction execution...")
        act_result = await executor.execute(
            AtomicActionType.ACT,
            {
                "selected_action": "test_action", 
                "action_parameters": {},
                "available_capabilities": ["test_action"]
            }
        )
        print(f"   Result: success={act_result.success}, type={act_result.action_type}")
        assert act_result.success is True
        print("   [OK] ActAction works correctly")
        
        print("\n3. Testing ObserveAction execution...")
        observe_result = await executor.execute(
            AtomicActionType.OBSERVE,
            {"action_result": "test result", "last_action": "test_action"}
        )
        print(f"   Result: success={observe_result.success}, type={observe_result.action_type}")
        assert observe_result.success is True
        print("   [OK] ObserveAction works correctly")
        
        print("\n4. Testing sequence execution...")
        sequence = [
            {"action_type": "think", "parameters": {"goal": "Sequence test", "available_capabilities": []}},
            {"action_type": "act", "parameters": {"selected_action": "test", "action_parameters": {}, "available_capabilities": ["test"]}},
            {"action_type": "observe", "parameters": {"action_result": "seq result", "last_action": "test"}}
        ]
        
        sequence_results = await executor.execute_sequence(sequence, rollback_on_failure=True)
        print(f"   Results: {[r.success for r in sequence_results]}")
        assert len(sequence_results) == 3
        assert all(r.success for r in sequence_results)
        print("   [OK] Sequence execution works correctly")
        
        print("\n[SUCCESS] All tests passed! Atomic actions refactoring is working correctly.")

if __name__ == "__main__":
    asyncio.run(test_atomic_actions())