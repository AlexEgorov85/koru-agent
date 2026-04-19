"""
Скрипт для создания system промптов для всех user промптов.
"""
import os
from pathlib import Path

PROMPTS_DIR = Path("data/prompts")

# Шаблоны system промптов для разных типов компонентов
SYSTEM_PROMPT_TEMPLATES = {
    "skill.planning": """capability: {capability}.system
component_type: skill
version: v1.0.0
status: active
description: Системный промпт для {name}
content: |
  Ты — модуль планирования. Создай план действий для достижения цели.
  Верни результат в формате JSON согласно выходному контракту.

  === ПРАВИЛА ===
  1. План должен быть реалистичным и выполнимым
  2. Каждый шаг должен иметь понятную цель
  3. Используй доступные инструменты эффективно
variables: []
metadata:
  author: system
  created: '2026-02-19'
  description: Системный промпт для {capability}
""",
    "skill.data_analysis": """capability: {capability}.system
component_type: skill
version: v1.0.0
status: active
description: Системный промпт для {name}
content: |
  Ты — модуль анализа данных. Проанализируй данные и верни результат.
  Верни результат в формате JSON согласно выходному контракту.

  === ПРАВИЛА ===
  1. Будь объективен и точен
  2. Используй только предоставленные данные
  3. Избегай предположений без оснований
variables: []
metadata:
  author: system
  created: '2026-02-19'
  description: Системный промпт для {capability}
""",
    "skill.final_answer": """capability: {capability}.system
component_type: skill
version: v1.0.0
status: active
description: Системный промпт для {name}
content: |
  Ты — модуль генерации финального ответа. Сформируй ответ на основе контекста.
  Верни результат в формате JSON согласно выходному контракту.

  === ПРАВИЛА ===
  1. Ответ должен быть полным и точным
  2. Используй только проверенные данные
  3. Избегай противоречий
variables: []
metadata:
  author: system
  created: '2026-02-19'
  description: Системный промпт для {capability}
""",
    "service.contract": """capability: {capability}.system
component_type: service
version: v1.0.0
status: active
description: Системный промпт для {name}
content: |
  Ты — сервис управления контрактами. Управляй контрактами.
  Верни результат в формате JSON согласно выходному контракту.

  === ПРАВИЛА ===
  1. Соблюдай формат контрактов
  2. Проверяй валидность данных
variables: []
metadata:
  author: system
  created: '2026-02-19'
  description: Системный промпт для {capability}
""",
    "service.sql_generation": """capability: {capability}.system
component_type: service
version: v1.0.0
status: active
description: Системный промпт для {name}
content: |
  Ты — сервис генерации SQL. Создай SQL запрос.
  Верни результат в формате JSON согласно выходному контракту.

  === ПРАВИЛА ===
  1. SQL должен быть безопасным (SELECT only)
  2. Используй параметризованные запросы
  3. Оптимизируй запросы
variables: []
metadata:
  author: system
  created: '2026-02-19'
  description: Системный промпт для {capability}
""",
    "behavior": """capability: {capability}.system
component_type: behavior
version: v1.0.0
status: active
description: Системный промпт для {name}
content: |
  Ты — поведенческий паттерн. Выполни действие.
  Верни результат в формате JSON согласно выходному контракту.

  === ПРАВИЛА ===
  1. Следуй архитектуре
  2. Возвращай структурированный результат
variables: []
metadata:
  author: system
  created: '2026-02-19'
  description: Системный промпт для {capability}
""",
}


def get_template(capability: str) -> str:
    """Возвращает шаблон для capability."""
    if capability.startswith("skill.planning"):
        return SYSTEM_PROMPT_TEMPLATES["skill.planning"]
    elif capability.startswith("skill.data_analysis"):
        return SYSTEM_PROMPT_TEMPLATES["skill.data_analysis"]
    elif capability.startswith("skill.final_answer"):
        return SYSTEM_PROMPT_TEMPLATES["skill.final_answer"]
    elif capability.startswith("service.contract"):
        return SYSTEM_PROMPT_TEMPLATES["service.contract"]
    elif capability.startswith("service.sql_generation"):
        return SYSTEM_PROMPT_TEMPLATES["service.sql_generation"]
    elif capability.startswith("behavior"):
        return SYSTEM_PROMPT_TEMPLATES["behavior"]
    else:
        # Default template
        return """capability: {capability}.system
component_type: skill
version: v1.0.0
status: active
description: Системный промпт для {name}
content: |
  Ты — модуль {name}. Выполни задачу.
  Верни результат в формате JSON согласно выходному контракту.

  === ПРАВИЛА ===
  1. Следуй инструкциям
  2. Будь точен
variables: []
metadata:
  author: system
  created: '2026-02-19'
  description: Системный промпт для {capability}
"""


def create_system_prompts():
    """Создаёт system промпты для всех user промптов."""
    created_count = 0
    
    # Находим все user промпты
    for user_file in PROMPTS_DIR.rglob("*.user_v1.0.0.yaml"):
        # Извлекаем capability из имени файла
        rel_path = user_file.relative_to(PROMPTS_DIR)
        parts = list(rel_path.parts)
        
        # Убираем .user_v1.0.0.yaml из имени файла
        filename = parts[-1].replace(".user_v1.0.0.yaml", "")
        
        # Формируем capability из пути
        # Примеры:
        # skill/planning/planning.create_plan.user → skill.planning.create_plan
        # behavior/behavior.react.think.user → behavior.react.think
        
        if len(parts) == 2 and parts[0] == 'behavior':
            # behavior/behavior.X.user → behavior.X
            capability = f"behavior.{filename.replace('behavior.', '')}"
        elif len(parts) > 1:
            # component_type/component_name/capability.user
            component_type = parts[0]  # skill, tool, service, behavior
            component_name = parts[1]  # planning, sql_generation, etc.
            capability_base = filename  # planning.create_plan, sql_generation.generate_query, etc.
            
            # Убираем дублирование component_name из capability_base если есть
            if capability_base.startswith(component_name + "."):
                capability_base = capability_base[len(component_name) + 1:]
            
            capability = f"{component_type}.{component_name}.{capability_base}"
        else:
            capability = filename
        
        # Создаём system файл с capability в содержимом
        system_filename = f"{filename}.system_v1.0.0.yaml"
        parts[-1] = system_filename
        system_path = PROMPTS_DIR / Path(*parts)
        
        if system_path.exists():
            print(f"[SKIP] {system_path}")
            continue
        
        # Получаем шаблон
        template = get_template(capability)
        content = template.format(capability=capability, name=capability_base.replace(".", " ").title() if len(parts) > 1 else filename.replace(".", " ").title())
        
        # Создаём файл
        system_path.parent.mkdir(parents=True, exist_ok=True)
        system_path.write_text(content, encoding='utf-8')
        print(f"[OK] {system_path}")
        created_count += 1
    
    print(f"\nCreated: {created_count} system prompts")


if __name__ == "__main__":
    create_system_prompts()
