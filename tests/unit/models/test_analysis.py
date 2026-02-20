"""
Тесты моделей анализа.
"""

import pytest
from datetime import datetime
from core.models.types.analysis import AnalysisResult, BookWithCharacter


class TestAnalysisResult:
    """Тесты AnalysisResult."""
    
    def test_create_valid(self):
        """Создание валидного анализа."""
        analysis = AnalysisResult(
            entity_id="book_1",
            analysis_type="character",
            result={"main_character": "Евгений Онегин", "gender": "male"},
            confidence=0.95,
            reasoning="Имя героя в названии"
        )
        assert analysis.entity_id == "book_1"
        assert analysis.analysis_type == "character"
        assert analysis.confidence == 0.95
    
    def test_is_valid(self):
        """Проверка валидности."""
        valid = AnalysisResult(
            entity_id="book_1",
            analysis_type="character",
            result={"main_character": "Test"},
            confidence=0.9
        )
        assert valid.is_valid() is True
        
        invalid_low_conf = AnalysisResult(
            entity_id="book_1",
            analysis_type="character",
            result={"main_character": "Test"},
            confidence=0.5  # < 0.8
        )
        assert invalid_low_conf.is_valid() is False
        
        error = AnalysisResult(
            entity_id="book_1",
            analysis_type="character",
            result={},
            error="Analysis failed"
        )
        assert error.is_valid() is False
    
    def test_to_from_dict(self):
        """Конвертация в dict и обратно."""
        original = AnalysisResult(
            entity_id="book_1",
            analysis_type="character",
            result={"main_character": "Test", "gender": "female"},
            confidence=0.9
        )
        
        data = original.to_dict()
        restored = AnalysisResult.from_dict(data)
        
        assert restored.entity_id == original.entity_id
        assert restored.analysis_type == original.analysis_type
        assert restored.result == original.result
    
    def test_confidence_validation(self):
        """Валидация confidence."""
        with pytest.raises(ValueError):
            AnalysisResult(
                entity_id="book_1",
                analysis_type="character",
                result={},
                confidence=1.5  # > 1.0
            )
        
        with pytest.raises(ValueError):
            AnalysisResult(
                entity_id="book_1",
                analysis_type="character",
                result={},
                confidence=-0.1  # < 0.0
            )
    
    def test_universal_analysis_type(self):
        """Тест: любой тип анализа работает."""
        # character анализ
        char_analysis = AnalysisResult(
            entity_id="book_1",
            analysis_type="character",
            result={"main_character": "Test"}
        )
        assert char_analysis.analysis_type == "character"
        
        # theme анализ
        theme_analysis = AnalysisResult(
            entity_id="doc_1",
            analysis_type="theme",
            result={"themes": ["love", "war"]}
        )
        assert theme_analysis.analysis_type == "theme"
        
        # category анализ
        cat_analysis = AnalysisResult(
            entity_id="kb_1",
            analysis_type="category",
            result={"category": "technical"}
        )
        assert cat_analysis.analysis_type == "category"


class TestBookWithCharacter:
    """Тесты BookWithCharacter."""
    
    def test_create_valid(self):
        """Создание валидной книги."""
        book = BookWithCharacter(
            book_id=1,
            book_title="Евгений Онегин",
            author_name="Александр Пушкин",
            main_character="Евгений Онегин",
            gender="male",
            confidence=0.95
        )
        assert book.book_title == "Евгений Онегин"
        assert book.gender == "male"
    
    def test_main_character_optional(self):
        """main_character опционален."""
        book = BookWithCharacter(
            book_id=1,
            book_title="Test Book",
            author_name="Test Author",
            main_character=None,
            gender=None,
            confidence=0.5
        )
        assert book.main_character is None
