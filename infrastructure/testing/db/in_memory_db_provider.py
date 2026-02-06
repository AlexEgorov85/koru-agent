"""
In-memory провайдер БД для тестирования
"""
from typing import Dict, Any, Optional, List

import json
import sqlite3
from io import StringIO
import threading

from infrastructure.gateways.database_providers.base_provider import BaseDBProvider, DatabaseHealthStatus


class InMemoryDBProvider(BaseDBProvider):
    """
    In-memory провайдер БД
    - Повторяет контракт BaseDBProvider
    - Хранение данных в памяти
    - Поддержка CRUD операций
    - Поддержка транзакций
    - Очистка состояния между тестами
    """
    
    def __init__(self, connection_string: str = "inmemory://", config: Optional[Dict[str, Any]] = None):
        super().__init__(connection_string, config or {})
        self.data_store: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()  # Для потокобезопасности
        self.transaction_stack: List[List[Dict[str, Any]]] = []
        self._is_connected = True
        self.health_status = DatabaseHealthStatus.HEALTHY
    
    async def initialize(self) -> bool:
        """
        Инициализация провайдера
        """
        self._is_connected = True
        self.health_status = DatabaseHealthStatus.HEALTHY
        return True
    
    async def shutdown(self) -> None:
        """
        Завершение работы провайдера
        """
        self._is_connected = False
        self.health_status = DatabaseHealthStatus.UNKNOWN
        self.clear_all_data()
    
    def clear_all_data(self):
        """
        Очистка всех данных между тестами
        """
        with self._lock:
            self.data_store.clear()
            self.query_count = 0
            self.error_count = 0
            self.avg_query_time = 0.0
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Выполнение SQL-запроса в in-memory хранилище
        """
        if not self._is_connected:
            raise RuntimeError("Database not connected")
        
        self.query_count += 1
        start_time = __import__('time').time()
        
        try:
            result = self._execute_query_internal(query, params)
            success = True
        except Exception as e:
            self.error_count += 1
            success = False
            raise e
        finally:
            end_time = __import__('time').time()
            query_time = end_time - start_time
            self._update_metrics(query_time, success)
        
        return result
    
    def _execute_query_internal(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Внутренняя реализация выполнения запроса
        """
        # Приводим параметры к нормальному виду
        if params is None:
            params = {}
        
        # Парсим SQL-запрос для определения типа операции
        query_upper = query.strip().upper()
        
        with self._lock:
            if query_upper.startswith("SELECT"):
                return self._handle_select(query, params)
            elif query_upper.startswith("INSERT"):
                self._handle_insert(query, params)
                return []
            elif query_upper.startswith("UPDATE"):
                self._handle_update(query, params)
                return []
            elif query_upper.startswith("DELETE"):
                self._handle_delete(query, params)
                return []
            else:
                # Для других команд возвращаем пустой результат
                return []
    
    def _handle_select(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Обработка SELECT-запроса
        """
        # Простой парсер для SELECT-запросов
        # Поддерживает базовый синтаксис: SELECT * FROM table WHERE condition
        import re
        
        # Извлекаем имя таблицы
        table_match = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
        if not table_match:
            return []
        
        table_name = table_match.group(1)
        if table_name not in self.data_store:
            return []
        
        # Получаем все записи из таблицы
        records = self.data_store[table_name][:]  # Копируем список
        
        # Применяем условия WHERE если они есть
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+LIMIT|\s+ORDER|$)', query, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1).strip()
            records = self._apply_where_clause(records, where_clause, params)
        
        # Применяем LIMIT если он есть
        limit_match = re.search(r'LIMIT\s+(\d+)', query, re.IGNORECASE)
        if limit_match:
            limit = int(limit_match.group(1))
            records = records[:limit]
        
        # Применяем ORDER BY если он есть
        order_match = re.search(r'ORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?', query, re.IGNORECASE)
        if order_match:
            order_field = order_match.group(1)
            order_dir = order_match.group(2) or 'ASC'
            reverse = order_dir.upper() == 'DESC'
            records.sort(key=lambda x: x.get(order_field, ''), reverse=reverse)
        
        return records
    
    def _apply_where_clause(self, records: List[Dict[str, Any]], where_clause: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Применение WHERE-условия к записям
        """
        # Простая реализация для базовых условий
        # Поддерживает: field = value, field != value, field > value, field < value
        import re
        
        # Заменяем параметры в условии (предполагаем формат $1, $2 или ?)
        processed_clause = where_clause
        if params:
            # Если параметры представлены как список (для ? или $1, $2 и т.д.)
            if isinstance(params, list):
                for i, val in enumerate(params):
                    processed_clause = processed_clause.replace(f"${i+1}", str(val)).replace("?", str(val), 1)
            else:
                # Если параметры представлены как словарь
                for key, value in params.items():
                    processed_clause = processed_clause.replace(f":{key}", str(value))
                    processed_clause = processed_clause.replace(f"@{key}", str(value))
        
        # Применяем фильтрацию
        filtered_records = []
        for record in records:
            if self._evaluate_condition(record, processed_clause):
                filtered_records.append(record)
        
        return filtered_records
    
    def _evaluate_condition(self, record: Dict[str, Any], condition: str) -> bool:
        """
        Оценка условия для записи
        """
        # Простая реализация для базовых операторов
        condition = condition.strip()
        
        # Поддержка простых условий вида: field = value, field != value и т.д.
        operators = ['>=', '<=', '!=', '=', '>', '<']
        for op in operators:
            if op in condition:
                left, right = condition.split(op, 1)
                left = left.strip()
                right = right.strip()
                
                # Убираем кавычки из правой части если они есть
                if right.startswith("'") and right.endswith("'"):
                    right = right[1:-1]
                elif right.startswith('"') and right.endswith('"'):
                    right = right[1:-1]
                
                left_val = record.get(left.strip(), None)
                if left_val is None:
                    return False
                
                # Преобразуем правую часть к типу левой части для сравнения
                try:
                    if isinstance(left_val, int):
                        right = int(right)
                    elif isinstance(left_val, float):
                        right = float(right)
                    elif isinstance(left_val, bool):
                        right = right.lower() in ['true', '1', 'yes', 'on']
                except (ValueError, TypeError):
                    # Если преобразование не удалось, оставляем как строку
                    pass
                
                if op == '=':
                    return left_val == right
                elif op == '!=':
                    return left_val != right
                elif op == '>':
                    return left_val > right
                elif op == '<':
                    return left_val < right
                elif op == '>=':
                    return left_val >= right
                elif op == '<=':
                    return left_val <= right
        
        return False  # Если не удалось распознать условие, возвращаем False
    
    def _handle_insert(self, query: str, params: Dict[str, Any]):
        """
        Обработка INSERT-запроса
        """
        import re
        
        # Извлекаем имя таблицы
        table_match = re.search(r'INTO\s+(\w+)', query, re.IGNORECASE)
        if not table_match:
            raise ValueError("Could not parse table name from INSERT query")
        
        table_name = table_match.group(1)
        
        # Извлекаем имена колонок
        columns_match = re.search(r'\(([^)]+)\)', query, re.IGNORECASE)
        if not columns_match:
            raise ValueError("Could not parse column names from INSERT query")
        
        columns_str = columns_match.group(1)
        columns = [col.strip() for col in columns_str.split(',')]
        
        # Извлекаем значения
        values_match = re.search(r'VALUES\s*\(([^)]+)\)', query, re.IGNORECASE)
        if not values_match:
            raise ValueError("Could not parse values from INSERT query")
        
        values_str = values_match.group(1)
        # Разбираем значения, учитывая возможные запятые внутри строк
        values = self._parse_values_list(values_str, params)
        
        if len(columns) != len(values):
            raise ValueError(f"Number of columns ({len(columns)}) does not match number of values ({len(values)})")
        
        # Создаем новую запись
        new_record = {}
        for i, col in enumerate(columns):
            new_record[col.strip()] = values[i]
        
        # Добавляем запись в таблицу
        if table_name not in self.data_store:
            self.data_store[table_name] = []
        
        self.data_store[table_name].append(new_record)
    
    def _parse_values_list(self, values_str: str, params: Dict[str, Any]) -> List[Any]:
        """
        Разбор списка значений для INSERT-запроса
        """
        values = []
        current_value = ""
        in_quotes = False
        quote_char = None
        i = 0
        
        while i < len(values_str):
            char = values_str[i]
            
            if not in_quotes and (char == "'" or char == '"'):
                in_quotes = True
                quote_char = char
                current_value += char
            elif in_quotes and char == quote_char:
                # Проверяем, экранирован ли символ
                if i + 1 < len(values_str) and values_str[i + 1] == quote_char:
                    # Двойная кавычка - это экранирование
                    current_value += char + values_str[i + 1]
                    i += 1  # Пропускаем следующую кавычку
                else:
                    # Закрывающая кавычка
                    in_quotes = False
                    current_value += char
            elif not in_quotes and char == ',':
                # Завершаем текущее значение
                values.append(current_value.strip())
                current_value = ""
            else:
                current_value += char
            
            i += 1
        
        # Добавляем последнее значение
        if current_value.strip():
            values.append(current_value.strip())
        
        # Обрабатываем параметры (например, $1, $2 или ?)
        processed_values = []
        for value in values:
            value = value.strip()
            if value.startswith("$") and value[1:].isdigit():
                # Это параметр в формате $1, $2 и т.д.
                param_index = int(value[1:]) - 1
                if isinstance(params, list) and param_index < len(params):
                    processed_values.append(params[param_index])
                else:
                    processed_values.append(value)  # Не удалось заменить
            elif value == "?":
                # Это параметр в формате ?, используем первый элемент из params если это список
                if isinstance(params, list) and len(params) > 0:
                    processed_values.append(params.pop(0) if hasattr(params, 'pop') else params[0])
                else:
                    processed_values.append(value)  # Не удалось заменить
            else:
                # Убираем кавычки если это строка
                if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
                    processed_values.append(value[1:-1])
                else:
                    # Если это не строка, возможно это число или null
                    if value.lower() == 'null':
                        processed_values.append(None)
                    elif value.isdigit():
                        processed_values.append(int(value))
                    else:
                        try:
                            processed_values.append(float(value))
                        except ValueError:
                            processed_values.append(value)
        
        return processed_values
    
    def _handle_update(self, query: str, params: Dict[str, Any]):
        """
        Обработка UPDATE-запроса
        """
        import re
        
        # Извлекаем имя таблицы
        table_match = re.search(r'UPDATE\s+(\w+)', query, re.IGNORECASE)
        if not table_match:
            raise ValueError("Could not parse table name from UPDATE query")
        
        table_name = table_match.group(1)
        if table_name not in self.data_store:
            return  # Таблица не существует, выходим
        
        # Извлекаем SET часть
        set_match = re.search(r'SET\s+(.+?)(?:\s+WHERE\b|$)', query, re.IGNORECASE)
        if not set_match:
            raise ValueError("Could not parse SET clause from UPDATE query")
        
        set_clause = set_match.group(1).strip()
        updates = self._parse_set_clause(set_clause, params)
        
        # Извлекаем WHERE часть
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+LIMIT|$)', query, re.IGNORECASE)
        where_clause = where_match.group(1).strip() if where_match else None
        
        # Применяем обновления к записям
        for record in self.data_store[table_name]:
            # Проверяем, удовлетворяет ли запись условию WHERE (если есть)
            if where_clause:
                # Здесь мы должны передать параметры в условие, как в _apply_where_clause
                where_with_params = where_clause
                if params and isinstance(params, dict):
                    for key, value in params.items():
                        where_with_params = where_with_params.replace(f":{key}", str(value))
                        where_with_params = where_with_params.replace(f"@{key}", str(value))
                        
                if not self._evaluate_condition(record, where_with_params):
                    continue
            
            # Применяем обновления
            for field, value in updates.items():
                record[field] = value
    
    def _parse_set_clause(self, set_clause: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Разбор SET-части UPDATE-запроса
        """
        updates = {}
        # Разбираем поля и значения в формате field = value, field2 = value2
        pairs = set_clause.split(',')
        for pair in pairs:
            pair = pair.strip()
            if '=' in pair:
                field, value = pair.split('=', 1)
                field = field.strip()
                value = value.strip()
                
                # Обработка параметров
                if value.startswith("$") and value[1:].isdigit():
                    param_index = int(value[1:]) - 1
                    if isinstance(params, list) and param_index < len(params):
                        updates[field] = params[param_index]
                    else:
                        updates[field] = value
                elif value.startswith("'") and value.endswith("'"):
                    updates[field] = value[1:-1]  # Убираем кавычки
                elif value.startswith('"') and value.endswith('"'):
                    updates[field] = value[1:-1]  # Убираем кавычки
                elif value.lower() == 'null':
                    updates[field] = None
                elif value.isdigit():
                    updates[field] = int(value)
                else:
                    try:
                        updates[field] = float(value)
                    except ValueError:
                        updates[field] = value  # Оставляем как строку
        
        return updates
    
    def _handle_delete(self, query: str, params: Dict[str, Any]):
        """
        Обработка DELETE-запроса
        """
        import re
        
        # Извлекаем имя таблицы
        table_match = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
        if not table_match:
            raise ValueError("Could not parse table name from DELETE query")
        
        table_name = table_match.group(1)
        if table_name not in self.data_store:
            return  # Таблица не существует, выходим
        
        # Извлекаем WHERE часть
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+LIMIT|$)', query, re.IGNORECASE)
        where_clause = where_match.group(1).strip() if where_match else None
        
        if not where_clause:
            # Удаляем все записи из таблицы
            self.data_store[table_name] = []
            return
        
        # Фильтруем записи, которые НЕ удовлетворяют условию WHERE
        filtered_records = []
        for record in self.data_store[table_name]:
            # Здесь мы должны передать параметры в условие, как в _apply_where_clause
            where_with_params = where_clause
            if params and isinstance(params, dict):
                for key, value in params.items():
                    where_with_params = where_with_params.replace(f":{key}", str(value))
                    where_with_params = where_with_params.replace(f"@{key}", str(value))
                    
            # Если запись НЕ удовлетворяет условию WHERE, оставляем её
            if not self._evaluate_condition(record, where_with_params):
                filtered_records.append(record)
        
        # Заменяем данные таблицы отфильтрованными записями
        self.data_store[table_name] = filtered_records
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности
        """
        return {
            "status": self.health_status.value,
            "connection_string": self.connection_string,
            "connected": self._is_connected,
            "tables_count": len(self.data_store),
            "total_records": sum(len(records) for records in self.data_store.values()),
            "query_count": self.query_count,
            "error_count": self.error_count
        }