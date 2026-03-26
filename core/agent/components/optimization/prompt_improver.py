"""
PromptImprover — LLM генерация улучшений промптов.

ОТВЕТСТВЕННОСТЬ:
- Генерация улучшенных версий промптов через LLM
- На основе root causes и примеров
- Детерминированная генерация (seed, temperature=0)
"""
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.models.data.prompt import Prompt
from core.models.enums.common_enums import ComponentType


@dataclass
class ImprovedPrompt:
    """Улучшенная версия промпта"""
    original_prompt: str
    improved_prompt: str
    changes_made: List[str]
    improvement_type: str  # error_handling, clarity, examples, etc.
    confidence: float  # 0.0-1.0 насколько LLM уверен в улучшении
    metadata: Dict[str, Any]


class PromptImprover:
    """
    Генератор улучшений промптов через LLM.

    USAGE:
    ```python
    improver = PromptImprover(llm_provider)
    
    improvement = await improver.improve(
        prompt=original_prompt,
        root_causes=[...],
        examples=[...],
        improvement_focus='error_handling'
    )
    ```
    """

    def __init__(self, llm_provider: BaseLLMProvider):
        """
        Инициализация.

        ARGS:
        - llm_provider: LLM провайдер для генерации
        """
        self.llm_provider = llm_provider

    async def improve(
        self,
        prompt: Prompt,
        root_causes: List[Dict[str, Any]],
        examples: Optional[List[Dict[str, Any]]] = None,
        improvement_focus: str = 'error_handling'
    ) -> ImprovedPrompt:
        """
        Генерация улучшенной версии промпта.

        ARGS:
        - prompt: оригинальный промпт
        - root_causes: корневые причины проблем
        - examples: примеры хороших/плохих ответов
        - improvement_focus: фокус улучшения

        RETURNS:
        - ImprovedPrompt: улучшенная версия
        """
        # Формирование промпта для генерации
        generation_prompt = self._build_generation_prompt(
            prompt=prompt.content,
            root_causes=root_causes,
            examples=examples,
            improvement_focus=improvement_focus
        )

        # Генерация через LLM
        response = await self._generate_with_llm(generation_prompt)

        # Парсинг ответа
        improved = self._parse_improvement_response(response, prompt.content)

        return improved

    def _build_generation_prompt(
        self,
        prompt: str,
        root_causes: List[Dict[str, Any]],
        examples: Optional[List[Dict[str, Any]]],
        improvement_focus: str
    ) -> str:
        """
        Построение промпта для генерации улучшений.

        ARGS:
        - prompt: оригинальный промпт
        - root_causes: корневые причины
        - examples: примеры
        - improvement_focus: фокус

        RETURNS:
        - str: промпт для LLM
        """
        # Анализ проблем
        problems_text = "\n".join([
            f"- {rc.get('problem', 'Unknown')}"
            for rc in root_causes[:3]
        ])

        # Рекомендации
        recommendations_text = "\n".join([
            f"- {rc.get('fix', 'Fix this issue')}"
            for rc in root_causes[:3]
        ])

        # Примеры если есть
        examples_text = ""
        if examples:
            examples_text = "\n\nПРИМЕРЫ:\n"
            for ex in examples[:2]:
                examples_text += f"\nХороший пример:\n{ex.get('output', 'N/A')}\n"

        # Фокус улучшения
        focus_instructions = {
            'error_handling': '''
ДОБАВЬ ОБРАБОТКУ ОШИБОК:
1. Явные инструкции что делать при ошибках
2. Градации confidence_score (0.0-1.0)
3. Примеры ответов для разных сценариев (успех/частично/нет данных)
4. Инструкции "никогда не выдумывай данные"
''',
            'clarity': '''
УЛУЧШИ ЯСНОСТЬ:
1. Разбей сложные инструкции на шаги
2. Убери неоднозначные формулировки
3. Добавь явные примеры формата вывода
''',
            'examples': '''
ДОБАВЬ ПРИМЕРЫ:
1. Минимум 2-3 примера правильного вывода
2. Примеры edge cases
3. Примеры ошибочных ситуаций и как их обрабатывать
''',
            'constraints': '''
ДОБАВЬ ОГРАНИЧЕНИЯ:
1. Явные правила валидации
2. Ограничения на формат вывода
3. Запреты (чего делать нельзя)
'''
        }

        return f"""
Ты — эксперт по оптимизации промптов для LLM.

ЗАДАЧА: Улучши следующий промпт на основе анализа проблем.

ОРИГИНАЛЬНЫЙ ПРОМПТ:
{prompt}

=== АНАЛИЗ ПРОБЛЕМ ===
Найдены проблемы:
{problems_text}

Рекомендации по исправлению:
{recommendations_text}

=== ФОКУС УЛУЧШЕНИЯ ===
{focus_instructions.get(improvement_focus, 'Улучши промпт')}
{examples_text}

=== ТРЕБОВАНИЯ К НОВОМУ ПРОМТУ ===
1. Сохрани структуру и переменные оригинального промпта
2. Добавь конкретные улучшения для выявленных проблем
3. Сделай промпт более конкретным и однозначным
4. Добавь примеры если это поможет
5. НЕ меняй выходной формат (JSON schema должна остаться той же)

=== ФОРМАТ ОТВЕТА ===
Верни ответ в формате JSON:
{{
    "improved_prompt": "полный текст улучшенного промпта",
    "changes_made": ["список изменений"],
    "improvement_type": "тип улучшения",
    "confidence": 0.0-1.0
}}

УЛУЧШЕННЫЙ ПРОМПТ:
"""

    async def _generate_with_llm(self, prompt: str) -> str:
        """
        Генерация через LLM.

        ARGS:
        - prompt: промпт для генерации

        RETURNS:
        - str: ответ LLM
        """
        # Параметры для детерминированной генерации
        response = await self.llm_provider.generate(
            prompt=prompt,
            temperature=0.0,  # Детерминированно
            max_tokens=4000,
            seed=42  # Фиксированный seed
        )

        return response.content

    def _parse_improvement_response(
        self,
        response: str,
        original_prompt: str
    ) -> ImprovedPrompt:
        """
        Парсинг ответа LLM.

        ARGS:
        - response: ответ LLM
        - original_prompt: оригинальный промпт

        RETURNS:
        - ImprovedPrompt: улучшенная версия
        """
        import json

        # Поиск JSON в ответе
        start = response.find('{')
        end = response.rfind('}') + 1

        if start == -1 or end == -1:
            # Если JSON не найден, используем весь ответ как improved prompt
            return ImprovedPrompt(
                original_prompt=original_prompt,
                improved_prompt=response,
                changes_made=['General improvement'],
                improvement_type='general',
                confidence=0.5,
                metadata={'parse_error': 'JSON not found'}
            )

        try:
            data = json.loads(response[start:end])

            return ImprovedPrompt(
                original_prompt=original_prompt,
                improved_prompt=data.get('improved_prompt', response),
                changes_made=data.get('changes_made', ['Unknown changes']),
                improvement_type=data.get('improvement_type', 'general'),
                confidence=float(data.get('confidence', 0.5)),
                metadata={'parsed': True}
            )
        except json.JSONDecodeError:
            return ImprovedPrompt(
                original_prompt=original_prompt,
                improved_prompt=response,
                changes_made=['Parse error, using full response'],
                improvement_type='general',
                confidence=0.3,
                metadata={'parse_error': 'JSON decode error'}
            )

    def generate_version_id(self, prompt: Prompt, improvement: ImprovedPrompt) -> str:
        """
        Генерация ID новой версии.

        ARGS:
        - prompt: оригинальный промпт
        - improvement: улучшение

        RETURNS:
        - str: ID версии
        """
        # Хеш от содержимого
        content_hash = hashlib.sha256(
            improvement.improved_prompt.encode()
        ).hexdigest()[:8]

        # Инкремент версии
        current_version = prompt.version.lstrip('v')
        parts = current_version.split('.')

        if len(parts) >= 3:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            new_version = f"v{major}.{minor}.{patch + 1}"
        else:
            new_version = "v1.0.1"

        return f"{new_version}_{content_hash}"
