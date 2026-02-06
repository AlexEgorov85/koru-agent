# Руководство по настройке Composable AI Agent Framework

В этом руководстве описаны шаги и рекомендации по адаптации Composable AI Agent Framework под конкретные задачи и требования. Вы узнаете, как модифицировать существующие компоненты и создавать новые для удовлетворения специфических нужд.

## Общая стратегия настройки

### 1. Анализ требований

Перед началом настройки необходимо проанализировать:

- **Тип задачи**: Какие задачи будет решать система?
- **Домен задачи**: В какой области будет использоваться система?
- **Требования безопасности**: Какие меры безопасности необходимы?
- **Ограничения ресурсов**: Какие есть ограничения по ресурсам?
- **Интеграции**: С какими внешними системами нужно интегрироваться?
- **Форматы данных**: Какие форматы данных используются?

### 2. Планирование архитектуры

Определите, какие компоненты нужно настроить:

```
Архитектура настройки:
┌─────────────────┐
│  Специфические  │ ← Создание специфических компонентов
│   компоненты    │
├─────────────────┤
│  Интеграция с   │ ← Интеграция специфических компонентов
│  существующими  │   с существующей архитектурой
├─────────────────┤
│  Конфигурация   │ ← Настройка параметров системы
│                 │
├─────────────────┤
│  Тестирование   │ ← Проверка корректности настройки
│                 │
└─────────────────┘
```

## Настройка агентов

### 1. Создание специфических агентов

Для создания агента под конкретные задачи:

```python
# application/agents/specialized_agents.py
from domain.abstractions.agent import IAgent
from domain.models.agent.agent_state import AgentState
from application.services.event_publisher import EventPublisher
from application.orchestration.atomic_action_executor import AtomicActionExecutor

class SpecializedAgent(IAgent):
    """Специфический агент для конкретных задач"""
    
    def __init__(self, domain_type: DomainType, config: Dict[str, Any] = None):
        self.domain_type = domain_type
        self.config = config or {}
        self.state = AgentState()
        self.event_publisher = EventPublisher()
        self.action_executor = AtomicActionExecutor()
        self._specialized_patterns = []
        self._custom_tools = []
        self._domain_specific_prompts = []
        
        # Инициализировать специфические компоненты
        self._initialize_specialized_components()
    
    def _initialize_specialized_components(self):
        """Инициализировать специфические компоненты агента"""
        # Загрузить специфические паттерны для домена
        self._load_specialized_patterns()
        
        # Загрузить специфические инструменты
        self._load_custom_tools()
        
        # Загрузить доменно-специфические промты
        self._load_domain_specific_prompts()
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу с использованием специфических компонентов"""
        try:
            # Определить тип задачи и выбрать подходящий специфический паттерн
            specialized_pattern = self._select_specialized_pattern(task_description, context)
            
            if specialized_pattern:
                # Выполнить задачу через специфический паттерн
                result = await specialized_pattern.execute(
                    state=self.state,
                    context=context or {},
                    available_capabilities=self.get_available_capabilities()
                )
                
                return {
                    "success": True,
                    "result": result,
                    "pattern_used": specialized_pattern.name,
                    "task_type": "specialized"
                }
            else:
                # Использовать базовую логику выполнения
                return await self._execute_general_task(task_description, context)
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении задачи: {str(e)}",
                "task_type": "specialized"
            }
    
    def _select_specialized_pattern(self, task_description: str, context: Dict[str, Any]) -> Optional[IThinkingPattern]:
        """Выбрать подходящий специфический паттерн для задачи"""
        for pattern in self._specialized_patterns:
            if pattern.can_handle_task(task_description, context):
                return pattern
        return None
    
    def _load_specialized_patterns(self):
        """Загрузить специфические паттерны для домена"""
        # Загрузить паттерны из конфигурации или файловой системы
        pattern_configs = self.config.get("specialized_patterns", [])
        
        for pattern_config in pattern_configs:
            pattern_type = pattern_config["type"]
            pattern_params = pattern_config.get("parameters", {})
            
            # Создать паттерн в зависимости от типа
            if pattern_type == "security_analysis":
                from application.patterns.security_analysis_pattern import SecurityAnalysisPattern
                pattern = SecurityAnalysisPattern(pattern_params)
            elif pattern_type == "code_quality":
                from application.patterns.code_quality_pattern import CodeQualityPattern
                pattern = CodeQualityPattern(pattern_params)
            else:
                # Заглушка для других типов
                continue
            
            self._specialized_patterns.append(pattern)
    
    def _load_custom_tools(self):
        """Загрузить специфические инструменты"""
        tool_configs = self.config.get("custom_tools", [])
        
        for tool_config in tool_configs:
            tool_type = tool_config["type"]
            tool_params = tool_config.get("parameters", {})
            
            # Создать инструмент в зависимости от типа
            if tool_type == "file_analyzer":
                from infrastructure.tools.file_analyzer_tool import FileAnalyzerTool
                tool = FileAnalyzerTool(**tool_params)
            elif tool_type == "code_security_scanner":
                from infrastructure.tools.security_scanner_tool import SecurityScannerTool
                tool = SecurityScannerTool(**tool_params)
            else:
                # Заглушка для других типов
                continue
            
            self._custom_tools.append(tool)
            self.action_executor.register_action(tool)
    
    def _load_domain_specific_prompts(self):
        """Загрузить доменно-специфические промты"""
        from application.services.prompt_loader import PromptLoader
        
        prompt_loader = PromptLoader(base_path=f"prompts/{self.domain_type.value}")
        domain_prompts, errors = prompt_loader.load_all_prompts()
        
        if errors:
            print(f"Ошибки при загрузке промтов для домена {self.domain_type}: {errors}")
        
        self._domain_specific_prompts = domain_prompts
    
    async def _execute_general_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить общую задачу через базовую логику"""
        # Реализация базовой логики выполнения задачи
        # которая используется, когда нет подходящего специфического паттерна
        pass
    
    def get_available_capabilities(self) -> List[str]:
        """Получить доступные возможности агента"""
        capabilities = []
        
        # Добавить возможности из специфических паттернов
        for pattern in self._specialized_patterns:
            capabilities.extend(pattern.get_required_capabilities())
        
        # Добавить возможности из специфических инструментов
        for tool in self._custom_tools:
            capabilities.append(tool.name)
        
        return list(set(capabilities))
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать агента к конкретной задаче"""
        # Определить, какие специфические компоненты подходят для задачи
        applicable_patterns = [
            pattern for pattern in self._specialized_patterns
            if pattern.can_handle_task(task_description, {})
        ]
        
        return {
            "applicable_patterns": [p.name for p in applicable_patterns],
            "required_capabilities": self._get_required_capabilities_for_task(task_description),
            "confidence_level": len(applicable_patterns) / len(self._specialized_patterns) if self._specialized_patterns else 0
        }
    
    def _get_required_capabilities_for_task(self, task_description: str) -> List[str]:
        """Получить необходимые возможности для задачи"""
        # Определить необходимые возможности на основе описания задачи
        desc_lower = task_description.lower()
        required_caps = []
        
        if "безопасность" in desc_lower or "security" in desc_lower:
            required_caps.extend(["security_analysis", "vulnerability_scanning"])
        
        if "качество" in desc_lower or "quality" in desc_lower:
            required_caps.extend(["code_quality_analysis", "best_practices_check"])
        
        if "анализ" in desc_lower:
            required_caps.extend(["code_analysis", "data_analysis"])
        
        return required_caps
```

