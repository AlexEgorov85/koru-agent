#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Комплексный анализ статистики коммитов за неделю (только код)"""

import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

def run_git_command(args):
    """Выполнить git команду и вернуть результат"""
    result = subprocess.run(
        ['git'] + args,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    return result.stdout.strip().split('\n') if result.stdout.strip() else []

def is_code_file(filename):
    """Проверить, является ли файл кодом (не документация)"""
    # Исключаем документацию и тестовые данные
    exclude_extensions = {
        '.md', '.txt', '.rst', '.pdf',
        '.yaml', '.yml',  # Конфигурационные файлы
        '.json',  # JSON файлы
    }
    exclude_dirs = {'docs/', 'logs/', 'data/', 'tests/'}
    
    # Проверяем расширение
    for ext in exclude_extensions:
        if filename.endswith(ext):
            return False
    
    # Проверяем директории
    for dir_name in exclude_dirs:
        if filename.startswith(dir_name):
            return False
    
    return True

# Получаем список файлов по типам изменений
added_files = run_git_command(['log', '--since=1 week ago', '--diff-filter=A', '--name-only', '--format='])
deleted_files = run_git_command(['log', '--since=1 week ago', '--diff-filter=D', '--name-only', '--format='])
modified_files = run_git_command(['log', '--since=1 week ago', '--diff-filter=M', '--name-only', '--format='])

# Получаем статистику по строкам
numstat_lines = run_git_command(['log', '--since=1 week ago', '--numstat', '--format='])

lines_added = 0
lines_deleted = 0
code_files_modified = 0
code_files_added = 0
code_files_deleted = 0

file_changes = {}

for line in numstat_lines:
    if line.strip():
        parts = line.split('\t')
        if len(parts) >= 3:
            added, deleted, filename = parts[0], parts[1], parts[2]
            
            # Считаем только код
            if is_code_file(filename):
                if added != '-':
                    lines_added += int(added)
                if deleted != '-':
                    lines_deleted += int(deleted)
                
                total = 0
                if added != '-':
                    total += int(added)
                if deleted != '-':
                    total += int(deleted)
                
                file_changes[filename] = file_changes.get(filename, 0) + total

# Подсчитываем файлы
for f in added_files:
    if f and is_code_file(f):
        code_files_added += 1

for f in deleted_files:
    if f and is_code_file(f):
        code_files_deleted += 1

for f in modified_files:
    if f and is_code_file(f):
        code_files_modified += 1

# Получаем количество коммитов
commits = run_git_command(['log', '--since=1 week ago', '--oneline'])

# Выводим статистику
print('=' * 70)
print('📊 СТАТИСТИКА ИЗМЕНЕНИЙ ЗА НЕДЕЛЮ (ТОЛЬКО КОД)')
print('=' * 70)
print(f'💾 Коммитов: {len(commits)}')
print(f'📝 Файлов кода изменено: {code_files_modified}')
print(f'➕ Файлов кода добавлено: {code_files_added}')
print(f'➖ Файлов кода удалено: {code_files_deleted}')
print(f'📈 Строк кода добавлено: {lines_added:,}')
print(f'📉 Строк кода удалено: {lines_deleted:,}')
print(f'📁 Всего файлов кода затронуто: {code_files_modified + code_files_added + code_files_deleted}')
print('=' * 70)

# Топ-10 самых изменённых файлов кода
print('\n📋 ТОП-10 САМЫХ ИЗМЕНЁННЫХ ФАЙЛОВ КОДА:')
print('-' * 70)

sorted_files = sorted(file_changes.items(), key=lambda x: x[1], reverse=True)[:10]
for i, (filename, changes) in enumerate(sorted_files, 1):
    print(f'{i:2}. {changes:>6,} строк | {filename}')

print('=' * 70)

# Статистика по директориям
print('\n📁 ИЗМЕНЕНИЯ ПО ДИРЕКТОРИЯМ:')
print('-' * 70)

dir_changes = {}
for filename, changes in file_changes.items():
    dir_name = filename.split('/')[0] if '/' in filename else filename.split('\\')[0] if '\\' in filename else '.'
    dir_changes[dir_name] = dir_changes.get(dir_name, 0) + changes

sorted_dirs = sorted(dir_changes.items(), key=lambda x: x[1], reverse=True)[:10]
for dir_name, changes in sorted_dirs:
    print(f'  {dir_name:<40} {changes:>8,} строк')

print('=' * 70)
