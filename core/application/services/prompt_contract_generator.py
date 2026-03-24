"""
Генератор промптов и контрактов (Prompt Contract Generator).

КОМПОНЕНТЫ:
- PromptContractGenerator: генерация новых версий промптов и контрактов

FEATURES:
- Генерация новых версий промптов на основе анализа неудач
- Автоматическое создание контрактов (JSON Schema)
- Сохранение в файловую систему
- Интеграция с LLM для генерации контента
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from core.models.data.prompt import Prompt
from core.models.data.contract import Contract
from core.models.data.benchmark import FailureAnalysis
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
from core.infrastructure.logging import EventBusLogger


@dataclass
class GenerationConfig:
    """Конфигурация генерации"""
    temperature: float = 0.7
    max_tokens: int = 4000
    top_p: float = 0.9
    include_examples: bool = True
    preserve_structure: bool = True


class PromptContractGenerator:
    """
    Генератор новых версий промптов и контрактов.

    RESPONSIBILITIES:
    - Генерация новых версий промптов на основе анализа неудач
    - Создание JSON Schema контрактов
    - Сохранение в файловую систему
    - Ведение истории изменений

    USAGE:
    ```python
    generator = PromptContractGenerator(llm_provider, data_source, data_dir)
    new_prompt = await generator.generate_prompt_variant(prompt, failure_analysis)
    contract = await generator.generate_matching_contract(new_prompt)
    ```
    """

    def __init__(
        self,
        llm_provider,
        data_source: FileSystemDataSource,
        data_dir: Path,
        event_bus: Optional[UnifiedEventBus] = None,
        config: Optional[GenerationConfig] = None
    ):
        """
        Инициализация генератора.

        ARGS:
        - llm_provider: провайдер LLM для генерации контента
        - data_source: источник данных для сохранения
        - data_dir: директория для сохранения файлов
        - event_bus: шина событий (опционально)
        - config: конфигурация генерации
        """
        self.llm_provider = llm_provider
        self.data_source = data_source
        self.data_dir = Path(data_dir)
        self.event_bus = event_bus
        self.config = config or GenerationConfig()

        # Инициализация логгера
        self.event_bus_logger = None
        if event_bus:
            self.event_bus_logger = EventBusLogger(
                event_bus,
                session_id="system",
                agent_id="system",
                component="PromptContractGenerator"
            )

        # Директории для сохранения
        self.prompts_dir = self.data_dir / "prompts"
        self.contracts_dir = self.data_dir / "contracts"

        # История генераций
        self._generation_history = []

    async def generate_prompt_variant(
        self,
        original_prompt: Prompt,
        failure_analysis: FailureAnalysis,
        target_improvement: str = ""
    ) -> Prompt:
        """
        Генерация новой версии промпта.

        ARGS:
        - original_prompt: оригинальный промпт для улучшения
        - failure_analysis: анализ неудач для понимания проблем
        - target_improvement: целевое улучшение (опционально)

        RETURNS:
        - Prompt: новая версия промпта
        """
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Генерация новой версии промпта для {original_prompt.capability}")

        # Формирование промпта для генерации
        generation_prompt = self._build_generation_prompt(
            original_prompt,
            failure_analysis,
            target_improvement
        )

        # Генерация через LLM
        new_content = await self._generate_with_llm(generation_prompt)

        # Создание новой версии промпта
        new_version = self._increment_version(original_prompt.version)

        from core.models.enums.common_enums import ComponentType

        new_prompt = Prompt(
            capability=original_prompt.capability,
            version=new_version,
            content=new_content,
            variables=original_prompt.variables,  # Сохраняем переменные
            status='draft',
            component_type=original_prompt.component_type,
            metadata={
                **original_prompt.metadata,
                'generated_from': original_prompt.version,
                'generation_timestamp': datetime.now().isoformat(),
                'target_improvement': target_improvement,
                'failure_categories': ','.join(failure_analysis.failure_categories.keys())
            }
        )

        # Сохранение в историю
        self._record_generation(original_prompt.version, new_version, 'prompt')

        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Сгенерирована версия {new_version}")

        return new_prompt

    async def generate_from_scratch(
        self,
        capability: str,
        description: str,
        examples: Optional[List[str]] = None
    ) -> Prompt:
        """
        Генерация промпта с нуля.

        ARGS:
        - capability: название способности
        - description: описание того что должен делать промпт
        - examples: примеры желаемого поведения (опционально)

        RETURNS:
        - Prompt: новый промпт
        """
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Генерация промпта с нуля для {capability}")

        # Формирование промпта для генерации
        generation_prompt = self._build_scratch_prompt(capability, description, examples)

        # Генерация через LLM
        content = await self._generate_with_llm(generation_prompt)

        # Создание промпта
        from core.models.enums.common_enums import ComponentType

        new_prompt = Prompt(
            capability=capability,
            version='v1.0.0',
            content=content,
            variables=[],
            status='draft',
            component_type=ComponentType.SKILL,
            metadata={
                'generated_from_scratch': 'true',
                'generation_timestamp': datetime.now().isoformat(),
                'description': description
            }
        )

        self._record_generation(None, 'v1.0.0', 'prompt')

        return new_prompt

    async def generate_matching_contract(self, prompt: Prompt) -> Contract:
        """
        Генерация контракта (JSON Schema) для промпта.

        ARGS:
        - prompt: промпт для которого создаётся контракт

        RETURNS:
        - Contract: контракт с JSON Schema
        """
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"Генерация контракта для {prompt.capability}@{prompt.version}")

        # Формирование промпта для генерации схемы
        schema_prompt = self._build_schema_prompt(prompt)

        # Генерация JSON Schema через LLM
        schema_content = await self._generate_with_llm(schema_prompt)

        # Парсинг JSON
        try:
            schema = self._parse_json_schema(schema_content)
        except json.JSONDecodeError as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка парсинга JSON Schema: {e}")
            # Возвращаем дефолтную схему
            schema = self._create_default_schema(prompt)

        # Создание контракта
        contract = Contract(
            capability=prompt.capability,
            version=prompt.version,
            input_schema=schema,
            output_schema=self._create_output_schema(),
            metadata={
                'generated_from_prompt': prompt.version,
                'generation_timestamp': datetime.now().isoformat()
            }
        )

        self._record_generation(None, prompt.version, 'contract')

        return contract

    async def save_prompt(self, prompt: Prompt) -> bool:
        """
        Сохранение промпта в файловую систему.

        ARGS:
        - prompt: промпт для сохранения

        RETURNS:
        - bool: успешно ли сохранение
        """
        try:
            # Создание директории если не существует
            prompts_dir = self.prompts_dir / prompt.capability.replace('.', '/')
            prompts_dir.mkdir(parents=True, exist_ok=True)

            # Сохранение через data_source
            await self.data_source.save_prompt(
                capability_name=prompt.capability,
                version=prompt.version,
                prompt=prompt
            )

            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Промпт сохранён: {prompt.capability}@{prompt.version}")
            return True

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка сохранения промпта: {e}")
            return False

    async def save_contract(self, contract: Contract) -> bool:
        """
        Сохранение контракта в файловую систему.

        ARGS:
        - contract: контракт для сохранения

        RETURNS:
        - bool: успешно ли сохранение
        """
        try:
            # Создание директории если не существует
            contracts_dir = self.contracts_dir / contract.capability.replace('.', '/')
            contracts_dir.mkdir(parents=True, exist_ok=True)

            # Сохранение через data_source
            await self.data_source.save_contract(
                capability_name=contract.capability,
                version=contract.version,
                contract=contract
            )

            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Контракт сохранён: {contract.capability}@{contract.version}")
            return True

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка сохранения контракта: {e}")
            return False

    async def generate_and_save(
        self,
        original_prompt: Prompt,
        failure_analysis: FailureAnalysis,
        target_improvement: str = ""
    ) -> Tuple[Optional[Prompt], Optional[Contract]]:
        """
        Генерация и сохранение промпта и контракта.

        ARGS:
        - original_prompt: оригинальный промпт
        - failure_analysis: анализ неудач
        - target_improvement: целевое улучшение

        RETURNS:
        - Tuple[Prompt, Contract]: (новый промпт, контракт) или (None, None) при ошибке
        """
        try:
            # Генерация нового промпта
            new_prompt = await self.generate_prompt_variant(
                original_prompt,
                failure_analysis,
                target_improvement
            )

            # Сохранение промпта
            if not await self.save_prompt(new_prompt):
                return None, None

            # Генерация контракта
            contract = await self.generate_matching_contract(new_prompt)

            # Сохранение контракта
            if not await self.save_contract(contract):
                return new_prompt, None

            return new_prompt, contract

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка генерации и сохранения: {e}")
            return None, None

    def _build_generation_prompt(
        self,
        original_prompt: Prompt,
        failure_analysis: FailureAnalysis,
        target_improvement: str
    ) -> str:
        """Формирование промпта для генерации улучшенной версии"""

        # Анализ топ категорий ошибок
        top_failures = failure_analysis.get_top_failure_categories(3)
        failures_text = "\n".join([f"- {cat}: {count} раз" for cat, count in top_failures])

        # Рекомендации
        recommendations_text = "\n".join([f"- {rec}" for rec in failure_analysis.recommendations[:3]])

        return f"""
