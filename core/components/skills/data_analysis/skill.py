"""
Навык анализа данных с Python-first архитектурой.

АРХИТЕКТУРА:
- Режим PYTHON: только AnalyticsEngine (без LLM для вычислений)
- Режим LLM: LLM генерирует DSL → Engine исполняет → LLM интерпретирует
- Режим SEMANTIC: текст → чанкинг → batch + tree-reduce синтез
- Режим CODE: LLM генерирует код → SafeCodeExecutor (legacy)

ГАРАНТИИ:
- Числа считает только Python (AnalyticsEngine)
- LLM только планирует, интерпретирует или синтезирует текст
- Валидация через YAML-контракты
- Нет exec без AST-валидации

ИСПОЛЬЗОВАНИЕ:
    skill = DataAnalysisSkill(
        name="data_analysis",
        component_config=config,
        executor=executor,
        application_context=app_ctx
    )
    
    # Выполнение анализа
    result = await skill.execute(
        capability=Capability(name="data_analysis.analyze_step_data"),
        parameters={
            "step_id": "123",
            "question": "Сколько всего продаж?",
            "mode": "python"  # auto|python|llm|semantic|code
        },
        context=execution_context
    )
    
    # Результат:
    # {
    #     "answer": "Всего продаж: 150000",
    #     "execution_status": "success",
    #     "confidence": 1.0,
    #     "executed_operations": ["filter", "aggregate"],
    #     "metadata": {"mode_used": "python", "row_count": 100}
    # }

ВХОДНОЙ КОНТРАКТ (parameters):
    - step_id: str — ID шага с данными в SessionContext
    - question: str — вопрос для анализа
    - mode: str — режим (auto|python|llm|semantic|code), default: auto
    - max_retries: int — кол-во попыток при ошибке, default: 2
    - timeout_seconds: float — таймаут для code mode, default: 5.0

ВЫХОДНОЙ КОНТРАКТ (result):
    - answer: str — текстовый ответ на вопрос
    - execution_status: str — success|error|skipped
    - confidence: float — уверенность 0.0-1.0
    - executed_operations: List[str] — список выполненных операций
    - metadata: dict — {mode_used, row_count, processing_time_ms, ...}
    - execution_error: str — текст ошибки если status=error
"""
import asyncio
import time
import json
import re
from typing import List, Dict, Any, Optional

from core.components.skills.skill import Skill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionStatus
from core.infrastructure.logging.event_types import LogEventType
from core.errors.exceptions import SkillExecutionError
from core.components.skills.data_analysis.utils.data_profiler import DataProfiler
from core.components.skills.data_analysis.analytics_engine import AnalyticsEngine
from core.components.skills.data_analysis.safe_code_executor import SafeCodeExecutor
from core.components.skills.data_analysis.utils.text_chunker import TextChunker
from core.components.skills.data_analysis.batch_processor import BatchProcessor
from core.components.skills.data_analysis.tree_reducer import TreeReducer
from core.components.skills.data_analysis.safe_formula_parser import SafeFormulaParser


