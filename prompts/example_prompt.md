---
id: prompt_analysis_001
semantic_version: "1.0.0"
domain: "problem_solving"
provider_type: "openai"
capability_name: "code_analysis"
role: "system"
status: "active"
variables_schema:
  - name: "goal"
    type: "string"
    required: true
    description: "Цель анализа кода"
  - name: "file_content"
    type: "string"
    required: true
    description: "Содержимое файла для анализа"
  - name: "context"
    type: "string"
    required: false
    description: "Дополнительный контекст"
expected_response_schema:
  type: "object"
  properties:
    analysis:
      type: "string"
    suggestions:
      type: "array"
      items:
        type: "string"
---
Ты — эксперт по анализу кода. Твоя задача — проанализировать предоставленный код и дать рекомендации по улучшению.

Цель: {{goal}}
Контекст: {{context}}

Анализируй следующий код:
{{file_content}}

Верни результат в формате JSON.
