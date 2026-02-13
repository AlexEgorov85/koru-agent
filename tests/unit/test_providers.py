"""
Тестовый скрипт для проверки провайдеров
"""
import sys
import os
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.infrastructure.providers.llm.factory import LLMProviderFactory
from core.infrastructure.providers.llm.mock_provider import MockLLMConfig

def test_factories():
    print("Тестируем фабрики провайдеров...")
    
    # Создаем фабрику
    factory = LLMProviderFactory()
    print(f"Фабрика создана: {factory}")
    
    # Проверяем доступные провайдеры
    print(f"Доступные провайдеры: {list(factory._providers.keys())}")
    
    # Попробуем создать мок-провайдер
    try:
        config = MockLLMConfig(model_name="test-model", temperature=0.7)
        mock_provider = factory.create_provider('mock', config=config)
        print(f"Mock провайдер создан: {type(mock_provider).__name__}")
    except Exception as e:
        print(f"Ошибка создания mock провайдера: {e}")
        import traceback
        traceback.print_exc()
    
    # Попробуем создать llama_cpp провайдер (только если установлен llama-cpp-python)
    try:
        # Для теста создадим минимальный словарь конфигурации
        config = {
            'model_path': 'models/test.gguf',  # Это будет проверено при инициализации
            'model_name': 'test-model',
            'n_ctx': 512,
            'n_threads': 1,
            'verbose': False
        }
        llama_provider = factory.create_provider('llama_cpp', config=config, model_name='test-model')
        print(f"Llama.cpp провайдер создан: {type(llama_provider).__name__}")
    except ImportError as e:
        print(f"llama-cpp-python не установлен (это нормально для тестирования): {e}")
    except Exception as e:
        print(f"Другая ошибка при создании llama_cpp провайдера: {e}")

if __name__ == "__main__":
    test_factories()