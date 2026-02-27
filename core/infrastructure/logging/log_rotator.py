"""
LogRotator - ротация, архивация и очистка старых логов.

FEATURES:
- Автоматическая ротация по размеру и времени
- Архивация по датам (YYYY/MM/)
- Очистка старых логов по политике хранения
- Сжатие архивов (опционально)

POLICIES:
- active_days: Хранить в active/ N дней
- archive_months: Хранить в archive/ N месяцев
- max_size_mb: Максимальный размер файла
- max_files_per_day: Макс файлов в день
"""
import os
import shutil
import gzip
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from core.infrastructure.logging.log_config_new import LoggingConfig, get_logging_config


logger = logging.getLogger(__name__)


class LogRotator:
    """
    Ротатор логов с поддержкой политик хранения.
    
    RESPONSIBILITIES:
    - Ротация файлов по размеру
    - Перемещение из active/ в archive/
    - Удаление старых логов
    - Сжатие архивов
    
    USAGE:
        rotator = LogRotator()
        await rotator.initialize()
        
        # Ручная ротация
        await rotator.rotate_agent_log()
        
        # Очистка старых логов
        deleted = await rotator.cleanup_old_logs()
    """
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Инициализация LogRotator.
        
        ARGS:
            config: Конфигурация логирования
        """
        self.config = config or get_logging_config()
        self._initialized = False
        
        # Блокировка для потокобезопасности
        self._lock = asyncio.Lock()
        
        # Задача фоновой очистки
        self._background_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """Инициализация ротатора."""
        if self._initialized:
            logger.warning("LogRotator уже инициализирован")
            return
        
        logger.info("Инициализация LogRotator...")
        
        # Создание директорий
        self.config.archive_dir.mkdir(parents=True, exist_ok=True)
        self.config.indexed_dir.mkdir(parents=True, exist_ok=True)
        
        # Запуск фоновой очистки (раз в час)
        await self._start_background_cleanup()
        
        self._initialized = True
        logger.info("LogRotator инициализирован")
    
    async def _start_background_cleanup(self) -> None:
        """Запуск фоновой очистки."""
        self._stop_event.clear()
        self._background_task = asyncio.create_task(self._background_cleanup_loop())
        logger.debug("Запущена фоновая очистка логов")
    
    async def _background_cleanup_loop(self) -> None:
        """Фоновый цикл очистки (каждые 60 минут)."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(3600)  # 1 час
                
                # Проверка размера логов
                await self._check_log_sizes()
                
                # Очистка старых логов (раз в сутки)
                if datetime.now().hour == 3:  # В 3 часа ночи
                    await self.cleanup_old_logs()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка фоновой очистки: {e}")
    
    async def _check_log_sizes(self) -> None:
        """Проверка размера логов и ротация при необходимости."""
        async with self._lock:
            now = datetime.now()
            agent_log = self.config.archive_dir / str(now.year) / f"{now.month:02d}" / f"agent_{now.strftime('%Y-%m-%d')}.log"
            
            if agent_log.exists():
                size_mb = agent_log.stat().st_size / (1024 * 1024)
                
                if size_mb > self.config.retention.max_size_mb:
                    logger.info(f"Ротация agent.log: размер {size_mb:.1f}MB > лимита {self.config.retention.max_size_mb}MB")
                    await self._rotate_file(agent_log)
    
    async def _rotate_file(self, file_path: Path, keep_original: bool = False) -> Optional[Path]:
        """
        Ротация файла (добавление номера к имени).
        
        ARGS:
            file_path: Путь к файлу
            keep_original: Сохранить оригинал
            
        RETURNS:
            Путь к новому файлу или None
        """
        try:
            # Поиск следующего доступного номера
            base_name = file_path.stem
            suffix = file_path.suffix
            
            counter = 1
            while counter < 100:
                rotated_name = f"{base_name}.{counter}{suffix}"
                rotated_path = file_path.parent / rotated_name
                
                if not rotated_path.exists():
                    if keep_original:
                        # Копирование
                        shutil.copy2(file_path, rotated_path)
                    else:
                        # Переименование
                        file_path.rename(rotated_path)
                    
                    logger.debug(f"Ротация: {file_path} → {rotated_path}")
                    return rotated_path
                
                counter += 1
            
            logger.warning(f"Не удалось ротировать {file_path}: слишком много ротаций")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка ротации файла {file_path}: {e}")
            return None
    
    async def rotate_agent_log(self) -> Optional[Path]:
        """
        Ротация лога агента.
        
        RETURNS:
            Путь к ротированному файлу или None
        """
        now = datetime.now()
        agent_log = self.config.archive_dir / str(now.year) / f"{now.month:02d}" / f"agent_{now.strftime('%Y-%m-%d')}.log"
        
        if not agent_log.exists():
            return None
        
        return await self._rotate_file(agent_log, keep_original=False)
    
    async def archive_active_logs(self) -> int:
        """
        Перемещение логов из active/ в archive/.
        
        RETURNS:
            Количество перемещённых файлов
        """
        moved_count = 0
        
        if not self.config.active_dir.exists():
            return 0
        
        async with self._lock:
            now = datetime.now()
            target_dir = self.config.archive_dir / str(now.year) / f"{now.month:02d}"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Перемещение файлов из active/
            for file_path in self.config.active_dir.glob("*"):
                if file_path.is_dir():
                    continue
                
                # Пропуск symlink
                if file_path.is_symlink():
                    continue
                
                target_path = target_dir / file_path.name
                
                try:
                    shutil.move(str(file_path), str(target_path))
                    moved_count += 1
                    logger.debug(f"Архивировано: {file_path} → {target_path}")
                except Exception as e:
                    logger.error(f"Ошибка архивации {file_path}: {e}")
        
        logger.info(f"Архивировано {moved_count} файлов из active/")
        return moved_count
    
    async def cleanup_old_logs(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Очистка старых логов по политике хранения.
        
        ARGS:
            dry_run: Не удалять, только показать что будет удалено
            
        RETURNS:
            Dict со статистикой очистки
        """
        logger.info(f"Начало очистки старых логов (dry_run={dry_run})...")
        
        stats = {
            'deleted_files': 0,
            'deleted_size_bytes': 0,
            'deleted_sessions': 0,
            'deleted_llm_calls': 0,
            'errors': [],
        }
        
        async with self._lock:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention.active_days)
            archive_cutoff = datetime.now() - timedelta(days=self.config.retention.archive_months * 30)
            
            # Очистка active/ (старше active_days)
            if self.config.active_dir.exists():
                for file_path in self.config.active_dir.rglob("*"):
                    if file_path.is_dir() or file_path.is_symlink():
                        continue
                    
                    try:
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        
                        if mtime < cutoff_date:
                            size = file_path.stat().st_size
                            
                            if not dry_run:
                                file_path.unlink()
                            
                            stats['deleted_files'] += 1
                            stats['deleted_size_bytes'] += size
                            logger.debug(f"Удалено (active): {file_path} ({size} байт)")
                            
                    except Exception as e:
                        stats['errors'].append(str(e))
                        logger.error(f"Ошибка очистки {file_path}: {e}")
            
            # Очистка archive/ (старше archive_months)
            if self.config.archive_dir.exists():
                for year_dir in self.config.archive_dir.iterdir():
                    if not year_dir.is_dir():
                        continue
                    
                    try:
                        year = int(year_dir.name)
                    except ValueError:
                        continue
                    
                    for month_dir in year_dir.iterdir():
                        if not month_dir.is_dir():
                            continue
                        
                        try:
                            month = int(month_dir.name)
                            dir_date = datetime(year, month, 1)
                            
                            if dir_date < archive_cutoff:
                                # Удаление всей директории месяца
                                dir_size = sum(
                                    f.stat().st_size for f in month_dir.rglob("*") if f.is_file()
                                )
                                
                                if not dry_run:
                                    shutil.rmtree(month_dir)
                                
                                stats['deleted_files'] += len(list(month_dir.rglob("*")))
                                stats['deleted_size_bytes'] += dir_size
                                logger.debug(f"Удалён месяц: {month_dir} ({dir_size} байт)")
                                
                        except (ValueError, OSError) as e:
                            stats['errors'].append(str(e))
                            logger.error(f"Ошибка очистки {month_dir}: {e}")
            
            # Очистка indexed/ (оставляем только текущие индексы)
            if self.config.indexed_dir.exists():
                for file_path in self.config.indexed_dir.glob("*.jsonl"):
                    # Индексы не удаляем, они перестраиваются
                    pass
        
        # Логирование результатов
        logger.info(
            f"Очистка завершена: {stats['deleted_files']} файлов, "
            f"{stats['deleted_size_bytes'] / (1024*1024):.2f} MB"
        )
        
        return stats
    
    async def compress_old_archives(self, older_than_days: int = 30) -> int:
        """
        Сжатие старых архивов в gzip.
        
        ARGS:
            older_than_days: Сжимать файлы старше N дней
            
        RETURNS:
            Количество сжатых файлов
        """
        compressed_count = 0
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        
        if not self.config.archive_dir.exists():
            return 0
        
        async with self._lock:
            for year_dir in self.config.archive_dir.iterdir():
                if not year_dir.is_dir():
                    continue
                
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    
                    for file_path in month_dir.rglob("*"):
                        if not file_path.is_file() or file_path.suffix == '.gz':
                            continue
                        
                        try:
                            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                            
                            if mtime < cutoff_date:
                                # Сжатие файла
                                gz_path = Path(str(file_path) + '.gz')
                                
                                with open(file_path, 'rb') as f_in:
                                    with gzip.open(gz_path, 'wb') as f_out:
                                        shutil.copyfileobj(f_in, f_out)
                                
                                # Удаление оригинала
                                file_path.unlink()
                                
                                compressed_count += 1
                                logger.debug(f"Сжато: {file_path} → {gz_path}")
                                
                        except Exception as e:
                            logger.error(f"Ошибка сжатия {file_path}: {e}")
        
        logger.info(f"Сжато {compressed_count} файлов")
        return compressed_count
    
    async def get_log_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики использования дискового пространства.
        
        RETURNS:
            Dict со статистикой
        """
        stats = {
            'active': {'files': 0, 'size_bytes': 0},
            'archive': {'files': 0, 'size_bytes': 0, 'by_month': {}},
            'indexed': {'files': 0, 'size_bytes': 0},
            'total_size_bytes': 0,
        }
        
        # Статистика active/
        if self.config.active_dir.exists():
            for file_path in self.config.active_dir.rglob("*"):
                if file_path.is_file() and not file_path.is_symlink():
                    size = file_path.stat().st_size
                    stats['active']['files'] += 1
                    stats['active']['size_bytes'] += size
        
        # Статистика archive/
        if self.config.archive_dir.exists():
            for year_dir in self.config.archive_dir.iterdir():
                if not year_dir.is_dir():
                    continue
                
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    
                    month_key = f"{year_dir.name}/{month_dir.name}"
                    month_stats = {'files': 0, 'size_bytes': 0}
                    
                    for file_path in month_dir.rglob("*"):
                        if file_path.is_file():
                            size = file_path.stat().st_size
                            month_stats['files'] += 1
                            month_stats['size_bytes'] += size
                            stats['archive']['files'] += 1
                            stats['archive']['size_bytes'] += size
                    
                    stats['archive']['by_month'][month_key] = month_stats
        
        # Статистика indexed/
        if self.config.indexed_dir.exists():
            for file_path in self.config.indexed_dir.glob("*"):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    stats['indexed']['files'] += 1
                    stats['indexed']['size_bytes'] += size
        
        # Общая сумма
        stats['total_size_bytes'] = (
            stats['active']['size_bytes'] +
            stats['archive']['size_bytes'] +
            stats['indexed']['size_bytes']
        )
        
        # Добавление человекочитаемых размеров
        stats['active']['size_mb'] = stats['active']['size_bytes'] / (1024 * 1024)
        stats['archive']['size_mb'] = stats['archive']['size_bytes'] / (1024 * 1024)
        stats['indexed']['size_mb'] = stats['indexed']['size_bytes'] / (1024 * 1024)
        stats['total_size_mb'] = stats['total_size_bytes'] / (1024 * 1024)
        
        return stats
    
    async def shutdown(self) -> None:
        """Завершение работы ротатора."""
        logger.info("Завершение работы LogRotator...")
        
        # Остановка фоновой очистки
        self._stop_event.set()
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        
        self._initialized = False
        logger.info("LogRotator завершил работу")
    
    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации."""
        return self._initialized


# Глобальный экземпляр
_rotator: Optional[LogRotator] = None


def get_log_rotator() -> LogRotator:
    """Получение глобального LogRotator."""
    global _rotator
    if _rotator is None:
        _rotator = LogRotator()
    return _rotator


async def init_log_rotator(config: Optional[LoggingConfig] = None) -> LogRotator:
    """
    Инициализация глобального LogRotator.
    
    ARGS:
        config: Конфигурация
        
    RETURNS:
        LogRotator: Инициализированный ротатор
    """
    global _rotator
    _rotator = LogRotator(config)
    await _rotator.initialize()
    return _rotator
