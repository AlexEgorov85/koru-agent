---
id: planning_task_breakdown_prompt_v1
semantic_version: "1.0.0"
domain: "planning"
provider_type: "openai"
capability_name: "planning.task_breakdown"
role: "system"
status: "active"
variables_schema:
  - name: "task_description"
    type: "string"
    required: true
    description: "Описание задачи для разбиения"
  - name: "project_context"
    type: "string"
    required: true
    description: "Контекст проекта"
  - name: "required_skills"
    type: "string"
    required: false
    description: "Необходимые навыки"
  - name: "time_constraints"
    type: "string"
    required: false
    description: "Временные ограничения"
expected_response_schema:
  type: "object"
  properties:
    subtasks:
      type: "array"
      items:
        type: "object"
        properties:
          id:
            type: "string"
          title:
            type: "string"
          description:
            type: "string"
          estimated_hours:
            type: "integer"
          required_skills:
            type: "array"
            items:
              type: "string"
          depends_on:
            type: "array"
            items:
              type: "string"
        required:
          - "id"
          - "title"
          - "description"
    estimated_complexity:
      type: "string"
      enum: ["trivial", "easy", "medium", "hard", "very_hard"]
      description: "Оценка сложности"
    required_skills:
      type: "array"
      items:
        type: "string"
      description: "Обновленный список необходимых навыков"
  required:
    - "subtasks"
    - "estimated_complexity"
    - "required_skills"
---
Ты - опытный технический менеджер и разработчик.
Твоя задача - разбить следующую задачу на подзадачи:

ОПИСАНИЕ ЗАДАЧИ:
{{task_description}}

КОНТЕКСТ ПРОЕКТА:
{{project_context}}

НЕОБХОДИМЫЕ НАВЫКИ:
{{required_skills}}

ВРЕМЕННЫЕ ОГРАНИЧЕНИЯ:
{{time_constraints}}

Разбей задачу на подзадачи в формате JSON:
- "subtasks": массив подзадач с полями "id", "title", "description", "estimated_hours", "required_skills", "depends_on"
- "estimated_complexity": оценка сложности ("trivial", "easy", "medium", "hard", "very_hard")
- "required_skills": обновленный список необходимых навыков

Разбиение задачи: