# Разработка агентов под свои задачи

В этом разделе описаны рекомендации и практики по адаптации и расширению агентов Composable AI Agent Framework для удовлетворения специфических требований и задач. Вы узнаете, как модифицировать существующие агенты и создавать новые для расширения функциональности системы.

## Архитектура агентов

### 1. Интерфейсы и абстракции

Система агентов построена на принципах открытости/закрытости и подстановки Лисков:

```python
# domain/abstractions/agent.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class AgentState(BaseModel):
    """
    Явное состояние агента.
    Не содержит логики — только данные.
    """

    step: int = 0
    error_count: int = 0
    no_progress_steps: int = 0
    finished: bool = False
    metrics: Dict[str, Any] = {}
    history: List[str] = []
    current_plan_step: Optional[str] = None

    def register_error(self):
        self.error_count += 1

    def register_progress(self, progressed: bool):
        if progressed:
            self.no_progress_steps = 0
        else:
            self.no_progress_steps += 1

    def complete(self):
        """Отмечает агента как завершившего выполнение."""
        self.finished = True

class IAgent(ABC):
    """Интерфейс агента"""
    
    @property
    @abstractmethod
    def state(self) -> AgentState:
        """Состояние агента"""
        pass
    
    @abstractmethod
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу с указанным описанием и контекстом"""
        pass
    
    @abstractmethod
    async def execute_atomic_action(self, action_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить атомарное действие"""
        pass
    
    @abstractmethod
    async def execute_composable_pattern(self, pattern_name: str, context: Any) -> Dict[str, Any]:
        """Выполнить компонуемый паттерн"""
        pass
    
    @abstractmethod
    async def adapt_to_domain(self, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать агента к домену с указанными возможностями"""
        pass

class BaseAgent(IAgent, ABC):
    """Базовый класс для агентов"""
    
    def __init__(self, initial_state: AgentState = None):
        self.state = initial_state or AgentState()
        self._is_initialized = False
        self._tools = {}
        self._skills = {}
        self._event_publisher = None
        self._action_executor = None
        self._pattern_executor = None
    
    async def initialize(self):
        """Инициализировать агента"""
        self._is_initialized = True
    
    async def cleanup(self):
        """Очистить ресурсы агента"""
        self._is_initialized = False
        self._tools.clear()
        self._skills.clear()
```

### 2. Создание специфических агентов

Для создания агентов под специфические задачи:

