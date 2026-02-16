import re

# Тестируем различные варианты регулярных выражений
text = "This is {{ variable1 }} and { variable2 } and {{ var3 }}"
print(f"Text: {text}")

# Правильное регулярное выражение для двойных скобок
pattern_double = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}'
matches_double = re.findall(pattern_double, text)
print(f"Double braces matches: {matches_double}")

# Правильное регулярное выражение для одинарных скобок
pattern_single = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
matches_single = re.findall(pattern_single, text)
print(f"Single braces matches: {matches_single}")

# Объединенное регулярное выражение
pattern_combined = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}|\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
matches_combined = re.findall(pattern_combined, text)
print(f"Combined matches: {matches_combined}")

# Обработка результатов
processed_results = []
for match_tuple in matches_combined:
    # findall возвращает кортежи, берем непустое значение
    for item in match_tuple:
        if item:  # Если элемент не пустой
            processed_results.append(item)
            break  # Берем первый непустой элемент из кортежа

print(f"Processed results: {processed_results}")

# Проверим на реальном примере
real_text = "{{ capabilities_list }} {{ goal }} {{ context }} {{ max_steps }}"
real_matches = re.findall(pattern_combined, real_text)
print(f"Real text matches: {real_matches}")

real_processed = []
for match_tuple in real_matches:
    for item in match_tuple:
        if item:
            real_processed.append(item)
            break

print(f"Real processed: {real_processed}")