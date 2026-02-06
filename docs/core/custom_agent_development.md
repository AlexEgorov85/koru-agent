# Разработка агентов под свои задачи

В этом разделе описаны рекомендации и практики по созданию и настройке агентов для специфических задач и требований. Вы узнаете, как адаптировать существующие агенты, создавать новые и интегрировать их с различными компонентами системы.

## Архитектура агентов

### 1. Интерфейс агента

Все агенты реализуют общий интерфейс:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from domain.models.agent.agent_state import AgentState

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
        self._state = initial_state or AgentState()
        self._initialized = False
    
    async def initialize(self):
        """Инициализировать агента"""
        self._initialized = True
    
    async def cleanup(self):
        """Очистить ресурсы агента"""
        self._initialized = False
```

### 2. Состояние агента

Состояние агента определяет его текущий статус и прогресс:

```python
from pydantic import BaseModel, field_validator
from typing import Dict, Any, List, Optional

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
```

## Создание специфических агентов

### 1. Планирование агента

Перед созданием нового агента важно определить его назначение и архитектуру:

#### Шаг 1: Определение области применения
- Какой домен задач?
- Какие типы задач будет решать?
- Какие инструменты и навыки будут использоваться?
- Какие паттерны мышления требуются?

#### Шаг 2: Определение архитектуры
- Какие компоненты будут интегрированы?
- Как будет происходить адаптация к задачам?
- Как будет управляться состояние?
- Как будет происходить восстановление после ошибок?

### 2. Пример создания специфического агента

**Пример агента для анализа кода:**

```python
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType
from application.services.prompt_loader import PromptLoader
from infrastructure.tools.file_reader_tool import FileReaderTool
from infrastructure.tools.ast_parser_tool import ASTParserTool
from infrastructure.tools.sql_tool import SQLTool
from application.orchestration.atomic_actions import AtomicActionExecutor