```python
# application/agents/specialized_agents.py
from domain.abstractions.agent import BaseAgent, IAgent
from domain.value_objects.domain_type import DomainType
from application.orchestration.atomic_actions import AtomicActionExecutor
from application.orchestration.composable_patterns import ComposablePatternExecutor
from application.services.event_publisher import EventPublisher

class SpecializedCodeAnalysisAgent(BaseAgent):
    """Специфический агент для анализа кода"""
    
    def __init__(
        self,
        initial_state: AgentState = None,
        event_publisher: IEventPublisher = None,
        action_executor: AtomicActionExecutor = None,
        pattern_executor: ComposablePatternExecutor = None
    ):
        super().__init__(initial_state)
        self.event_publisher = event_publisher
        self.action_executor = action_executor
        self.pattern_executor = pattern_executor
        self.domain_type = DomainType.CODE_ANALYSIS
        self._required_tools = [
            "file_reader",
            "ast_parser", 
            "security_scanner",
            "code_quality_analyzer"
        ]
        self._supported_capabilities = [
            "security_analysis",
            "code_review", 
            "vulnerability_detection",
            "best_practices_check"
        ]
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу анализа кода"""
        if not self._is_initialized:
            await self.initialize()
        
        try:
            # Обновить состояние
            self.state.step += 1
            
            # Определить тип задачи
            task_type = self._determine_task_type(task_description)
            
            # Выполнить специфическую логику в зависимости от типа задачи
            if task_type == "security_analysis":
                result = await self._execute_security_analysis(task_description, context)
            elif task_type == "code_review":
                result = await self._execute_code_review(task_description, context)
            elif task_type == "vulnerability_scan":
                result = await self._execute_vulnerability_scan(task_description, context)
            else:
                result = await self._execute_general_analysis(task_description, context)
            
            # Обновить состояние при успехе
            self.state.register_progress(progressed=True)
            
            # Опубликовать событие выполнения задачи
            if self.event_publisher:
                await self.event_publisher.publish("task_completed", {
                    "agent_id": id(self),
                    "task_description": task_description,
                    "result": result,
                    "step": self.state.step
                })
            
            return {"success": True, **result}
        except Exception as e:
            self.state.register_error()
            self.state.register_progress(progressed=False)
            
            # Опубликовать событие ошибки
            if self.event_publisher:
                await self.event_publisher.publish("task_failed", {
                    "agent_id": id(self),
                    "task_description": task_description,
                    "error": str(e),
                    "step": self.state.step
                })
            
            return {
                "success": False,
                "error": f"Ошибка при выполнении задачи: {str(e)}",
                "step": self.state.step
            }
    
    def _determine_task_type(self, task_description: str) -> str:
        """Определить тип задачи по описанию"""
        desc_lower = task_description.lower()
        
        if "безопасность" in desc_lower or "security" in desc_lower or "уязвим" in desc_lower:
            return "security_analysis"
        elif "review" in desc_lower or "ревью" in desc_lower or "качество" in desc_lower:
            return "code_review"
        elif "сканирование" in desc_lower or "scan" in desc_lower or "уязвимости" in desc_lower:
            return "vulnerability_scan"
        else:
            return "general_analysis"
    
    async def _execute_security_analysis(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ безопасности кода"""
        # Извлечь пути к файлам из описания задачи или контекста
        file_paths = self._extract_file_paths(task_description)
        
        if not file_paths and context and "file_path" in context:
            file_paths = [context["file_path"]]
        
        if not file_paths:
            return {
                "success": False,
                "error": "Не указаны файлы для анализа безопасности"
            }
        
        results = []
        all_findings = []
        
        for file_path in file_paths:
            # Выполнить атомарное действие для чтения файла
            read_result = await self.execute_atomic_action("file_reader", {"path": file_path})
            
            if not read_result["success"]:
                results.append({
                    "file": file_path,
                    "success": False,
                    "error": read_result["error"]
                })
                continue
            
            # Выполнить анализ AST
            ast_result = await self.execute_atomic_action("ast_parser", {
                "code": read_result["content"],
                "language": context.get("language", "python")
            })
            
            # Выполнить анализ безопасности
            security_result = await self.execute_atomic_action("security_scanner", {
                "code": read_result["content"],
                "ast": ast_result,
                "analysis_types": ["sql_injection", "xss", "command_injection"]
            })
            
            file_findings = security_result.get("findings", [])
            all_findings.extend(file_findings)
            
            results.append({
                "file": file_path,
                "success": True,
                "findings": file_findings,
                "summary": self._generate_security_summary(file_findings)
            })
        
        return {
            "results": results,
            "total_findings": len(all_findings),
            "findings_by_severity": self._count_findings_by_severity(all_findings),
            "overall_security_score": self._calculate_security_score(all_findings)
        }
    
    async def _execute_code_review(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить ревью кода"""
        # Логика выполнения ревью кода
        pass
    
    async def _execute_vulnerability_scan(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить сканирование уязвимостей"""
        # Логика сканирования уязвимостей
        pass
    
    async def _execute_general_analysis(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить общий анализ"""
        # Логика общего анализа
        pass
    
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
    
    def _generate_security_summary(self, findings: List[Dict[str, Any]]) -> str:
        """Сгенерировать сводку по результатам анализа безопасности"""
        if not findings:
            return "Анализ не выявил уязвимостей безопасности."
        
        high_severity = len([f for f in findings if f.get("severity", "").upper() in ["HIGH", "CRITICAL"]])
        medium_severity = len([f for f in findings if f.get("severity", "").upper() == "MEDIUM"])
        low_severity = len([f for f in findings if f.get("severity", "").upper() == "LOW"])
        
        return f"Найдено уязвимостей: {len(findings)} (Высокий приоритет: {high_severity}, Средний: {medium_severity}, Низкий: {low_severity})"
    
    def _count_findings_by_severity(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Подсчитать уязвимости по уровню серьезности"""
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        for finding in findings:
            severity = finding.get("severity", "MEDIUM").upper()
            if severity in counts:
                counts[severity] += 1
        
        return counts
    
    def _calculate_security_score(self, findings: List[Dict[str, Any]]) -> float:
        """Рассчитать общий балл безопасности (0-100)"""
        if not findings:
            return 100.0  # Отличная безопасность
        
        # Рассчитать на основе серьезности и количества уязвимостей
        weighted_score = 0
        total_weight = 0
        
        severity_weights = {
            "CRITICAL": 10,
            "HIGH": 7,
            "MEDIUM": 4,
            "LOW": 1
        }
        
        for finding in findings:
            severity = finding.get("severity", "MEDIUM").upper()
            weight = severity_weights.get(severity, 4)  # По умолчанию средний вес
            weighted_score += weight
            total_weight += 10  # Максимальный вес для нормализации
        
        if total_weight > 0:
            vulnerability_score = (weighted_score / total_weight) * 100
            # Чем больше уязвимостей, тем ниже балл (обратная зависимость)
            return max(0, 100 - vulnerability_score)
        else:
            return 100.0
```

