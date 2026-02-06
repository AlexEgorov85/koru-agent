# Разработка инструментов и навыков под свои задачи

В этом разделе описаны рекомендации и практики по созданию и адаптации инструментов и навыков Koru AI Agent Framework под специфические задачи и требования. Вы узнаете, как создавать новые инструменты и навыки, а также модифицировать существующие для расширения функциональности системы.

## Архитектура инструментов и навыков

### 1. Интерфейсы и абстракции

Система инструментов и навыков построена на принципах открытости/закрытости и подстановки Лисков:

```python
# domain/abstractions/tool.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pydantic import BaseModel

class ToolMetadata(BaseModel):
    """Метаданные инструмента"""
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    return_schema: Dict[str, Any]
    category: str
    version: str = "1.0.0"
    permissions: List[str] = []

class ITool(ABC):
    """Интерфейс инструмента"""
    
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Метаданные инструмента"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить инструмент с указанными параметрами"""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить корректность параметров"""
        pass

class BaseTool(ITool, ABC):
    """Базовый класс для инструментов"""
    
    def __init__(self):
        self._is_initialized = False
        self._required_permissions = []
    
    async def initialize(self):
        """Инициализировать инструмент"""
        self._is_initialized = True
    
    async def cleanup(self):
        """Очистить ресурсы инструмента"""
        self._is_initialized = False

# domain/abstractions/skill.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class SkillMetadata(BaseModel):
    """Метаданные навыка"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    category: str
    version: str = "1.0.0"
    required_tools: List[str] = []

class ISkill(ABC):
    """Интерфейс навыка"""
    
    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """Метаданные навыка"""
        pass
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить навык с указанным контекстом"""
        pass
    
    @abstractmethod
    def validate_context(self, context: Dict[str, Any]) -> bool:
        """Проверить корректность контекста"""
        pass

class BaseSkill(ISkill, ABC):
    """Базовый класс для навыков"""
    
    def __init__(self):
        self._is_initialized = False
        self._required_tools = []
        self._execution_history = []
    
    async def initialize(self):
        """Инициализировать навык"""
        self._is_initialized = True
    
    async def cleanup(self):
        """Очистить ресурсы навыка"""
        self._is_initialized = False
        self._execution_history.clear()
```

### 2. Создание специфических инструментов

Для создания инструментов под специфические задачи:

