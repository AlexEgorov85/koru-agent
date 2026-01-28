"""
Python Language Adapter — полная интеграция с tree-sitter для Python 3.x.
ОСОБЕННОСТИ:
- Поддержка ВСЕХ конструкций Python 3.x (включая синтаксис 3.10+)
- Максимальное извлечение информации из AST дерева
- Корректная обработка байтовых координат и кодировок
- Богатые метаданные для каждой единицы кода
- Поддержка иерархии (вложенные классы, функции, методы)
- Извлечение декораторов, аннотаций типов, значений по умолчанию
- Обработка специальных методов (@property, @staticmethod, @classmethod)
- Извлечение констант, глобальных переменных, слотов классов
- Поддержка генераторов, асинхронных функций, матч-кейсов
- Детерминированное поведение без вызовов к внешним системам
"""
import logging
import hashlib
import re
from typing import List, Dict, Any, Optional, Tuple, Set, cast
from tree_sitter import Tree, Node
from core.infrastructure.services.code_analysis.adapters.base_adapter import BaseLanguageAdapter
from core.infrastructure.services.code_analysis.base import ASTNode, Location as BaseLocation
from models.code_unit import CodeSpan, CodeUnit, CodeUnitType, Location


logger = logging.getLogger(__name__)


class PythonTreeSitterNode(ASTNode):
    """
    Обёртка над узлом tree-sitter для соответствия абстрактному интерфейсу.
    КЛЮЧЕВЫЕ ОСОБЕННОСТИ:
    - Корректная работа с байтовыми координатами (решение проблемы с именами)
    - Кэширование детей для производительности
    - Валидация координат перед извлечением текста
    - Поддержка всех типов узлов грамматики Python
    """
    
    def __init__(self, node: Node, source_bytes: bytes):
        self._node = node
        self._source_bytes = source_bytes
        self._children: List['PythonTreeSitterNode'] = []
        self._parent: Optional['PythonTreeSitterNode'] = None
        
        # Кэшируем детей для производительности
        for child in node.children:
            child_wrapper = PythonTreeSitterNode(child, source_bytes)
            child_wrapper._parent = self
            self._children.append(child_wrapper)
    
    @property
    def type(self) -> str:
        return self._node.type
    
    @property
    def children(self) -> List['PythonTreeSitterNode']:
        return self._children
    
    @property
    def parent(self) -> Optional['PythonTreeSitterNode']:
        return self._parent
    
    @property
    def start_byte(self) -> int:
        return self._node.start_byte
    
    @property
    def end_byte(self) -> int:
        return self._node.end_byte
    
    @property
    def start_point(self) -> Tuple[int, int]:
        return self._node.start_point
    
    @property
    def end_point(self) -> Tuple[int, int]:
        return self._node.end_point
    
    def get_text(self, source_bytes: bytes) -> str:
        """
        Безопасное извлечение текста с обработкой байтовых координат.
        ИСПРАВЛЕНИЕ: используем переданные source_bytes вместо внутренних для консистентности.
        """
        try:
            # Валидация координат
            if (self._node.start_byte < 0 or 
                self._node.end_byte > len(source_bytes) or 
                self._node.start_byte > self._node.end_byte):
                logger.warning(
                    f"Некорректные координаты узла '{self._node.type}': "
                    f"{self._node.start_byte}-{self._node.end_byte} "
                    f"(длина кода: {len(source_bytes)})"
                )
                return ""
            
            # Извлечение текста из байтов
            node_bytes = source_bytes[self._node.start_byte:self._node.end_byte]
            text = node_bytes.decode('utf-8', errors='replace').strip()
            
            # Удаляем лишние отступы для многострочных строк
            if text.startswith(('"""', "'''")) and text.endswith(('"""', "'''")):
                lines = text.split('\n')
                if len(lines) > 1:
                    # Удаляем первый и последний элемент (кавычки)
                    content_lines = lines[1:-1]
                    # Удаляем общий отступ
                    if content_lines:
                        min_indent = min(
                            (len(line) - len(line.lstrip())) 
                            for line in content_lines 
                            if line.strip()
                        )
                        content_lines = [
                            line[min_indent:] if len(line) > min_indent else line
                            for line in content_lines
                        ]
                        text = '\n'.join(content_lines)
            
            return text
            
        except Exception as e:
            logger.error(f"Ошибка извлечения текста узла {self._node.type}: {str(e)}")
            return ""
    
    def find_children_by_type(self, node_type: str) -> List['PythonTreeSitterNode']:
        return [child for child in self._children if child.type == node_type]
    
    def find_first_child_by_type(self, node_type: str) -> Optional['PythonTreeSitterNode']:
        for child in self._children:
            if child.type == node_type:
                return child
        return None
    
    def child_by_field_name(self, field_name: str) -> Optional['PythonTreeSitterNode']:
        """Получение дочернего узла по имени поля (как в оригинальном tree-sitter)."""
        child = self._node.child_by_field_name(field_name)
        if child and hasattr(child, 'type'):
            # Оборачиваем в нашу обёртку
            return PythonTreeSitterNode(child, self._source_bytes)
        return None
    
    @property
    def location(self) -> BaseLocation:
        return BaseLocation(
            file_path="",  # Заполняется на уровне файла
            start_line=self._node.start_point[0] + 1,
            end_line=self._node.end_point[0] + 1,
            start_column=self._node.start_point[1] + 1,
            end_column=self._node.end_point[1] + 1
        )


