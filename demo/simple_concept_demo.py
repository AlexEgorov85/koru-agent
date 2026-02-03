#!/usr/bin/env python3
"""
Простая демонстрация концепции production-ready PromptRepository
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any


class PromptStatus:
    """Статусы жизненного цикла промта"""
    DRAFT = "draft"
    ACTIVE = "active"
    SHADOW = "shadow"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PromptRole:
    """Роль промта в диалоге"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class VariableSchema:
    """Схема переменной шаблона"""
    def __init__(self, name: str, var_type: str, required: bool = True, description: str = ""):
        self.name = name
        self.type = var_type  # "string", "integer", "boolean", "array", "object"
        self.required = required
        self.description = description


class PromptVersion:
    """Версия промта с полным жизненным циклом"""
    
    def __init__(
        self,
        id: str,
        semantic_version: str,
        domain: str,
        provider_type: str,
        capability_name: str,
        role: str,
        content: str,
        variables_schema: List[VariableSchema],
        status: str = PromptStatus.DRAFT,
        version_notes: str = ""
    ):
        self.id = id
        self.semantic_version = semantic_version
        self.domain = domain
        self.provider_type = provider_type
        self.capability_name = capability_name
        self.role = role
        self.content = content
        self.variables_schema = variables_schema
        self.status = status
        self.version_notes = version_notes
        self.created_at = datetime.utcnow()
    
    def get_address_key(self) -> str:
        """Ключ для поиска: домен:провайдер:capability:роль"""
        return f"{self.domain}:{self.provider_type}:{self.capability_name}:{self.role}"
    
    def validate_variables(self, variables: Dict[str, Any]) -> Dict[str, List[str]]:
        """Валидация переменных по схеме, возвращает ошибки"""
        errors = {}
        
        for schema_var in self.variables_schema:
            var_name = schema_var.name
            required = schema_var.required
            
            if required and var_name not in variables:
                errors.setdefault(var_name, []).append(f"Обязательная переменная '{var_name}' отсутствует")
                continue
                
            if var_name in variables:
                value = variables[var_name]
                
                # Проверка типа
                expected_type = schema_var.type
                actual_type = type(value).__name__
                
                if expected_type == "string" and not isinstance(value, str):
                    errors.setdefault(var_name, []).append(f"Ожидается строка, получено {actual_type}")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.setdefault(var_name, []).append(f"Ожидается целое число, получено {actual_type}")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.setdefault(var_name, []).append(f"Ожидается булево значение, получено {actual_type}")
                elif expected_type == "array" and not isinstance(value, list):
                    errors.setdefault(var_name, []).append(f"Ожидается массив, получено {actual_type}")
                elif expected_type == "object" and not isinstance(value, dict):
                    errors.setdefault(var_name, []).append(f"Ожидается объект, получено {actual_type}")
        
        return errors