class DataAnalysisSkill(Skill):
    @property
    def description(self) -> str:
        return "Анализ данных: Python-first вычисления, LLM для синтеза"

    name: str = "data_analysis"

    def __init__(
        self,
        name: str,
        component_config: Any,
        executor: Any,
        application_context: Any = None,
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )

    def get_capabilities(self) -> List[Capability]:
        """
        Возвращает список capabilities, поддерживаемых навыком.
        
        RETURNS:
        - List[Capability]: capability для анализа данных
        
        CAPABILITY:
        - name: data_analysis.analyze_step_data
        - description: Анализ данных: Python-first вычисления + LLM синтез
        - supported_strategies: ["react", "planning"]
        - meta.modes: ["auto", "python", "llm", "semantic", "code"]
        """
        return [
            Capability(
                name="data_analysis.analyze_step_data",
                description="Анализ данных: Python-first вычисления + LLM синтез",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "supports_chunking": True,
                    "modes": ["auto", "python", "llm", "semantic", "code"],
                    "supports_self_correction": True,
                    "batch_processing": True,
                    "tree_reduce": True
                }
            )
        ]

    async def initialize(self) -> bool:
        success = await super().initialize()
        if not success:
            return False

        if "data_analysis.analyze_step_data" not in self.prompts:
            self._log_warning("Промпт не загружен", event_type=LogEventType.WARNING)

        if "data_analysis.analyze_step_data" not in self.input_contracts:
            self._log_warning("Входной контракт не загружен", event_type=LogEventType.WARNING)

        if "data_analysis.analyze_step_data" not in self.output_contracts:
            self._log_warning("Выходной контракт не загружен", event_type=LogEventType.WARNING)

        return True

    def _get_event_type_for_success(self) -> str:
        return "skill.data_analysis.executed"

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Главный метод выполнения навыка. Вызывается из execute() после валидации.
        
        АРХИТЕКТУРА:
        1. Нормализация параметров (dict/pydantic → dict)
        2. Загрузка данных из SessionContext по step_id
        3. Профилирование данных (DataProfiler)
        4. Выбор режима (mode)
        5. Выполнение через соответствующий _run_* метод
        6. Возврат результата с метаданными
        
        ARGS:
        - capability: Capability — capability из get_capabilities()
        - parameters: Dict — входные параметры (step_id, question, mode, ...)
        - execution_context: ExecutionContext — контекст выполнения (см. ниже)
        
        execution_context содержит:
        - session_context: SessionContext — сессия с данными
        - step_context: StepContext — контекст текущего шага
        - agent_config: AgentConfig — конфиг агента
        
        RETURNS:
        - Dict с ключами:
            - answer: str — текстовый ответ
            - execution_status: str — success|error|skipped
            - confidence: float — 0.0-1.0
            - executed_operations: List[str] — операции ["filter", "aggregate"]
            - metadata: dict — {mode_used, row_count, processing_time_ms, ...}
            - execution_error: str — ошибка если status=error
        
        ИСКЛЮЧЕНИЯ:
        - ValueError: step_id или question не переданы
        - ValueError: нет данных для step_id в SessionContext
        - SkillExecutionError: ошибка при выполнении
        """
        start_time = time.time()

        self._log_info(
            f"📊 [data_analysis] Начало анализа",
            event_type=LogEventType.TOOL_CALL
        )

        params_dict = self._normalize_parameters(parameters)

        step_id = params_dict.get("step_id")
        question = params_dict.get("question")
        mode = params_dict.get("mode", "auto")
        max_retries = params_dict.get("max_retries", 2)
        timeout = params_dict.get("timeout_seconds", 5.0)

        if not step_id:
            raise ValueError("Параметр 'step_id' обязателен")
        if not question:
            raise ValueError("Параметр 'question' обязателен")

        self._log_info(
            f"📋 [data_analysis] step_id={step_id}, question='{question[:50]}...', mode={mode}",
            event_type=LogEventType.INFO
        )

        session_ctx = getattr(execution_context, 'session_context', None)
        if not session_ctx:
            raise ValueError("SessionContext не доступен")

        rows, raw_text, data_metadata = self._load_data_from_context(step_id, session_ctx)

        if not rows and not raw_text:
            raise ValueError(f"Нет данных для step_id={step_id}")

        self._log_info(
            f"📦 [data_analysis] Загружено: {len(rows) if rows else 0} строк, {len(raw_text) if raw_text else 0} символов",
            event_type=LogEventType.INFO
        )

        is_tabular = bool(rows and isinstance(rows, list))
        data = rows if rows else raw_text
        
        if is_tabular:
            profile = DataProfiler.profile_rows(data)
            data_profile = {
                "type": "tabular",
                "profile": profile
            }
        else:
            profile = DataProfiler.profile_text(str(data))
            data_profile = {
                "type": "text",
                "profile": profile
            }

        selected_mode = mode

        executed_operations = []

        if selected_mode == "auto":
            selected_mode = "python"
            self._log_info("🔀 [data_analysis] Auto mode → python (no heuristics)", event_type=LogEventType.INFO)

        if selected_mode == "python":
            result = await self._run_python_mode(data, profile, question, start_time, executed_operations)
        elif selected_mode == "llm":
            result = await self._run_llm_mode(data, profile, question, max_retries, start_time, execution_context, executed_operations)
        elif selected_mode == "semantic":
            result = await self._run_semantic_mode_v2(raw_text, question, start_time, execution_context, executed_operations)
        elif selected_mode == "code":
            result = await self._run_code_mode(data, profile, question, max_retries, timeout, start_time, execution_context, executed_operations)
        else:
            result = await self._run_python_mode(data, profile, question, start_time, executed_operations)

        result["executed_operations"] = executed_operations
return result

    def _normalize_parameters(self, parameters: Any) -> Dict[str, Any]:
        """
        Нормализация параметров в единый формат dict.
        
        АРГУМЕНТЫ:
        - parameters: может быть dict, Pydantic model, или объект с .dict() методом
        
        ВОЗВРАЩАЕТ:
        - Dict с параметрами
        
        ИСКЛЮЧЕНИЯ:
        - ValueError: если тип не поддерживается
        """
        if hasattr(parameters, 'model_dump'):
            return parameters.model_dump()
        elif hasattr(parameters, 'dict'):
            return parameters.dict()
        elif isinstance(parameters, dict):
            return parameters
        raise ValueError(f"Неподдерживаемый тип параметров: {type(parameters)}")
    
    

    async def _run_python_mode(
        self,
        data: Any,
        profile: Dict,
        question: str,
        start_time: float,
        executed_operations: List[str]
    ) -> Dict[str, Any]:
        """
        Режим PYTHON: детерминированные вычисления через AnalyticsEngine.
        
        ОПИСАНИЕ:
        - Использует AnalyticsEngine для filter/group_by/aggregate/sort/limit
        - НЕ использует LLM для вычислений (только для формата ответа)
        - 100% детерминировано, безопасно, быстро
        
        АРГУМЕНТЫ:
        - data: List[Dict] — табличные данные из SessionContext
        - profile: Dict — профиль данных от DataProfiler (типы колонок, статистика)
        - question: str — вопрос пользователя
        - start_time: float — время старта для расчёта processing_time_ms
        - executed_operations: List[str] — список для записи выполненных операций
        
        ВОЗВРАЩАЕТ:
        - Dict с результатом анализа
        
        ЛОГИКА:
        1. Пытается определить операции из вопроса (_detect_operations_from_question)
        2. Выполняет через AnalyticsEngine.execute_dsl(data, operations)
        3. Форматирует результат в текст (_format_analytics_result)
        4. При ошибке — fallback на describe()
        """
        self._log_info("🐍 [data_analysis] PYTHON mode — AnalyticsEngine", event_type=LogEventType.INFO)

        if not isinstance(data, list) or not data:
            return self._build_output(
                answer="Нет табличных данных для анализа",
                execution_status="skipped",
                execution_error="Данные не в табличном формате",
                confidence=0.0,
                executed_operations=executed_operations,
                metadata={"mode_used": "python", "processing_time_ms": round((time.time() - start_time) * 1000, 2)}
            )

        operations = self._detect_operations_from_question(question, profile)
        
        try:
            result = AnalyticsEngine.execute_dsl(data, {"operations": operations})
            executed_operations.extend([op.get("type") for op in operations])

            answer = self._format_analytics_result(result, question)
            confidence = 1.0

        except Exception as e:
            self._log_warning(f"⚠️ [data_analysis] Python mode error: {e}", event_type=LogEventType.WARNING)
            desc = AnalyticsEngine.describe(data)
            answer = f"Статистика:\n{json.dumps(desc, ensure_ascii=False, indent=2)}"
            executed_operations.append("describe")
            confidence = 0.8

        return self._build_output(
            answer=answer,
            execution_status="success",
            execution_error=None,
            confidence=confidence,
            executed_operations=executed_operations,
            metadata={
                "mode_used": "python",
                "row_count": len(data) if isinstance(data, list) else 0,
                "data_type": "tabular",
                "processing_time_ms": round((time.time() - start_time) * 1000, 2)
            }
        )

    def _detect_operations_from_question(self, question: str, profile: Dict) -> List[Dict[str, Any]]:
        """
        Определение операций AnalyticsEngine из текста вопроса.
        
        АРГУМЕНТЫ:
        - question: str — вопрос пользователя (анализируется на ключевые слова)
        - profile: Dict — профиль данных (нужен для знания колонок)
        
        ВОЗВРАЩАЕТ:
        - List[Dict] — список операций для AnalyticsEngine.execute_dsl()
        
        ПОДДЕРЖИВАЕТ:
        - filter: "фильтр", "где", "статус", "категория"
        - group_by: "группировка", "по", "сумма", "итог"
        - sort: "сортировка", "топ", "самый"
        - limit: "первый", "лимит", "только"
        - describe: по умолчанию если ничего не определено
        """
        operations = []
        question_lower = question.lower()

        columns = profile.get("columns", [])
        numeric_cols = [c["name"] for c in columns if c.get("type") in ("integer", "float")]

        if "фильтр" in question_lower or "где" in question_lower or "=" in question:
            for col in columns:
                if col["type"] == "string" and any(kw in question_lower for kw in ["статус", "категория", "тип"]):
                    operations.append({
                        "type": "filter",
                        "conditions": [{"column": col["name"], "operator": "not_null"}]
                    })

        if any(kw in question_lower for kw in ["группиров", "по", "категория", "сумма", "итог"]):
            if numeric_cols:
                operations.append({
                    "type": "group_by",
                    "columns": [c["name"] for c in columns if c["type"] == "string"][:1],
                    "metrics": [{"column": numeric_cols[0], "func": "sum"}]
                })

        if any(kw in question_lower for kw in ["сортиров", "топ", "самый"]):
            sort_col = numeric_cols[0] if numeric_cols else columns[0]["name"]
            order = "desc" if "топ" in question_lower or "самый" in question_lower else "asc"
            operations.append({"type": "sort", "column": sort_col, "order": order})

        if any(kw in question_lower for kw in ["перв", "лимит", "только"]):
            operations.append({"type": "limit", "n": 5})

        if not operations:
            operations.append({"type": "describe"})

        return operations

    def _format_analytics_result(self, result: Dict[str, Any], question: str) -> str:
        """
        Форматирование результата AnalyticsEngine в читаемый текст.
        
        АРГУМЕНТЫ:
        - result: Dict — результат от AnalyticsEngine.execute_dsl()
        - question: str — оригинальный вопрос (для контекста)
        
        ВОЗВРАЩАЕТ:
        - str — текстовое представление результата
        """
        if result.get("operation_type") == "describe":
            return f"Статистика по данным:\n{json.dumps(result.get('result', {}), ensure_ascii=False, indent=2)}"

        row_count = result.get("row_count", 0)
        operations_executed = result.get("operations_executed", 0)
        data_rows = result.get("result", [])

        if isinstance(data_rows, list) and data_rows:
            formatted_data = json.dumps(data_rows[:10], ensure_ascii=False, indent=2)
            if row_count > 10:
                formatted_data += f"\n... и ещё {row_count - 10} строк"
            
            return f"Выполнено операций: {operations_executed}\nРезультат ({row_count} строк):\n{formatted_data}"

        return f"Результат: {json.dumps(result, ensure_ascii=False, indent=2)}"

    async def _run_llm_mode(
        self,
        data: Any,
        profile: Dict,
        question: str,
        max_retries: int,
        start_time: float,
        execution_context: Any,
        executed_operations: List[str]
    ) -> Dict[str, Any]:
        """
        Режим LLM: LLM генерирует DSL → AnalyticsEngine исполняет → LLM интерпретирует.
        
        ОПИСАНИЕ:
        - LLM анализирует вопрос и генерирует JSON-DSL спецификацию
        - AnalyticsEngine выполняет DSL операции (безопасно, детерминировано)
        - LLM интерпретирует результат в текст для пользователя
        
        АРГУМЕНТЫ:
        - data: List[Dict] — табличные данные
        - profile: Dict — профиль данных от DataProfiler
        - question: str — вопрос пользователя
        - max_retries: int — кол-во попыток при ошибке генерации DSL
        - start_time: float — время старта
        - execution_context: Any — контекст для LLM вызовов
        - executed_operations: List[str] — список для записи выполненных операций
        
        ВОЗВРАЩАЕТ:
        - Dict с результатом
        
        ПОТОК:
        1. LLM генерирует DSL через _generate_dsl() → промпт dsl_plan
        2. AnalyticsEngine.execute_dsl(data, dsl_spec) → результат
        3. LLM интерпретирует через _interpret_result() → промпт interpret
        4. Fallback на _run_python_mode при ошибках
        """
        self._log_info("🧠 [data_analysis] LLM mode — DSL планирование", event_type=LogEventType.INFO)

        prompt_obj = self.get_prompt("data_analysis.analyze_step_data.dsl_plan")
        if not prompt_obj:
            return await self._run_python_mode(data, profile, question, start_time, executed_operations)

        last_error = ""
        retries_used = 0

        for attempt in range(max_retries + 1):
            dsl_spec = await self._generate_dsl(question, profile, last_error, execution_context)
            
            if not dsl_spec or not dsl_spec.get("operations"):
                last_error = "LLM не сгенерировал DSL"
                continue

            try:
                result = AnalyticsEngine.execute_dsl(data, dsl_spec)
                executed_operations.extend([op.get("type") for op in dsl_spec.get("operations", [])])

                answer = self._format_analytics_result(result, question)

                interpreted = await self._interpret_result(answer, question, execution_context)
                
                return self._build_output(
                    answer=interpreted,
                    execution_status="success",
                    execution_error=None,
                    confidence=0.85,
                    executed_operations=executed_operations,
                    metadata={
                        "mode_used": "llm",
                        "row_count": len(data) if isinstance(data, list) else 0,
                        "data_type": "tabular",
                        "retries_used": retries_used,
                        "processing_time_ms": round((time.time() - start_time) * 1000, 2)
                    }
                )

            except Exception as e:
                last_error = str(e)
                retries_used += 1
                self._log_warning(f"⚠️ [data_analysis] DSL error (attempt {retries_used}): {last_error}", event_type=LogEventType.WARNING)

        return await self._run_python_mode(data, profile, question, start_time, executed_operations)

    async def _generate_dsl(
        self,
        question: str,
        profile: Dict,
        prev_error: str,
        execution_context: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Генерация JSON-DSL спецификации через LLM.
        
        АРГУМЕНТЫ:
        - question: str — вопрос пользователя
        - profile: Dict — профиль данных (типы колонок, статистика)
        - prev_error: str — ошибка с предыдущей попытки (для retry)
        - execution_context: Any — контекст для LLM вызова
        
        ВОЗВРАЩАЕТ:
        - Dict с ключом "operations": [...] или None при ошибке
        
        ПРОМПТ:
        - Использует: data_analysis.analyze_step_data.dsl_plan
        - Переменные: {question}, {profile}, {prev_error}
        
        LLM ВЫЗОВ:
        - action: llm.generate_structured
        - strict_mode: True (требует валидный JSON)
        """
        prompt_obj = self.get_prompt("data_analysis.analyze_step_data.dsl_plan")
        if not prompt_obj:
            return None

        vars_dict = {
            "question": question,
            "profile": json.dumps(profile, ensure_ascii=False),
            "prev_error": f"\nОшибка: {prev_error}\nИсправь DSL." if prev_error else ""
        }
        rendered = self._render_prompt(prompt_obj.content, vars_dict)

        output_contract = self.get_output_contract("data_analysis.analyze_step_data")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": rendered,
                "structured_output": {
                    "output_model": "data_analysis.analyze_step_data",
                    "schema_def": output_contract if output_contract else {},
                    "max_retries": 1,
                    "strict_mode": True
                },
                "temperature": 0.1,
                "max_tokens": 1500
            },
            context=execution_context
        )

        if llm_result.status != ExecutionStatus.COMPLETED:
            return None

        if hasattr(llm_result.result, 'model_dump'):
            return llm_result.result.model_dump()
        elif hasattr(llm_result.result, 'dict'):
            return llm_result.result.dict()
        return llm_result.result

    async def _interpret_result(
        self,
        result: str,
        question: str,
        execution_context: Any
    ) -> str:
        """
        Интерпретация результата анализа через LLM.
        
        АРГУМЕНТЫ:
        - result: str — результат от AnalyticsEngine (сырой JSON/текст)
        - question: str — оригинальный вопрос пользователя
        - execution_context: Any — контекст для LLM вызова
        
        ВОЗВРАЩАЕТ:
        - str — текстовый ответ на русском языке
        
        ПРОМПТ:
        - Использует: data_analysis.analyze_step_data.interpret
        - Переменные: {question}, {result}
        
        ПРАВИЛА:
        - Использует только факты из результата
        - Не выдумывает информацию
        - Указывает конкретные цифры и метрики
        """
        prompt_obj = self.get_prompt("data_analysis.analyze_step_data.interpret")
        if not prompt_obj:
            return result

        rendered = self._render_prompt(prompt_obj.content, {
            "question": question,
            "result": result
        })

        llm_result = await self.executor.execute_action(
            action_name="llm.generate",
            parameters={
                "prompt": rendered,
                "temperature": 0.2,
                "max_tokens": 1000
            },
            context=execution_context
        )

        if llm_result.status == ExecutionStatus.COMPLETED:
            return llm_result.result or result

        return result

    async def _run_semantic_mode_v2(
        self,
        raw_text: str,
        question: str,
        start_time: float,
        execution_context: Any,
        executed_operations: List[str]
    ) -> Dict[str, Any]:
        """
        Режим SEMANTIC: анализ текста через batch processing + tree-reduce.
        
        ОПИСАНИЕ:
        - Рекурсивное разбиение текста на чанки (TextChunker)
        - Batch обработка чанков через LLM (BatchProcessor)
        - Tree-reduce синтез результатов (TreeReducer)
        - Работает с текстом ЛЮБОГО размера (нет лимита)
        
        АРГУМЕНТЫ:
        - raw_text: str — текст для анализа
        - question: str — вопрос пользователя
        - start_time: float — время старта
        - execution_context: Any — контекст для LLM вызовов
        - executed_operations: List[str] — список для записи
        
        ВОЗВРАЩАЕТ:
        - Dict с результатом
        
        ПОТОК:
        1. TextChunker.split() → чанки (без лимита)
        2. BatchProcessor.process_batches() → summary для каждого чанка
        3. TreeReducer.reduce() → финальный объединённый ответ
        
        ПРОМПТЫ:
        - Основной: data_analysis.analyze_step_data (для анализа чанка)
        """
        self._log_info("📝 [data_analysis] SEMANTIC mode — batch + tree-reduce", event_type=LogEventType.INFO)

        if not raw_text:
            return self._build_output(
                answer="Нет текстовых данных для анализа",
                execution_status="skipped",
                execution_error="Нет текста",
                confidence=0.0,
                executed_operations=executed_operations,
                metadata={"mode_used": "semantic", "row_count": 0, "processing_time_ms": round((time.time() - start_time) * 1000, 2)}
            )

        chunks = TextChunker.split(
            raw_text,
            chunk_size=2500,
            overlap=200,
            min_chunk_size=200
        )

        executed_operations.append(f"chunking:{len(chunks)}")
        
        self._log_info(f"📄 [data_analysis] Создано {len(chunks)} чанков", event_type=LogEventType.INFO)

        async def analyze_chunk(chunk: Dict[str, Any]) -> Dict[str, Any]:
            prompt_obj = self.get_prompt("data_analysis.analyze_step_data")
            if not prompt_obj:
                return {"content": chunk.get("content", "")[:500]}

            rendered = self._render_prompt(prompt_obj.content, {
                "question": question,
                "raw_data": chunk.get("content", "")[:6000],
                "profile": "text"
            })

            llm_result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={"prompt": rendered, "temperature": 0.2, "max_tokens": 800},
                context=execution_context
            )

            if llm_result.status == ExecutionStatus.COMPLETED:
                return {"content": llm_result.result or "", "chunk_id": chunk.get("chunk_id", 0)}
            return {"content": "", "chunk_id": chunk.get("chunk_id", 0)}

        batch_processor = BatchProcessor(self.executor, execution_context, chunk_size=15, max_concurrent=3)
        
        summaries = await batch_processor.process_batches(
            chunks,
            analyze_chunk,
            aggregation_fn=None
        )

        executed_operations.append(f"llm_calls:{len(summaries)}")

        tree_reducer = TreeReducer(self.executor, execution_context, max_output_tokens=3000, threshold_tokens=1500)
        
        final_answer = await tree_reducer.reduce(summaries, question)

        executed_operations.append("tree_reduce")

        return self._build_output(
            answer=final_answer,
            execution_status="success",
            execution_error=None,
            confidence=0.75,
            executed_operations=executed_operations,
            metadata={
                "mode_used": "semantic",
                "row_count": len(raw_text),
                "data_type": "text",
                "chunks_created": len(chunks),
                "processing_time_ms": round((time.time() - start_time) * 1000, 2)
            }
        )

    async def _run_code_mode(
        self,
        data: Any,
        profile: Dict,
        question: str,
        max_retries: int,
        timeout: float,
        start_time: float,
        execution_context: Any,
        executed_operations: List[str]
    ) -> Dict[str, Any]:
        """
        Режим CODE: LLM генерирует Python код → SafeCodeExecutor исполняет.
        
        ОПИСАНИЕ:
        - LLM генерирует Python код для анализа данных
        - SafeCodeExecutor выполняет код в sandbox (AST-валидация, таймаут)
        - Legacy режим, рекомендуется использовать python или llm
        
        АРГУМЕНТЫ:
        - data: Any — данные (List[Dict] или str)
        - profile: Dict — профиль данных
        - question: str — вопрос пользователя
        - max_retries: int — кол-во попыток при ошибке исполнения
        - timeout: float — таймаут исполнения кода в секундах
        - start_time: float — время старта
        - execution_context: Any — контекст для LLM
        - executed_operations: List[str] — список операций
        
        ВОЗВРАЩАЕТ:
        - Dict с результатом
        
        ИСКЛЮЧЕНИЯ:
        - SkillExecutionError: после max_retries попыток
        """
        self._log_info("⚡ [data_analysis] CODE mode — LLM генерация кода", event_type=LogEventType.INFO)

        last_error = ""
        retries_used = 0

        for attempt in range(max_retries + 1):
            code_gen_result = await self._generate_analysis_code(question, profile, last_error, execution_context)
            generated_code = code_gen_result.get("code", "")

            if not generated_code:
                last_error = "LLM не сгенерировал код"
                continue

            exec_context = {"data": data, "profile": profile}
            exec_result = await SafeCodeExecutor.execute(generated_code, exec_context, timeout)

            if exec_result["status"] == "success":
                explanation = code_gen_result.get("explanation", "Код выполнен успешно")
                exec_output = exec_result.get("result")

                if isinstance(exec_output, (dict, list)):
                    answer = f"{explanation}\nРезультат: {json.dumps(exec_output, ensure_ascii=False, indent=2)[:1000]}"
                elif exec_output is not None:
                    answer = f"{explanation}\nРезультат: {str(exec_output)[:500]}"
                else:
                    answer = explanation

                executed_operations.append("code_generation")
                executed_operations.append("safe_execution")

                return self._build_output(
                    answer=answer,
                    execution_status="success",
                    execution_error=None,
                    confidence=0.9,
                    executed_operations=executed_operations,
                    metadata={
                        "row_count": len(data) if isinstance(data, list) else 0,
                        "data_type": "tabular" if isinstance(data, list) else "text",
                        "mode_used": "code",
                        "retries_used": retries_used,
                        "processing_time_ms": round((time.time() - start_time) * 1000, 2)
                    }
                )

            last_error = exec_result.get("error", "Неизвестная ошибка")
            retries_used += 1
            self._log_warning(f"⚠️ [data_analysis] Ошибка кода (попытка {retries_used}): {last_error}", event_type=LogEventType.WARNING)

        raise SkillExecutionError(
            f"Не удалось выполнить анализ после {max_retries + 1} попыток. Последняя ошибка: {last_error}",
            component="data_analysis"
        )

    async def _generate_analysis_code(
        self,
        question: str,
        profile: Dict,
        prev_error: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Генерация Python кода через LLM для анализа данных.
        
        АРГУМЕНТЫ:
        - question: str — вопрос пользователя
        - profile: Dict — профиль данных
        - prev_error: str — ошибка с предыдущей попытки
        - execution_context: Any — контекст для LLM
        
        ВОЗВРАЩАЕТ:
        - Dict с ключами: code (str), explanation (str)
        
        ПРОМПТ:
        - Использует: data_analysis.analyze_step_data.code_gen
        """
        prompt_obj = self.get_prompt("data_analysis.analyze_step_data.code_gen")
        if not prompt_obj:
            raise SkillExecutionError("Промпт code_gen не найден", component="data_analysis")

        vars_dict = {
            "question": question,
            "profile": json.dumps(profile, ensure_ascii=False, indent=2),
            "prev_error": f"\nПредыдущая ошибка: {prev_error}\nИсправь код и избегай этой ошибки." if prev_error else ""
        }
        rendered = self._render_prompt(prompt_obj.content, vars_dict)

        output_contract = self.get_output_contract("data_analysis.analyze_step_data.code_gen")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": rendered,
                "structured_output": {
                    "output_model": "data_analysis.analyze_step_data.code_gen.output",
                    "schema_def": output_contract if output_contract else {},
                    "max_retries": 1,
                    "strict_mode": True
                },
                "temperature": 0.1,
                "max_tokens": 1000
            },
            context=execution_context
        )

        if llm_result.status != ExecutionStatus.COMPLETED:
            raise SkillExecutionError(f"LLM code_gen failed: {llm_result.error}", component="data_analysis")

        if hasattr(llm_result.result, 'model_dump'):
            return llm_result.result.model_dump()
        elif hasattr(llm_result.result, 'dict'):
            return llm_result.result.dict()
        return llm_result.result

    def _build_output(
        self,
        answer: str,
        execution_status: str,
        execution_error: Optional[str],
        confidence: float,
        executed_operations: List[str],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Формирование стандартного ответа навыка.
        
        АРГУМЕНТЫ:
        - answer: str — текстовый ответ на вопрос
        - execution_status: str — success|error|skipped
        - execution_error: str — текст ошибки (если status=error)
        - confidence: float — уверенность 0.0-1.0
        - executed_operations: List[str] — выполненные операции
        - metadata: Dict — метаданные {mode_used, row_count, ...}
        
        ВОЗВРАЩАЕТ:
        - Dict — готовый к возврату результат
        """
        return {
            "answer": answer,
            "execution_status": execution_status,
            "execution_error": execution_error,
            "confidence": confidence,
            "executed_operations": executed_operations,
            "metadata": metadata
        }

    def _render_prompt(self, prompt: str, variables: Dict[str, Any]) -> str:
        """
        Подстановка переменных в промпт.
        
        АРГУМЕНТЫ:
        - prompt: str — исходный текст промпта с {variable}
        - variables: Dict — словарь {variable: value}
        
        ВОЗВРАЩАЕТ:
        - str — промпт с подставленными значениями
        
        ПРИМЕР:
        >>> prompt = "Вопрос: {question}, Данные: {profile}"
        >>> _render_prompt(prompt, {"question": "Сколько?", "profile": "{...}"})
        "Вопрос: Сколько?, Данные: {...}"
        """
        import re
        result = prompt
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        result = re.sub(r'\{[a-z_]+\}', '', result)
        return result

    def _load_data_from_context(self, step_id: str, session_ctx) -> tuple:
        """
        Загрузка данных из SessionContext по step_id.
        
        АРГУМЕНТЫ:
        - step_id: str — ID шага для поиска данных
        - session_ctx: SessionContext — контекст сессии с data_context
        
        ВОЗВРАЩАЕТ:
        - tuple: (rows: List[Dict], raw_text: str, metadata: Dict)
          - rows: List[Dict] — табличные данные (если есть)
          - raw_text: str — текстовые данные (если есть)
          - metadata: Dict — {source_type, step_id, size_mb}
        
        ЛОГИКА:
        - Ищет в session_ctx.data_context по step_id или step_number
        - Возвращает rows если данные List[Dict] или dict с "rows"
        - Возвращает raw_text если данные текстовые
        """
        if not hasattr(session_ctx, 'data_context'):
            return [], "", {}

        items = session_ctx.data_context.get_all_items()

        for item in items:
            meta = item.metadata
            if not meta:
                continue

            add_data = meta.additional_data or {}
            meta_step_id = add_data.get("step_id")
            meta_step_number = meta.step_number

            if meta_step_id == step_id or str(meta_step_number) == str(step_id):
                content = item.content
                if content:
                    if isinstance(content, dict):
                        rows = content.get("rows", [])
                        if rows:
                            metadata = {
                                "source_type": "session_context",
                                "step_id": step_id,
                                "size_mb": len(json.dumps(rows).encode('utf-8')) / (1024 * 1024)
                            }
                            return rows, "", metadata

                        raw = content.get("content", content.get("raw_data", content.get("data", "")))
                        if raw:
                            metadata = {
                                "source_type": "session_context",
                                "step_id": step_id,
                                "size_mb": len(str(raw).encode('utf-8')) / (1024 * 1024)
                            }
                            return [], str(raw), metadata

                    elif isinstance(content, list):
                        rows = content
                        metadata = {
                            "source_type": "session_context",
                            "step_id": step_id,
                            "size_mb": len(json.dumps(rows).encode('utf-8')) / (1024 * 1024)
                        }
                        return rows, "", metadata

        return [], "", {}