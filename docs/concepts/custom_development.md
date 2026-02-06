# Разработка концептов под свои задачи

В этом разделе описаны рекомендации и практики по адаптации и расширению концептуальных компонентов Koru AI Agent Framework для удовлетворения специфических требований и задач. Вы узнаете, как модифицировать существующие концепции и создавать новые для расширения функциональности системы.

## Основные концепции

### 1. Паттерны мышления (Thinking Patterns)

Паттерны мышления определяют стратегии решения задач. Для адаптации под свои задачи:

#### Создание специфических паттернов

```python
# domain/patterns/specialized_patterns.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState

class ISpecializedPattern(IThinkingPattern):
    """Интерфейс специфического паттерна мышления"""
    
    @abstractmethod
    def can_handle_task_type(self, task_type: str) -> bool:
        """Проверить, может ли паттерн обработать задачу указанного типа"""
        pass
    
    @abstractmethod
    def get_required_capabilities(self) -> List[str]:
        """Получить список требуемых возможностей для выполнения паттерна"""
        pass

class SecurityAnalysisPattern(ISpecializedPattern):
    """Паттерн анализа безопасности"""
    
    @property
    def name(self) -> str:
        return "security_analysis_pattern"
    
    def can_handle_task_type(self, task_type: str) -> bool:
        """Проверить, может ли паттерн обработать задачу анализа безопасности"""
        return task_type in ["security_analysis", "vulnerability_scan", "security_review"]
    
    def get_required_capabilities(self) -> List[str]:
        """Получить возможности, необходимые для анализа безопасности"""
        return [
            "code_reading", "ast_parsing", "security_scanning", 
            "pattern_matching", "report_generation"
        ]
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить анализ безопасности"""
        # Проверить, доступны ли необходимые возможности
        required_capabilities = self.get_required_capabilities()
        missing_capabilities = [cap for cap in required_capabilities if cap not in available_capabilities]
        
        if missing_capabilities:
            return {
                "success": False,
                "error": f"Отсутствуют необходимые возможности: {missing_capabilities}",
                "missing_capabilities": missing_capabilities
            }
        
        # Выполнить анализ безопасности
        code = context.get("code", "")
        language = context.get("language", "python")
        target_vulnerabilities = context.get("target_vulnerabilities", [])
        
        analysis_result = await self._perform_security_analysis(
            code, language, target_vulnerabilities
        )
        
        return {
            "success": True,
            "findings": analysis_result["findings"],
            "summary": analysis_result["summary"],
            "recommendations": analysis_result["recommendations"]
        }
    
    async def _perform_security_analysis(
        self, 
        code: str, 
        language: str, 
        target_vulnerabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить анализ безопасности кода"""
        findings = []
        
        # Выполнить проверки безопасности в зависимости от языка
        if language.lower() == "python":
            findings.extend(await self._check_python_security_issues(code))
        elif language.lower() == "javascript":
            findings.extend(await self._check_javascript_security_issues(code))
        
        # Фильтровать по целевым уязвимостям, если указаны
        if target_vulnerabilities:
            findings = [
                finding for finding in findings 
                if finding["type"].lower() in [tv.lower() for tv in target_vulnerabilities]
            ]
        
        # Сформировать сводку
        summary = {
            "total_findings": len(findings),
            "high_severity": len([f for f in findings if f["severity"] == "HIGH"]),
            "medium_severity": len([f for f in findings if f["severity"] == "MEDIUM"]),
            "low_severity": len([f for f in findings if f["severity"] == "LOW"])
        }
        
        # Сформировать рекомендации
        recommendations = self._generate_recommendations(findings)
        
        return {
            "findings": findings,
            "summary": summary,
            "recommendations": recommendations
        }
    
    async def _check_python_security_issues(self, code: str) -> List[Dict[str, Any]]:
        """Проверить Python-код на уязвимости безопасности"""
        findings = []
        
        # Проверить на SQL-инъекции
        import re
        sql_injection_patterns = [
            r"(?i)(select|insert|update|delete).*[\+\-\*/].*\{.*\}",
            r"(?i)(cursor\.execute|execute).*\+.*\+",
            r"(?i)(query|sql).*(\+|\$).*"
        ]
        
        for pattern in sql_injection_patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                findings.append({
                    "type": "SQL_INJECTION",
                    "severity": "HIGH",
                    "line_number": code[:match.start()].count('\n') + 1,
                    "description": "Потенциальная уязвимость SQL-инъекции",
                    "code_snippet": match.group(0)[:100]
                })
        
        # Проверить на XSS
        xss_patterns = [
            r"(?i)(html|body|script).*(\+|\$).*",
            r"(?i)response\.write.*\+.*\+"
        ]
        
        for pattern in xss_patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                findings.append({
                    "type": "XSS",
                    "severity": "MEDIUM",
                    "line_number": code[:match.start()].count('\n') + 1,
                    "description": "Потенциальная уязвимость XSS",
                    "code_snippet": match.group(0)[:100]
                })
        
        return findings
    
    def _generate_recommendations(self, findings: List[Dict[str, Any]]) -> List[str]:
        """Сгенерировать рекомендации на основе найденных уязвимостей"""
        recommendations = []
        
        if any(f["type"] == "SQL_INJECTION" for f in findings):
            recommendations.append("Используйте параметризованные запросы для предотвращения SQL-инъекций")
        
        if any(f["type"] == "XSS" for f in findings):
            recommendations.append("Экранируйте пользовательский ввод при выводе в HTML")
        
        return recommendations
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче анализа безопасности"""
        # Определить тип задачи и целевые уязвимости
        task_type = self._determine_task_type(task_description)
        target_vulnerabilities = self._extract_target_vulnerabilities(task_description)
        
        return {
            "task_type": task_type,
            "target_vulnerabilities": target_vulnerabilities,
            "required_capabilities": self.get_required_capabilities()
        }
    
    def _determine_task_type(self, task_description: str) -> str:
        """Определить тип задачи анализа безопасности"""
        desc_lower = task_description.lower()
        
        if "vulnerability" in desc_lower or "уязвим" in desc_lower:
            return "vulnerability_scan"
        elif "review" in desc_lower or "ревью" in desc_lower:
            return "security_review"
        else:
            return "security_analysis"
    
    def _extract_target_vulnerabilities(self, task_description: str) -> List[str]:
        """Извлечь целевые типы уязвимостей из описания задачи"""
        desc_lower = task_description.lower()
        vulnerabilities = []
        
        if "sql" in desc_lower and ("injection" in desc_lower or "инъек" in desc_lower):
            vulnerabilities.append("sql_injection")
        if "cross" in desc_lower and "script" in desc_lower:
            vulnerabilities.append("xss")
        if "command" in desc_lower and "injection" in desc_lower:
            vulnerabilities.append("command_injection")
        if "auth" in desc_lower or "аутентиф" in desc_lower:
            vulnerabilities.append("authentication_issues")
        
        return vulnerabilities
```