```python
# infrastructure/tools/specialized_tools.py
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List
from domain.abstractions.tool import BaseTool, ToolMetadata
from application.services.security_validator import SecurityValidator

class SpecializedFileAnalyzerTool(BaseTool):
    """Специфический инструмент для анализа файлов"""
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024, supported_formats: List[str] = None):
        super().__init__()
        self.max_file_size = max_file_size
        self.supported_formats = supported_formats or [
            '.txt', '.py', '.js', '.ts', '.java', '.cs', '.cpp', '.c', 
            '.html', '.css', '.json', '.yaml', '.xml'
        ]
        self.security_validator = SecurityValidator()
        self._required_permissions = ["read_file", "analyze_content"]
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="specialized_file_analyzer",
            description="Анализирует файлы на наличие уязвимостей и проблем качества",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу для анализа"
                    },
                    "analysis_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["security", "quality", "complexity", "style"]
                        },
                        "default": ["security", "quality"],
                        "description": "Типы анализа для выполнения"
                    },
                    "include_details": {
                        "type": "boolean",
                        "default": False,
                        "description": "Включать подробные детали анализа"
                    }
                },
                "required": ["file_path"]
            },
            return_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "analysis_results": {
                        "type": "object",
                        "properties": {
                            "security_findings": {"type": "array"},
                            "quality_issues": {"type": "array"},
                            "complexity_metrics": {"type": "object"},
                            "style_violations": {"type": "array"}
                        }
                    },
                    "file_info": {
                        "type": "object",
                        "properties": {
                            "size": {"type": "integer"},
                            "extension": {"type": "string"},
                            "line_count": {"type": "integer"}
                        }
                    },
                    "error": {"type": "string"}
                }
            },
            category="analysis",
            permissions=["read_file", "analyze_content"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ файла"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        file_path = parameters["file_path"]
        analysis_types = parameters.get("analysis_types", ["security", "quality"])
        include_details = parameters.get("include_details", False)
        
        try:
            # Проверить безопасность пути
            if not self._is_safe_path(file_path):
                return {
                    "success": False,
                    "error": "Небезопасный путь к файлу"
                }
            
            path = Path(file_path)
            
            # Проверить существование файла
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Файл не найден: {file_path}"
                }
            
            # Проверить формат файла
            if path.suffix.lower() not in self.supported_formats:
                return {
                    "success": False,
                    "error": f"Неподдерживаемый формат файла: {path.suffix}"
                }
            
            # Проверить размер файла
            file_size = path.stat().st_size
            if file_size > self.max_file_size:
                return {
                    "success": False,
                    "error": f"Файл слишком большой: {file_size} байт, максимум {self.max_file_size}"
                }
            
            # Прочитать содержимое файла
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Выполнить анализ
            analysis_results = await self._perform_analysis(
                content, 
                path.suffix.lower(), 
                analysis_types, 
                include_details
            )
            
            return {
                "success": True,
                "analysis_results": analysis_results,
                "file_info": {
                    "size": file_size,
                    "extension": path.suffix.lower(),
                    "line_count": len(content.splitlines())
                }
            }
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": f"Не удалось декодировать файл с кодировкой utf-8: {file_path}"
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"Нет доступа к файлу: {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при анализе файла: {str(e)}"
            }
    
    async def _perform_analysis(
        self, 
        content: str, 
        file_extension: str, 
        analysis_types: List[str], 
        include_details: bool
    ) -> Dict[str, Any]:
        """Выполнить анализ содержимого файла"""
        results = {
            "security_findings": [],
            "quality_issues": [],
            "complexity_metrics": {},
            "style_violations": []
        }
        
        for analysis_type in analysis_types:
            if analysis_type == "security":
                results["security_findings"] = await self._analyze_security(content, file_extension)
            elif analysis_type == "quality":
                results["quality_issues"] = await self._analyze_quality(content, file_extension)
            elif analysis_type == "complexity":
                results["complexity_metrics"] = await self._analyze_complexity(content, file_extension)
            elif analysis_type == "style":
                results["style_violations"] = await self._analyze_style(content, file_extension)
        
        return results
    
    async def _analyze_security(self, content: str, extension: str) -> List[Dict[str, Any]]:
        """Анализ безопасности содержимого"""
        findings = []
        
        # Примеры проверок безопасности
        if extension in ['.py', '.js', '.php']:
            # Проверка на потенциальные SQL-инъекции
            import re
            sql_injection_patterns = [
                r"(?i)(select|insert|update|delete).*[\+\-\*/].*\{.*\}",
                r"(?i)(cursor\.execute|execute).*\+.*\+",
                r"(?i)(query|sql).*(\+|\$).*"
            ]
            
            for pattern in sql_injection_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    findings.append({
                        "type": "SQL_INJECTION_POSSIBLE",
                        "severity": "HIGH",
                        "line_number": content[:match.start()].count('\n') + 1,
                        "code_snippet": match.group(0)[:100],
                        "description": "Обнаружен потенциальный паттерн SQL-инъекции"
                    })
        
        return findings
    
    async def _analyze_quality(self, content: str, extension: str) -> List[Dict[str, Any]]:
        """Анализ качества кода"""
        issues = []
        
        # Примеры проверок качества
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            if len(line) > 120:  # Слишком длинная строка
                issues.append({
                    "type": "LONG_LINE",
                    "severity": "MEDIUM",
                    "line_number": i,
                    "description": f"Слишком длинная строка ({len(line)} символов, максимум 120)",
                    "code_snippet": line[:100]
                })
        
        return issues
    
    async def _analyze_complexity(self, content: str, extension: str) -> Dict[str, Any]:
        """Анализ сложности кода"""
        # Реализация анализа сложности (например, cyclomatic complexity)
        lines_of_code = len([line for line in content.splitlines() if line.strip()])
        comment_lines = len([line for line in content.splitlines() if line.strip().startswith('#') or line.strip().startswith('//')])
        
        return {
            "lines_of_code": lines_of_code,
            "comment_lines": comment_lines,
            "comment_ratio": comment_lines / lines_of_code if lines_of_code > 0 else 0
        }
    
    async def _analyze_style(self, content: str, extension: str) -> List[Dict[str, Any]]:
        """Анализ стиля кода"""
        violations = []
        
        # Примеры проверок стиля
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            if line.endswith(' '):  # Пробелы в конце строки
                violations.append({
                    "type": "TRAILING_WHITESPACE",
                    "severity": "LOW",
                    "line_number": i,
                    "description": "Пробелы в конце строки",
                    "code_snippet": repr(line)
                })
        
        return violations
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        if "file_path" not in parameters:
            return False
        
        file_path = parameters["file_path"]
        if not isinstance(file_path, str) or not file_path.strip():
            return False
        
        # Проверить типы анализа, если указаны
        if "analysis_types" in parameters:
            analysis_types = parameters["analysis_types"]
            if not isinstance(analysis_types, list):
                return False
            
            valid_types = {"security", "quality", "complexity", "style"}
            if not all(atype in valid_types for atype in analysis_types):
                return False
        
        return True
    
    def _is_safe_path(self, path: str) -> bool:
        """Проверить, является ли путь безопасным для чтения"""
        try:
            # Преобразовать в абсолютный путь
            abs_path = Path(path).resolve()
            
            # Получить корневой каталог (где запущен фреймворк)
            root_path = Path.cwd().resolve()
            
            # Проверить, что путь находится внутри корневого каталога
            abs_path.relative_to(root_path)
            return True
        except ValueError:
            # Если путь вне корневого каталога, он небезопасен
            return False
```