### 2. Настройка конфигурации агента

Для настройки агента создайте специфическую конфигурацию:

```yaml
# config/specialized_agent_config.yaml
specialized_agent:
  domain_type: "code_analysis"
  max_iterations: 100
  timeout: 600
  enable_logging: true
  specialized_patterns:
    - type: "security_analysis"
      parameters:
        scan_depth: "deep"
        vulnerability_types: ["sql_injection", "xss", "command_injection"]
    - type: "code_quality"
      parameters:
        standards: ["pep8", "security_best_practices"]
        max_complexity: 10
  custom_tools:
    - type: "file_analyzer"
      parameters:
        max_file_size: 5242880  # 5MB
        supported_formats: [".py", ".js", ".ts", ".java", ".cs"]
    - type: "security_scanner"
      parameters:
        enabled_checks: ["sqli", "xss", "sensitive_data"]
        timeout: 30
  resource_limits:
    memory: "2GB"
    cpu_percentage: 75.0
  security_policy:
    enable_auditing: true
    restrict_file_access: true
    allowed_directories:
      - "./projects"
      - "./data"
      - "./outputs"
```

## Настройка паттернов мышления

### 1. Создание специфических паттернов

Для создания паттернов под конкретные задачи:

```python
# application/patterns/specialized_patterns.py
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState
from typing import Any, Dict, List

class SpecializedThinkingPattern(IThinkingPattern):
    """Специфический паттерн мышления для конкретных задач"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = self.config.get("name", "specialized_pattern")
        self._required_tools = self.config.get("required_tools", [])
        self._execution_strategy = self.config.get("execution_strategy", "sequential")
        self._supported_domains = self.config.get("supported_domains", [])
        self._task_keywords = self.config.get("task_keywords", [])
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить специфический паттерн мышления"""
        try:
            # Проверить, доступны ли необходимые инструменты
            missing_tools = [
                tool for tool in self._required_tools
                if tool not in available_capabilities
            ]
            
            if missing_tools:
                return {
                    "success": False,
                    "error": f"Отсутствуют необходимые инструменты: {missing_tools}",
                    "missing_tools": missing_tools,
                    "pattern_used": self.name
                }
            
            # Выполнить специфическую логику
            result = await self._execute_specialized_logic(state, context)
            
            return {
                "success": True,
                "result": result,
                "pattern_used": self.name,
                "execution_strategy": self._execution_strategy
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении паттерна {self.name}: {str(e)}",
                "pattern_used": self.name,
                "error_type": type(e).__name__
            }
    
    async def _execute_specialized_logic(self, state: AgentState, context: Any) -> Dict[str, Any]:
        """Выполнить специфическую логику паттерна"""
        # Реализация специфической логики для решения задачи
        # в зависимости от типа паттерна и конфигурации
        pass
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к конкретной задаче"""
        # Определить, может ли паттерн обработать задачу
        can_handle = self._can_handle_task(task_description)
        
        return {
            "can_handle": can_handle,
            "confidence_level": self._calculate_confidence(task_description) if can_handle else 0,
            "required_capabilities": self._required_tools,
            "estimated_complexity": self._estimate_complexity(task_description),
            "pattern_name": self.name
        }
    
    def _can_handle_task(self, task_description: str) -> bool:
        """Проверить, может ли паттерн обработать задачу"""
        desc_lower = task_description.lower()
        
        # Проверить ключевые слова задачи
        for keyword in self._task_keywords:
            if keyword.lower() in desc_lower:
                return True
        
        # Проверить, поддерживает ли паттерн домен задачи
        if hasattr(self, 'domain_type'):
            return self.domain_type.value in self._supported_domains
        
        return False
    
    def _calculate_confidence(self, task_description: str) -> float:
        """Рассчитать уровень уверенности в обработке задачи"""
        desc_lower = task_description.lower()
        matched_keywords = 0
        
        for keyword in self._task_keywords:
            if keyword.lower() in desc_lower:
                matched_keywords += 1
        
        return matched_keywords / len(self._task_keywords) if self._task_keywords else 0.5
    
    def _estimate_complexity(self, task_description: str) -> str:
        """Оценить сложность задачи"""
        desc_lower = task_description.lower()
        
        if any(keyword in desc_lower for keyword in ["комплексный", "сложный", "множественный", "multi"]):
            return "high"
        elif any(keyword in desc_lower for keyword in ["средний", "умеренный", "moderate"]):
            return "medium"
        else:
            return "low"
    
    def get_required_capabilities(self) -> List[str]:
        """Получить необходимые возможности для паттерна"""
        return self._required_tools.copy()

class SecurityAnalysisPattern(SpecializedThinkingPattern):
    """Паттерн анализа безопасности кода"""
    
    def __init__(self, config: Dict[str, Any] = None):
        security_config = {
            "name": "security_analysis_pattern",
            "required_tools": ["code_reader", "ast_parser", "security_scanner"],
            "task_keywords": ["безопасность", "security", "vulnerability", "уязвимость", "инъекция", "xss", "sqli"],
            "supported_domains": ["code_analysis", "security_analysis"],
            **(config or {})
        }
        
        super().__init__(security_config)
        self._vulnerability_types = self.config.get("vulnerability_types", [
            "sql_injection", "xss", "command_injection", 
            "path_traversal", "deserialization", "csrf"
        ])
    
    async def _execute_specialized_logic(self, state: AgentState, context: Any) -> Dict[str, Any]:
        """Выполнить логику анализа безопасности"""
        code = context.get("code", "")
        language = context.get("language", "python")
        
        findings = []
        
        # Выполнить анализ на основе типа языка
        if language.lower() == "python":
            findings.extend(self._analyze_python_security(code))
        elif language.lower() == "javascript":
            findings.extend(self._analyze_javascript_security(code))
        
        return {
            "findings": findings,
            "total_vulnerabilities": len(findings),
            "high_severity_count": len([f for f in findings if f["severity"] == "HIGH"]),
            "analysis_language": language,
            "vulnerability_types_checked": self._vulnerability_types
        }
    
    def _analyze_python_security(self, code: str) -> List[Dict[str, Any]]:
        """Анализ безопасности Python-кода"""
        import re
        findings = []
        
        # Проверить на SQL-инъекции
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
                    "code_snippet": match.group(0)[:100],
                    "description": "Потенциальная уязвимость SQL-инъекции"
                })
        
        # Проверить на использование небезопасных функций
        dangerous_functions = [
            "eval(", "exec(", "execfile(", "__import__(",
            "compile(", "open(", "subprocess."
        ]
        
        for func in dangerous_functions:
            if func in code:
                findings.append({
                    "type": "DANGEROUS_FUNCTION_USAGE",
                    "severity": "HIGH" if func in ["eval(", "exec("] else "MEDIUM",
                    "description": f"Обнаружено использование небезопасной функции: {func}",
                    "code_snippet": code[code.find(func):code.find(func)+50]
                })
        
        return findings
```

