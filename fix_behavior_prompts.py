import os
import yaml
from pathlib import Path

# Пути к проблемным файлам
problem_files = [
    "data/prompts/behavior/behavior/behavior.planning.decompose_v1.0.0.yaml",
    "data/prompts/behavior/behavior/behavior.planning.sequence_v1.0.0.yaml",
    "data/prompts/behavior/behavior/behavior.planning_v1.0.0.yaml",
    "data/prompts/behavior/behavior/behavior.react.act_v1.0.0.yaml",
    "data/prompts/behavior/behavior/behavior.react.observe_v1.0.0.yaml",
    "data/prompts/behavior/behavior/behavior.react.think_v1.0.0.yaml",
    "data/prompts/behavior/behavior/behavior.react_v1.0.0.yaml"
]

for file_path in problem_files:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Проверяем, есть ли переменная 'input' в объявленных переменных
        variables = data.get('variables', [])
        input_var_exists = any(var.get('name') == 'input' for var in variables)
        
        if input_var_exists:
            # Проверяем, используется ли 'input' в content
            content = data.get('content', '')
            if '{input}' not in content and '{{input}}' not in content and '{{ input }}' not in content:
                print(f"Fixing {file_path}: adding {{input}} to content")
                
                # Добавляем {input} в содержимое
                if 'task' in content:
                    # Если есть переменная task, добавим input рядом
                    data['content'] = content.replace('{task}', '{input} (task: {task})')
                else:
                    # Иначе просто добавим в начало
                    data['content'] = '{input} ' + content
                
                # Сохраняем изменения
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
                print(f"  Fixed: {file_path}")
            else:
                print(f"No issue with {file_path}: input is used")
        else:
            print(f"No 'input' variable in {file_path}")

print("All behavior prompt files checked and fixed if needed.")