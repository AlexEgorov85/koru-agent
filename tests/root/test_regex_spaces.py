import re

# Тестируем различные варианты регулярных выражений
text = "This is {{ variable1 }} and { variable2 } and {{ var3 }}"
print(f"Text: {text}")

# Правильное регулярное выражение для двойных скобок (с пробелами)
pattern_double = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
matches_double = re.findall(pattern_double, text)
print(f"Double braces matches: {matches_double}")

# Правильное регулярное выражение для одинарных скобок (с пробелами)
pattern_single = r'\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}'
matches_single = re.findall(pattern_single, text)
print(f"Single braces matches: {matches_single}")

# Объединенное регулярное выражение (с пробелами)
pattern_combined = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}|\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}'
matches_combined = re.findall(pattern_combined, text)
print(f"Combined matches: {matches_combined}")

# Проверим на реальном примере
real_text = "{{ capabilities_list }} {{ goal }} {{ context }} {{ max_steps }}"
real_matches = re.findall(pattern_combined, real_text)
print(f"Real text matches: {real_matches}")

# Обработка результатов
real_processed = []
for match_tuple in real_matches:
    for item in match_tuple:
        if item:  # Если элемент не пустой
            real_processed.append(item)
            break  # Берем первый непустой элемент из кортежа

print(f"Real processed: {real_processed}")