### 2. Атомарные действия (Atomic Actions)

Атомарные действия - минимальные неделимые операции. Для создания специфических действий:

```python
# domain/actions/specialized_actions.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from domain.abstractions.atomic_action import IAtomicAction
from pathlib import Path
import os

class ISpecializedAction(IAtomicAction):
    """Интерфейс специфического атомарного действия"""
    
    @abstractmethod
    def get_resource_requirements(self) -> Dict[str, Any]:
        """Получить требования к ресурсам для выполнения действия"""
        pass
    
    @abstractmethod
    def get_security_implications(self) -> List[str]:
        """Получить возможные последствия безопасности"""
        pass

class SecureFileReaderAction(ISpecializedAction):
    """Безопасное чтение файлов с дополнительными проверками"""
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024):  # 10MB
        self.max_file_size = max_file_size
        self.allowed_extensions = {".py", ".js", ".ts", ".java", ".cs", ".cpp", ".c", ".txt", ".md", ".yaml", ".json"}
    
    @property
    def name(self) -> str:
        return "secure_file_reader"
    
    def get_resource_requirements(self) -> Dict[str, Any]:
        """Получить требования к ресурсам"""
        return {
            "memory": "50MB",
            "disk_space": str(self.max_file_size),
            "permissions": ["read_file"]
        }
    
    def get_security_implications(self) -> List[str]:
        """Получить последствия безопасности"""
        return [
            "Reading files from filesystem",
            "Potential information disclosure",
            "File path traversal risk"
        ]
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить безопасное чтение файла"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        file_path = parameters["path"]
        encoding = parameters.get("encoding", "utf-8")
        
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
            
            # Проверить расширение файла
            if path.suffix.lower() not in self.allowed_extensions:
                return {
                    "success": False,
                    "error": f"Неподдерживаемое расширение файла: {path.suffix}"
                }
            
            # Проверить размер файла
            file_size = path.stat().st_size
            if file_size > self.max_file_size:
                return {
                    "success": False,
                    "error": f"Файл слишком большой: {file_size} байт, максимум {self.max_file_size}"
                }
            
            # Прочитать файл
            with open(path, 'r', encoding=encoding) as file:
                content = file.read()
            
            return {
                "success": True,
                "content": content,
                "size": file_size,
                "encoding": encoding,
                "extension": path.suffix.lower()
            }
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": f"Не удалось декодировать файл с кодировкой {encoding}"
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"Нет доступа к файлу: {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при чтении файла: {str(e)}"
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        if "path" not in parameters:
            return False
        
        path = parameters["path"]
        if not isinstance(path, str) or not path.strip():
            return False
        
        encoding = parameters.get("encoding", "utf-8")
        if not isinstance(encoding, str):
            return False
        
        return True
    
    def _is_safe_path(self, path: str) -> bool:
        """Проверить, является ли путь безопасным для чтения"""
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

class CodeComplexityAnalyzerAction(ISpecializedAction):
    """Действие для анализа сложности кода"""
    
    def __init__(self):
        self.supported_languages = ["python", "javascript", "java", "csharp"]
    
    @property
    def name(self) -> str:
        return "code_complexity_analyzer"
    
    def get_resource_requirements(self) -> Dict[str, Any]:
        """Получить требования к ресурсам"""
        return {
            "memory": "100MB",
            "cpu": "medium",
            "processing_time": "variable"
        }
    
    def get_security_implications(self) -> List[str]:
        """Получить последствия безопасности"""
        return [
            "Code analysis may reveal implementation details",
            "Processing untrusted code may pose risks"
        ]
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ сложности кода"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        code = parameters["code"]
        language = parameters.get("language", "python").lower()
        
        if language not in self.supported_languages:
            return {
                "success": False,
                "error": f"Язык {language} не поддерживается. Поддерживаемые: {self.supported_languages}"
            }
        
        try:
            # Выполнить анализ сложности
            complexity_metrics = await self._analyze_complexity(code, language)
            
            return {
                "success": True,
                "complexity_metrics": complexity_metrics,
                "language": language
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при анализе сложности кода: {str(e)}"
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        if "code" not in parameters:
            return False
        
        code = parameters["code"]
        if not isinstance(code, str) or not code.strip():
            return False
        
        language = parameters.get("language", "python")
        if not isinstance(language, str):
            return False
        
        return True
    
    async def _analyze_complexity(self, code: str, language: str) -> Dict[str, Any]:
        """Анализ сложности кода"""
        if language == "python":
            return await self._analyze_python_complexity(code)
        elif language == "javascript":
            return await self._analyze_javascript_complexity(code)
        # Добавить другие языки по мере необходимости
        else:
            return {"cyclomatic_complexity": 0, "lines_of_code": len(code.splitlines())}
    
    async def _analyze_python_complexity(self, code: str) -> Dict[str, Any]:
        """Анализ сложности Python-кода"""
        import ast
        
        try:
            tree = ast.parse(code)
            
            # Подсчитать количество узлов
            node_count = len(list(ast.walk(tree)))
            
            # Подсчитать количество функций и классов
            function_count = len([node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)])
            class_count = len([node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)])
            
            # Подсчитать количество строк
            lines_of_code = len(code.splitlines())
            
            # Оценить цикломатическую сложность
            complexity_score = self._estimate_cyclomatic_complexity(tree)
            
            return {
                "node_count": node_count,
                "function_count": function_count,
                "class_count": class_count,
                "lines_of_code": lines_of_code,
                "estimated_complexity": complexity_score,
                "language": "python"
            }
        except SyntaxError:
            return {
                "error": "Невозможно проанализировать синтаксис Python-кода",
                "lines_of_code": len(code.splitlines())
            }
    
    def _estimate_cyclomatic_complexity(self, tree: ast.AST) -> int:
        """Оценить цикломатическую сложность"""
        complexity = 1  # Начинаем с 1
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.With, ast.Try)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):  # and, or
                complexity += len(node.values) - 1
        
        return complexity
```