## Расширение функциональности агентов

### 1. Создание специфических паттернов мышления

Для адаптации агентов под специфические задачи создайте специфические паттерны мышления:

```python
# application/patterns/specialized_patterns.py
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState
from typing import Any, Dict, List

class SecurityAnalysisPattern(IThinkingPattern):
    """Паттерн мышления для анализа безопасности"""
    
    @property
    def name(self) -> str:
        return "security_analysis_pattern"
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить анализ безопасности"""
        if not isinstance(context, dict):
            return {
                "success": False,
                "error": "Контекст должен быть словарем"
            }
        
        code = context.get("code")
        language = context.get("language", "python")
        analysis_types = context.get("analysis_types", ["security"])
        
        if not code:
            return {
                "success": False,
                "error": "Не предоставлен код для анализа"
            }
        
        results = {}
        
        for analysis_type in analysis_types:
            if analysis_type == "security":
                results["security_analysis"] = await self._perform_security_analysis(code, language)
            elif analysis_type == "quality":
                results["quality_analysis"] = await self._perform_quality_analysis(code, language)
            elif analysis_type == "complexity":
                results["complexity_analysis"] = await self._perform_complexity_analysis(code, language)
        
        return {
            "success": True,
            "analysis_results": results,
            "language": language
        }
    
    async def _perform_security_analysis(self, code: str, language: str) -> Dict[str, Any]:
        """Выполнить анализ безопасности кода"""
        findings = []
        
        # Примеры проверок безопасности
        if language.lower() == "python":
            # Проверка на SQL-инъекции
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
                        "type": "SQL_INJECTION_POSSIBLE",
                        "severity": "HIGH",
                        "line_number": code[:match.start()].count('\n') + 1,
                        "code_snippet": match.group(0)[:100],
                        "description": "Обнаружен потенциальный паттерн SQL-инъекции"
                    })
        
        return {
            "findings": findings,
            "total_findings": len(findings),
            "high_severity_findings": len([f for f in findings if f["severity"] == "HIGH"]),
            "medium_severity_findings": len([f for f in findings if f["severity"] == "MEDIUM"]),
            "low_severity_findings": len([f for f in findings if f["severity"] == "LOW"])
        }
    
    async def _perform_quality_analysis(self, code: str, language: str) -> Dict[str, Any]:
        """Выполнить анализ качества кода"""
        issues = []
        
        # Примеры проверок качества
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if len(line) > 120:  # Слишком длинная строка
                issues.append({
                    "type": "LONG_LINE",
                    "severity": "MEDIUM",
                    "line_number": i,
                    "description": f"Слишком длинная строка ({len(line)} символов, максимум 120)",
                    "code_snippet": line[:100]
                })
        
        return {
            "issues": issues,
            "total_issues": len(issues),
            "quality_score": self._calculate_quality_score(lines, issues)
        }
    
    def _calculate_quality_score(self, lines: List[str], issues: List[Dict[str, Any]]) -> float:
        """Рассчитать балл качества кода"""
        # Простая метрика: чем больше проблем, тем ниже балл
        max_issues_per_line = 0.1  # Максимум 10% строк могут иметь проблемы
        max_score = 100.0
        
        lines_count = len(lines)
        issues_count = len(issues)
        
        if lines_count == 0:
            return max_score
        
        issues_ratio = issues_count / lines_count
        
        # Штраф за превышение лимита проблем
        penalty = max(0, (issues_ratio - max_issues_per_line) * 1000)
        
        score = max(0, max_score - (issues_ratio * 50) - penalty)
        return score
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче"""
        return {
            "analysis_types": self._determine_analysis_types(task_description),
            "required_tools": ["file_reader", "ast_parser", "security_scanner"]
        }
    
    def _determine_analysis_types(self, task_description: str) -> List[str]:
        """Определить типы анализа на основе описания задачи"""
        desc_lower = task_description.lower()
        analysis_types = []
        
        if any(keyword in desc_lower for keyword in ["безопасность", "security", "уязвим", "vulnerability"]):
            analysis_types.append("security")
        
        if any(keyword in desc_lower for keyword in ["качество", "quality", "best practice", "рефакторинг"]):
            analysis_types.append("quality")
        
        if any(keyword in desc_lower for keyword in ["сложность", "complexity", "анализ структуры"]):
            analysis_types.append("complexity")
        
        return analysis_types or ["security"]  # По умолчанию анализ безопасности
```

