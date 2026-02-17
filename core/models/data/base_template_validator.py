"""
Базовый класс для компонентов, содержащих шаблоны.
"""
import re
from typing import Set, List, Tuple, Optional


class TemplateValidatorMixin:
    """Примесь для валидации Jinja2-шаблонов в компонентах."""
    
    @classmethod
    def validate_jinja_template(
        cls, 
        template_content: str, 
        declared_variables: Set[str], 
        component_info: str = "unknown",
        template_field: str = "template"
    ) -> Tuple[bool, List[str]]:
        """
        Унифицированный метод валидации Jinja2-шаблонов.
        
        Args:
            template_content: содержимое шаблона
            declared_variables: множество объявленных переменных
            component_info: информация о компоненте для логирования
            template_field: название поля шаблона для логирования
        
        Returns:
            tuple: (valid: bool, warnings: list)
        """
        # Извлекаем переменные из шаблона: { variable_name }, {{ variable_name }}, или {{ variable_name|filter }}
        # Поддерживаем оба формата: Jinja2 ({{}}) и простой ({}), с возможными пробелами и фильтрами.
        matches = re.findall(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|[^\}]*)?\s*\}\}|\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}', template_content)
        
        # Обрабатываем результаты: findall возвращает кортежи, берем непустое значение
        template_vars = set()
        for match_tuple in matches:
            for item in match_tuple:
                if item:  # Если элемент не пустой
                    template_vars.add(item)
                    break  # Берем первый непустой элемент из кортежа

        # Проверяем необъявленные переменные
        undeclared = template_vars - declared_variables
        if undeclared:
            raise ValueError(
                f"Необъявленные переменные в {template_field} {component_info}: {sorted(undeclared)}\n"
                f"Объявленные переменные: {sorted(declared_variables)}"
            )

        # Проверяем объявленные, но неиспользуемые переменные (предупреждение)
        unused = declared_variables - template_vars
        warnings = []
        if unused:
            # Используем ASCII символы для избежания проблем с кодировкой
            warnings.append(f"[WARNING] Warning for {component_info}: declared but unused variables in {template_field}: {sorted(unused)}")

        return True, warnings

    def validate_templates(self) -> List[str]:
        """
        Метод для валидации всех шаблонов в компоненте.
        Должен быть переопределен в дочерних классах.
        
        Returns:
            list: список предупреждений
        """
        return []