## Управление доменами

### 1. Создание специфических доменов

Для адаптации системы управления доменами под специфические задачи:

```python
# domain/managers/specialized_domain_manager.py
from typing import Dict, Any, List
from domain.abstractions.domain_manager import IDomainManager
from domain.value_objects.domain_type import DomainType

class ISpecializedDomainManager(IDomainManager):
    """Интерфейс специфического менеджера доменов"""
    
    @abstractmethod
    async def register_specialized_domain(
        self, 
        domain_type: DomainType, 
        config: Dict[str, Any], 
        security_policy: Dict[str, Any]
    ):
        """Зарегистрировать домен с дополнительной политикой безопасности"""
        pass
    
    @abstractmethod
    def get_domain_security_policy(self, domain_type: DomainType) -> Dict[str, Any]:
        """Получить политику безопасности домена"""
        pass

class SpecializedDomainManager(IDomainManager):
    """Специфический менеджер доменов с расширенными возможностями"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._domain_security_policies = {}
        self._domain_resource_limits = {}
        self._domain_compliance_rules = {}
        self._domain_audit_log = []
    
    async def register_specialized_domain(
        self, 
        domain_type: DomainType, 
        config: Dict[str, Any], 
        security_policy: Dict[str, Any]
    ):
        """Зарегистрировать домен с дополнительной политикой безопасности"""
        # Выполнить базовую регистрацию
        await self.register_domain(domain_type, config)
        
        # Сохранить политику безопасности
        self._domain_security_policies[domain_type] = security_policy
        
        # Применить ограничения ресурсов из политики
        if "resource_limits" in security_policy:
            self._domain_resource_limits[domain_type] = security_policy["resource_limits"]
        
        # Применить правила соответствия
        if "compliance_rules" in security_policy:
            self._domain_compliance_rules[domain_type] = security_policy["compliance_rules"]
        
        print(f"Специфический домен {domain_type} зарегистрирован с политикой безопасности")
    
    def get_domain_security_policy(self, domain_type: DomainType) -> Dict[str, Any]:
        """Получить политику безопасности домена"""
        return self._domain_security_policies.get(domain_type, {})
    
    def get_domain_resource_limits(self, domain_type: DomainType) -> Dict[str, Any]:
        """Получить ограничения ресурсов домена"""
        return self._domain_resource_limits.get(domain_type, {})
    
    def get_domain_compliance_rules(self, domain_type: DomainType) -> List[Dict[str, Any]]:
        """Получить правила соответствия домена"""
        return self._domain_compliance_rules.get(domain_type, [])
    
    async def adapt_agent_to_domain(
        self, 
        agent_id: str, 
        domain_type: DomainType, 
        capabilities: List[str]
    ):
        """Адаптировать агента к домену с дополнительными проверками безопасности"""
        if domain_type not in self.domains:
            raise ValueError(f"Домен {domain_type} не зарегистрирован")
        
        # Проверить политику безопасности домена
        security_policy = self.get_domain_security_policy(domain_type)
        if security_policy:
            if not await self._validate_agent_security_compliance(agent_id, domain_type, security_policy):
                raise ValueError(f"Агент {agent_id} не соответствует требованиям безопасности домена {domain_type}")
        
        # Проверить ограничения ресурсов
        resource_limits = self.get_domain_resource_limits(domain_type)
        if resource_limits:
            if not self._validate_agent_resource_compliance(agent_id, domain_type, resource_limits):
                raise ValueError(f"Агент {agent_id} превышает ограничения ресурсов домена {domain_type}")
        
        # Выполнить базовую адаптацию
        await super().adapt_agent_to_domain(agent_id, domain_type, capabilities)
        
        # Залогировать адаптацию
        await self._log_domain_adaptation(agent_id, domain_type, capabilities)
    
    async def _validate_agent_security_compliance(
        self, 
        agent_id: str, 
        domain_type: DomainType, 
        security_policy: Dict[str, Any]
    ) -> bool:
        """Проверить соответствие агента требованиям безопасности домена"""
        # Проверить, есть ли у агента требуемые разрешения
        required_permissions = security_policy.get("required_permissions", [])
        agent_permissions = await self._get_agent_permissions(agent_id)
        
        for permission in required_permissions:
            if permission not in agent_permissions:
                return False
        
        # Проверить уровень изоляции агента
        isolation_level = security_policy.get("isolation_level", "none")
        agent_isolation = await self._get_agent_isolation_level(agent_id)
        
        if self._compare_isolation_levels(agent_isolation, isolation_level) < 0:
            return False
        
        return True
    
    def _validate_agent_resource_compliance(
        self, 
        agent_id: str, 
        domain_type: DomainType, 
        resource_limits: Dict[str, Any]
    ) -> bool:
        """Проверить соответствие агента ограничениям ресурсов домена"""
        # В реальной реализации здесь будет проверка использования ресурсов агентом
        # против ограничений домена
        return True
    
    def _compare_isolation_levels(self, agent_level: str, required_level: str) -> int:
        """Сравнить уровни изоляции (-1: меньше, 0: равно, 1: больше)"""
        levels = {"none": 0, "basic": 1, "standard": 2, "strict": 3, "maximum": 4}
        
        agent_val = levels.get(agent_level, 0)
        required_val = levels.get(required_level, 0)
        
        if agent_val < required_val:
            return -1
        elif agent_val > required_val:
            return 1
        else:
            return 0
    
    async def _log_domain_adaptation(
        self, 
        agent_id: str, 
        domain_type: DomainType, 
        capabilities: List[str]
    ):
        """Залогировать адаптацию агента к домену"""
        log_entry = {
            "timestamp": time.time(),
            "agent_id": agent_id,
            "domain_type": domain_type.value,
            "capabilities": capabilities,
            "event_type": "domain_adaptation"
        }
        
        self._domain_audit_log.append(log_entry)
        
        # Ограничить размер лога
        if len(self._domain_audit_log) > 10000:  # Максимум 10,000 записей
            self._domain_audit_log = self._domain_audit_log[-10000:]
    
    def get_domain_audit_log(self, domain_type: DomainType = None, limit: int = None) -> List[Dict[str, Any]]:
        """Получить лог аудита домена"""
        if domain_type:
            domain_logs = [
                entry for entry in self._domain_audit_log 
                if entry["domain_type"] == domain_type.value
            ]
        else:
            domain_logs = self._domain_audit_log
        
        return domain_logs[-limit:] if limit else domain_logs
    
    async def _get_agent_permissions(self, agent_id: str) -> List[str]:
        """Получить разрешения агента (в реальной реализации)"""
        # В реальной системе здесь будет получение разрешений агента
        # из системы управления доступом
        return []
    
    async def _get_agent_isolation_level(self, agent_id: str) -> str:
        """Получить уровень изоляции агента (в реальной реализации)"""
        # В реальной системе здесь будет получение уровня изоляции агента
        return "standard"
```