### 2. Интеграция инструментов и навыков

Для расширения функциональности агентов интегрируйте специфические инструменты и навыки:

```python
# application/agents/enhanced_agent.py
from application.agents.specialized_agent import SpecializedAgent
from application.skills.multi_file_analysis_skill import MultiFileAnalysisSkill
from infrastructure.tools.advanced_file_analyzer import AdvancedFileAnalyzerTool
from infrastructure.tools.dependency_scanner import DependencyScannerTool

class EnhancedCodeAnalysisAgent(SpecializedAgent):
    """Улучшенный агент для анализа кода с расширенной функциональностью"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Создать расширенные инструменты
        self.advanced_file_analyzer = AdvancedFileAnalyzerTool()
        self.dependency_scanner = DependencyScannerTool()
        
        # Создать расширенные навыки
        self.multi_file_analysis_skill = MultiFileAnalysisSkill(
            file_analyzer=self.advanced_file_analyzer,
            dependency_scanner=self.dependency_scanner
        )
        
        # Зарегистрировать инструменты
        self.register_tool("advanced_file_analyzer", self.advanced_file_analyzer)
        self.register_tool("dependency_scanner", self.dependency_scanner)
        
        # Зарегистрировать навыки
        self.register_skill("multi_file_analysis", self.multi_file_analysis_skill)
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Расширенное выполнение задачи с использованием специфических компонентов"""
        
        # Определить, нужно ли использовать расширенный анализ
        if self._requires_enhanced_analysis(task_description, context):
            return await self._execute_enhanced_analysis(task_description, context)
        
        # Использовать базовую реализацию
        return await super().execute_task(task_description, context)
    
    def _requires_enhanced_analysis(self, task_description: str, context: Dict[str, Any] = None) -> bool:
        """Определить, требуется ли расширенный анализ"""
        desc_lower = task_description.lower()
        
        # Триггеры для расширенного анализа
        enhanced_triggers = [
            "комплексный", "детальный", "глубокий", "все файлы", "зависимости",
            "comprehensive", "detailed", "deep", "all files", "dependencies"
        ]
        
        return any(trigger in desc_lower for trigger in enhanced_triggers)
    
    async def _execute_enhanced_analysis(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить расширенный анализ с использованием специфических компонентов"""
        
        try:
            # Извлечь путь к проекту из контекста или описания задачи
            project_path = context.get("project_path") if context else self._extract_project_path(task_description)
            
            if not project_path:
                return {
                    "success": False,
                    "error": "Не указан путь к проекту для расширенного анализа"
                }
            
            # Выполнить многофайловый анализ
            analysis_result = await self.multi_file_analysis_skill.execute({
                "project_path": project_path,
                "file_patterns": context.get("file_patterns", ["**/*.py", "**/*.js", "**/*.ts"]),
                "exclude_patterns": context.get("exclude_patterns", ["**/node_modules/**", "**/__pycache__/**"]),
                "analysis_types": context.get("analysis_types", ["security", "quality", "dependencies"]),
                "include_details": context.get("include_details", True)
            })
            
            return {
                "success": True,
                "enhanced_analysis_results": analysis_result,
                "analysis_type": "comprehensive"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении расширенного анализа: {str(e)}"
            }
    
    def _extract_project_path(self, task_description: str) -> str:
        """Извлечь путь к проекту из описания задачи"""
        import re
        
        # Паттерны для поиска путей к проектам
        patterns = [
            r'проект\s+([^\s]+)',
            r'директори(?:я|ию)\s+([^\s]+)',
            r'([^\s]+[/\\][^\s/\\]+)'  # Базовая структура пути
        ]
        
        for pattern in patterns:
            match = re.search(pattern, task_description, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    async def execute_atomic_action(self, action_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Расширенное выполнение атомарного действия"""
        
        # Проверить, есть ли специфический обработчик для действия
        if hasattr(self, f"_handle_{action_name}"):
            handler = getattr(self, f"_handle_{action_name}")
            return await handler(parameters)
        
        # Использовать базовую реализацию
        return await super().execute_atomic_action(action_name, parameters)
    
    async def _handle_advanced_file_analysis(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Обработчик расширенного анализа файла"""
        return await self.advanced_file_analyzer.execute(parameters)
    
    async def _handle_dependency_scan(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Обработчик сканирования зависимостей"""
        return await self.dependency_scanner.execute(parameters)
    
    def register_tool(self, name: str, tool: ITool):
        """Регистрация инструмента с проверкой совместимости"""
        # Проверить, поддерживает ли инструмент домен агента
        if hasattr(tool, 'compatible_domains') and self.domain_type not in tool.compatible_domains:
            raise ValueError(f"Инструмент {name} несовместим с доменом {self.domain_type}")
        
        self._tools[name] = tool
    
    def register_skill(self, name: str, skill: ISkill):
        """Регистрация навыка с проверкой совместимости"""
        # Проверить, поддерживает ли навык домен агента
        if hasattr(skill, 'compatible_domains') and self.domain_type not in skill.compatible_domains:
            raise ValueError(f"Навык {name} несовместим с доменом {self.domain_type}")
        
        self._skills[name] = skill
```

