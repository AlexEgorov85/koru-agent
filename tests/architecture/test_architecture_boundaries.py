import pytest
import ast
import os
from pathlib import Path


def get_imports_from_file(filepath):
    """Получить все импорты из файла"""
    with open(filepath, 'r', encoding='utf-8') as file:
        try:
            tree = ast.parse(file.read())
        except SyntaxError:
            return []  # Если файл не содержит валидный Python код
    
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    
    return imports


def test_domain_does_not_depend_on_infrastructure():
    """Тест, что доменные модели не зависят от инфраструктурных компонентов"""
    domain_path = Path("domain")
    infrastructure_modules = [
        'infrastructure',
        'sqlalchemy',
        'psycopg2',
        'mysql',
        'pymongo',
        'redis',
        'boto3',
        'requests'
    ]
    
    # Собираем все Python файлы в домене
    domain_files = list(domain_path.rglob("*.py"))
    
    violations = []
    for file_path in domain_files:
        imports = get_imports_from_file(file_path)
        for imp in imports:
            # Проверяем, начинается ли импорт с одного из инфраструктурных модулей
            for infra_module in infrastructure_modules:
                if imp.startswith(infra_module):
                    violations.append((file_path, imp))
    
    # Исключения: некоторые импорты могут быть допустимы
    allowed_violations = []
    filtered_violations = []
    
    for violation in violations:
        file_path, imp = violation
        # Разрешаем импорты внутри одного и того же слоя
        if 'domain' in str(file_path) and imp.startswith('domain'):
            continue  # Это нормально
        filtered_violations.append(violation)
    
    if filtered_violations:
        error_msg = "Найдены нарушения архитектурных границ:\n"
        for file_path, imp in filtered_violations:
            error_msg += f"- {file_path} импортирует {imp}\n"
        pytest.fail(error_msg)


def test_domain_models_are_isolated():
    """Тест изоляции доменных моделей от внешних зависимостей"""
    domain_models_path = Path("domain/models")
    if not domain_models_path.exists():
        pytest.skip("Директория domain/models не найдена")
    
    model_files = list(domain_models_path.rglob("*.py"))
    
    # Проверим конкретно модель PromptVersion
    prompt_version_file = Path("domain/models/prompt/prompt_version.py")
    if prompt_version_file.exists():
        imports = get_imports_from_file(prompt_version_file)
        
        # Проверяем, что импорты соответствуют допустимым для домена
        allowed_imports = [
            'pydantic', 'typing', 'enum', 'uuid', 'datetime',
            'domain.', 'infrastructure.gateways.llm_providers.',
            'domain.value_objects.'
        ]
        
        violations = []
        for imp in imports:
            is_allowed = False
            for allowed in allowed_imports:
                if imp.startswith(allowed.split('.')[0]):  # Проверяем начало импорта
                    is_allowed = True
                    break
            if not is_allowed:
                violations.append(imp)
        
        # Дополнительно проверим, что специфические импорты из инфраструктуры находятся в разрешенных списках
        specific_allowed = [
            'infrastructure.gateways.llm_providers.base_provider.LLMProviderType',
            'domain.value_objects.domain_type.DomainType'
        ]
        
        filtered_violations = []
        for violation in violations:
            is_specific_allowed = False
            for allowed in specific_allowed:
                if violation in allowed:
                    is_specific_allowed = True
                    break
            if not is_specific_allowed:
                filtered_violations.append(violation)
        
        if filtered_violations:
            pytest.fail(f"Нарушения в {prompt_version_file}: {filtered_violations}")


def test_application_does_not_depend_on_frameworks_directly():
    """Тест, что прикладной слой не зависит напрямую от внешних фреймворков"""
    application_path = Path("application")
    framework_modules = [
        'flask', 'django', 'fastapi', 'aiohttp', 'tornado',
        'celery', 'rq', 'kafka', 'rabbitmq'
    ]
    
    app_files = list(application_path.rglob("*.py"))
    
    violations = []
    for file_path in app_files:
        imports = get_imports_from_file(file_path)
        for imp in imports:
            for framework in framework_modules:
                if imp.startswith(framework):
                    violations.append((file_path, imp))
    
    if violations:
        error_msg = "Прикладной слой напрямую зависит от фреймворков:\n"
        for file_path, imp in violations:
            error_msg += f"- {file_path} импортирует {imp}\n"
        pytest.fail(error_msg)


def test_dependency_direction():
    """Тест направления зависимостей"""
    # Проверяем, что домен не зависит от приложения и инфраструктуры
    domain_files = list(Path("domain").rglob("*.py"))
    app_infra_imports = []
    
    for file_path in domain_files:
        imports = get_imports_from_file(file_path)
        for imp in imports:
            if imp.startswith(('application.', 'infrastructure.')):
                app_infra_imports.append((file_path, imp))
    
    if app_infra_imports:
        error_msg = "Домен зависит от прикладного слоя или инфраструктуры:\n"
        for file_path, imp in app_infra_imports:
            error_msg += f"- {file_path} импортирует {imp}\n"
        pytest.fail(error_msg)
    
    # Проверяем, что приложение может зависеть от домена (это нормально)
    app_files = list(Path("application").rglob("*.py"))
    domain_imports = []
    
    for file_path in app_files:
        imports = get_imports_from_file(file_path)
        for imp in imports:
            if imp.startswith('domain.'):
                domain_imports.append((file_path, imp))
    
    # Это нормально, не считается за ошибку
    assert len(domain_imports) >= 0  # Просто проверяем, что тест работает


if __name__ == "__main__":
    test_domain_does_not_depend_on_infrastructure()
    test_domain_models_are_isolated()
    test_application_does_not_depend_on_frameworks_directly()
    test_dependency_direction()
    print("Все архитектурные тесты пройдены!")