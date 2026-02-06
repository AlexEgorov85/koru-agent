from infrastructure.testing.llm.test_llm_provider import TestLLMProvider

class CodeAnalysisLLMScenarios:
    """Сценарии ответов LLM для анализа кода."""
    
    @staticmethod
    def configure_provider(provider: TestLLMProvider):
        """Настраивает мок с детерминированными ответами для анализа кода."""
        
        # Сценарий 1: Анализ структуры проекта
        provider.add_response_by_content(
            prompt_content="анализируй структуру проекта",
            response="""
<thinking>
Анализирую структуру проекта для поиска Python-файлов.
</thinking>
<action>
{"tool": "file_lister", "parameters": {"path": ".", "pattern": "*.py"}}
</action>
"""
        )
        
        # Сценарий 2: Ответ на результат инструмента (нашли файлы)
        provider.add_response_by_content(
            prompt_content="main.py, utils.py",
            response="""
<thinking>
Найдены 2 Python-файла: main.py и utils.py. Анализ завершён.
</thinking>
<action>
{"type": "finish", "result": "Найдены Python-файлы: main.py, utils.py"}
</action>
"""
        )
        
        # Сценарий 3: Обработка ошибки (файл не найден)
        provider.add_error_by_content(
            prompt_content="не_существует",
            error=RuntimeError("Файл не найден")
        )