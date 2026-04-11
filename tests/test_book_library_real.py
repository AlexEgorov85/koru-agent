#!/usr/bin/env python3
"""
Реальный тест BookLibrarySkill с правильной инициализацией session_context.
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config import get_config
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.config.app_config import AppConfig
from core.session_context.session_context import SessionContext
from core.agent.components.action_executor import ExecutionContext
from core.models.data.capability import Capability


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.success = False
        self.error = None
        self.duration_ms = 0
        self.data = None
    
    def __str__(self):
        status = "✅ PASS" if self.success else "❌ FAIL"
        return f"{status} {self.name} ({self.duration_ms:.0f}ms)"


class BookLibraryRealTest:
    def __init__(self, profile: str = "dev"):
        self.profile = profile
        self.infra = None
        self.app_context = None
        self.skill = None
        self.session_context = None
        self.results: List[TestResult] = []
    
    async def initialize(self):
        
        # 1. Загрузка конфигурации
        config = get_config(profile=self.profile, data_dir='data')
        
        # 2. InfrastructureContext
        infra_start = time.perf_counter()
        self.infra = InfrastructureContext(config)
        await self.infra.initialize()
        infra_time = (time.perf_counter() - infra_start) * 1000
        
        # 3. ApplicationContext
        app_start = time.perf_counter()
        self.app_context = ApplicationContext(
            infrastructure_context=self.infra,
            config=AppConfig.from_discovery(
                profile=self.profile,
                data_dir='data'
            ),
            profile=self.profile
        )
        await self.app_context.initialize()
        app_time = (time.perf_counter() - app_start) * 1000
        
        # 4. ⚠️ КРИТИЧНО: Создание session_context
        self.session_context = SessionContext(session_id=str(self.infra.id))
        self.session_context.set_goal("Тестирование BookLibrarySkill")
        self.app_context.session_context = self.session_context
        
        # 5. Получение навыка
        self.skill = self.app_context.get_skill("book_library")
        if not self.skill:
            raise RuntimeError("BookLibrarySkill не найден!")
        await self.skill.initialize()

        capabilities = self.skill.get_capabilities()
        for cap in capabilities:
            pass  # Capabilities перечислены

    async def test_list_scripts(self) -> TestResult:
        result = TestResult("list_scripts")
        start = time.perf_counter()
        
        try:
            capability = Capability(
                name="book_library.list_scripts",
                description="Получение списка скриптов",
                skill_name="book_library"
            )
            
            exec_context = ExecutionContext(
                session_context=self.session_context,
                available_capabilities=["book_library.list_scripts"]
            )
            
            response = await self.skill.execute(
                capability=capability,
                parameters={},
                execution_context=exec_context
            )
            
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.data = response.data if hasattr(response, 'data') else response
            
            if response.status.value == "completed":
                scripts = result.data.get('scripts', []) if isinstance(result.data, dict) else []
                if len(scripts) > 0:
                    result.success = True
                    for script in scripts[:3]:
                        pass  # Scripts перечислены
                else:
                    result.success = False
                    result.error = "Список скриптов пуст"
            else:
                result.success = False
                result.error = f"Статус: {response.status.value}"
            
        except Exception as e:
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.success = False
            result.error = str(e)
        
        self.results.append(result)
        return result
    
    async def test_execute_script_get_all_books(self) -> TestResult:
        result = TestResult("execute_script.get_all_books")
        start = time.perf_counter()
        
        try:
            capability = Capability(
                name="book_library.execute_script",
                description="Выполнение скрипта",
                skill_name="book_library"
            )
            
            exec_context = ExecutionContext(
                session_context=self.session_context,
                available_capabilities=["book_library.execute_script"]
            )
            
            response = await self.skill.execute(
                capability=capability,
                parameters={
                    "script_name": "get_all_books",
                    "parameters": {
                        "max_rows": 5
                    }
                },
                execution_context=exec_context
            )
            
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.data = response.data if hasattr(response, 'data') else response
            
            if response.status.value == "completed":
                rows = result.data.get('rows', []) if isinstance(result.data, dict) else []
                result.success = True
                for book in rows[:2]:
                    title = book.get('book_title', book.get('title', 'N/A'))
            else:
                result.success = False
                result.error = f"Статус: {response.status.value}, Error: {response.error}"
            
        except Exception as e:
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.success = False
            result.error = str(e)
        
        self.results.append(result)
        return result
    
    async def test_execute_script_get_books_by_author(self) -> TestResult:
        result = TestResult("execute_script.get_books_by_author")
        start = time.perf_counter()
        
        try:
            capability = Capability(
                name="book_library.execute_script",
                description="Выполнение скрипта",
                skill_name="book_library"
            )
            
            exec_context = ExecutionContext(
                session_context=self.session_context,
                available_capabilities=["book_library.execute_script"]
            )
            
            response = await self.skill.execute(
                capability=capability,
                parameters={
                    "script_name": "get_books_by_author",
                    "parameters": {
                        "author": "Толстой",
                        "max_rows": 3
                    }
                },
                execution_context=exec_context
            )
            
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.data = response.data if hasattr(response, 'data') else response
            
            if response.status.value == "completed":
                rows = result.data.get('rows', []) if isinstance(result.data, dict) else []
                result.success = True
                for book in rows[:2]:
                    title = book.get('book_title', book.get('title', 'N/A'))
            else:
                result.success = False
                result.error = f"Статус: {response.status.value}, Error: {response.error}"
            
        except Exception as e:
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.success = False
            result.error = str(e)
        
        self.results.append(result)
        return result
    
    async def test_search_books_dynamic(self) -> TestResult:
        result = TestResult("search_books.dynamic")
        start = time.perf_counter()
        
        try:
            capability = Capability(
                name="book_library.search_books",
                description="Динамический поиск книг",
                skill_name="book_library"
            )
            
            exec_context = ExecutionContext(
                session_context=self.session_context,
                available_capabilities=["book_library.search_books"]
            )
            
            response = await self.skill.execute(
                capability=capability,
                parameters={
                    "query": "Найти книги Льва Толстого",
                    "max_results": 5
                },
                execution_context=exec_context
            )
            
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.data = response.data if hasattr(response, 'data') else response
            
            if response.status.value == "completed":
                rows = result.data.get('rows', []) if isinstance(result.data, dict) else []
                exec_type = result.data.get('execution_type', 'unknown')
                result.success = True
                for book in rows[:2]:
                    title = book.get('book_title', book.get('title', 'N/A'))
            else:
                result.success = False
                result.error = f"Статус: {response.status.value}, Error: {response.error}"
            
        except Exception as e:
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.success = False
            result.error = str(e)
        
        self.results.append(result)
        return result
    
    async def test_semantic_search(self) -> TestResult:
        result = TestResult("semantic_search")
        start = time.perf_counter()
        
        try:
            capability = Capability(
                name="book_library.semantic_search",
                description="Семантический поиск",
                skill_name="book_library"
            )
            
            exec_context = ExecutionContext(
                session_context=self.session_context,
                available_capabilities=["book_library.semantic_search"]
            )
            
            # Проверка готовности Vector Search
            if not self.infra.is_vector_search_ready('books'):
                result.success = False
                result.error = "Vector Search не готов (индексы не созданы)"
                self.results.append(result)
                return result
            
            response = await self.skill.execute(
                capability=capability,
                parameters={
                    "query": "книги о войне и мире",
                    "top_k": 5,
                    "min_score": 0.5
                },
                execution_context=exec_context
            )
            
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.data = response.data if hasattr(response, 'data') else response
            
            if response.status.value == "completed":
                results_list = result.data.get('results', []) if isinstance(result.data, dict) else []
                search_type = result.data.get('search_type', 'unknown')
                result.success = True
                for res in results_list[:2]:
                    content = res.get('content', 'N/A')
            else:
                result.success = False
                result.error = f"Статус: {response.status.value}, Error: {response.error}"
            
        except Exception as e:
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.success = False
            result.error = str(e)
        
        self.results.append(result)
        return result
    
    async def run_all_tests(self):
        
        await self.test_list_scripts()
        await self.test_execute_script_get_all_books()
        await self.test_execute_script_get_books_by_author()
        await self.test_search_books_dynamic()
        await self.test_semantic_search()
        
        self.print_report()
    
    def print_report(self):
        
        passed = sum(1 for r in self.results if r.success)
        failed = len(self.results) - passed
        total_time = sum(r.duration_ms for r in self.results)

        failed = sum(1 for r in self.results if not r.success)

        for result in self.results:
            if result.error:
                pass  # Errors logged

        if failed == 0:
            print(f"✅ All tests passed ({total_time:.0f}ms)")
        else:
            print(f"❌ {failed} tests failed")

    async def shutdown(self):
        if self.app_context:
            await self.app_context.shutdown()
        if self.infra:
            await self.infra.shutdown()


async def main():
    test = BookLibraryRealTest(profile="dev")
    
    try:
        await test.initialize()
        await test.run_all_tests()
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await test.shutdown()


if __name__ == "__main__":
    asyncio.run(main())