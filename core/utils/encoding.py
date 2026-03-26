"""
Утилиты настройки кодировки для кроссплатформенной работы.

ЦЕЛЬ:
- Устранить дублирование chcp 65001 по всему коду
- Единая точка настройки UTF-8
- Корректная работа с emoji и Unicode на всех ОС

ИСПОЛЬЗОВАНИЕ:
```python
from core.utils.encoding import setup_encoding

# Вызывать ОДИН раз в начале программы
setup_encoding()
```

ПРОБЛЕМЫ КОТОРЫЕ РЕШАЕТ:
- ❌ Mojibake (кракозябры) в логах
- ❌ Проблемы с emoji на Windows
- ❌ Разная кодировка stdout/stderr
- ❌ Scripts fix_encoding.py больше не нужен
"""
import sys
import locale
import os
from typing import Optional, TextIO


class EncodingSetup:
    """
    Менеджер настройки кодировки.
    
    FEATURES:
    - Авто-определение платформы
    - Безопасная настройка stdout/stderr
    - Обработка ошибок без падения
    - Идемпотентность (можно вызывать многократно)
    """
    
    def __init__(self):
        self._is_setup = False
        self._original_stdout: Optional[TextIO] = None
        self._original_stderr: Optional[TextIO] = None
    
    def setup(self, force: bool = False) -> bool:
        """
        Настройка кодировки для всей системы.
        
        ARGS:
        - force: Принудительная настройка даже если уже настроено
        
        RETURNS:
        - True если успешно, False если ошибка
        """
        # Защита от повторного вызова
        if self._is_setup and not force:
            return True
        
        try:
            # Сохраняем оригинальные потоки
            self._original_stdout = sys.stdout
            self._original_stderr = sys.stderr
            
            if sys.platform == 'win32':
                self._setup_windows()
            else:
                self._setup_unix()
            
            # Настраиваем locale
            self._setup_locale()
            
            self._is_setup = True
            return True
            
        except Exception as e:
            return False
    
    def _setup_windows(self) -> None:
        """Настройка кодировки на Windows."""
        # Устанавливаем UTF-8 кодировку консоли
        try:
            os.system('chcp 65001 >nul 2>&1')
        except Exception:
            pass  # Игнорируем ошибки chcp
        
        # Перенастраиваем stdout/stderr на UTF-8
        try:
            # Проверяем что потоки имеют метод reconfigure (Python 3.7+)
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            # Fallback: оборачиваем в TextIOWrapper
            try:
                import io
                if sys.stdout and sys.stdout.encoding != 'utf-8':
                    sys.stdout = io.TextIOWrapper(
                        sys.stdout.buffer, 
                        encoding='utf-8', 
                        errors='replace',
                        line_buffering=True
                    )
                if sys.stderr and sys.stderr.encoding != 'utf-8':
                    sys.stderr = io.TextIOWrapper(
                        sys.stderr.buffer, 
                        encoding='utf-8', 
                        errors='replace',
                        line_buffering=True
                    )
            except Exception:
                pass  # Последняя надежда
    
    def _setup_unix(self) -> None:
        """Настройка кодировки на Unix/Linux/macOS."""
        try:
            # Проверяем и устанавливаем locale
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            except locale.Error:
                pass  # Игнорируем если locale не доступен
        
        # Настраиваем stdout/stderr
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    
    def _setup_locale(self) -> None:
        """Настройка locale для корректной работы Unicode."""
        # Установка PYTHONIOENCODING
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
        
        # Попытка установки locale
        locales_to_try = [
            'C.UTF-8',
            'en_US.UTF-8',
            'ru_RU.UTF-8',
            '',
        ]
        
        for loc in locales_to_try:
            try:
                if loc:
                    locale.setlocale(locale.LC_ALL, loc)
                else:
                    locale.setlocale(locale.LC_ALL, '')
                break
            except locale.Error:
                continue
    
    def restore(self) -> None:
        """Восстановление оригинальных потоков."""
        if self._original_stdout:
            sys.stdout = self._original_stdout
        if self._original_stderr:
            sys.stderr = self._original_stderr
        self._is_setup = False
    
    @property
    def is_setup(self) -> bool:
        """Проверка что кодировка настроена."""
        return self._is_setup
    
    def get_encoding_info(self) -> dict:
        """
        Получить информацию о текущей кодировке.
        
        RETURNS:
        - Dict с информацией о кодировке
        """
        return {
            'platform': sys.platform,
            'stdout_encoding': getattr(sys.stdout, 'encoding', 'unknown'),
            'stderr_encoding': getattr(sys.stderr, 'encoding', 'unknown'),
            'stdin_encoding': getattr(sys.stdin, 'encoding', 'unknown'),
            'filesystem_encoding': sys.getfilesystemencoding(),
            'default_encoding': sys.getdefaultencoding(),
            'locale': locale.getdefaultlocale(),
            'is_setup': self._is_setup,
        }


