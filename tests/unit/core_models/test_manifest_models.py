import pytest
from core.models.data.manifest import Manifest, ComponentType, ComponentStatus, QualityMetrics


class TestManifestModels:
    
    def test_valid_manifest_creation(self):
        manifest = Manifest(
            component_id="test_component",
            component_type=ComponentType.SKILL,
            version="v1.0.0",
            owner="test_owner",
            status=ComponentStatus.ACTIVE
        )
        
        assert manifest.component_id == "test_component"
        assert manifest.version == "v1.0.0"
        assert manifest.owner == "test_owner"
    
    def test_invalid_version_format(self):
        with pytest.raises(ValueError):
            Manifest(
                component_id="test",
                component_type=ComponentType.SKILL,
                version="1.0.0",
                owner="owner",
                status=ComponentStatus.ACTIVE
            )
    
    def test_missing_owner(self):
        with pytest.raises(ValueError):
            Manifest(
                component_id="test",
                component_type=ComponentType.SKILL,
                version="v1.0.0",
                owner="",
                status=ComponentStatus.ACTIVE
            )
    
    def test_quality_metrics_range(self):
        metrics = QualityMetrics(
            success_rate_target=0.95,
            avg_execution_time_ms=500,
            error_rate_threshold=0.05
        )
        assert metrics.success_rate_target == 0.95
        
        with pytest.raises(ValueError):
            QualityMetrics(
                success_rate_target=1.5,
                avg_execution_time_ms=500,
                error_rate_threshold=0.05
            )