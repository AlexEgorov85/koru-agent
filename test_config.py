from core.config import get_config

config = get_config(profile='dev')
print('Model:', config.vector_search.embedding.model_name)
print('Dimension:', config.vector_search.embedding.dimension)