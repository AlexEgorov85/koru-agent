#!/usr/bin/env python3
"""
Скрипт для создания всех недостающих файлов промптов и контрактов.
"""
import yaml
from pathlib import Path

def create_missing_files():
    """Создание всех недостающих файлов промптов и контрактов."""
    
    data_dir = Path("data")
    registry_path = Path("registry.yaml")
    
    # Загрузим registry для получения информации о типах
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} типов capability из registry.yaml")
    
    # Список capability, для которых нужно создать файлы
    missing_capabilities = [
        'sql_generation.generate_query',
        'book_library.search_books',  # Уже есть, но добавим для полноты
        'planning.create_plan',       # Уже есть, но добавим для полноты
        'behavior.planning.decompose',
        'behavior.planning.sequence',
        'behavior.react.act',
        'behavior.react.observe',
        'behavior.react.think'
    ]
    
    # Создаем промпты для всех capability
    for capability in missing_capabilities:
        if capability in capability_types:
            comp_type = capability_types[capability]
            cap_parts = capability.split('.')
            if len(cap_parts) >= 2:
                cap_main = cap_parts[0]
                
                # Создаем директорию
                prompt_dir = data_dir / "prompts" / comp_type / cap_main
                prompt_dir.mkdir(parents=True, exist_ok=True)
                
                # Создаем файл промпта
                prompt_file = prompt_dir / f"{capability}_v1.0.0.yaml"
                
                if not prompt_file.exists():  # Создаем только если файл не существует
                    # Определяем содержимое в зависимости от capability
                    if capability == 'sql_generation.generate_query':
                        content = '''Generate a SQL query for the following request:
{{ natural_language_request }}

Using the database schema:
{{ table_schema }}

Return only the SQL query without any explanation.'''
                        variables = [
                            {'name': 'natural_language_request', 'description': 'Request in natural language', 'required': True},
                            {'name': 'table_schema', 'description': 'Database schema', 'required': True}
                        ]
                    elif capability == 'book_library.search_books':
                        content = '''Search for books based on the query: {{ query }}

Return up to {{ max_results|default(10) }} most relevant results.'''
                        variables = [
                            {'name': 'query', 'description': 'Search query', 'required': True},
                            {'name': 'max_results', 'description': 'Maximum number of results', 'required': False}
                        ]
                    elif capability == 'planning.create_plan':
                        content = '''You are a planning module for an agent system.
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
                        variables = [
                            {'name': 'goal', 'description': 'Target goal to plan for', 'required': True},
                            {'name': 'context', 'description': 'Additional context', 'required': False},
                            {'name': 'capabilities_list', 'description': 'Available system capabilities', 'required': True},
                            {'name': 'max_steps', 'description': 'Maximum number of steps allowed', 'required': True}
                        ]
                    elif capability.startswith('behavior.planning'):
                        content = f'''Behavior implementation for {capability}:
{{{{ input }}}}

Process the input according to the behavior pattern and return appropriate response.'''
                        variables = [
                            {'name': 'input', 'description': 'Input for the behavior', 'required': True}
                        ]
                    elif capability.startswith('behavior.react'):
                        content = f'''REACT pattern implementation for {capability}:
OBSERVE: {{{{ observation }}}}
THINK: {{{{ thought }}}}
ACT: {{{{ action }}}}