### 3. Создание специфических навыков

Навыки комбинируют несколько инструментов для решения сложных задач:

```python
# application/skills/specialized_skills.py
from typing import Any, Dict, List
from domain.abstractions.skill import BaseSkill, SkillMetadata
from domain.abstractions.tool import ITool

class MultiFileSecurityAnalysisSkill(BaseSkill):
    """Навык комплексного анализа безопасности нескольких файлов"""
    
    def __init__(
        self, 
        file_analyzer_tool: ITool, 
        dependency_checker_tool: ITool, 
        configuration_analyzer_tool: ITool
    ):
        super().__init__()
        self.file_analyzer = file_analyzer_tool
        self.dependency_checker = dependency_checker_tool
        self.configuration_analyzer = configuration_analyzer_tool
        self._required_tools = [
            file_analyzer_tool, 
            dependency_checker_tool, 
            configuration_analyzer_tool
        ]
    
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="multi_file_security_analysis",
            description="Комплексный анализ безопасности нескольких файлов проекта",
            input_schema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Путь к проекту для анализа"
                    },
                    "file_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["**/*.py", "**/*.js", "**/*.ts"],
                        "description": "Паттерны файлов для анализа"
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["**/node_modules/**", "**/__pycache__/**", "**/.git/**"],
                        "description": "Паттерны файлов для исключения"
                    },
                    "analysis_depth": {
                        "type": "string",
                        "enum": ["shallow", "medium", "deep"],
                        "default": "medium",
                        "description": "Глубина анализа"
                    }
                },
                "required": ["project_path"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "summary": {
                        "type": "object",
                        "properties": {
                            "total_files_analyzed": {"type": "integer"},
                            "total_findings": {"type": "integer"},
                            "high_severity_findings": {"type": "integer"},
                            "medium_severity_findings": {"type": "integer"},
                            "low_severity_findings": {"type": "integer"}
                        }
                    },
                    "detailed_results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file_path": {"type": "string"},
                                "findings": {"type": "array"}
                            }
                        }
                    },
                    "recommendations": {"type": "array", "items": {"type": "string"}},
                    "error": {"type": "string"}
                }
            },
            category="security_analysis",
            required_tools=["file_analyzer", "dependency_checker", "config_analyzer"]
        )
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить комплексный анализ безопасности"""
        if not self.validate_context(context):
            return {
                "success": False,
                "error": "Некорректный контекст выполнения"
            }
        
        project_path = context["project_path"]
        file_patterns = context.get("file_patterns", ["**/*.py", "**/*.js", "**/*.ts"])
        exclude_patterns = context.get("exclude_patterns", ["**/node_modules/**", "**/__pycache__/**"])
        analysis_depth = context.get("analysis_depth", "medium")
        
        try:
            # Найти файлы для анализа
            files_to_analyze = await self._find_files(project_path, file_patterns, exclude_patterns)
            
            if not files_to_analyze:
                return {
                    "success": False,
                    "error": f"Не найдено файлов для анализа по паттернам {file_patterns}"
                }
            
            # Выполнить анализ каждого файла
            all_results = []
            total_findings = 0
            high_severity = 0
            medium_severity = 0
            low_severity = 0
            
            for file_path in files_to_analyze:
                # Выполнить анализ файла
                analysis_result = await self.file_analyzer.execute({
                    "file_path": str(file_path),
                    "analysis_types": self._get_analysis_types_for_depth(analysis_depth),
                    "include_details": True
                })
                
                if analysis_result["success"]:
                    file_results = {
                        "file_path": str(file_path),
                        "findings": analysis_result["analysis_results"]["security_findings"]
                    }
                    
                    # Подсчитать уязвимости
                    for finding in file_results["findings"]:
                        total_findings += 1
                        severity = finding.get("severity", "MEDIUM").upper()
                        if severity == "HIGH" or severity == "CRITICAL":
                            high_severity += 1
                        elif severity == "MEDIUM":
                            medium_severity += 1
                        else:
                            low_severity += 1
                    
                    all_results.append(file_results)
            
            # Выполнить анализ зависимостей
            dependency_analysis = await self.dependency_checker.execute({
                "project_path": project_path
            })
            
            # Выполнить анализ конфигураций
            config_analysis = await self.configuration_analyzer.execute({
                "project_path": project_path
            })
            
            # Сформировать рекомендации
            recommendations = await self._generate_recommendations(
                all_results, 
                dependency_analysis, 
                config_analysis
            )
            
            return {
                "success": True,
                "summary": {
                    "total_files_analyzed": len(files_to_analyze),
                    "total_findings": total_findings,
                    "high_severity_findings": high_severity,
                    "medium_severity_findings": medium_severity,
                    "low_severity_findings": low_severity
                },
                "detailed_results": all_results,
                "dependency_analysis": dependency_analysis,
                "configuration_analysis": config_analysis,
                "recommendations": recommendations
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении комплексного анализа: {str(e)}"
            }
    
    async def _find_files(self, project_path: str, patterns: List[str], exclude_patterns: List[str]) -> List[Path]:
        """Найти файлы в проекте по паттернам"""
        import fnmatch
        from pathlib import Path
        
        project_root = Path(project_path)
        files = []
        
        for pattern in patterns:
            for file_path in project_root.rglob(pattern):
                # Проверить, не исключается ли файл
                should_exclude = False
                for exclude_pattern in exclude_patterns:
                    if fnmatch.fnmatch(str(file_path), exclude_pattern):
                        should_exclude = True
                        break
                
                if not should_exclude:
                    files.append(file_path)
        
        return files
    
    def _get_analysis_types_for_depth(self, depth: str) -> List[str]:
        """Получить типы анализа в зависимости от глубины"""
        if depth == "shallow":
            return ["security"]
        elif depth == "medium":
            return ["security", "quality"]
        else:  # deep
            return ["security", "quality", "complexity", "style"]
    
    async def _generate_recommendations(
        self, 
        file_results: List[Dict[str, Any]], 
        dependency_results: Dict[str, Any], 
        config_results: Dict[str, Any]
    ) -> List[str]:
        """Сформировать рекомендации на основе результатов анализа"""
        recommendations = []
        
        # Анализ результатов файлов
        total_findings = sum(len(result["findings"]) for result in file_results)
        high_severity_findings = sum(
            1 for result in file_results 
            for finding in result["findings"] 
            if finding.get("severity", "").upper() in ["HIGH", "CRITICAL"]
        )
        
        if high_severity_findings > 10:
            recommendations.append("Критическое количество уязвимостей высокого уровня, требуется срочное устранение")
        elif high_severity_findings > 5:
            recommendations.append("Значительное количество уязвимостей высокого уровня, рекомендуется срочное устранение")
        
        # Анализ зависимостей
        if dependency_results.get("success") and dependency_results.get("outdated_packages"):
            outdated_count = len(dependency_results["outdated_packages"])
            if outdated_count > 10:
                recommendations.append(f"Обнаружено {outdated_count} устаревших пакетов, рекомендуется обновление")
        
        # Анализ конфигураций
        if config_results.get("success") and config_results.get("security_issues"):
            config_issues = config_results["security_issues"]
            if any(issue.get("severity") == "HIGH" for issue in config_issues):
                recommendations.append("Обнаружены критические проблемы в конфигурационных файлах")
        
        return recommendations
    
    def validate_context(self, context: Dict[str, Any]) -> bool:
        """Проверить контекст выполнения"""
        if "project_path" not in context:
            return False
        
        project_path = context["project_path"]
        if not isinstance(project_path, str) or not project_path.strip():
            return False
        
        # Проверить типы анализа, если указаны
        if "analysis_types" in context:
            analysis_types = context["analysis_types"]
            if not isinstance(analysis_types, list):
                return False
            
            valid_types = {"security", "quality", "complexity", "style"}
            if not all(atype in valid_types for atype in analysis_types):
                return False
        
        return True
    
    def _extract_file_paths(self, task_description: str) -> List[str]:
        """Извлечь пути к файлам из описания задачи"""
        import re
        
        # Паттерны для поиска путей к файлам
        patterns = [
            r'файл\s+([^\s]+)',  # файл path/to/file.py
            r'([^\s]+\.(?:py|js|ts|java|cs|cpp|c|html|css|json|yaml|xml))',  # файлы с расширениями
            r'"([^"]+\.(?:py|js|ts|java|cs|cpp|c|html|css|json|yaml|xml))"',  # в кавычках
            r"'([^']+\.(?:py|js|ts|java|cs|cpp|c|html|css|json|yaml|xml))'"   # в апострофах
        ]
        
        file_paths = []
        for pattern in patterns:
            matches = re.findall(pattern, task_description, re.IGNORECASE)
            file_paths.extend(matches)
        
        return list(set(file_paths))  # Удалить дубликаты
    
    async def _perform_deep_analysis(self, content: str, file_path: str, analysis_types: List[str]) -> Dict[str, Any]:
        """Выполнить глубокий анализ содержимого файла"""
        results = {}
        
        for analysis_type in analysis_types:
            if analysis_type == "security":
                results["security"] = await self._deep_security_analysis(content, file_path)
            elif analysis_type == "quality":
                results["quality"] = await self._deep_quality_analysis(content, file_path)
            elif analysis_type == "complexity":
                results["complexity"] = await self._deep_complexity_analysis(content, file_path)
            elif analysis_type == "style":
                results["style"] = await self._deep_style_analysis(content, file_path)
        
        return results
    
    async def _deep_security_analysis(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Выполнить глубокий анализ безопасности"""
        findings = []
        
        # Более подробный анализ безопасности
        import ast
        import re
        
        try:
            # Анализ AST для поиска уязвимостей
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Проверка вызовов потенциально опасных функций
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        if func_name in ['eval', 'exec', 'compile']:
                            findings.append({
                                "type": "DANGEROUS_FUNCTION_CALL",
                                "severity": "CRITICAL",
                                "line_number": node.lineno,
                                "function": func_name,
                                "description": f"Обнаружен вызов потенциально опасной функции: {func_name}"
                            })
                        elif func_name in ['open', 'subprocess.run', 'os.system']:
                            findings.append({
                                "type": "SECURITY_SENSITIVE_CALL",
                                "severity": "HIGH",
                                "line_number": node.lineno,
                                "function": func_name,
                                "description": f"Обнаружен вызов функции с потенциальными рисками безопасности: {func_name}"
                            })
        
        except SyntaxError:
            # Если не удается распарсить AST, выполнить текстовый анализ
            pass
        
        # Текстовый анализ для других языков
        if file_path.endswith('.js'):
            # Проверка на XSS в JavaScript
            xss_patterns = [
                r'document\.write\([^)]*\+[^)]*\)',
                r'innerHTML\s*=\s*',
                r'eval\([^)]*\)'
            ]
            
            for pattern in xss_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    findings.append({
                        "type": "XSS_VULNERABILITY",
                        "severity": "HIGH",
                        "line_number": content[:match.start()].count('\n') + 1,
                        "pattern": pattern,
                        "description": "Обнаружена потенциальная уязвимость XSS"
                    })
        
        return findings
```

