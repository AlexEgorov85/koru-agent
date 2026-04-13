"""
Скрипт для переименования промптов с добавлением .user для user промптов.

Использование:
    python scripts/rename_prompts.py
"""
import os
from pathlib import Path

PROMPTS_DIR = Path("data/prompts")

# Промпты которые нужно переименовать (old_name → new_name)
PROMPT_RENAMES = {
    # Skills
    "skill/planning/planning_v1.0.0.yaml": "skill/planning/planning.user_v1.0.0.yaml",
    "skill/planning/planning.create_plan_v1.0.0.yaml": "skill/planning/planning.create_plan.user_v1.0.0.yaml",
    "skill/planning/planning.decompose_task_v1.0.0.yaml": "skill/planning/planning.decompose_task.user_v1.0.0.yaml",
    "skill/planning/planning.mark_task_completed_v1.0.0.yaml": "skill/planning/planning.mark_task_completed.user_v1.0.0.yaml",
    "skill/planning/planning.update_plan_v1.0.0.yaml": "skill/planning/planning.update_plan.user_v1.0.0.yaml",
    "skill/data_analysis/data_analysis.analyze_step_data_v1.0.0.yaml": "skill/data_analysis/data_analysis.analyze_step_data.user_v1.0.0.yaml",
    "skill/final_answer/final_answer.generate_v1.0.0.yaml": "skill/final_answer/final_answer.generate.user_v1.0.0.yaml",

    # Services
    "service/contract/contract.service_v1.0.0.yaml": "service/contract/contract.service.user_v1.0.0.yaml",
    "service/sql_generation/sql_generation_v1.0.0.yaml": "service/sql_generation/sql_generation.user_v1.0.0.yaml",
    "service/sql_generation/sql_generation.generate_query_v1.0.0.yaml": "service/sql_generation/sql_generation.generate_query.user_v1.0.0.yaml",

    # Behaviors (уже переименованы, но проверим)
    "behavior/behavior/behavior_v1.0.0.yaml": "behavior/behavior/behavior.user_v1.0.0.yaml",
    "behavior/behavior/behavior.planning_v1.0.0.yaml": "behavior/behavior/behavior.planning.user_v1.0.0.yaml",
    "behavior/behavior/behavior.planning.decompose_v1.0.0.yaml": "behavior/behavior/behavior.planning.decompose.user_v1.0.0.yaml",
    "behavior/behavior/behavior.planning.sequence_v1.0.0.yaml": "behavior/behavior/behavior.planning.sequence.user_v1.0.0.yaml",
    "behavior/behavior/behavior.react_v1.0.0.yaml": "behavior/behavior/behavior.react.user_v1.0.0.yaml",
    "behavior/behavior/behavior.react.act_v1.0.0.yaml": "behavior/behavior/behavior.react.act.user_v1.0.0.yaml",
    "behavior/behavior/behavior.react.observe_v1.0.0.yaml": "behavior/behavior/behavior.react.observe.user_v1.0.0.yaml",
}


def rename_prompts():
    """Переименовывает промпты согласно словарю PROMPT_RENAMES."""
    renamed_count = 0
    
    for old_rel, new_rel in PROMPT_RENAMES.items():
        old_path = PROMPTS_DIR / old_rel
        new_path = PROMPTS_DIR / new_rel
        
        if not old_path.exists():
            print(f"[WARN] Not found: {old_path}")
            continue
        
        # Создаём директорию если нужно
        new_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Переименовываем
        old_path.rename(new_path)
        print(f"[OK] {old_rel} -> {new_rel}")
        renamed_count += 1
    
    print(f"\nRenamed: {renamed_count} files")


if __name__ == "__main__":
    rename_prompts()