## Интеграция специфических компонентов

### 1. Фабрика специфических компонентов

Для создания и управления специфическими концептуальными компонентами:

```python
# application/factories/specialized_concept_factory.py
from typing import Type, Dict, Any
from domain.patterns.specialized_patterns import ISpecializedPattern
from domain.actions.specialized_actions import ISpecializedAction
from domain.managers.specialized_domain_manager import ISpecializedDomainManager

class SpecializedConceptFactory:
    """Фабрика для создания специфических концептуальных компонентов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._registered_pattern_types = {}
        self._registered_action_types = {}
        self._registered_domain_types = {}
        
        # Зарегистрировать встроенные типы
        self._register_builtin_types()
    
    def _register_builtin_types(self):
        """Зарегистрировать встроенные типы концептуальных компонентов"""
        self.register_pattern_type("security_analysis", SecurityAnalysisPattern)
        self.register_action_type("secure_file_reader", SecureFileReaderAction)
        self.register_action_type("code_complexity_analyzer", CodeComplexityAnalyzerAction)
    
    def register_pattern_type(self, name: str, pattern_class: Type[ISpecializedPattern]):
        """Зарегистрировать тип паттерна мышления"""
        self._registered_pattern_types[name] = pattern_class
    
    def register_action_type(self, name: str, action_class: Type[ISpecializedAction]):
        """Зарегистрировать тип атомарного действия"""
        self._registered_action_types[name] = action_class
    
    def register_domain_type(self, name: str, domain_class: Type[ISpecializedDomainManager]):
        """Зарегистрировать тип менеджера доменов"""
        self._registered_domain_types[name] = domain_class
    
    async def create_specialized_pattern(self, pattern_type: str, **kwargs) -> ISpecializedPattern:
        """Создать специфический паттерн мышления"""
        if pattern_type not in self._registered_pattern_types:
            raise ValueError(f"Тип паттерна '{pattern_type}' не зарегистрирован")
        
        pattern_class = self._registered_pattern_types[pattern_type]
        config = {**self.config.get("pattern_defaults", {}), **kwargs}
        
        pattern = pattern_class(**config)
        return pattern
    
    async def create_specialized_action(self, action_type: str, **kwargs) -> ISpecializedAction:
        """Создать специфическое атомарное действие"""
        if action_type not in self._registered_action_types:
            raise ValueError(f"Тип действия '{action_type}' не зарегистрирован")
        
        action_class = self._registered_action_types[action_type]
        config = {**self.config.get("action_defaults", {}), **kwargs}
        
        action = action_class(**config)
        return action
    
    async def create_specialized_domain_manager(self, manager_type: str, **kwargs) -> ISpecializedDomainManager:
        """Создать специфический менеджер доменов"""
        if manager_type not in self._registered_domain_types:
            raise ValueError(f"Тип менеджера доменов '{manager_type}' не зарегистрирован")
        
        manager_class = self._registered_domain_types[manager_type]
        config = {**self.config.get("domain_defaults", {}), **kwargs}
        
        manager = manager_class(config)
        return manager
    
    def get_available_pattern_types(self) -> List[str]:
        """Получить доступные типы паттернов"""
        return list(self._registered_pattern_types.keys())
    
    def get_available_action_types(self) -> List[str]:
        """Получить доступные типы действий"""
        return list(self._registered_action_types.keys())
    
    def get_available_domain_types(self) -> List[str]:
        """Получить доступные типы менеджеров доменов"""
        return list(self._registered_domain_types.keys())

class AdvancedConceptFactory(SpecializedConceptFactory):
    """Расширенная фабрика концептуальных компонентов"""
    
    def __init__(self, base_config: Dict[str, Any] = None):
        super().__init__(base_config)
        self._middleware_registry = {}
        self._validator_registry = {}
        self._enricher_registry = {}
    
    async def create_configurable_pattern(
        self,
        pattern_type: str,
        config: Dict[str, Any] = None,
        middleware: List[Callable] = None,
        validators: List[Callable] = None,
        enrichers: List[Callable] = None
    ) -> ISpecializedPattern:
        """Создать настраиваемый паттерн мышления"""
        
        # Создать базовый паттерн
        pattern = await self.create_specialized_pattern(pattern_type, **(config or {}))
        
        # Добавить middleware
        if middleware:
            for mw_func in middleware:
                if hasattr(pattern, 'add_middleware'):
                    pattern.add_middleware(mw_func)
        
        # Добавить валидаторы
        if validators:
            for validator_func in validators:
                if hasattr(pattern, 'add_validator'):
                    pattern.add_validator(validator_func)
        
        # Добавить enrichers
        if enrichers:
            for enricher_func in enrichers:
                if hasattr(pattern, 'add_enricher'):
                    pattern.add_enricher(enricher_func)
        
        return pattern
    
    def register_middleware(self, name: str, middleware_func: Callable):
        """Зарегистрировать middleware"""
        self._middleware_registry[name] = middleware_func
    
    def register_validator(self, name: str, validator_func: Callable):
        """Зарегистрировать валидатор"""
        self._validator_registry[name] = validator_func
    
    def register_enricher(self, name: str, enricher_func: Callable):
        """Зарегистрировать enricher"""
        self._enricher_registry[name] = enricher_func
    
    def get_registered_component(self, component_type: str, name: str):
        """Получить зарегистрированный компонент"""
        registries = {
            "middleware": self._middleware_registry,
            "validator": self._validator_registry,
            "enricher": self._enricher_registry
        }
        
        if component_type in registries:
            return registries[component_type].get(name)
        return None
```