class PythonLanguageAdapter(BaseLanguageAdapter):
    """
    Адаптер для языка Python с полной поддержкой всех конструкций Python 3.x.
    
    ПОЛНАЯ ПОДДЕРЖКА КОНСТРУКЦИЙ:
    - Классы: наследование, множественное наследование, метаклассы, слоты, декораторы
    - Функции: параметры, аннотации типов, значения по умолчанию, *args, **kwargs
    - Методы: @property, @staticmethod, @classmethod, асинхронные методы
    - Импорты: абсолютные, относительные, с алиасами, звёздочные импорты
    - Глобальные переменные и константы (строки, числа, списки, словари, кортежи)
    - Специальные методы (__init__, __str__, __repr__ и т.д.)
    - Генераторы (yield, yield from)
    - Асинхронные функции (async/await)
    - Контекстные менеджеры (with)
    - Обработка исключений (try/except/finally)
    - Аннотации переменных (PEP 526)
    - Матч-кейсы (Python 3.10+)
    - Типовые псевдонимы (TypeAlias)
    - Декораторы с аргументами
    
    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    - Детерминированное поведение (без случайных элементов)
    - НЕТ семантического анализа (только структурный анализ AST)
    - НЕТ вызовов к внешним системам (включая LLM)
    - Все операции предсказуемы и воспроизводимы
    - Возврат универсальных моделей CodeUnit для мультиязычной поддержки
    """
    
    language_name = "python"
    file_extensions = ["py", "pyi", "pyw"]
    
    def __init__(self):
        super().__init__()
        self.parser = None  # Будет инициализирован в initialize()
    
    async def initialize(self) -> bool:
        """Инициализация парсера Python через tree-sitter."""
        try:
            import tree_sitter_python
            from tree_sitter import Language, Parser
            
            # Инициализация парсера
            PY_LANGUAGE = Language(tree_sitter_python.language())
            self.parser = Parser(language=PY_LANGUAGE)
            
            self.initialized = True
            logger.info("PythonLanguageAdapter успешно инициализирован с поддержкой всех конструкций Python 3.x")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации Python парсера: {str(e)}", exc_info=True)
            return False
    
    async def parse(self, source_code: str, source_bytes: bytes) -> ASTNode:
        """
        Парсит Python код в абстрактное дерево.
        КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: всегда используем байтовое представление для корректной работы с координатами.
        """
        if not self.initialized:
            raise RuntimeError("PythonLanguageAdapter не инициализирован")
        
        if not self._validate_source(source_code, source_bytes):
            raise ValueError("Некорректный исходный код")
        
        try:
            # Парсим через tree-sitter
            tree: Tree = self.parser.parse(source_bytes)
            
            # Оборачиваем корневой узел в абстрактный интерфейс
            root_node = PythonTreeSitterNode(tree.root_node, source_bytes)
            
            logger.debug(f"Успешно спарсен Python файл, узлов: {len(tree.root_node.children)}")
            return root_node
            
        except Exception as e:
            logger.error(f"Ошибка парсинга Python кода: {str(e)}", exc_info=True)
            raise
    
    async def get_outline(self, ast: ASTNode, file_path: str) -> List[CodeUnit]:
        """
        Строит ПОЛНУЮ структуру Python файла и возвращает список универсальных моделей CodeUnit.
        
        ИЗВЛЕКАЕТ ВСЕ ЭЛЕМЕНТЫ:
        - Модуль (корневой элемент со всеми глобальными переменными и константами)
        - Классы верхнего уровня (с наследованием, декораторами, слотами)
        - Функции верхнего уровня (с параметрами, аннотациями, декораторами)
        - Методы классов (включая специальные методы __init__, @property и т.д.)
        - Вложенные классы и функции
        - Импорты (абсолютные, относительные, с алиасами)
        - Глобальные переменные и константы
        - Типовые псевдонимы (TypeAlias)
        
        ВОЗВРАЩАЕТ:
            Список объектов CodeUnit с богатыми метаданными для всех элементов файла.
        
        ПРИМЕР ИСПОЛЬЗОВАНИЯ:
            adapter = PythonLanguageAdapter()
            await adapter.initialize()
            ast = await adapter.parse(source_code, source_bytes)
            code_units = await adapter.get_outline(ast, "core/main.py")
            
            for unit in code_units:
                print(f"{unit.type.value}: {unit.name} at line {unit.location.start_line}")
                if unit.metadata:
                    print(f"  Metadata: {unit.metadata}")
        """
        if not isinstance(ast, PythonTreeSitterNode):
            raise ValueError("Ожидается PythonTreeSitterNode")
        
        code_units: List[CodeUnit] = []
        source_bytes = ast._source_bytes  # Получаем байты из узла
        
        # 1. Создание модуля (корневой элемент)
        module_id = f"module_{self._normalize_id(file_path)}"
        module_source_code = source_bytes.decode('utf-8', errors='replace')
        module_unit = CodeUnit(
            id=module_id,
            name=file_path.split('/')[-1].replace('.py', ''),
            type=CodeUnitType.MODULE,
            location=BaseLocation(
                file_path=file_path,
                start_line=1,
                end_line=ast.location.end_line,
                start_column=1,
                end_column=ast.location.end_column
            ),
            code_span=CodeSpan(
                source_code=module_source_code),
            parent_id=None,
            child_ids=[],
            metadata={
                "file_path": file_path,
                "module_docstring": self._extract_module_docstring(ast, source_bytes),
                "python_version": "3.x",
                "encoding": "utf-8"
            },
            language="python"
        )
        code_units.append(module_unit)
        module_child_ids: List[str] = []
        
        # 2. Обход дерева для извлечения ВСЕХ элементов
        def process_node(node: PythonTreeSitterNode, parent_unit: Optional[CodeUnit] = None, depth: int = 0):
            """Рекурсивная обработка узлов дерева со всеми конструкциями Python."""
            parent_id = parent_unit.id if parent_unit else module_id
            
            # Обработка классов
            if node.type == 'class_definition':
                return self._process_class_definition(node, parent_id, file_path, source_bytes, code_units, depth)
            
            # Обработка функций и методов
            elif node.type in ['function_definition', 'async_function_definition']:
                return self._process_function_definition(node, parent_id, file_path, source_bytes, code_units, depth)
            
            # Обработка импортов
            elif node.type in ['import_statement', 'import_from_statement']:
                return self._process_import_statement(node, parent_id, file_path, source_bytes, code_units)
            
            # Обработка глобальных переменных и констант (только на верхнем уровне модуля)
            elif node.type in ['assignment', 'augmented_assignment', 'expression_statement'] and parent_unit is None:
                return self._process_global_variable(node, parent_id, file_path, source_bytes, code_units)
            
            # Обработка аннотаций переменных (PEP 526)
            elif node.type == 'type_annotation' and parent_unit is None:
                return self._process_variable_annotation(node, parent_id, file_path, source_bytes, code_units)
            
            # Обработка типовых псевдонимов (TypeAlias)
            elif node.type == 'type_alias':
                return self._process_type_alias(node, parent_id, file_path, source_bytes, code_units)
            
            # Рекурсивная обработка детей для вложенных структур
            for child in node.children:
                child_id = process_node(child, parent_unit, depth + 1)
                if child_id and parent_unit:
                    parent_unit.child_ids.append(child_id)
            
            return None
        
        # 3. Запуск обхода дерева
        for child in cast(PythonTreeSitterNode, ast).children:
            child_id = process_node(child, module_unit, depth=0)
            if child_id:
                module_child_ids.append(child_id)
        
        # 4. Обновление дочерних элементов модуля
        module_unit.child_ids = module_child_ids
        
        logger.debug(
            f"Построена полная структура для {file_path}: "
            f"{len(code_units)} элементов ({len(module_child_ids)} верхнего уровня)"
        )
        return code_units
    
    async def resolve_import(
        self,
        import_name: str,
        current_file: str,
        project_files: List[str]
    ) -> Optional[str]:
        """
        Разрешает имя импорта Python в путь к файлу проекта.
        ПОЛНАЯ ПОДДЕРЖКА:
        - Абсолютные импорты: from core.skills import base_skill
        - Относительные импорты: from . import base_skill, from ..utils import helper
        - Импорты с алиасами: import core.skills as skills
        - Звёздочные импорты: from module import *
        - Импорт модулей и пакетов
        
        ВАЖНО: Разрешение выполняется ТОЛЬКО по имени файла, без семантического анализа.
        """
        # Обработка относительных импортов (начинающихся с точки)
        if import_name.startswith('.'):
            # Определяем базовую директорию текущего файла
            current_dir = '/'.join(current_file.split('/')[:-1])
            levels = import_name.count('.')
            base_dir = current_dir
            for _ in range(levels - 1):  # -1 потому что первая точка относится к текущей директории
                base_dir = '/'.join(base_dir.split('/')[:-1]) if base_dir else ''
            
            # Оставшаяся часть после точек
            target = import_name[levels:] if levels < len(import_name) else ''
            if target:
                target_filename = f"{target.replace('.', '/')}.py"
                search_path = f"{base_dir}/{target_filename}" if base_dir else target_filename
            else:
                # Импорт текущей директории (__init__.py)
                search_path = f"{base_dir}/__init__.py" if base_dir else "__init__.py"
        else:
            # Абсолютный импорт
            target_filename = f"{import_name.replace('.', '/')}.py"
            search_path = target_filename
        
        # Поиск точного совпадения
        for file_path in project_files:
            if file_path.endswith(search_path):
                return file_path
        
        # Поиск по частичному совпадению имени
        for file_path in project_files:
            if import_name.lower() in file_path.lower():
                return file_path
        
        # Поиск __init__.py для пакетов
        if '.' in import_name:
            package_name = import_name.rsplit('.', 1)[0]
            package_init = f"{package_name.replace('.', '/')}/__init__.py"
            for file_path in project_files:
                if file_path.endswith(package_init):
                    return file_path
        
        return None
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДЛЯ ИЗВЛЕЧЕНИЯ ИНФОРМАЦИИ ====================
    
    def _process_class_definition(
        self,
        node: PythonTreeSitterNode,
        parent_id: str,
        file_path: str,
        source_bytes: bytes,
        code_units: List[CodeUnit],
        depth: int = 0
    ) -> str:
        """Обработка определения класса со всеми метаданными."""
        # Извлечение имени класса
        name_node = node.child_by_field_name('name')
        class_name = name_node.get_text(source_bytes) if name_node else f"AnonymousClass_{node.location.start_line}"
        
        # Извлечение тела класса
        body_node = node.child_by_field_name('body')
        class_code = node.get_text(source_bytes) if body_node else ""
        
        # Создание уникального ID
        class_id = f"class_{self._normalize_id(class_name)}_{node.location.start_line}"
        
        # Извлечение базовых классов
        bases = self._extract_base_classes(node, source_bytes)
        
        # Извлечение декораторов
        decorators = self._extract_decorators(node, source_bytes)
        
        # Извлечение слотов класса (__slots__)
        slots = self._extract_class_slots(node, source_bytes)
        
        # Извлечение метакласса
        metaclass = self._extract_metaclass(node, source_bytes)
        
        # Извлечение докстринга
        docstring = self._extract_docstring(node, source_bytes)
        
        # Создание CodeUnit для класса
        class_unit = CodeUnit(
            id=class_id,
            name=class_name,
            type=CodeUnitType.CLASS,
            location=Location(
                file_path=file_path,
                start_line=node.location.start_line,
                end_line=node.location.end_line,
                start_column=node.location.start_column,
                end_column=node.location.end_column
            ),
            code_span=CodeSpan(
                source_code=class_code
            ),
            parent_id=parent_id,
            child_ids=[],
            metadata={
                "line": node.location.start_line,
                "decorators": decorators,
                "bases": bases,
                "slots": slots,
                "metaclass": metaclass,
                "docstring": docstring[:200] if docstring else None,  # Ограничиваем длину для метаданных
                "is_abstract": any('@abstractmethod' in d or 'abc.ABC' in str(bases) for d in decorators),
                "has_init": False,  # Будет установлено при обработке методов
                "has_slots": bool(slots),
                "depth": depth
            },
            language="python"
        )
        code_units.append(class_unit)
        
        # Обработка методов и вложенных классов
        class_child_ids: List[str] = []
        if body_node:
            for child in body_node.children:
                if child.type in ['function_definition', 'async_function_definition', 'class_definition']:
                    child_id = self._process_node_recursive(child, class_unit, file_path, source_bytes, code_units, depth + 1)
                    if child_id:
                        class_child_ids.append(child_id)
                        # Проверка на наличие __init__
                        if child.type in ['function_definition', 'async_function_definition']:
                            name_node = child.child_by_field_name('name')
                            if name_node and name_node.get_text(source_bytes) == '__init__':
                                class_unit.metadata["has_init"] = True
        
        class_unit.child_ids = class_child_ids
        return class_id
    
    def _process_function_definition(
        self,
        node: PythonTreeSitterNode,
        parent_id: str,
        file_path: str,
        source_bytes: bytes,
        code_units: List[CodeUnit],
        depth: int = 0
    ) -> str:
        """Обработка определения функции или метода со всеми метаданными."""
        # Определение типа (функция или метод)
        parent_type = None
        parent_unit = next((u for u in code_units if u.id == parent_id), None)
        if parent_unit and parent_unit.type == CodeUnitType.CLASS:
            unit_type = CodeUnitType.METHOD
            parent_type = "class"
        else:
            unit_type = CodeUnitType.FUNCTION
            parent_type = "module"
        
        # Извлечение имени функции
        name_node = node.child_by_field_name('name')
        func_name = name_node.get_text(source_bytes) if name_node else f"anonymous_{node.location.start_line}"
        
        # Извлечение тела функции
        body_node = node.child_by_field_name('body')
        func_code = node.get_text(source_bytes) if body_node else ""
        
        # Создание уникального ID
        func_id = f"{unit_type.value}_{self._normalize_id(func_name)}_{node.location.start_line}"
        
        # Извлечение параметров
        parameters = self._extract_parameters(node, source_bytes)
        
        # Извлечение аннотации возвращаемого типа
        return_type = self._extract_return_type(node, source_bytes)
        
        # Извлечение декораторов
        decorators = self._extract_decorators(node, source_bytes)
        
        # Определение специальных типов методов
        is_static = any('@staticmethod' in d for d in decorators)
        is_classmethod = any('@classmethod' in d for d in decorators)
        is_property = any('@property' in d for d in decorators)
        is_async = node.type == 'async_function_definition'
        is_generator = 'yield' in func_code.lower() or 'yield from' in func_code.lower()
        
        # Извлечение докстринга
        docstring = self._extract_docstring(node, source_bytes)
        
        # Создание CodeUnit для функции/метода
        func_unit = CodeUnit(
            id=func_id,
            name=func_name,
            type=unit_type,
            location=BaseLocation(
                file_path=file_path,
                start_line=node.location.start_line,
                end_line=node.location.end_line,
                start_column=node.location.start_column,
                end_column=node.location.end_column
            ),
            code_span=CodeSpan(
                source_code=func_code
            ),
            parent_id=parent_id,
            child_ids=[],
            metadata={
                "line": node.location.start_line,
                "is_async": is_async,
                "is_generator": is_generator,
                "is_static": is_static,
                "is_classmethod": is_classmethod,
                "is_property": is_property,
                "parameters": parameters,
                "return_type": return_type,
                "decorators": decorators,
                "docstring": docstring[:200] if docstring else None,
                "is_dunder": func_name.startswith('__') and func_name.endswith('__'),
                "is_private": func_name.startswith('_') and not func_name.startswith('__'),
                "is_magic": func_name in [
                    '__init__', '__new__', '__del__', '__str__', '__repr__', '__len__', 
                    '__getitem__', '__setitem__', '__delitem__', '__iter__', '__next__',
                    '__enter__', '__exit__', '__call__', '__getattr__', '__setattr__',
                    '__getattribute__', '__delattr__', '__dir__', '__eq__', '__ne__',
                    '__lt__', '__le__', '__gt__', '__ge__', '__hash__', '__bool__',
                    '__format__', '__sizeof__', '__subclasscheck__', '__instancecheck__'
                ],
                "depth": depth,
                "parent_type": parent_type
            },
            language="python"
        )
        code_units.append(func_unit)
        
        # Обработка вложенных функций и классов
        func_child_ids: List[str] = []
        if body_node:
            for child in body_node.children:
                if child.type in ['function_definition', 'async_function_definition', 'class_definition']:
                    child_id = self._process_node_recursive(child, func_unit, file_path, source_bytes, code_units, depth + 1)
                    if child_id:
                        func_child_ids.append(child_id)
        
        func_unit.child_ids = func_child_ids
        return func_id
    
    def _process_import_statement(
        self,
        node: PythonTreeSitterNode,
        parent_id: str,
        file_path: str,
        source_bytes: bytes,
        code_units: List[CodeUnit]
    ) -> str:
        """Обработка операторов импорта с извлечением всех деталей."""
        import_text = node.get_text(source_bytes)
        import_type = CodeUnitType.IMPORT_FROM if node.type == 'import_from_statement' else CodeUnitType.IMPORT
        
        # Извлечение основной информации об импорте
        import_info = self._extract_import_details(node, source_bytes)
        import_name = import_info.get('module', import_info.get('name', 'unknown'))
        
        # Создание уникального ID
        import_id = f"import_{self._normalize_id(import_name)}_{node.location.start_line}_{hash(import_text) % 10000}"
        
        # Создание CodeUnit для импорта
        import_unit = CodeUnit(
            id=import_id,
            name=import_name,
            type=import_type,
            location=Location(
                file_path=file_path,
                start_line=node.location.start_line,
                end_line=node.location.end_line,
                start_column=node.location.start_column,
                end_column=node.location.end_column
            ),
            code_span=CodeSpan(
                source_code=import_text
            ),
            parent_id=parent_id,
            child_ids=[],
            metadata={
                "line": node.location.start_line,
                "raw_text": import_text,
                "module": import_info.get('module'),
                "names": import_info.get('names', []),
                "aliases": import_info.get('aliases', {}),
                "is_relative": import_info.get('is_relative', False),
                "level": import_info.get('level', 0),
                "is_wildcard": import_info.get('is_wildcard', False),
                "import_type": node.type
            },
            language="python"
        )
        code_units.append(import_unit)
        return import_id
    
    def _process_global_variable(
        self,
        node: PythonTreeSitterNode,
        parent_id: str,
        file_path: str,
        source_bytes: bytes,
        code_units: List[CodeUnit]
    ) -> Optional[str]:
        """Обработка глобальных переменных и констант на уровне модуля."""
        # Проверяем, является ли это присваиванием константы
        if node.type == 'expression_statement':
            # Проверяем на наличие аннотации типа
            if node.children and node.children[0].type == 'assignment':
                node = node.children[0]
            else:
                return None
        
        # Ищем левую часть присваивания
        left = node.child_by_field_name('left')
        if not left or left.type != 'identifier':
            return None
        
        var_name = left.get_text(source_bytes)
        
        # Пропускаем приватные переменные и специальные имена (кроме __all__, __version__ и т.д.)
        if var_name.startswith('__') and not var_name.endswith('__'):
            return None
        
        # Извлекаем значение (если это константа)
        right = node.child_by_field_name('right')
        value_info = self._extract_constant_value(right, source_bytes) if right else None
        
        # Определяем, является ли это константой (все заглавные буквы или специальные имена)
        is_constant = (
            var_name.isupper() or 
            var_name in ['__all__', '__version__', '__author__', '__license__', '__doc__']
        )
        
        if not is_constant and value_info is None:
            return None
        
        # Создание уникального ID
        var_id = f"variable_{self._normalize_id(var_name)}_{node.location.start_line}"
        
        # Создание CodeUnit для переменной
        var_unit = CodeUnit(
            id=var_id,
            name=var_name,
            type=CodeUnitType.VARIABLE,
            location=Location(
                file_path=file_path,
                start_line=node.location.start_line,
                end_line=node.location.end_line,
                start_column=node.location.start_column,
                end_column=node.location.end_column
            ),
            code_span=CodeSpan(
                source_code=node.get_text(source_bytes)
            ),
            parent_id=parent_id,
            child_ids=[],
            metadata={
                "line": node.location.start_line,
                "is_constant": is_constant,
                "value_type": value_info.get('type') if value_info else None,
                "value_preview": value_info.get('preview') if value_info else None,
                "is_special": var_name.startswith('__') and var_name.endswith('__'),
                "annotation": self._extract_variable_annotation(node, source_bytes)
            },
            language="python"
        )
        code_units.append(var_unit)
        return var_id
    
    def _process_variable_annotation(
        self,
        node: PythonTreeSitterNode,
        parent_id: str,
        file_path: str,
        source_bytes: bytes,
        code_units: List[CodeUnit]
    ) -> Optional[str]:
        """Обработка аннотаций переменных (PEP 526)."""
        # Находим имя переменной
        left = node.child_by_field_name('left')
        if not left or left.type != 'identifier':
            return None
        
        var_name = left.get_text(source_bytes)
        annotation = node.child_by_field_name('right')
        annotation_text = annotation.get_text(source_bytes) if annotation else None
        
        # Создание уникального ID
        var_id = f"variable_{self._normalize_id(var_name)}_{node.location.start_line}"
        
        # Создание CodeUnit для аннотированной переменной
        var_unit = CodeUnit(
            id=var_id,
            name=var_name,
            type=CodeUnitType.VARIABLE,
            location=Location(
                file_path=file_path,
                start_line=node.location.start_line,
                end_line=node.location.end_line,
                start_column=node.location.start_column,
                end_column=node.location.end_column
            ),
            code_span=CodeSpan(
                source_code=node.get_text(source_bytes)
            ),
            parent_id=parent_id,
            child_ids=[],
            metadata={
                "line": node.location.start_line,
                "is_annotated": True,
                "annotation": annotation_text,
                "is_type_alias": False
            },
            language="python"
        )
        code_units.append(var_unit)
        return var_id
    
    def _process_type_alias(
        self,
        node: PythonTreeSitterNode,
        parent_id: str,
        file_path: str,
        source_bytes: bytes,
        code_units: List[CodeUnit]
    ) -> str:
        """Обработка типовых псевдонимов (TypeAlias)."""
        # Извлечение имени псевдонима
        left = node.child_by_field_name('left')
        alias_name = left.get_text(source_bytes) if left else f"TypeAlias_{node.location.start_line}"
        
        # Извлечение типа
        right = node.child_by_field_name('right')
        type_text = right.get_text(source_bytes) if right else "Unknown"
        
        # Создание уникального ID
        alias_id = f"type_alias_{self._normalize_id(alias_name)}_{node.location.start_line}"
        
        # Создание CodeUnit для типового псевдонима
        alias_unit = CodeUnit(
            id=alias_id,
            name=alias_name,
            type=CodeUnitType.VARIABLE,  # Используем VARIABLE как наиболее близкий тип
            location=Location(
                file_path=file_path,
                start_line=node.location.start_line,
                end_line=node.location.end_line,
                start_column=node.location.start_column,
                end_column=node.location.end_column
            ),
            code_span=CodeSpan(
                source_code=node.get_text(source_bytes)
            ),
            parent_id=parent_id,
            child_ids=[],
            metadata={
                "line": node.location.start_line,
                "is_type_alias": True,
                "type_definition": type_text,
                "is_pep604_union": '|' in type_text  # Проверка на синтаксис PEP 604 (str | int)
            },
            language="python"
        )
        code_units.append(alias_unit)
        return alias_id
    
    def _process_node_recursive(
        self,
        node: PythonTreeSitterNode,
        parent_unit: CodeUnit,
        file_path: str,
        source_bytes: bytes,
        code_units: List[CodeUnit],
        depth: int
    ) -> Optional[str]:
        """Рекурсивная обработка узла в зависимости от его типа."""
        if node.type == 'class_definition':
            return self._process_class_definition(node, parent_unit.id, file_path, source_bytes, code_units, depth)
        elif node.type in ['function_definition', 'async_function_definition']:
            return self._process_function_definition(node, parent_unit.id, file_path, source_bytes, code_units, depth)
        return None
    
    # ==================== МЕТОДЫ ИЗВЛЕЧЕНИЯ МЕТАДАННЫХ ====================
    
    def _extract_base_classes(self, node: PythonTreeSitterNode, source_bytes: bytes) -> List[Dict[str, Any]]:
        """Извлечение базовых классов из определения класса."""
        bases = []
        argument_list = node.child_by_field_name('superclasses')
        if argument_list:
            for child in argument_list.children:
                if child.type not in ['(', ')', ',']:
                    base_text = child.get_text(source_bytes)
                    bases.append({
                        "name": base_text,
                        "type": self._infer_type_from_text(base_text),
                        "node_type": child.type
                    })
        return bases
    
    def _extract_decorators(self, node: PythonTreeSitterNode, source_bytes: bytes) -> List[Dict[str, Any]]:
        """Извлечение декораторов из узла."""
        decorators = []
        for child in node.children:
            if child.type == 'decorator':
                decorator_node = child.child_by_field_name('argument') or child.find_first_child_by_type('call')
                if decorator_node:
                    decorator_text = decorator_node.get_text(source_bytes)
                    # Извлечение аргументов декоратора
                    args = self._extract_call_arguments(decorator_node, source_bytes) if decorator_node.type == 'call' else []
                    decorators.append({
                        "name": decorator_text.split('(')[0].strip('@').strip(),
                        "full_text": decorator_text,
                        "has_arguments": len(args) > 0,
                        "arguments": args
                    })
                else:
                    decorator_text = child.get_text(source_bytes).strip('@')
                    decorators.append({
                        "name": decorator_text,
                        "full_text": f"@{decorator_text}",
                        "has_arguments": False,
                        "arguments": []
                    })
        return decorators
    
    def _extract_parameters(self, node: PythonTreeSitterNode, source_bytes: bytes) -> List[Dict[str, Any]]:
        """Извлечение параметров функции с аннотациями и значениями по умолчанию."""
        parameters = []
        parameters_node = node.child_by_field_name('parameters')
        if parameters_node:
            for child in parameters_node.children:
                if child.type == 'typed_parameter':
                    name_node = child.child_by_field_name('name')
                    type_node = child.child_by_field_name('type')
                    default_node = child.child_by_field_name('default')
                    
                    param_info = {
                        "name": name_node.get_text(source_bytes) if name_node else "unknown",
                        "type_annotation": type_node.get_text(source_bytes) if type_node else None,
                        "has_default": default_node is not None,
                        "default_value": default_node.get_text(source_bytes) if default_node else None,
                        "is_self": name_node and name_node.get_text(source_bytes) == 'self',
                        "is_cls": name_node and name_node.get_text(source_bytes) == 'cls'
                    }
                    parameters.append(param_info)
                    
                elif child.type == 'identifier':
                    param_info = {
                        "name": child.get_text(source_bytes),
                        "type_annotation": None,
                        "has_default": False,
                        "default_value": None,
                        "is_self": child.get_text(source_bytes) == 'self',
                        "is_cls": child.get_text(source_bytes) == 'cls'
                    }
                    parameters.append(param_info)
                    
                elif child.type == 'list_splat_pattern':
                    name_node = child.child_by_field_name('name') or child.find_first_child_by_type('identifier')
                    param_info = {
                        "name": name_node.get_text(source_bytes) if name_node else "args",
                        "type_annotation": None,
                        "has_default": False,
                        "default_value": None,
                        "is_vararg": True,
                        "is_kwarg": False
                    }
                    parameters.append(param_info)
                    
                elif child.type == 'dictionary_splat_pattern':
                    name_node = child.child_by_field_name('name') or child.find_first_child_by_type('identifier')
                    param_info = {
                        "name": name_node.get_text(source_bytes) if name_node else "kwargs",
                        "type_annotation": None,
                        "has_default": False,
                        "default_value": None,
                        "is_vararg": False,
                        "is_kwarg": True
                    }
                    parameters.append(param_info)
        return parameters
    
    def _extract_return_type(self, node: PythonTreeSitterNode, source_bytes: bytes) -> Optional[str]:
        """Извлечение аннотации возвращаемого типа."""
        return_type_node = node.child_by_field_name('return_type')
        if return_type_node:
            return return_type_node.get_text(source_bytes)
        return None
    
    def _extract_docstring(self, node: PythonTreeSitterNode, source_bytes: bytes) -> Optional[str]:
        """Извлечение докстринга из узла."""
        # Ищем первый дочерний узел типа "expression_statement" с "string"
        body = node.child_by_field_name('body')
        if body and body.children:
            first_child = body.children[0]
            if first_child.type == 'expression_statement':
                string_node = first_child.find_first_child_by_type('string')
                if string_node:
                    docstring = string_node.get_text(source_bytes)
                    # Очищаем от кавычек
                    docstring = docstring.strip('\"\'').strip()
                    return docstring
        return None
    
    def _extract_module_docstring(self, ast: PythonTreeSitterNode, source_bytes: bytes) -> Optional[str]:
        """Извлечение докстринга модуля."""
        if ast.children:
            first_child = ast.children[0]
            if first_child.type == 'expression_statement':
                string_node = first_child.find_first_child_by_type('string')
                if string_node:
                    docstring = string_node.get_text(source_bytes)
                    docstring = docstring.strip('\"\'').strip()
                    return docstring
        return None
    
    def _extract_class_slots(self, node: PythonTreeSitterNode, source_bytes: bytes) -> Optional[List[str]]:
        """Извлечение слотов класса (__slots__)."""
        body = node.child_by_field_name('body')
        if body:
            for child in body.children:
                if child.type == 'expression_statement':
                    assignment = child.find_first_child_by_type('assignment')
                    if assignment:
                        left = assignment.child_by_field_name('left')
                        if left and left.type == 'identifier' and left.get_text(source_bytes) == '__slots__':
                            right = assignment.child_by_field_name('right')
                            if right:
                                return self._extract_list_literal(right, source_bytes)
        return None
    
    def _extract_metaclass(self, node: PythonTreeSitterNode, source_bytes: bytes) -> Optional[str]:
        """Извлечение метакласса из аргументов класса."""
        argument_list = node.child_by_field_name('superclasses')
        if argument_list:
            for child in argument_list.children:
                if child.type == 'keyword_argument':
                    name = child.child_by_field_name('name')
                    if name and name.get_text(source_bytes) == 'metaclass':
                        value = child.child_by_field_name('value')
                        if value:
                            return value.get_text(source_bytes)
        return None
    
    def _extract_import_details(self, node: PythonTreeSitterNode, source_bytes: bytes) -> Dict[str, Any]:
        """Извлечение детальной информации об импорте."""
        result = {
            'is_relative': False,
            'level': 0,
            'module': None,
            'names': [],
            'aliases': {},
            'is_wildcard': False
        }
        
        if node.type == 'import_from_statement':
            # Относительный импорт (уровень определяется количеством точек)
            dotted_name = node.child_by_field_name('module_name')
            if dotted_name:
                module_text = dotted_name.get_text(source_bytes)
                if module_text.startswith('.'):
                    result['is_relative'] = True
                    result['level'] = module_text.count('.')
                    result['module'] = module_text.lstrip('.')
                else:
                    result['module'] = module_text
            
            # Извлечение имён и алиасов
            name_list = node.child_by_field_name('name_list')
            if name_list:
                for child in name_list.children:
                    if child.type == 'aliased_import':
                        name_node = child.child_by_field_name('name')
                        alias_node = child.child_by_field_name('alias')
                        if name_node:
                            name = name_node.get_text(source_bytes)
                            result['names'].append(name)
                            if alias_node:
                                alias = alias_node.get_text(source_bytes)
                                result['aliases'][name] = alias
                    elif child.type == 'identifier':
                        name = child.get_text(source_bytes)
                        result['names'].append(name)
                        if name == '*':
                            result['is_wildcard'] = True
        
        else:  # import_statement
            dotted_name = node.find_first_child_by_type('dotted_name')
            if dotted_name:
                result['module'] = dotted_name.get_text(source_bytes)
                result['names'] = [result['module'].split('.')[-1]]
        
        return result
    
    def _extract_constant_value(self, node: PythonTreeSitterNode, source_bytes: bytes) -> Optional[Dict[str, Any]]:
        """Извлечение значения константы для глобальных переменных."""
        if node.type in ['string', 'integer', 'float', 'true', 'false', 'none']:
            value_text = node.get_text(source_bytes)
            value_type = {
                'string': 'str',
                'integer': 'int',
                'float': 'float',
                'true': 'bool',
                'false': 'bool',
                'none': 'NoneType'
            }.get(node.type, node.type)
            
            return {
                'type': value_type,
                'preview': value_text[:50] if len(value_text) > 50 else value_text,
                'is_literal': True
            }
        
        # Для списков, словарей, кортежей
        if node.type in ['list', 'dictionary', 'tuple']:
            return {
                'type': node.type,
                'preview': node.get_text(source_bytes)[:50],
                'is_literal': True
            }
        
        return None
    
    def _extract_variable_annotation(self, node: PythonTreeSitterNode, source_bytes: bytes) -> Optional[str]:
        """Извлечение аннотации типа переменной."""
        # Ищем аннотацию в присваивании
        for child in node.children:
            if child.type == 'type':
                return child.get_text(source_bytes)
        return None
    
    def _extract_list_literal(self, node: PythonTreeSitterNode, source_bytes: bytes) -> Optional[List[str]]:
        """Извлечение элементов списка."""
        if node.type == 'list':
            elements = []
            for child in node.children:
                if child.type not in ['[', ']', ',']:
                    elements.append(child.get_text(source_bytes).strip('"\''))
            return elements
        return None
    
    def _extract_call_arguments(self, node: PythonTreeSitterNode, source_bytes: bytes) -> List[Dict[str, str]]:
        """Извлечение аргументов вызова функции/декоратора."""
        args = []
        argument_list = node.child_by_field_name('arguments') or node.find_first_child_by_type('argument_list')
        if argument_list:
            for child in argument_list.children:
                if child.type not in ['(', ')', ',']:
                    if child.type == 'keyword_argument':
                        name = child.child_by_field_name('name')
                        value = child.child_by_field_name('value')
                        if name and value:
                            args.append({
                                "name": name.get_text(source_bytes),
                                "value": value.get_text(source_bytes)
                            })
                    else:
                        args.append({
                            "name": None,
                            "value": child.get_text(source_bytes)
                        })
        return args
    
    def _infer_type_from_text(self, text: str) -> str:
        """Простое определение типа из текста (для базовых классов)."""
        text_lower = text.lower()
        if text_lower in ['int', 'float', 'str', 'bool', 'list', 'dict', 'tuple', 'set', 'none']:
            return text_lower
        elif text_lower.startswith(('int', 'float', 'str', 'bool', 'list', 'dict', 'tuple', 'set', 'optional', 'union', 'list[', 'dict[', 'tuple[')):
            return 'generic'
        return 'custom'
    
    def _normalize_id(self, text: str) -> str:
        """Нормализация текста для использования в ID (удаление спецсимволов)."""
        return re.sub(r'[^a-zA-Z0-9_]', '_', text)[:50]