# ============================================================
# Глобальный экземпляр
# ============================================================

_encoding_manager: Optional[EncodingSetup] = None


def get_encoding_manager() -> EncodingSetup:
    """Получить менеджер кодировки."""
    global _encoding_manager
    if _encoding_manager is None:
        _encoding_manager = EncodingSetup()
    return _encoding_manager


def setup_encoding(force: bool = False) -> bool:
    """
    Настроить кодировку для всей системы.
    
    Вызывать ОДИН раз в начале программы (в main.py).
    
    ARGS:
    - force: Принудительная настройка
    
    RETURNS:
    - True если успешно
    """
    return get_encoding_manager().setup(force=force)


def restore_encoding() -> None:
    """Восстановить оригинальную кодировку."""
    get_encoding_manager().restore()


def is_encoding_setup() -> bool:
    """Проверка что кодировка настроена."""
    return get_encoding_manager().is_setup


def get_encoding_info() -> dict:
    """Получить информацию о кодировке."""
    return get_encoding_manager().get_encoding_info()


# ============================================================
# Утилиты для работы с текстом
# ============================================================

class StderrFilter:
    """
    Фильтр stderr для подавления технических сообщений.
    
    USAGE:
    ```python
    sys.stderr = StderrFilter(sys.stderr, patterns=["llama_context:"])
    ```
    """
    
    def __init__(self, original_stderr, patterns: list = None):
        self.original_stderr = original_stderr
        self.patterns = patterns or []
    
    def write(self, text):
        """Запись в stderr с фильтрацией."""
        # Пропускаем сообщения matching patterns
        for pattern in self.patterns:
            if pattern in text:
                return
        self.original_stderr.write(text)
        self.original_stderr.flush()
    
    def flush(self):
        """Проброс flush."""
        self.original_stderr.flush()
    
    def isatty(self):
        """Проброс isatty."""
        return self.original_stderr.isatty()


def safe_encode(text: str, encoding: str = 'utf-8') -> bytes:
    """
    Безопасное кодирование строки.
    
    ARGS:
    - text: Строка для кодирования
    - encoding: Кодировка
    
    RETURNS:
    - Закодированные байты
    """
    if not isinstance(text, str):
        text = str(text)
    return text.encode(encoding, errors='replace')


def safe_decode(data: bytes, encoding: str = 'utf-8') -> str:
    """
    Безопасное декодирование байтов.
    
    ARGS:
    - data: Байты для декодирования
    - encoding: Кодировка
    
    RETURNS:
    - Декодированная строка
    """
    if not isinstance(data, bytes):
        return str(data)
    return data.decode(encoding, errors='replace')


def sanitize_for_terminal(text: str) -> str:
    """
    Очистка текста для безопасного вывода в терминал.
    
    Удаляет символы которые могут вызвать проблемы:
    - Непечатаемые символы (кроме \n, \t)
    - Символы управления курсором
    - BOM маркеры
    
    ARGS:
    - text: Текст для очистки
    
    RETURNS:
    - Очищенный текст
    """
    if not text:
        return text
    
    # Удаляем BOM
    text = text.replace('\ufeff', '')
    
    # Удаляем непечатаемые символы (кроме \n, \t, \r)
    result = []
    for char in text:
        if char in '\n\t\r':
            result.append(char)
        elif char.isprintable():
            result.append(char)
        # Остальные символы пропускаем
    
    return ''.join(result)


def fix_mojibake(text: str) -> str:
    """
    Попытка исправления mojibake (кракозябров).
    
    ARGS:
    - text: Текст с возможными кракозябрами
    
    RETURNS:
    - Исправленный текст
    """
    if not text:
        return text
    
    # Частые случаи mojibake
    replacements = {
        'РЎ': 'С',  # Русская С вместо латинской
        'РЎ': 'с',
        'Рў': 'Т',
        'РЎР': 'Ст',
    }
    
    result = text
    for wrong, correct in replacements.items():
        result = result.replace(wrong, correct)
    
    return result


# ============================================================
# Контекстный менеджер
# ============================================================

class encoding_context:
    """
    Контекстный менеджер для временной смены кодировки.
    
    USAGE:
    ```python
    with encoding_context('cp1251'):
        # Работа с cp1251
    # Автоматическое восстановление UTF-8
    ```
    """
    
    def __init__(self, encoding: str = 'utf-8'):
        self.encoding = encoding
        self._old_stdout = None
        self._old_stderr = None
    
    def __enter__(self):
        import io
        
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding=self.encoding,
                errors='replace'
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding=self.encoding,
                errors='replace'
            )
        except Exception:
            pass
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._old_stdout:
            sys.stdout = self._old_stdout
        if self._old_stderr:
            sys.stderr = self._old_stderr
