# Валидация промтов

Валидация промтов в Composable AI Agent Framework обеспечивает корректность, безопасность и согласованность использования промтов в системе. Система валидации проверяет как структурные, так и логические аспекты промтов, гарантируя их корректную работу в различных сценариях использования.

## Цели валидации

Валидация промтов направлена на обеспечение:

1. **Корректности структуры**: Проверка соответствия формату и структуре
2. **Безопасности**: Предотвращение потенциально опасного содержимого
3. **Согласованности**: Обеспечение единообразия и логической целостности
4. **Совместимости**: Проверка соответствия требованиям LLM провайдеров
5. **Функциональности**: Обеспечение корректной работы с переменными и ответами

## Типы валидации

### 1. Структурная валидация

Проверяет корректность формата и структуры промта:

- Наличие обязательных полей в YAML frontmatter
- Корректность формата семантической версии
- Правильность структуры переменных
- Соответствие формату JSON Schema для ожидаемого ответа

```python
def validate_prompt_structure(prompt: PromptVersion) -> ValidationResult:
    """Проверка структуры промта"""
    errors = []
    
    # Проверка обязательных полей
    if not prompt.semantic_version:
        errors.append("semantic_version is required")
    
    if not prompt.domain:
        errors.append("domain is required")
    
    if not prompt.role:
        errors.append("role is required")
    
    # Проверка формата версии
    if not re.match(r"^\d+\.\d+\.\d+$", prompt.semantic_version):
        errors.append("semantic_version must follow MAJOR.MINOR.PATCH format")
    
    # Проверка переменных
    for var in prompt.variables_schema:
        if not var.name:
            errors.append("Variable name is required")
        if var.type not in ["string", "integer", "boolean", "array", "object"]:
            errors.append(f"Invalid variable type: {var.type}")
    
    return ValidationResult(success=len(errors) == 0, errors=errors)
```

### 2. Семантическая валидация

Проверяет логическую корректность промта:

- Соответствие роли промта его содержимому
- Корректность использования переменных
- Согласованность ожидаемого ответа с содержимым промта
- Логическая целостность связанных компонентов

### 3. Безопасная валидация

Проверяет безопасность содержимого промта:

- Отсутствие потенциально опасных инструкций
- Проверка на наличие попыток обхода ограничений
- Контроль доступа к системным ресурсам
- Проверка на наличие вредоносного содержимого

### 4. Функциональная валидация

Проверяет работоспособность промта:

- Тестирование с различными наборами переменных
- Проверка корректности рендеринга
- Валидация ожидаемого формата ответа
- Проверка совместимости с LLM провайдерами

## Компоненты системы валидации

### 1. Валидатор переменных

Проверяет корректность использования и определения переменных:

```python
def validate_variables_usage(content: str, variables_schema: List[VariableSchema]) -> ValidationResult:
    """Проверка использования переменных в содержимом промта"""
    errors = []
    
    # Проверка наличия всех переменных в содержимом
    for var in variables_schema:
        placeholder = f"{{{var.name}}}"
        if var.required and placeholder not in content:
            errors.append(f"Required variable '{var.name}' not used in content")
    
    # Проверка использования необъявленных переменных
    import re
    placeholders = re.findall(r'\{\{(\w+)\}\}', content)
    declared_vars = {var.name for var in variables_schema}
    
    for placeholder in placeholders:
        if placeholder not in declared_vars:
            errors.append(f"Undeclared variable '{placeholder}' used in content")
    
    return ValidationResult(success=len(errors) == 0, errors=errors)
```

### 2. Валидатор ответов

Проверяет корректность ожидаемого формата ответа:

```python
def validate_expected_response_schema(expected_response: Dict[str, Any]) -> ValidationResult:
    """Проверка корректности схемы ожидаемого ответа"""
    errors = []
    
    if expected_response is None:
        return ValidationResult(success=True, errors=[])
    
    # Проверка базовой структуры JSON Schema
    if "type" not in expected_response:
        errors.append("Expected response schema must have 'type' property")
    
    if expected_response.get("type") == "object":
        if "properties" not in expected_response:
            errors.append("Object response schema must have 'properties' property")
    
    return ValidationResult(success=len(errors) == 0, errors=errors)
```

### 3. Валидатор безопасности

Проверяет безопасность содержимого промта:

```python
def validate_prompt_security(content: str) -> ValidationResult:
    """Проверка безопасности содержимого промта"""
    errors = []
    
    # Проверка на наличие потенциально опасных инструкций
    dangerous_patterns = [
        r"ignore\s+previous\s+instructions",
        r"disregard\s+safety\s+guidelines",
        r"override\s+security\s+measures",
        r"execute\s+system\s+commands?",
        r"access\s+restricted\s+files?"
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            errors.append(f"Dangerous pattern found: {pattern}")
    
    # Проверка на наличие попыток обхода
    bypass_patterns = [
        r"jailbreak",
        r"prompt\s+injection",
        r"system\s+bypass"
    ]
    
    for pattern in bypass_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            errors.append(f"Bypass attempt pattern found: {pattern}")
    
    return ValidationResult(success=len(errors) == 0, errors=errors)
```

## Процесс валидации

### 1. При загрузке промта

При загрузке промтов из файловой системы выполняется комплексная валидация:

