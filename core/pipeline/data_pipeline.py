"""
Конвейер обработки данных (Data Pipeline).

АРХИТЕКТУРА:
- Явный конвейер с этапами обработки
- Валидация данных на каждом этапе
- Трансформация и обогащение данных
- Обработка ошибок с откатом
- Аудит прохождения через этапы

ПРЕИМУЩЕСТВА:
- ✅ Явный поток данных
- ✅ Модульные этапы обработки
- ✅ Валидация на каждом этапе
- ✅ Откат при ошибках
- ✅ Аудит прохождения
"""
import asyncio
import inspect
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from core.infrastructure.event_bus import (
    EventDomain,
    EventType,
)
from core.errors import ErrorHandler, ErrorContext, get_error_handler


logger = logging.getLogger(__name__)


class PipelineStageType(Enum):
    """Тип этапа конвейера."""
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    ENRICHMENT = "enrichment"
    FILTER = "filter"
    AGGREGATION = "aggregation"
    CUSTOM = "custom"


class PipelineStatus(Enum):
    """Статус выполнения конвейера."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class PipelineContext:
    """
    Контекст выполнения конвейера.
    
    ATTRIBUTES:
    - data: данные конвейера
    - metadata: метаданные
    - stage_results: результаты этапов
    - started_at: время начала
    - completed_at: время завершения
    - status: статус выполнения
    """
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    stage_results: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: PipelineStatus = PipelineStatus.PENDING
    current_stage: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "data": str(self.data) if self.data else None,
            "metadata": self.metadata,
            "stage_results": self.stage_results,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "current_stage": self.current_stage,
        }


@dataclass
class StageResult:
    """Результат выполнения этапа."""
    stage_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "stage_name": self.stage_name,
            "success": self.success,
            "data": str(self.data) if self.data else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class PipelineStage(ABC):
    """
    Базовый класс этапа конвейера.
    
    RESPONSIBILITIES:
    - Обработка данных
    - Валидация входных/выходных данных
    - Возврат результата
    """
    
    def __init__(self, name: str, stage_type: PipelineStageType = PipelineStageType.CUSTOM):
        self.name = name
        self.stage_type = stage_type
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def process(self, data: Any, context: PipelineContext) -> Any:
        """
        Обработка данных.
        
        ARGS:
        - data: входные данные
        - context: контекст конвейера
        
        RETURNS:
        - Any: обработанные данные
        
        RAISES:
        - Exception: если обработка не удалась
        """
        pass
    
    async def validate(self, data: Any, context: PipelineContext) -> bool:
        """
        Валидация данных перед обработкой.
        
        ARGS:
        - data: данные для валидации
        - context: контекст конвейера
        
        RETURNS:
        - bool: True если валидация успешна
        """
        return True
    
    async def rollback(self, data: Any, context: PipelineContext) -> Any:
        """
        Откат изменений этапа.
        
        ARGS:
        - data: текущие данные
        - context: контекст конвейера
        
        RETURNS:
        - Any: данные после отката
        """
        # По умолчанию откат не требуется
        return data


class ValidationStage(PipelineStage):
    """
    Этап валидации данных.
    
    FEATURES:
    - Проверка схемы данных
    - Проверка обязательных полей
    - Проверка типов данных
    """
    
    def __init__(self, name: str, validators: List[Callable] = None):
        super().__init__(name, PipelineStageType.VALIDATION)
        self._validators = validators or []
    
    async def process(self, data: Any, context: PipelineContext) -> Any:
        """Валидация данных."""
        for validator in self._validators:
            if not await self._call_validator(validator, data, context):
                validator_name = getattr(validator, '__name__', str(validator))
                raise PipelineValidationError(f"Validation failed: {validator_name}")
        
        self._logger.debug(f"Валидация успешна для этапа {self.name}")
        return data
    
    async def _call_validator(self, validator: Callable, data: Any, context: PipelineContext) -> bool:
        """Вызов валидатора."""
        try:
            if hasattr(validator, '__await__'):
                return await validator(data, context)
            else:
                return validator(data, context)
        except Exception as e:
            validator_name = getattr(validator, '__name__', str(validator))
            self._logger.warning(f"Валидатор {validator_name} вернул False: {e}")
            return False


class TransformationStage(PipelineStage):
    """
    Этап трансформации данных.
    
    FEATURES:
    - Преобразование формата данных
    - Нормализация
    - Сериализация/десериализация
    """
    
    def __init__(self, name: str, transformer: Callable):
        super().__init__(name, PipelineStageType.TRANSFORMATION)
        self._transformer = transformer
        self._is_async = hasattr(transformer, '__await__') or inspect.iscoroutinefunction(transformer)
    
    async def process(self, data: Any, context: PipelineContext) -> Any:
        """Трансформация данных."""
        if self._is_async:
            return await self._transformer(data, context)
        else:
            return self._transformer(data, context)


class EnrichmentStage(PipelineStage):
    """
    Этап обогащения данных.
    
    FEATURES:
    - Добавление дополнительных данных
    - Связывание с другими источниками
    - Вычисление производных полей
    """
    
    def __init__(self, name: str, enrichers: List[Callable] = None):
        super().__init__(name, PipelineStageType.ENRICHMENT)
        self._enrichers = enrichers or []
    
    async def process(self, data: Any, context: PipelineContext) -> Any:
        """Обогащение данных."""
        result = data
        
        for enricher in self._enrichers:
            if hasattr(enricher, '__await__'):
                result = await enricher(result, context)
            else:
                result = enricher(result, context)
        
        return result


class PipelineError(Exception):
    """Ошибка конвейера."""
    def __init__(self, message: str, stage: str = None):
        self.message = message
        self.stage = stage
        super().__init__(self.message)


class PipelineValidationError(PipelineError):
    """Ошибка валидации в конвейере."""
    pass


class DataPipeline:
    """
    Конвейер обработки данных.
    
    FEATURES:
    - Последовательное выполнение этапов
    - Валидация на каждом этапе
    - Откат при ошибках
    - Аудит выполнения
    - Статистика выполнения
    
    USAGE:
    ```python
    # Создание конвейера
    pipeline = DataPipeline(name="data_processing")
    
    # Добавление этапов
    pipeline.add_stage(ValidationStage("validate", validators=[...]))
    pipeline.add_stage(TransformationStage("transform", transformer=...))
    pipeline.add_stage(EnrichmentStage("enrich", enrichers=[...]))
    
    # Выполнение
    result = await pipeline.process(input_data)
    
    # Статистика
    stats = pipeline.get_stats()
    ```
    """

    def __init__(
        self,
        name: str,
        event_bus=None,
        error_handler: Optional[ErrorHandler] = None,
    ):
        """
        Инициализация конвейера.

        ARGS:
        - name: имя конвейера
        - event_bus: шина событий (UnifiedEventBus)
        - error_handler: обработчик ошибок
        """
        self.name = name
        self._event_bus = event_bus
        self._error_handler = error_handler or get_error_handler()
        
        self._stages: List[PipelineStage] = []
        self._stage_index: Dict[str, int] = {}
        
        self._execution_count = 0
        self._success_count = 0
        self._error_count = 0
        self._total_duration_ms = 0.0
        
        self._logger = logging.getLogger(f"{__name__}.DataPipeline")
        self._logger.info(f"DataPipeline '{name}' создан")
    
    def add_stage(self, stage: PipelineStage):
        """
        Добавление этапа конвейера.
        
        ARGS:
        - stage: этап для добавления
        """
        self._stages.append(stage)
        self._stage_index[stage.name] = len(self._stages) - 1
        self._logger.debug(f"Добавлен этап '{stage.name}' ({stage.stage_type.value})")
    
    def remove_stage(self, stage_name: str) -> bool:
        """
        Удаление этапа конвейера.
        
        ARGS:
        - stage_name: имя этапа
        
        RETURNS:
        - bool: True если этап удалён
        """
        if stage_name not in self._stage_index:
            return False
        
        index = self._stage_index[stage_name]
        self._stages.pop(index)
        del self._stage_index[stage_name]
        
        # Обновление индексов
        self._stage_index = {s.name: i for i, s in enumerate(self._stages)}
        
        self._logger.debug(f"Удалён этап '{stage_name}'")
        return True
    
    async def process(self, data: Any, metadata: Dict = None) -> Any:
        """
        Обработка данных через все этапы конвейера.
        
        ARGS:
        - data: входные данные
        - metadata: метаданные
        
        RETURNS:
        - Any: обработанные данные
        
        RAISES:
        - PipelineError: если обработка не удалась
        """
        self._execution_count += 1
        start_time = time.time()
        
        # Создание контекста
        context = PipelineContext(
            data=data,
            metadata=metadata or {},
            started_at=datetime.now(),
            status=PipelineStatus.RUNNING,
        )
        
        self._logger.info(f"Начало выполнения конвейера '{self.name}' ({len(self._stages)} этапов)")
        
        # Событие начала
        await self._publish_pipeline_event(
            EventType.EXECUTION_STARTED,
            {"pipeline": self.name, "stages_count": len(self._stages)}
        )
        
        # Выполнение этапов
        try:
            for i, stage in enumerate(self._stages):
                context.current_stage = stage.name
                
                self._logger.debug(f"Выполнение этапа '{stage.name}' ({i+1}/{len(self._stages)})")
                
                # Валидация перед этапом
                if not await stage.validate(context.data, context):
                    raise PipelineValidationError(
                        f"Validation failed at stage '{stage.name}'",
                        stage=stage.name
                    )
                
                # Обработка
                stage_start = time.time()
                context.data = await stage.process(context.data, context)
                stage_duration = (time.time() - stage_start) * 1000
                
                # Сохранение результата этапа
                context.stage_results[stage.name] = StageResult(
                    stage_name=stage.name,
                    success=True,
                    data=context.data,
                    duration_ms=stage_duration,
                ).to_dict()
                
                self._logger.debug(f"Этап '{stage.name}' завершён за {stage_duration:.2f}ms")
            
            # Успешное завершение
            context.status = PipelineStatus.COMPLETED
            context.completed_at = datetime.now()
            self._success_count += 1
            
            duration = (time.time() - start_time) * 1000
            self._total_duration_ms += duration
            
            self._logger.info(f"Конвейер '{self.name}' завершён успешно за {duration:.2f}ms")
            
            # Событие завершения
            await self._publish_pipeline_event(
                EventType.EXECUTION_COMPLETED,
                {
                    "pipeline": self.name,
                    "duration_ms": duration,
                    "stages_completed": len(self._stages),
                }
            )
            
            return context.data
            
        except Exception as e:
            context.status = PipelineStatus.FAILED
            self._error_count += 1
            
            duration = (time.time() - start_time) * 1000
            self._total_duration_ms += duration
            
            self._logger.error(f"Ошибка конвейера '{self.name}': {e}")
            
            # Обработка ошибки
            error_context = ErrorContext(
                component=f"pipeline:{self.name}",
                operation=context.current_stage or "process",
                metadata={"stage": context.current_stage},
            )
            await self._error_handler.handle(e, error_context)
            
            # Событие ошибки
            await self._publish_pipeline_event(
                EventType.EXECUTION_FAILED,
                {
                    "pipeline": self.name,
                    "error": str(e),
                    "stage": context.current_stage,
                }
            )
            
            # Откат
            await self._rollback(context, e)
            
            raise PipelineError(f"Pipeline '{self.name}' failed: {e}", stage=context.current_stage)
    
    async def _rollback(self, context: PipelineContext, error: Exception):
        """
        Откат изменений при ошибке.
        
        ARGS:
        - context: контекст конвейера
        - error: ошибка которая произошла
        """
        self._logger.info(f"Начало отката конвейера '{self.name}'")
        
        # Откат в обратном порядке
        for stage in reversed(self._stages):
            try:
                context.data = await stage.rollback(context.data, context)
                self._logger.debug(f"Откат этапа '{stage.name}' успешен")
            except Exception as rollback_error:
                self._logger.error(f"Ошибка отката этапа '{stage.name}': {rollback_error}")
        
        context.status = PipelineStatus.ROLLED_BACK
        self._logger.info(f"Откат конвейера '{self.name}' завершён")
    
    async def _publish_pipeline_event(self, event_type: EventType, data: Dict):
        """Публикация события конвейера."""
        await self._event_bus.publish(
            event_type,
            data=data,
            domain=EventDomain.COMMON,
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики конвейера."""
        avg_duration = (
            self._total_duration_ms / self._execution_count
            if self._execution_count > 0 else 0.0
        )
        
        success_rate = (
            self._success_count / self._execution_count * 100
            if self._execution_count > 0 else 0.0
        )
        
        return {
            "name": self.name,
            "stages_count": len(self._stages),
            "stages": [
                {"name": s.name, "type": s.stage_type.value}
                for s in self._stages
            ],
            "execution_count": self._execution_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration,
            "total_duration_ms": self._total_duration_ms,
        }
    
    def get_stage_names(self) -> List[str]:
        """Получение имён всех этапов."""
        return [s.name for s in self._stages]


class PipelineBuilder:
    """
    Билдер для создания конвейеров.
    
    USAGE:
    ```python
    pipeline = (PipelineBuilder("my_pipeline")
        .validate(validators=[...])
        .transform(transformer=...)
        .enrich(enrichers=[...])
        .build()
    )
    ```
    """
    
    def __init__(self, name: str):
        self._name = name
        self._stages: List[PipelineStage] = []
        self._stage_counter = 0
    
    def validate(self, validators: List[Callable] = None, name: str = None) -> 'PipelineBuilder':
        """Добавление этапа валидации."""
        stage_name = name or f"validate_{self._stage_counter}"
        self._stages.append(ValidationStage(stage_name, validators))
        self._stage_counter += 1
        return self
    
    def transform(self, transformer: Callable, name: str = None) -> 'PipelineBuilder':
        """Добавление этапа трансформации."""
        stage_name = name or f"transform_{self._stage_counter}"
        self._stages.append(TransformationStage(stage_name, transformer))
        self._stage_counter += 1
        return self
    
    def enrich(self, enrichers: List[Callable] = None, name: str = None) -> 'PipelineBuilder':
        """Добавление этапа обогащения."""
        stage_name = name or f"enrich_{self._stage_counter}"
        self._stages.append(EnrichmentStage(stage_name, enrichers))
        self._stage_counter += 1
        return self
    
    def add_stage(self, stage: PipelineStage) -> 'PipelineBuilder':
        """Добавление произвольного этапа."""
        self._stages.append(stage)
        return self
    
    def build(
        self,
        event_bus_manager: EventBusManager = None,
        error_handler: ErrorHandler = None,
    ) -> DataPipeline:
        """
        Построение конвейера.
        
        ARGS:
        - event_bus_manager: менеджер событий
        - error_handler: обработчик ошибок
        
        RETURNS:
        - DataPipeline: готовый конвейер
        """
        pipeline = DataPipeline(
            self._name,
            event_bus_manager=event_bus_manager,
            error_handler=error_handler,
        )
        
        for stage in self._stages:
            pipeline.add_stage(stage)
        
        return pipeline


# Глобальный реестр конвейеров
_pipeline_registry: Dict[str, DataPipeline] = {}


def register_pipeline(name: str, pipeline: DataPipeline):
    """Регистрация конвейера в глобальном реестре."""
    _pipeline_registry[name] = pipeline
    logger.debug(f"Конвейер '{name}' зарегистрирован")


def get_pipeline(name: str) -> Optional[DataPipeline]:
    """Получение конвейера из реестра."""
    return _pipeline_registry.get(name)


def get_all_pipelines() -> Dict[str, DataPipeline]:
    """Получение всех зарегистрированных конвейеров."""
    return _pipeline_registry.copy()
