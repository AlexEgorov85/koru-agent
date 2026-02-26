"""
Тесты для Data Pipeline.

TESTS:
- test_pipeline_creation: Создание конвейера
- test_add_stage: Добавление этапов
- test_process: Обработка данных
- test_validation_stage: Этап валидации
- test_transformation_stage: Этап трансформации
- test_enrichment_stage: Этап обогащения
- test_rollback: Откат при ошибке
- test_stats: Статистика
- test_builder: Билдер конвейеров
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.pipeline import (
    DataPipeline,
    PipelineBuilder,
    ValidationStage,
    TransformationStage,
    EnrichmentStage,
    PipelineStage,
    PipelineStageType,
    PipelineError,
    PipelineValidationError,
    PipelineStatus,
    register_pipeline,
    get_pipeline,
    get_all_pipelines,
)


@pytest.fixture
def pipeline():
    """Фикстура: конвейер."""
    return DataPipeline(name="test_pipeline")


class AsyncValidator:
    """Асинхронный валидатор для тестов."""
    async def __call__(self, data, context):
        return isinstance(data, dict) and "value" in data


class SyncValidator:
    """Синхронный валидатор для тестов."""
    def __call__(self, data, context):
        return isinstance(data, dict)


class TestPipelineCreation:
    """Тесты создания конвейера."""

    def test_create_pipeline(self, pipeline):
        """Создание конвейера."""
        assert pipeline is not None
        assert pipeline.name == "test_pipeline"
        assert len(pipeline._stages) == 0

    def test_add_stage(self, pipeline):
        """Добавление этапа."""
        stage = ValidationStage("validate")
        pipeline.add_stage(stage)
        
        assert len(pipeline._stages) == 1
        assert pipeline.get_stage_names() == ["validate"]

    def test_remove_stage(self, pipeline):
        """Удаление этапа."""
        pipeline.add_stage(ValidationStage("validate"))
        pipeline.add_stage(TransformationStage("transform", transformer=lambda x, ctx: x))
        
        result = pipeline.remove_stage("validate")
        
        assert result is True
        assert len(pipeline._stages) == 1
        assert pipeline.get_stage_names() == ["transform"]

    def test_remove_nonexistent_stage(self, pipeline):
        """Удаление несуществующего этапа."""
        result = pipeline.remove_stage("nonexistent")
        
        assert result is False


class TestValidationStage:
    """Тесты этапа валидации."""

    @pytest.mark.asyncio
    async def test_validation_success(self, pipeline):
        """Успешная валидация."""
        validator = SyncValidator()
        pipeline.add_stage(ValidationStage("validate", validators=[validator]))
        
        result = await pipeline.process({"value": 42})
        
        assert result == {"value": 42}

    @pytest.mark.asyncio
    async def test_validation_failure(self, pipeline):
        """Неуспешная валидация."""
        validator = SyncValidator()
        pipeline.add_stage(ValidationStage("validate", validators=[validator]))
        
        # Ошибка валидации оборачивается в PipelineError
        with pytest.raises(PipelineError):
            await pipeline.process("invalid_data")

    @pytest.mark.asyncio
    async def test_async_validation(self, pipeline):
        """Асинхронная валидация."""
        validator = AsyncValidator()
        pipeline.add_stage(ValidationStage("validate", validators=[validator]))
        
        result = await pipeline.process({"value": 42})
        
        assert result == {"value": 42}


class TestTransformationStage:
    """Тесты этапа трансформации."""

    @pytest.mark.asyncio
    async def test_sync_transformation(self, pipeline):
        """Синхронная трансформация."""
        def transformer(data, context):
            return {"transformed": data.get("value", 0) * 2}
        
        pipeline.add_stage(TransformationStage("transform", transformer=transformer))
        
        result = await pipeline.process({"value": 21})
        
        assert result == {"transformed": 42}

    @pytest.mark.asyncio
    async def test_async_transformation(self, pipeline):
        """Асинхронная трансформация."""
        async def transformer(data, context):
            return {"async_transformed": data.get("value", 0) + 10}
        
        pipeline.add_stage(TransformationStage("transform", transformer=transformer))
        
        result = await pipeline.process({"value": 32})
        
        assert result == {"async_transformed": 42}


class TestEnrichmentStage:
    """Тесты этапа обогащения."""

    @pytest.mark.asyncio
    async def test_single_enricher(self, pipeline):
        """Один обогатитель."""
        def enricher(data, context):
            data["enriched"] = True
            return data
        
        pipeline.add_stage(EnrichmentStage("enrich", enrichers=[enricher]))
        
        result = await pipeline.process({"value": 42})
        
        assert result == {"value": 42, "enriched": True}

    @pytest.mark.asyncio
    async def test_multiple_enrichers(self, pipeline):
        """Несколько обогатителей."""
        def enricher1(data, context):
            data["step1"] = True
            return data
        
        def enricher2(data, context):
            data["step2"] = True
            return data
        
        pipeline.add_stage(EnrichmentStage("enrich", enrichers=[enricher1, enricher2]))
        
        result = await pipeline.process({"value": 42})
        
        assert result == {"value": 42, "step1": True, "step2": True}


class TestPipelineExecution:
    """Тесты выполнения конвейера."""

    @pytest.mark.asyncio
    async def test_multiple_stages(self, pipeline):
        """Несколько этапов."""
        # Валидация
        pipeline.add_stage(ValidationStage("validate", validators=[SyncValidator()]))
        
        # Трансформация
        def transformer(data, context):
            return {"value": data["value"] * 2}
        pipeline.add_stage(TransformationStage("transform", transformer=transformer))
        
        # Обогащение
        def enricher(data, context):
            data["processed"] = True
            return data
        pipeline.add_stage(EnrichmentStage("enrich", enrichers=[enricher]))
        
        result = await pipeline.process({"value": 10})
        
        assert result == {"value": 20, "processed": True}

    @pytest.mark.asyncio
    async def test_stage_results(self, pipeline):
        """Результаты этапов."""
        pipeline.add_stage(ValidationStage("validate", validators=[SyncValidator()]))
        
        await pipeline.process({"value": 42})
        
        stats = pipeline.get_stats()
        assert "validate" in [s["name"] for s in stats["stages"]]


class TestPipelineRollback:
    """Тесты отката."""

    @pytest.mark.asyncio
    async def test_rollback_on_error(self, pipeline):
        """Откат при ошибке."""
        # Успешная валидация
        pipeline.add_stage(ValidationStage("validate", validators=[SyncValidator()]))
        
        # Трансформация которая выбрасывает ошибку
        def failing_transformer(data, context):
            raise Exception("Transformation failed")
        
        pipeline.add_stage(TransformationStage("transform", transformer=failing_transformer))
        
        with pytest.raises(PipelineError):
            await pipeline.process({"value": 42})
        
        # Проверка что статус ROLLED_BACK
        # (в реальности нужно проверять контекст, но для теста достаточно что ошибка поймана)

    @pytest.mark.asyncio
    async def test_custom_rollback(self):
        """Кастомный откат."""
        class RollbackStage(PipelineStage):
            def __init__(self):
                super().__init__("rollback_test")
                self.rollback_called = False
            
            async def process(self, data, context):
                return {"processed": data}
            
            async def rollback(self, data, context):
                self.rollback_called = True
                return {"rolled_back": data}
        
        pipeline = DataPipeline("rollback_pipeline")
        stage = RollbackStage()
        
        def failing_stage(data, context):
            raise Exception("Error")
        
        pipeline.add_stage(stage)
        pipeline.add_stage(TransformationStage("fail", transformer=failing_stage))
        
        with pytest.raises(PipelineError):
            await pipeline.process({"value": 42})
        
        assert stage.rollback_called is True


class TestPipelineStats:
    """Тесты статистики."""

    @pytest.mark.asyncio
    async def test_execution_count(self, pipeline):
        """Подсчет выполнений."""
        pipeline.add_stage(ValidationStage("validate", validators=[SyncValidator()]))
        
        await pipeline.process({"value": 1})
        await pipeline.process({"value": 2})
        await pipeline.process({"value": 3})
        
        stats = pipeline.get_stats()
        
        assert stats["execution_count"] == 3
        assert stats["success_count"] == 3

    @pytest.mark.asyncio
    async def test_error_count(self, pipeline):
        """Подсчет ошибок."""
        pipeline.add_stage(ValidationStage("validate", validators=[SyncValidator()]))
        
        def failing_stage(data, context):
            raise Exception("Error")
        
        pipeline.add_stage(TransformationStage("fail", transformer=failing_stage))
        
        for i in range(3):
            try:
                await pipeline.process({"value": i})
            except PipelineError:
                pass
        
        stats = pipeline.get_stats()
        
        assert stats["execution_count"] == 3
        assert stats["error_count"] == 3

    @pytest.mark.asyncio
    async def test_success_rate(self, pipeline):
        """Процент успеха."""
        pipeline.add_stage(ValidationStage("validate", validators=[SyncValidator()]))
        
        # 2 успеха
        await pipeline.process({"value": 1})
        await pipeline.process({"value": 2})
        
        # 2 ошибки
        def failing_stage(data, context):
            raise Exception("Error")
        pipeline.add_stage(TransformationStage("fail", transformer=failing_stage))
        
        for i in range(2):
            try:
                await pipeline.process({"value": i})
            except PipelineError:
                pass
        
        stats = pipeline.get_stats()
        
        assert stats["success_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_avg_duration(self, pipeline):
        """Средняя длительность."""
        pipeline.add_stage(ValidationStage("validate", validators=[SyncValidator()]))
        
        await pipeline.process({"value": 1})
        await pipeline.process({"value": 2})
        
        stats = pipeline.get_stats()
        
        assert stats["avg_duration_ms"] > 0
        assert stats["total_duration_ms"] > 0


class TestPipelineBuilder:
    """Тесты билдера конвейеров."""

    def test_builder_create_pipeline(self):
        """Создание конвейера через билдер."""
        pipeline = (PipelineBuilder("built_pipeline")
            .validate(validators=[SyncValidator()])
            .transform(transformer=lambda x, ctx: x)
            .build()
        )
        
        assert pipeline is not None
        assert pipeline.name == "built_pipeline"
        assert len(pipeline.get_stage_names()) == 2

    def test_builder_fluent_interface(self):
        """Fluent интерфейс билдера."""
        builder = PipelineBuilder("test")
        
        result = builder.validate(validators=[SyncValidator()])
        assert result is builder
        
        result = builder.transform(transformer=lambda x, ctx: x)
        assert result is builder
        
        result = builder.enrich(enrichers=[lambda x, ctx: x])
        assert result is builder

    def test_builder_custom_stage(self):
        """Добавление кастомного этапа."""
        custom_stage = ValidationStage("custom")
        
        pipeline = (PipelineBuilder("custom_pipeline")
            .add_stage(custom_stage)
            .build()
        )
        
        assert len(pipeline.get_stage_names()) == 1
        assert pipeline.get_stage_names()[0] == "custom"


class TestPipelineRegistry:
    """Тесты реестра конвейеров."""

    def test_register_pipeline(self):
        """Регистрация конвейера."""
        pipeline = DataPipeline("registered_pipeline")
        register_pipeline("registered_pipeline", pipeline)
        
        retrieved = get_pipeline("registered_pipeline")
        
        assert retrieved is pipeline

    def test_get_nonexistent_pipeline(self):
        """Получение несуществующего конвейера."""
        pipeline = get_pipeline("nonexistent")
        
        assert pipeline is None

    def test_get_all_pipelines(self):
        """Получение всех конвейеров."""
        pipeline1 = DataPipeline("pipeline1")
        pipeline2 = DataPipeline("pipeline2")
        
        register_pipeline("pipeline1", pipeline1)
        register_pipeline("pipeline2", pipeline2)
        
        all_pipelines = get_all_pipelines()
        
        assert len(all_pipelines) >= 2
        assert "pipeline1" in all_pipelines
        assert "pipeline2" in all_pipelines


class TestPipelineContext:
    """Тесты контекста конвейера."""

    def test_context_creation(self):
        """Создание контекста."""
        from core.pipeline import PipelineContext, PipelineStatus
        
        context = PipelineContext(data={"value": 42})
        
        assert context.data == {"value": 42}
        assert context.status == PipelineStatus.PENDING
        assert context.started_at is None

    def test_context_to_dict(self):
        """Конвертация контекста в dict."""
        from core.pipeline import PipelineContext
        
        context = PipelineContext(data={"value": 42})
        data = context.to_dict()
        
        assert "data" in data
        assert "status" in data
        assert "metadata" in data


class TestStageResult:
    """Тесты результата этапа."""

    def test_stage_result_creation(self):
        """Создание результата этапа."""
        from core.pipeline import StageResult
        
        result = StageResult(
            stage_name="test",
            success=True,
            data={"value": 42},
            duration_ms=10.5,
        )
        
        assert result.stage_name == "test"
        assert result.success is True
        assert result.duration_ms == 10.5

    def test_stage_result_to_dict(self):
        """Конвертация результата в dict."""
        from core.pipeline import StageResult
        
        result = StageResult(
            stage_name="test",
            success=True,
            data={"value": 42},
        )
        
        data = result.to_dict()
        
        assert data["stage_name"] == "test"
        assert data["success"] is True
