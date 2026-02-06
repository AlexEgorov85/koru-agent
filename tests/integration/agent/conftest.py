import pytest
from application.services.file_prompt_repository import FilePromptRepository

def pytest_configure(config):
    """Валидация промтов перед запуском интеграционных тестов."""
    # Проверяем, что запускаются интеграционные тесты
    cmd_args = ' '.join(config.args)
    if "integration" in cmd_args or "integration" in str(config.rootpath):
        repo = FilePromptRepository(base_path="prompts")
        errors = repo.load_from_directory("prompts")
        
        if errors:
            pytest.exit(
                f"❌ Обнаружены ошибки в промтах. Интеграционные тесты не могут быть запущены:\n" +
                "\n".join(errors),
                returncode=1
            )
        
        # Проверяем наличие критически важных промтов
        required_prompts = [
            ("problem_solving", "code_analysis", "system"),
            ("problem_solving", "code_analysis", "user"),
            ("problem_solving", "llm_decision", "system"),
        ]
        
        missing = []
        for domain, capability, role in required_prompts:
            version = repo.get_active_version(domain, capability, "openai", role)
            if not version:
                missing.append(f"{domain}/{capability}/{role}")
        
        if missing:
            pytest.exit(
                f"❌ Отсутствуют критически важные промты:\n" + "\n".join(missing),
                returncode=1
            )
