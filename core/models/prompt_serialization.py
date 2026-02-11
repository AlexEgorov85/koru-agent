from typing import Dict, List, Any, Union
from pathlib import Path
import yaml
import re
from jinja2 import Environment, BaseLoader
from .prompt import Prompt, PromptStatus, PromptMetadata


class PromptSerializer:
    """Класс для расширенной сериализации промптов с валидацией шаблонов Jinja2"""
    
    @staticmethod
    def validate_jinja2_template(content: str, variables: List[str]) -> Dict[str, List[str]]:
        """
        Проверяет корректность шаблона Jinja2 и соответствие переменных
        Возвращает словарь с найденными ошибками
        """
        errors = {
            'syntax_errors': [],
            'undeclared_variables': [],
            'unused_variables': []
        }
        
        # Проверяем синтаксис Jinja2
        try:
            env = Environment(loader=BaseLoader(), autoescape=False)
            env.parse(content)
        except Exception as e:
            errors['syntax_errors'].append(str(e))
        
        # Ищем все переменные в формате {{ variable }}
        content_vars = re.findall(r'\{\{\s*(\w+)\s*\}\}', content)
        
        # Проверяем, что все переменные в content объявлены в metadata.variables
        for var in content_vars:
            if var not in variables:
                errors['undeclared_variables'].append(var)
        
        # Проверяем, что все объявленные переменные используются в content
        for var in variables:
            if not re.search(r'\{\{\s*' + re.escape(var) + r'\s*\}\}', content):
                errors['unused_variables'].append(var)
        
        return errors

    @staticmethod
    def extract_variables_from_content(content: str) -> List[str]:
        """Извлекает переменные из контента Jinja2 шаблона"""
        # Ищем все переменные в формате {{ variable }}
        variables = re.findall(r'\{\{\s*(\w+)\s*\}\}', content)
        # Удаляем дубликаты, сохраняя порядок
        unique_vars = []
        for var in variables:
            if var not in unique_vars:
                unique_vars.append(var)
        return unique_vars

    @staticmethod
    def to_yaml(prompt: Prompt) -> str:
        """Сериализует промпт в человекочитаемый YAML"""
        # Подготовим данные для сериализации
        data = {
            'metadata': prompt.metadata.model_dump(),
            'content': prompt.content
        }
        
        # Сериализуем в YAML с человеческим форматом
        yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, indent=2)
        return yaml_str

    @staticmethod
    def to_file(prompt: Prompt, base_path: Path) -> Path:
        """Сохраняет промпт в правильную директорию по шаблону"""
        # Определяем путь на основе skill и capability
        skill_path = base_path / prompt.metadata.skill
        skill_path.mkdir(parents=True, exist_ok=True)
        
        # Формируем имя файла
        capability_clean = prompt.metadata.capability.replace('.', '_')
        version_clean = prompt.metadata.version.replace('v', '').replace('.', '_')
        filename = f"{capability_clean}_v{version_clean}.yaml"
        
        file_path = skill_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(PromptSerializer.to_yaml(prompt))
        
        return file_path

    @staticmethod
    def from_yaml(yaml_content: Union[str, Path]) -> Prompt:
        """Десериализует из YAML с автоматическим определением статуса"""
        if isinstance(yaml_content, Path):
            with open(yaml_content, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        else:
            data = yaml.safe_load(yaml_content)
        
        # Определяем статус из пути файла, если это Path
        if isinstance(yaml_content, Path):
            path_str = str(yaml_content)
            
            # Если файл в папке archived/ → status=ARCHIVED
            if '/archived/' in path_str or '\\archived\\' in path_str:
                data['metadata']['status'] = PromptStatus.ARCHIVED
            
            # Если имя содержит _draft → status=DRAFT
            elif '_draft' in path_str.lower():
                data['metadata']['status'] = PromptStatus.DRAFT
        
        # Если статус не указан явно, устанавливаем ACTIVE по умолчанию
        if 'status' not in data['metadata']:
            data['metadata']['status'] = PromptStatus.ACTIVE
        
        # Создаем объект Prompt
        return Prompt(**data)

    @staticmethod
    def from_legacy_format(legacy_data: Dict[str, Any], capability: str, version: str, author: str) -> Prompt:
        """
        Конвертирует старый формат промпта в новый объект Prompt
        """
        # Определяем статус на основе расположения файла или других признаков
        status = PromptStatus.ACTIVE  # по умолчанию
        
        # Извлекаем переменные из контента
        content = legacy_data.get('content', '')
        extracted_vars = PromptSerializer.extract_variables_from_content(content)
        
        # Создаем метаданные
        metadata = {
            'version': version,
            'skill': legacy_data.get('skill', 'unknown'),
            'capability': capability,
            'strategy': legacy_data.get('strategy'),
            'role': legacy_data.get('role', 'system'),
            'language': legacy_data.get('language', 'ru'),
            'tags': legacy_data.get('tags', []),
            'variables': extracted_vars,
            'status': status,
            'quality_metrics': legacy_data.get('quality_metrics'),
            'author': author,
            'changelog': legacy_data.get('changelog', [])
        }
        
        # Создаем объект Prompt
        return Prompt(
            metadata=PromptMetadata(**metadata),
            content=content
        )