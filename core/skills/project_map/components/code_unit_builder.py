"""Компонент для построения CodeUnit из AST узлов.

Отвечает за создание CodeUnit объектов из различных типов AST узлов.
Реализует принцип единственной ответственности для построения единиц кода.

Особенности:
1. Единая точка создания CodeUnit
2. Валидация данных перед созданием
3. Генерация уникальных ID
4. Обработка специфичных для Python конструкций

Примеры использования:

1. Создание CodeUnit для функции:
```python
builder = CodeUnitBuilder(project_map_skill)
func_unit = builder.build_function_unit(
    node=function_node,
    file_path="core/main.py",
    source_code=full_source,
    parent_id=module_id
)
```

2. Создание CodeUnit для класса:
```python
class_unit = builder.build_class_unit(
    node=class_node,
    file_path="core/models.py",
    source_code=full_source,
    parent_id=module_id
)
```

3. Создание CodeUnit для импорта:
```python
import_unit = builder.build_import_unit(
    node=import_node,
    file_path="core/main.py",
    source_code=full_source,
    parent_id=module_id
)
```

Компонент интегрируется с ProjectMapSkill и использует его для доступа к логированию и конфигурации.
"""

import logging
from typing import Dict, Any, Optional, List
from core.skills.project_map.models.code_unit import CodeUnit, Location, CodeSpan, CodeUnitType
import hashlib

logger = logging.getLogger(__name__)

