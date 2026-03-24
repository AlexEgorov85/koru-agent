#!/usr/bin/env python3
"""Анализ сессий для понимания проблемы с traces"""
import json
from pathlib import Path

sessions_dir = Path('data/logs/sessions')

print("="*70)
print("АНАЛИЗ СЕССИЙ")
print("="*70)

for session_dir in sorted(sessions_dir.iterdir(), reverse=True)[:10]:
    jsonl_file = session_dir / 'session.jsonl'
    if not jsonl_file.exists():
        continue
    
    metrics = []
    llm_events = []
    capabilities = set()
    
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                event_type = event.get('event_type', '')
                
                if event_type == 'metric.collected':
                    metrics.append(event)
                    cap = event.get('capability', 'unknown')
                    if cap != 'unknown':
                        capabilities.add(cap)
                
                if event_type in ('llm.prompt.generated', 'llm.response.received'):
                    llm_events.append(event)
            except:
                pass
    
    print(f"\n{session_dir.name}:")
    print(f"  Metric events: {len(metrics)}")
    print(f"  LLM events: {len(llm_events)}")
    print(f"  Capabilities: {list(capabilities)}")
    
    # Показать распределение метрик по capability
    if metrics:
        cap_counts = {}
        for m in metrics:
            cap = m.get('capability', 'unknown')
            cap_counts[cap] = cap_counts.get(cap, 0) + 1
        print(f"  Metrics by capability: {cap_counts}")
