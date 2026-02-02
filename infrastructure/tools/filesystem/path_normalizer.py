"""
PathNormalizer - инструмент для нормализации путей файлов.
"""
from typing import Dict, Any
import os
from pathlib import Path

from domain.abstractions.tools.base_tool import BaseTool
from domain.models.resource import Resource


class PathNormalizerTool(BaseTool):
    """
    Инструмент для нормализации путей файлов.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (инструмент)
    - Зависимости: от абстракций (BaseTool)
    - Ответственность: нормализация и проверка путей файлов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    name = "path_normalizer"
    
    def __init__(self, **kwargs):
        """Инициализация инструмента нормализации путей."""
        super().__init__(**kwargs)
        self.name = "path_normalizer"
    
    async def execute(self, parameters: Dict[str, Any]) -> Resource:
        """
        Выполнение операции нормализации пути.
        
        Args:
            parameters: Параметры операции, включающие 'path' - путь для нормализации
        
        Returns:
            Resource: Результат операции нормализации пути
        """
        try:
            raw_path = parameters.get("path")
            if not raw_path:
                raise ValueError("Параметр 'path' обязателен для нормализации")
            
            # Нормализуем путь
            normalized_path = self._normalize_path(raw_path)
            
            # Получаем абсолютный путь
            absolute_path = self._get_absolute_path(normalized_path)
            
            # Проверяем существование пути
            exists = os.path.exists(absolute_path)
            
            # Проверяем тип пути (файл или директория)
            path_type = None
            if exists:
                if os.path.isfile(absolute_path):
                    path_type = "file"
                elif os.path.isdir(absolute_path):
                    path_type = "directory"
            
            result_data = {
                "success": True,
                "original_path": raw_path,
                "normalized_path": normalized_path,
                "absolute_path": absolute_path,
                "exists": exists,
                "type": path_type
            }
            
            return Resource(
                id=f"path_normalized_{normalized_path}",
                name=f"Normalized path {normalized_path}",
                type="path_info",
                data=result_data,
                metadata={"normalized_path": normalized_path, "path_exists": exists}
            )
            
        except Exception as e:
            error_data = {
                "success": False,
                "error": str(e),
                "original_path": parameters.get("path", "")
            }
            
            return Resource(
                id=f"path_error_{parameters.get('path', 'unknown')}",
                name=f"Error normalizing path {parameters.get('path', 'unknown')}",
                type="error",
                data=error_data,
                metadata={"error_type": "NormalizationError", "exception": str(e)}
            )
    
    def _normalize_path(self, path: str) -> str:
        """
        Нормализация пути: приведение к стандартному формату.
        
        Args:
            path: Исходный путь
            
        Returns:
            str: Нормализованный путь
        """
        # Заменяем обратные слэши на обычные
        normalized = path.replace('\\', '/')
        
        # Нормализуем путь с помощью os.path.normpath
        normalized = os.path.normpath(normalized)
        
        # Заменяем обратно на обычные слэши, если нужно
        normalized = normalized.replace('\\', '/')
        
        return normalized
    
    def _get_absolute_path(self, path: str) -> str:
        """
        Получение абсолютного пути.
        
        Args:
            path: Относительный или абсолютный путь
            
        Returns:
            str: Абсолютный путь
        """
        return os.path.abspath(path)
    
    def _is_safe_path(self, path: str, base_path: str = None) -> bool:
        """
        Проверка безопасности пути (предотвращение выхода за пределы разрешенной директории).
        
        Args:
            path: Проверяемый путь
            base_path: Базовая директория для проверки (если None, используется текущая директория)
            
        Returns:
            bool: True, если путь безопасен
        """
        if base_path is None:
            base_path = os.getcwd()
        
        # Получаем абсолютный путь
        abs_path = os.path.abspath(path)
        base_abs_path = os.path.abspath(base_path)
        
        # Проверяем, начинается ли абсолютный путь с базового пути
        return os.path.commonpath([abs_path]) == os.path.commonpath([abs_path, base_abs_path])
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Возвращает возможности инструмента.
        """
        return {
            "normalize_path": {
                "description": "Нормализация пути файла или директории",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Путь для нормализации"
                        }
                    },
                    "required": ["path"]
                }
            },
            "validate_path": {
                "description": "Проверка существования и типа пути",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Путь для проверки"
                        }
                    },
                    "required": ["path"]
                }
            }
        }