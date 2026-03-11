from core.config.app_config import AppConfig

c = AppConfig(data_dir='data')
print('vector_search:', c.vector_search)
if c.vector_search:
    print('storage:', c.vector_search.storage)
    print('indexes:', c.vector_search.indexes)
