"""
Инфраструктурный сервис для получения описания таблицы.
"""
import logging
from typing import Dict, Any
from core.infrastructure.service.base_service import BaseService, ServiceInput, ServiceOutput
from core.session_context.base_session_context import BaseSessionContext
from core.system_context.base_system_contex import BaseSystemContext


class TableDescriptionServiceInput(ServiceInput):
    """Входные данные для TableDescriptionService."""
    def __init__(self, schema_name: str, table_name: str, context: BaseSessionContext, step_number: int):
        self.schema_name = schema_name
        self.table_name = table_name
        self.context = context
        self.step_number = step_number


class TableDescriptionServiceOutput(ServiceOutput):
    """Выходные данные для TableDescriptionService."""
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

    @property
    def description(self) -> str:
        return "Сервис для получения описания таблицы с метаданными"
    
    def __init__(self, system_context: BaseSystemContext, name: str = None):
        """
        Инициализация сервиса получения описания таблицы.

        ARGS:
        - system_context: системный контекст для выполнения SQL-запросов
        - name: имя сервиса (опционально)
        """
        super().__init__(system_context, name or "TableDescriptionService")
        self.system_context = system_context

    async def initialize(self) -> bool:
        """
        Инициализация сервиса описания таблицы.
        
        RETURNS:
        - True если инициализация прошла успешно, иначе False
        """
        try:
            self.logger.info("Инициализация сервиса описания таблицы")
            # Проверка доступности системного контекста и необходимых компонентов
            if self.system_context is None:
                self.logger.error("Отсутствует системный контекст")
                return False
            
            self.logger.info("Сервис описания таблицы успешно инициализирован")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации сервиса описания таблицы: {str(e)}")
            return False

    async def execute(self, input_data: TableDescriptionServiceInput) -> TableDescriptionServiceOutput:
        """
        Выполнение сервиса - получение метаданных таблицы.

        ARGS:
        - input_data: входные данные с информацией о схеме и таблице

        RETURNS:
        - TableDescriptionServiceOutput: выходные данные с метаданными таблицы
        """
        metadata = await self.get_table_metadata(
            schema_name=input_data.schema_name,
            table_name=input_data.table_name,
            context=input_data.context,
            step_number=input_data.step_number
        )
        return TableDescriptionServiceOutput(metadata=metadata)

    async def shutdown(self) -> None:
        """
        Завершение работы сервиса описания таблицы.
        """
        try:
            self.logger.info("Завершение работы сервиса описания таблицы")
            # Любые необходимые действия при завершении работы
            self.logger.info("Сервис описания таблицы успешно завершил работу")
        except Exception as e:
            self.logger.error(f"Ошибка при завершении работы сервиса описания таблицы: {str(e)}")
            raise
    
    async def get_table_metadata(
        self, 
        schema_name: str, 
        table_name: str, 
        context: BaseSessionContext,
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
            WHERE cols.table_schema = %s
                AND cols.table_name = %s
            ORDER BY cols.ordinal_position;
            """

            # 2. Получение описания таблицы отдельным запросом
            table_desc_sql = f"""
            SELECT
                obj_description(c.oid) as table_comment
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = %s AND n.nspname = %s
            """

            # 3. Выполнение запросов с параметрами для безопасности
            self.logger.debug(f"Выполнение запроса для получения метаданных таблицы {schema_name}.{table_name}")
            columns_result = await self.system_context.execute_sql_query(
                query=sql,
                parameters=[schema_name, table_name]
            )
            table_desc_result = await self.system_context.execute_sql_query(
                query=table_desc_sql,
                parameters=[table_name, schema_name]
            )

            # 4. Проверка результатов
            if not columns_result or not hasattr(columns_result, 'rows') or not columns_result.rows:
                self.logger.warning(f"Таблица {schema_name}.{table_name} не найдена или не имеет столбцов")
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
                    self.logger.debug(f"Получено описание таблицы: {table_description}")
                else:
                    self.logger.debug("Описание таблицы отсутствует или пустое")

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
            WHERE tc.table_schema = %s
                AND tc.table_name = %s
            ORDER BY tc.constraint_name, kcu.ordinal_position;
            """
            
            constraints_result = await self.system_context.execute_sql_query(
                query=constraints_sql,
                parameters=[schema_name, table_name]
            )
            
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
            self.logger.info(f"Получены метаданные для таблицы {schema_name}.{table_name}: колонок={column_count}, ограничений={constraint_count}")

            return metadata

        except Exception as e:
            self.logger.error(f"Ошибка получения метаданных для таблицы {schema_name}.{table_name}: {str(e)}", exc_info=True)
            # Возвращаем базовую структуру даже при ошибке
            return {
                "schema_name": schema_name,
                "table_name": table_name,
                "description": f"Ошибка получения метаданных: {str(e)}",
                "columns": [],
                "constraints": [],
                "examples": []
            }
    
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