class CodeAnalysisAgent(BaseAgent):
    """Агент для анализа кода"""
    
    def __init__(
        self,
        domain_type: DomainType,
        prompt_loader: PromptLoader,
        file_reader: FileReaderTool,
        ast_parser: ASTParserTool,
        sql_tool: SQLTool,
        action_executor: AtomicActionExecutor
    ):
        super().__init__()
        self.domain_type = domain_type
        self.prompt_loader = prompt_loader
        self.file_reader = file_reader
        self.ast_parser = ast_parser
        self.sql_tool = sql_tool
        self.action_executor = action_executor
        self._capabilities = []
        self._loaded_prompts = {}
        
        # Зарегистрировать инструменты
        self.action_executor.register_action(file_reader)
        self.action_executor.register_action(ast_parser)
        self.action_executor.register_action(sql_tool)
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу анализа кода"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Обновить состояние
            self.state.step += 1
            
            # Определить тип задачи
            task_type = self._determine_task_type(task_description)
            
            if task_type == "code_analysis":
                return await self._execute_code_analysis_task(task_description, context)
            elif task_type == "security_analysis":
                return await self._execute_security_analysis_task(task_description, context)
            elif task_type == "code_review":
                return await self._execute_code_review_task(task_description, context)
            else:
                return await self._execute_general_analysis_task(task_description, context)
        except Exception as e:
            self.state.register_error()
            return {
                "success": False,
                "error": f"Ошибка при выполнении задачи: {str(e)}",
                "step": self.state.step
            }
    
    async def execute_atomic_action(self, action_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить атомарное действие"""
        try:
            result = await self.action_executor.execute_action(action_name, parameters)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении атомарного действия: {str(e)}"
            }
    
    async def execute_composable_pattern(self, pattern_name: str, context: Any) -> Dict[str, Any]:
        """Выполнить компонуемый паттерн"""
        # В реальной реализации здесь будет интеграция с паттернами мышления
        # Пока возвращаем заглушку
        return {
            "success": True,
            "pattern": pattern_name,
            "result": f"Выполнен паттерн {pattern_name} с контекстом {context}",
            "context": context
        }
    
    async def adapt_to_domain(self, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать агента к домену"""
        self.domain_type = domain_type
        self._capabilities = capabilities
        
        # Загрузить промты для домена
        await self._load_domain_prompts(domain_type, capabilities)
        
        return True
    
    def _determine_task_type(self, task_description: str) -> str:
        """Определить тип задачи по описанию"""
        task_lower = task_description.lower()
        
        if "анализ" in task_lower and ("кода" in task_lower or "code" in task_lower):
            return "code_analysis"
        elif "безопасность" in task_lower or "security" in task_lower or "уязвимость" in task_lower:
            return "security_analysis"
        elif "review" in task_lower or "ревью" in task_lower:
            return "code_review"
        else:
            return "general_analysis"
    
    async def _execute_code_analysis_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу анализа кода"""
        try:
            # Получить файл для анализа из контекста или описания
            file_path = context.get("file_path") if context else None
            
            if not file_path:
                # Попробовать извлечь путь к файлу из описания задачи
                file_path = self._extract_file_path(task_description)
            
            if file_path:
                # Прочитать файл
                read_result = await self.execute_atomic_action("file_reader", {"path": file_path})
                
                if not read_result["success"]:
                    return {
                        "success": False,
                        "error": f"Не удалось прочитать файл: {read_result['error']}",
                        "step": self.state.step
                    }
                
                code_content = read_result["content"]
                
                # Выполнить парсинг AST
                ast_result = await self.execute_atomic_action("ast_parser", {
                    "code": code_content,
                    "language": context.get("language", "python")
                })
                
                # Выполнить анализ с использованием подходящего промта
                analysis_result = await self._perform_code_analysis(code_content, ast_result, context)
                
                return {
                    "success": True,
                    "analysis_result": analysis_result,
                    "file_analyzed": file_path,
                    "step": self.state.step
                }
            else:
                return {
                    "success": False,
                    "error": "Не указан файл для анализа",
                    "step": self.state.step
                }
        except Exception as e:
            self.state.register_error()
            return {
                "success": False,
                "error": f"Ошибка при анализе кода: {str(e)}",
                "step": self.state.step
            }
    
    async def _execute_security_analysis_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу анализа безопасности"""
        # Реализация анализа безопасности
        # Включает проверку на уязвимости, анализ безопасности кода и т.д.
        pass
    
    async def _execute_code_review_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу ревью кода"""
        # Реализация ревью кода
        # Включает анализ качества кода, стиля, лучших практик и т.д.
        pass
    
    async def _execute_general_analysis_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить общую задачу анализа"""
        # Реализация общей задачи анализа
        # Может включать комбинацию различных подходов
        pass
    
    async def _perform_code_analysis(self, code_content: str, ast_result: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ кода"""
        # Использовать подходящий промт для анализа
        analysis_prompt = self._get_prompt_for_task("code_analysis", self.domain_type)
        
        if analysis_prompt:
            # Заменить переменные в промте
            rendered_prompt = self._render_prompt(analysis_prompt, {
                "code": code_content,
                "ast": str(ast_result),
                "task_description": context.get("task_description", "") if context else ""
            })
            
            # Вызвать LLM с промтом
            # В реальной реализации здесь будет вызов LLM
            analysis_result = {
                "summary": f"Анализ кода завершен. Размер: {len(code_content)} символов.",
                "findings": [],
                "recommendations": []
            }
            
            return analysis_result
        else:
            # Если нет подходящего промта, выполнить базовый анализ
            return {
                "summary": f"Базовый анализ кода завершен. Размер: {len(code_content)} символов.",
                "findings": [],
                "recommendations": []
            }
    
    def _get_prompt_for_task(self, task_type: str, domain: DomainType) -> Optional[str]:
        """Получить подходящий промт для задачи"""
        key = f"{domain.value}:{task_type}"
        return self._loaded_prompts.get(key)
    
    async def _load_domain_prompts(self, domain: DomainType, capabilities: List[str]):
        """Загрузить промты для домена"""
        all_prompts, errors = self.prompt_loader.load_all_prompts()
        
        for prompt in all_prompts:
            if prompt.domain == domain:
                key = f"{domain.value}:{prompt.capability_name}"
                self._loaded_prompts[key] = prompt.content
    
    def _render_prompt(self, prompt_template: str, variables: Dict[str, Any]) -> str:
        """Рендеринг промта с подстановкой переменных"""
        content = prompt_template
        
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            content = content.replace(placeholder, str(var_value))
        
        return content
    
    def _extract_file_path(self, task_description: str) -> Optional[str]:
        """Извлечь путь к файлу из описания задачи"""
        import re
        # Простой паттерн для извлечения пути к файлу
        # В реальной реализации может быть более сложным
        patterns = [
            r'файл\s+([^\s]+)',
            r'([^\s]+\.(?:py|js|ts|java|cs|php|rb|cpp|c))',
            r'"([^"]+\.(?:py|js|ts|java|cs|php|rb|cpp|c))"',
            r"'([^']+\.(?:py|js|ts|java|cs|php|rb|cpp|c))'"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, task_description, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
```

### 3. Пример создания агента для обработки данных

```python
class DataProcessingAgent(BaseAgent):
    """Агент для обработки данных"""
    
    def __init__(
        self,
        domain_type: DomainType,
        prompt_loader: PromptLoader,
        sql_tool: SQLTool,
        file_reader: FileReaderTool,
        action_executor: AtomicActionExecutor
    ):
        super().__init__()
        self.domain_type = domain_type
        self.prompt_loader = prompt_loader
        self.sql_tool = sql_tool
        self.file_reader = file_reader
        self.action_executor = action_executor
        self._capabilities = ["data_processing", "data_analysis", "sql_execution"]
        
        # Зарегистрировать инструменты
        self.action_executor.register_action(sql_tool)
        self.action_executor.register_action(file_reader)
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу обработки данных"""
        if not self._initialized:
            await self.initialize()
        
        try:
            self.state.step += 1
            
            # Определить тип задачи
            task_type = self._determine_task_type(task_description)
            
            if task_type == "sql_query":
                return await self._execute_sql_query_task(task_description, context)
            elif task_type == "data_analysis":
                return await self._execute_data_analysis_task(task_description, context)
            elif task_type == "data_transformation":
                return await self._execute_data_transformation_task(task_description, context)
            else:
                return await self._execute_general_data_task(task_description, context)
        except Exception as e:
            self.state.register_error()
            return {
                "success": False,
                "error": f"Ошибка при выполнении задачи: {str(e)}",
                "step": self.state.step
            }
    
    def _determine_task_type(self, task_description: str) -> str:
        """Определить тип задачи обработки данных"""
        task_lower = task_description.lower()
        
        if "sql" in task_lower or "запрос" in task_lower or "select" in task_lower:
            return "sql_query"
        elif "анализ" in task_lower and ("данны" in task_lower or "data" in task_lower):
            return "data_analysis"
        elif "преобраз" in task_lower or "трансформ" in task_lower:
            return "data_transformation"
        else:
            return "general_data_task"
    
    async def _execute_sql_query_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу SQL-запроса"""
        try:
            # Извлечь SQL-запрос из описания или контекста
            sql_query = context.get("query") if context else None
            
            if not sql_query:
                sql_query = self._extract_sql_query(task_description)
            
            if sql_query:
                # Выполнить SQL-запрос
                query_result = await self.execute_atomic_action("sql_tool", {"query": sql_query})
                
                if not query_result["success"]:
                    return {
                        "success": False,
                        "error": f"Ошибка выполнения SQL-запроса: {query_result['error']}",
                        "step": self.state.step
                    }
                
                return {
                    "success": True,
                    "query_results": query_result["results"],
                    "row_count": query_result["row_count"],
                    "step": self.state.step
                }
            else:
                return {
                    "success": False,
                    "error": "Не удалось извлечь SQL-запрос",
                    "step": self.state.step
                }
        except Exception as e:
            self.state.register_error()
            return {
                "success": False,
                "error": f"Ошибка при выполнении SQL-запроса: {str(e)}",
                "step": self.state.step
            }
    
    async def _execute_data_analysis_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу анализа данных"""
        # Реализация анализа данных
        # Может включать статистический анализ, визуализацию и т.д.
        pass
    
    async def _execute_data_transformation_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить задачу трансформации данных"""
        # Реализация трансформации данных
        # Может включать очистку, нормализацию, преобразование форматов и т.д.
        pass
    
    async def _execute_general_data_task(self, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить общую задачу обработки данных"""
        # Реализация общей задачи обработки данных
        # Может включать комбинацию различных подходов
        pass
    
    def _extract_sql_query(self, task_description: str) -> Optional[str]:
        """Извлечь SQL-запрос из описания задачи"""
        import re
        
        # Попытаться найти SQL-запрос в описании
        # Ищем выражения, начинающиеся с SELECT, INSERT, UPDATE, DELETE
        patterns = [
            r'(SELECT.*?;?)',
            r'(INSERT.*?;?)',
            r'(UPDATE.*?;?)',
            r'(DELETE.*?;?)',
            r'`(SELECT.*?;?)`',  # Заключенные в обратные кавычки
            r'"(SELECT.*?)"',    # Заключенные в кавычки
        ]
        
        for pattern in patterns:
            match = re.search(pattern, task_description, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
```

## Интеграция агентов с системой

### 1. Регистрация агентов

Для интеграции агентов в систему:

```python
# agent_registration.py
from application.factories.agent_factory import AgentFactory
from infrastructure.services.prompt_loader import PromptLoader
from infrastructure.tools.file_reader_tool import FileReaderTool
from infrastructure.tools.ast_parser_tool import ASTParserTool
from infrastructure.tools.sql_tool import SQLTool
from application.orchestration.atomic_actions import AtomicActionExecutor

class AgentRegistrationService:
    """Сервис регистрации агентов"""
    
    def __init__(self):
        self.agents = {}
    
    async def register_code_analysis_agent(self):
        """Зарегистрировать агента анализа кода"""
        # Создать зависимости
        prompt_loader = PromptLoader(base_path="./prompts")
        file_reader = FileReaderTool()
        ast_parser = ASTParserTool()
        sql_tool = SQLTool(connection_string="sqlite:///example.db")
        action_executor = AtomicActionExecutor()
        
        # Создать агента
        agent = CodeAnalysisAgent(
            domain_type=DomainType.CODE_ANALYSIS,
            prompt_loader=prompt_loader,
            file_reader=file_reader,
            ast_parser=ast_parser,
            sql_tool=sql_tool,
            action_executor=action_executor
        )
        
        # Инициализировать агента
        await agent.initialize()
        
        # Зарегистрировать агента
        self.agents["code_analysis"] = agent
        
        return agent
    
    async def register_data_processing_agent(self):
        """Зарегистрировать агента обработки данных"""
        # Создать зависимости
        prompt_loader = PromptLoader(base_path="./prompts")
        sql_tool = SQLTool(connection_string="sqlite:///data.db")
        file_reader = FileReaderTool()
        action_executor = AtomicActionExecutor()
        
        # Создать агента
        agent = DataProcessingAgent(
            domain_type=DomainType.DATA_PROCESSING,
            prompt_loader=prompt_loader,
            sql_tool=sql_tool,
            file_reader=file_reader,
            action_executor=action_executor
        )
        
        # Инициализировать агента
        await agent.initialize()
        
        # Зарегистрировать агента
        self.agents["data_processing"] = agent
        
        return agent
    
    def get_agent(self, agent_name: str):
        """Получить зарегистрированный агент"""
        return self.agents.get(agent_name)
```

### 2. Использование агентов

Пример использования специфических агентов:

```python
# agent_usage_example.py
from domain.value_objects.domain_type import DomainType

async def code_analysis_example():
    """Пример использования агента анализа кода"""
    
    # Создать сервис регистрации
    registration_service = AgentRegistrationService()
    
    # Зарегистрировать агента анализа кода
    agent = await registration_service.register_code_analysis_agent()
    
    # Выполнить задачу анализа кода
    task_result = await agent.execute_task(
        task_description="Проанализируй файл ./src/main.py на наличие уязвимостей безопасности",
        context={
            "file_path": "./src/main.py",
            "language": "python",
            "analysis_type": "security"
        }
    )
    
    print("Результат анализа кода:")
    print(task_result)
    
    return task_result

async def data_processing_example():
    """Пример использования агента обработки данных"""
    
    # Создать сервис регистрации
    registration_service = AgentRegistrationService()
    
    # Зарегистрировать агента обработки данных
    agent = await registration_service.register_data_processing_agent()
    
    # Выполнить задачу SQL-запроса
    task_result = await agent.execute_task(
        task_description="Получи последние 10 записей из таблицы users",
        context={
            "query": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10"
        }
    )
    
    print("Результат SQL-запроса:")
    print(task_result)
    
    return task_result

# Использование агента через фабрику
async def factory_usage_example():
    """Пример использования агента через фабрику"""
    
    # Создать фабрику агентов
    agent_factory = AgentFactory()
    
    # Создать агента для домена анализа кода
    agent = await agent_factory.create_agent(
        agent_type="code_analysis",  # Тип специфического агента
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Выполнить задачу
    result = await agent.execute_task(
        task_description="Проанализируй этот Python код на качество и безопасность",
        context={
            "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
            "language": "python"
        }
    )
    
    print("Результат выполнения через фабрику:")
    print(result)
    
    return result
```

## Адаптация существующих агентов

### 1. Расширение существующего агента

Для адаптации существующего агента под специфические нужды:

```python
class ExtendedCodeAnalysisAgent(CodeAnalysisAgent):
    """Расширенный агент анализа кода с дополнительными возможностями"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_rules = []
        self.security_scanners = []
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Расширенное выполнение задачи с дополнительными проверками"""
        
        # Вызов базовой реализации
        base_result = await super().execute_task(task_description, context)
        
        if base_result["success"] and "analysis_result" in base_result:
            # Применить пользовательские правила
            extended_result = await self._apply_custom_rules(
                base_result["analysis_result"], 
                context
            )
            
            base_result["analysis_result"] = extended_result
        
        return base_result
    
    async def _apply_custom_rules(self, analysis_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Применить пользовательские правила к результату анализа"""
        if not self.custom_rules:
            return analysis_result
        
        # Применить каждое правило
        for rule in self.custom_rules:
            analysis_result = await rule.apply(analysis_result, context)
        
        return analysis_result
    
    def add_custom_rule(self, rule):
        """Добавить пользовательское правило анализа"""
        self.custom_rules.append(rule)
    
    def add_security_scanner(self, scanner):
        """Добавить сканер безопасности"""
        self.security_scanners.append(scanner)
```

### 2. Композиция агентов

Создание агентов, которые объединяют функциональность нескольких агентов:

```python
class CompositeAgent(BaseAgent):
    """Композитный агент, объединяющий функциональность нескольких агентов"""
    
    def __init__(self, agents: List[IAgent]):
        super().__init__()
        self.agents = agents
        self._agent_routing_rules = {}
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу, направив её подходящему агенту"""
        
        # Определить, какой агент должен выполнить задачу
        target_agent = self._route_task_to_agent(task_description)
        
        if target_agent:
            # Выполнить задачу через целевой агент
            result = await target_agent.execute_task(task_description, context)
            
            # Обновить состояние композитного агента
            self.state.step += 1
            if not result.get("success", True):
                self.state.register_error()
            
            return result
        else:
            return {
                "success": False,
                "error": "Не найден подходящий агент для выполнения задачи",
                "step": self.state.step
            }
    
    def _route_task_to_agent(self, task_description: str) -> Optional[IAgent]:
        """Определить, какой агент должен выполнить задачу"""
        task_lower = task_description.lower()
        
        # Проверить правила маршрутизации
        for pattern, agent in self._agent_routing_rules.items():
            if pattern.lower() in task_lower:
                return agent
        
        # Если нет точного соответствия, использовать эвристику
        if any(word in task_lower for word in ["код", "code", "анализ", "security", "уязвим"]):
            # Найти агента для анализа кода
            for agent in self.agents:
                if hasattr(agent, 'domain_type') and agent.domain_type == DomainType.CODE_ANALYSIS:
                    return agent
        
        if any(word in task_lower for word in ["данны", "data", "sql", "запрос", "таблиц"]):
            # Найти агента для обработки данных
            for agent in self.agents:
                if hasattr(agent, 'domain_type') and agent.domain_type == DomainType.DATA_PROCESSING:
                    return agent
        
        # По умолчанию вернуть первый агент
        return self.agents[0] if self.agents else None
    
    def add_routing_rule(self, pattern: str, agent: IAgent):
        """Добавить правило маршрутизации задач"""
        self._agent_routing_rules[pattern] = agent
```

## Лучшие практики

### 1. Модульность и переиспользуемость

Создавайте агентов, которые можно легко комбинировать:

```python
# Хорошо: модульные компоненты
class DataExtractorAgent(BaseAgent):
    """Агент для извлечения данных"""
    pass

class DataTransformerAgent(BaseAgent):
    """Агент для преобразования данных"""
    pass

class DataAnalyzerAgent(BaseAgent):
    """Агент анализа данных, использующий другие агенты"""
    pass

# Плохо: монолитный компонент
class AllInOneDataProcessorAgent(BaseAgent):
    """Агент, делающий всё сразу - сложно тестировать и поддерживать"""
    pass
```

### 2. Управление состоянием

Обязательно учитывайте состояние агента:

```python
class StatefulAgent(BaseAgent):
    """Агент с управляемым состоянием"""
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу с управлением состоянием"""
        
        # Обновить состояние перед выполнением
        self.state.step += 1
        self.state.current_plan_step = task_description[:50]  # Первые 50 символов задачи
        
        try:
            # Выполнить основную логику
            result = await self._execute_core_logic(task_description, context)
            
            # Обновить состояние при успехе
            self.state.register_progress(progressed=True)
            
            return {"success": True, **result}
        except Exception as e:
            # Обновить состояние при ошибке
            self.state.register_error()
            self.state.register_progress(progressed=False)
            
            return {
                "success": False,
                "error": str(e),
                "step": self.state.step
            }
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Выполнить задачу с надежной обработкой ошибок"""
    try:
        # Проверить состояние агента
        if self.state.finished:
            return {
                "success": False,
                "error": "Агент завершил выполнение",
                "completed": True
            }
        
        # Проверить количество ошибок
        if self.state.error_count > self.max_allowed_errors:
            self.state.complete()
            return {
                "success": False,
                "error": f"Превышено максимальное количество ошибок ({self.max_allowed_errors})",
                "terminated": True
            }
        
        # Проверить количество шагов без прогресса
        if self.state.no_progress_steps > self.max_no_progress_steps:
            return {
                "success": False,
                "error": f"Превышено максимальное количество шагов без прогресса ({self.max_no_progress_steps})",
                "needs_intervention": True
            }
        
        # Основная логика выполнения
        result = await self._execute_main_logic(task_description, context)
        return {"success": True, **result}
    except ValidationError as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Ошибка валидации: {str(e)}",
            "error_type": "validation_error"
        }
    except SecurityError as e:
        self.state.register_error()
        self.state.complete()  # Критическая ошибка безопасности
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security_error",
            "terminated": True
        }
    except Exception as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal_error"
        }
```

### 4. Тестирование агентов

Создавайте тесты для каждого агента:

```python
# test_custom_agents.py
import pytest
from unittest.mock import AsyncMock, Mock
import tempfile
import os

class TestCodeAnalysisAgent:
    @pytest.mark.asyncio
    async def test_code_analysis_success(self):
        """Тест успешного анализа кода"""
        # Создание моков зависимостей
        mock_prompt_loader = AsyncMock()
        mock_file_reader = AsyncMock()
        mock_ast_parser = AsyncMock()
        mock_sql_tool = AsyncMock()
        mock_action_executor = AsyncMock()
        
        # Настройка возвращаемых значений
        mock_file_reader.execute.return_value = {
            "success": True,
            "content": "def hello(): pass"
        }
        mock_ast_parser.execute.return_value = {"nodes": []}
        
        # Создание агента
        agent = CodeAnalysisAgent(
            domain_type=DomainType.CODE_ANALYSIS,
            prompt_loader=mock_prompt_loader,
            file_reader=mock_file_reader,
            ast_parser=mock_ast_parser,
            sql_tool=mock_sql_tool,
            action_executor=mock_action_executor
        )
        
        # Выполнение задачи
        result = await agent.execute_task(
            task_description="Проанализируй файл test.py",
            context={"file_path": "test.py"}
        )
        
        # Проверка результата
        assert result["success"] is True
        assert "analysis_result" in result
        assert result["file_analyzed"] == "test.py"
    
    @pytest.mark.asyncio
    async def test_code_analysis_file_not_found(self):
        """Тест обработки ошибки отсутствия файла"""
        # Создание моков зависимостей
        mock_prompt_loader = AsyncMock()
        mock_file_reader = AsyncMock()
        mock_ast_parser = AsyncMock()
        mock_sql_tool = AsyncMock()
        mock_action_executor = AsyncMock()
        
        # Настройка возвращаемых значений для ошибки
        mock_file_reader.execute.return_value = {
            "success": False,
            "error": "File not found"
        }
        
        # Создание агента
        agent = CodeAnalysisAgent(
            domain_type=DomainType.CODE_ANALYSIS,
            prompt_loader=mock_prompt_loader,
            file_reader=mock_file_reader,
            ast_parser=mock_ast_parser,
            sql_tool=mock_sql_tool,
            action_executor=mock_action_executor
        )
        
        # Выполнение задачи
        result = await agent.execute_task(
            task_description="Проанализируй файл nonexistent.py",
            context={"file_path": "nonexistent.py"}
        )
        
        # Проверка результата
        assert result["success"] is False
        assert "File not found" in result["error"]

class TestDataProcessingAgent:
    @pytest.mark.asyncio
    async def test_sql_query_execution(self):
        """Тест выполнения SQL-запроса"""
        # Создание моков зависимостей
        mock_prompt_loader = AsyncMock()
        mock_sql_tool = AsyncMock()
        mock_file_reader = AsyncMock()
        mock_action_executor = AsyncMock()
        
        # Настройка возвращаемых значений
        mock_sql_tool.execute.return_value = {
            "success": True,
            "results": [{"id": 1, "name": "test"}],
            "row_count": 1
        }
        
        # Создание агента
        agent = DataProcessingAgent(
            domain_type=DomainType.DATA_PROCESSING,
            prompt_loader=mock_prompt_loader,
            sql_tool=mock_sql_tool,
            file_reader=mock_file_reader,
            action_executor=mock_action_executor
        )
        
        # Выполнение задачи
        result = await agent.execute_task(
            task_description="Получи данные из таблицы users",
            context={"query": "SELECT * FROM users LIMIT 1"}
        )
        
        # Проверка результата
        assert result["success"] is True
        assert len(result["query_results"]) == 1
        assert result["row_count"] == 1
```

Эти примеры показывают, как создавать и адаптировать агентов под специфические задачи, обеспечивая модульность, безопасность и надежность системы.