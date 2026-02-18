"""
Хранилище метрик на файловой системе.

КОМПОНЕНТЫ:
- FileSystemMetricsStorage: реализация IMetricsStorage

FEATURES:
- Сохранение метрик в JSON файлы
- Агрегация метрик по capability и версии
- Очистка старых метрик
- Потокобезопасная запись
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from core.models.data.metrics import MetricRecord, AggregatedMetrics, MetricType
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage


class FileSystemMetricsStorage(IMetricsStorage):
    """
    Хранилище метрик на файловой системе.

    STRUCTURE:
    data/
    └── metrics/
        ├── {capability}/
        │   ├── {version}/
        │   │   ├── metrics_{date}.json
        │   │   └── aggregated.json
        │   └── latest/
        │       └── metrics.json

    FEATURES:
    - Автоматическое создание директорий
    - Потокобезопасная запись через lock
    - Агрегация в реальном времени
    """

    def __init__(self, base_dir: Path = None):
        """
        Инициализация хранилища.

        ARGS:
        - base_dir: базовая директория для хранения (по умолчанию data/metrics)
        """
        if base_dir is None:
            base_dir = Path('data/metrics')

        self.base_dir = base_dir
        self._lock = asyncio.Lock()
        self._ensure_base_dir()

    def _ensure_base_dir(self) -> None:
        """Создание базовой директории если не существует"""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_capability_dir(self, capability: str) -> Path:
        """Получение директории для capability"""
        # Замена недопустимых символов в имени capability
        safe_capability = capability.replace('/', '_').replace('\\', '_')
        return self.base_dir / safe_capability

    def _get_version_dir(self, capability: str, version: str) -> Path:
        """Получение директории для версии"""
        capability_dir = self._get_capability_dir(capability)
        capability_dir.mkdir(parents=True, exist_ok=True)

        safe_version = version.replace('/', '_').replace('\\', '_')
        return capability_dir / safe_version

    def _get_metrics_file(self, capability: str, version: str, date: datetime = None) -> Path:
        """Получение пути к файлу метрик"""
        if date is None:
            date = datetime.now()

        version_dir = self._get_version_dir(capability, version)
        date_str = date.strftime('%Y-%m-%d')
        return version_dir / f'metrics_{date_str}.json'

    def _get_aggregated_file(self, capability: str, version: str) -> Path:
        """Получение пути к файлу агрегированных метрик"""
        version_dir = self._get_version_dir(capability, version)
        return version_dir / 'aggregated.json'

    def _get_latest_file(self, capability: str) -> Path:
        """Получение пути к файлу последних метрик"""
        capability_dir = self._get_capability_dir(capability)
        latest_dir = capability_dir / 'latest'
        latest_dir.mkdir(parents=True, exist_ok=True)
        return latest_dir / 'metrics.json'

    async def record(self, metric: MetricRecord) -> None:
        """
        Запись метрики в хранилище.

        ARGS:
        - metric: объект метрики для записи

        FEATURES:
        - Потокобезопасная запись через lock
        - Добавление в существующий файл за сегодня
        - Обновление aggregated.json
        """
        async with self._lock:
            # Получение файла метрик за сегодня
            metrics_file = self._get_metrics_file(
                metric.capability,
                metric.version or 'default',
                metric.timestamp
            )

            # Загрузка существующих метрик
            existing_metrics = self._load_metrics_file(metrics_file)

            # Добавление новой метрики
            existing_metrics.append(metric.to_dict())

            # Сохранение
            self._save_metrics_file(metrics_file, existing_metrics)

            # Обновление aggregated метрик
            await self._update_aggregated_metrics(
                metric.capability,
                metric.version or 'default'
            )

            # Обновление latest файла
            self._update_latest_metrics(metric)

    def _load_metrics_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Загрузка метрик из файла"""
        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []

    def _save_metrics_file(self, file_path: Path, metrics: List[Dict[str, Any]]) -> None:
        """Сохранение метрик в файл"""
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

    async def _update_aggregated_metrics(self, capability: str, version: str) -> None:
        """Обновление агрегированных метрик"""
        records = await self.get_records(capability, version)
        aggregated = AggregatedMetrics.from_records(capability, version, records)

        agg_file = self._get_aggregated_file(capability, version)
        self._save_metrics_file(agg_file, [aggregated.to_dict()])

    def _update_latest_metrics(self, metric: MetricRecord) -> None:
        """Обновление файла последних метрик"""
        latest_file = self._get_latest_file(metric.capability)
        existing = self._load_metrics_file(latest_file)

        # Добавление метрики (храним последние 1000)
        existing.append(metric.to_dict())
        existing = existing[-1000:]

        self._save_metrics_file(latest_file, existing)

    async def get_records(
        self,
        capability: str,
        version: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: Optional[int] = None
    ) -> List[MetricRecord]:
        """
        Получение записей метрик по фильтрам.

        ARGS:
        - capability: название способности
        - version: версия промпта/контракта (опционально)
        - time_range: временной диапазон (start, end) (опционально)
        - limit: максимальное количество записей (опционально)

        RETURNS:
        - List[MetricRecord]: список записей метрик
        """
        records = []

        if version:
            # Получение из конкретной версии
            version_dir = self._get_version_dir(capability, version)
            if version_dir.exists():
                for file_path in version_dir.glob('metrics_*.json'):
                    records.extend(self._load_metrics_from_file(file_path))
        else:
            # Получение из всех версий
            capability_dir = self._get_capability_dir(capability)
            if capability_dir.exists():
                for version_dir in capability_dir.iterdir():
                    if version_dir.is_dir() and version_dir.name != 'latest':
                        for file_path in version_dir.glob('metrics_*.json'):
                            records.extend(self._load_metrics_from_file(file_path))

        # Фильтрация по времени
        if time_range:
            start, end = time_range
            records = [r for r in records if start <= r.timestamp <= end]

        # Сортировка по времени
        records.sort(key=lambda r: r.timestamp, reverse=True)

        # Ограничение количества
        if limit:
            records = records[:limit]

        return records

    def _load_metrics_from_file(self, file_path: Path) -> List[MetricRecord]:
        """Загрузка метрик из файла с парсингом"""
        data = self._load_metrics_file(file_path)
        records = []

        for item in data:
            try:
                record = MetricRecord.from_dict(item)
                records.append(record)
            except (KeyError, ValueError):
                # Пропуск некорректных записей
                continue

        return records

    async def aggregate(
        self,
        capability: str,
        version: str,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> AggregatedMetrics:
        """
        Агрегация метрик для бенчмарка.

        ARGS:
        - capability: название способности
        - version: версия промпта/контракта
        - time_range: временной диапазон (start, end) (опционально)

        RETURNS:
        - AggregatedMetrics: агрегированные метрики
        """
        records = await self.get_records(capability, version, time_range)
        return AggregatedMetrics.from_records(capability, version, records)

    async def clear_old(self, older_than: datetime) -> int:
        """
        Очистка старых метрик.

        ARGS:
        - older_than: удалять метрики старше этой даты

        RETURNS:
        - int: количество удалённых записей
        """
        async with self._lock:
            deleted_count = 0

            # Поиск всех файлов метрик
            for file_path in self.base_dir.rglob('metrics_*.json'):
                # Извлечение даты из имени файла
                try:
                    date_str = file_path.stem.replace('metrics_', '')
                    file_date = datetime.strptime(date_str, '%Y-%m-%d')

                    if file_date < older_than:
                        # Удаление файла
                        deleted_count += len(self._load_metrics_file(file_path))
                        file_path.unlink()
                except (ValueError, OSError):
                    continue

            # Очистка aggregated файлов для удалённых версий
            for agg_file in self.base_dir.rglob('aggregated.json'):
                capability_dir = agg_file.parent.parent
                if not any(capability_dir.iterdir()):
                    try:
                        agg_file.unlink()
                    except OSError:
                        pass

            return deleted_count

    async def get_aggregated(self, capability: str, version: str) -> Optional[AggregatedMetrics]:
        """
        Получение сохранённых агрегированных метрик.

        ARGS:
        - capability: название способности
        - version: версия промпта/контракта

        RETURNS:
        - Optional[AggregatedMetrics]: агрегированные метрики или None
        """
        agg_file = self._get_aggregated_file(capability, version)

        if not agg_file.exists():
            return None

        data = self._load_metrics_file(agg_file)
        if not data:
            return None

        try:
            agg_data = data[0]
            return AggregatedMetrics(
                capability=agg_data.get('capability', capability),
                version=agg_data.get('version', version),
                total_runs=agg_data.get('total_runs', 0),
                success_count=agg_data.get('success_count', 0),
                failure_count=agg_data.get('failure_count', 0),
                accuracy=agg_data.get('accuracy', 0.0),
                avg_execution_time_ms=agg_data.get('avg_execution_time_ms', 0.0),
                min_execution_time_ms=agg_data.get('min_execution_time_ms', 0.0),
                max_execution_time_ms=agg_data.get('max_execution_time_ms', 0.0),
                std_execution_time_ms=agg_data.get('std_execution_time_ms', 0.0),
                total_tokens=agg_data.get('total_tokens', 0),
                avg_tokens=agg_data.get('avg_tokens', 0.0),
                custom_metrics=agg_data.get('custom_metrics', {})
            )
        except (KeyError, IndexError):
            return None

    async def get_capabilities(self) -> List[str]:
        """
        Получение списка всех capability.

        RETURNS:
        - List[str]: список названий capability
        """
        capabilities = []

        if self.base_dir.exists():
            for item in self.base_dir.iterdir():
                if item.is_dir() and item.name != '__pycache__':
                    # Восстановление оригинального имени
                    capabilities.append(item.name.replace('_', '/'))

        return capabilities

    async def get_versions(self, capability: str) -> List[str]:
        """
        Получение списка версий для capability.

        ARGS:
        - capability: название способности

        RETURNS:
        - List[str]: список версий
        """
        versions = []
        capability_dir = self._get_capability_dir(capability)

        if capability_dir.exists():
            for item in capability_dir.iterdir():
                if item.is_dir() and item.name != 'latest':
                    versions.append(item.name.replace('_', '/'))

        return versions
