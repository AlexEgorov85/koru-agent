import time
from typing import Dict, Any
from pydantic import BaseModel

from core.agent.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus
from core.errors.exceptions import VectorSearchError
from core.components.skills.handlers.base_handler import SkillHandler


class SemanticSearchHandler(SkillHandler):
    """
    Обработчик семантического поиска через векторную БД.

    RESPONSABILITIES:
    - Проверка доступности FAISS индекса
    - Выполнение векторного поиска
    - Обработка и валидация результатов

    CAPABILITY:
    - book_library.semantic_search
    """

    capability_name = "book_library.semantic_search"

    async def _execute_impl(self, capability, parameters, execution_context=None):
        """Делегирует execute() — обратная совместимость."""
        return await self.execute(parameters, execution_context)

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Выполнение семантического поиска.

        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        start_time = time.time()
        await self.log_info(f"Запуск семантического поиска книг: params={params}")

        query = params.query if hasattr(params, 'query') else ''
        top_k = params.top_k if hasattr(params, 'top_k') else 10
        min_score = params.min_score if hasattr(params, 'min_score') else 0.5

        # 2. Проверка доступности векторного поиска
        await self._check_vector_search_ready(execution_context)

        # 3. Выполнение векторного поиска
        search_data = await self._execute_vector_search(query, top_k, min_score, execution_context)

        # 4. Форматирование результата
        total_time = time.time() - start_time
        result_data = self._format_result(search_data, total_time)

        await self.log_info(
            f"Семантический поиск завершён: найдено {result_data['total_found']} результатов "
            f"за {total_time*1000:.2f}мс (тип: vector)"
        )

        # 5. Публикация метрик
        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="vector",
            rows_returned=result_data["total_found"]
        )

        # 6. Валидация через выходной контракт
        return self._validate_output(result_data)

    def _extract_params(self, params: Dict[str, Any]) -> tuple:
        """
        Извлечение параметров запроса.

        ARGS:
        - params: входные параметры

        RETURNS:
        - tuple: (query, top_k, min_score)
        """
        query = params.get('query') if isinstance(params, dict) else getattr(params, 'query', None)
        top_k = params.get('top_k', 10) if isinstance(params, dict) else getattr(params, 'top_k', 10)
        min_score = params.get('min_score', 0.5) if isinstance(params, dict) else getattr(params, 'min_score', 0.5)

        if not query:
            raise ValueError("Параметр 'query' обязателен для семантического поиска")

        return query, top_k, min_score

    async def _check_vector_search_ready(self, execution_context: Any = None) -> None:
        """
        Проверка доступности векторного поиска.

        ARGS:
        - execution_context: контекст выполнения

        RAISES:
        - InfrastructureError: если векторный поиск не инициализирован
        """
        try:
            exec_ctx = execution_context if execution_context else ExecutionContext()
            test_result = await self.executor.execute_action(
                action_name="vector_search.search",
                parameters={"query": "test", "top_k": 1, "source": "books"},
                context=execution_context
            )
            if test_result.status != ExecutionStatus.COMPLETED:
                raise VectorSearchError(
                    "Vector Search для книг не инициализирован. "
                    "Проверьте что FAISS индекс создан и vector_search доступен."
                )
        except VectorSearchError:
            raise
        except Exception as e:
            raise VectorSearchError(
                f"Vector Search для книг не инициализирован. "
                f"Проверьте что FAISS индекс создан и vector_search доступен. Ошибка: {e}"
            )

    async def _execute_vector_search(
        self,
        query: str,
        top_k: int,
        min_score: float,
        execution_context: Any = None
    ) -> Dict[str, Any]:
        """
        Выполнение векторного поиска.

        ARGS:
        - query: поисковый запрос
        - top_k: количество результатов
        - min_score: минимальный порог релевантности
        - execution_context: контекст выполнения

        RETURNS:
        - dict: данные поиска

        RAISES:
        - VectorSearchError: если поиск не удался
        """
        try:
            exec_ctx = execution_context if execution_context else ExecutionContext()

            result = await self.executor.execute_action(
                action_name="vector_search.search",
                parameters={
                    "query": query,
                    "top_k": top_k,
                    "min_score": min_score,
                    "source": "books"
                },
                context=execution_context
            )

            if result.status != ExecutionStatus.COMPLETED:
                raise VectorSearchError(
                    f"Векторный поиск завершился с ошибкой: {result.error}. "
                    f"Статус: {result.status}",
                    component="book_library.semantic_search"
                )

            # Извлечение данных из результата
            search_data = self._extract_search_data(result)
            return search_data

        except VectorSearchError:
            raise
        except Exception as e:
            raise VectorSearchError(
                f"Векторный поиск не удался: {e}. "
                f"Проверьте что FAISS индекс создан и содержит данные.",
                component="book_library.semantic_search"
            )

    def _extract_search_data(self, result) -> Dict[str, Any]:
        """
        Извлечение данных из результата векторного поиска.

        ARGS:
        - result: результат выполнения

        RETURNS:
        - dict: данные поиска
        """
        search_data = None

        if hasattr(result, 'data') and result.data:
            if hasattr(result.data, 'data'):
                search_data = result.data.data
            elif hasattr(result.data, 'model_dump'):
                search_data = result.data.model_dump()
            else:
                search_data = result.data
        elif hasattr(result, 'model_dump'):
            search_data = result.model_dump()
        else:
            search_data = result

        return search_data

    def _format_result(self, search_data: Dict[str, Any], total_time: float) -> Dict[str, Any]:
        """
        Форматирование результата поиска.

        ARGS:
        - search_data: данные поиска
        - total_time: общее время выполнения

        RETURNS:
        - dict: отформатированный результат
        """
        if isinstance(search_data, dict):
            results_list = search_data.get("results", [])
            total_found = search_data.get("total_found", 0)
        elif hasattr(search_data, 'model_dump'):
            results_list = list(search_data.results) if search_data.results else []
            total_found = int(search_data.total_found) if search_data.total_found else 0
        else:
            results_list = []
            total_found = 0

        return {
            "results": results_list,
            "total_found": total_found,
            "execution_time": total_time,
            "execution_type": "vector"
        }