## Настройка системы промтов

### 1. Создание специфических промтов

Для настройки системы промтов под конкретные задачи:

```python
# application/services/specialized_prompt_loader.py
from application.services.prompt_loader import PromptLoader
from domain.models.prompt.prompt_version import PromptVersion, PromptRole
from domain.value_objects.domain_type import DomainType
import yaml
import json
from pathlib import Path

class SpecializedPromptLoader(PromptLoader):
    """Загрузчик специфических промтов"""
    
    def __init__(self, base_path: str = "./prompts", specialized_domains: List[DomainType] = None):
        super().__init__(base_path)
        self.specialized_domains = specialized_domains or []
        self._specialized_validators = {}
        self._specialized_transformers = {}
        
        # Загрузить специфические валидаторы
        self._load_specialized_validators()
    
    def load_all_prompts(self) -> Tuple[List[PromptVersion], List[str]]:
        """Загрузить все промты с дополнительной обработкой"""
        prompts, errors = super().load_all_prompts()
        
        # Применить специфические валидаторы
        validated_prompts = []
        for prompt in prompts:
            if self._is_specialized_prompt(prompt):
                if self._validate_specialized_prompt(prompt):
                    validated_prompts.append(prompt)
                else:
                    errors.append(f"Специфический промт не прошел валидацию: {prompt.id}")
            else:
                validated_prompts.append(prompt)
        
        return validated_prompts, errors
    
    def _is_specialized_prompt(self, prompt: PromptVersion) -> bool:
        """Проверить, является ли промт специфическим"""
        return prompt.domain in self.specialized_domains
    
    def _validate_specialized_prompt(self, prompt: PromptVersion) -> bool:
        """Валидировать специфический промт"""
        domain = prompt.domain
        
        if domain in self._specialized_validators:
            validator = self._specialized_validators[domain]
            return validator(prompt)
        
        # По умолчанию использовать базовую валидацию
        return self._validate_prompt_content(prompt.content)
    
    def _validate_prompt_content(self, content: str) -> bool:
        """Базовая валидация содержимого промта"""
        # Проверить на наличие потенциально опасных паттернов
        dangerous_patterns = [
            r"ignore\s+previous\s+instructions",
            r"disregard\s+safety\s+guidelines",
            r"bypass\s+security\s+measures",
            r"execute\s+system\s+command",
            r"run\s+shell\s+command"
        ]
        
        for pattern in dangerous_patterns:
            import re
            if re.search(pattern, content, re.IGNORECASE):
                return False
        
        return True
    
    def _load_specialized_validators(self):
        """Загрузить специфические валидаторы"""
        # Валидатор для домена анализа кода
        def code_analysis_validator(prompt: PromptVersion) -> bool:
            # Проверить, что промт содержит необходимые элементы для анализа кода
            required_elements = ["анализ", "код", "безопасность", "уязвимости"]
            content_lower = prompt.content.lower()
            return any(element in content_lower for element in required_elements)
        
        # Валидатор для домена обработки данных
        def data_processing_validator(prompt: PromptVersion) -> bool:
            # Проверить, что промт содержит элементы для обработки данных
            required_elements = ["данные", "обработка", "анализ", "таблица", "запрос"]
            content_lower = prompt.content.lower()
            return any(element in content_lower for element in required_elements)
        
        # Регистрация валидаторов
        self._specialized_validators[DomainType.CODE_ANALYSIS] = code_analysis_validator
        self._specialized_validators[DomainType.DATA_PROCESSING] = data_processing_validator
    
    def create_specialized_prompt(
        self,
        domain: DomainType,
        capability: str,
        role: PromptRole,
        version: str,
        content: str,
        variables_schema: List[Dict[str, Any]] = None
    ) -> PromptVersion:
        """Создать специфический промт"""
        
        # Создать ID на основе домена, капабилити, роли и версии
        prompt_id = f"{domain.value}_{capability}_{role.value}_v{version.replace('.', '_')}"
        
        # Создать объект промта
        prompt = PromptVersion(
            id=prompt_id,
            semantic_version=version,
            domain=domain,
            provider_type=LLMProviderType.OPENAI,  # По умолчанию
            capability_name=capability,
            role=role,
            content=content,
            variables_schema=variables_schema or [],
            status=PromptStatus.ACTIVE,
            created_at=datetime.utcnow(),
            expected_response_schema={}
        )
        
        # Применить специфическую валидацию
        if not self._validate_specialized_prompt(prompt):
            raise ValueError(f"Специфический промт не прошел валидацию: {prompt_id}")
        
        return prompt
    
    async def save_specialized_prompt(self, prompt: PromptVersion, file_path: str):
        """Сохранить специфический промт в файл"""
        
        # Создать директории при необходимости
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Создать frontmatter
        frontmatter = {
            "provider": prompt.provider_type.value,
            "role": prompt.role.value,
            "status": prompt.status.value,
            "version": prompt.semantic_version,
            "domain": prompt.domain.value,
            "capability": prompt.capability_name,
            "variables": prompt.variables_schema,
            "expected_response": prompt.expected_response_schema
        }
        
        # Создать содержимое файла
        yaml_frontmatter = yaml.dump(frontmatter, default_flow_style=False)
        content = f"---\n{yaml_frontmatter}---\n\n{prompt.content}"
        
        # Записать файл
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)
```

