# Создание навыков (Skills)

Навыки (Skills) в Koru AI Agent Framework представляют собой более высокоуровневые абстракции, чем инструменты. Они могут комбинировать несколько инструментов и атомарных действий для выполнения сложных задач. В этом разделе описан процесс создания и интеграции пользовательских навыков.

## Архитектура навыков

### 1. Интерфейс навыка

Все навыки реализуют общий интерфейс:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class SkillMetadata(BaseModel):
    """Метаданные навыка"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    category: str
    version: str = "1.0.0"
    required_tools: list = []

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
    
    async def initialize(self):
        """Инициализировать навык"""
        self._is_initialized = True
    
    async def cleanup(self):
        """Очистить ресурсы навыка"""
        self._is_initialized = False
```

### 2. Фабрика навыков

Фабрика для создания экземпляров навыков:

```python
from infrastructure.factories.skill_factory import SkillFactory

class SkillFactory:
    """Фабрика для создания навыков"""
    
    def __init__(self):
        self.skill_classes = {}
    
    def register_skill_class(self, name: str, skill_class: type):
        """Зарегистрировать класс навыка"""
        self.skill_classes[name] = skill_class
    
    async def create_skill(self, name: str, **kwargs) -> ISkill:
        """Создать экземпляр навыка"""
        if name not in self.skill_classes:
            raise ValueError(f"Навык {name} не зарегистрирован")
        
        skill_class = self.skill_classes[name]
        skill_instance = skill_class(**kwargs)
        await skill_instance.initialize()
        
        return skill_instance
```

## Создание пользовательских навыков

### 1. Простой навык анализа кода

```python
class CodeAnalysisSkill(BaseSkill):
    """Навык анализа кода"""
    
    def __init__(self, file_reader_tool, ast_parser_tool, security_checker_tool):
        super().__init__()
        self.file_reader = file_reader_tool
        self.ast_parser = ast_parser_tool
        self.security_checker = security_checker_tool
        self._required_tools = [file_reader_tool, ast_parser_tool, security_checker_tool]
    
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="code_analysis_skill",
            description="Анализирует код на наличие уязвимостей и проблем качества",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу для анализа"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["security", "quality", "both"],
                        "default": "both",
                        "description": "Тип анализа для выполнения"
                    }
                },
                "required": ["file_path"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "severity": {"type": "string"},
                                "description": {"type": "string"},
                                "line_number": {"type": "integer"}
                            }
                        }
                    },
                    "summary": {"type": "string"},
                    "error": {"type": "string"}
                }
            },
            category="code_analysis",
            required_tools=["file_reader", "ast_parser", "security_checker"]
        )
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ кода"""
        if not self.validate_context(context):
            return {
                "success": False,
                "error": "Некорректный контекст выполнения"
            }
        
        file_path = context["file_path"]
        analysis_type = context.get("analysis_type", "both")
        
        try:
            # Шаг 1: Чтение файла
            read_result = await self.file_reader.execute({"path": file_path})
            if not read_result["success"]:
                return {
                    "success": False,
                    "error": f"Не удалось прочитать файл: {read_result['error']}"
                }
            
            code_content = read_result["content"]
            
            # Шаг 2: Парсинг AST
            ast_result = await self.ast_parser.execute({
                "code": code_content,
                "language": context.get("language", "python")
            })
            
            # Шаг 3: Анализ безопасности (если требуется)
            security_findings = []
            if analysis_type in ["security", "both"]:
                security_result = await self.security_checker.execute({
                    "code": code_content,
                    "ast": ast_result
                })
                security_findings = security_result.get("findings", [])
            
            # Шаг 4: Анализ качества (если требуется)
            quality_findings = []
            if analysis_type in ["quality", "both"]:
                # Здесь мог бы быть вызов инструмента анализа качества кода
                quality_findings = self._analyze_code_quality(code_content)
            
            # Объединение результатов
            all_findings = security_findings + quality_findings
            
            return {
                "success": True,
                "findings": all_findings,
                "summary": self._generate_summary(all_findings),
                "total_findings": len(all_findings),
                "security_findings": len(security_findings),
                "quality_findings": len(quality_findings)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении анализа: {str(e)}"
            }
    
    def validate_context(self, context: Dict[str, Any]) -> bool:
        """Проверить контекст выполнения"""
        return "file_path" in context and isinstance(context["file_path"], str)
    
    def _analyze_code_quality(self, code: str) -> list:
        """Анализ качества кода (внутренняя реализация)"""
        # Реализация анализа качества кода
        # Возвращает список проблем с качеством
        return []
    
    def _generate_summary(self, findings: list) -> str:
        """Генерация сводки по результатам анализа"""
        if not findings:
            return "Анализ не выявил проблем в коде."
        
        high_severity = len([f for f in findings if f.get("severity") == "HIGH"])
        medium_severity = len([f for f in findings if f.get("severity") == "MEDIUM"])
        low_severity = len([f for f in findings if f.get("severity") == "LOW"])
        
        return f"Найдено проблем: {len(findings)} (Высокий приоритет: {high_severity}, Средний: {medium_severity}, Низкий: {low_severity})"
