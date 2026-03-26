#!/usr/bin/env python3
"""
Утилита для экспорта метрик производительности в Prometheus format.

Запуск:
    python scripts/monitoring/export_metrics.py
    
Интеграция с Prometheus:
    1. Добавить job в prometheus.yml:
       - job_name: 'agent_v5'
         static_configs:
         - targets: ['localhost:8000']
         metrics_path: '/metrics'
"""
import asyncio
import time
import json
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, asdict

from core.config.models import SystemConfig
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext


@dataclass
class Metrics:
    """Метрики производительности."""
    # Инициализация
    init_time_ms: float = 0.0
    infra_init_time_ms: float = 0.0
    app_init_time_ms: float = 0.0
    
    # Компоненты
    skills_count: int = 0
    tools_count: int = 0
    services_count: int = 0
    behaviors_count: int = 0
    
    # Промпты и контракты
    prompts_count: int = 0
    contracts_count: int = 0

    # Память (MB)
    memory_current_mb: float = 0.0
    memory_peak_mb: float = 0.0

    # Timestamp
    timestamp: float = 0.0


class MetricsExporter:
    """Экспортер метрик в Prometheus format."""
    
    def __init__(self):
        self.metrics = Metrics()
    
    async def collect(self, data_dir: str = "./data") -> Metrics:
        """Сбор метрик."""
        import tracemalloc
        
        start_time = time.perf_counter()
        tracemalloc.start()
        
        # Infrastructure
        infra_start = time.perf_counter()
        config = SystemConfig(data_dir=data_dir, debug=False)
        infra = InfrastructureContext(config)
        await infra.initialize()
        self.metrics.infra_init_time_ms = (time.perf_counter() - infra_start) * 1000
        
        # Application
        app_start = time.perf_counter()
        app_config = AppConfig.from_registry(profile='prod')
        app_context = ApplicationContext(
            infrastructure_context=infra,
            config=app_config,
            profile='prod'
        )
        await app_context.initialize()
        self.metrics.app_init_time_ms = (time.perf_counter() - app_start) * 1000
        
        self.metrics.init_time_ms = (time.perf_counter() - start_time) * 1000
        
        # Компоненты
        self.metrics.skills_count = len(app_context.components.all_of_type(
            app_context.ComponentType.SKILL
        ))
        self.metrics.tools_count = len(app_context.components.all_of_type(
            app_context.ComponentType.TOOL
        ))
        self.metrics.services_count = len(app_context.components.all_of_type(
            app_context.ComponentType.SERVICE
        ))
        self.metrics.behaviors_count = len(app_context.components.all_of_type(
            app_context.ComponentType.BEHAVIOR
        ))
        
        # Промпты и контракты
        self.metrics.prompts_count = len(app_context.data_repository._prompts_index)
        self.metrics.contracts_count = len(app_context.data_repository._contracts_index)

        # Память
        current, peak = tracemalloc.get_traced_memory()
        self.metrics.memory_current_mb = current / 1024 / 1024
        self.metrics.memory_peak_mb = peak / 1024 / 1024
        tracemalloc.stop()
        
        # Timestamp
        self.metrics.timestamp = time.time()
        
        await infra.shutdown()
        
        return self.metrics
    
    def to_prometheus(self) -> str:
        """Конвертация в Prometheus format."""
        lines = []
        
        # Help и type для каждой метрики
        for field_name, field_value in asdict(self.metrics).items():
            metric_name = f"agent_v5_{field_name}"
            
            # Help
            lines.append(f"# HELP {metric_name} Agent v5 {field_name.replace('_', ' ')}")
            
            # Type
            if isinstance(field_value, int):
                lines.append(f"# TYPE {metric_name} gauge")
            elif field_name == "timestamp":
                lines.append(f"# TYPE {metric_name} gauge")
            else:
                lines.append(f"# TYPE {metric_name} gauge")
            
            # Value
            lines.append(f"{metric_name} {field_value}")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Конвертация в JSON."""
        return json.dumps(asdict(self.metrics), indent=2)


async def main():
    """Основная функция."""
    print("=" * 60)
    print("Сбор метрик производительности Agent_v5")
    print("=" * 60)
    
    exporter = MetricsExporter()
    metrics = await exporter.collect()
    
    print("\n📊 Метрики:")
    print(f"  Время инициализации: {metrics.init_time_ms:.2f} мс")
    print(f"    - Infrastructure: {metrics.infra_init_time_ms:.2f} мс")
    print(f"    - Application: {metrics.app_init_time_ms:.2f} мс")
    
    print(f"\n  Компоненты:")
    print(f"    - Skills: {metrics.skills_count}")
    print(f"    - Tools: {metrics.tools_count}")
    print(f"    - Services: {metrics.services_count}")
    print(f"    - Behaviors: {metrics.behaviors_count}")
    
    print(f"\n  Ресурсы:")
    print(f"    - Prompts: {metrics.prompts_count}")
    print(f"    - Contracts: {metrics.contracts_count}")

    print(f"\n  Память:")
    print(f"    - Текущая: {metrics.memory_current_mb:.2f} MB")
    print(f"    - Пиковая: {metrics.memory_peak_mb:.2f} MB")
    
    print("\n" + "=" * 60)
    print("Prometheus format:")
    print("=" * 60)
    print(exporter.to_prometheus())
    
    # Сохранение в файл
    output_file = Path(__file__).parent.parent.parent / "metrics" / "current.json"
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(exporter.to_json())
    
    print(f"\n💾 Метрики сохранены в: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