```python
class PromptValidator:
    """Комплексный валидатор промтов"""
    
    def validate_prompt_file(self, file_path: str) -> ValidationResult:
        """Валидация промта из файла"""
        try:
            # Чтение файла
            content = Path(file_path).read_text(encoding='utf-8')
            
            # Извлечение frontmatter и содержимого
            frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
            if not frontmatter_match:
                return ValidationResult(success=False, errors=["File doesn't contain valid frontmatter"])
            
            yaml_str, prompt_content = frontmatter_match.groups()
            metadata = yaml.safe_load(yaml_str)
            
            # Создание объекта PromptVersion для валидации
            prompt_obj = self._create_prompt_object(metadata, prompt_content, file_path)
            
            # Последовательная валидация
            results = [
                self.validate_structure(prompt_obj),
                self.validate_semantics(prompt_obj),
                self.validate_security(prompt_obj.content),
                self.validate_variables(prompt_obj.content, prompt_obj.variables_schema)
            ]
            
            # Сбор всех ошибок
            all_errors = []
            for result in results:
                if not result.success:
                    all_errors.extend(result.errors)
            
            return ValidationResult(success=len(all_errors) == 0, errors=all_errors)
            
        except Exception as e:
            return ValidationResult(success=False, errors=[f"Validation error: {str(e)}"])
    
    def _create_prompt_object(self, metadata: dict, content: str, file_path: str) -> PromptVersion:
        """Создание объекта промта для валидации"""
        # Реализация создания объекта из метаданных
        pass
```

### 2. При выполнении промта

При выполнении промта выполняется валидация переменных:

```python
def validate_rendered_prompt(
    prompt_template: str,
    variables: Dict[str, Any],
    variables_schema: List[VariableSchema]
) -> ValidationResult:
    """Валидация переменных при рендеринге промта"""
    errors = []
    
    # Валидация переменных по схеме
    schema_errors = validate_against_schema(variables, variables_schema)
    if schema_errors:
        errors.extend(schema_errors)
    
    # Проверка на потенциально опасные значения
    for var_name, var_value in variables.items():
        if isinstance(var_value, str):
            if contains_dangerous_content(var_value):
                errors.append(f"Potentially dangerous content in variable '{var_name}'")
    
    return ValidationResult(success=len(errors) == 0, errors=errors)
```

## Лучшие практики валидации

### 1. Комплексный подход

Используйте все типы валидации для обеспечения полной безопасности и корректности:

- Структурная валидация для проверки формата
- Семантическая для проверки логики
- Безопасная для предотвращения угроз
- Функциональная для проверки работоспособности

### 2. Автоматизация

Валидация должна быть автоматизирована и выполняться:

- При загрузке промтов
- При создании новых версий
- При изменении существующих промтов
- При выполнении промтов с переменными

### 3. Постепенное усиление

Валидация должна быть настроена с учетом уровня доверия:

- Строгая валидация для публичного использования
- Умеренная для внутреннего использования
- Гибкая для разработки и тестирования

### 4. Мониторинг и логирование

Все попытки использования невалидных промтов должны логироваться:

- Факты попыток использования
- Причины отказа
- Источники попыток
- Статистика ошибок

## Интеграция с системой

### 1. Система загрузки промтов

Загрузчик промтов интегрирован с валидатором:

```python
class PromptLoader:
    """Загрузчик промтов с валидацией"""
    
    def __init__(self):
        self.validator = PromptValidator()
    
    def load_all_prompts(self) -> Tuple[List[PromptVersion], List[str]]:
        """Загрузка всех промтов с валидацией"""
        prompts = []
        errors = []
        
        for file_path in self._find_prompt_files():
            validation_result = self.validator.validate_prompt_file(file_path)
            
            if validation_result.success:
                prompt = self._load_prompt_from_file(file_path)
                prompts.append(prompt)
            else:
                errors.append(f"Validation failed for {file_path}: {'; '.join(validation_result.errors)}")
        
        return prompts, errors
```

### 2. Система выполнения

Система выполнения проверяет промты перед использованием:

```python
class PromptExecutor:
    """Исполнитель промтов с валидацией"""
    
    def execute_prompt(
        self,
        prompt: PromptVersion,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Выполнение промта с валидацией переменных"""
        
        # Валидация переменных
        validation_result = validate_rendered_prompt(
            prompt.content,
            variables,
            prompt.variables_schema
        )
        
        if not validation_result.success:
            raise ValueError(f"Validation failed: {'; '.join(validation_result.errors)}")
        
        # Рендеринг промта с переменными
        rendered_prompt = self.render_prompt(prompt.content, variables)
        
        # Выполнение через LLM
        response = self.call_llm(rendered_prompt, prompt)
        
        # Валидация ответа если задана схема
        if prompt.expected_response_schema:
            response_validation = validate_response(response, prompt.expected_response_schema)
            if not response_validation.success:
                # Обработка невалидного ответа
                pass
        
        return response
```

## Расширение системы валидации

Систему валидации можно расширять через:

- Пользовательские валидаторы
- Плагины валидации
- Конфигурационные правила
- Специфичные для домена проверки

Такой подход позволяет адаптировать систему валидации под конкретные требования и сценарии использования.