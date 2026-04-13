"""
PromptGenerator - умная генерация промптов с стратегиями мутаций.

ОТВЕТСТВЕННОСТЬ:
- Генерация новых версий промптов на основе анализа неудач
- Применение стратегий мутаций (ADD_EXAMPLES, ADD_CONSTRAINTS, SIMPLIFY, ERROR_FIX)
- Детерминированная генерация
- Отслеживание parent версий и типов мутаций
- Генерация на основе root causes и examples
"""
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass

from core.components.benchmarks.benchmark_models import (
    PromptVersion,
    MutationType,
    FailureAnalysis,
)
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
from core.infrastructure.logging.event_types import LogEventType

if TYPE_CHECKING:
    from core.infrastructure.logging.session import LoggingSession

from .root_cause_analyzer import RootCause
from .example_extractor import Example, ErrorExample


@dataclass
class GenerationConfig:
    """Конфигурация PromptGenerator"""
    temperature: float = 0.7
    max_tokens: int = 4000
    top_p: float = 0.9
    diversity_threshold: float = 0.3  # Минимальная разница между кандидатами
    max_candidates: int = 5  # Максимум кандидатов за итерацию


class PromptGenerator:
    """
    Генератор промптов с умными стратегиями мутаций.

    RESPONSIBILITIES:
    - Генерация кандидатов на основе failure analysis
    - Применение стратегий мутаций
    - Обеспечение детерминированности
    - Отслеживание lineage версий

    MUTATION STRATEGIES:
    - ADD_EXAMPLES: добавление примеров для сложных кейсов
    - ADD_CONSTRAINTS: добавление ограничений для валидации
    - SIMPLIFY: упрощение формулировок
    - ERROR_FIX: исправление конкретных ошибок

    USAGE:
    ```python
    generator = PromptGenerator(event_bus, llm_callback)
    candidates = await generator.generate(parent_version, failure_analysis)
    ```
    """

    def __init__(
        self,
        event_bus: UnifiedEventBus,
        llm_callback=None,  # Optional callback for LLM generation
        config: Optional[GenerationConfig] = None,
        log_session: Optional['LoggingSession'] = None
    ):
        """
        Инициализация PromptGenerator.

        ARGS:
        - event_bus: шина событий
        - llm_callback: callback для LLM генерации (prompt) -> str
        - config: конфигурация
        - log_session: сессия логирования
        """
        self.event_bus = event_bus
        self.llm_callback = llm_callback
        self.config = config or GenerationConfig()
        self._log_session = log_session

        # История генераций для отслеживания diversity
        self._generation_history: List[Dict[str, Any]] = []

    def _get_logger(self) -> logging.Logger:
        """Получение логгера из log_session или fallback."""
        if self._log_session and self._log_session.app_logger:
            return self._log_session.app_logger
        return logging.getLogger(__name__)

    async def generate(
        self,
        parent: PromptVersion,
        failure_analysis: FailureAnalysis
    ) -> List[PromptVersion]:
        """
        Генерация кандидатов на основе parent версии и анализа неудач.

        ARGS:
        - parent: родительская версия
        - failure_analysis: анализ неудач

        RETURNS:
        - List[PromptVersion]: список кандидатов
        """
        self._get_logger().info(
            f"Генерация кандидатов на основе {parent.id}",
            extra={"event_type": LogEventType.TOOL_CALL}
        )

        candidates = []

        # Определение стратегий мутаций на основе failure analysis
        strategies = self._select_strategies(failure_analysis)

        # Генерация кандидатов для каждой стратегии
        for strategy in strategies:
            candidate = await self._generate_candidate(
                parent=parent,
                mutation_type=strategy,
                failure_analysis=failure_analysis
            )
            if candidate:
                candidates.append(candidate)

        # Проверка diversity
        candidates = self._ensure_diversity(candidates)

        self._get_logger().info(
            f"Сгенерировано {len(candidates)} кандидатов",
            extra={"event_type": LogEventType.TOOL_CALL}
        )

        return candidates[:self.config.max_candidates]

    def _select_strategies(
        self,
        failure_analysis: FailureAnalysis
    ) -> List[MutationType]:
        """
        Выбор стратегий мутаций на основе анализа неудач.

        ARGS:
        - failure_analysis: анализ неудач

        RETURNS:
        - List[MutationType]: список стратегий
        """
        strategies = []

        # Анализ типов ошибок
        top_categories = failure_analysis.get_top_failure_categories(3)

        for category, count in top_categories:
            category_lower = category.lower()

            # Выбор стратегии на основе типа ошибки
            if 'syntax' in category_lower or 'parse' in category_lower:
                strategies.append(MutationType.ADD_EXAMPLES)
            elif 'validation' in category_lower or 'schema' in category_lower:
                strategies.append(MutationType.ADD_CONSTRAINTS)
            elif 'complex' in category_lower or 'confusing' in category_lower:
                strategies.append(MutationType.SIMPLIFY)
            elif 'error' in category_lower or 'fail' in category_lower:
                strategies.append(MutationType.ERROR_FIX)

        # Добавление default стратегий если пусто
        if not strategies:
            strategies = [MutationType.SIMPLIFY, MutationType.ADD_CONSTRAINTS]

        # Удаление дубликатов
        return list(set(strategies))

    async def _generate_candidate(
        self,
        parent: PromptVersion,
        mutation_type: MutationType,
        failure_analysis: FailureAnalysis
    ) -> Optional[PromptVersion]:
        """
        Генерация одного кандидата.

        ARGS:
        - parent: родительская версия
        - mutation_type: тип мутации
        - failure_analysis: анализ неудач

        RETURNS:
        - Optional[PromptVersion]: кандидат или None
        """
        try:
            # Формирование промпта для мутации
            mutation_prompt = self._build_mutation_prompt(
                parent=parent,
                mutation_type=mutation_type,
                failure_analysis=failure_analysis
            )

            # Генерация через LLM или callback
            if self.llm_callback:
                new_content = await self.llm_callback(mutation_prompt)
            else:
                # Default генерация (для тестов)
                new_content = self._apply_mutation(
                    parent.prompt,
                    mutation_type,
                    failure_analysis
                )

            # Создание новой версии
            new_version = self._create_version(
                parent=parent,
                content=new_content,
                mutation_type=mutation_type
            )

            return new_version

        except Exception as e:
            self._get_logger().error(
                f"Ошибка генерации кандидата: {e}",
                extra={"event_type": LogEventType.ERROR}
            )
            return None

    def _build_mutation_prompt(
        self,
        parent: PromptVersion,
        mutation_type: MutationType,
        failure_analysis: FailureAnalysis
    ) -> str:
        """
        Построение промпта для мутации.

        ARGS:
        - parent: родительская версия
        - mutation_type: тип мутации
        - failure_analysis: анализ неудач

        RETURNS:
        - str: промпт для LLM
        """
        top_failures = failure_analysis.get_top_failure_categories(3)
        failures_text = "\n".join([f"- {cat}: {count} раз" for cat, count in top_failures])

        mutation_instructions = {
            MutationType.ADD_EXAMPLES: f"""
ДОБАВЬ ПРИМЕРЫ для обработки следующих типов ошибок:
{failures_text}

Сохраняй структуру оригинального промпта.
Добавь раздел с примерами для каждого типа ошибки.
""",
            MutationType.ADD_CONSTRAINTS: f"""
ДОБАВЬ ОГРАНИЧЕНИЯ и правила валидации для:
{failures_text}

Добавь явные проверки для каждого типа ошибки.
Укажи что делать в случае нарушения ограничений.
""",
            MutationType.SIMPLIFY: f"""
УПРОСТИ формулировки промпта.

Проблемные области:
{failures_text}

Сделай инструкции более конкретными и однозначными.
Убери избыточные формулировки.
Разбей сложные инструкции на шаги.
""",
            MutationType.ERROR_FIX: f"""
ИСПРАВЬ ОШИБКИ на основе анализа неудач:
{failures_text}

Добавь обработку для каждого типа ошибки.
Укажи явное поведение в ошибочных ситуациях.
"""
        }

        return f"""
ОРИГИНАЛЬНЫЙ ПРОМПТ:
{parent.prompt}

ТИП МУТАЦИИ: {mutation_type.value}

{mutation_instructions.get(mutation_type, "")}

НОВЫЙ ПРОМПТ:
"""

    def _apply_mutation(
        self,
        prompt: str,
        mutation_type: MutationType,
        failure_analysis: FailureAnalysis
    ) -> str:
        """
        Применение мутации к промпту (default реализация).

        ARGS:
        - prompt: оригинальный промпт
        - mutation_type: тип мутации
        - failure_analysis: анализ неудач

        RETURNS:
        - str: мутированный промпт
        """
        top_failures = failure_analysis.get_top_failure_categories(3)

        if mutation_type == MutationType.ADD_EXAMPLES:
            examples_section = "\n\n# ПРИМЕРЫ ОБРАБОТКИ ОШИБОК:\n"
            for category, _ in top_failures:
                examples_section += f"# Для ошибок типа '{category}':\n"
                examples_section += f"# Пример: [input] -> [corrected output]\n"
            return prompt + examples_section

        elif mutation_type == MutationType.ADD_CONSTRAINTS:
            constraints_section = "\n\n# ОГРАНИЧЕНИЯ И ПРОВЕРКИ:\n"
            for category, _ in top_failures:
                constraints_section += f"- Проверять корректность для случая: {category}\n"
            return prompt + constraints_section

        elif mutation_type == MutationType.SIMPLIFY:
            # Упрощение - удаление избыточных слов
            simplified = prompt.replace("пожалуйста", "")
            simplified = simplified.replace("необходимо", "нужно")
            simplified = simplified.replace("следует", "надо")
            return simplified

        elif mutation_type == MutationType.ERROR_FIX:
            error_section = "\n\n# ОБРАБОТКА ОШИБОК:\n"
            for category, _ in top_failures:
                error_section += f"- При ошибке '{category}': повторить попытку с исправлениями\n"
            return prompt + error_section

        return prompt

    def _create_version(
        self,
        parent: PromptVersion,
        content: str,
        mutation_type: MutationType
    ) -> PromptVersion:
        """
        Создание новой версии промпта.

        ARGS:
        - parent: родительская версия
        - content: содержимое промпта
        - mutation_type: тип мутации

        RETURNS:
        - PromptVersion: новая версия
        """
        # Генерация уникального ID
        version_id = self._generate_version_id(parent.id, content)

        return PromptVersion(
            id=version_id,
            parent_id=parent.id,
            capability=parent.capability,
            prompt=content,
            status='candidate',
            mutation_type=mutation_type,
            created_at=datetime.now()
        )

    def _generate_version_id(self, parent_id: str, content: str) -> str:
        """
        Генерация уникального ID версии.

        ARGS:
        - parent_id: ID родительской версии
        - content: содержимое промпта

        RETURNS:
        - str: уникальный ID
        """
        hash_input = f"{parent_id}:{content}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        return f"v_{hash_value}"

    def _ensure_diversity(
        self,
        candidates: List[PromptVersion]
    ) -> List[PromptVersion]:
        """
        Обеспечение разнообразия кандидатов.

        Каждый кандидат создан от одного baseline, но добавляет уникальные
        улучшения для разных capabilities. Сравниваем только capability names
        в добавленном тексте.
        """
        if len(candidates) <= 1:
            return candidates

        baseline_len = len(candidates[0].prompt)
        diverse = [candidates[0]]

        for candidate in candidates[1:]:
            is_diverse = True
            for selected in diverse:
                diff_a = selected.prompt[baseline_len:]
                diff_b = candidate.prompt[baseline_len:]

                if not diff_a or not diff_b:
                    is_diverse = False
                    break

                # Извлекаем capability names из diff
                caps_a = set()
                caps_b = set()
                for cap_marker in ['planning.', 'execute', 'search', 'unknown', 'analyze']:
                    if cap_marker in diff_a:
                        caps_a.add(cap_marker)
                    if cap_marker in diff_b:
                        caps_b.add(cap_marker)

                # Если capabilities разные — кандидаты diverse
                if caps_a != caps_b:
                    is_diverse = True
                else:
                    # Fallback: сравниваем первые 30 символов
                    prefix_a = diff_a[:30].lower()
                    prefix_b = diff_b[:30].lower()
                    similarity = self._calculate_similarity(prefix_a, prefix_b)
                    is_diverse = similarity <= 0.5

                if not is_diverse:
                    break

            if is_diverse:
                diverse.append(candidate)

        return diverse

    def _calculate_similarity(self, text_a: str, text_b: str) -> float:
        """
        Расчёт схожести двух текстов.

        ARGS:
        - text_a: первый текст
        - text_b: второй текст

        RETURNS:
        - float: схожесть (0.0-1.0)
        """
        # Простая реализация на основе общих слов
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b

        return len(intersection) / len(union) if union else 0.0

    def record_generation(
        self,
        parent_id: str,
        candidate_ids: List[str],
        mutation_types: List[MutationType]
    ) -> None:
        """
        Запись генерации в историю.

        ARGS:
        - parent_id: ID родительской версии
        - candidate_ids: ID кандидатов
        - mutation_types: типы применённых мутаций
        """
        self._generation_history.append({
            'timestamp': datetime.now().isoformat(),
            'parent_id': parent_id,
            'candidate_ids': candidate_ids,
            'mutation_types': [mt.value for mt in mutation_types]
        })

    def get_diversity_stats(self) -> Dict[str, Any]:
        """
        Получение статистики diversity генераций.

        RETURNS:
        - Dict[str, Any]: статистика
        """
        if not self._generation_history:
            return {'total_generations': 0}

        mutation_counts = {}
        for record in self._generation_history:
            for mt in record.get('mutation_types', []):
                mutation_counts[mt] = mutation_counts.get(mt, 0) + 1

        return {
            'total_generations': len(self._generation_history),
            'mutation_type_distribution': mutation_counts,
            'diversity_types': len(mutation_counts)
        }

    # ============================================================
    # НОВЫЙ API: Генерация на основе root causes и examples
    # ============================================================

    async def generate_improvements(
        self,
        original_prompt: PromptVersion,
        root_causes: List[RootCause],
        good_examples: Optional[List[Example]] = None,
        error_examples: Optional[List[ErrorExample]] = None
    ) -> List[PromptVersion]:
        """
        Генерация улучшенных промптов на основе root causes и examples.

        Это API который использует:
        - RootCauseAnalyzer для понимания проблем
        - ExampleExtractor для few-shot примеров

        ARGS:
        - original_prompt: оригинальная версия промпта
        - root_causes: корневые причины проблем
        - good_examples: хорошие примеры выполнения
        - error_examples: примеры ошибок

        RETURNS:
        - List[PromptVersion]: список улучшенных кандидатов
        """
        self._get_logger().info(
            f"Генерация улучшений на основе {len(root_causes)} root causes",
            extra={"event_type": LogEventType.TOOL_CALL}
        )

        candidates = []

        # Группировка root causes по типу проблемы
        causes_by_type = self._group_causes_by_type(root_causes)
        print(f"  🔍 [PromptGen] Groups: {len(causes_by_type)}")

        # Генерация кандидатов для каждого типа проблемы
        for cause_type, causes in causes_by_type.items():
            try:
                candidate = await self._generate_targeted_improvement(
                    parent=original_prompt,
                    causes=causes,
                    good_examples=good_examples,
                    error_examples=error_examples
                )
                if candidate:
                    candidates.append(candidate)
                    print(f"  ✅ [PromptGen] Candidate created for group: {cause_type}")
                else:
                    print(f"  ❌ [PromptGen] _generate_targeted_improvement returned None for: {cause_type}")
            except Exception as e:
                print(f"  ❌ [PromptGen] Exception for group '{cause_type}': {e}")

        # Если нет root causes, используем примеры
        if not candidates and good_examples:
            candidate = await self._generate_from_examples(
                parent=original_prompt,
                good_examples=good_examples
            )
            if candidate:
                candidates.append(candidate)

        # Обеспечение diversity
        print(f"  🔍 [PromptGen] Before diversity: {len(candidates)} candidates")
        # Когда все кандидаты созданы от одного baseline с разными capabilities,
        # diversity filter слишком агрессивен. Пропускаем его если кандидатов > 1
        # и все они имеют разные cause_type keys
        if len(causes_by_type) > 1 and len(candidates) > 1:
            print(f"  🔍 [PromptGen] Skipping diversity — {len(causes_by_type)} distinct cause types")
        else:
            candidates = self._ensure_diversity(candidates)
        print(f"  🔍 [PromptGen] After diversity: {len(candidates)} candidates")

        self._get_logger().info(
            f"Сгенерировано {len(candidates)} улучшенных кандидатов",
            extra={"event_type": LogEventType.TOOL_CALL}
        )

        return candidates[:self.config.max_candidates]

    def _group_causes_by_type(
        self,
        root_causes: List[RootCause]
    ) -> Dict[str, List[RootCause]]:
        """Группировка root causes по типу причины"""
        grouped = {}
        for cause in root_causes:
            # Используем cause + affected_capabilities как ключ для более детальной группировки
            cap_key = cause.affected_capabilities[0] if cause.affected_capabilities else 'unknown'
            group_key = f"{cap_key}:{cause.cause}"
            if group_key not in grouped:
                grouped[group_key] = []
            grouped[group_key].append(cause)
        return grouped

    async def _generate_targeted_improvement(
        self,
        parent: PromptVersion,
        causes: List[RootCause],
        good_examples: Optional[List[Example]] = None,
        error_examples: Optional[List[ErrorExample]] = None
    ) -> Optional[PromptVersion]:
        """
        Генерация целевого улучшения для конкретной проблемы.

        ARGS:
        - parent: родительская версия
        - causes: список причин
        - good_examples: хорошие примеры
        - error_examples: примеры ошибок

        RETURNS:
        - Optional[PromptVersion]: улучшенная версия
        """
        # Определение типа мутации на основе причины
        mutation_type = self._select_mutation_type(causes)

        # Формирование улучшений — делаем их уникальными для каждой группы
        improvements = []

        # Добавляем capability-specific контекст
        caps = set()
        for cause in causes:
            caps.update(cause.affected_capabilities)

        cap_context = ", ".join(c for c in caps if c != 'unknown') or "все компоненты"

        improvements.append(f"# IMPROVEMENT FOR: {cap_context}")
        improvements.append(f"# Problem type: {mutation_type.value}")

        for cause in causes:
            # Делаем каждый фикс уникальным, добавляя контекст
            cap_context_for_cause = ", ".join(cause.affected_capabilities) if cause.affected_capabilities else "общий"
            improvements.append(f"## FIX ({cap_context_for_cause}): {cause.fix}")
            if cause.related_issues:
                improvements.append(f"   Related issues: {', '.join(cause.related_issues)}")

        # Добавление примеров если есть
        if good_examples:
            improvements.append("\n# GOOD EXAMPLES:")
            for ex in good_examples[:2]:
                improvements.append(ex.to_prompt_format())

        if error_examples:
            improvements.append("\n# COMMON MISTAKES TO AVOID:")
            for ex in error_examples[:2]:
                improvements.append(ex.to_prompt_format())

        # Применение улучшения к промпту
        new_content = parent.prompt + "\n\n" + "\n".join(improvements)

        # Создание новой версии
        return self._create_version(
            parent=parent,
            content=new_content,
            mutation_type=mutation_type
        )

    async def _generate_from_examples(
        self,
        parent: PromptVersion,
        good_examples: List[Example]
    ) -> Optional[PromptVersion]:
        """
        Генерация улучшения только на основе примеров.

        ARGS:
        - parent: родительская версия
        - good_examples: хорошие примеры

        RETURNS:
        - Optional[PromptVersion]: улучшенная версия
        """
        examples_section = "\n\n# FEW-SHOT EXAMPLES:\n"
        for i, ex in enumerate(good_examples[:3], 1):
            examples_section += f"\n## Example {i}:\n"
            examples_section += ex.to_prompt_format()
            examples_section += "\n"

        new_content = parent.prompt + examples_section

        return self._create_version(
            parent=parent,
            content=new_content,
            mutation_type=MutationType.ADD_EXAMPLES
        )

    def _select_mutation_type(self, causes: List[RootCause]) -> MutationType:
        """
        Выбор типа мутации на основе причин.

        ARGS:
        - causes: список причин

        RETURNS:
        - MutationType: тип мутации
        """
        # Анализ причин
        cause_texts = [c.cause.lower() for c in causes]
        issue_types = [i for c in causes for i in c.related_issues]

        # Выбор на основе ключевых слов
        if any('пример' in t or 'example' in t for t in cause_texts + issue_types):
            return MutationType.ADD_EXAMPLES
        elif any('ограничен' in t or 'constraint' in t for t in cause_texts + issue_types):
            return MutationType.ADD_CONSTRAINTS
        elif any('ошиб' in t or 'error' in t for t in cause_texts + issue_types):
            return MutationType.ERROR_FIX
        elif any('неоднознач' in t or 'ambiguous' in t for t in cause_texts + issue_types):
            return MutationType.SIMPLIFY
        else:
            # Default
            return MutationType.ADD_EXAMPLES
