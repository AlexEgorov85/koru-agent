"""
Память ошибок (Failure Memory) для хранения истории сбоев.

АРХИТЕКТУРА:
- ЕДИНЫЙ источник истины об ошибках
- Хранит историю ошибок по capability с TTL
- Предоставляет методы для принятия решений о переключении паттернов
- Интегрируется с ErrorClassifier для записи типа ошибки

ОТВЕТСТВЕННОСТЬ:
- Запись ошибок с классификацией
- Подсчёт количества ошибок по capability
- Детекция необходимости переключения паттерна
- Временная очистка записей (TTL)
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from core.models.enums.common_enums import ErrorType


class FailureRecord:
    """
    Запись об ошибке в памяти.
    
    ATTRIBUTES:
    - capability: имя capability где произошла ошибка
    - error_type: тип ошибки (TRANSIENT, LOGIC, VALIDATION, FATAL)
    - count: общее количество ошибок этого типа
    - consecutive: количество последовательных ошибок этого типа
    - last_attempt: время последней ошибки
    """
    
    def __init__(
        self,
        capability: str,
        error_type: ErrorType,
        timestamp: datetime
    ):
        self.capability = capability
        self.error_type = error_type
        self.count = 1
        self.consecutive = 1
        self.last_attempt = timestamp
    
    def increment(self, timestamp: datetime, same_type: bool):
        """
        Увеличить счётчики ошибки.
        
        ПАРАМЕТРЫ:
        - timestamp: время текущей ошибки
        - same_type: True если тип ошибки совпадает с предыдущим
        """
        self.count += 1
        self.last_attempt = timestamp
        
        if same_type:
            self.consecutive += 1
        else:
            self.consecutive = 1
    
    def to_dict(self) -> Dict:
        """Конвертация в словарь."""
        return {
            "capability": self.capability,
            "error_type": self.error_type.value,
            "count": self.count,
            "consecutive": self.consecutive,
            "last_attempt": self.last_attempt.isoformat()
        }


class FailureMemory:
    """
    Память ошибок — ЕДИНЫЙ источник истины.
    
    ПРИНЦИПЫ:
    - Хранит ошибки по ключу "capability:error_type"
    - Автоматически очищает старые записи (TTL)
    - Предоставляет методы для принятия решений
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    failure_memory = FailureMemory(max_age_minutes=30)
    
    # Запись ошибки
    failure_memory.record(
        capability="search_database.execute",
        error_type=ErrorType.TRANSIENT,
        timestamp=datetime.now()
    )
    
    # Проверка необходимости переключения паттерна
    if failure_memory.should_switch_pattern("search_database.execute"):
        # Переключить паттерн
        pass
    
    # Сброс при успехе
    failure_memory.reset("search_database.execute")
    """
    
    # Пороги для принятия решений
    CONSECUTIVE_LOGIC_THRESHOLD = 3  # 3 последовательные LOGIC ошибки → switch
    TOTAL_ERRORS_THRESHOLD = 2       # 2 ошибки любого типа → switch
    
    def __init__(self, max_age_minutes: int = 30):
        """
        Инициализация памяти ошибок.
        
        ПАРАМЕТРЫ:
        - max_age_minutes: время жизни записей в минутах (TTL)
        """
        self._failures: Dict[str, FailureRecord] = {}
        self._max_age = timedelta(minutes=max_age_minutes)
    
    def record(
        self,
        capability: str,
        error_type: ErrorType,
        timestamp: Optional[datetime] = None
    ):
        """
        Записать ошибку в память.
        
        ПАРАМЕТРЫ:
        - capability: имя capability где произошла ошибка
        - error_type: тип ошибки
        - timestamp: время ошибки (по умолчанию now)
        
        АЛГОРИТМ:
        1. Создать ключ "capability:error_type"
        2. Если запись существует — увеличить счётчики
        3. Если запись не существует — создать новую
        4. Очистить старые записи
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        key = self._make_key(capability, error_type)
        
        if key in self._failures:
            # Проверка совпадения типа ошибки
            same_type = self._failures[key].error_type == error_type
            self._failures[key].increment(timestamp, same_type)
        else:
            self._failures[key] = FailureRecord(
                capability=capability,
                error_type=error_type,
                timestamp=timestamp
            )
        
        # Очистка старых записей
        self._cleanup()
    
    def reset(self, capability: str):
        """
        Сбросить счётчик ошибок при успехе.
        
        ПАРАМЕТРЫ:
        - capability: имя capability для сброса
        
        АЛГОРИТМ:
        - Удаляет все записи для данной capability
        - Вызывается при успешном выполнении
        """
        keys_to_remove = [
            key for key in self._failures.keys()
            if capability in key
        ]
        for key in keys_to_remove:
            del self._failures[key]
    
    def should_switch_pattern(self, capability: str) -> bool:
        """
        Проверить необходимость переключения паттерна.

        ПАРАМЕТРЫ:
        - capability: имя capability для проверки

        ВОЗВРАЩАЕТ:
        - bool: True если нужно переключить паттерн

        КРИТЕРИИ:
        - 3 последовательные LOGIC ошибки → switch
        - 2 ошибки любого типа → switch
        """
        self._cleanup()
        
        # Собираем все записи для данной capability
        capability_records = [
            record for key, record in self._failures.items()
            if capability in key
        ]
        
        if not capability_records:
            return False
        
        # Подсчитываем общее количество ошибок
        total_errors = sum(record.count for record in capability_records)
        
        # 2 ошибки любого типа → switch
        if total_errors >= self.TOTAL_ERRORS_THRESHOLD:
            return True
        
        # 3 последовательные LOGIC ошибки
        for record in capability_records:
            if (record.error_type == ErrorType.LOGIC and
                    record.consecutive >= self.CONSECUTIVE_LOGIC_THRESHOLD):
                return True
        
        return False
    
    def get_count(self, capability: str, error_type: Optional[ErrorType] = None) -> int:
        """
        Получить количество ошибок для capability.

        ПАРАМЕТРЫ:
        - capability: имя capability
        - error_type: тип ошибки (опционально, если None — суммарно)

        ВОЗВРАЩАЕТ:
        - int: количество ошибок

        ⚠️ ТОЛЬКО ЧТЕНИЕ: не принимает решений!
        """
        self._cleanup()

        total = 0
        for key, record in self._failures.items():
            if capability in key:
                if error_type is None or record.error_type == error_type:
                    total += record.count

        return total

    def get_failures(self, capability: str) -> List[FailureRecord]:
        """
        Получить все записи об ошибках для capability.

        ПАРАМЕТРЫ:
        - capability: имя capability

        ВОЗВРАЩАЕТ:
        - List[FailureRecord]: список записей

        ⚠️ ТОЛЬКО ЧТЕНИЕ: не принимает решений!
        Pattern сам анализирует failures и принимает решения.
        """
        self._cleanup()

        return [
            record for key, record in self._failures.items()
            if capability in key
        ]

    # ========================================================================
    # DEPRECATED: decision logic удалена (Этап 2)
    # ========================================================================

    # def should_switch_pattern(self, capability: str) -> bool:
    #     """⚠️ DEPRECATED: Pattern сам решает когда переключаться."""
    #     raise NotImplementedError(
    #         "should_switch_pattern() удалён в Этапе 2. "
    #         "Pattern сам анализирует failures через context.get_failures()."
    #     )

    # def get_recommendation(self, capability: str) -> Optional[str]:
    #     """⚠️ DEPRECATED: Pattern сам принимает решения."""
    #     raise NotImplementedError(
    #         "get_recommendation() удалён в Этапе 2. "
    #         "Pattern сам решает как обрабатывать ошибки."
    #     )

    def get_recent_errors(self, capability: str, limit: int = 5) -> List[FailureRecord]:
        """
        Получить последние ошибки для capability.
        
        ПАРАМЕТРЫ:
        - capability: имя capability
        - limit: максимальное количество записей
        
        ВОЗВРАЩАЕТ:
        - List[FailureRecord]: список записей об ошибках
        """
        self._cleanup()
        
        records = [
            record for key, record in self._failures.items()
            if capability in key
        ]
        
        # Сортировка по времени (последние первыми)
        records.sort(key=lambda r: r.last_attempt, reverse=True)
        
        return records[:limit]
    
    def get_all_failures(self) -> Dict[str, FailureRecord]:
        """
        Получить все записи об ошибках.
        
        ВОЗВРАЩАЕТ:
        - Dict[str, FailureRecord]: все записи
        """
        self._cleanup()
        return self._failures.copy()
    
    def clear(self):
        """Очистить всю память ошибок."""
        self._failures.clear()
    
    def _make_key(self, capability: str, error_type: ErrorType) -> str:
        """
        Создать ключ для хранения записи.
        
        ПАРАМЕТРЫ:
        - capability: имя capability
        - error_type: тип ошибки
        
        ВОЗВРАЩАЕТ:
        - str: ключ в формате "capability:error_type"
        """
        return f"{capability}:{error_type.value}"
    
    def _cleanup(self):
        """
        Удалить старые записи (TTL).
        
        АЛГОРИТМ:
        1. Получить текущее время
        2. Найти записи старше max_age
        3. Удалить найденные записи
        """
        now = datetime.now()
        expired = [
            key for key, record in self._failures.items()
            if now - record.last_attempt > self._max_age
        ]
        for key in expired:
            del self._failures[key]
    
    def __len__(self) -> int:
        """Количество записей в памяти."""
        return len(self._failures)
    
    def __repr__(self) -> str:
        """Строковое представление."""
        return f"FailureMemory(failures={len(self._failures)})"