### 2. Структура специфических промтов

Создайте структуру для специфических промтов:

```
prompts/
├── custom_domain/          # Ваш специфический домен
│   ├── security_analysis/  # Специфическая капабилити
│   │   ├── system/         # Роль системы
│   │   │   └── v1.0.0.md   # Версия промта
│   │   ├── user/
│   │   │   └── v1.0.0.md
│   │   └── assistant/
│   │       └── v1.0.0.md
│   └── data_processing/
│       ├── system/
│       │   └── v1.0.0.md
│       └── tool/
│           └── v1.0.0.md
```

Пример специфического промта:

```markdown
---
provider: openai
role: system
status: active
version: 1.0.0
domain: custom_domain
capability: security_analysis
variables:
  - name: task_description
    type: string
    required: true
    description: "Описание задачи анализа безопасности"
  - name: target_vulnerabilities
    type: array
    required: false
    description: "Целевые типы уязвимостей для поиска"
expected_response:
  type: object
  properties:
    findings:
      type: array
      items:
        type: object
        properties:
          type:
            type: string
          severity:
            type: string
          description:
            type: string
          location:
            type: object
---

# Инструкции для агента анализа безопасности

Ты являешься экспертом в области безопасности кода. При анализе кода следуй следующим принципам:

1. Идентифицируй потенциальные уязвимости в коде
2. Оцени уровень риска каждой уязвимости
3. Предложи конкретные рекомендации по устранению
4. Объясни, почему каждая уязвимость представляет риск

## Задача

{{task_description}}

{% if target_vulnerabilities %}
## Фокусируйся на этих типах уязвимостей:
{% for vuln in target_vulnerabilities %}
- {{vuln}}
{% endfor %}
{% endif %}

Ты должен отвечать только в формате JSON с определенной структурой.
```

## Настройка инструментов и навыков

### 1. Создание специфических инструментов

Для создания инструментов под конкретные задачи:

