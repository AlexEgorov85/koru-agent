"""
Модуль конвейера данных.

КОМПОНЕНТЫ:
- data_pipeline: конвейер обработки данных
- stages: этапы конвейера (validation, transformation, enrichment)
- builder: билдер для создания конвейеров

USAGE:
```python
from core.pipeline import (
    DataPipeline,
    PipelineBuilder,
    ValidationStage,
    TransformationStage,
    EnrichmentStage,
)

# Создание через билдер
pipeline = (PipelineBuilder("my_pipeline")
    .validate(validators=[validate_schema])
    .transform(transformer=normalize_data)
    .enrich(enrichers=[add_metadata])
    .build()
)

# Выполнение
result = await pipeline.process(input_data)

# Статистика
stats = pipeline.get_stats()
```
"""
from .data_pipeline import (
    DataPipeline,
    PipelineStage,
    PipelineStageType,
    PipelineStatus,
    PipelineContext,
    StageResult,
    ValidationStage,
    TransformationStage,
    EnrichmentStage,
    PipelineError,
    PipelineValidationError,
    PipelineBuilder,
    register_pipeline,
    get_pipeline,
    get_all_pipelines,
)

__all__ = [
    # Pipeline
    'DataPipeline',
    'PipelineStage',
    'PipelineStageType',
    'PipelineStatus',
    'PipelineContext',
    'StageResult',
    
    # Stages
    'ValidationStage',
    'TransformationStage',
    'EnrichmentStage',
    
    # Errors
    'PipelineError',
    'PipelineValidationError',
    
    # Builder
    'PipelineBuilder',
    
    # Registry
    'register_pipeline',
    'get_pipeline',
    'get_all_pipelines',
]