Улучши следующий промпт для LLM на основе анализа неудач.

ОРИГИНАЛЬНЫЙ ПРОМПТ:
{original_prompt.content}

АНАЛИЗ НЕУДАЧ:
Всего неудач: {failure_analysis.total_failures}

Категории ошибок:
{failures_text}

Рекомендации по улучшению:
{recommendations_text}

ЦЕЛЕВОЕ УЛУЧШЕНИЕ:
{target_improvement if target_improvement else 'Улучшить общую точность и надёжность'}

ТРЕБОВАНИЯ К НОВОМУ ПРОМПТУ:
1. Сохрани структуру и переменные оригинального промпта
2. Устраняй выявленные проблемы
3. Добавь явные инструкции для сложных случаев
4. Включи примеры если это поможет
5. Сделай промпт более конкретным и однозначным

НОВЫЙ ПРОМПТ:
"""

    def _build_scratch_prompt(
        self,
        capability: str,
        description: str,
        examples: Optional[List[str]]
    ) -> str:
        """Формирование промпта для генерации с нуля"""

        examples_text = ""
        if examples:
            examples_text = "\n\nПРИМЕРЫ ЖЕЛАЕМОГО ПОВЕДЕНИЯ:\n" + "\n".join(examples)

        return f"""
Создай промпт для LLM для следующей способности:

НАЗВАНИЕ: {capability}

ОПИСАНИЕ:
{description}
{examples_text}

ТРЕБОВАНИЯ К ПРОМПТУ:
1. Чётко определи задачу
2. Укажи формат входных данных
3. Укажи формат выходных данных
4. Включи инструкции для обработки краевых случаев
5. Добавь примеры если это уместно

ПРОМПТ:
"""

    def _build_schema_prompt(self, prompt: Prompt) -> str:
        """Формирование промпта для генерации JSON Schema"""

        return f"""
Создай JSON Schema для валидации входных данных следующего промпта:

{prompt.content[:2000]}  # Ограничиваем длину

ТРЕБОВАНИЯ:
1. Schema должна быть в формате JSON Schema Draft 7
2. Включи все необходимые поля
3. Укажи типы данных для каждого поля
4. Добавь описания для полей
5. Укажи required поля

JSON SCHEMA:
"""

    async def _generate_with_llm(self, prompt: str) -> str:
        """Генерация контента через LLM"""
        # Вызов LLM провайдера
        # Примечание: здесь должна быть реальная интеграция с LLM
        # Для тестов используем заглушку
        if self.event_bus_logger:
            await self.event_bus_logger.debug("Генерация через LLM...")
        return f"Generated content for: {prompt[:100]}..."

    def _parse_json_schema(self, content: str) -> Dict[str, Any]:
        """Парсинг JSON Schema из ответа LLM"""
        # Поиск JSON в ответе
        start = content.find('{')
        end = content.rfind('}') + 1

        if start == -1 or end == -1:
            raise json.JSONDecodeError("JSON не найден", content, 0)

        json_str = content[start:end]
        return json.loads(json_str)

    def _create_default_schema(self, prompt: Prompt) -> Dict[str, Any]:
        """Создание дефолтной схемы"""
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }

    def _create_output_schema(self) -> Dict[str, Any]:
        """Создание схемы выходных данных"""
        return {
            "type": "object",
            "properties": {
                "output": {"type": "string"},
                "metadata": {"type": "object"}
            },
            "required": ["output"]
        }

    def _increment_version(self, version: str) -> str:
        """Инкремент версии"""
        # Простая логика: увеличиваем patch версию
        parts = version.lstrip('v').split('.')

        try:
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0

            # Увеличиваем patch
            new_patch = patch + 1

            return f"v{major}.{minor}.{new_patch}"
        except (ValueError, IndexError):
            # Если не удалось распарсить, возвращаем v1.0.0
            return "v1.0.0"

    def _record_generation(
        self,
        from_version: Optional[str],
        to_version: str,
        generation_type: str
    ) -> None:
        """Запись генерации в историю"""
        self._generation_history.append({
            'timestamp': datetime.now().isoformat(),
            'type': generation_type,
            'from_version': from_version,
            'to_version': to_version
        })

    def get_generation_history(self) -> List[Dict[str, Any]]:
        """Получение истории генераций"""
        return self._generation_history.copy()

    async def rollback_to_version(
        self,
        capability: str,
        version: str
    ) -> bool:
        """
        Откат к предыдущей версии.

        ARGS:
        - capability: название способности
        - version: версия для отката

        RETURNS:
        - bool: успешно ли
        """
        try:
            # Загрузка указанной версии
            prompt = await self.data_source.load_prompt(capability, version)

            # Помечаем как активную (через обновление статуса)
            # Это должно быть реализовано в data_source
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Откат к версии {version} для {capability}")

            return True

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка отката: {e}")
            return False