```python
# infrastructure/tools/specialized_tools.py
from domain.abstractions.tool import ITool
from domain.models.tool_metadata import ToolMetadata
import os
from pathlib import Path

class SpecializedFileAnalyzerTool(ITool):
    """Специфический инструмент для анализа файлов под конкретные задачи"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self._max_file_size = self.config.get("max_file_size", 10 * 1024 * 1024)  # 10MB
        self._supported_formats = self.config.get("supported_formats", [
            ".py", ".js", ".ts", ".java", ".cs", ".cpp", ".c",
            ".html", ".css", ".json", ".yaml", ".xml"
        ])
        self._analysis_types = self.config.get("analysis_types", [
            "security", "quality", "complexity", "dependencies"
        ])
        self._required_permissions = ["read_file", "analyze_content"]
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="specialized_file_analyzer",
            description="Анализирует файлы на наличие специфических проблем",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу для анализа"
                    },
                    "analysis_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "enum": self._analysis_types,
                        "default": self._analysis_types,
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
                            "dependency_issues": {"type": "array"}
                        }
                    },
                    "file_info": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "size": {"type": "integer"},
                            "extension": {"type": "string"}
                        }
                    },
                    "error": {"type": "string"}
                }
            },
            category="analysis",
            permissions=["read_file", "analyze_content"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ файла с дополнительной обработкой"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        file_path = parameters["file_path"]
        analysis_types = parameters.get("analysis_types", self._analysis_types)
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
            
            # Проверить расширение файла
            if path.suffix.lower() not in self._supported_formats:
                return {
                    "success": False,
                    "error": f"Формат файла {path.suffix} не поддерживается. Поддерживаемые: {self._supported_formats}"
                }
            
            # Проверить размер файла
            file_size = path.stat().st_size
            if file_size > self._max_file_size:
                return {
                    "success": False,
                    "error": f"Файл слишком большой: {file_size} байт, максимум {self._max_file_size}"
                }
            
            # Прочитать файл
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Выполнить анализ в зависимости от типов
            analysis_results = {}
            
            for analysis_type in analysis_types:
                if analysis_type == "security":
                    analysis_results["security_findings"] = await self._perform_security_analysis(content)
                elif analysis_type == "quality":
                    analysis_results["quality_issues"] = await self._perform_quality_analysis(content)
                elif analysis_type == "complexity":
                    analysis_results["complexity_metrics"] = await self._perform_complexity_analysis(content)
                elif analysis_type == "dependencies":
                    analysis_results["dependency_issues"] = await self._perform_dependency_analysis(content)
            
            return {
                "success": True,
                "analysis_results": analysis_results,
                "file_info": {
                    "path": str(path),
                    "size": file_size,
                    "extension": path.suffix.lower(),
                    "analysis_types_performed": analysis_types
                },
                "include_details": include_details
            }
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": f"Не удалось декодировать файл с кодировкой {parameters.get('encoding', 'utf-8')}"
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
            
            if not all(atype in self._analysis_types for atype in analysis_types):
                return False
        
        return True
    
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
    
    async def _perform_security_analysis(self, content: str) -> List[Dict[str, Any]]:
        """Выполнить анализ безопасности содержимого файла"""
        findings = []
        
        # Проверить на SQL-инъекции
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
                    "type": "SQL_INJECTION",
                    "severity": "HIGH",
                    "line_number": content[:match.start()].count('\n') + 1,
                    "code_snippet": match.group(0)[:100],
                    "description": "Потенциальная уязвимость SQL-инъекции"
                })
        
        # Проверить на использование небезопасных функций
        dangerous_functions = ["eval(", "exec(", "execfile(", "__import__(", "compile("]
        for func in dangerous_functions:
            if func in content:
                findings.append({
                    "type": "DANGEROUS_FUNCTION_USAGE",
                    "severity": "HIGH" if func in ["eval(", "exec("] else "MEDIUM",
                    "description": f"Обнаружено использование небезопасной функции: {func}",
                    "code_snippet": content[content.find(func):content.find(func)+50]
                })
        
        return findings
    
    async def _perform_quality_analysis(self, content: str) -> List[Dict[str, Any]]:
        """Выполнить анализ качества содержимого файла"""
        issues = []
        
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
    
    async def _perform_complexity_analysis(self, content: str) -> Dict[str, Any]:
        """Выполнить анализ сложности содержимого файла"""
        lines_of_code = len([line for line in content.splitlines() if line.strip()])
        comment_lines = len([line for line in content.splitlines() if line.strip().startswith('#') or line.strip().startswith('//')])
        
        return {
            "lines_of_code": lines_of_code,
            "comment_lines": comment_lines,
            "comment_ratio": comment_lines / lines_of_code if lines_of_code > 0 else 0,
            "estimated_complexity_score": self._estimate_complexity_score(content)
        }
    
    async def _perform_dependency_analysis(self, content: str) -> List[Dict[str, Any]]:
        """Выполнить анализ зависимостей содержимого файла"""
        issues = []
        
        # Пример анализа зависимостей для Python
        import re
        import_keywords = ["import", "from"]
        for keyword in import_keywords:
            if keyword in content:
                # Найти все импорты
                import_matches = re.finditer(rf"\b{keyword}\s+([a-zA-Z0-9_.]+)", content)
                for match in import_matches:
                    module_name = match.group(1)
                    # Проверить, есть ли потенциальные проблемы с зависимостями
                    if any(bad_module in module_name.lower() for bad_module in ["os", "subprocess", "sys"]):
                        issues.append({
                            "type": "POTENTIALLY_DANGEROUS_IMPORT",
                            "severity": "MEDIUM",
                            "module": module_name,
                            "description": f"Обнаружено использование потенциально опасного модуля: {module_name}"
                        })
        
        return issues
    
    def _estimate_complexity_score(self, content: str) -> float:
        """Оценить оценку сложности кода"""
        # Простая метрика сложности: отношение строк кода к комментариям
        lines = content.splitlines()
        code_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('//')])
        comment_lines = len([line for line in lines if line.strip() and (line.strip().startswith('#') or line.strip().startswith('//'))])
        
        if code_lines == 0:
            return 0.0
        
        # Чем меньше комментариев на строку кода, тем сложнее код
        comment_density = comment_lines / code_lines
        return min(10.0, 5.0 + (5.0 * comment_density))  # Оценка от 0 до 10
```

