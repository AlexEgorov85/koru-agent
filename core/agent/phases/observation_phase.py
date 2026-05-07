"""
Фаза наблюдения: унифицированный анализ результата.

АРХИТЕКТУРА:
- observation_phase.analyze() — единая точка входа
- Вся логика анализа (rule-based + LLM) находится здесь
- Возвращает СТРОГО ObservationResult (Pydantic модель из state.py)
- Использует format_observation для умного форматирования данных
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from core.agent.state import ObservationResult
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
from core.models.data.execution import ExecutionResult, ExecutionStatus


class ObservationPhase:
    """
    Унифицированная фаза наблюдения.

    Единая точка входа для анализа результата выполнения.
    Содержит всю логику анализа (rule-based + LLM).
    Возвращает СТРОГО ObservationResult (Pydantic модель).
    """

    # Настройки — LLM используется только при ошибках и пустых данных

    # Пороги сжатия данных
    LARGE_DATA_ROW_THRESHOLD = 5        # > 5 строк — считать данные большими, не писать сырые в observation
    VERY_LARGE_DATA_ROW_THRESHOLD = 100  # > 100 строк — требовать data_analysis.analyze_step_data
    MAX_EXAMPLES_TO_SHOW = 3              # Сколько примеров строк показывать в key_findings
    MAX_PREVIEW_CHARS = 100               # Лимит символов для preview текста
    MAX_TEXT_LENGTH = 500                 # Лимит символов для текстовых результатов
    MAX_KEYS_TO_PREVIEW = 3                # Сколько ключей показывать в preview строки

    # Настройки форматирования (аналогично observation_formatter.py)
    TABLE_MAX_ROWS = 10                     # Максимум строк в табличном выводе
    TABLE_MAX_KEYS = 5                      # Максимум ключей для preview
    EMOJI_DATA = "📊"                       # Данные
    EMOJI_WARNING = "⚠️"                    # Предупреждение
    EMOJI_ANALYZE = "💡"                    # Требуется анализ

    def __init__(
        self,
        metrics: Any,
        policy: Any,
        log: logging.Logger,
        event_bus: Any,
        application_context: Any = None,
    ):
        self.metrics = metrics
        self.policy = policy
        self.log = log
        self.event_bus = event_bus
        self.application_context = application_context

    def _normalize_result(self, result: Any) -> Dict[str, Any]:
        """
        Нормализация любого результата в унифицированный формат.

        ВОЗВРАЩАЕТ:
        - dict с ключами: data_type, count, items, sample, query
        """
        if result is None:
            return {"data_type": "none", "count": 0, "items": [], "sample": None, "query": ""}

        # Pydantic модели -> dict
        if hasattr(result, 'model_dump'):
            result = result.model_dump()
        elif hasattr(result, 'dict'):
            result = result.dict()

        # SQL результаты (dict с rows)
        if isinstance(result, dict) and ("rows" in result or "rowcount" in result):
            rows = result.get("rows", [])
            return {
                "data_type": "sql",
                "count": len(rows) if rows else result.get("rowcount", 0),
                "items": rows if rows else [],
                "sample": rows[0] if rows else None,
                "query": result.get("query", ""),
            }

        # Vector search (list словарей с score)
        if isinstance(result, list) and len(result) > 0:
            first = result[0]
            if isinstance(first, dict) and "score" in first:
                return {
                    "data_type": "vector_search",
                    "count": len(result),
                    "items": result,
                    "sample": first,
                    "query": result[0].get("query", "") if isinstance(result, dict) and "query" in result else "",
                }

        # Обычный список
        if isinstance(result, list):
            return {
                "data_type": "list",
                "count": len(result),
                "items": result,
                "sample": result[0] if result else None,
                "query": "",
            }

        # Словарь
        if isinstance(result, dict):
            return {
                "data_type": "dict",
                "count": len(result),
                "items": list(result.items())[:self.MAX_KEYS_TO_PREVIEW],
                "sample": result,
                "query": "",
            }

        # Всё остальное
        return {
            "data_type": "text",
            "count": 1,
            "items": [str(result)[:self.MAX_PREVIEW_CHARS]],
            "sample": str(result)[:self.MAX_PREVIEW_CHARS],
            "query": "",
        }

    def _build_observation(self, normalized: Dict[str, Any], action_name: str) -> Dict[str, Any]:
        """
        Единая логика формирования observation на основе нормализованных данных.

        ВОЗВРАЩАЕТ:
        - dict с ключами: observation_text, key_findings, next_step_suggestion, completeness
        """
        data_type = normalized["data_type"]
        count = normalized["count"]
        items = normalized["items"]
        sample = normalized["sample"]

        observation_text = ""
        key_findings = []
        completeness = 1.0
        reliability = 0.8
        next_step_suggestion = "Продолжить следующий шаг на основе прогресса цели"

        # Если данных МНОГО — ТОЛЬКО СВОДКА (без сырых данных в observation)
        if count > self.LARGE_DATA_ROW_THRESHOLD:
            observation_text = (
                f"{self.EMOJI_OBSERVATION} НАБЛЮДЕНИЕ (тип: {data_type})\n"
                f"{self.EMOJI_DATA} Получено {count} строк. "
                f"{self.EMOJI_ANALYZE} Для полного анализа используйте data_analysis.analyze_step_data"
            )

            # Добавляем примеры в key_findings (всегда)
            for i, item in enumerate(items[:self.MAX_EXAMPLES_TO_SHOW]):
                if isinstance(item, dict):
                    if data_type == "vector_search":
                        score = item.get('score', 0)
                        text = item.get('matched_text', item.get('content', str(item)))[:self.MAX_PREVIEW_CHARS]
                        key_findings.append(f"[{i+1}] (score={score:.2f}) {text}")
                    else:
                        preview = {k: v for k, v in list(item.items())[:self.MAX_KEYS_TO_PREVIEW]}
                        key_findings.append(f"[{i+1}] {preview}")
                else:
                    key_findings.append(f"[{i+1}] {str(item)[:self.MAX_PREVIEW_CHARS]}")

            if count > self.MAX_EXAMPLES_TO_SHOW:
                key_findings.append(f"... ещё {count - self.MAX_EXAMPLES_TO_SHOW} элементов")

            # Если ДЕЙСТВИТЕЛЬНО МНОГО — требуем вызов data_analysis
            if count > self.VERY_LARGE_DATA_ROW_THRESHOLD:
                next_step_suggestion = (
                    f"Обнаружено слишком много данных ({count} записей). "
                    f"Для анализа ОБЯЗАТЕЛЬНО запустите навык data_analysis.analyze_step_data."
                )
        else:
            # Данных мало — можно показать подробности
            if data_type == "sql":
                key_findings.append(f"{self.EMOJI_DATA} Получено {count} строк")
                # Форматирование таблицей (аналогично observation_formatter.py)
                if items:
                    lines = []
                    for i, row in enumerate(items[:self.TABLE_MAX_ROWS]):
                        if isinstance(row, dict):
                            line = "| " + " | ".join(str(v) for v in row.values()) + " |"
                            lines.append(line)
                        else:
                            lines.append(f"| {row} |")
                    if count > self.TABLE_MAX_ROWS:
                        lines.append(f"... и ещё {count - self.TABLE_MAX_ROWS} записей")
                    observation_text = "\n".join(lines)
                else:
                    observation_text = "Запрос выполнен, данных не найдено"

                # Примеры строк (в key_findings)
                for i, row in enumerate(items[:self.MAX_EXAMPLES_TO_SHOW]):
                    if isinstance(row, dict):
                        preview = {k: v for k, v in list(row.items())[:self.TABLE_MAX_KEYS]}
                        key_findings.append(f"[{i+1}] {preview}")

            elif data_type == "vector_search":
                query_text = f" for query: {normalized.get('query', '')[:self.MAX_PREVIEW_CHARS]}" if normalized.get('query') else ""
                observation_text = f"{self.EMOJI_DATA} Найдено {count} результатов{query_text}"
                key_findings.append(f"{self.EMOJI_DATA} Найдено {count} результатов")

                for i, r in enumerate(items[:self.MAX_EXAMPLES_TO_SHOW]):
                    if isinstance(r, dict):
                        score = r.get('score', 0)
                        text = r.get('matched_text', r.get('content', str(r)))[:self.MAX_PREVIEW_CHARS]
                        key_findings.append(f"[{i+1}] (score={score:.2f}) {text}")

            elif data_type == "list":
                key_findings.append(f"{self.EMOJI_DATA} Список содержит {count} элементов")
                try:
                    observation_text = json.dumps(items, ensure_ascii=False, indent=2, default=str)[:self.MAX_TEXT_LENGTH]
                except (TypeError, ValueError):
                    observation_text = str(items)[:self.MAX_TEXT_LENGTH]

            elif data_type == "dict":
                key_findings.append(f"{self.EMOJI_DATA} Словарь содержит {count} ключей")
                try:
                    observation_text = json.dumps(sample, ensure_ascii=False, indent=2, default=str)[:self.MAX_TEXT_LENGTH]
                except (TypeError, ValueError):
                    observation_text = str(sample)[:self.MAX_TEXT_LENGTH]

            else: # text
                observation_text = str(sample)[:self.MAX_TEXT_LENGTH]
                key_findings.append(f"{self.EMOJI_DATA} Текстовый результат: {observation_text[:50]}")

            if count > self.MAX_EXAMPLES_TO_SHOW:
                key_findings.append(f"... ещё {count - self.MAX_EXAMPLES_TO_SHOW} элементов")

            completeness = 0.8 if count < 5 else 1.0

        return {
            "observation_text": observation_text,
            "key_findings": key_findings,
            "next_step_suggestion": next_step_suggestion,
            "completeness": completeness,
            "reliability": reliability,
        }

    def _rule_based_observation(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: Any,
        error: Optional[str] = None,
    ) -> ObservationResult:
        """
        Rule-based анализ результата без вызова LLM.

        Вся логика сжатия данных — в _normalize_result и _build_observation.
        """
        # Ошибки обрабатываем отдельно
        if error:
            return self._handle_error_observation(action_name, parameters, error)

        # Пустота результата
        if result is None or (isinstance(result, (list, dict)) and len(result) == 0):
            return ObservationResult(
                status="empty",
                observation="Получен пустой результат",
                key_findings=[f"Действие '{action_name}' не вернуло данных"],
                data_quality={"completeness": 0.0, "reliability": 0.5},
                errors=[],
                next_step_suggestion="Попробуйте другие параметры или проверьте доступность данных",
                requires_additional_action=True,
                rule_based=True,
            )

        # Нормализация и построение наблюдения (единый путь для всех типов данных)
        normalized = self._normalize_result(result)
        built = self._build_observation(normalized, action_name)

        # Проверяем warning-флаги для словарей
        reliability = built["reliability"]
        if isinstance(result, dict):
            if result.get('warning') or result.get('truncated'):
                reliability = 0.6
                built["key_findings"].append(f"Предупреждение: {result.get('warning', 'Результат обрезан')}")
                self.log.info(
                    f"⚠️ [Observation] Результат имеет предупреждения: {result.get('warning', 'N/A')}",
                    extra={"event_type": EventType.WARNING},
                )

        return ObservationResult(
            status="success",
            observation=built["observation_text"],
            key_findings=built["key_findings"],
            data_quality={"completeness": built["completeness"], "reliability": reliability},
            errors=[],
            next_step_suggestion=built["next_step_suggestion"],
            requires_additional_action=built["completeness"] == 0.0,
            rule_based=True,
        )

    def _handle_error_observation(
        self, action_name: str, parameters: Dict[str, Any], error: str
    ) -> ObservationResult:
        """Обработка ошибки в rule-based режиме."""
        # Проверяем, это ошибка валидации?
        is_validation_error = any(
            keyword in error.lower()
            for keyword in ['validation error', 'field required', 'input should be', 'extra fields not permitted']
        )

        if is_validation_error:
            validation_details = self._extract_validation_details(error)
            observation_text = (
                f"Ошибка валидации параметров для '{action_name}'. "
                f"Переданные параметры: {parameters}. "
                f"Проблема: {validation_details['summary']}"
            )
            key_findings = [
                f"Параметры не прошли валидацию",
                f"Передано: {list(parameters.keys()) if parameters else 'нет параметров'}",
                f"Ошибка: {validation_details['summary']}"
            ]
            if validation_details['missing_fields']:
                key_findings.append(f"Отсутствуют обязательные поля: {validation_details['missing_fields']}")
            if validation_details['invalid_fields']:
                key_findings.append(f"Неверный тип у полей: {validation_details['invalid_fields']}")

            return ObservationResult(
                status="error",
                observation=observation_text,
                key_findings=key_findings,
                data_quality={"completeness": 0.0, "reliability": 0.0},
                errors=[validation_details['summary']],
                next_step_suggestion=(
                    f"Исправьте параметры для '{action_name}'. "
                    f"Убедитесь что все обязательные поля присутствуют и имеют правильный тип."
                ),
                requires_additional_action=True,
                rule_based=True,
            )

        return ObservationResult(
            status="error",
            observation=f"Ошибка выполнения: {error}",
            key_findings=[f"Действие '{action_name}' не выполнено"],
            data_quality={"completeness": 0.0, "reliability": 0.0},
            errors=[error],
            next_step_suggestion="Повторить с другими параметрами или используйте стратегию восстановления",
            requires_additional_action=True,
            rule_based=True,
        )

    async def _run_llm_analysis(
        self,
        result: ExecutionResult,
        action: str,
        parameters: Dict[str, Any],
        session_id: str,
        step_number: int,
    ) -> ObservationResult:
        """Запустить LLM анализ."""
        error = result.error if result.status == ExecutionStatus.FAILED else None
        result_data = result.data

        try:
            # Получаем контракт
            schema = None
            if self.application_context and hasattr(self.application_context, 'get_output_contract'):
                try:
                    output_contract = self.application_context.get_output_contract("behavior.react.observe")
                    if output_contract:
                        if hasattr(output_contract, 'model_json_schema'):
                            schema = output_contract.model_json_schema()
                        elif hasattr(output_contract, 'model_schema'):
                            schema = output_contract.model_schema()
                        elif isinstance(output_contract, dict):
                            schema = output_contract.get('schema_data')
                except Exception:
                    pass

            if schema is None:
                self.log.error(
                    "❌ [Observation] Не удалось загрузить схему контракта 'behavior.react.observe'. LLM будет вызван без строгой схемы!",
                    extra={"event_type": EventType.ERROR},
                )

            # Преобразуем результат в строку для LLM
            result_str = str(result_data) if result_data is not None else ""
            error_str = error or ""

            # Строим prompt
            prompt = self._build_observation_prompt(
                action_name=action,
                parameters=parameters,
                result=result_str,
                error=error_str,
            )

            self.log.info(
                f"👁️ [Observation] Анализ результата: action={action}, error={bool(error)}",
                extra={"event_type": EventType.INFO},
            )

            # Вызов LLM
            orchestrator = self._llm_orchestrator
            provider = self._llm_provider

            if not orchestrator or not provider:
                self.log.error("LLM orchestrator или provider не доступен")
                return self._fallback_observation(result_data, error)

            llm_request = LLMRequest(
                prompt=prompt,
                system_prompt="Ты — аналитик результатов выполнения действий агента. Твоя задача — объективно оценить результат и дать рекомендации.",
                temperature=0.2,
                max_tokens=800,
            structured_output=StructuredOutputConfig(
                output_model=None,
                schema_def=schema if schema else None,
                max_retries=2,
                strict_mode=False,
            ),
            )

            result_obj = await orchestrator.execute_structured(
                request=llm_request,
                provider=provider,
                session_id=session_id,
                agent_id="agent",
                step_number=step_number,
                phase='observe',
                use_native_structured_output=False,
            )

            if not result_obj or not hasattr(result_obj, 'parsed_content') or result_obj.parsed_content is None:
                self.log.error(f"LLM вернул невалидный ответ: {result_obj}")
                return self._fallback_observation(result_data, error)

            observation = result_obj.parsed_content

            # Конвертация в dict, потом в ObservationResult
            if hasattr(observation, 'model_dump'):
                obs_dict = observation.model_dump()
            elif hasattr(observation, 'dict'):
                obs_dict = observation.dict()
            elif isinstance(observation, dict):
                obs_dict = observation
            else:
                obs_dict = {"status": "partial", "observation": str(observation), "requires_additional_action": True}

            # Создаём ObservationResult из dict
            observation_result = ObservationResult(
                status=obs_dict.get('status', 'unknown'),
                observation=obs_dict.get('observation', ''),
                key_findings=obs_dict.get('key_findings', []),
                data_quality=obs_dict.get('data_quality', {}),
                errors=obs_dict.get('errors', []),
                next_step_suggestion=obs_dict.get('next_step_suggestion', ''),
                requires_additional_action=obs_dict.get('requires_additional_action', True),
                rule_based=False,
            )

            self.log.info(
                f"✅ [Observation] Наблюдение: status={obs_dict.get('status')}, quality={obs_dict.get('data_quality', {})}",
                extra={"event_type": EventType.INFO},
            )

            self.metrics.record_observer_call(used_llm=True)
            return observation_result

        except Exception as e:
            self.log.error(f"Ошибка в ObservationPhase LLM: {e}", exc_info=True)
            return self._fallback_observation(result_data, error)

    def _build_observation_prompt(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: str,
        error: str,
    ) -> str:
        """Построение prompt для анализа результата."""
        params_detail = ""
        if parameters:
            for key, value in parameters.items():
                params_detail += f"  - {key}: {value}\n"

        return f"""
