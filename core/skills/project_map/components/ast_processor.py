"""
Компонент для корректной обработки AST деревьев с tree_sitter.

КЛЮЧЕВЫЕ ИСПРАВЛЕНИЯ:
1. Работа с байтами вместо строк при парсинге
2. Корректное извлечение текста узлов через байтовые координаты
3. Обработка BOM (Byte Order Mark) в начале файла
4. Правильная работа с кодировками
5. Валидация координат перед извлечением текста

Пример корректной работы:
```python
ast_processor = ASTProcessor(project_map_skill)
code_units = ast_processor.process_file_ast(
    tree=ast_tree,
    file_path="core/skills/project_map/skill.py",
    source_code=file_content,
    source_bytes=source_bytes  # Важно: байтовое представление
)
# Теперь имена будут корректными: "ProjectMapSkill", "_analyze_project" и т.д.
```
"""

from typing import List, Dict, Any, Optional, Tuple
from tree_sitter import Tree, Node
from core.skills.project_map.components.code_unit_builder import CodeUnitBuilder
from core.skills.project_map.models.code_unit import CodeUnit, Location, CodeSpan, CodeUnitType
import logging
import re

logger = logging.getLogger(__name__)

class ASTProcessor:
    """Компонент для корректной обработки AST деревьев."""
    
    def __init__(self, skill_context):
        self.skill_context = skill_context
        self._builder = CodeUnitBuilder(skill_context)
    
    def process_file_ast(self, tree: Tree, file_path: str, source_code: str, 
                        source_bytes: bytes, max_depth: int = 10) -> List[CodeUnit]:
        """
        Обработка AST дерева файла с корректным извлечением данных.
        
        ИСПРАВЛЕНИЯ:
        1. Использование source_bytes для корректного извлечения текста
        2. Обработка BOM в начале файла
        3. Валидация координат узлов
        4. Корректное извлечение имен из AST
        
        Args:
            tree: AST дерево, полученное от ASTParserTool
            file_path: путь к файлу
            source_code: исходный код в виде строки (для удобства)
            source_bytes: исходный код в виде байтов (для корректной работы с координатами)
            max_depth: максимальная глубина анализа (не используется в текущей реализации)
        
        Returns:
            List[CodeUnit]: список всех найденных единиц кода в файле
        """
        logger.debug(f"Начало обработки AST для файла: {file_path}")
        
        root_node = tree.root_node
        code_units = []
        
        try:
            # 1. Проверка и обработка BOM
            source_bytes, source_code = self._handle_bom(source_bytes, source_code)
            
            # 2. Извлечение модуля (файла)
            module_unit = self._extract_module(root_node, file_path, source_code, source_bytes)
            if module_unit:
                code_units.append(module_unit)
                logger.debug(f"Найден модуль: {module_unit.name}")
            
            # 3. Извлечение импортов
            imports = self._extract_imports(root_node, file_path, source_code, source_bytes, module_unit.id if module_unit else None)
            code_units.extend(imports)
            logger.debug(f"Найдено импортов: {len(imports)}")
            
            # 4. Извлечение классов и функций верхнего уровня
            for i, node in enumerate(root_node.children):
                logger.debug(f"Обработка узла {i}: type={node.type}, start_point={node.start_point}")
                
                if node.type == 'class_definition':
                    class_unit = self._extract_class_definition(node, file_path, source_code, source_bytes, module_unit.id if module_unit else None)
                    if class_unit:
                        code_units.append(class_unit)
                        logger.debug(f"Найден класс: {class_unit.name} at line {class_unit.location.start_line}")
                        # Извлечение методов класса
                        methods = self._extract_class_methods(node, file_path, source_code, source_bytes, class_unit.id)
                        code_units.extend(methods)
                        logger.debug(f"Найдено методов у класса {class_unit.name}: {len(methods)}")
                
                elif node.type in ['function_definition', 'async_function_definition']:
                    func_unit = self._extract_function_definition(node, file_path, source_code, source_bytes, module_unit.id if module_unit else None)
                    if func_unit:
                        code_units.append(func_unit)
                        logger.debug(f"Найдена функция: {func_unit.name} at line {func_unit.location.start_line}")
            
            # 5. Извлечение глобальных переменных
            variables = self._extract_global_variables(root_node, file_path, source_code, source_bytes, module_unit.id if module_unit else None)
            code_units.extend(variables)
            logger.debug(f"Найдено глобальных переменных: {len(variables)}")
            
            logger.info(f"Успешно проанализирован файл {file_path}: найдено {len(code_units)} единиц кода")
            return code_units
            
        except Exception as e:
            logger.error(f"Ошибка обработки AST для файла {file_path}: {str(e)}", exc_info=True)
            return []
    
    def _handle_bom(self, source_bytes: bytes, source_code: str) -> Tuple[bytes, str]:
        """Обработка BOM (Byte Order Mark) в начале файла."""
        # Проверка на наличие BOM (UTF-8 BOM: EF BB BF)
        if source_bytes.startswith(b'\xef\xbb\xbf'):
            logger.debug("Обнаружен BOM (UTF-8) в начале файла")
            # Удаляем BOM из байтового представления
            source_bytes = source_bytes[3:]
            # Обновляем строковое представление
            source_code = source_code[1:] if source_code.startswith('\ufeff') else source_code
        return source_bytes, source_code
    
    def _get_node_text(self, node: Node, source_bytes: bytes, source_code: str) -> str:
        """
        Безопасное получение текста узла с правильной обработкой байтовых координат.
        
        Args:
            node: узел AST
            source_bytes: исходный код в байтовом представлении
            source_code: исходный код в строковом представлении
        
        Returns:
            str: текст узла
        """
        try:
            # Валидация координат
            if node.start_byte < 0 or node.end_byte > len(source_bytes) or node.start_byte > node.end_byte:
                logger.warning(f"Некорректные координаты узла: start_byte={node.start_byte}, end_byte={node.end_byte}, "
                              f"длина source_bytes={len(source_bytes)}, type={node.type}")
                return ""
            
            # Извлечение текста из байтового представления
            node_bytes = source_bytes[node.start_byte:node.end_byte]
            
            try:
                # Декодирование с обработкой ошибок
                node_text = node_bytes.decode('utf-8', errors='replace')
                # Очистка от лишних пробелов и символов
                node_text = node_text.strip()
                return node_text
            except UnicodeDecodeError as e:
                logger.warning(f"Ошибка декодирования текста узла: {str(e)}")
                # Попытка альтернативной кодировки
                try:
                    node_text = node_bytes.decode('latin-1', errors='replace').strip()
                    return node_text
                except Exception as inner_e:
                    logger.error(f"Ошибка при альтернативном декодировании: {str(inner_e)}")
                    return ""
                    
        except Exception as e:
            logger.error(f"Ошибка получения текста узла: {str(e)}, type={node.type}", exc_info=True)
            return ""
    
    def _extract_module(self, node: Node, file_path: str, source_code: str, source_bytes: bytes) -> Optional[CodeUnit]:
        """Извлечение модуля (файла) с корректной обработкой имен."""
        try:
            # Получение имени модуля из пути к файлу
            file_name = file_path.split('/')[-1].replace('.py', '')
            if not file_name:
                file_name = "__init__"
            
            # Получение полного текста модуля
            module_text = self._get_node_text(node, source_bytes, source_code)
            
            location = Location(
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_column=node.start_point[1] + 1,
                end_column=node.end_point[1] + 1
            )
            
            code_span = CodeSpan(source_code=module_text)
            
            # Генерация уникального ID
            module_id = f"module_{file_name}_{hash(module_text) % 10000}"
            
            # Извлечение docstring модуля
            docstring = self._extract_module_docstring(node, source_code, source_bytes)
            
            return CodeUnit(
                id=module_id,
                name=file_name,
                type=CodeUnitType.MODULE,
                location=location,
                code_span=code_span,
                metadata={
                    'docstring': docstring,
                    'file_path': file_path,
                    'is_package': '__init__.py' in file_path.lower()
                },
                language="python"
            )
        except Exception as e:
            logger.error(f"Ошибка построения модуля {file_path}: {str(e)}", exc_info=True)
            return None
    
    def _extract_class_definition(self, node: Node, file_path: str, source_code: str, source_bytes: bytes, parent_id: str) -> Optional[CodeUnit]:
        """Извлечение определения класса с корректной обработкой имен."""
        try:
            # 1. Извлечение имени класса
            name_node = node.child_by_field_name('name')
            if not name_node:
                logger.warning(f"Не найден узел имени для класса в {file_path} at line {node.start_point[0] + 1}")
                return None
            
            class_name = self._get_node_text(name_node, source_bytes, source_code)
            if not class_name or len(class_name) > 100:  # Защита от очень длинных имен
                logger.warning(f"Некорректное имя класса: '{class_name}' в {file_path}")
                return None
            
            # 2. Получение текста всего класса
            class_text = self._get_node_text(node, source_bytes, source_code)
            
            # 3. Извлечение дополнительной информации
            bases = self._extract_class_bases(node, source_code, source_bytes)
            docstring = self._extract_docstring(node, source_code, source_bytes)
            decorators = self._extract_decorators(node, source_code, source_bytes)
            
            # 4. Создание location с валидацией
            start_line = max(1, node.start_point[0] + 1)
            end_line = max(start_line, node.end_point[0] + 1)
            
            location = Location(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                start_column=max(1, node.start_point[1] + 1),
                end_column=max(1, node.end_point[1] + 1)
            )
            
            code_span = CodeSpan(source_code=class_text)
            
            # 5. Генерация уникального ID
            class_id = f"class_{class_name}_{hash(class_text) % 10000}"
            
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
                    'methods_count': len([c for c in node.children if c.type in ['function_definition', 'async_function_definition']])
                },
                language="python"
            )
        except Exception as e:
            logger.error(f"Ошибка построения класса в {file_path}: {str(e)}", exc_info=True)
            return None
    
    def _extract_function_definition(self, node: Node, file_path: str, source_code: str, source_bytes: bytes, parent_id: str) -> Optional[CodeUnit]:
        """Извлечение определения функции с корректной обработкой имен."""
        try:
            # 1. Извлечение имени функции
            name_node = node.child_by_field_name('name')
            if not name_node:
                logger.warning(f"Не найден узел имени для функции в {file_path} at line {node.start_point[0] + 1}")
                return None
            
            func_name = self._get_node_text(name_node, source_bytes, source_code)
            if not func_name or len(func_name) > 100:
                logger.warning(f"Некорректное имя функции: '{func_name}' в {file_path}")
                return None
            
            # 2. Определение является ли функция методом класса
            is_method = parent_id and parent_id.startswith('class_')
            
            # 3. Получение текста всей функции
            func_text = self._get_node_text(node, source_bytes, source_code)
            
            # 4. Извлечение дополнительной информации
            parameters = self._extract_parameters(node, source_code, source_bytes)
            return_type = self._extract_return_type(node, source_code, source_bytes)
            docstring = self._extract_docstring(node, source_code, source_bytes)
            decorators = self._extract_decorators(node, source_code, source_bytes)
            is_async = node.type == 'async_function_definition' or 'async' in func_text[:50].lower()
            
            # 5. Создание location с валидацией
            start_line = max(1, node.start_point[0] + 1)
            end_line = max(start_line, node.end_point[0] + 1)
            
            location = Location(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                start_column=max(1, node.start_point[1] + 1),
                end_column=max(1, node.end_point[1] + 1)
            )
            
            code_span = CodeSpan(source_code=func_text)
            
            # 6. Генерация уникального ID
            func_type = CodeUnitType.METHOD if is_method else CodeUnitType.FUNCTION
            func_id = f"{'method' if is_method else 'func'}_{func_name}_{hash(func_text) % 10000}"
            
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
                    'is_method': is_method,
                    'is_constructor': is_method and func_name == '__init__'
                },
                language="python"
            )
        except Exception as e:
            logger.error(f"Ошибка построения функции {func_name} в {file_path}: {str(e)}", exc_info=True)
            return None

    def _extract_imports(self, node: Node, file_path: str, source_code: str, source_bytes: bytes, parent_id: Optional[str]) -> List[CodeUnit]:
        """Извлечение всех импортов из AST с корректной обработкой."""
        imports = []
        
        def walk_imports(current_node: Node):
            # Обработка импортов на текущем уровне
            if current_node.type == 'import_statement':
                self._process_import_statement(current_node, file_path, source_code, source_bytes, parent_id, imports)
            elif current_node.type == 'import_from_statement':
                self._process_import_from_statement(current_node, file_path, source_code, source_bytes, parent_id, imports)
                
            # Рекурсивный обход дочерних узлов
            for child in current_node.children:
                walk_imports(child)
        
        walk_imports(node)
        return imports

    def _process_import_statement(self, node: Node, file_path: str, source_code: str, source_bytes: bytes, 
                                parent_id: Optional[str], imports: List[CodeUnit]):
        """Обработка узла import_statement."""
        import_text = self._get_node_text(node, source_bytes, source_code)
        location = self._create_location(node, file_path)
        
        # Обработка каждого импорта в statement
        for child in node.children:
            if child.type == 'dotted_name':
                # Простой импорт: import module
                module_name = self._get_node_text(child, source_bytes, source_code)
                self._create_import_unit(
                    module_name, module_name, None, file_path, import_text,
                    location, parent_id, False, 'import', imports
                )
            elif child.type == 'aliased_import':
                # Импорт с алиасом: import module as alias
                name_node = child.child_by_field_name('name')
                alias_node = child.child_by_field_name('alias')
                if name_node and alias_node:
                    module_name = self._get_node_text(name_node, source_bytes, source_code)
                    alias_name = self._get_node_text(alias_node, source_bytes, source_code)
                    self._create_import_unit(
                        alias_name, module_name, alias_name, file_path, import_text,
                        location, parent_id, False, 'import', imports
                    )

    def _process_import_from_statement(self, node: Node, file_path: str, source_code: str, source_bytes: bytes,
                                  parent_id: Optional[str], imports: List[CodeUnit]):
        """Обработка узла import_from_statement с корректной обработкой различных типов импортов."""
        import_text = self._get_node_text(node, source_bytes, source_code)
        location = self._create_location(node, file_path)
        
        # 1. Получение имени модуля (from ... import)
        module_node = node.child_by_field_name('module_name')
        module_name = ""
        is_relative = False
        
        if module_node:
            module_name = self._get_node_text(module_node, source_bytes, source_code)
            is_relative = module_name.startswith('.')
        else:
            # Обработка относительных импортов без указания модуля (from . import name)
            dot_count = 0
            for child in node.children:
                if child.type == 'relative_import' or (child.type == 'dotted_name' and child.text.startswith(b'.')):
                    dot_count += 1
            if dot_count > 0:
                is_relative = True
                module_name = "." * dot_count
        
        # 2. Определение типа импорта и получение импортируемых имен
        import_type = "unknown"
        imported_items = []
        
        # Ищем все узлы после ключевого слова 'import'
        found_import_keyword = False
        for child in node.children:
            # Ищем ключевое слово 'import'
            if child.type == 'import':
                found_import_keyword = True
                continue
            
            # После ключевого слова 'import' обрабатываем все узлы как импортируемые имена
            if found_import_keyword:
                if child.type == 'wildcard_import':  # from module import *
                    imported_items.append(('*', None, None))
                    import_type = "wildcard"
                    break
                elif child.type in ['identifier', 'dotted_name']:
                    # Простой импорт: from module import name
                    name = self._get_node_text(child, source_bytes, source_code)
                    imported_items.append((name, None, None))
                    import_type = "simple"
                elif child.type == 'aliased_import':
                    # Обработка импорта с алиасом: from module import name as alias
                    name_node = child.child_by_field_name('name') or self._find_child_by_type(child, ['identifier', 'dotted_name'])
                    alias_node = child.child_by_field_name('alias') or self._find_child_by_type(child, ['identifier'])
                    
                    if name_node:
                        name = self._get_node_text(name_node, source_bytes, source_code)
                        alias = None
                        if alias_node:
                            alias = self._get_node_text(alias_node, source_bytes, source_code)
                        imported_items.append((name, alias, None))
                        import_type = "aliased"
            
            # Альтернативный поиск импортируемых имен, если не нашли после 'import'
            if not found_import_keyword and child.type in ['import_specifier', 'aliased_import', 'wildcard_import']:
                if child.type == 'wildcard_import':
                    imported_items.append(('*', None, None))
                    import_type = "wildcard"
                elif child.type == 'import_specifier':
                    # from module import name
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        name = self._get_node_text(name_node, source_bytes, source_code)
                        imported_items.append((name, None, None))
                        import_type = "simple"
                elif child.type == 'aliased_import':
                    # from module import name as alias
                    name_node = child.child_by_field_name('name')
                    alias_node = child.child_by_field_name('alias')
                    if name_node:
                        name = self._get_node_text(name_node, source_bytes, source_code)
                        alias = self._get_node_text(alias_node, source_bytes, source_code) if alias_node else None
                        imported_items.append((name, alias, None))
                        import_type = "aliased"
        
        # Если не нашли импортируемые имена, пытаемся найти их альтернативным способом
        if not imported_items:
            # Ищем все идентификаторы после модуля
            for i, child in enumerate(node.children):
                if child == module_node and i + 1 < len(node.children):
                    next_child = node.children[i + 1]
                    if next_child.type == 'import':
                        continue
                    
                    # Обработка одного имени
                    if next_child.type in ['identifier', 'dotted_name']:
                        name = self._get_node_text(next_child, source_bytes, source_code)
                        imported_items.append((name, None, None))
                        import_type = "simple"
                    
                    # Обработка списка имен
                    elif next_child.type == 'import_specifier_list':
                        for spec in next_child.children:
                            if spec.type in ['identifier', 'dotted_name']:
                                name = self._get_node_text(spec, source_bytes, source_code)
                                imported_items.append((name, None, None))
                                import_type = "simple"
                            elif spec.type == 'aliased_import':
                                name_node = spec.child_by_field_name('name')
                                alias_node = spec.child_by_field_name('alias')
                                if name_node:
                                    name = self._get_node_text(name_node, source_bytes, source_code)
                                    alias = self._get_node_text(alias_node, source_bytes, source_code) if alias_node else None
                                    imported_items.append((name, alias, None))
                                    import_type = "aliased"
        
        # 3. Создание CodeUnit для каждого импортируемого имени
        if not imported_items:
            # Если не найдены имена, создаем импорт для всего модуля
            if module_name:
                self._create_import_unit(
                    name=module_name.split('.')[-1],
                    module=module_name,
                    alias=None,
                    file_path=file_path,
                    import_text=import_text,
                    location=location,
                    parent_id=parent_id,
                    is_relative=is_relative,
                    import_type="from_import",
                    imports=imports
                )
            return
        
        # Обработка каждого импортируемого имени
        for name, alias, original_name in imported_items:
            if name == '*':
                # Создаем импорт для wildcard
                self._create_import_unit(
                    name="*",
                    module=module_name,
                    alias=None,
                    file_path=file_path,
                    import_text=import_text,
                    location=location,
                    parent_id=parent_id,
                    is_relative=is_relative,
                    import_type="from_import_wildcard",
                    imports=imports
                )
            else:
                # Создаем импорт для конкретного имени
                self._create_import_unit(
                    name=alias or name,
                    module=module_name,
                    alias=alias,
                    file_path=file_path,
                    import_text=import_text,
                    location=location,
                    parent_id=parent_id,
                    is_relative=is_relative,
                    import_type=f"from_import_{import_type}",
                    imports=imports
                )

    def _find_child_by_type(self, node: Node, target_types: List[str]) -> Optional[Node]:
        """Поиск первого дочернего узла заданного типа."""
        for child in node.children:
            if child.type in target_types:
                return child
        return None


    def _process_single_import_specifier(self, node: Node, module_name: str, is_relative: bool,
                                        file_path: str, import_text: str, location: Location,
                                        parent_id: Optional[str], imports: List[CodeUnit],
                                        source_code: str, source_bytes: bytes,):
        """Обработка одного импортируемого имени."""
        # Определение типа узла импорта
        if node.type == 'import_specifier':
            name_node = node.child_by_field_name('name')
            alias_node = node.child_by_field_name('alias')
            
            if name_node:
                name = self._get_node_text(name_node, source_bytes, source_code)
                alias = None
                if alias_node:
                    alias = self._get_node_text(alias_node, source_bytes, source_code)
                
                self._create_import_unit(
                    alias or name, module_name, alias, file_path, import_text,
                    location, parent_id, is_relative, 'from_import', imports
                )
        elif node.type == 'aliased_import':
            name_node = node.child_by_field_name('name') or node.named_children[0]
            alias_node = node.child_by_field_name('alias') or node.named_children[-1]
            
            if name_node and alias_node:
                name = self._get_node_text(name_node, source_bytes, source_code)
                alias = self._get_node_text(alias_node, source_bytes, source_code)
                self._create_import_unit(
                    alias, module_name, alias, file_path, import_text,
                    location, parent_id, is_relative, 'from_import', imports
                )

    def _create_import_unit(self, name: str, module: str, alias: Optional[str], file_path: str,
                        import_text: str, location: Location, parent_id: Optional[str],
                        is_relative: bool, import_type: str, imports: List[CodeUnit]):
        """Создание CodeUnit для импорта."""
        if not name or not module:
            return
            
        import_id = f"import_{name.replace('.', '_')}_{hash(import_text) % 10000}"
        import_unit = CodeUnit(
            id=import_id,
            name=name,
            type=CodeUnitType.IMPORT,
            location=location,
            code_span=CodeSpan(source_code=import_text),
            parent_id=parent_id,
            metadata={
                'import_type': import_type,
                'original_text': import_text,
                'module': module,
                'alias': alias,
                'is_relative': is_relative
            },
            language="python"
        )
        imports.append(import_unit)

    def _create_location(self, node: Node, file_path: str) -> Location:
        """Создание объекта Location с валидацией координат."""
        return Location(
            file_path=file_path,
            start_line=max(1, node.start_point[0] + 1),
            end_line=max(1, node.end_point[0] + 1),
            start_column=max(1, node.start_point[1] + 1),
            end_column=max(1, node.end_point[1] + 1)
        )

    def _extract_module_docstring(self, node: Node, source_code: str, source_bytes: bytes) -> Optional[str]:
        """Извлечение docstring модуля."""
        # Поиск первого выражения в модуле
        for child in node.children:
            if child.type == 'expression_statement':
                for grandchild in child.children:
                    if grandchild.type == 'string':
                        string_content = self._get_node_text(grandchild, source_bytes, source_code)
                        # Очистка от кавычек
                        return string_content.strip('"\'')
        return None
    
    def _extract_docstring(self, node: Node, source_code: str, source_bytes: bytes) -> Optional[str]:
        """Извлечение docstring из узла."""
        # Поиск тела узла
        body_node = node.child_by_field_name('body')
        if not body_node:
            return None
        
        # Поиск первого выражения в теле
        for child in body_node.children:
            if child.type == 'expression_statement':
                for grandchild in child.children:
                    if grandchild.type == 'string':
                        string_content = self._get_node_text(grandchild, source_bytes, source_code)
                        # Очистка от кавычек и экранирования
                        docstring = re.sub(r'^[\'"]+|[\'"]+$', '', string_content)
                        docstring = re.sub(r'\\(["\'])', r'\1', docstring)
                        docstring = docstring.strip()
                        return docstring if docstring else None
        return None
    
    def _extract_decorators(self, node: Node, source_code: str, source_bytes: bytes) -> List[str]:
        """Извлечение декораторов из узла."""
        decorators = []
        
        # Поиск декораторов над определением
        for child in node.children:
            if child.type == 'decorator':
                decorator_text = self._get_node_text(child, source_bytes, source_code)
                decorators.append(decorator_text)
        
        return decorators
    
    def _extract_class_bases(self, node: Node, source_code: str, source_bytes: bytes) -> List[str]:
        """Извлечение базовых классов для класса."""
        bases = []
        superclass_node = node.child_by_field_name('superclasses')
        
        if superclass_node:
            for base in superclass_node.children:
                if base.type != ',' and base.type != '(' and base.type != ')':  # Пропускаем разделители
                    base_name = self._get_node_text(base, source_bytes, source_code)
                    bases.append(base_name)
        
        return bases
    
    def _extract_parameters(self, node: Node, source_code: str, source_bytes: bytes) -> List[Dict[str, Any]]:
        """Извлечение параметров функции."""
        params = []
        parameters_node = node.child_by_field_name('parameters')
        
        if not parameters_node:
            return params
        
        for param_node in parameters_node.children:
            if param_node.type == 'identifier':
                param_name = self._get_node_text(param_node, source_bytes, source_code)
                if param_name:
                    params.append({
                        'name': param_name,
                        'line': param_node.start_point[0] + 1
                    })
            elif param_node.type == 'typed_parameter':
                name_node = param_node.child_by_field_name('name')
                type_node = param_node.child_by_field_name('type')
                if name_node:
                    param_name = self._get_node_text(name_node, source_bytes, source_code)
                    param_type = self._get_node_text(type_node, source_bytes, source_code) if type_node else None
                    params.append({
                        'name': param_name,
                        'type_annotation': param_type,
                        'line': param_node.start_point[0] + 1
                    })
            elif param_node.type == 'default_parameter':
                name_node = param_node.child_by_field_name('name')
                value_node = param_node.child_by_field_name('value')
                if name_node:
                    param_name = self._get_node_text(name_node, source_bytes, source_code)
                    default_value = self._get_node_text(value_node, source_bytes, source_code) if value_node else None
                    params.append({
                        'name': param_name,
                        'default_value': default_value,
                        'line': param_node.start_point[0] + 1
                    })
        
        return params
    
    def _extract_return_type(self, node: Node, source_code: str, source_bytes: bytes) -> Optional[str]:
        """Извлечение возвращаемого типа функции."""
        return_type_node = node.child_by_field_name('return_type')
        if return_type_node:
            return self._get_node_text(return_type_node, source_bytes, source_code)
        return None
    
    def _extract_global_variables(self, node: Node, file_path: str, source_code: str, source_bytes: bytes, parent_id: Optional[str]) -> List[CodeUnit]:
        """Извлечение глобальных переменных уровня модуля с корректной обработкой."""
        variables = []
        
        def walk_globals(current_node: Node):
            # Поиск присваиваний на уровне модуля
            if current_node.type == 'assignment':
                # Проверка на простое присваивание переменной
                if len(current_node.children) >= 2 and current_node.children[0].type == 'identifier':
                    left = current_node.children[0]
                    right = current_node.children[1]
                    
                    var_name = self._get_node_text(left, source_bytes, source_code).strip()
                    if var_name and var_name.isidentifier():
                        var_value = self._get_node_text(right, source_bytes, source_code)[:100] + "..." if len(self._get_node_text(right, source_bytes, source_code)) > 100 else self._get_node_text(right, source_bytes, source_code)
                        
                        location = Location(
                            file_path=file_path,
                            start_line=max(1, current_node.start_point[0] + 1),
                            end_line=max(1, current_node.end_point[0] + 1),
                            start_column=max(1, current_node.start_point[1] + 1),
                            end_column=max(1, current_node.end_point[1] + 1)
                        )
                        
                        var_text = self._get_node_text(current_node, source_bytes, source_code)
                        var_id = f"var_{var_name}_{hash(var_text) % 10000}"
                        
                        var_unit = CodeUnit(
                            id=var_id,
                            name=var_name,
                            type=CodeUnitType.VARIABLE,
                            location=location,
                            code_span=CodeSpan(source_code=var_text),
                            parent_id=parent_id,
                            metadata={
                                'value': var_value,
                                'is_constant': var_name.isupper(),
                                'line': location.start_line
                            },
                            language="python"
                        )
                        variables.append(var_unit)
            
            # Рекурсивный обход, но пропускаем функции и классы
            for child in current_node.children:
                if child.type not in ['class_definition', 'function_definition', 'block', 'decorated_definition']:
                    walk_globals(child)
        
        walk_globals(node)
        return variables
    
    def _extract_class_methods(self, node: Node, file_path: str, source_code: str, source_bytes: bytes, parent_id: str) -> List[CodeUnit]:
        """Извлечение методов класса."""
        methods = []
        
        # Поиск тела класса
        body_node = node.child_by_field_name('body')
        if not body_node:
            return methods
        
        for child in body_node.children:
            if child.type in ['function_definition', 'async_function_definition']:
                method_unit = self._extract_function_definition(child, file_path, source_code, source_bytes, parent_id)
                if method_unit:
                    methods.append(method_unit)
        
        return methods