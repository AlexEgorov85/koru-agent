---
id: planning_plan_generation_prompt_v1
semantic_version: "1.0.0"
domain: "planning"
provider_type: "openai"
capability_name: "planning.plan_generation"
role: "system"
status: "active"
variables_schema:
  - name: "requirements"
    type: "string"
    required: true
    description: "Требования для реализации"
  - name: "project_context"
    type: "string"
    required: true
    description: "Контекст проекта"
  - name: "constraints"
    type: "string"
    required: false
    description: "Ограничения проекта"
  - name: "priority"
    type: "string"
    required: false
    default_value: "normal"
    description: "Приоритет задач"
  - name: "estimated_effort_hours"
    type: "integer"
    required: false
    description: "Оценка трудозатрат в часах"
expected_response_schema:
  type: "object"
  properties:
    plan:
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
          dependencies:
            type: "array"
            items:
              type: "string"
          priority:
            type: "string"
          status:
            type: "string"
        required:
          - "id"
          - "title"
          - "description"
    estimated_duration:
      type: "number"
      description: "Общая оценка продолжительности в часах"
    risk_assessment:
      type: "object"
      description: "Оценка рисков"
  required:
    - "plan"
    - "estimated_duration"
    - "risk_assessment"
---
Ты - опытный разработчик программного обеспечения и технический менеджер.
Твоя задача - создать детальный план реализации следующих требований:

ТРЕБОВАНИЯ:
{{requirements}}

КОНТЕКСТ ПРОЕКТА:
{{project_context}}

ОГРАНИЧЕНИЯ:
{{constraints}}

ПРИОРИТЕТ:
{{priority}}

ОЦЕНКА ТРУДОЗАТРАТ:
{{estimated_effort_hours}} часов

Формат ответа должен быть в формном формате JSON со следующими полями:
- "plan": массив задач, каждая задача должна содержать "id", "title", "description", "estimated_hours", "dependencies", "priority", "status"
- "estimated_duration": общая оценка продолжительности в часах
- "risk_assessment": словарь с оценкой рисков

Ответ: