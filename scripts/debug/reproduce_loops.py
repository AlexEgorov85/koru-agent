"""
Скрипт воспроизведения зацикливания агента.

Запускает агента и детектирует:
1. Повторяющиеся decision подряд
2. Отсутствие изменений в state snapshot
3. Зацикливание ReAct паттерна
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config.models import SystemConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.agent.factory import AgentFactory
from core.agent.components.state import AgentState


async def test_react_loop():
    """
    Тест 1: ReAct зацикливание.
    
    Запускает агента и отслеживает повторяющиеся decision без изменения state.
    """
    print("=" * 60)
    print("ТЕСТ 1: ReAct зацикливание")
    print("=" * 60)
    
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_context = ApplicationContext(infra, profile='sandbox')
    await app_context.initialize()
    
    factory = AgentFactory(app_context)
    agent = await factory.create_agent(goal="Найди книги Пушкина")
    
    step_log = []
    previous_decision = None
    previous_snapshot = None
    loop_detected = False
    
    for step in range(20):
        decision = await agent.behavior_manager.generate_next_decision(
            session_context=app_context.session_context,
            available_capabilities=app_context.get_all_capabilities()
        )
        
        current_snapshot = agent.state.snapshot()
        
        step_log.append({
            'step': step,
            'decision_action': decision.action.value if decision else None,
            'decision_capability': getattr(decision, 'capability_name', None),
            'state_snapshot': current_snapshot,
            'history_length': len(agent.state.history)
        })
        
        # Проверка повторения
        if previous_decision and decision:
            if (decision.action == previous_decision.action and
                getattr(decision, 'capability_name') == getattr(previous_decision, 'capability_name')):
                if previous_snapshot == current_snapshot:
                    print(f"❌ LOOP DETECTED at step {step}")
                    print(f"   Decision: {decision.action.value}")
                    print(f"   Capability: {getattr(decision, 'capability_name', 'N/A')}")
                    print(f"   Snapshot: {current_snapshot}")
                    loop_detected = True
                    break
        
        previous_decision = decision
        previous_snapshot = current_snapshot
    
    if not loop_detected:
        print("✅ No loops detected in 20 steps")
        print(f"   Steps executed: {len(step_log)}")
        print(f"   Final state: {step_log[-1]['state_snapshot'] if step_log else 'N/A'}")
    
    await infra.shutdown()
    return not loop_detected


async def test_state_mutation():
    """
    Тест 2: Мутация state после observe.
    
    Проверяет что state меняется после каждого шага.
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Мутация state после observe")
    print("=" * 60)
    
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_context = ApplicationContext(infra, profile='sandbox')
    await app_context.initialize()
    
    factory = AgentFactory(app_context)
    agent = await factory.create_agent(goal="Тест мутации state")
    
    snapshots = []
    mutation_failed = False
    
    for step in range(5):
        snapshot_before = agent.state.snapshot()
        
        # Симуляция шага
        decision = await agent.behavior_manager.generate_next_decision(
            session_context=app_context.session_context,
            available_capabilities=app_context.get_all_capabilities()
        )
        
        snapshot_after = agent.state.snapshot()
        snapshots.append(snapshot_after)
        
        # Проверка мутации
        if step > 0 and snapshot_before == snapshot_after:
            print(f"❌ STATE MUTATION FAILED at step {step}")
            print(f"   Snapshot before: {snapshot_before}")
            print(f"   Snapshot after: {snapshot_after}")
            mutation_failed = True
            break
    
    if not mutation_failed:
        print("✅ State mutated successfully in all 5 steps")
        print(f"   Snapshots: {len(snapshots)} unique states")
    
    await infra.shutdown()
    return not mutation_failed


async def test_decision_validation():
    """
    Тест 3: Валидация ACT decision.
    
    Проверяет что ACT decision всегда имеет capability_name.
    """
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Валидация ACT decision")
    print("=" * 60)
    
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_context = ApplicationContext(infra, profile='sandbox')
    await app_context.initialize()
    
    factory = AgentFactory(app_context)
    agent = await factory.create_agent(goal="Тест валидации decision")
    
    invalid_act_detected = False
    
    for step in range(10):
        decision = await agent.behavior_manager.generate_next_decision(
            session_context=app_context.session_context,
            available_capabilities=app_context.get_all_capabilities()
        )
        
        # Проверка ACT decision
        if decision and decision.action.value == "ACT":
            if not getattr(decision, 'capability_name', None):
                print(f"❌ INVALID ACT DECISION at step {step}")
                print(f"   Decision: {decision}")
                print(f"   capability_name: {getattr(decision, 'capability_name', 'MISSING')}")
                invalid_act_detected = True
                break
            else:
                print(f"✅ Step {step}: ACT decision valid, capability={decision.capability_name}")
    
    if not invalid_act_detected:
        print("✅ All ACT decisions have capability_name")
    
    await infra.shutdown()
    return not invalid_act_detected


async def main():
    """Запуск всех тестов воспроизведения."""
    print("\n" + "=" * 60)
    print("ДИAГНОСТИКА ЗАЦИКЛИВАНИЯ AGENT_V5")
    print("=" * 60)
    
    results = {}
    
    # Тест 1: ReAct зацикливание
    results['react_loop'] = await test_react_loop()
    
    # Тест 2: Мутация state
    results['state_mutation'] = await test_state_mutation()
    
    # Тест 3: Валидация decision
    results['decision_validation'] = await test_decision_validation()
    
    # Итоговый отчёт
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    else:
        print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ (требуется стабилизация)")
    print("=" * 60)
    
    return all_passed


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