class CodeUnitBuilder:
    """Компонент для построения CodeUnit из AST узлов.
    
    Основная ответственность - создание валидных CodeUnit объектов
    из различных типов AST узлов с правильной обработкой метаданных.
    
    Атрибуты:
    - skill_context: контекст навыка для доступа к логированию и конфигурации
    
    Пример:
    ```python
    builder = CodeUnitBuilder(project_map_skill)
    function_unit = builder.build_function_unit(node, file_path, source_code, parent_id)
    ```
    """
    
    def __init__(self, skill_context):
        self.skill_context = skill_context
    
    def build_module_unit(self, node, file_path: str, source_code: str) -> Optional[CodeUnit]:
        """Построение CodeUnit для модуля (файла).
        
        Args:
            node: корневой узел AST
            file_path: путь к файлу
            source_code: полный исходный код файла
        
        Returns:
            Optional[CodeUnit]: CodeUnit для модуля или None
        
        Пример:
        ```python
        module_unit = builder.build_module_unit(root_node, "core/main.py", source_code)
        ```
        """
        try:
            module_source = source_code[node.start_byte:node.end_byte]
            
            location = Location(
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_column=node.start_point[1] + 1,
                end_column=node.end_point[1] + 1
            )
            
            code_span = CodeSpan(source_code=module_source)
            
            # Генерация уникального ID
            file_name = file_path.split('/')[-1].replace('.py', '')
            module_id = f"module_{file_name}_{hashlib.md5(file_path.encode()).hexdigest()[:8]}"
            
            # Извлечение docstring модуля
            docstring = self._extract_module_docstring(node, source_code)
            
            return CodeUnit(
                id=module_id,
                name=file_name,
                type=CodeUnitType.MODULE,
                location=location,
                code_span=code_span,
                metadata={
                    'docstring': docstring,
                    'file_path': file_path,
                    'is_package': '__init__.py' in file_path,
                    'imports': [],
                    'exports': []
                },
                language="python"
            )
        except Exception as e:
            self.skill_context.logger.error(f"Ошибка построения модуля {file_path}: {str(e)}")
            return None
    
    def build_class_unit(self, node, file_path: str, source_code: str, parent_id: str) -> Optional[CodeUnit]:
        """Построение CodeUnit для класса.
        
        Args:
            node: узел AST для класса
            file_path: путь к файлу
            source_code: исходный код
            parent_id: ID родительского модуля
        
        Returns:
            Optional[CodeUnit]: CodeUnit для класса или None
        
        Пример:
        ```python
        class_unit = builder.build_class_unit(class_node, "core/models.py", source_code, module_id)
        ```
        """
        try:
            name_node = node.child_by_field_name('name')
            if not name_node:
                return None
            
            class_name = source_code[name_node.start_byte:name_node.end_byte]
            
            # Извлечение базовых классов
            bases = self._extract_class_bases(node, source_code)
            
            # Извлечение docstring
            docstring = self._extract_docstring(node, source_code)
            
            # Извлечение декораторов
            decorators = self._extract_decorators(node, source_code)
            
            # Создание CodeUnit
            location = Location(
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_column=node.start_point[1] + 1,
                end_column=node.end_point[1] + 1
            )
            
            class_source = source_code[node.start_byte:node.end_byte]
            code_span = CodeSpan(source_code=class_source)
            
            class_id = f"class_{class_name}_{hashlib.md5(class_source.encode()).hexdigest()[:8]}"
            
            return CodeUnit(
                id=class_id,
                name=class_name,
                type=CodeUnitType.CLASS,
                location=location,
                code_span=code_span,
                parent_id=parent_id,
                metadata={
                    'bases': bases,
                    'docstring': docstring,
                    'decorators': decorators,
                    'methods_count': len([c for c in node.children if c.type == 'function_definition']),
                    'is_dataclass': any('@dataclass' in d for d in decorators),
                    'has_init': any(c.type == 'function_definition' and 
                                  source_code[c.child_by_field_name('name').start_byte:c.child_by_field_name('name').end_byte] == '__init__'
                                  for c in node.children if c.type == 'function_definition')
                },
                language="python"
            )
        except Exception as e:
            self.skill_context.logger.error(f"Ошибка построения класса в {file_path}: {str(e)}")
            return None
    
    def build_function_unit(self, node, file_path: str, source_code: str, parent_id: str) -> Optional[CodeUnit]:
        """Построение CodeUnit для функции или метода.
        
        Args:
            node: узел AST для функции
            file_path: путь к файлу
            source_code: исходный код
            parent_id: ID родительского элемента
        
        Returns:
            Optional[CodeUnit]: CodeUnit для функции или None
        
        Пример:
        ```python
        func_unit = builder.build_function_unit(func_node, "core/utils.py", source_code, module_id)
        ```
        """
        try:
            name_node = node.child_by_field_name('name')
            if not name_node:
                return None
            
            func_name = source_code[name_node.start_byte:name_node.end_byte]
            
            # Определение является ли функция методом класса
            is_method = parent_id and parent_id.startswith('class_')
            
            # Извлечение параметров
            parameters = self._extract_parameters(node, source_code)
            
            # Извлечение возвращаемого типа
            return_type = self._extract_return_type(node, source_code)
            
            # Извлечение docstring
            docstring = self._extract_docstring(node, source_code)
            
            # Извлечение декораторов
            decorators = self._extract_decorators(node, source_code)
            
            # Проверка async
            is_async = node.type == 'async_function_definition' or 'async' in source_code[node.start_byte:node.start_byte+20].lower()
            
            # Создание CodeUnit
            location = Location(
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_column=node.start_point[1] + 1,
                end_column=node.end_point[1] + 1
            )
            
            func_source = source_code[node.start_byte:node.end_byte]
            code_span = CodeSpan(source_code=func_source)
            
            func_type = CodeUnitType.METHOD if is_method else CodeUnitType.FUNCTION
            func_id = f"{'method' if is_method else 'func'}_{func_name}_{hashlib.md5(func_source.encode()).hexdigest()[:8]}"
            
            return CodeUnit(
                id=func_id,
                name=func_name,
                type=func_type,
                location=location,
                code_span=code_span,
                parent_id=parent_id,
                metadata={
                    'parameters': parameters,
                    'return_type': return_type,
                    'docstring': docstring,
                    'is_async': is_async,
                    'decorators': decorators,
                    'complexity': self._calculate_complexity(node, source_code),
                    'is_method': is_method,
                    'is_constructor': is_method and func_name == '__init__'
                },
                language="python"
            )
        except Exception as e:
            self.skill_context.logger.error(f"Ошибка построения функции {func_name} в {file_path}: {str(e)}")
            return None
    
    def build_import_unit(self, node, file_path: str, source_code: str, parent_id: str) -> Optional[CodeUnit]:
        """Построение CodeUnit для импорта.
        
        Args:
            node: узел AST для импорта
            file_path: путь к файлу
            source_code: исходный код
            parent_id: ID родительского модуля
        
        Returns:
            Optional[CodeUnit]: CodeUnit для импорта или None
        
        Пример:
        ```python
        import_unit = builder.build_import_unit(import_node, "core/main.py", source_code, module_id)
        ```
        """
        try:
            import_text = source_code[node.start_byte:node.end_byte]
            
            # Определение типа импорта
            import_type = "import"
            if node.type == 'import_from_statement':
                import_type = "from_import"
            
            # Извлечение первого имени из импорта для использования в качестве имени
            imported_names = self._extract_imported_names(node, source_code)
            if not imported_names:
                return None
            
            first_import = imported_names[0]
            import_name = first_import['name']
            
            location = Location(
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_column=node.start_point[1] + 1,
                end_column=node.end_point[1] + 1
            )
            
            code_span = CodeSpan(source_code=import_text)
            
            import_id = f"import_{import_name}_{hashlib.md5(import_text.encode()).hexdigest()[:8]}"
            
            return CodeUnit(
                id=import_id,
                name=import_name,
                type=CodeUnitType.IMPORT,
                location=location,
                code_span=code_span,
                parent_id=parent_id,
                metadata={
                    'import_type': import_type,
                    'original_text': import_text,
                    'module': first_import.get('module'),
                    'alias': first_import.get('alias'),
                    'is_relative': first_import.get('is_relative', False),
                    'all_imports': imported_names
                },
                language="python"
            )
        except Exception as e:
            self.skill_context.logger.error(f"Ошибка построения импорта в {file_path}: {str(e)}")
            return None
    
    def build_variable_unit(self, node, file_path: str, source_code: str, parent_id: str, var_name: str, var_value: str) -> Optional[CodeUnit]:
        """Построение CodeUnit для переменной.
        
        Args:
            node: узел AST для переменной
            file_path: путь к файлу
            source_code: исходный код
            parent_id: ID родительского элемента
            var_name: имя переменной
            var_value: значение переменной
        
        Returns:
            Optional[CodeUnit]: CodeUnit для переменной или None
        
        Пример:
        ```python
        var_unit = builder.build_variable_unit(assignment_node, "core/config.py", source_code, module_id, "DEBUG", "True")
        ```
        """
        try:
            location = Location(
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_column=node.start_point[1] + 1,
                end_column=node.end_point[1] + 1
            )
            
            variable_source = source_code[node.start_byte:node.end_byte]
            code_span = CodeSpan(source_code=variable_source)
            
            var_id = f"var_{var_name}_{hashlib.md5(variable_source.encode()).hexdigest()[:8]}"
            
            return CodeUnit(
                id=var_id,
                name=var_name,
                type=CodeUnitType.VARIABLE,
                location=location,
                code_span=code_span,
                parent_id=parent_id,
                metadata={
                    'value': var_value[:100] + "..." if len(var_value) > 100 else var_value,
                    'is_constant': var_name.isupper(),
                    'line': node.start_point[0] + 1
                },
                language="python"
            )
        except Exception as e:
            self.skill_context.logger.error(f"Ошибка построения переменной {var_name} в {file_path}: {str(e)}")
            return None
    
    # Вспомогательные методы для извлечения данных
    def _extract_module_docstring(self, node, source_code: str) -> Optional[str]:
        """Извлечение docstring модуля."""
        # Поиск первого выражения в модуле
        for child in node.children:
            if child.type == 'expression_statement':
                for grandchild in child.children:
                    if grandchild.type == 'string':
                        string_content = source_code[grandchild.start_byte:grandchild.end_byte]
                        # Очистка от кавычек
                        return string_content.strip('"\'')
        return None
    
    def _extract_docstring(self, node, source_code: str) -> Optional[str]:
        """Извлечение docstring из узла."""
        # Поиск тела узла
        body_node = None
        if hasattr(node, 'child_by_field_name'):
            body_node = node.child_by_field_name('body')
        
        if not body_node:
            return None
        
        # Поиск первого выражения в теле
        first_child = next((c for c in body_node.children if c.type != 'block'), None)
        if not first_child or first_child.type != 'expression_statement':
            return None
        
        # Поиск строкового литерала
        string_node = next((c for c in first_child.children if c.type == 'string'), None)
        if not string_node:
            return None
        
        string_content = source_code[string_node.start_byte:string_node.end_byte]
        # Очистка от кавычек и экранирования
        docstring = string_content.strip('"\'')
        docstring = docstring.replace('\\"', '"').replace("\\'", "'")
        
        return docstring if docstring.strip() else None
    
    def _extract_decorators(self, node, source_code: str) -> List[str]:
        """Извлечение декораторов из узла."""
        decorators = []
        
        # Поиск декораторов над определением
        if hasattr(node, 'children'):
            for child in node.children:
                if child.type == 'decorator':
                    decorator_text = source_code[child.start_byte:child.end_byte].strip()
                    decorators.append(decorator_text)
        
        return decorators
    
    def _extract_class_bases(self, node, source_code: str) -> List[str]:
        """Извлечение базовых классов для класса."""
        bases = []
        superclass_node = node.child_by_field_name('superclasses')
        
        if superclass_node:
            for base in superclass_node.children:
                if base.type != ',' and base.type != '(':  # Пропускаем разделители
                    base_name = source_code[base.start_byte:base.end_byte]
                    bases.append(base_name)
        
        return bases
    
    def _extract_parameters(self, node, source_code: str) -> List[Dict[str, Any]]:
        """Извлечение параметров функции."""
        params = []
        parameters_node = node.child_by_field_name('parameters')
        
        if not parameters_node:
            return params
        
        for param_node in parameters_node.children:
            if param_node.type in ['identifier', 'typed_parameter', 'default_parameter', 'keyword_separator']:
                if param_node.type == 'identifier':
                    # Простой параметр
                    param_name = source_code[param_node.start_byte:param_node.end_byte]
                    params.append({
                        'name': param_name,
                        'line': param_node.start_point[0] + 1
                    })
                
                elif param_node.type == 'typed_parameter':
                    # Параметр с типом
                    name_node = param_node.child_by_field_name('name')
                    type_node = param_node.child_by_field_name('type')
                    if name_node:
                        param_name = source_code[name_node.start_byte:name_node.end_byte]
                        param_type = source_code[type_node.start_byte:type_node.end_byte] if type_node else None
                        params.append({
                            'name': param_name,
                            'type_annotation': param_type,
                            'line': param_node.start_point[0] + 1
                        })
                
                elif param_node.type == 'default_parameter':
                    # Параметр со значением по умолчанию
                    name_node = param_node.child_by_field_name('name')
                    value_node = param_node.child_by_field_name('value')
                    if name_node:
                        param_name = source_code[name_node.start_byte:name_node.end_byte]
                        default_value = source_code[value_node.start_byte:value_node.end_byte] if value_node else None
                        params.append({
                            'name': param_name,
                            'default_value': default_value,
                            'line': param_node.start_point[0] + 1
                        })
                
                elif param_node.type == 'keyword_separator':
                    # * или ** параметры
                    if '*' in source_code[param_node.start_byte:param_node.end_byte]:
                        params.append({
                            'name': '*args' if 'args' in source_code[param_node.start_byte:param_node.end_byte] else '**kwargs',
                            'is_vararg': '*' in source_code[param_node.start_byte:param_node.start_byte+2] and 'args' in source_code[param_node.start_byte:param_node.end_byte],
                            'is_kwarg': '**' in source_code[param_node.start_byte:param_node.start_byte+3] or 'kwargs' in source_code[param_node.start_byte:param_node.end_byte],
                            'line': param_node.start_point[0] + 1
                        })
        
        return params
    
    def _calculate_complexity(self, node, source_code: str) -> int:
        """Расчет цикломатической сложности (упрощенная версия)."""
        complexity = 1  # Базовая сложность
        
        def count_complexity_points(current_node):
            nonlocal complexity
            node_text = source_code[current_node.start_byte:current_node.end_byte].lower()
            
            # Условные операторы
            if current_node.type in ['if_statement', 'conditional_expression']:
                complexity += 1
                # Дополнительная сложность для вложенных условий
                if 'elif' in node_text or 'else' in node_text:
                    complexity += 1
            
            # Циклы
            elif current_node.type in ['for_statement', 'while_statement']:
                complexity += 1
            
            # Обработка исключений
            elif current_node.type == 'try_statement':
                complexity += 1
            
            # Логические операторы в выражениях
            elif current_node.type == 'boolean_operator':
                complexity += 1
            
            # Рекурсивный обход дочерних узлов
            for child in current_node.children:
                count_complexity_points(child)
        
        count_complexity_points(node)
        return min(complexity, 100)  # Ограничение максимальной сложности
    
    def _extract_return_type(self, node, source_code: str) -> Optional[str]:
        """Извлечение возвращаемого типа функции."""
        return_type_node = node.child_by_field_name('return_type')
        if return_type_node:
            return source_code[return_type_node.start_byte:return_type_node.end_byte]
        return None
    
    def _extract_imported_names(self, node, source_code: str, source_bytes: bytes) -> List[Dict[str, Any]]:
        """Извлечение имен из узла импорта."""
        result = []
        
        if node.type == 'import_statement':
            # Обработка "import module" и "import module as alias"
            for child in node.children:
                if child.type == 'dotted_name':
                    module_name = self._get_node_text(child, source_bytes, source_code)
                    result.append({
                        'name': module_name.split('.')[-1],
                        'module': module_name,
                        'is_relative': False
                    })
                elif child.type == 'aliased_import':
                    # Обработка "import module as alias"
                    for grandchild in child.children:
                        if grandchild.type == 'dotted_name':
                            module_name = self._get_node_text(grandchild, source_bytes, source_code)
                        elif grandchild.type == 'identifier':
                            alias_name = self._get_node_text(grandchild, source_bytes, source_code)
                    if 'module_name' in locals() and 'alias_name' in locals():
                        result.append({
                            'name': alias_name,
                            'module': module_name,
                            'alias': alias_name,
                            'is_relative': False
                        })
        elif node.type == 'import_from_statement':
            # Исправленная обработка "from module import name"
            module_node = node.child_by_field_name('module_name')
            if not module_node:
                # Попробуем найти модуль в дочерних узлах, если field не работает
                for child in node.children:
                    if child.type == 'dotted_name' or child.type == 'relative_import':
                        module_node = child
                        break
            
            if module_node:
                module_name = self._get_node_text(module_node, source_bytes, source_code)
                is_relative = module_name.startswith('.') or any(c.type == 'relative_import' for c in node.children)
                
                # Извлечение импортируемых имен - исправленный подход
                imports_node = node.child_by_field_name('name') or node.child_by_field_name('names') or node.child_by_field_name('imports')
                
                if not imports_node:
                    # Альтернативный поиск импортируемых имен
                    for child in node.children:
                        if child.type in ['dotted_name', 'identifier', 'aliased_import', 'import_specifier']:
                            imports_node = child
                            break
                
                imported_items = []
                
                # Если imports_node - это список
                if imports_node and hasattr(imports_node, 'children'):
                    imported_items = imports_node.children
                # Если imports_node - это один узел
                elif imports_node:
                    imported_items = [imports_node]
                
                # Если все еще нет импортируемых имен, проверяем дочерние узлы узла импорта
                if not imported_items:
                    for child in node.children:
                        if child != module_node and child.type not in ['from', 'import', 'relative_import']:
                            imported_items.append(child)
                
                # Обработка каждого импортируемого элемента
                for import_item in imported_items:
                    if import_item.type == 'dotted_name' or import_item.type == 'identifier':
                        name = self._get_node_text(import_item, source_bytes, source_code)
                        if name:
                            result.append({
                                'name': name.split('.')[-1],
                                'module': module_name,
                                'is_relative': is_relative
                            })
                    elif import_item.type == 'aliased_import' or import_item.type == 'import_specifier':
                        # Обработка "from module import name as alias"
                        name_node = None
                        alias_node = None
                        
                        # Ищем имя и алиас в дочерних узлах
                        for child in import_item.children:
                            if child.type == 'identifier':
                                if name_node is None:
                                    name_node = child
                                else:
                                    alias_node = child
                            elif child.type == 'dotted_name' and name_node is None:
                                name_node = child
                        
                        if name_node:
                            name = self._get_node_text(name_node, source_bytes, source_code)
                            alias = name  # По умолчанию алиас равен имени
                            
                            if alias_node:
                                alias = self._get_node_text(alias_node, source_bytes, source_code)
                            
                            result.append({
                                'name': alias,
                                'module': module_name,
                                'alias': alias if alias != name else None,
                                'original_name': name,
                                'is_relative': is_relative
                            })
                    elif import_item.type == 'relative_import':
                        # Обработка "from . import name"
                        is_relative = True
                        continue
            
            # Отладочное логирование для понимания структуры AST
            if not result and node.type == 'import_from_statement':
                logger.debug(f"Не удалось извлечь имена из import_from_statement. Структура узла:")
                logger.debug(f"- Тип узла: {node.type}")
                logger.debug(f"- Дочерние узлы: {[child.type for child in node.children]}")
                logger.debug(f"- Поля узла: {[field for field in dir(node) if not field.startswith('_')]}")
                logger.debug(f"- Текст узла: {self._get_node_text(node, source_bytes, source_code)}")
        
        return result