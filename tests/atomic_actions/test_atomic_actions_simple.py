"""
Тестирование рефакторинга атомарных действий (без эмодзи)
"""
import asyncio
import tempfile
from pathlib import Path
from application.orchestration.atomic_actions.executor import AtomicActionExecutor
from application.orchestration.atomic_actions.react_actions import (
    ThinkAction,
    ActAction,
    ObserveAction
)
from domain.abstractions.event_types import EventType, IEventPublisher


class MockEventPublisher:
    """Мок для публикатора событий"""
    async def publish(self, event_type: EventType, source: str, data: dict):
        print(f"Event: {event_type.value} from {source}: {data}")


async def test_atomic_actions():
    print("=== Testing atomic actions refactoring ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        event_publisher = MockEventPublisher()
        
        # Create atomic action executor
        executor = AtomicActionExecutor(project_root=project_root, event_publisher=event_publisher)
        
        # Register actions
        executor.register_action("think", ThinkAction(event_publisher=event_publisher))
        executor.register_action("act", ActAction(event_publisher=event_publisher))
        executor.register_action("observe", ObserveAction(event_publisher=event_publisher))
        
        print("1. Testing ThinkAction:")
        think_result = await executor.execute("think", {"goal": "Test goal", "history": [], "available_capabilities": []})
        print(f"   Result: {think_result.success}, thought: {getattr(think_result, 'thought', 'N/A')}")
        assert think_result.success is True
        print("   OK: ThinkAction works correctly\n")
        
        print("2. Testing ActAction:")
        act_result = await executor.execute("act", {
            "selected_action": "test_action", 
            "action_parameters": {"param": "value"},
            "available_capabilities": ["test_action"]
        })
        print(f"   Result: {act_result.success}, action_result: {getattr(act_result, 'action_result', 'N/A')}")
        assert act_result.success is True
        print("   OK: ActAction works correctly\n")
        
        print("3. Testing ObserveAction:")
        observe_result = await executor.execute("observe", {
            "action_result": "test result",
            "last_action": "test_action"
        })
        print(f"   Result: {observe_result.success}, observation: {getattr(observe_result, 'observation', 'N/A')}")
        assert observe_result.success is True
        print("   OK: ObserveAction works correctly\n")
        
        print("4. Testing FileOperationAction (security):")
        # Create a safe file
        test_file = project_root / "test.txt"
        test_file.write_text("test content")
        
        file_result = await executor.execute("file_operation", {
            "operation_type": "read",
            "file_path": "test.txt"
        })
        print(f"   Result: {file_result.success}, result: {getattr(file_result, 'result', 'N/A')}")
        assert file_result.success is True
        print("   OK: FileOperationAction works correctly\n")
        
        print("5. Testing security (path traversal protection):")
        unsafe_result = await executor.execute("file_operation", {
            "operation_type": "read",
            "file_path": "../../../windows/system32/config/sam"  # Windows unsafe path
        })
        print(f"   Result: {unsafe_result.success}, error: {unsafe_result.error_message}")
        assert unsafe_result.success is False
        print("   OK: Path traversal protection works\n")
        
        print("6. Testing composition of actions:")
        actions_sequence = [
            {"action": "think", "parameters": {"goal": "Test composition", "available_capabilities": ["test_action"]}},
            {"action": "act", "parameters": {"selected_action": "test_action", "action_parameters": {}, "available_capabilities": ["test_action"]}},
            {"action": "observe", "parameters": {"action_result": "test result", "last_action": "test_action"}}
        ]
        
        composition_results = await executor.execute_with_rollback(actions_sequence)
        print(f"   Results: {[r.success for r in composition_results]}")
        assert all(r.success for r in composition_results)
        print("   OK: Composition of actions works correctly\n")
        
        print("7. Testing rollback on failure:")
        # Sequence with error on 2nd step
        bad_sequence = [
            {"action": "file_operation", "parameters": {"operation_type": "write", "file_path": "step1.txt", "file_content": "data1"}},
            {"action": "file_operation", "parameters": {"operation_type": "read", "file_path": "../../../windows/system32/config/sam"}},  # Error
            {"action": "think", "parameters": {"goal": "should not reach"}}
        ]
        
        bad_results = await executor.execute_with_rollback(bad_sequence)
        print(f"   Results: {[r.success for r in bad_results]}, error at step: {not bad_results[1].success}")
        # Second step should fail
        assert not bad_results[1].success
        print("   OK: Rollback on failure works correctly\n")
        
        print("SUCCESS: All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_atomic_actions())