```

### 2. Навык обработки данных

```python
class DataProcessingSkill(BaseSkill):
    """Навык обработки данных"""
    
    def __init__(self, file_reader_tool, sql_tool, data_validator_tool):
        super().__init__()
        self.file_reader = file_reader_tool
        self.sql_tool = sql_tool
        self.data_validator = data_validator_tool
        self._required_tools = [file_reader_tool, sql_tool, data_validator_tool]
    
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="data_processing_skill",
            description="Обрабатывает и анализирует данные из различных источников",
            input_schema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["file", "database", "api"],
                        "description": "Источник данных"
                    },
                    "source_config": {
                        "type": "object",
                        "description": "Конфигурация источника данных"
                    },
                    "processing_type": {
                        "type": "string",
                        "enum": ["clean", "transform", "validate", "analyze"],
                        "default": "validate",
                        "description": "Тип обработки данных"
                    }
                },
                "required": ["source", "source_config"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "processed_data": {"type": "array"},
                    "validation_results": {"type": "object"},
                    "statistics": {"type": "object"},
                    "error": {"type": "string"}
                }
            },
            category="data_processing",
            required_tools=["file_reader", "sql_tool", "data_validator"]
        )
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить обработку данных"""
        if not self.validate_context(context):
            return {
                "success": False,
                "error": "Некорректный контекст выполнения"
            }
        
        source = context["source"]
        processing_type = context.get("processing_type", "validate")
        
        try:
            # Получение данных из источника
            data = await self._fetch_data(source, context["source_config"])
            
            if processing_type == "clean":
                processed_data = await self._clean_data(data)
            elif processing_type == "transform":
                processed_data = await self._transform_data(data, context.get("transform_config", {}))
            elif processing_type == "analyze":
                processed_data = await self._analyze_data(data)
            else:  # validate
                processed_data = data
            
            # Валидация данных
            validation_results = await self.data_validator.execute({
                "data": processed_data,
                "rules": context.get("validation_rules", {})
            })
            
            # Статистика
            statistics = self._calculate_statistics(processed_data)
            
            return {
                "success": True,
                "processed_data": processed_data,
                "validation_results": validation_results,
                "statistics": statistics
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при обработке данных: {str(e)}"
            }
    
    async def _fetch_data(self, source: str, config: Dict[str, Any]):
        """Получить данные из источника"""
        if source == "file":
            result = await self.file_reader.execute({"path": config["path"]})
            if result["success"]:
                # Предполагаем, что данные в формате CSV/JSON
                import json
                return json.loads(result["content"])
        elif source == "database":
            result = await self.sql_tool.execute({"query": config["query"]})
            if result["success"]:
                return result["results"]
        
        raise ValueError(f"Не поддерживаемый источник данных: {source}")
    
    async def _clean_data(self, data: list) -> list:
        """Очистка данных"""
        # Реализация очистки данных
        return data
    
    async def _transform_data(self, data: list, transform_config: Dict[str, Any]) -> list:
        """Трансформация данных"""
        # Реализация трансформации данных
        return data
    
    async def _analyze_data(self, data: list) -> list:
        """Анализ данных"""
        # Реализация анализа данных
        return data
    
    def _calculate_statistics(self, data: list) -> dict:
        """Расчет статистики по данным"""
        return {
            "total_records": len(data),
            "fields_count": len(data[0]) if data else 0,
            "null_values": sum(1 for record in data for value in record.values() if value is None)
        }
    
    def validate_context(self, context: Dict[str, Any]) -> bool:
        """Проверить контекст выполнения"""
        required_fields = ["source", "source_config"]
        return all(field in context for field in required_fields)
```

## Интеграция навыков с агентами

### 1. Регистрация навыков

```python
# skills_registration.py
from infrastructure.factories.skill_factory import SkillFactory
from infrastructure.tools.file_reader_tool import FileReaderTool
from infrastructure.tools.ast_parser_tool import ASTParserTool
from infrastructure.tools.sql_tool import SQLTool

async def register_agent_skills():
    """Регистрация навыков для агентов"""
    
    # Создание фабрики навыков
    skill_factory = SkillFactory()
    
    # Создание инструментов
    file_reader = FileReaderTool()
    ast_parser = ASTParserTool()
    sql_tool = SQLTool(connection_string="sqlite:///example.db")
    # Допустим, есть и другие инструменты...
    
    # Регистрация классов навыков
    skill_factory.register_skill_class("code_analysis", CodeAnalysisSkill)
    skill_factory.register_skill_class("data_processing", DataProcessingSkill)
    
    # Создание экземпляров навыков с зависимыми инструментами
    code_analysis_skill = await skill_factory.create_skill(
        "code_analysis",
        file_reader_tool=file_reader,
        ast_parser_tool=ast_parser,
        security_checker_tool=None  # Можно передать реальный инструмент проверки безопасности
    )
    
    data_processing_skill = await skill_factory.create_skill(
        "data_processing",
        file_reader_tool=file_reader,
        sql_tool=sql_tool,
        data_validator_tool=None  # Можно передать реальный инструмент валидации
    )
    
    return {
        "code_analysis": code_analysis_skill,
        "data_processing": data_processing_skill
    }
```

### 2. Использование навыков в агентах

```python
# agent_with_skills.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

class SkilledAgent:
    """Агент с поддержкой навыков"""
    
    def __init__(self, agent, skills_dict):
        self.agent = agent
        self.skills = skills_dict
    
    async def execute_skill(self, skill_name: str, context: Dict[str, Any]):
        """Выполнить навык через агента"""
        if skill_name not in self.skills:
            raise ValueError(f"Навык {skill_name} не доступен")
        
        skill = self.skills[skill_name]
        result = await skill.execute(context)
        
        return result
    
    async def execute_task_with_skill(self, task_description: str, skill_name: str, skill_context: Dict[str, Any]):
        """Выполнить задачу с использованием навыка"""
        # Сначала выполнить навык
        skill_result = await self.execute_skill(skill_name, skill_context)
        
        if not skill_result["success"]:
            return skill_result
        
        # Затем передать результат в агент для дальнейшей обработки
        enhanced_context = {
            "original_task": task_description,
            "skill_result": skill_result
        }
        
        agent_result = await self.agent.execute_task(
            task_description=f"{task_description} с учетом результатов навыка {skill_name}",
            context=enhanced_context
        )
        
        return {
            "skill_result": skill_result,
            "agent_result": agent_result
        }

# Пример использования
async def skilled_agent_example():
    """Пример использования агента с навыками"""
    
    # Создание агента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Регистрация навыков
    skills = await register_agent_skills()
    
    # Создание агента с навыками
    skilled_agent = SkilledAgent(agent, skills)
    
    # Выполнение задачи с использованием навыка анализа кода
    result = await skilled_agent.execute_task_with_skill(
        task_description="Проанализируй этот Python файл на уязвимости",
        skill_name="code_analysis",
        skill_context={
            "file_path": "./src/example.py",
            "analysis_type": "security",
            "language": "python"
        }
    )
    
    print(f"Результат выполнения: {result}")
    
    return result
```

## Лучшие практики создания навыков

### 1. Модульность

Создавайте навыки, которые выполняют одну конкретную задачу:

```python
# Плохо: навык делает слишком много
class AllInOneSkill(BaseSkill):
    # Выполняет анализ кода, обработку данных и генерацию отчетов
    pass

# Хорошо: каждый навык решает конкретную задачу
class CodeAnalysisSkill(BaseSkill):
    # Только анализ кода
    pass

class DataProcessingSkill(BaseSkill):
    # Только обработка данных
    pass
```

### 2. Валидация контекста

Обязательно проверяйте входные данные:

```python
def validate_context(self, context: Dict[str, Any]) -> bool:
    """Проверить контекст выполнения"""
    required_fields = ["file_path"]
    if not all(field in context for field in required_fields):
        return False
    
    # Дополнительные проверки
    if "file_path" in context and not isinstance(context["file_path"], str):
        return False
    
    return True
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """Выполнить навык с обработкой ошибок"""
    try:
        # Основная логика выполнения
        result = await self._execute_main_logic(context)
        return {"success": True, **result}
    except ValidationError as e:
        return {
            "success": False,
            "error": f"Ошибка валидации: {str(e)}"
        }
    except ExternalServiceError as e:
        return {
            "success": False,
            "error": f"Ошибка внешнего сервиса: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Неожиданная ошибка: {str(e)}"
        }
```

### 4. Тестирование навыков

Создавайте тесты для каждого навыка:

```python
# test_skills.py
import pytest
from unittest.mock import AsyncMock

class TestCodeAnalysisSkill:
    @pytest.mark.asyncio
    async def test_code_analysis_success(self):
        """Тест успешного выполнения анализа кода"""
        # Создание моков инструментов
        mock_file_reader = AsyncMock()
        mock_file_reader.execute.return_value = {
            "success": True,
            "content": "def hello(): pass"
        }
        
        mock_ast_parser = AsyncMock()
        mock_ast_parser.execute.return_value = {"nodes": []}
        
        mock_security_checker = AsyncMock()
        mock_security_checker.execute.return_value = {"findings": []}
        
        # Создание навыка
        skill = CodeAnalysisSkill(mock_file_reader, mock_ast_parser, mock_security_checker)
        
        # Выполнение навыка
        context = {"file_path": "test.py"}
        result = await skill.execute(context)
        
        # Проверка результата
        assert result["success"] is True
        assert "findings" in result
        assert "summary" in result
    
    @pytest.mark.asyncio
    async def test_code_analysis_file_not_found(self):
        """Тест обработки ошибки отсутствия файла"""
        # Создание моков инструментов
        mock_file_reader = AsyncMock()
        mock_file_reader.execute.return_value = {
            "success": False,
            "error": "File not found"
        }
        
        # Остальные моки...
        
        skill = CodeAnalysisSkill(mock_file_reader, AsyncMock(), AsyncMock())
        
        context = {"file_path": "nonexistent.py"}
        result = await skill.execute(context)
        
        assert result["success"] is False
        assert "File not found" in result["error"]
```

## Интеграция с системой

### 1. Регистрация в системе

Навыки должны быть зарегистрированы в системе для использования:

```python
# system_initialization.py
from application.services.system_initialization_service import SystemInitializationService

class SkillRegistrationService(SystemInitializationService):
    """Сервис регистрации навыков в системе"""
    
    async def initialize_skills(self):
        """Инициализировать и зарегистрировать навыки"""
        skills = await register_agent_skills()
        
        # Здесь может быть логика регистрации навыков в центральном реестре
        for skill_name, skill_instance in skills.items():
            self.system_registry.register_skill(skill_name, skill_instance)
        
        print(f"Зарегистрировано {len(skills)} навыков")
```

### 2. Мониторинг и логирование

Система должна логировать использование навыков:

```python
import logging

class SkillWithLogging(BaseSkill):
    """Навык с логированием"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.metadata.name)
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить навык с логированием"""
        self.logger.info(f"Executing skill with context keys: {list(context.keys())}")
        
        start_time = time.time()
        result = await super().execute(context)
        execution_time = time.time() - start_time
        
        self.logger.info(f"Skill execution completed in {execution_time:.2f}s")
        self.logger.info(f"Result success: {result.get('success', False)}")
        
        return result
```

Эти примеры показывают, как создавать и интегрировать пользовательские навыки в Koru AI Agent Framework, обеспечивая расширяемость и гибкость системы.