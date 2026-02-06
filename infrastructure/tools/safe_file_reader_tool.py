import os
import pathlib
from typing import Dict, Any, Optional
from dataclasses import dataclass
import asyncio

@dataclass
class SafeFileReadInput:
    path: str
    encoding: str = "utf-8"

@dataclass
class SafeFileReadOutput:
    success: bool
    content: str = ""
    error: str = ""
    content_path: Optional[str] = None

class SafeFileReaderTool:
    """
    Безопасный инструмент для чтения файлов с полной защитой от различных атак.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (инструмент)
    - Зависимости: только от стандартной библиотеки и pathlib
    - Ответственность: безопасное чтение файлов с проверками
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    БЕЗОПАСНОСТЬ:
    1. Защита от path traversal (../, ..\)
    2. Защита от символических ссылок вне проекта
    3. Ограничение размера файла (макс 10MB)
    4. Блокировка чувствительных файлов (.env, credentials и т.д.)
    5. Безопасная обработка ошибок
    """
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Инициализация безопасного инструмента чтения файлов.
        
        Args:
            project_root: Корневая директория проекта для ограничения доступа
        """
        self.project_root = pathlib.Path(project_root or os.getcwd()).resolve()
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        
        # Паттерны чувствительных файлов
        self.sensitive_patterns = [
            ".env",
            ".env.local",
            ".env.production",
            ".env.development",
            "credentials",
            "passwords",
            "secrets",
            ".pem",
            ".key",
            ".crt",
            ".git/config",
            ".ssh",
            ".aws/credentials",
            "id_rsa",
            "id_dsa",
            ".dockerenv",
            ".python-version",
            "Gemfile.lock",
            "package-lock.json",
            "yarn.lock"
        ]

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполнение безопасного чтения файла.
        
        Args:
            parameters: Параметры выполнения (path, encoding)
            
        Returns:
            Dict[str, Any]: Результат выполнения с полями success, content, error
        """
        try:
            # Валидация и создание объекта входных данных
            input_data = SafeFileReadInput(**parameters)
            
            # Выполнение всех проверок безопасности перед открытием файла
            validation_result = await self._validate_path_security(input_data.path)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "content": "",
                    "error": validation_result["error"],
                    "content_path": None
                }
            
            # Безопасное чтение файла
            safe_path = validation_result["safe_path"]
            content_result = await self._read_file_securely(safe_path, input_data.encoding)
            
            return content_result
            
        except TypeError as e:
            # Ошибка при создании объекта входных данных
            return {
                "success": False,
                "content": "",
                "error": f"Некорректные параметры: {str(e)}",
                "content_path": None
            }
        except Exception as e:
            # Внутренняя ошибка инструмента
            return {
                "success": False,
                "content": "",
                "error": f"Внутренняя ошибка инструмента: {str(e)}",
                "content_path": None
            }

    async def _validate_path_traversal(self, user_path: str) -> Dict[str, Any]:
        """
        Проверка на попытки path traversal.
        
        Args:
            user_path: Пользовательский путь к файлу
            
        Returns:
            Dict с результатом проверки
        """
        # Проверяем наличие '../' или '..\' в пути (без учета регистра)
        if "../" in user_path or "..\\" in user_path or "..%5C" in user_path or "..%2F" in user_path:
            return {
                "valid": False,
                "error": "Обнаружена попытка path traversal: '../' или '..\\' в пути"
            }
        
        # Используем pathlib для безопасного построения пути
        try:
            requested_path = (self.project_root / user_path).resolve()
        except (ValueError, OSError) as e:
            return {
                "valid": False,
                "error": f"Некорректный путь: {str(e)}"
            }
        
        # Проверяем, что резолвнутый путь начинается с корня проекта
        try:
            requested_path.relative_to(self.project_root)
        except ValueError:
            return {
                "valid": False,
                "error": "Путь находится вне разрешенной директории проекта"
            }
        
        return {
            "valid": True,
            "safe_path": requested_path
        }

    async def _check_symbolic_links(self, path: pathlib.Path) -> Dict[str, Any]:
        """
        Проверка символических ссылок.
        
        Args:
            path: Путь к файлу
            
        Returns:
            Dict с результатом проверки
        """
        try:
            # Получаем статус файла без разрешения символических ссылок
            lstat_result = path.lstat()
            
            # Проверяем, является ли путь символической ссылкой
            if path.is_symlink():
                # Разрешаем символическую ссылку
                resolved_path = path.resolve()
                
                # Проверяем, что разрешенная ссылка все еще внутри проекта
                try:
                    resolved_path.relative_to(self.project_root)
                except ValueError:
                    return {
                        "valid": False,
                        "error": f"Символическая ссылка ведет вне проекта: {resolved_path}"
                    }
                
                # Проверяем рекурсивно, не ведет ли ссылка к другим ссылкам вне проекта
                try:
                    # Проверяем, что разрешенный путь существует
                    if not resolved_path.exists():
                        return {
                            "valid": False,
                            "error": f"Символическая ссылка указывает на несуществующий файл: {resolved_path}"
                        }
                except (OSError, RuntimeError):
                    return {
                        "valid": False,
                        "error": f"Ошибка доступа по символической ссылке: {path}"
                    }
        
        except (OSError, RuntimeError) as e:
            return {
                "valid": False,
                "error": f"Ошибка проверки символических ссылок: {str(e)}"
            }
        
        return {"valid": True}

    async def _check_sensitive_files(self, path: pathlib.Path) -> Dict[str, Any]:
        """
        Проверка на чувствительные файлы.
        
        Args:
            path: Путь к файлу
            
        Returns:
            Dict с результатом проверки
        """
        path_str = str(path).lower()
        
        for pattern in self.sensitive_patterns:
            if pattern.lower() in path_str:
                return {
                    "valid": False,
                    "error": f"Файл заблокирован по причине безопасности: {pattern} (паттерн: {path})"
                }
        
        return {"valid": True}

    async def _check_file_size(self, path: pathlib.Path) -> Dict[str, Any]:
        """
        Проверка размера файла.
        
        Args:
            path: Путь к файлу
            
        Returns:
            Dict с результатом проверки
        """
        try:
            file_stat = path.stat()
            file_size = file_stat.st_size
            
            if file_size > self.max_file_size:
                return {
                    "valid": False,
                    "error": f"Файл слишком большой: {file_size} байт, максимум: {self.max_file_size} байт"
                }
            
            return {
                "valid": True,
                "size": file_size
            }
        except OSError as e:
            return {
                "valid": False,
                "error": f"Не удалось получить размер файла: {str(e)}"
            }

    async def _validate_file_access(self, path: pathlib.Path) -> Dict[str, Any]:
        """
        Проверка существования файла и прав доступа.
        
        Args:
            path: Путь к файлу
            
        Returns:
            Dict с результатом проверки
        """
        if not path.exists():
            return {
                "valid": False,
                "error": f"Файл не существует: {path}"
            }
        
        if path.is_dir():
            return {
                "valid": False,
                "error": f"Путь указывает на директорию, а не на файл: {path}"
            }
        
        if not path.is_file():
            return {
                "valid": False,
                "error": f"Путь не является файлом: {path}"
            }
        
        if not os.access(path, os.R_OK):
            return {
                "valid": False,
                "error": f"Нет прав на чтение файла: {path}"
            }
        
        return {"valid": True}

    async def _validate_path_security(self, user_path: str) -> Dict[str, Any]:
        """
        Комплексная проверка безопасности пути.
        
        Args:
            user_path: Пользовательский путь к файлу
            
        Returns:
            Dict с результатом проверки
        """
        # 1. Проверка path traversal
        traversal_check = await self._validate_path_traversal(user_path)
        if not traversal_check["valid"]:
            return traversal_check
        
        safe_path = traversal_check["safe_path"]
        
        # 2. Проверка символических ссылок
        symlink_check = await self._check_symbolic_links(safe_path)
        if not symlink_check["valid"]:
            return symlink_check
        
        # 3. Проверка чувствительных файлов
        sensitive_check = await self._check_sensitive_files(safe_path)
        if not sensitive_check["valid"]:
            return sensitive_check
        
        # 4. Проверка существования и прав доступа
        access_check = await self._validate_file_access(safe_path)
        if not access_check["valid"]:
            return access_check
        
        # 5. Проверка размера файла
        size_check = await self._check_file_size(safe_path)
        if not size_check["valid"]:
            return size_check
        
        return {
            "valid": True,
            "safe_path": safe_path
        }

    async def _read_file_securely(self, path: pathlib.Path, encoding: str = "utf-8") -> Dict[str, Any]:
        """
        Безопасное чтение содержимого файла.
        
        Args:
            path: Безопасный путь к файлу
            encoding: Кодировка файла
            
        Returns:
            Dict с результатом чтения
        """
        try:
            # Открываем файл в бинарном режиме для предотвращения проблем с кодировкой
            with open(path, 'rb') as file:
                content_bytes = file.read()
                
                # Проверяем размер снова на всякий случай
                if len(content_bytes) > self.max_file_size:
                    return {
                        "success": False,
                        "content": "",
                        "error": f"Файл превышает максимальный размер: {len(content_bytes)} байт",
                        "content_path": str(path)
                    }
                
                # Декодируем с обработкой ошибок
                try:
                    content = content_bytes.decode(encoding)
                except UnicodeDecodeError:
                    # Пробуем другие распространенные кодировки
                    for fallback_encoding in ['utf-8', 'cp1251', 'latin-1']:
                        try:
                            content = content_bytes.decode(fallback_encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        return {
                            "success": False,
                            "content": "",
                            "error": f"Не удалось декодировать файл с поддерживаемыми кодировками: {encoding}",
                            "content_path": str(path)
                        }
                
                return {
                    "success": True,
                    "content": content,
                    "error": "",
                    "content_path": str(path)
                }
                
        except PermissionError:
            return {
                "success": False,
                "content": "",
                "error": f"Нет прав на чтение файла: {path}",
                "content_path": str(path)
            }
        except FileNotFoundError:
            return {
                "success": False,
                "content": "",
                "error": f"Файл не найден: {path}",
                "content_path": str(path)
            }
        except OSError as e:
            return {
                "success": False,
                "content": "",
                "error": f"Ошибка чтения файла: {str(e)}",
                "content_path": str(path)
            }
        except Exception as e:
            return {
                "success": False,
                "content": "",
                "error": f"Неизвестная ошибка при чтении файла: {str(e)}",
                "content_path": str(path)
            }