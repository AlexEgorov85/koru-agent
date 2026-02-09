from asyncio.log import logger
from typing import Any, Dict, List
from core.session_context.base_session_context import BaseSessionContext
from core.skills.base_skill import BaseSkill
from core.skills.table_description.schema import TableDescriptionParams
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus


class TableDescriptionSkill(BaseSkill):
    name = "table_description"

    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        logger.info(f"Инициализирован навык получения описания: {self.name}")
    
    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="table_description.get_description",
                description="Получение описания таблицы в формате, оптимальном для LLM",
                parameters_schema=TableDescriptionParams.model_json_schema(),
                paremeter_class = TableDescriptionParams,
                skill_name=self.name,
                visiable=False
            )
        ]
    
    async def execute(self, capability: Capability, parameters: Any, context: BaseSessionContext) -> Any:
        """
        Выполнение capability навыка получения описания таблицы.
        
        ИЗМЕНЕНИЯ:
        - parameters теперь может быть объектом TableDescriptionParams
        - Навык работает с объектом вместо словаря
        - Нет необходимости в валидации - она выполнена ранее
        """
        try:
            # Если parameters - словарь, конвертируем в объект
            if isinstance(parameters, dict):
                params_obj = TableDescriptionParams(**parameters)
            else:
                params_obj = parameters  # Уже объект TableDescriptionParams
            
            # Используем объект параметров напрямую
            return await self._get_description(params_obj, context)
            
        except Exception as e:
            logger.exception(f"Ошибка выполнения capability {capability.name}: {str(e)}")
            return self._build_error_result(
                context=context,
                error_message=str(e),
                error_type="EXECUTION_ERROR"
            )
        

    async def _get_description(self, parameters: TableDescriptionParams, context: BaseSessionContext, step_number: int) -> ExecutionResult:
        """
        Получение описания таблицы с метаданными.
        
        ПРОЦЕСС:
        1. Валидация параметров через Pydantic
        2. Получение метаданных таблицы через tool_port
        3. Форматирование для LLM в запрошенном формате
        4. Построение ExecutionResult
        
        ПАРАМЕТРЫ:
        - parameters: параметры от LLM
        - context: контекст сессии
        - step_number: номер текущего шага
        
        ВОЗВРАЩАЕТ:
        ExecutionResult с результатом или ошибкой
        """
        try:
            # 1. Получение метаданных таблицы
            metadata = await self._get_table_metadata(
                schema_name=parameters.schema_name,
                table_name=parameters.table_name,
                context=context,
                step_number=step_number
            )
            
            # 3. Форматирование для LLM в запрошенном формате
            description = self._format_for_llm(
                metadata=metadata,
                format_type=parameters.format,
                include_examples=parameters.include_examples,
                max_examples=parameters.max_examples
            )
            
            # 4. Построение успешного результата
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                observation_item_id=None,  # Будет установлен в ExecutionGateway
                result={
                    "schema_name": parameters.schema_name,
                    "table_name": parameters.table_name,
                    "description": description,
                    "format": parameters.format,
                    "has_examples": parameters.include_examples and len(metadata.get("examples", [])) > 0
                },
                summary=f"Получено описание таблицы {parameters.schema_name}.{parameters.table_name} в формате {parameters.format}",
                error=None
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения описания таблицы: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                observation_item_id=None,
                result=None,
                summary=str(e),
                error=f"METADATA_ERROR: {str(e)}"
            )
    
    
    async def _get_table_metadata(self, schema_name: str, table_name: str, context: BaseSessionContext, step_number: int) -> Dict[str, Any]:
        """
        Получение метаданных таблицы через SQL Tool.
        
        ИСПРАВЛЕНИЯ:
        1. Корректная обработка результатов SQL-запросов
        2. Правильное извлечение описания таблицы
        3. Корректная обработка ограничений (constraints)
        4. Обработка пустых результатов
        5. Формирование правильной структуры метаданных
        """
        try:
            # 1. Формирование SQL-запроса для получения метаданных
            sql = f"""
            SELECT 
                cols.ordinal_position,
                cols.column_name,
                cols.data_type,
                cols.character_maximum_length,
                cols.numeric_precision,
                cols.numeric_scale,
                cols.is_nullable,
                cols.column_default,
                pgd.description as column_comment,
                tc.constraint_type,
                tc.constraint_name
            FROM information_schema.columns cols
            LEFT JOIN pg_catalog.pg_statio_all_tables st 
                ON st.schemaname = cols.table_schema 
                AND st.relname = cols.table_name
            LEFT JOIN pg_catalog.pg_description pgd 
                ON pgd.objoid = st.relid 
                AND pgd.objsubid = cols.ordinal_position
            LEFT JOIN information_schema.key_column_usage kcu 
                ON kcu.table_schema = cols.table_schema 
                AND kcu.table_name = cols.table_name 
                AND kcu.column_name = cols.column_name
            LEFT JOIN information_schema.table_constraints tc 
                ON tc.constraint_name = kcu.constraint_name
            WHERE cols.table_schema = '{schema_name}' 
                AND cols.table_name = '{table_name}'
            ORDER BY cols.ordinal_position;
            """
            
            # 2. Получение описания таблицы отдельным запросом
            table_desc_sql = f"""
            SELECT 
                obj_description((oid)::regclass) as table_comment
            FROM pg_catalog.pg_class
            WHERE 
                relname = '{table_name}' AND 
                relnamespace = (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = '{schema_name}')
            """
            
            # 3. Выполнение запросов
            logger.debug(f"Выполнение запроса для получения метаданных таблицы {schema_name}.{table_name}")
            columns_result = await self.system_context.execute_sql_query(query=sql)
            table_desc_result = await self.system_context.execute_sql_query(query=table_desc_sql)
            
            # 4. Проверка результатов
            if not columns_result or not hasattr(columns_result, 'rows') or not columns_result.rows:
                logger.warning(f"Таблица {schema_name}.{table_name} не найдена или не имеет столбцов")
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
                # Правильное извлечение описания из результата
                first_row = table_desc_result.rows[0]
                if hasattr(first_row, 'get'):
                    table_comment = first_row.get("table_comment")
                else:
                    # Если это не словарь, а объект с атрибутами
                    table_comment = getattr(first_row, 'table_comment', None)
                
                if table_comment and isinstance(table_comment, str) and table_comment.strip():
                    table_description = table_comment.strip()
                    logger.debug(f"Получено описание таблицы: {table_description}")
                else:
                    logger.debug("Описание таблицы отсутствует или пустое")
            else:
                logger.debug("Не удалось получить описание таблицы - пустой результат")
            
            # 6. Преобразование результата в структурированный формат
            columns = []
            constraints = {}
            
            for row in columns_result.rows:
                # Правильное извлечение данных из результата
                column_name = getattr(row, 'column_name', None)
                if column_name is None and hasattr(row, 'get'):
                    column_name = row.get('column_name')
                
                data_type = getattr(row, 'data_type', None)
                if data_type is None and hasattr(row, 'get'):
                    data_type = row.get('data_type')
                
                is_nullable = getattr(row, 'is_nullable', None)
                if is_nullable is None and hasattr(row, 'get'):
                    is_nullable = row.get('is_nullable')
                
                column_default = getattr(row, 'column_default', None)
                if column_default is None and hasattr(row, 'get'):
                    column_default = row.get('column_default')
                
                column_comment = getattr(row, 'column_comment', None)
                if column_comment is None and hasattr(row, 'get'):
                    column_comment = row.get('column_comment')
                
                # Обработка информации о столбце
                column_info = {
                    "column_name": column_name if column_name is not None else "",
                    "data_type": data_type if data_type is not None else "",
                    "character_maximum_length": getattr(row, 'character_maximum_length', None),
                    "numeric_precision": getattr(row, 'numeric_precision', None),
                    "numeric_scale": getattr(row, 'numeric_scale', None),
                    "is_nullable": is_nullable == "YES" if isinstance(is_nullable, str) else bool(is_nullable),
                    "column_default": column_default,
                    "description": column_comment if column_comment and isinstance(column_comment, str) else "Без описания"
                }
                columns.append(column_info)
                
                # Обработка ограничений
                constraint_type = getattr(row, 'constraint_type', None)
                if constraint_type is None and hasattr(row, 'get'):
                    constraint_type = row.get('constraint_type')
                    
                constraint_name = getattr(row, 'constraint_name', None)
                if constraint_name is None and hasattr(row, 'get'):
                    constraint_name = row.get('constraint_name')
                    
                column_name_val = column_name if column_name is not None else ""
                
                if constraint_type and constraint_name:
                    if constraint_name not in constraints:
                        constraints[constraint_name] = {
                            "name": constraint_name,
                            "type": constraint_type,
                            "columns": []
                        }
                    constraints[constraint_name]["columns"].append(column_name_val)
            
            # 7. Формирование итогового результата
            metadata = {
                "schema_name": schema_name,
                "table_name": table_name,
                "description": table_description,
                "columns": columns,
                "constraints": list(constraints.values()),
                "examples": []  # Примеры данных будут добавлены позже при необходимости
            }
            
            # 8. Логирование успешного получения метаданных
            column_count = len(columns)
            constraint_count = len(constraints)
            logger.info(f"Получены метаданные для таблицы {schema_name}.{table_name}: колонок={column_count}, ограничений={constraint_count}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Ошибка получения метаданных для таблицы {schema_name}.{table_name}: {str(e)}", exc_info=True)
            # Возвращаем базовую структуру даже при ошибке
            return {
                "schema_name": schema_name,
                "table_name": table_name,
                "description": f"Ошибка получения метаданных: {str(e)}",
                "columns": [],
                "constraints": [],
                "examples": []
            }


    def _format_for_llm(self, metadata: Dict[str, Any], format_type: str, include_examples: bool, max_examples: int) -> str:
        """
        Форматирование метаданных для LLM в запрошенном формате.
        
        ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ:
        - text: простой текстовый формат
        - json: структурированный JSON
        - markdown: формат Markdown для лучшей читаемости
        
        СТРАТЕГИЯ:
        - При ошибке форматирования - fallback на текстовый формат
        - Ограничение количества примеров для безопасности
        - Экранирование специальных символов
        
        ПАРАМЕТРЫ:
        - metadata: метаданные таблицы
        - format_type: запрошенный формат вывода
        - include_examples: включать ли примеры данных
        - max_examples: максимальное количество примеров
        
        ВОЗВРАЩАЕТ:
        Строка с отформатированным описанием таблицы
        """
        try:
            # Выбор формата на основе запроса
            if format_type == "markdown":
                return self._format_markdown(metadata, include_examples, max_examples)
            elif format_type == "json":
                import json
                return json.dumps(self._format_json(metadata, include_examples, max_examples), indent=2, ensure_ascii=False)
            else:  # default to text
                return self._format_text(metadata, include_examples, max_examples)
                
        except Exception as e:
            logger.error(f"Ошибка форматирования для LLM: {str(e)}. Используем fallback на текстовый формат.")
            # Возвращаем базовый текстовый формат как fallback
            return self._format_text(metadata, include_examples, max_examples)

    def _format_markdown(self, metadata: Dict[str, Any], include_examples: bool, max_examples: int) -> str:
        """
        Форматирование метаданных в формате Markdown.
        
        СТРУКТУРА:
        # Заголовок таблицы
        **Описание:** описание таблицы
        
        ## Столбцы
        | Имя | Тип | Описание | Nullable |
        |-----|-----|----------|----------|
        
        ## Ограничения
        
        ## Примеры данных (если запрошено)
        
        ПРЕИМУЩЕСТВА:
        - Четкая структура для LLM
        - Хорошая читаемость для человека
        - Поддержка форматирования таблиц
        """
        lines = []
        table_full_name = f"{metadata.get('schema_name', '')}.{metadata.get('table_name', '')}"
        lines.append(f"# Таблица: `{table_full_name}`")
        lines.append(f"**Описание:** {metadata.get('description', 'Без описания')}")
        lines.append("")
        
        # Столбцы
        lines.append("## Столбцы")
        lines.append("| Имя | Тип | Описание | Nullable | Default |")
        lines.append("|-----|-----|----------|----------|---------|")
        
        for column in metadata.get("columns", []):
            col_name = column.get('column_name', '')
            data_type = column.get('data_type', '')
            description = column.get('description', 'Без описания')
            nullable = 'Да' if column.get('is_nullable') else 'Нет'
            default_val = column.get('column_default', '')
            default_str = default_val if default_val else '-'
            lines.append(f"| `{col_name}` | `{data_type}` | {description} | {nullable} | {default_str} |")
        
        lines.append("")
        
        # Ограничения
        constraints = metadata.get("constraints", [])
        if constraints:
            lines.append("## Ограничения")
            for constraint in constraints:
                constraint_type = constraint.get('type', '').lower()
                if constraint_type == "primary key":
                    lines.append(f"- **Первичный ключ**: {', '.join(constraint.get('columns', []))}")
                elif constraint_type == "foreign key":
                    lines.append(f"- **Внешний ключ**: {', '.join(constraint.get('columns', []))}")
                elif constraint_type == "unique":
                    lines.append(f"- **Уникальность**: {', '.join(constraint.get('columns', []))}")
            lines.append("")
        
        # Примеры данных
        if include_examples and metadata.get("examples"):
            examples = metadata["examples"][:max_examples]
            if examples:
                lines.append("## Примеры данных")
                lines.append("```json")
                for i, example in enumerate(examples):
                    lines.append(f"# Строка {i+1}")
                    if isinstance(example, dict):
                        for key, value in example.items():
                            lines.append(f"{key}: {value}")
                    else:
                        lines.append(str(example))
                    if i < len(examples) - 1:
                        lines.append("---")
                lines.append("```")
        
        return "\n".join(lines)

    def _format_json(self, metadata: Dict[str, Any], include_examples: bool, max_examples: int) -> Dict[str, Any]:
        """
        Форматирование метаданных в формате JSON.
        
        СТРУКТУРА:
        {
            "table": "schema.table",
            "description": "Описание таблицы",
            "columns": [
                {
                    "name": "column_name",
                    "type": "data_type",
                    "description": "Описание колонки",
                    "nullable": true/false,
                    "default": "default_value"
                }
            ],
            "constraints": [
                {
                    "name": "constraint_name",
                    "type": "constraint_type",
                    "columns": ["column1", "column2"]
                }
            ],
            "examples": [...]  # если запрошено
        }
        
        ПРЕИМУЩЕСТВА:
        - Машинно-читаемый формат
        - Легко парсится LLM
        - Структурированные данные
        """
        result = {
            "table": f"{metadata.get('schema_name', '')}.{metadata.get('table_name', '')}",
            "description": metadata.get("description", "Без описания"),
            "columns": [],
            "constraints": metadata.get("constraints", [])
        }
        
        for column in metadata.get("columns", []):
            result["columns"].append({
                "name": column.get("column_name", ""),
                "type": column.get("data_type", ""),
                "description": column.get("description", "Без описания"),
                "nullable": column.get("is_nullable", False),
                "default": column.get("column_default")
            })
        
        # Добавление примеров данных
        if include_examples and metadata.get("examples"):
            result["examples"] = metadata["examples"][:max_examples]
        
        return result

    def _format_text(self, metadata: Dict[str, Any], include_examples: bool, max_examples: int) -> str:
        """
        Форматирование метаданных в простом текстовом формате.
        
        СТРУКТУРА:
        Таблица: schema.table
        Описание: описание таблицы
        
        Столбцы:
        - column_name (data_type)
        Описание: описание колонки
        Nullable: да/нет
        Default: значение
        
        Ограничения:
        - Первичный ключ: column1, column2
        
        Примеры данных:
        1. {example}
        
        ПРЕИМУЩЕСТВА:
        - Простота и надежность
        - Минимальные требования к обработке
        - Универсальность для всех LLM
        """
        lines = []
        table_full_name = f"{metadata.get('schema_name', '')}.{metadata.get('table_name', '')}"
        lines.append(f"Таблица: {table_full_name}")
        lines.append(f"Описание: {metadata.get('description', 'Без описания')}")
        lines.append("")
        lines.append("Столбцы:")
        
        for column in metadata.get("columns", []):
            nullable = "ДА" if column.get("is_nullable") else "НЕТ"
            default_val = column.get("column_default", "нет")
            lines.append(f"- {column.get('column_name', '')} ({column.get('data_type', '')})")
            lines.append(f"  Описание: {column.get('description', 'Без описания')}")
            lines.append(f"  Nullable: {nullable}")
            if default_val != "нет":
                lines.append(f"  Default: {default_val}")
            lines.append("")
        
        # Ограничения
        constraints = metadata.get("constraints", [])
        if constraints:
            lines.append("Ограничения:")
            for constraint in constraints:
                constraint_type = constraint.get('type', '').lower()
                columns_str = ", ".join(constraint.get('columns', []))
                if constraint_type == "primary key":
                    lines.append(f"- Первичный ключ: {columns_str}")
                elif constraint_type == "foreign key":
                    lines.append(f"- Внешний ключ: {columns_str}")
                elif constraint_type == "unique":
                    lines.append(f"- Уникальность: {columns_str}")
            lines.append("")
        
        # Добавление примеров данных
        if include_examples and metadata.get("examples"):
            examples = metadata["examples"][:max_examples]
            if examples:
                lines.append(f"Примеры данных (максимум {max_examples}):")
                for i, example in enumerate(examples):
                    if isinstance(example, dict):
                        example_str = ", ".join([f"{k}={v}" for k, v in example.items()])
                    else:
                        example_str = str(example)
                    lines.append(f"{i+1}. {example_str}")
        
        return "\n".join(lines)