## Интеграция с системой

### 1. Регистрация специфических компонентов

Для интеграции специфических инструментов и навыков:

```python
# application/factories/specialized_component_factory.py
from typing import Type, Dict, Any
from domain.abstractions.tool import ITool
from domain.abstractions.skill import ISkill
from infrastructure.tools.specialized_tools import SpecializedFileAnalyzerTool
from application.skills.specialized_skills import MultiFileSecurityAnalysisSkill

class SpecializedComponentFactory:
    """Фабрика для создания специфических компонентов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._registered_tools = {}
        self._registered_skills = {}
        
        # Зарегистрировать встроенные специфические компоненты
        self._register_builtin_components()
    
    def _register_builtin_components(self):
        """Зарегистрировать встроенные специфические компоненты"""
        self.register_tool_class("specialized_file_analyzer", SpecializedFileAnalyzerTool)
        self.register_skill_class("multi_file_security_analysis", MultiFileSecurityAnalysisSkill)
    
    def register_tool_class(self, name: str, tool_class: Type[ITool]):
        """Зарегистрировать класс инструмента"""
        self._registered_tools[name] = tool_class
    
    def register_skill_class(self, name: str, skill_class: Type[ISkill]):
        """Зарегистрировать класс навыка"""
        self._registered_skills[name] = skill_class
    
    async def create_tool(self, name: str, **kwargs) -> ITool:
        """Создать экземпляр инструмента"""
        if name not in self._registered_tools:
            raise ValueError(f"Инструмент {name} не зарегистрирован")
        
        tool_class = self._registered_tools[name]
        config = {**self.config.get("tool_defaults", {}), **kwargs}
        
        tool_instance = tool_class(**config)
        await tool_instance.initialize()
        
        return tool_instance
    
    async def create_skill(self, name: str, **kwargs) -> ISkill:
        """Создать экземпляр навыка"""
        if name not in self._registered_skills:
            raise ValueError(f"Навык {name} не зарегистрирован")
        
        skill_class = self._registered_skills[name]
        config = {**self.config.get("skill_defaults", {}), **kwargs}
        
        # Если навык требует инструменты, создать их
        skill_instance = skill_class(**config)
        await skill_instance.initialize()
        
        return skill_instance
    
    def get_available_tools(self) -> List[str]:
        """Получить список доступных инструментов"""
        return list(self._registered_tools.keys())
    
    def get_available_skills(self) -> List[str]:
        """Получить список доступных навыков"""
        return list(self._registered_skills.keys())

class AdvancedComponentFactory(ComponentFactory):
    """Расширенная фабрика компонентов с поддержкой специфических компонентов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.specialized_factory = SpecializedComponentFactory(config)
        
        # Объединить зарегистрированные компоненты
        self._tool_classes.update(self.specialized_factory._registered_tools)
        self._skill_classes.update(self.specialized_factory._registered_skills)
    
    async def create_component(self, component_type: str, name: str, **kwargs) -> Any:
        """Создать компонент по типу и имени"""
        if component_type == "tool":
            return await self.create_tool(name, **kwargs)
        elif component_type == "skill":
            return await self.create_skill(name, **kwargs)
        else:
            raise ValueError(f"Неподдерживаемый тип компонента: {component_type}")
    
    def register_custom_component_type(self, component_type: str, registry: Dict[str, type]):
        """Зарегистрировать пользовательский тип компонента"""
        if component_type == "specialized_tool":
            self._tool_classes.update(registry)
        elif component_type == "specialized_skill":
            self._skill_classes.update(registry)
        else:
            self._custom_registries[component_type] = registry
```

