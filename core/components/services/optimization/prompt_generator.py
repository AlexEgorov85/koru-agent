"""
PromptGenerator — генерация улучшенного промта через LLM.

НАЗНАЧЕНИЕ:
- Загружает текущий промпт из PromptService
- Отправляет в LLM текущий промпт + анализ ошибок + предложения изменений
- Получает новую версию промта
- Сохраняет как draft версию
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from core.components.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.models.enums.common_enums import ComponentType
from core.agent.components.action_executor import ExecutionContext


@dataclass
class PromptGeneratorInput(ServiceInput):
    """Входные данные для генерации."""
    prompt_path: str
    analysis_root_causes: List[str]
    analysis_changes: List[str]
    failed_examples: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PromptGeneratorOutput(ServiceOutput):
    """Результат генерации."""
    new_prompt_text: str = ""
    new_version: str = ""
    changes_applied: List[str] = field(default_factory=list)
    success: bool = False


class PromptGenerator(BaseService):
    """
    Генератор улучшенных промптов через LLM.

    RESPONSIBILITIES:
    - Загрузка текущего промта
    - Формирование запроса к LLM с контекстом улучшений
    - Получение и валидация новой версии
    - Сохранение как draft

    USAGE:
    ```python
    generator = PromptGenerator(app_context, event_bus)
    await generator.initialize()
    result = await generator.generate(PromptGeneratorInput(
        prompt_path="behavior.react.think.user",
        analysis_root_causes=["LLM таймауты"],
        analysis_changes=["Упростить структуру ответа"]
    ))
    ```
    """

    DEPENDENCIES = ["event_bus"]

    def __init__(self, application_context, event_bus=None):
        super().__init__(application_context)
        self._event_bus = event_bus
        self._executor = None
        self._prompt_service = None

    @property
    def name(self) -> str:
        return "prompt_generator"

    @property
    def component_type(self) -> ComponentType:
        return ComponentType.SERVICE

    async def initialize(self) -> bool:
        if self._is_initialized:
            return True
        if self._application_context:
            self._executor = self._application_context.executor
            self._prompt_service = self._application_context.prompt_service
        return await super().initialize()

    async def generate(self, input_data: PromptGeneratorInput) -> PromptGeneratorOutput:
        """Генерация улучшенного промта."""
        if not self._executor:
            return PromptGeneratorOutput(success=False)

        current_prompt = await self._load_current_prompt(input_data.prompt_path)
        if not current_prompt:
            return PromptGeneratorOutput(success=False)

        prompt = self._build_generation_prompt(
            current_prompt=current_prompt,
            root_causes=input_data.analysis_root_causes,
            changes=input_data.analysis_changes,
            failed_examples=input_data.failed_examples
        )

        try:
            exec_context = ExecutionContext()
            result = await self._executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": prompt,
                    "structured_output": {
                        "type": "object",
                        "properties": {
                            "improved_prompt": {
                                "type": "string",
                                "description": "Полный текст улучшенного промта"
                            },
                            "changes_applied": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Список применённых изменений"
                            },
                            "version": {
                                "type": "string",
                                "description": "Новая версия промта (например v1.1.0)"
                            }
                        },
                        "required": ["improved_prompt", "changes_applied"]
                    }
                },
                context=exec_context
            )

            if result.status.value == "completed" and result.data:
                return self._parse_response(result.data)

        except Exception as e:
            await self._log_error(f"Prompt generation failed: {e}")

        return PromptGeneratorOutput(success=False)

    async def _load_current_prompt(self, prompt_path: str) -> Optional[str]:
        """Загрузка текущего промта из PromptService."""
        if self._prompt_service:
            try:
                prompt = self._prompt_service.get_prompt(prompt_path)
                if prompt:
                    return prompt
            except Exception:
                pass
        
        # Fallback: чтение из файла
        try:
            from pathlib import Path
            base_dir = Path("data/prompts/behavior/behavior")
            files = list(base_dir.glob(f"{prompt_path}*.yaml"))
            if files:
                import yaml
                with open(files[0], 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    return data.get('content', '') or data.get('text', '')
        except Exception:
            pass
        
        return None

    def _build_generation_prompt(
        self,
        current_prompt: str,
        root_causes: List[str],
        changes: List[str],
        failed_examples: List[Dict[str, Any]]
    ) -> str:
        causes_text = "\n".join(f"- {c}" for c in root_causes)
        changes_text = "\n".join(f"- {c}" for c in changes)
        
        examples_text = ""
        for ex in failed_examples[:3]:
            examples_text += f"\n- Запрос: {ex.get('goal', '')}\n  Ожидалось: {ex.get('expected', '')}\n  Получено: {ex.get('actual', '')}\n"

        return f"""Ты — инженер промптов. Твоя задача — улучшить системный промпт для AI-агента.

## Текущий промпт
```
{current_prompt}
```

## Корневые причины ошибок
{causes_text}

## Предлагаемые изменения
{changes_text}

## Примеры ошибок
{examples_text if examples_text else "Нет примеров"}

## Задача
1. Проанализируй текущий промпт
2. Примени предложенные изменения
3. Сохрани общую структуру и стиль
4. Верни полный текст улучшенного промта

## Требования
- Не удаляй существующие правила без необходимости
- Добавляй новые правила в конец соответствующих секций
- Сохраняй форматирование
- Верни ПОЛНЫЙ текст промта, а не только изменения

Верни ответ в формате JSON."""

    def _parse_response(self, data: Any) -> PromptGeneratorOutput:
        if isinstance(data, dict):
            return PromptGeneratorOutput(
                new_prompt_text=data.get('improved_prompt', ''),
                changes_applied=data.get('changes_applied', []),
                new_version=data.get('version', 'v1.1.0'),
                success=bool(data.get('improved_prompt', ''))
            )
        return PromptGeneratorOutput(success=False)