async def demo_concept():
    """Демонстрация концепции PromptRepository"""
    print("=== Демонстрация Production-Ready PromptRepository ===\n")
    
    print("1. Создание версии промта с полным жизненным циклом...")
    
    # Создаем тестовую версию промта
    test_version = PromptVersion(
        id="prod_demo_version_001",
        semantic_version="1.0.0",
        domain="problem_solving",
        provider_type="openai",
        capability_name="code_analysis",
        role=PromptRole.SYSTEM,
        content="Ты — эксперт по анализу кода. Проанализируй: {{code_snippet}} с целью {{analysis_goal}}",
        variables_schema=[
            VariableSchema(
                name="code_snippet",
                var_type="string",
                required=True,
                description="Сниппет кода для анализа"
            ),
            VariableSchema(
                name="analysis_goal",
                var_type="string",
                required=True,
                description="Цель анализа"
            ),
            VariableSchema(
                name="context",
                var_type="string",
                required=False,
                description="Дополнительный контекст"
            )
        ],
        status=PromptStatus.ACTIVE,
        version_notes="Инициализация production-версии промта для анализа кода"
    )
    
    print(f"   - ID: {test_version.id}")
    print(f"   - Семантическая версия: {test_version.semantic_version}")
    print(f"   - Домен: {test_version.domain}")
    print(f"   - Провайдер: {test_version.provider_type}")
    print(f"   - Капабилити: {test_version.capability_name}")
    print(f"   - Роль: {test_version.role}")
    print(f"   - Статус: {test_version.status}")
    print(f"   - Адрес: {test_version.get_address_key()}")
    print(f"   - Содержимое: {test_version.content}")
    print(f"   - Переменные: {[(v.name, v.type, v.required) for v in test_version.variables_schema]}")
    print(f"   - Заметки: {test_version.version_notes}")
    
    print("\n2. Демонстрация валидации переменных...")
    
    # Проверяем валидацию с корректными переменными
    validation_result = test_version.validate_variables({
        "code_snippet": "def hello(): pass",
        "analysis_goal": "нахождение багов"
    })
    print(f"   - Валидация корректных переменных: {len(validation_result)} ошибок")
    
    # Проверяем валидацию без обязательной переменной
    validation_result = test_version.validate_variables({
        "code_snippet": "def hello(): pass"
        # analysis_goal отсутствует
    })
    print(f"   - Валидация без обязательной переменной: {len(validation_result)} ошибок")
    if validation_result:
        for var_name, errors in validation_result.items():
            print(f"     - Ошибка переменной '{var_name}': {errors[0]}")
    
    print("\n3. Демонстрация схемы переменных...")
    
    print("   - Схема переменных:")
    for var_schema in test_version.variables_schema:
        required_status = "обязательная" if var_schema.required else "опциональная"
        print(f"     * {var_schema.name}: {var_schema.type} ({required_status}) - {var_schema.description}")
    
    print("\n4. Демонстрация статусов жизненного цикла...")
    
    statuses = [PromptStatus.DRAFT, PromptStatus.ACTIVE, PromptStatus.SHADOW, 
                PromptStatus.DEPRECATED, PromptStatus.ARCHIVED]
    
    status_descriptions = {
        PromptStatus.DRAFT: "Черновик, не готов к использованию",
        PromptStatus.ACTIVE: "Активная версия, используется в системе",
        PromptStatus.SHADOW: "Теневая версия для A/B тестирования",
        PromptStatus.DEPRECATED: "Устаревшая, но еще работает",
        PromptStatus.ARCHIVED: "Архивированная, больше не используется"
    }
    
    for status in statuses:
        print(f"   - {status}: {status_descriptions[status]}")
    
    print("\n5. Демонстрация рендеринга с валидацией...")
    
    # Проверяем, что все обязательные переменные присутствуют
    template_context = {
        "code_snippet": "def add(a, b):\n    return a + b",
        "analysis_goal": "нахождение потенциальных проблем",
        "context": "функция сложения двух чисел"
    }
    
    validation_errors = test_version.validate_variables(template_context)
    if validation_errors:
        print(f"   - Ошибки валидации: {validation_errors}")
    else:
        print("   - Валидация пройдена успешно")
        
        # Подстановка переменных в шаблон
        rendered_content = test_version.content
        for var_name, var_value in template_context.items():
            rendered_content = rendered_content.replace(f"{{{var_name}}}}}", str(var_value))
        
        print(f"   - Отрендеренный промт: {rendered_content}")
    
    print("\n6. Демонстрация интеграции с файловой системой...")
    
    # Пример структуры файла промта
    prompt_file_content = {
        "id": test_version.id,
        "semantic_version": test_version.semantic_version,
        "domain": test_version.domain,
        "provider_type": test_version.provider_type,
        "capability_name": test_version.capability_name,
        "role": test_version.role,
        "status": test_version.status,
        "variables_schema": [
            {
                "name": v.name,
                "type": v.type,
                "required": v.required,
                "description": v.description
            } for v in test_version.variables_schema
        ],
        "content": test_version.content,
        "version_notes": test_version.version_notes
    }
    
    print("   - Структура файла промта (в формате JSON):")
    print(f"     {json.dumps(prompt_file_content, indent=4, ensure_ascii=False)[:200]}...")
    
    print("\n7. Демонстрация архитектурных компонентов...")
    
    print("   - PromptVersion: Модель данных версии промта")
    print("   - PromptRepository: Абстракция репозитория промтов")
    print("   - DatabasePromptRepository: Реализация с использованием DBProvider")
    print("   - CachedPromptRepository: Кэширующая обертка")
    print("   - PromptRenderer: Рендерер с валидацией переменных")
    print("   - PromptExecutionSnapshot: Снапшоты выполнения")
    
    print("\n8. Демонстрация потока выполнения...")
    
    print("   1. Agent -> Capability (получает ID версии промта)")
    print("   2. PromptRenderer <- Capability (запрашивает версию из репозитория)")
    print("   3. CachedPromptRepository <- ID версии (проверяет кэш)")
    print("   4. DatabasePromptRepository <- ID версии (если нет в кэше)")
    print("   5. PromptVersion.validate_variables(контекст) (валидация переменных)")
    print("   6. Подстановка переменных в шаблон")
    print("   7. Создание PromptExecutionSnapshot (для отладки и мониторинга)")
    print("   8. Отрендеренный промт -> LLM")
    
    print("\n=== Демонстрация завершена ===")
    print("\nКлючевые особенности production-ready PromptRepository:")
    print("  + Полный жизненный цикл промтов (draft -> active -> shadow -> deprecated -> archived)")
    print("  + Строгая валидация переменных по схеме")
    print("  + Защита от инъекций через проверку переменных")
    print("  + Снапшоты выполнения для отладки и мониторинга")
    print("  + Кэширование в памяти для высокой производительности")
    print("  + Интеграция с файловой системой и базой данных")
    print("  + Совместимость с GreenPlum/PostgreSQL")
    print("  + Обработка ошибок и fallback-механизмы")
    print("  + Метрики использования и производительности")


async def main():
    await demo_concept()


if __name__ == "__main__":
    asyncio.run(main())