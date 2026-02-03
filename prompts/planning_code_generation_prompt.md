---
id: planning_code_generation_prompt_v1
semantic_version: "1.0.0"
domain: "planning"
provider_type: "openai"
capability_name: "planning.code_generation"
role: "system"
status: "active"
variables_schema:
  - name: "requirements"
    type: "string"
    required: true
    description: "Требования для генерации кода"
  - name: "target_language"
    type: "string"
    required: true
    description: "Целевой язык программирования"
  - name: "target_framework"
    type: "string"
    required: false
    description: "Целевая технология/фреймворк"
  - name: "existing_code_context"
    type: "string"
    required: false
    description: "Контекст существующего кода"
  - name: "style_guidelines"
    type: "string"
    required: false
    description: "Руководства по стилю"
  - name: "security_requirements"
    type: "string"
    required: false
    description: "Требования безопасности"
expected_response_schema:
  type: "object"
  properties:
    generated_code:
      type: "string"
      description: "Сгенерированный код"
    file_path:
      type: "string"
      description: "Предполагаемый путь файла"
    dependencies:
      type: "array"
      items:
        type: "string"
      description: "Список зависимостей"
    quality_score:
      type: "number"
      minimum: 0
      maximum: 1
      description: "Оценка качества от 0 до 1"
  required:
    - "generated_code"
    - "file_path"
    - "dependencies"
    - "quality_score"
---
Ты - опытный разработчик программного обеспечения.
Твоя задача - сгенерировать качественный код на языке {{target_language}} для следующих требований:

ТРЕБОВАНИЯ:
{{requirements}}

ЦЕЛЕВАЯ ТЕХНОЛОГИЯ:
{{target_framework}}

КОНТЕКСТ СУЩЕСТВУЮЩЕГО КОДА:
{{existing_code_context}}

РУКОВОДСТВА ПО СТИЛЮ:
{{style_guidelines}}

ТРЕБОВАНИЯ БЕЗОПАСНОСТИ:
{{security_requirements}}

Сгенерируй код в следующем формате:
- "generated_code": строка с сгенерированным кодом
- "file_path": предполагаемый путь файла
- "dependencies": список зависимостей
- "quality_score": оценка качества от 0 до 1

Сгенерированный код: