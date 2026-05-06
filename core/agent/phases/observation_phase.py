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

    # Настройки
    TRIGGER_MODE = "always"  # "always" | "on_error" | "on_empty"

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

    async def analyze(
        self,
        result: ExecutionResult,
        decision_action: str,
        decision_parameters: Dict[str, Any],
        session_context: Any,
        step_number: int,
    ) -> ObservationResult:
        """
        Унифицированный анализ результата.

        Args:
            result: ExecutionResult от ExecutionPhase
            decision_action: Название действия
            decision_parameters: Параметры действия
            session_context: Контекст сессии для регистрации
            step_number: Номер шага

        Returns:
            ObservationResult: Pydantic модель наблюдения (observation уже сжат при необходимости)
        """
        
        
        session_id = session_context.session_id if session_context else "unknown"

        # Определяем нужно ли LLM
        should_call_llm = self._should_call_llm(result)

        # Выполняем анализ
        if should_call_llm:
            observation_result = await self._run_llm_analysis(
                result=result,
                action=decision_action,
                parameters=decision_parameters,
                session_id=session_id,
                step_number=step_number,
            )
        else:
            observation_result = self._rule_based_observation(
                action_name=decision_action,
                parameters=decision_parameters,
                result=result.data,
                error=result.error if result.status == ExecutionStatus.FAILED else None,
            )

        # Логируем
        self.log.info(
            f"📊 Observation: status={observation_result.status}, "
            f"quality={observation_result.data_quality}",
            extra={"event_type": EventType.INFO},
        )

        return observation_result

    def _should_call_llm(self, result: ExecutionResult) -> bool:
        """Определить нужно ли LLM."""
        trigger_mode = self.TRIGGER_MODE

        if trigger_mode == "always":
            return True

        if result.status == ExecutionStatus.FAILED:
            return True

        if result.data in (None, {}, [], ""):
            return True

        if trigger_mode == "on_error":
            return result.status == ExecutionStatus.FAILED

        if trigger_mode == "on_empty":
            return result.data in (None, {}, [], "")

        return False

    def _rule_based_observation(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        result: Any,
        error: Optional[str] = None,
    ) -> ObservationResult:
        """
        Rule-based анализ результата без вызова LLM.

        Вся логика сжатия данных — здесь.
        observation_text формируется уже с учётом размера данных.
        """
        # Преобразуем Pydantic модели в стандартные типы Python
        if hasattr(result, 'model_dump'):
            result = result.model_dump()
        elif hasattr(result, 'dict'):
            result = result.dict()

        # Определяем статус
        if error:
            return self._handle_error_observation(action_name, parameters, error)

        # Проверяем пустоту результата
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

        # Успешный результат - анализируем данные и формируем информативное наблюдение
        completeness = 1.0
        reliability = 0.8
        observation_text = ""
        key_findings = []
        next_step_suggestion = "Продолжить следующий шаг на основе прогресса цели"

        # Для vector_search результатов
        if "vector_search" in action_name or (
            isinstance(result, list) and len(result) > 0
            and isinstance(result[0], dict) and "score" in result[0]
        ):
            results_list = []
            if isinstance(result, list):
                results_list = result
            elif isinstance(result, dict) and "results" in result:
                results_list = result.get("results", [])

            if results_list:
                count = len(results_list)
                query_text = ""
                if isinstance(result, dict) and "query" in result:
                    query_text = f" for query: {result['query'][:50]}"
                observation_text = f"Найдено {count} результатов{query_text}"

                key_findings.append(f"Найдено {count} результатов")

                # Добавляем примеры результатов
                for i, r in enumerate(results_list[:5]):
                    if isinstance(r, dict):
                        score = r.get('score', 0)
                        text = r.get('matched_text', r.get('content', r.get('text', str(r))))[:100]
                        key_findings.append(f"[{i+1}] (score={score:.2f}) {text}")

                if count > 5:
                    key_findings.append(f"... ещё {count - 5} результатов")

                if count > 10:
                    if count > 100:
                        next_step_suggestion = (
                            f"Обнаружено слишком много данных ({count} записей). "
                            f"Для анализа ОБЯЗАТЕЛЬНО запустите навык data_analysis.analyze_step_data. "
                            f"Перед запуском проверьте параметры или SQL-запрос — "
                            f"если они неполные, запустите навык повторно с доработанными параметрами "
                            f"(измените фильтры или SQL-запрос), чтобы сузить выборку."
                        )
                    else:
                        next_step_suggestion = (
                            f"Для полного анализа {count} результатов используйте data_analysis.analyze_step_data"
                        )

                completeness = 1.0 if count > 0 else 0.0
            else:
                observation_text = "Результаты не найдены"
                completeness = 0.0
                key_findings.append("Результаты не возвращены")

        # Для SQL результатов
        elif isinstance(result, dict) and ("rows" in result or "rowcount" in result):
            rows = result.get("rows", [])
            row_count = len(rows) if rows else result.get("rowcount", 0)

            if row_count > 0:
                key_findings.append(f"Получено {row_count} строк")

                # ЕСЛИ ДАННЫХ МНОГО — ТОЛЬКО СВОДКА (сжатие здесь!)
                if row_count > 10:
                    observation_text = (
                        f"Получено {row_count} строк. "
                        f"Для полного анализа используйте data_analysis.analyze_step_data"
                    )
                    if row_count > 100:
                        next_step_suggestion = (
                            f"Обнаружено слишком много данных ({row_count} строк). "
                            f"Для анализа ОБЯЗАТЕЛЬНО запустите навык data_analysis.analyze_step_data."
                        )
                else:
                    # Выводим сами данные только если их не слишком много
                    try:
                        observation_text = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
                    except (TypeError, ValueError):
                        observation_text = str(rows)

                # Показываем примеры строк в key_findings (всегда)
                for i, row in enumerate(rows[:3]):
                    if isinstance(row, dict):
                        preview = {k: v for k, v in list(row.items())[:3]}
                        key_findings.append(f"[{i+1}] {preview}")

                if row_count > 3:
                    key_findings.append(f"... ещё {row_count - 3} строк")

                completeness = 1.0
            else:
                observation_text = "Запрос не вернул данных"
                completeness = 0.0
                key_findings.append("Запрос вернул пустой результат")

        # Для списков
        elif isinstance(result, list):
            count = len(result)
            if count > 0:
                key_findings.append(f"Список содержит {count} элементов")

                # ЕСЛИ ДАННЫХ МНОГО — ТОЛЬКО СВОДКА
                if count > 10:
                    observation_text = (
                        f"Получено {count} элементов. "
                        f"Для полного анализа используйте data_analysis.analyze_step_data"
                    )
                    if count > 100:
                        next_step_suggestion = (
                            f"Обнаружено слишком много данных ({count} элементов). "
                            f"Для анализа ОБЯЗАТЕЛЬНО запустите навык data_analysis.analyze_step_data."
                        )
                else:
                    try:
                        observation_text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
                    except (TypeError, ValueError):
                        observation_text = str(result)

                if count > 3:
                    key_findings.append(f"... и ещё {count - 3} элементов")

                completeness = 0.8 if count < 5 else 1.0
            else:
                observation_text = "Получен пустой список"
                completeness = 0.0
                key_findings.append("Возвращён пустой список")

        # Для словарей
        elif isinstance(result, dict):
            key_count = len(result)
            try:
                observation_text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
            except (TypeError, ValueError):
                observation_text = str(result)
            key_findings.append(f"Словарь содержит {key_count} ключей")
            completeness = 0.8 if key_count > 0 else 0.0

        else:
            observation_text = str(result)
            completeness = 0.5

        # Проверяем warning-флаги
        if isinstance(result, dict):
            if result.get('warning') or result.get('truncated'):
                reliability = 0.6
                key_findings.append(f"Предупреждение: {result.get('warning', 'Результат обрезан')}")
            self.log.info(
                f"⚠️ [Observation] Результат имеет предупреждения: {result.get('warning', 'N/A')}",
                extra={"event_type": EventType.WARNING},
            )

        return ObservationResult(
            status="success",
            observation=observation_text,
            key_findings=key_findings,
            data_quality={"completeness": completeness, "reliability": reliability},
            errors=[],
            next_step_suggestion=next_step_suggestion if completeness > 0 else "Попробуйте другие параметры или проверьте доступность данных",
            requires_additional_action=completeness == 0.0,
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

            # Fallback схема
            if schema is None:
                schema = {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["success", "partial", "error", "empty"]},
                        "observation": {"type": "string", "description": "Краткое описание наблюдаемого результата"},
                        "key_findings": {"type": "array", "items": {"type": "string"}},
                        "data_quality": {
                            "type": "object",
                            "properties": {
                                "completeness": {"type": "number", "minimum": 0, "maximum": 1},
                                "reliability": {"type": "number", "minimum": 0, "maximum": 1}
                            }
                        },
                        "errors": {"type": "array", "items": {"type": "string"}},
                        "next_step_suggestion": {"type": "string"},
                        "requires_additional_action": {"type": "boolean"}
                    },
                    "required": ["status", "observation", "requires_additional_action"],
                    "additionalProperties": True,
                }

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
                    schema_def=schema,
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
