"""
Файловый инструмент - операции с файловой системой с поддержкой изолированных кэшей и sandbox режима.

АРХИТЕКТУРА:
- Использует изолированные кэши, предзагруженные через ComponentConfig
- Зависимости запрашиваются из инфраструктуры при выполнении
- Поддержка sandbox режима для безопасного выполнения операций
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
from core.application.tools.base_tool import BaseTool, ToolInput, ToolOutput
from core.application.context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig


class FileToolInput(ToolInput):
    """Входные данные для FileTool"""
    def __init__(self, operation: str, path: str, content: Optional[str] = None, **kwargs):
        self.operation = operation
        self.path = path
        self.content = content
        self.kwargs = kwargs


class FileToolOutput(ToolOutput):
    """Выходные данные для FileTool"""
    def __init__(self, success: bool, data: Dict[str, Any] = None, error: str = None):
        self.success = success
        self.data = data or {}
        self.error = error


class FileTool(BaseTool):
    """
    Файловый инструмент - операции с файловой системой.
    """

    @property
    def description(self) -> str:
        return "Файловый инструмент - операции с файловой системой с поддержкой изолированных кэшей и sandbox режима"

    def __init__(self, name: str, application_context: ApplicationContext, component_config: Optional[ComponentConfig] = None, **kwargs):
        super().__init__(name, application_context, component_config, **kwargs)

    async def initialize(self) -> bool:
        """Инициализация инструмента."""
        return True

    def _is_write_operation(self, operation: str) -> bool:
        """Проверяет, является ли операция write-операцией."""
        write_operations = ["write", "delete", "rename", "move", "chmod", "chown"]
        return operation.lower() in write_operations

    async def shutdown(self) -> None:
        """Корректное завершение работы."""
        pass

    async def execute(self, input_data: FileToolInput) -> FileToolOutput:
        """
        Выполнение файловой операции.

        ARGS:
        - input_data: объект FileToolInput с параметрами выполнения
        """
        operation = input_data.operation
        file_path = input_data.path

        if not file_path:
            return FileToolOutput(
                success=False,
                error="Путь к файлу не предоставлен"
            )

        # Проверяем, что путь находится в разрешенной директории
        # для безопасности
        # Используем директорию данных из инфраструктурной конфигурации
        # ApplicationContext имеет доступ к InfrastructureContext
        allowed_base_path = Path(self.application_context.infrastructure_context.config.data_dir or "data")
        requested_path = Path(file_path).resolve()

        try:
            # Проверяем, что запрашиваемый путь находится внутри разрешенной директории
            requested_path.relative_to(allowed_base_path.resolve())
        except ValueError:
            return FileToolOutput(
                success=False,
                error="Запрашиваемый путь находится вне разрешенной директории"
            )

        # Проверка sandbox-режима для операций записи
        if not self.component_config.side_effects_enabled and self._is_write_operation(operation):
            return FileToolOutput(
                success=True,
                data={
                    "success": True,
                    "message": f"[SANDBOX] Would perform {operation} on {requested_path}",
                    "dry_run": True
                }
            )

        if operation == "read":
            result = await self._read_file(requested_path)
        elif operation == "write":
            content = input_data.content or ""
            result = await self._write_file(requested_path, content)
        elif operation == "delete":
            result = await self._delete_file(requested_path)
        elif operation == "list":
            result = await self._list_directory(requested_path.parent if requested_path.is_file() else requested_path)
        else:
            result = {
                "success": False,
                "error": f"Неизвестная операция: {operation}"
            }

        return FileToolOutput(success=result["success"], data=result, error=result.get("error"))

    async def _read_file(self, path: Path) -> Dict[str, Any]:
        """Чтение содержимого файла."""
        try:
            if not path.exists():
                return {
                    "success": False,
                    "error": "Файл не существует"
                }

            if path.is_dir():
                return {
                    "success": False,
                    "error": "Путь указывает на директорию, а не на файл"
                }

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            return {
                "success": True,
                "content": content,
                "size": len(content),
                "path": str(path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _write_file(self, path: Path, content: str) -> Dict[str, Any]:
        """Запись содержимого в файл."""
        try:
            # Создаем директории, если они не существуют
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            return {
                "success": True,
                "message": f"Файл успешно записан: {path}",
                "path": str(path),
                "size": len(content)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _delete_file(self, path: Path) -> Dict[str, Any]:
        """Удаление файла."""
        try:
            if not path.exists():
                return {
                    "success": False,
                    "error": "Файл не существует"
                }

            if path.is_dir():
                return {
                    "success": False,
                    "error": "Путь указывает на директорию, а не на файл"
                }

            path.unlink()

            return {
                "success": True,
                "message": f"Файл успешно удален: {path}",
                "path": str(path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _list_directory(self, path: Path) -> Dict[str, Any]:
        """Список файлов в директории."""
        try:
            if not path.exists():
                return {
                    "success": False,
                    "error": "Директория не существует"
                }

            if not path.is_dir():
                return {
                    "success": False,
                    "error": "Путь указывает на файл, а не на директорию"
                }

            items = []
            for item in path.iterdir():
                item_info = {
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file"
                }

                if item.is_file():
                    try:
                        stat = item.stat()
                        item_info["size"] = stat.st_size
                        item_info["modified"] = stat.st_mtime
                    except:
                        item_info["size"] = 0
                        item_info["modified"] = 0

                items.append(item_info)

            return {
                "success": True,
                "items": items,
                "count": len(items),
                "path": str(path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }