param_value = 'Пушкин'
param_name = 'author'

if param_name in ['author', 'title_pattern']:
    if '%' not in param_value:
        param_value = f'%{param_value}%'
        
print(f'Параметр author после обработки: {repr(param_value)}')