ACTION: {action_name}

PARAMETERS:
{self._truncate(str(parameters), 500)}

PARAMETER DETAILS:
{params_detail if params_detail else "  (none)"}

RESULT:
{self._truncate(result, 1500)}

ERROR:
{error if error else "None"}

---

Проанализируй результат выполнения действия. ВАЖНО: твой ответ должен быть информативным и содержать конкретные данные из результата.

1. STATUS: Был ли результат успешным?
   - success: данные получены и полезны
   - partial: данные получены но неполные
   - empty: данных нет (пустой результат)
   - error: произошла ошибка

2. OBSERVATION: Напиши ПОДРОБНОЕ описание что именно получено.
   - Для vector_search: укажи количество найденных результатов, примеры найденных текстов с оценками (score)
   - Для SQL запросов: укажи количество строк, примеры данных из первых строк
   - Для других инструментов: опиши структуру и содержимое результата
   - Если данных МНОГО (более 5 строк или 1000 символов) — укажи статистику и напиши: "Для полного анализа используйте data_analysis.analyze_step_data"

3. KEY FINDINGS: Извлеки КОНКРЕТНЫЕ факты из данных (например, найденные тексты, значения полей, статистика)

4. DATA_QUALITY: Насколько качественны данные?
   - completeness: 0.0–1.0 (насколько полные данные)
   - reliability: 0.0–1.0 (насколько надёжны данные)