Process according to REACT methodology.'''
                        variables = [
                            {'name': 'observation', 'description': 'Current observation', 'required': True},
                            {'name': 'thought', 'description': 'Current thought', 'required': True},
                            {'name': 'action', 'description': 'Current action', 'required': True}
                        ]
                    else:
                        content = f'Default prompt for {capability}: {{{{ input }}}} '
                        variables = [
                            {'name': 'input', 'description': 'Main input', 'required': True}
                        ]
                    
                    prompt_content = {
                        'capability': capability,
                        'version': 'v1.0.0',
                        'status': 'active',
                        'component_type': comp_type,
                        'content': content,
                        'variables': variables,
                        'metadata': {
                            'description': f'Prompt for {capability}',
                            'author': 'system',
                            'created': '2026-02-15'
                        }
                    }
                    
                    with open(prompt_file, 'w', encoding='utf-8') as f:
                        yaml.dump(prompt_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    print(f"[INFO] Создан промпт: {prompt_file}")
    
    # Создаем контракты для всех capability
    for capability in missing_capabilities:
        if capability in capability_types:
            comp_type = capability_types[capability]
            cap_parts = capability.split('.')
            if len(cap_parts) >= 2:
                cap_main = cap_parts[0]
                
                # Создаем директорию для контрактов
                contract_dir = data_dir / "contracts" / comp_type / cap_main
                contract_dir.mkdir(parents=True, exist_ok=True)
                
                # Создаем входной контракт
                input_contract_file = contract_dir / f"{capability}_input_v1.0.0.yaml"
                if not input_contract_file.exists():
                    # Определяем свойства в зависимости от capability
                    if capability == 'sql_generation.generate_query':
                        properties = {
                            'natural_language_request': {'type': 'string', 'description': 'Request in natural language'},
                            'table_schema': {'type': 'string', 'description': 'Database schema'}
                        }
                        required = ['natural_language_request', 'table_schema']
                    elif capability == 'book_library.search_books':
                        properties = {
                            'query': {'type': 'string', 'description': 'Search query'},
                            'max_results': {'type': 'integer', 'description': 'Maximum number of results', 'default': 10}
                        }
                        required = ['query']
                    elif capability == 'planning.create_plan':
                        properties = {
                            'goal': {'type': 'string', 'description': 'Target goal to plan for'},
                            'context': {'type': 'string', 'description': 'Additional context', 'default': ''},
                            'capabilities_list': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Available capabilities'},
                            'max_steps': {'type': 'integer', 'description': 'Maximum number of steps', 'default': 10}
                        }
                        required = ['goal']
                    elif capability.startswith('behavior.planning'):
                        properties = {
                            'input': {'type': 'string', 'description': f'Input for {capability}'}
                        }
                        required = ['input']
                    elif capability.startswith('behavior.react'):
                        properties = {
                            'observation': {'type': 'string', 'description': 'Current observation'},
                            'thought': {'type': 'string', 'description': 'Current thought'},
                            'action': {'type': 'string', 'description': 'Current action'}
                        }
                        required = ['observation', 'thought', 'action']
                    else:
                        properties = {
                            'input': {'type': 'string', 'description': f'Input for {capability}'}
                        }
                        required = ['input']
                    
                    input_contract_content = {
                        'capability': capability,
                        'version': 'v1.0.0',
                        'status': 'active',
                        'component_type': comp_type,
                        'direction': 'input',
                        'schema_data': {
                            'type': 'object',
                            'properties': properties,
                            'required': required
                        },
                        'description': f'Input contract for {capability}'
                    }
                    
                    with open(input_contract_file, 'w', encoding='utf-8') as f:
                        yaml.dump(input_contract_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    print(f"[INFO] Создан входной контракт: {input_contract_file}")
                
                # Создаем выходной контракт
                output_contract_file = contract_dir / f"{capability}_output_v1.0.0.yaml"
                if not output_contract_file.exists():
                    # Определяем свойства в зависимости от capability
                    if capability == 'sql_generation.generate_query':
                        properties = {
                            'sql_query': {'type': 'string', 'description': 'Generated SQL query'},
                            'explanation': {'type': 'string', 'description': 'Brief explanation'}
                        }
                        required = ['sql_query']
                    elif capability == 'book_library.search_books':
                        properties = {
                            'results': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'title': {'type': 'string', 'description': 'Book title'},
                                        'author': {'type': 'string', 'description': 'Book author'},
                                        'year': {'type': 'integer', 'description': 'Publication year'},
                                        'isbn': {'type': 'string', 'description': 'ISBN'}
                                    },
                                    'required': ['title', 'author']
                                },
                                'description': 'Search results'
                            },
                            'total_found': {'type': 'integer', 'description': 'Total number of books found'}
                        }
                        required = ['results', 'total_found']
                    elif capability == 'planning.create_plan':
                        properties = {
                            'plan': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'step': {'type': 'integer', 'description': 'Step number'},
                                        'action': {'type': 'string', 'description': 'Action to take'},
                                        'estimated_time': {'type': 'string', 'description': 'Estimated time'}
                                    }
                                },
                                'description': 'Action plan steps'
                            }
                        }
                        required = ['plan']
                    elif capability.startswith('behavior.planning'):
                        properties = {
                            'result': {'type': 'string', 'description': f'Result for {capability}'}
                        }
                        required = ['result']
                    elif capability.startswith('behavior.react'):
                        properties = {
                            'response': {'type': 'string', 'description': 'REACT pattern response'},
                            'next_action': {'type': 'string', 'description': 'Next action to take'}
                        }
                        required = ['response']
                    else:
                        properties = {
                            'result': {'type': 'string', 'description': f'Output for {capability}'}
                        }
                        required = ['result']
                    
                    output_contract_content = {
                        'capability': capability,
                        'version': 'v1.0.0',
                        'status': 'active',
                        'component_type': comp_type,
                        'direction': 'output',
                        'schema_data': {
                            'type': 'object',
                            'properties': properties,
                            'required': required
                        },
                        'description': f'Output contract for {capability}'
                    }
                    
                    with open(output_contract_file, 'w', encoding='utf-8') as f:
                        yaml.dump(output_contract_content, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    print(f"[INFO] Создан выходной контракт: {output_contract_file}")
    
    print("[SUCCESS] Создание всех недостающих файлов завершено!")


if __name__ == "__main__":
    print("Начинаем создание всех недостающих файлов...")
    create_missing_files()
    print("\n[SUCCESS] Все недостающие файлы созданы!")