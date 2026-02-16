#!/usr/bin/env python3
"""
Скрипт для создания всех необходимых файлов промптов и контрактов в правильной структуре.
"""
import os
import shutil
from pathlib import Path
import yaml

def create_all_necessary_files():
    """Создание всех необходимых файлов промптов и контрактов."""
    
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"[ERROR] Папка {data_dir} не найдена!")
        return
    
    # Загрузим registry.yaml для получения информации о типах
    registry_path = Path("registry.yaml")
    if not registry_path.exists():
        print(f"[ERROR] Файл {registry_path} не найден!")
        return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} типов capability из registry.yaml")
    
    # Создаем новую структуру папок
    new_structure = {
        'prompts': ['skill', 'tool', 'service', 'behavior'],
        'contracts': ['skill', 'tool', 'service', 'behavior']
    }
    
    for parent_dir, subdirs in new_structure.items():
        parent_path = data_dir / parent_dir
        parent_path.mkdir(exist_ok=True)
        
        for subdir in subdirs:
            # Создаем подкаталоги для каждого типа
            (parent_path / subdir).mkdir(exist_ok=True)
            
            # В каждом подкаталоге создаем подкаталоги для capability_base
            for capability, comp_type in capability_types.items():
                if comp_type == subdir:
                    cap_parts = capability.split('.')
                    if len(cap_parts) >= 2:
                        cap_main = cap_parts[0]
                        (parent_path / subdir / cap_main).mkdir(exist_ok=True)
    
    print("[INFO] Создана новая структура папок")
    
    # Создаем файлы промптов для всех capability
    for capability, comp_type in capability_types.items():
        cap_parts = capability.split('.')
        if len(cap_parts) >= 2:
            cap_main = cap_parts[0]
            
            # Создаем файл промпта
            prompt_dir = data_dir / 'prompts' / comp_type / cap_main
            prompt_file = prompt_dir / f"{capability}_v1.0.0.yaml"
            
            # Определяем пример содержимого промпта в зависимости от capability
            prompt_examples = {
                'planning.create_plan': 'Create a detailed plan to achieve the goal: {goal}',
                'book_library.search_books': 'Search for books based on criteria: {criteria}',
                'sql_generation.generate_query': 'Generate SQL query for: {request}',
                'behavior.planning': 'Plan the next step based on current state: {state}',
                'behavior.react': 'Think about the situation: {situation}',
                'behavior.planning.decompose': 'Decompose the task: {task} into smaller steps',
                'behavior.planning.sequence': 'Sequence the steps for: {steps}',
                'behavior.react.act': 'Take action based on thought: {thought}',
                'behavior.react.observe': 'Observe the result of action: {action}',
                'behavior.react.think': 'Think about observation: {observation}'
            }
            
            prompt_content = {
                'capability': capability,
                'version': 'v1.0.0',
                'status': 'active',
                'component_type': comp_type,
                'content': prompt_examples.get(capability, f'Default prompt for {capability}: {{{"input"}}}'),
                'variables': [
                    {
                        'name': 'input',
                        'description': 'Main input for the prompt',
                        'required': True
                    }
                ],
                'metadata': {
                    'description': f'Prompt for {capability}',
                    'author': 'system',
                    'created': '2026-02-15'
                }
            }
            
            # Добавляем специфические переменные для некоторых capability
            if capability == 'planning.create_plan':
                prompt_content['variables'] = [
                    {'name': 'goal', 'description': 'Target goal to plan for', 'required': True},
                    {'name': 'context', 'description': 'Additional context', 'required': False}
                ]
                prompt_content['content'] = '''You are a planning module for an agent system.
Your task is to create an initial action plan to achieve the goal.

AVAILABLE SYSTEM CAPABILITIES:
{{ capabilities_list }}

INSTRUCTIONS:
1. BUILD a plan from scratch based on the goal
2. BREAK the plan into specific, executable steps
3. CONSIDER available system capabilities when choosing actions
4. MAKE steps sequential and logical
5. INCLUDE realistic time estimates for each step
6. CONSIDER system limitations (maximum {{ max_steps }} steps)

GOAL:
{{ goal }}

ADDITIONAL CONTEXT:
{{ context }}

Return the plan in structured format.'''
            elif capability == 'book_library.search_books':
                prompt_content['variables'] = [
                    {'name': 'query', 'description': 'Search query', 'required': True},
                    {'name': 'max_results', 'description': 'Maximum number of results', 'required': False}
                ]
                prompt_content['content'] = '''Search for books based on the query: {{ query }}

Return up to {{ max_results|default(10) }} most relevant results.'''
            elif capability == 'sql_generation.generate_query':
                prompt_content['variables'] = [
                    {'name': 'natural_language_request', 'description': 'Request in natural language', 'required': True},
                    {'name': 'table_schema', 'description': 'Database schema', 'required': True}
                ]
                prompt_content['content'] = '''Generate a SQL query for the following request:
{{ natural_language_request }}

Using the database schema:
{{ table_schema }}

Return only the SQL query without any explanation.'''
            
            with open(prompt_file, 'w', encoding='utf-8') as f:
                yaml.dump(prompt_content, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            print(f"[INFO] Создан промпт: {prompt_file}")
    
    # Создаем файлы контрактов для всех capability
    for capability, comp_type in capability_types.items():
        cap_parts = capability.split('.')
        if len(cap_parts) >= 2:
            cap_main = cap_parts[0]
            
            # Создаем файлы контрактов (input и output)
            contract_dir = data_dir / 'contracts' / comp_type / cap_main
            
            for direction in ['input', 'output']:
                contract_file = contract_dir / f"{capability}_{direction}_v1.0.0.yaml"
                
                # Определяем пример схемы в зависимости от capability и направления
                if direction == 'input':
                    if capability == 'planning.create_plan':
                        schema_properties = {
                            'goal': {'type': 'string', 'description': 'Target goal to plan for'},
                            'context': {'type': 'string', 'description': 'Additional context', 'default': ''},
                            'capabilities_list': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Available capabilities'}
                        }
                        required_fields = ['goal']
                    elif capability == 'book_library.search_books':
                        schema_properties = {
                            'query': {'type': 'string', 'description': 'Search query'},
                            'max_results': {'type': 'integer', 'description': 'Maximum number of results', 'default': 10}
                        }
                        required_fields = ['query']
                    elif capability == 'sql_generation.generate_query':
                        schema_properties = {
                            'natural_language_request': {'type': 'string', 'description': 'Request in natural language'},
                            'table_schema': {'type': 'string', 'description': 'Database schema'}
                        }
                        required_fields = ['natural_language_request', 'table_schema']
                    else:
                        schema_properties = {
                            'input': {'type': 'string', 'description': f'Input for {capability}'}
                        }
                        required_fields = ['input']
                else:  # output
                    if capability == 'planning.create_plan':
                        schema_properties = {
                            'plan': {'type': 'array', 'items': {'type': 'object', 'properties': {
                                'step': {'type': 'integer', 'description': 'Step number'},
                                'action': {'type': 'string', 'description': 'Action to take'},
                                'estimated_time': {'type': 'string', 'description': 'Estimated time'}
                            }}, 'description': 'Action plan steps'}
                        }
                        required_fields = ['plan']
                    elif capability == 'book_library.search_books':
                        schema_properties = {
                            'results': {'type': 'array', 'items': {'type': 'object', 'properties': {
                                'title': {'type': 'string', 'description': 'Book title'},
                                'author': {'type': 'string', 'description': 'Author name'},
                                'year': {'type': 'integer', 'description': 'Publication year'}
                            }}, 'description': 'Search results'}
                        }
                        required_fields = ['results']
                    elif capability == 'sql_generation.generate_query':
                        schema_properties = {
                            'sql_query': {'type': 'string', 'description': 'Generated SQL query'},
                            'explanation': {'type': 'string', 'description': 'Brief explanation'}
                        }
                        required_fields = ['sql_query']
                    else:
                        schema_properties = {
                            'result': {'type': 'string', 'description': f'Output for {capability}'}
                        }
                        required_fields = ['result']
                
                contract_content = {
                    'capability': capability,
                    'version': 'v1.0.0',
                    'status': 'active',
                    'component_type': comp_type,
                    'direction': direction,
                    'schema_data': {
                        'type': 'object',
                        'properties': schema_properties,
                        'required': required_fields
                    },
                    'description': f'{direction.capitalize()} contract for {capability}'
                }
                
                with open(contract_file, 'w', encoding='utf-8') as f:
                    yaml.dump(contract_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                
                print(f"[INFO] Создан контракт: {contract_file}")
    
    print("[SUCCESS] Создание всех необходимых файлов завершено!")


def verify_created_files():
    """Проверка созданных файлов."""
    data_dir = Path("data")
    
    print("\n[INFO] Проверка созданных файлов:")
    
    total_prompts = 0
    total_contracts = 0
    
    for parent_dir in ['prompts', 'contracts']:
        parent_path = data_dir / parent_dir
        if parent_path.exists():
            print(f"\n  {parent_dir}/:")
            for type_dir in parent_path.iterdir():
                if type_dir.is_dir():
                    print(f"    {type_dir.name}/:")
                    for cap_dir in type_dir.iterdir():
                        if cap_dir.is_dir():
                            files = list(cap_dir.glob("*.yaml"))
                            if files:  # Показываем только папки с файлами
                                print(f"      {cap_dir.name}/: {len(files)} файлов")
                                for i, file in enumerate(files[:5]):  # Показываем первые 5 файлов
                                    print(f"        - {file.name}")
                                    if parent_dir == 'prompts':
                                        total_prompts += 1
                                    else:
                                        total_contracts += 1
                                if len(files) > 5:
                                    print(f"        ... и еще {len(files) - 5} файлов")
    
    print(f"\n[INFO] Всего создано: {total_prompts} промптов, {total_contracts} контрактов")


if __name__ == "__main__":
    print("Начинаем создание всех необходимых файлов...")
    create_all_necessary_files()
    verify_created_files()
    print("\n[SUCCESS] Создание всех необходимых файлов завершено!")