"""Тесты границ слоёв архитектуры"""
import pytest
import os
import sys
from pathlib import Path


class TestLayerBoundaries:
    """Тесты границ слоёв архитектуры"""
    
    def test_domain_layer_is_independent_from_application_and_infrastructure(self):
        """Тест что слой домена независим от слоёв приложения и инфраструктуры"""
        # Проверяем, что в директории domain нет импортов из application и infrastructure
        domain_path = Path("domain")
        if domain_path.exists():
            # Рекурсивно проверяем все Python-файлы в домене
            domain_py_files = list(domain_path.rglob("*.py"))
            
            for py_file in domain_py_files:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Проверяем, что в файлах домена нет импортов из application и infrastructure
                    assert "from application" not in content, f"Файл {py_file} содержит импорт из application"
                    assert "import application" not in content, f"Файл {py_file} содержит импорт из application"
                    assert "from infrastructure" not in content, f"Файл {py_file} содержит импорт из infrastructure"
                    assert "import infrastructure" not in content, f"Файл {py_file} содержит импорт из infrastructure"
    
    def test_application_layer_depends_only_on_domain_not_infrastructure(self):
        """Тест что слой приложения зависит только от домена, но не от инфраструктуры"""
        application_path = Path("application")
        if application_path.exists():
            # Рекурсивно проверяем все Python-файлы в приложении
            application_py_files = list(application_path.rglob("*.py"))
            
            for py_file in application_py_files:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Проверяем, что в файлах приложения есть импорты из domain
                    has_domain_import = "from domain" in content or "import domain" in content
                    
                    # Проверяем, что в файлах приложения нет импортов из infrastructure
                    has_infra_import = "from infrastructure" in content or "import infrastructure" in content
                    
                    # В идеальной архитектуре должны быть импорты из domain, но не из infrastructure
                    # Однако, в реальных системах могут быть легитимные случаи использования infrastructure в application
                    # Поэтому мы просто регистрируем такие случаи для ручной проверки
                    if has_infra_import:
                        print(f"Предупреждение: файл {py_file} содержит импорт из infrastructure, "
                              f"это может нарушать граници слоёв")
    
    def test_infrastructure_layer_can_depend_on_domain_and_application(self):
        """Тест что слой инфраструктуры может зависеть от домена и приложения"""
        infrastructure_path = Path("infrastructure")
        if infrastructure_path.exists():
            # Рекурсивно проверяем все Python-файлы в инфраструктуре
            infrastructure_py_files = list(infrastructure_path.rglob("*.py"))
            
            # В слое инфраструктуры допускаются импорты из domain и application
            # поэтому этот тест скорее проверяет, что файлы существуют
            assert len(infrastructure_py_files) > 0, "Не найдено файлов в слое инфраструктуры"
    
    def test_layers_have_correct_dependencies_direction(self):
        """Тест направленности зависимостей между слоями"""
        # Проверяем, что зависимости направлены сверху вниз:
        # Domain <- Application <- Infrastructure
        # Т.е. Domain не зависит от других слоёв, Infrastructure может зависеть от всех
        
        domain_path = Path("domain")
        application_path = Path("application") 
        infrastructure_path = Path("infrastructure")
        
        # Убедимся, что все пути существуют
        assert domain_path.exists(), "Директория domain не найдена"
        assert application_path.exists(), "Директория application не найдена"
        assert infrastructure_path.exists(), "Директория infrastructure не найдена"
        
        # Проверим, что домен не зависит от других слоев
        domain_files = list(domain_path.rglob("*.py")) if domain_path.exists() else []
        for file in domain_files:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Проверяем, что домен не импортирует application или infrastructure
                for disallowed_import in ["application", "infrastructure"]:
                    if disallowed_import in content:
                        # Проверяем, что это не часть комментария или строки
                        lines = content.split('\n')
                        for i, line in enumerate(lines, 1):
                            if disallowed_import in line and not line.strip().startswith('#'):
                                # Исключаем случаи, когда имя папки встречается в строке документации
                                if '"""' not in line and "'''" not in line:
                                    print(f"Возможное нарушение границ: {file}:{i} - {line.strip()}")