### 2. Использование специфических компонентов

Пример использования специфических инструментов и навыков:

```python
# specialized_usage_example.py
from application.factories.advanced_component_factory import AdvancedComponentFactory
from domain.value_objects.domain_type import DomainType

async def specialized_components_example():
    """Пример использования специфических компонентов"""
    
    # Создать расширенную фабрику
    factory = AdvancedComponentFactory({
        "tool_defaults": {
            "max_file_size": 5 * 1024 * 1024,  # 5MB
            "timeout": 300
        },
        "skill_defaults": {
            "max_execution_time": 600,
            "enable_monitoring": True
        }
    })
    
    # Создать специфический инструмент
    file_analyzer = await factory.create_tool(
        "specialized_file_analyzer",
        max_file_size=10 * 1024 * 1024,  # 10MB
        supported_formats=['.py', '.js', '.ts', '.java', '.cs']
    )
    
    # Создать специфический навык
    security_skill = await factory.create_skill(
        "multi_file_security_analysis",
        file_analyzer_tool=file_analyzer,
        dependency_checker_tool=await factory.create_tool("dependency_checker"),
        configuration_analyzer_tool=await factory.create_tool("config_analyzer")
    )
    
    # Выполнить анализ файла с помощью инструмента
    analysis_result = await file_analyzer.execute({
        "file_path": "./src/main.py",
        "analysis_types": ["security", "quality"],
        "include_details": True
    })
    
    print(f"Результат анализа файла: {analysis_result}")
    
    # Выполнить комплексный анализ с помощью навыка
    project_analysis_result = await security_skill.execute({
        "project_path": "./my_project",
        "file_patterns": ["**/*.py", "**/*.js"],
        "exclude_patterns": ["**/tests/**", "**/node_modules/**"],
        "analysis_depth": "deep"
    })
    
    print(f"Результат комплексного анализа проекта: {project_analysis_result}")
    
    return analysis_result, project_analysis_result

# Интеграция с агентами
async def agent_with_specialized_components_example():
    """Пример интеграции специфических компонентов с агентами"""
    
    # Создать фабрику агентов
    from application.factories.agent_factory import AgentFactory
    agent_factory = AgentFactory()
    
    # Создать агента
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Зарегистрировать специфические компоненты в агенте
    factory = AdvancedComponentFactory()
    
    # Создать инструменты
    specialized_analyzer = await factory.create_tool("specialized_file_analyzer")
    dependency_checker = await factory.create_tool("dependency_checker")
    
    # Зарегистрировать инструменты в агенте
    agent.register_tool(specialized_analyzer)
    agent.register_tool(dependency_checker)
    
    # Создать и зарегистрировать навык
    security_skill = await factory.create_skill(
        "multi_file_security_analysis",
        file_analyzer_tool=specialized_analyzer,
        dependency_checker_tool=dependency_checker,
        configuration_analyzer_tool=await factory.create_tool("config_analyzer")
    )
    
    agent.register_skill(security_skill)
    
    # Выполнить задачу с использованием специфических компонентов
    task_result = await agent.execute_task(
        task_description="Выполни комплексный анализ безопасности проекта в директории ./my_project",
        context={
            "project_path": "./my_project",
            "analysis_types": ["security", "dependencies", "configurations"]
        }
    )
    
    print(f"Результат выполнения задачи с использованием специфических компонентов: {task_result}")
    
    return task_result
```

