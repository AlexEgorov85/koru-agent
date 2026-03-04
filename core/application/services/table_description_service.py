"""
Инфраструктурный сервис для получения описания таблицы.
"""
from typing import Dict, Any
from core.application.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.application.context.application_context import ApplicationContext


class TableDescriptionServiceInput(ServiceInput):
    """Входные данные для TableDescriptionservices."""
    def __init__(self, schema_name: str, table_name: str, context: Any, step_number: int):
        self.schema_name = schema_name
        self.table_name = table_name
        self.context = context
        self.step_number = step_number


class TableDescriptionServiceOutput(ServiceOutput):
    """Выходные данные для TableDescriptionservices."""
    def __init__(self, metadata: Dict[str, Any]):
        self.metadata = metadata


class TableDescriptionService(BaseService):
    """
    Сервис для получения описания таблицы с метаданными.

    ОСОБЕННОСТИ:
    - Использует SQL-запросы для получения метаданных
    - Возвращает структурированные данные
    - Обеспечивает безопасность через проверку схемы и таблицы
    - Поддерживает разные форматы вывода
    """
    
    # Базовый сервис без зависимостей — инициализируется первым
    DEPENDENCIES = []  # Нет зависимостей

    @property
    def description(self) -> str:
        return "Сервис для получения описания таблицы с метаданными"

    def __init__(self, application_context: ApplicationContext, name: str = None, component_config=None, executor=None):
        """
        Инициализация сервиса получения описания таблицы.

        ARGS:
        - application_context: прикладной контекст для выполнения SQL-запросов
        - name: имя сервиса (опционально)
        - component_config: конфигурация компонента
        - executor: ActionExecutor для взаимодействия между компонентами
        """
        from core.config.component_config import ComponentConfig
        # Создаем минимальный ComponentConfig, если не передан
        if component_config is None:
            component_config = ComponentConfig(
                variant_id="table_description_service_default",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={}
            )
        super().__init__(name or "table_description_service", application_context, component_config, executor)
        # НЕ загружаем зависимости здесь! Только инициализация внутреннего состояния

    async def _custom_initialize(self) -> bool:
        """
        Специфичная инициализация для TableDescriptionService.
        """
        try:
            if self.event_bus_logger:
                await self.event_bus_logger.info("Инициализация сервиса описания таблицы")
            # Проверка доступности прикладного контекста и необходимых компонентов
            if self.application_context is None:
                if self.event_bus_logger:
                    await self.event_bus_logger.error("Отсутствует прикладной контекст")
                return False

            # Инициализация кэша таблиц
            self._table_cache = {}

            if self.event_bus_logger:
                await self.event_bus_logger.info("Сервис описания таблицы успешно инициализирован")
            return True
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка инициализации сервиса описания таблицы: {str(e)}")
            return False

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения сервиса описания таблиц."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.PROVIDER_REGISTERED

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики сервиса описания таблиц.

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        # Получение метаданных таблицы
        metadata = await self.get_table_metadata(
            schema_name=parameters.get("schema_name", ""),
            table_name=parameters.get("table_name", ""),
            context=parameters.get("context"),
            step_number=parameters.get("step_number")
        )
        return {"metadata": metadata, "capability": capability.name}

    async def shutdown(self) -> None:
        """
        Завершение работы сервиса описания таблицы.
        """
        try:
            if self.event_bus_logger:
                await self.event_bus_logger.info("Завершение работы сервиса описания таблицы")
            # Любые необходимые действия при завершении работы
            if self.event_bus_logger:
                await self.event_bus_logger.info("Сервис описания таблицы успешно завершил работу")
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка при завершении работы сервиса описания таблицы: {str(e)}")
            raise

    async def get_table_metadata(
        self,
        schema_name: str,
        table_name: str,
        context: Any,
        step_number: int
    ) -> Dict[str, Any]:
        """
        Получение метаданных таблицы через SQL-запросы.

        ARGS:
        - schema_name: имя схемы
        - table_name: имя таблицы
        - context: контекст сессии
        - step_number: номер шага

        RETURNS:
        - Словарь с метаданными таблицы
        """
        try:
            # Проверка на безопасность имен (предотвращение SQL-инъекций)
            if not self._is_valid_identifier(schema_name) or not self._is_valid_identifier(table_name):
                raise ValueError("Invalid schema or table name")

            # 1. Формирование SQL-запроса для получения метаданных
            sql = f"""
            SELECT
                cols.column_name,
                cols.data_type,
                cols.character_maximum_length,
                cols.numeric_precision,
                cols.numeric_scale,
                cols.is_nullable,
                cols.column_default,
                col_desc.description as column_comment
            FROM information_schema.columns cols
            LEFT JOIN pg_catalog.pg_statio_all_tables st
                ON st.schemaname = cols.table_schema
                AND st.relname = cols.table_name
            LEFT JOIN pg_catalog.pg_description col_desc
                ON col_desc.objoid = st.relid
                AND col_desc.objsubid = cols.ordinal_position
            WHERE cols.table_schema = $1
                AND cols.table_name = $2
            ORDER BY cols.ordinal_position;
            """

            # 2. Получение описания таблицы отдельным запросом
            table_desc_sql = f"""
            SELECT
                obj_description(c.oid) as table_comment
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = $1 AND n.nspname = $2
            """

            # 3. Выполнение запросов с параметрами для безопасности
            if self.event_bus_logger:
                await self.event_bus_logger.debug(f"Выполнение запроса для получения метаданных таблицы {schema_name}.{table_name}")

            # Получаем DB провайдер из инфраструктурного контекста через прикладной контекст
            db_provider = self.application_context.infrastructure_context.get_provider("default_db")
            if not db_provider:
                raise RuntimeError("DB провайдер не найден в инфраструктурном контексте")

            # Выполняем SQL-запросы через DB провайдер
            columns_result = await db_provider.execute(sql, {"p1": schema_name, "p2": table_name})
            table_desc_result = await db_provider.execute(table_desc_sql, {"p1": table_name, "p2": schema_name})

            # 4. Проверка результатов
            if not columns_result or not hasattr(columns_result, 'rows') or not columns_result.rows:
                if self.event_bus_logger:
                    await self.event_bus_logger.warning(f"Таблица {schema_name}.{table_name} не найдена или не имеет столбцов")
                return {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "description": "Таблица не найдена или не имеет столбцов",
                    "columns": [],
                    "constraints": [],
                    "examples": []
                }

            # 5. Получение описания таблицы
            table_description = "Без описания"
            if table_desc_result and hasattr(table_desc_result, 'rows') and table_desc_result.rows:
                first_row = table_desc_result.rows[0]
                if hasattr(first_row, '__getitem__'):  # Если это Row-like объект
                    table_comment = first_row.get("table_comment", "") if hasattr(first_row, 'get') else first_row[0]
                else:
                    # Если это объект с атрибутами
                    table_comment = getattr(first_row, 'table_comment', "")

                if table_comment and isinstance(table_comment, str) and table_comment.strip():
                    table_description = table_comment.strip()
                    if self.event_bus_logger:
                        await self.event_bus_logger.debug(f"Получено описание таблицы: {table_description}")
                else:
                    if self.event_bus_logger:
                        await self.event_bus_logger.debug("Описание таблицы отсутствует или пустое")

            # 6. Преобразование результата в структурированный формат
            columns = []

            for row in columns_result.rows:
                # Правильное извлечение данных из результата
                if hasattr(row, '__getitem__'):  # Если это Row-like объект
                    column_name = row.get('column_name') if hasattr(row, 'get') else row[0]
                    data_type = row.get('data_type') if hasattr(row, 'get') else row[1]
                    char_max_len = row.get('character_maximum_length') if hasattr(row, 'get') else row[2]
                    num_precision = row.get('numeric_precision') if hasattr(row, 'get') else row[3]
                    num_scale = row.get('numeric_scale') if hasattr(row, 'get') else row[4]
                    is_nullable = row.get('is_nullable') if hasattr(row, 'get') else row[5]
                    column_default = row.get('column_default') if hasattr(row, 'get') else row[6]
                    column_comment = row.get('column_comment') if hasattr(row, 'get') else row[7]
                else:
                    # Если это объект с атрибутами
                    column_name = getattr(row, 'column_name', "")
                    data_type = getattr(row, 'data_type', "")
                    char_max_len = getattr(row, 'character_maximum_length', None)
                    num_precision = getattr(row, 'numeric_precision', None)
                    num_scale = getattr(row, 'numeric_scale', None)
                    is_nullable = getattr(row, 'is_nullable', "")
                    column_default = getattr(row, 'column_default', None)
                    column_comment = getattr(row, 'column_comment', "")

                # Обработка информации о столбце
                column_info = {
                    "column_name": column_name or "",
                    "data_type": data_type or "",
                    "character_maximum_length": char_max_len,
                    "numeric_precision": num_precision,
                    "numeric_scale": num_scale,
                    "is_nullable": is_nullable == "YES" if isinstance(is_nullable, str) else bool(is_nullable),
                    "column_default": column_default,
                    "description": column_comment or "Без описания"
                }
                columns.append(column_info)

            # 7. Получение ограничений (constraints) отдельным запросом
            constraints_sql = f"""
            SELECT
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = $1
                AND tc.table_name = $2
            ORDER BY tc.constraint_name, kcu.ordinal_position;
            """

            constraints_result = await db_provider.execute(constraints_sql, {"p1": schema_name, "p2": table_name})

            constraints = {}
            if constraints_result and hasattr(constraints_result, 'rows'):
                for row in constraints_result.rows:
                    if hasattr(row, '__getitem__'):
                        constraint_name = row.get('constraint_name') if hasattr(row, 'get') else row[0]
                        constraint_type = row.get('constraint_type') if hasattr(row, 'get') else row[1]
                        column_name = row.get('column_name') if hasattr(row, 'get') else row[2]
                    else:
                        constraint_name = getattr(row, 'constraint_name', "")
                        constraint_type = getattr(row, 'constraint_type', "")
                        column_name = getattr(row, 'column_name', "")

                    if constraint_name and constraint_type:
                        if constraint_name not in constraints:
                            constraints[constraint_name] = {
                                "name": constraint_name,
                                "type": constraint_type,
                                "columns": []
                            }
                        constraints[constraint_name]["columns"].append(column_name)

            # 8. Формирование итогового результата
            metadata = {
                "schema_name": schema_name,
                "table_name": table_name,
                "description": table_description,
                "columns": columns,
                "constraints": list(constraints.values()),
                "examples": []  # Примеры данных будут добавлены позже при необходимости
            }

            # 9. Логирование успешного получения метаданных
            column_count = len(columns)
            constraint_count = len(constraints)
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Получены метаданные для таблицы {schema_name}.{table_name}: колонок={column_count}, ограничений={constraint_count}")

            return metadata

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка получения метаданных для таблицы {schema_name}.{table_name}: {str(e)}", exc_info=True)
            # Возвращаем базовую структуру даже при ошибке
            return {
                "schema_name": schema_name,
                "table_name": table_name,
                "description": f"Ошибка получения метаданных: {str(e)}",
                "columns": [],
                "constraints": [],
                "examples": []
            }

    async def get_tables_structure(self, table_list: list, schema_name: str = "Lib") -> Dict[str, Any]:
        """
        Получение структуры нескольких таблиц.

        ARGS:
        - table_list: список имен таблиц
        - schema_name: имя схемы (по умолчанию "Lib")

        RETURNS:
        - Словарь с метаданными для каждой таблицы
        """
        result = {}
        # В новой архитектуре контекст сессии создается в рамках прикладного контекста
        # Используем существующий контекст из application_context
        # Если data_context не существует, используем self.application_context как сессионный контекст
        session_context = getattr(self.application_context, 'data_context', self.application_context)

        for table_name in table_list:
            try:
                table_metadata = await self.get_table_metadata(
                    schema_name=schema_name,
                    table_name=table_name,
                    context=session_context,
                    step_number=1
                )
                result[f"{schema_name}.{table_name}"] = table_metadata
            except Exception as e:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"Ошибка получения метаданных для таблицы {schema_name}.{table_name}: {str(e)}")
                # Добавляем базовую информацию даже при ошибке
                result[f"{schema_name}.{table_name}"] = {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "description": f"Ошибка получения метаданных: {str(e)}",
                    "columns": [],
                    "constraints": [],
                    "examples": []
                }

        return result

    def _is_valid_identifier(self, identifier: str) -> bool:
        """
        Проверка, является ли идентификатор (имя схемы/таблицы) безопасным.

        ARGS:
        - identifier: имя для проверки

        RETURNS:
        - True если имя безопасно, иначе False
        """
        if not identifier or len(identifier) > 128:
            return False

        # Проверяем, что имя состоит только из букв, цифр и подчеркиваний
        import re
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier))