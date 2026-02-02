"""
Шаблоны промтов для планирования
"""
from typing import Dict, Any, Optional


class PromptTemplates:
    """Класс, содержащий шаблоны промтов для планирования задач и генерации кода"""
    
    # Шаблоны для генерации плана
    PLAN_GENERATION_TEMPLATE = """
Ты - опытный разработчик программного обеспечения и технический менеджер.
Твоя задача - создать детальный план реализации следующих требований:

ТРЕБОВАНИЯ:
{requirements}

КОНТЕКСТ ПРОЕКТА:
{project_context}

ОГРАНИЧЕНИЯ:
{constraints}

ПРИОРИТЕТ:
{priority}

ОЦЕНКА ТРУДОЗАТРАТ:
{estimated_effort_hours} часов

Формат ответа должен быть в формном формате JSON со следующими полями:
- "plan": массив задач, каждая задача должна содержать "id", "title", "description", "estimated_hours", "dependencies", "priority", "status"
- "estimated_duration": общая оценка продолжительности в часах
- "risk_assessment": словарь с оценкой рисков

Ответ:"""
    
    # Шаблоны для генерации кода
    CODE_GENERATION_TEMPLATE = """
Ты - опытный разработчик программного обеспечения.
Твоя задача - сгенерировать качественный код на языке {target_language} для следующих требований:

ТРЕБОВАНИЯ:
{requirements}

ЦЕЛЕВАЯ ТЕХНОЛОГИЯ:
{target_framework}

КОНТЕКСТ СУЩЕСТВУЮЩЕГО КОДА:
{existing_code_context}

РУКОВОДСТВА ПО СТИЛЮ:
{style_guidelines}

ТРЕБОВАНИЯ БЕЗОПАСНОСТИ:
{security_requirements}

Сгенерируй код в следующем формате:
- "generated_code": строка с сгенерированным кодом
- "file_path": предполагаемый путь файла
- "dependencies": список зависимостей
- "quality_score": оценка качества от 0 до 1

Сгенерированный код:"""
    
    # Шаблоны для разбиения задач
    TASK_BREAKDOWN_TEMPLATE = """
Ты - опытный технический менеджер и разработчик.
Твоя задача - разбить следующую задачу на подзадачи:

ОПИСАНИЕ ЗАДАЧИ:
{task_description}

КОНТЕКСТ ПРОЕКТА:
{project_context}

НЕОБХОДИМЫЕ НАВЫКИ:
{required_skills}

ВРЕМЕННЫЕ ОГРАНИЧЕНИЯ:
{time_constraints}

Разбей задачу на подзадачи в формате JSON:
- "subtasks": массив подзадач с полями "id", "title", "description", "estimated_hours", "required_skills", "depends_on"
- "estimated_complexity": оценка сложности ("trivial", "easy", "medium", "hard", "very_hard")
- "required_skills": обновленный список необходимых навыков

Разбиение задачи:"""
    
    @classmethod
    def generate_plan_prompt(cls, requirements: str, project_context: Dict[str, Any], 
                           constraints: Optional[list] = None, priority: str = "normal", 
                           estimated_effort_hours: Optional[int] = None) -> str:
        """Генерация промта для планирования"""
        return cls.PLAN_GENERATION_TEMPLATE.format(
            requirements=requirements,
            project_context=str(project_context),
            constraints=str(constraints or []),
            priority=priority,
            estimated_effort_hours=estimated_effort_hours or 0
        )
    
    @classmethod
    def generate_code_prompt(cls, requirements: str, target_language: str, 
                           target_framework: Optional[str] = None,
                           existing_code_context: Optional[str] = None,
                           style_guidelines: Optional[list] = None,
                           security_requirements: Optional[list] = None) -> str:
        """Генерация промта для генерации кода"""
        return cls.CODE_GENERATION_TEMPLATE.format(
            requirements=requirements,
            target_language=target_language,
            target_framework=target_framework or "не указан",
            existing_code_context=existing_code_context or "не предоставлен",
            style_guidelines=str(style_guidelines or []),
            security_requirements=str(security_requirements or [])
        )
    
    @classmethod
    def generate_task_breakdown_prompt(cls, task_description: str, 
                                     project_context: Dict[str, Any],
                                     required_skills: Optional[list] = None,
                                     time_constraints: Optional[dict] = None) -> str:
        """Генерация промта для разбиения задачи"""
        return cls.TASK_BREAKDOWN_TEMPLATE.format(
            task_description=task_description,
            project_context=str(project_context),
            required_skills=str(required_skills or []),
            time_constraints=str(time_constraints or {})
        )


# Словарь с шаблонами для удобного доступа
PROMPT_TEMPLATES: Dict[str, str] = {
    "plan_generation": PromptTemplates.PLAN_GENERATION_TEMPLATE,
    "code_generation": PromptTemplates.CODE_GENERATION_TEMPLATE,
    "task_breakdown": PromptTemplates.TASK_BREAKDOWN_TEMPLATE
}