## Лучшие практики

### 1. Безопасность и валидация

Обязательно реализуйте проверки безопасности:

```python
def _is_safe_path(self, path: str) -> bool:
    """Проверить, является ли путь безопасным для использования"""
    try:
        # Преобразовать в абсолютный путь
        abs_path = Path(path).resolve()
        
        # Получить корневой каталог проекта
        project_root = Path.cwd().resolve()
        
        # Проверить, что путь находится внутри корневого каталога
        abs_path.relative_to(project_root)
        return True
    except ValueError:
        # Если путь вне корневого каталога, он небезопасен
        return False

def _validate_file_access(self, file_path: str) -> bool:
    """Проверить, разрешен ли доступ к файлу"""
    path = Path(file_path)
    
    # Проверить, что файл существует
    if not path.exists():
        return False
    
    # Проверить права доступа
    if not os.access(path, os.R_OK):
        return False
    
    # Проверить тип файла (не является ли он символической ссылкой вне разрешенных директорий)
    if path.is_symlink():
        link_target = path.resolve()
        project_root = Path.cwd().resolve()
        try:
            link_target.relative_to(project_root)
        except ValueError:
            return False  # Символическая ссылка ведет вне проекта
    
    return True
```

### 2. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Выполнить инструмент с надежной обработкой ошибок"""
    try:
        # Валидация параметров
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        # Проверка безопасности
        if not self._check_security_constraints(parameters):
            return {
                "success": False,
                "error": "Нарушение ограничений безопасности"
            }
        
        # Проверка ресурсов
        if not await self._check_resource_availability():
            return {
                "success": False,
                "error": "Недостаточно ресурсов для выполнения"
            }
        
        # Выполнение основной логики
        result = await self._execute_main_logic(parameters)
        
        return {"success": True, **result}
    except SecurityError as e:
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security"
        }
    except ResourceLimitExceededError as e:
        return {
            "success": False,
            "error": f"Превышено ограничение ресурсов: {str(e)}",
            "error_type": "resource_limit"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal"
        }