## Интеграция с системой

### 1. Фабрика агентов

Для создания специфических агентов используйте расширенную фабрику:

```python
# application/factories/specialized_agent_factory.py
from application.factories.agent_factory import AgentFactory
from application.agents.specialized_agents import SpecializedCodeAnalysisAgent
from application.agents.enhanced_agent import EnhancedCodeAnalysisAgent
from domain.value_objects.domain_type import DomainType

class SpecializedAgentFactory(AgentFactory):
    """Фабрика для создания специфических агентов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._registered_agent_types = {
            "specialized_code_analyzer": SpecializedCodeAnalysisAgent,
            "enhanced_code_analyzer": EnhancedCodeAnalysisAgent,
            # Другие специфические типы агентов
        }
        self._domain_mappings = {
            DomainType.CODE_ANALYSIS: ["specialized_code_analyzer", "enhanced_code_analyzer"],
            DomainType.DATA_PROCESSING: [],  # Можно добавить другие домены
            DomainType.CONTENT_GENERATION: []
        }
    
    async def create_agent(
        self, 
        agent_type: str, 
        domain: DomainType, 
        config: Dict[str, Any] = None
    ) -> IAgent:
        """Создать агента специфического типа для домена"""
        
        if agent_type not in self._registered_agent_types:
            raise ValueError(f"Тип агента {agent_type} не зарегистрирован")
        
        # Проверить, поддерживает ли тип агента указанный домен
        supported_types = self._domain_mappings.get(domain, [])
        if agent_type not in supported_types and supported_types:  # Если список не пустой
            raise ValueError(f"Тип агента {agent_type} не поддерживает домен {domain}")
        
        agent_class = self._registered_agent_types[agent_type]
        
        # Создать зависимости
        event_publisher = await self._create_event_publisher(config)
        action_executor = await self._create_action_executor(config)
        pattern_executor = await self._create_pattern_executor(config)
        
        # Создать агента с зависимостями
        agent = agent_class(
            initial_state=AgentState(),
            event_publisher=event_publisher,
            action_executor=action_executor,
            pattern_executor=pattern_executor
        )
        
        # Инициализировать агента
        await agent.initialize()
        
        # Адаптировать к домену
        await agent.adapt_to_domain(domain, self._get_capabilities_for_domain(domain))
        
        return agent
    
    def _get_capabilities_for_domain(self, domain: DomainType) -> List[str]:
        """Получить возможности для домена"""
        capability_mappings = {
            DomainType.CODE_ANALYSIS: [
                "code_analysis", "security_scanning", "quality_assessment",
                "vulnerability_detection", "best_practices_check"
            ],
            DomainType.DATA_PROCESSING: [
                "data_transformation", "sql_execution", "data_validation"
            ],
            DomainType.CONTENT_GENERATION: [
                "text_generation", "content_synthesis", "style_adaptation"
            ]
        }
        
        return capability_mappings.get(domain, [])
    
    def register_agent_type(self, name: str, agent_class: type, supported_domains: List[DomainType] = None):
        """Зарегистрировать новый тип агента"""
        self._registered_agent_types[name] = agent_class
        
        if supported_domains:
            self._domain_mappings[name] = [domain.value for domain in supported_domains]
    
    def get_available_agent_types(self, domain: DomainType = None) -> List[str]:
        """Получить доступные типы агентов для домена"""
        if domain:
            return self._domain_mappings.get(domain, [])
        else:
            return list(self._registered_agent_types.keys())

class AdvancedAgentFactory(SpecializedAgentFactory):
    """Расширенная фабрика агентов с поддержкой пользовательских конфигураций"""
    
    async def create_agent_with_config(
        self,
        agent_type: str,
        domain: DomainType,
        agent_config: Dict[str, Any],
        tool_configs: Dict[str, Any] = None,
        skill_configs: Dict[str, Any] = None
    ) -> IAgent:
        """Создать агента с расширенной конфигурацией"""
        
        # Создать базового агента
        agent = await self.create_agent(agent_type, domain, agent_config)
        
        # Настроить инструменты с учетом конфигурации
        if tool_configs:
            await self._configure_agent_tools(agent, tool_configs)
        
        # Настроить навыки с учетом конфигурации
        if skill_configs:
            await self._configure_agent_skills(agent, skill_configs)
        
        return agent
    
    async def _configure_agent_tools(self, agent: IAgent, tool_configs: Dict[str, Any]):
        """Настроить инструменты агента"""
        for tool_name, tool_config in tool_configs.items():
            if tool_name in agent.get_available_tools():
                # Применить конфигурацию к существующему инструменту
                await agent.configure_tool(tool_name, tool_config)
    
    async def _configure_agent_skills(self, agent: IAgent, skill_configs: Dict[str, Any]):
        """Настроить навыки агента"""
        for skill_name, skill_config in skill_configs.items():
            if skill_name in agent.get_available_skills():
                # Применить конфигурацию к существующему навыку
                await agent.configure_skill(skill_name, skill_config)
```

