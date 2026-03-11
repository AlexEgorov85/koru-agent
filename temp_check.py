from core.config.models import SystemConfig

c = SystemConfig(data_dir='data')
print('vector_search:', c.vector_search)
if c.vector_search:
    print('storage:', c.vector_search.storage)
    print('indexes:', c.vector_search.indexes)