### 2. Пример использования специфических компонентов

```python
# specialized_concepts_usage.py
from application.factories.advanced_concept_factory import AdvancedConceptFactory
from domain.value_objects.domain_type import DomainType

async def specialized_concepts_example():
    """Пример использования специфических концептуальных компонентов"""
    
    # Создать расширенную фабрику
    factory = AdvancedConceptFactory({
        "pattern_defaults": {
            "timeout": 300,
            "retry_count": 3
        },
        "action_defaults": {
            "max_file_size": 5 * 1024 * 1024,  # 5MB
            "allowed_extensions": [".py", ".js", ".ts", ".java", ".cs"]
        },
        "domain_defaults": {
            "enable_security_policies": True,
            "audit_logging_enabled": True
        }
    })
    
    # Зарегистрировать специфические middleware
    def security_enrichment_middleware(context):
        """Middleware для обогащения контекста безопасности"""
        if "security_context" not in context:
            context["security_context"] = {
                "scan_depth": "comprehensive",
                "vulnerability_types": ["sql_injection", "xss", "command_injection"]
            }
        return context
    
    def complexity_validator(context):
        """Валидатор сложности задачи"""
        code = context.get("code", "")
        if len(code) > 10000:  # Если код слишком длинный
            raise ValueError("Код слишком длинный для анализа")
        return True
    
    factory.register_middleware("security_enrichment", security_enrichment_middleware)
    factory.register_validator("complexity_check", complexity_validator)
    
    # Создать специфический паттерн анализа безопасности
    security_pattern = await factory.create_configurable_pattern(
        "security_analysis",
        config={
            "analysis_depth": "deep",
            "enable_compliance_checking": True
        },
        middleware=[factory.get_registered_component("middleware", "security_enrichment")],
        validators=[factory.get_registered_component("validator", "complexity_check")]
    )
    
    # Создать специфическое атомарное действие для безопасного чтения файлов
    secure_file_reader = await factory.create_specialized_action(
        "secure_file_reader",
        max_file_size=10 * 1024 * 1024  # 10MB
    )
    
    # Создать специфический анализатор сложности кода
    complexity_analyzer = await factory.create_specialized_action(
        "code_complexity_analyzer"
    )
    
    # Создать специфический менеджер доменов
    domain_manager = await factory.create_specialized_domain_manager(
        "specialized",
        config={
            "enable_security_policies": True,
            "compliance_checking_enabled": True
        }
    )
    
    # Зарегистрировать домен с политикой безопасности
    await domain_manager.register_specialized_domain(
        DomainType.CODE_ANALYSIS,
        config={
            "capabilities": ["security_analysis", "code_quality", "complexity_analysis"]
        },
        security_policy={
            "required_permissions": ["read_code_files", "analyze_security"],
            "isolation_level": "standard",
            "resource_limits": {
                "memory": "2GB",
                "cpu_percentage": 50.0
            },
            "compliance_rules": [
                "follow_security_standards",
                "maintain_audit_trail"
            ]
        }
    )
    
    # Адаптировать агента к домену
    await domain_manager.adapt_agent_to_domain(
        "agent_123",
        DomainType.CODE_ANALYSIS,
        ["security_analysis", "complexity_analysis"]
    )
    
    # Выполнить анализ с использованием специфических компонентов
    task_context = {
        "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
        "language": "python",
        "analysis_types": ["security", "complexity"]
    }
    
    # Выполнить паттерн анализа
    pattern_result = await security_pattern.execute(
        state=AgentState(),
        context=task_context,
        available_capabilities=["code_reading", "security_scanning", "complexity_analysis"]
    )
    
    print(f"Результат анализа безопасности: {pattern_result}")
    
    # Выполнить анализ сложности кода
    complexity_result = await complexity_analyzer.execute({
        "code": task_context["code"],
        "language": task_context["language"]
    })
    
    print(f"Результат анализа сложности: {complexity_result}")
    
    # Получить лог аудита домена
    audit_log = domain_manager.get_domain_audit_log(DomainType.CODE_ANALYSIS, limit=10)
    print(f"Лог аудита домена: {audit_log}")
    
    return {
        "security_analysis": pattern_result,
        "complexity_analysis": complexity_result,
        "domain_audit_log": audit_log
    }

# Интеграция с агентами
async def agent_concept_integration_example():
    """Пример интеграции специфических концепций с агентами"""
    
    # Создать фабрику агентов
    from application.factories.agent_factory import AgentFactory
    agent_factory = AgentFactory()
    
    # Создать специфические компоненты
    concept_factory = AdvancedConceptFactory()
    
    # Создать специфический паттерн
    specialized_pattern = await concept_factory.create_specialized_pattern(
        "security_analysis",
        config={"depth": "comprehensive"}
    )
    
    # Создать специфические действия
    secure_reader = await concept_factory.create_specialized_action("secure_file_reader")
    complexity_analyzer = await concept_factory.create_specialized_action("code_complexity_analyzer")
    
    # Создать агента
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Зарегистрировать специфические компоненты в агенте
    agent.register_pattern(specialized_pattern)
    agent.register_action(secure_reader)
    agent.register_action(complexity_analyzer)
    
    # Выполнить задачу с использованием специфических компонентов
    result = await agent.execute_task(
        task_description="Проанализируй этот Python код на безопасность и сложность",
        context={
            "code": """
class UserAuth:
    def authenticate(self, username, password):
        # Уязвимость: SQL-инъекция
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        return execute_query(query)
        
    def get_user_data(self, user_id):
        # Еще одна уязвимость
        query = f"SELECT * FROM user_data WHERE id={user_id}"
        return execute_query(query)
""",
            "language": "python"
        }
    )
    
    print(f"Результат выполнения через агента: {result}")
    
    return result
```