### 2. Использование специфических агентов

Пример использования специфических агентов:

```python
# specialized_agent_usage.py
from application.factories.advanced_agent_factory import AdvancedAgentFactory
from domain.value_objects.domain_type import DomainType

async def specialized_agent_example():
    """Пример использования специфических агентов"""
    
    # Создать расширенную фабрику
    factory = AdvancedAgentFactory({
        "agent_defaults": {
            "max_iterations": 100,
            "timeout": 600
        },
        "tool_defaults": {
            "max_file_size": 5 * 1024 * 1024,  # 5MB
            "timeout": 30
        }
    })
    
    # Создать специфический агент для анализа кода
    agent = await factory.create_agent(
        agent_type="enhanced_code_analyzer",
        domain=DomainType.CODE_ANALYSIS,
        config={
            "analysis_depth": "deep",
            "enable_monitoring": True,
            "max_concurrent_analyses": 5
        }
    )
    
    # Выполнить задачу анализа безопасности
    result = await agent.execute_task(
        task_description="Проанализируй проект в директории ./my_project на наличие уязвимостей безопасности",
        context={
            "project_path": "./my_project",
            "file_patterns": ["**/*.py", "**/*.js", "**/*.ts"],
            "exclude_patterns": ["**/node_modules/**", "**/__pycache__/**"],
            "analysis_types": ["security", "dependencies", "configuration"],
            "include_details": True
        }
    )
    
    print(f"Результат анализа безопасности: {result}")
    
    return result

# Интеграция с существующими системами
async def agent_integration_example():
    """Пример интеграции специфических агентов с существующими системами"""
    
    # Создать фабрику
    factory = SpecializedAgentFactory()
    
    # Создать агента для анализа кода
    code_agent = await factory.create_agent(
        agent_type="specialized_code_analyzer",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Создать агента для обработки данных
    data_agent = await factory.create_agent(
        agent_type="specialized_data_processor",  # Предполагаем, что такой тип зарегистрирован
        domain=DomainType.DATA_PROCESSING
    )
    
    # Выполнить комплексную задачу с использованием обоих агентов
    # Например, сначала анализ кода, затем обработка полученных данных
    
    # Шаг 1: Анализ кода
    code_analysis_result = await code_agent.execute_task(
        task_description="Найди SQL-запросы в коде и проверь на уязвимости инъекций",
        context={
            "file_path": "./src/database_queries.py",
            "analysis_types": ["security"],
            "check_types": ["sql_injection"]
        }
    )
    
    if code_analysis_result["success"]:
        # Шаг 2: Обработка результатов анализа
        data_processing_result = await data_agent.execute_task(
            task_description="Обработай результаты анализа и сформируй отчет",
            context={
                "analysis_results": code_analysis_result["analysis_results"],
                "output_format": "json"
            }
        )
        
        print(f"Результат обработки: {data_processing_result}")
        
        return {
            "code_analysis": code_analysis_result,
            "data_processing": data_processing_result
        }
    else:
        print(f"Ошибка анализа кода: {code_analysis_result['error']}")
        return {"success": False, "error": code_analysis_result["error"]}

class CustomAgentOrchestrator:
    """Оркестратор для управления специфическими агентами"""
    
    def __init__(self, agent_factory: SpecializedAgentFactory):
        self.agent_factory = agent_factory
        self.active_agents = {}
        self.execution_history = []
    
    async def execute_multi_agent_task(
        self, 
        task_description: str, 
        agent_requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Выполнить задачу с использованием нескольких специфических агентов"""
        
        results = {}
        agent_tasks = []
        
        try:
            # Создать агентов на основе требований
            for req in agent_requirements:
                agent = await self.agent_factory.create_agent(
                    agent_type=req["type"],
                    domain=req["domain"],
                    config=req.get("config", {})
                )
                
                agent_id = f"agent_{len(self.active_agents)}"
                self.active_agents[agent_id] = agent
                
                # Подготовить задачу для агента
                agent_task = self._prepare_agent_task(task_description, req, agent_id)
                agent_tasks.append((agent_id, agent, agent_task))
            
            # Выполнить задачи агентов
            for agent_id, agent, task in agent_tasks:
                result = await agent.execute_task(task["description"], task["context"])
                results[agent_id] = result
                
                # Добавить в историю выполнения
                self.execution_history.append({
                    "agent_id": agent_id,
                    "task_description": task["description"],
                    "result": result,
                    "timestamp": time.time()
                })
            
            return {
                "success": True,
                "agent_results": results,
                "execution_history": self.execution_history[-10:]  # Последние 10 выполнений
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении многоагентной задачи: {str(e)}"
            }
        finally:
            # Очистить активных агентов
            self.active_agents.clear()
    
    def _prepare_agent_task(self, global_task: str, requirement: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
        """Подготовить задачу для конкретного агента"""
        # Определить, какая часть общей задачи относится к этому агенту
        domain = requirement["domain"]
        
        if domain == DomainType.CODE_ANALYSIS:
            return {
                "description": f"[{agent_id}] {global_task}",
                "context": {
                    "domain_specific_instruction": "Выполни анализ соответствующей предметной области",
                    **requirement.get("context", {})
                }
            }
        elif domain == DomainType.DATA_PROCESSING:
            return {
                "description": f"[{agent_id}] Обработай данные в рамках задачи: {global_task}",
                "context": {
                    "domain_specific_instruction": "Выполни обработку данных",
                    **requirement.get("context", {})
                }
            }
        else:
            return {
                "description": f"[{agent_id}] {global_task}",
                "context": requirement.get("context", {})
            }
```