## Интеграция компонентов

### 1. Фабрика специфических компонентов

Создайте фабрику для создания специфических компонентов:

```python
# application/factories/specialized_factory.py
from typing import Type, Dict, Any, List
from domain.abstractions.agent import IAgent
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.abstractions.tool import ITool
from application.agents.specialized_agents import SpecializedAgent
from application.patterns.specialized_patterns import SpecializedThinkingPattern
from infrastructure.tools.specialized_tools import SpecializedFileAnalyzerTool

class SpecializedComponentFactory:
    """Фабрика для создания специфических компонентов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._registered_agent_types = {}
        self._registered_pattern_types = {}
        self._registered_tool_types = {}
        
        # Зарегистрировать встроенные типы
        self._register_builtin_types()
    
    def _register_builtin_types(self):
        """Зарегистрировать встроенные типы компонентов"""
        self.register_agent_type("specialized", SpecializedAgent)
        self.register_pattern_type("specialized", SpecializedThinkingPattern)
        self.register_tool_type("file_analyzer", SpecializedFileAnalyzerTool)
        # Можно добавить другие встроенные типы
    
    def register_agent_type(self, name: str, agent_class: Type[IAgent]):
        """Зарегистрировать тип агента"""
        self._registered_agent_types[name] = agent_class
    
    def register_pattern_type(self, name: str, pattern_class: Type[IThinkingPattern]):
        """Зарегистрировать тип паттерна"""
        self._registered_pattern_types[name] = pattern_class
    
    def register_tool_type(self, name: str, tool_class: Type[ITool]):
        """Зарегистрировать тип инструмента"""
        self._registered_tool_types[name] = tool_class
    
    async def create_agent(self, agent_type: str, domain: DomainType, config: Dict[str, Any] = None) -> IAgent:
        """Создать специфический агент"""
        if agent_type not in self._registered_agent_types:
            raise ValueError(f"Тип агента '{agent_type}' не зарегистрирован")
        
        agent_class = self._registered_agent_types[agent_type]
        full_config = {**self.config.get("agent_defaults", {}), **(config or {})}
        
        agent = agent_class(domain, full_config)
        return agent
    
    async def create_pattern(self, pattern_type: str, config: Dict[str, Any] = None) -> IThinkingPattern:
        """Создать специфический паттерн"""
        if pattern_type not in self._registered_pattern_types:
            raise ValueError(f"Тип паттерна '{pattern_type}' не зарегистрирован")
        
        pattern_class = self._registered_pattern_types[pattern_type]
        full_config = {**self.config.get("pattern_defaults", {}), **(config or {})}
        
        pattern = pattern_class(full_config)
        return pattern
    
    async def create_tool(self, tool_type: str, config: Dict[str, Any] = None) -> ITool:
        """Создать специфический инструмент"""
        if tool_type not in self._registered_tool_types:
            raise ValueError(f"Тип инструмента '{tool_type}' не зарегистрирован")
        
        tool_class = self._registered_tool_types[tool_type]
        full_config = {**self.config.get("tool_defaults", {}), **(config or {})}
        
        tool = tool_class(full_config)
        return tool
    
    def get_available_agent_types(self) -> List[str]:
        """Получить доступные типы агентов"""
        return list(self._registered_agent_types.keys())
    
    def get_available_pattern_types(self) -> List[str]:
        """Получить доступные типы паттернов"""
        return list(self._registered_pattern_types.keys())
    
    def get_available_tool_types(self) -> List[str]:
        """Получить доступные типы инструментов"""
        return list(self._registered_tool_types.keys())

class AdvancedSpecializedFactory(SpecializedComponentFactory):
    """Расширенная фабрика с поддержкой сложных конфигураций"""
    
    def __init__(self, base_config: Dict[str, Any] = None):
        super().__init__(base_config)
        self._middleware_registry = {}
        self._validator_registry = {}
        self._enricher_registry = {}
    
    async def create_configurable_agent(
        self,
        agent_type: str,
        domain: DomainType,
        config: Dict[str, Any] = None,
        middleware: List[Callable] = None,
        validators: List[Callable] = None,
        enrichers: List[Callable] = None
    ) -> IAgent:
        """Создать настраиваемый агент с дополнительными компонентами"""
        
        # Создать базового агента
        agent = await self.create_agent(agent_type, domain, config)
        
        # Добавить middleware
        if middleware:
            for mw_func in middleware:
                if hasattr(agent, 'add_middleware'):
                    agent.add_middleware(mw_func)
        
        # Добавить валидаторы
        if validators:
            for validator_func in validators:
                if hasattr(agent, 'add_validator'):
                    agent.add_validator(validator_func)
        
        # Добавить enrichers
        if enrichers:
            for enricher_func in enrichers:
                if hasattr(agent, 'add_enricher'):
                    agent.add_enricher(enricher_func)
        
        return agent
    
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

### 2. Пример настройки под конкретную задачу

```python
# examples/custom_task_setup.py
from application.factories.advanced_specialized_factory import AdvancedSpecializedFactory
from domain.value_objects.domain_type import DomainType