def _check_security_constraints(self, parameters: Dict[str, Any]) -> bool:
    """Проверить ограничения безопасности"""
    # Проверить путь к файлу на безопасность
    if "file_path" in parameters:
        if not self._is_safe_path(parameters["file_path"]):
            return False
    
    # Проверить другие потенциально опасные параметры
    # ...
    
    return True

async def _check_resource_availability(self) -> bool:
    """Проверить доступность ресурсов"""
    # В реальной реализации здесь будет проверка
    # доступной памяти, CPU, сетевых ресурсов и т.д.
    import psutil
    
    # Проверить использование памяти
    memory_percent = psutil.virtual_memory().percent
    if memory_percent > 85:  # Порог 85%
        return False
    
    # Проверить использование CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent > 90:  # Порог 90%
        return False
    
    return True
```

### 3. Тестирование специфических компонентов

Создавайте тесты для каждого специфического компонента:

```python
# test_specialized_components.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
import tempfile
import os

class TestSpecializedFileAnalyzerTool:
    @pytest.mark.asyncio
    async def test_file_analysis_success(self):
        """Тест успешного анализа файла"""
        # Создать инструмент
        tool = SpecializedFileAnalyzerTool(
            max_file_size=1024*1024,  # 1MB
            supported_formats=['.py', '.txt']
        )
        
        # Создать временный файл для теста
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
def vulnerable_function(user_input):
    query = f"SELECT * FROM users WHERE id = {user_input}"
    return execute_query(query)