## Лучшие практики

### 1. Модульность и расширяемость

Создавайте концептуальные компоненты, которые можно легко расширять:

```python
# Хорошо: модульные и расширяемые компоненты
class BasePattern:
    """Базовый паттерн"""
    pass

class AnalysisPattern(BasePattern):
    """Паттерн анализа"""
    pass

class SecurityAnalysisPattern(AnalysisPattern):
    """Паттерн анализа безопасности"""
    pass

# Плохо: монолитные компоненты
class MonolithicPattern:
    """Монолитный паттерн - сложно расширять и тестировать"""
    pass
```

### 2. Безопасность и валидация

Обязательно учитывайте безопасность при создании концепций:

```python
def _validate_task_context(self, context: Dict[str, Any]) -> List[str]:
    """Проверить контекст задачи на безопасность"""
    errors = []
    
    # Проверить чувствительные поля
    sensitive_fields = ["password", "token", "api_key", "secret"]
    for field in sensitive_fields:
        if field in context:
            errors.append(f"Чувствительное поле '{field}' обнаружено в контексте задачи")
    
    # Проверить размер контекста
    context_size = len(str(context))
    max_size = 1024 * 1024  # 1MB
    if context_size > max_size:
        errors.append(f"Контекст задачи слишком велик: {context_size} байт, максимум {max_size}")
    
    return errors
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок в концептуальных компонентах:

```python
async def execute(self, state: AgentState, context: Any, capabilities: List[str]) -> Dict[str, Any]:
    """Выполнить паттерн с надежной обработкой ошибок"""
    try:
        # Проверить ограничения
        if state.error_count > state.max_error_threshold:
            return {
                "success": False,
                "error": "Превышено максимальное количество ошибок",
                "needs_reset": True
            }
        
        # Проверить контекст
        validation_errors = self._validate_task_context(context)
        if validation_errors:
            return {
                "success": False,
                "error": f"Ошибки валидации контекста: {validation_errors}",
                "validation_errors": validation_errors
            }
        
        # Выполнить основную логику
        result = await self._execute_core_logic(state, context, capabilities)
        
        # Обновить состояние при успехе
        state.register_progress(progressed=True)
        
        return {"success": True, **result}
    except SecurityError as e:
        state.register_error()
        state.register_progress(progressed=False)
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security"
        }
    except ResourceLimitExceededError as e:
        state.register_error()
        return {
            "success": False,
            "error": f"Превышено ограничение ресурсов: {str(e)}",
            "error_type": "resource_limit"
        }
    except Exception as e:
        state.register_error()
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal"
        }