async def setup_for_custom_task():
    """Пример настройки фреймворка под конкретную задачу"""
    
    # Создать расширенную фабрику
    factory = AdvancedSpecializedFactory({
        "agent_defaults": {
            "max_iterations": 100,
            "timeout": 600,
            "enable_logging": True
        },
        "pattern_defaults": {
            "execution_strategy": "adaptive",
            "resource_limits": {"memory": "1GB", "cpu": 50.0}
        },
        "tool_defaults": {
            "max_file_size": 10 * 1024 * 1024,  # 10MB
            "timeout": 30
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
    
    def resource_validation_validator(context):
        """Валидатор ограничений ресурсов"""
        if "resources" in context:
            resources = context["resources"]
            if resources.get("memory", 0) > 4 * 1024 * 1024 * 1024:  # 4GB
                raise ValueError("Превышено ограничение памяти")
        
        return True
    
    factory.register_middleware("security_enrichment", security_enrichment_middleware)
    factory.register_validator("resource_validation", resource_validation_validator)
    
    # Создать специфический агент для анализа безопасности кода
    security_agent = await factory.create_configurable_agent(
        "specialized",
        DomainType.SECURITY_ANALYSIS,
        config={
            "specialized_patterns": [
                {
                    "type": "security_analysis",
                    "parameters": {
                        "scan_depth": "deep",
                        "vulnerability_types": ["sql_injection", "xss", "csrf"]
                    }
                }
            ],
            "custom_tools": [
                {
                    "type": "file_analyzer",
                    "parameters": {
                        "max_file_size": 5 * 1024 * 1024,  # 5MB
                        "supported_formats": [".py", ".js", ".ts", ".java", ".cs"],
                        "analysis_types": ["security", "quality", "complexity"]
                    }
                }
            ],
            "resource_limits": {
                "max_memory": "2GB",
                "max_cpu_percentage": 75.0
            },
            "security_policy": {
                "enable_auditing": True,
                "restrict_file_access": True,
                "allowed_directories": ["./projects", "./src", "./tests"]
            }
        },
        middleware=[factory.get_registered_component("middleware", "security_enrichment")],
        validators=[factory.get_registered_component("validator", "resource_validation")]
    )
    
    # Создать специфический паттерн для анализа безопасности
    security_pattern = await factory.create_pattern(
        "specialized",
        config={
            "name": "custom_security_analysis_pattern",
            "required_tools": ["file_analyzer", "security_scanner"],
            "task_keywords": ["безопасность", "security", "vulnerability", "уязвимость"],
            "supported_domains": ["security_analysis", "code_analysis"]
        }
    )
    
    # Создать специфический инструмент для анализа файлов
    file_analyzer = await factory.create_tool(
        "file_analyzer",
        config={
            "max_file_size": 10 * 1024 * 1024,  # 10MB
            "supported_formats": [".py", ".js", ".ts", ".java", ".cs", ".cpp", ".c"],
            "analysis_types": ["security", "quality", "complexity", "dependencies"]
        }
    )
    
    # Зарегистрировать паттерн и инструмент в агенте
    security_agent.register_pattern(security_pattern)
    security_agent.register_tool(file_analyzer)
    
    # Подготовить задачу для выполнения
    task_context = {
        "code": """
def login(username, password):
    # Уязвимость: SQL-инъекция
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)

def execute_user_command(cmd):
    # Еще одна уязвимость: выполнение команд
    import subprocess
    result = subprocess.check_output(cmd, shell=True)
    return result
""",
        "language": "python",
        "analysis_requirements": {
            "focus_areas": ["input_validation", "command_execution", "sql_query"],
            "report_format": "detailed",
            "severity_threshold": "medium"
        }
    }
    
    # Выполнить задачу через специфический агент
    result = await security_agent.execute_task(
        task_description="Проанализируй этот Python код на наличие уязвимостей безопасности",
        context=task_context
    )
    
    print(f"Результат анализа безопасности: {result}")
    
    # Получить статистику использования компонентов
    if hasattr(security_agent, 'get_usage_stats'):
        stats = security_agent.get_usage_stats()
        print(f"Статистика использования: {stats}")
    
    return {
        "agent": security_agent,
        "pattern": security_pattern,
        "tool": file_analyzer,
        "result": result
    }

# Интеграция с существующей системой
async def integrate_with_existing_system():
    """Пример интеграции специфических компонентов с существующей системой"""
    
    # Создать специфические компоненты
    factory = AdvancedSpecializedFactory()
    
    # Создать специфический агент
    specialized_agent = await factory.create_agent(
        "specialized",
        DomainType.CUSTOM_DOMAIN,  # Использовать кастомный домен
        config={
            "custom_domain_config": {
                "api_endpoint": "https://custom-api.example.com",
                "auth_token": "${CUSTOM_API_TOKEN}",  # Будет загружен из env
                "custom_capabilities": ["custom_analysis", "proprietary_format_processing"]
            }
        }
    )
    
    # Создать фабрику агентов по умолчанию
    from application.factories.agent_factory import AgentFactory
    default_factory = AgentFactory()
    
    # Создать стандартного агента
    default_agent = await default_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Объединить функциональность (псевдокод - в реальной системе это будет зависеть от архитектуры)
    # specialized_agent.integrate_with_agent(default_agent)
    
    # Выполнить задачу, которая использует возможности обоих агентов
    result = await specialized_agent.execute_task(
        task_description="Выполни комплексный анализ с использованием специфических и стандартных возможностей",
        context={
            "data_source": "proprietary_format_file.dat",
            "analysis_types": ["custom", "standard_security", "standard_quality"],
            "output_format": "proprietary_report"
        }
    )
    
    print(f"Результат комплексного анализа: {result}")
    
    return result
```

## Лучшие практики настройки

### 1. Модульность и изоляция

Создавайте модульные компоненты, которые можно изолированно тестировать:

```python
# Хорошо: модульные компоненты
class BasePattern:
    """Базовый паттерн"""
    pass

class AnalysisPattern(BasePattern):
    """Паттерн анализа"""
    pass

class SecurityAnalysisPattern(AnalysisPattern):
    """Паттерн анализа безопасности"""
    pass

# Плохо: монолитный компонент
class MonolithicPattern:
    """Монолитный паттерн - сложно расширять и тестировать"""
    pass
```

### 2. Безопасность и валидация

Обязательно включайте проверки безопасности:

```python
def _validate_task_context(self, context: Dict[str, Any]) -> List[str]:
    """Проверить контекст задачи на безопасность"""
    errors = []
    
    # Проверить чувствительные поля
    sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
    for field in sensitive_fields:
        if field in context:
            errors.append(f"Чувствительное поле '{field}' обнаружено в контексте задачи")
    
    # Проверить размер контекста
    context_size = len(str(context))
    max_size = 10 * 1024 * 1024  # 10MB
    if context_size > max_size:
        errors.append(f"Контекст задачи слишком велик: {context_size} байт, максимум {max_size}")
    
    return errors
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Выполнить задачу с надежной обработкой ошибок"""
    try:
        # Проверить ограничения ресурсов
        if not await self._check_resource_availability():
            return {
                "success": False,
                "error": "Недостаточно ресурсов для выполнения задачи",
                "error_type": "resource_limit"
            }
        
        # Проверить безопасность задачи
        if not self._check_task_security(task_description, context):
            return {
                "success": False,
                "error": "Задача не соответствует политике безопасности",
                "error_type": "security_violation"
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
```

### 4. Тестирование специфических компонентов

Создавайте тесты для каждого специфического компонента:

```python
# test_custom_task_components.py
import pytest
from unittest.mock import AsyncMock, Mock
import tempfile
import os

class TestSpecializedAgent:
    @pytest.mark.asyncio
    async def test_specialized_agent_task_execution(self):
        """Тест выполнения задачи специфическим агентом"""
        
        # Создать специфический агент
        agent = SpecializedAgent(
            domain_type=DomainType.SECURITY_ANALYSIS,
            config={
                "specialized_patterns": [
                    {
                        "type": "security_analysis",
                        "parameters": {"scan_depth": "deep"}
                    }
                ]
            }
        )
        
        # Выполнить задачу
        result = await agent.execute_task(
            task_description="Проанализируй этот Python код на безопасность",
            context={
                "code": """
def vulnerable_login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
                "language": "python"
            }
        )
        
        # Проверить результат
        assert "success" in result
        assert result["success"] is True
        assert "pattern_used" in result
        # В зависимости от реализации, проверить другие поля результата

class TestSpecializedPattern:
    @pytest.mark.asyncio
    async def test_pattern_adaptation_to_task(self):
        """Тест адаптации паттерна к задаче"""
        
        pattern = SecurityAnalysisPattern({
            "task_keywords": ["безопасность", "security", "vulnerability"]
        })
        
        # Проверить, что паттерн может обработать задачу безопасности
        adaptation_result = await pattern.adapt_to_task("Проанализируй код на уязвимости безопасности")
        
        assert adaptation_result["can_handle"] is True
        assert adaptation_result["confidence_level"] > 0.5
        assert "security_analysis_pattern" in adaptation_result["pattern_name"]
    
    @pytest.mark.asyncio
    async def test_pattern_execution(self):
        """Тест выполнения специфического паттерна"""
        
        pattern = SecurityAnalysisPattern()
        
        result = await pattern.execute(
            state=AgentState(),
            context={
                "code": "def test(): pass",
                "language": "python"
            },
            available_capabilities=["code_reader", "ast_parser", "security_scanner"]
        )
        
        assert result["success"] is True
        assert "pattern_used" in result
        assert result["pattern_used"] == "security_analysis_pattern"

class TestSpecializedFileAnalyzerTool:
    @pytest.mark.asyncio
    async def test_file_analysis_success(self):
        """Тест успешного анализа файла"""
        
        tool = SpecializedFileAnalyzerTool({
            "max_file_size": 1024*1024,  # 1MB
            "supported_formats": [".py", ".txt"]
        })
        
        # Создать временный файл для теста
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("def hello(): pass")
            temp_file_path = f.name
        
        try:
            # Выполнить анализ файла
            result = await tool.execute({
                "file_path": temp_file_path,
                "analysis_types": ["security", "quality"]
            })
            
            # Проверить результат
            assert result["success"] is True
            assert "analysis_results" in result
            assert "file_info" in result
        finally:
            # Удалить временный файл
            os.unlink(temp_file_path)
    
    @pytest.mark.asyncio
    async def test_unsafe_path_rejection(self):
        """Тест отклонения небезопасного пути"""
        
        tool = SpecializedFileAnalyzerTool()
        
        # Попробовать проанализировать файл с небезопасным путем
        result = await tool.execute({
            "file_path": "../../../etc/passwd"  # Попытка выхода из корня проекта
        })
        
        # Проверить, что запрос был отклонен
        assert result["success"] is False
        assert "Небезопасный путь" in result["error"]
```

Это руководство поможет вам настроить Composable AI Agent Framework под ваши конкретные задачи, обеспечивая гибкость, безопасность и надежность системы.