## Лучшие практики

### 1. Модульность и расширяемость

Создавайте агентов, которые можно легко расширять:

```python
# Хорошо: модульная архитектура
class BaseAgent:
    """Базовый агент"""
    pass

class AnalysisAgent(BaseAgent):
    """Агент анализа"""
    pass

class SecurityAnalysisAgent(AnalysisAgent):
    """Агент анализа безопасности"""
    pass

# Плохо: монолитный агент
class MonolithicAgent:
    """Монолитный агент - сложно расширять и тестировать"""
    pass
```

### 2. Безопасность и валидация

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

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Выполнить задачу с надежной обработкой ошибок"""
    try:
        # Проверить ограничения
        if self.state.error_count > self.max_error_threshold:
            return {
                "success": False,
                "error": "Превышено максимальное количество ошибок",
                "needs_reset": True
            }
        
        # Выполнить основную логику
        result = await self._execute_extended_logic(task_description, context)
        
        # Обновить состояние при успехе
        self.state.register_progress(progressed=True)
        
        return {"success": True, **result}
    except SecurityError as e:
        self.state.register_error()
        self.state.complete()  # Критическая ошибка безопасности
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security",
            "terminated": True
        }
    except ResourceLimitExceededError as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Превышено ограничение ресурсов: {str(e)}",
            "error_type": "resource_limit"
        }
    except Exception as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal"
        }

def _check_resource_availability(self) -> bool:
    """Проверить доступность ресурсов"""
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

### 4. Тестирование специфических агентов

Создавайте тесты для каждого специфического агента:

```python
# test_specialized_agents.py
import pytest
from unittest.mock import AsyncMock, Mock
import tempfile
import os

class TestSpecializedCodeAnalysisAgent:
    @pytest.mark.asyncio
    async def test_security_analysis_success(self):
        """Тест успешного анализа безопасности"""
        # Создать моки зависимостей
        mock_event_publisher = AsyncMock()
        mock_action_executor = AsyncMock()
        mock_pattern_executor = AsyncMock()
        
        # Настроить моки атомарных действий
        mock_action_executor.execute_action.side_effect = [
            # Результат чтения файла
            {
                "success": True,
                "content": """