```

### 4. Тестирование концептуальных компонентов

Создавайте тесты для каждого концептуального компонента:

```python
# test_specialized_concepts.py
import pytest
from unittest.mock import AsyncMock, Mock
import tempfile
import os

class TestSecurityAnalysisPattern:
    @pytest.mark.asyncio
    async def test_security_analysis_pattern_execution(self):
        """Тест выполнения паттерна анализа безопасности"""
        # Создать паттерн
        pattern = SecurityAnalysisPattern()
        
        # Подготовить контекст
        context = {
            "code": """
def vulnerable_login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
            "language": "python",
            "target_vulnerabilities": ["sql_injection"]
        }
        
        # Выполнить паттерн
        result = await pattern.execute(
            state=AgentState(),
            context=context,
            available_capabilities=["code_reading", "security_scanning"]
        )
        
        # Проверить результат
        assert result["success"] is True
        assert "findings" in result
        assert len(result["findings"]) > 0
        assert any(finding["type"] == "SQL_INJECTION" for finding in result["findings"])
    
    @pytest.mark.asyncio
    async def test_pattern_adaptation_to_task(self):
        """Тест адаптации паттерна к задаче"""
        pattern = SecurityAnalysisPattern()
        
        # Адаптировать к задаче
        adaptation_result = await pattern.adapt_to_task(
            "Выполни глубокий анализ безопасности этого Python-кода"
        )
        
        # Проверить результат адаптации
        assert adaptation_result["task_type"] == "security_analysis"
        assert "sql_injection" in adaptation_result["target_vulnerabilities"]
        assert "security_scanning" in adaptation_result["required_capabilities"]

class TestSecureFileReaderAction:
    @pytest.mark.asyncio
    async def test_secure_file_reading(self):
        """Тест безопасного чтения файла"""
        # Создать действие
        action = SecureFileReaderAction(max_file_size=1024*1024)  # 1MB
        
        # Создать временный файл для теста
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("print('Hello, World!')")
            temp_file_path = f.name
        
        try:
            # Выполнить действие
            result = await action.execute({"path": temp_file_path})
            
            # Проверить результат
            assert result["success"] is True
            assert "Hello, World!" in result["content"]
            assert result["size"] > 0
        finally:
            # Удалить временный файл
            os.unlink(temp_file_path)
    
    @pytest.mark.asyncio
    async def test_unsafe_path_rejection(self):
        """Тест отклонения небезопасного пути"""
        action = SecureFileReaderAction()
        
        # Попробовать прочитать файл с небезопасным путем (выход за пределы проекта)
        result = await action.execute({"path": "../../../etc/passwd"})
        
        # Проверить, что действие было отклонено
        assert result["success"] is False
        assert "небезопасный путь" in result["error"].lower()

class TestSpecializedDomainManager:
    @pytest.mark.asyncio
    async def test_specialized_domain_registration(self):
        """Тест регистрации специфического домена"""
        # Создать менеджер
        manager = SpecializedDomainManager()
        
        # Зарегистрировать домен с политикой безопасности
        security_policy = {
            "required_permissions": ["read_code", "analyze_security"],
            "isolation_level": "standard",
            "resource_limits": {"memory": "2GB"}
        }
        
        await manager.register_specialized_domain(
            DomainType.CODE_ANALYSIS,
            {"capabilities": ["security_analysis"]},
            security_policy
        )
        
        # Проверить, что домен зарегистрирован
        assert DomainType.CODE_ANALYSIS in manager.domains
        
        # Проверить политику безопасности
        retrieved_policy = manager.get_domain_security_policy(DomainType.CODE_ANALYSIS)
        assert retrieved_policy == security_policy
```

Эти примеры показывают, как адаптировать и расширять концептуальные компоненты Koru AI Agent Framework под специфические задачи, обеспечивая модульность, безопасность и надежность системы.