5. NEXT STEP SUGGESTION: Что делать дальше?
   - Если данных много — рекомендуй использовать data_analysis.analyze_step_data
   - Если данных недостаточно — предложи изменить параметры или использовать другой инструмент

Ответь в формате JSON согласно схеме. Поле "observation" должно содержать ДЕТАЛЬНОЕ описание с конкретными данными.
""".strip()

    def _format_result(self, result: Any) -> str:
        """Форматирование результата в строку (обрезаем до 1000 символов)."""
        if result is None:
            return "None"

        if isinstance(result, dict):
            data = (
                result.get('result') or
                result.get('data') or
                result.get('rows') or
                result.get('output') or
                result
            )
            return self._truncate(str(data), 1000)

        if hasattr(result, 'model_dump'):
            return self._truncate(str(result.model_dump()), 1000)

        if hasattr(result, 'dict'):
            return self._truncate(str(result.dict()), 1000)

        return self._truncate(str(result), 1000)

    def _truncate(self, text: str, max_length: int) -> str:
        """Обрезка текста до максимальной длины."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "... [обрезано]"

    def _fallback_observation(self, result: Any, error: Optional[str]) -> ObservationResult:
        """Fallback наблюдение при ошибке LLM."""
        if error:
            return ObservationResult(
                status="error",
                observation=f"Error during execution: {error}",
                key_findings=[],
                data_quality={"completeness": 0.0, "reliability": 0.0},
                errors=[error],
                next_step_suggestion="Попробуйте другой подход или исправьте ошибку",
                requires_additional_action=True,
                rule_based=True,
            )

        if result is None or (isinstance(result, (list, dict)) and len(result) == 0):
            return ObservationResult(
                status="empty",
                observation="Получен пустой результат",
                key_findings=[],
                data_quality={"completeness": 0.0, "reliability": 0.5},
                errors=[],
                next_step_suggestion="Попробуйте другие параметры или другой инструмент",
                requires_additional_action=True,
                rule_based=True,
            )

        return ObservationResult(
            status="partial",
            observation="Результат получен, но не проанализирован LLM",
            key_findings=["Result exists"],
            data_quality={"completeness": 0.5, "reliability": 0.5},
            errors=[],
            next_step_suggestion="Продолжайте с осторожностью",
            requires_additional_action=True,
            rule_based=True,
        )

    def _extract_validation_details(self, error: str) -> Dict[str, Any]:
        """Извлекает детали ошибки валидации Pydantic."""
        missing_fields = []
        invalid_fields = []
        summary = error

        lines = error.strip().split('\n')
        if lines:
            summary = lines[0].strip()
            prefix = "Валидация входных данных не пройдена: "
            if summary.startswith(prefix):
                summary = summary[len(prefix):]

        missing_pattern = r"(\w+)\n\s+Field required"
        missing_matches = re.findall(missing_pattern, error)
        missing_fields = list(missing_matches)

        invalid_pattern = r"(\w+)\n\s+Input should be"
        invalid_matches = re.findall(invalid_pattern, error)
        invalid_fields = list(invalid_matches)

        return {
            "summary": summary,
            "missing_fields": missing_fields,
            "invalid_fields": invalid_fields,
        }

    @property
    def _llm_orchestrator(self):
        """Получить LLM orchestrator из контекста."""
        if self.application_context and hasattr(self.application_context, 'llm_orchestrator'):
            return self.application_context.llm_orchestrator
        return None

    @property
    def _llm_provider(self):
        """Получить LLM провайдер из инфраструктурного контекста."""
        if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
            infra = self.application_context.infrastructure_context
            if infra.resource_registry:
                resource = infra.resource_registry.get_resource("default_llm")
                if resource:
                    return resource.instance
        return None