""")
            temp_file_path = f.name
        
        try:
            # Выполнить анализ
            result = await tool.execute({
                "file_path": temp_file_path,
                "analysis_types": ["security", "quality"],
                "include_details": True
            })
            
            # Проверить результат
            assert result["success"] is True
            assert "analysis_results" in result
            assert "security_findings" in result["analysis_results"]
            assert "file_info" in result
            
            # Проверить, что найдены уязвимости (в данном случае SQL-инъекция)
            security_findings = result["analysis_results"]["security_findings"]
            assert len(security_findings) > 0
            
        finally:
            # Удалить временный файл
            os.unlink(temp_file_path)
    
    @pytest.mark.asyncio
    async def test_file_analysis_invalid_params(self):
        """Тест анализа с некорректными параметрами"""
        tool = SpecializedFileAnalyzerTool()
        
        result = await tool.execute({"invalid_param": "value"})
        
        assert result["success"] is False
        assert "Некорректные параметры" in result["error"]
    
    @pytest.mark.asyncio
    async def test_file_analysis_unsafe_path(self):
        """Тест анализа файла с небезопасным путем"""
        tool = SpecializedFileAnalyzerTool()
        
        result = await tool.execute({
            "file_path": "../../../etc/passwd"  # Попытка выхода из корня
        })
        
        assert result["success"] is False
        assert "Небезопасный путь" in result["error"]

class TestMultiFileSecurityAnalysisSkill:
    @pytest.mark.asyncio
    async def test_multi_file_analysis_success(self):
        """Тест успешного комплексного анализа нескольких файлов"""
        
        # Создать моки инструментов
        mock_file_analyzer = AsyncMock()
        mock_file_analyzer.execute.return_value = {
            "success": True,
            "analysis_results": {
                "security_findings": [
                    {
                        "type": "SQL_INJECTION_POSSIBLE",
                        "severity": "HIGH",
                        "line_number": 3,
                        "description": "Potential SQL injection"
                    }
                ]
            }
        }
        
        mock_dependency_checker = AsyncMock()
        mock_dependency_checker.execute.return_value = {
            "success": True,
            "outdated_packages": []
        }
        
        mock_config_analyzer = AsyncMock()
        mock_config_analyzer.execute.return_value = {
            "success": True,
            "security_issues": []
        }
        
        # Создать навык
        skill = MultiFileSecurityAnalysisSkill(
            file_analyzer_tool=mock_file_analyzer,
            dependency_checker_tool=mock_dependency_checker,
            configuration_analyzer_tool=mock_config_analyzer
        )
        
        # Создать временную директорию с файлами для теста
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создать тестовые файлы
            test_file1 = os.path.join(temp_dir, "test1.py")
            with open(test_file1, 'w') as f:
                f.write("def test(): pass")
            
            # Выполнить анализ
            result = await skill.execute({
                "project_path": temp_dir,
                "file_patterns": ["*.py"],
                "analysis_depth": "medium"
            })
            
            # Проверить результат
            assert result["success"] is True
            assert "summary" in result
            assert "detailed_results" in result
            assert result["summary"]["total_files_analyzed"] >= 1
    
    def test_context_validation(self):
        """Тест валидации контекста"""
        skill = MultiFileSecurityAnalysisSkill(AsyncMock(), AsyncMock(), AsyncMock())
        
        # Тест с некорректным контекстом
        invalid_context = {"invalid_param": "value"}
        assert skill.validate_context(invalid_context) is False
        
        # Тест с корректным контекстом
        valid_context = {"project_path": "/valid/path"}
        assert skill.validate_context(valid_context) is True

class TestAdvancedComponentFactory:
    def test_create_registered_tool(self):
        """Тест создания зарегистрированного инструмента"""
        factory = AdvancedComponentFactory()
        
        # Создать инструмент
        tool = factory.create_tool("specialized_file_analyzer")
        
        # Проверить, что инструмент создан
        assert tool is not None
        assert hasattr(tool, 'execute')
    
    def test_create_registered_skill(self):
        """Тест создания зарегистрированного навыка"""
        factory = AdvancedComponentFactory()
        
        # Создать навык
        skill = factory.create_skill("multi_file_security_analysis")
        
        # Проверить, что навык создан
        assert skill is not None
        assert hasattr(skill, 'execute')
    
    def test_get_available_components(self):
        """Тест получения списка доступных компонентов"""
        factory = AdvancedComponentFactory()
        
        available_tools = factory.get_available_tools()
        available_skills = factory.get_available_skills()
        
        # Проверить, что есть хотя бы один доступный компонент
        assert len(available_tools) > 0
        assert len(available_skills) > 0
        assert "specialized_file_analyzer" in available_tools
        assert "multi_file_security_analysis" in available_skills
```

Эти примеры показывают, как создавать и интегрировать специфические инструменты и навыки в Koru AI Agent Framework, обеспечивая расширяемость, безопасность и надежность системы.