"""
Скрипт для скачивания модели all-MiniLM-L6-v2 локально в папку проекта.

Использование:
    python download_model.py

Модель будет сохранена в: models/embedding/all-MiniLM-L6-v2
"""

import os
import sys

# Путь для сохранения модели
MODEL_SAVE_PATH = "models/embedding/all-MiniLM-L6-v2"


def download_model():
    """Скачать и сохранить модель локально."""
    print("📥 Скачивание модели all-MiniLM-L6-v2...")
    print(f"   Путь сохранения: {os.path.abspath(MODEL_SAVE_PATH)}")
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # Создаём директорию
        os.makedirs(MODEL_SAVE_PATH, exist_ok=True)
        
        # Скачиваем модель
        print("   Загрузка модели (может занять несколько минут)...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Сохраняем локально
        print(f"   Сохранение в {MODEL_SAVE_PATH}...")
        model.save(MODEL_SAVE_PATH)
        
        print("✅ Модель успешно скачана и сохранена!")
        print(f"   Локальный путь: {os.path.abspath(MODEL_SAVE_PATH)}")
        
        # Проверяем работу
        print("\n🧪 Проверка модели...")
        test_embedding = model.encode("Тестовое предложение")
        print(f"   Размерность вектора: {len(test_embedding)}")
        print("   Модель готова к использованию!")
        
        return True
        
    except ImportError as e:
        print(f"❌ Ошибка: sentence-transformers не установлен")
        print(f"   Установите: pip install sentence-transformers")
        return False
    except Exception as e:
        print(f"❌ Ошибка при загрузке: {e}")
        return False


def update_config():
    """Обновить конфигурацию с локальным путём."""
    import yaml
    
    config_path = "core/config/defaults/dev.yaml"
    
    if not os.path.exists(config_path):
        print(f"⚠️ Файл конфигурации не найден: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Обновляем путь к модели
        abs_model_path = os.path.abspath(MODEL_SAVE_PATH).replace('\\', '/')
        config['vector_search']['embedding']['model_name'] = abs_model_path
        
        # Сохраняем конфигурацию
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        print(f"✅ Конфигурация обновлена: {config_path}")
        print(f"   model_name: {abs_model_path}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обновления конфигурации: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("📦 Загрузка локальной модели эмбеддингов")
    print("=" * 60)
    
    success = download_model()
    
    if success:
        print("\n" + "=" * 60)
        print("🔄 Обновление конфигурации...")
        print("=" * 60)
        update_config()
        
        print("\n" + "=" * 60)
        print("✅ ГОТОВО!")
        print("=" * 60)
        print("\nТеперь модель будет загружаться локально без интернета.")
        print("=" * 60)