def vulnerable_function(user_input):
    query = f"SELECT * FROM users WHERE id = {user_input}"
    return execute_query(query)
""",
                "size": 100
            },
            # Результат парсинга AST
            {
                "success": True,
                "ast": {"nodes": []}
            },
            # Результат сканирования безопасности
            {
                "success": True,
                "findings": [
                    {
                        "type": "SQL_INJECTION_POSSIBLE",
                        "severity": "HIGH",
                        "line_number": 3,
                        "description": "Potential SQL injection vulnerability"
                    }
                ]
            }
        ]
        
        # Создать агента
        agent = SpecializedCodeAnalysisAgent(
            event_publisher=mock_event_publisher,
            action_executor=mock_action_executor,
            pattern_executor=mock_pattern_executor
        )
        
        # Выполнить задачу
        result = await agent.execute_task(
            task_description="Проанализируй файл на уязвимости безопасности",
            context={"file_path": "test.py"}
        )
        
        # Проверить результат
        assert result["success"] is True
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["success"] is True
        assert len(result["results"][0]["findings"]) == 1
    
    @pytest.mark.asyncio
    async def test_agent_handles_missing_file(self):
        """Тест обработки отсутствующего файла"""
        # Создать агента
        agent = SpecializedCodeAnalysisAgent()
        
        # Выполнить задачу с несуществующим файлом
        result = await agent.execute_task(
            task_description="Проанализируй несуществующий файл",
            context={"file_path": "nonexistent.py"}
        )
        
        # Проверить, что задача завершилась с ошибкой
        assert result["success"] is False
        assert "error" in result
        assert "файл не найден" in result["error"].lower()

class TestEnhancedCodeAnalysisAgent:
    @pytest.mark.asyncio
    async def test_enhanced_analysis_selection(self):
        """Тест выбора расширенного анализа"""
        agent = EnhancedCodeAnalysisAgent()
        
        # Тест с триггером расширенного анализа
        assert agent._requires_enhanced_analysis("Выполни комплексный анализ проекта") is True
        assert agent._requires_enhanced_analysis("Сделай детальный анализ безопасности") is True
        
        # Тест без триггера
        assert agent._requires_enhanced_analysis("Просто проанализируй код") is False
    
    @pytest.mark.asyncio
    async def test_enhanced_analysis_execution(self):
        """Тест выполнения расширенного анализа"""
        # Создать моки
        mock_skill = AsyncMock()
        mock_skill.execute.return_value = {
            "success": True,
            "files_analyzed": 5,
            "vulnerabilities_found": 2,
            "dependencies_scanned": 10
        }
        
        # Создать агента
        agent = EnhancedCodeAnalysisAgent()
        agent.register_skill("multi_file_analysis", mock_skill)
        
        # Выполнить задачу, требующую расширенного анализа
        result = await agent.execute_task(
            task_description="Выполни комплексный анализ безопасности проекта",
            context={
                "project_path": "./test_project",
                "analysis_types": ["security", "dependencies"]
            }
        )
        
        # Проверить, что был вызван навык расширенного анализа
        assert result["success"] is True
        assert "enhanced_analysis_results" in result
        mock_skill.execute.assert_called_once()

class TestSpecializedAgentFactory:
    def test_agent_type_registration(self):
        """Тест регистрации типов агентов"""
        factory = SpecializedAgentFactory()
        
        # Проверить, что встроенные типы зарегистрированы
        assert "specialized_code_analyzer" in factory.get_available_agent_types()
        assert "enhanced_code_analyzer" in factory.get_available_agent_types()
    
    @pytest.mark.asyncio
    async def test_create_agent_with_domain_check(self):
        """Тест создания агента с проверкой домена"""
        factory = SpecializedAgentFactory()
        
        # Создать агента для поддерживаемого домена
        agent = await factory.create_agent(
            "specialized_code_analyzer",
            DomainType.CODE_ANALYSIS
        )
        
        assert agent is not None
        
        # Попробовать создать агента с неподдерживаемым доменом
        with pytest.raises(ValueError):
            await factory.create_agent(
                "specialized_code_analyzer",  # Тип агента не поддерживает DATA_PROCESSING
                DomainType.DATA_PROCESSING
            )
```

Эти примеры показывают, как адаптировать и расширять архитектуру агентов Composable AI Agent Framework под специфические задачи, обеспечивая модульность, безопасность и надежность системы.