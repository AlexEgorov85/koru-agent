"""
Веб-интерфейс агента в стиле Qwen/DeepSeek — тёмная минималистичная тема.
"""

import sys
import os
import time
from pathlib import Path

# Добавляем корень проекта в путь
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st
from core.agent.factory import AgentFactory
from web_ui.agent_holder import get_status, is_ready, get_app_context, get_logs, clear_logs, get_shared_dialogue_history, reset_dialogue_history, get_agent_steps, set_agent_log_path, get_agent_log_path, populate_agent_steps

st.set_page_config(
    page_title="Агент",
    page_icon="🤖",
    layout="wide",
    menu_items={
        'Get help': None,
        'Report a bug': None,
        'About': None
    }
)

st.markdown("""
<style>
/* Light theme */
body, .stApp, p, li, div, span {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 15px;
    color: #1a1a1a;
}
#MainMenu {visibility: hidden !important;}
header {visibility: hidden !important;}
footer {visibility: hidden !important;}
header button[aria-label="Deploy"],
.stDeployButton {
    display: none !important;
}
.stTabs {
    border-bottom: 1px solid #e5e5e5;
}
.stTabs [data-testid="stTab"] {
    padding: 12px 24px;
    color: #666;
}
.stTextArea textarea, .stTextInput input {
    background: #ffffff !important;
    border: 1px solid #d1d1d1 !important;
    color: #1a1a1a !important;
    border-radius: 8px;
}
.stChatInputContainer {
    background: #ffffff !important;
    border: 1px solid #d1d1d1 !important;
    border-radius: 24px;
}
.stChatInputContainer input {
    color: #1a1a1a !important;
}
.stButton > button {
    background: #007AFF;
    color: white;
    border: none;
    border-radius: 8px;
}
h1, h2, h3 {
    color: #1a1a1a;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# Инициализация session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_request_time" not in st.session_state:
    st.session_state.last_request_time = 0
if "processing" not in st.session_state:
    st.session_state.processing = False

# Навигация через tabs
tab1, tab2 = st.tabs(["💬 Агент", "⚙️ Управление"])

# === TAB 1: АГЕНТ ===
with tab1:
    st.markdown("### 💬 Агент")

    status = get_status()

    if status["app_ready"]:
        st.success("Система готова")
    else:
        st.warning("Система не инициализирована — перейдите в Управление")

    # История сообщений (chat style)
    for msg in st.session_state.messages:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        duration = msg.get("duration_ms", 0)
        is_html = msg.get("is_html", False)

        avatar = "👨‍💻" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            if is_html:
                st.markdown(content, unsafe_allow_html=True)
            else:
                st.markdown(content)
            if duration > 0:
                # Форматируем время в удобный вид
                if duration >= 1000:
                    seconds = duration / 1000
                    time_str = f"{seconds:.1f} сек"
                else:
                    time_str = f"{duration} мс"
                st.caption(f"⏱️ {time_str}")

    # НОВОЕ: Отображение истории диалога из DialogueHistory
    if is_ready():
        dialogue_history = get_shared_dialogue_history()
        if dialogue_history.count() > 0:
            with st.expander("📜 История диалога", expanded=False):
                dialogue_text = dialogue_history.format_for_prompt()
                st.text(dialogue_text)
                
                # Кнопка очистки истории
                if st.button("🗑️ Очистить историю", key="clear_history_btn"):
                    reset_dialogue_history()
                    st.session_state.messages = []
                    st.rerun()

    # Placeholder для мыслей агента — ВВЕРХУ, перед полем ввода
    thinking_placeholder = st.empty()
    
    # Поле ввода как в классических LLM-чатах
    if is_ready():
        if prompt := st.chat_input("Введите ваш вопрос...", max_chars=2000, disabled=st.session_state.processing):
            # Сохраняем вопрос в session_state для обработки
            st.session_state.pending_question = prompt
            st.session_state.processing = True
            st.session_state.messages.append({
                "role": "user",
                "content": prompt,
                "duration_ms": 0
            })
            st.rerun()

        # Обработка ожидающего вопроса
        if "pending_question" in st.session_state and st.session_state.pending_question:
            pending = st.session_state.pending_question
            st.session_state.pending_question = None

            import asyncio
            clear_logs()

            # === НОВОЕ: Отображение мыслей агента в реальном времени ===
            start_time = time.time()
            
            # Функция для запуска агента в отдельном потоке
            import threading
            
            result_holder = [None]
            error_holder = [None]
            
            def run_agent_thread():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # Проверяем что контексты живы
                        if not is_ready():
                            error_holder[0] = RuntimeError("Система не инициализирована. Перейдите в Управление и нажмите 'Запустить систему'.")
                            return

                        app_ctx = get_app_context()
                        if app_ctx is None:
                            error_holder[0] = RuntimeError("Контекст приложения упал. Попробуйте перезапустить систему в Управлении.")
                            return

                        factory = AgentFactory(app_ctx)
                        shared_dialogue_history = get_shared_dialogue_history()

                        async def run():
                            agent = await factory.create_agent(goal=pending, dialogue_history=shared_dialogue_history)
                            # Устанавливаем путь к лог-файлу агента для UI
                            log_session = app_ctx.infrastructure_context.log_session
                            log_path = log_session.get_last_agent_log_path()
                            if log_path:
                                set_agent_log_path(log_path)
                            return await agent.run(pending)

                        result_holder[0] = loop.run_until_complete(run())
                    finally:
                        loop.close()
                except Exception as e:
                    error_holder[0] = e
            
            # Запускаем агента в отдельном потоке
            agent_thread = threading.Thread(target=run_agent_thread)
            agent_thread.start()
            
            # Пока агент работает - показываем мысли в реальном времени
            crash_detected = False

            while agent_thread.is_alive():
                # Проверяем что контексты живы
                if not is_ready():
                    crash_detected = True
                    break

                # Получаем свежие логи из файла (tail-режим)
                logs = get_logs()

                # Ищем последние сообщения для UI
                thinking_msg = None
                tool_call_msg = None
                decision_msg = None

                for log in reversed(logs):
                    evt = log.get("event_type", "")
                    # thinking — главный приоритет
                    if "THINKING" in evt and not thinking_msg:
                        thinking_msg = log.get("message", "")
                    # tool_call — показать если нет thinking
                    elif "TOOL_CALL" in evt and not tool_call_msg:
                        tool_call_msg = log.get("message", "")
                    # decision — показать если нет thinking/tool_call
                    elif "DECISION" in evt and not decision_msg:
                        decision_msg = log.get("message", "")

                # Формируем отображение: thinking > tool_call > decision
                display_msg = thinking_msg or tool_call_msg or decision_msg

                if display_msg:
                    # Формируем иконку по типу события
                    icon = "🤔"
                    if tool_call_msg and display_msg == tool_call_msg:
                        icon = "⚙️"
                    elif decision_msg and display_msg == decision_msg:
                        icon = "🧠"

                    thinking_placeholder.markdown(
                        f"<div style='background: #f0f0f0; color: #666666; padding: 12px 16px; border-radius: 8px; font-size: 14px;'>{icon} {display_msg}</div>",
                        unsafe_allow_html=True
                    )

                # Небольшая пауза чтобы UI успевал обновляться
                time.sleep(0.3)
            
            # Дожидаемся завершения
            agent_thread.join()

            # Заполняем шаги агента из лог-файла
            populate_agent_steps()

            # Очищаем контейнер мыслей
            thinking_placeholder.empty()
            
            # Проверяем на краш
            if crash_detected:
                st.session_state.processing = False
                st.error("⚠️ Система упала во время выполнения. Попробуйте перезапустить систему в Управлении.")
                st.rerun()
            
            # Проверяем результат
            if error_holder[0]:
                thinking_placeholder.empty()
                error_msg = str(error_holder[0])
                
                # Проверяем если это краш контекста
                if "connection" in error_msg.lower() or "closed" in error_msg.lower() or "context" in error_msg.lower():
                    st.session_state.processing = False
                    # Пробуем определить живы ли контексты
                    status = get_status()
                    if not status["is_ready"]:
                        st.error("⚠️ Контексты упали. Перейдите в Управление и перезапустите систему.")
                    else:
                        st.error(f"⚠️ Ошибка: {error_msg}")
                else:
                    st.error(f"⚠️ Ошибка: {error_msg}")
                
                st.rerun()
            
            result = result_holder[0]
            duration_ms = int((time.time() - start_time) * 1000)
            # === КОНЕЦ НОВОЕ ===

            st.session_state.last_request_time = time.time()

            # Извлечение ответа
            if hasattr(result, "data") and result.data:
                if isinstance(result.data, dict):
                    answer_data = result.data
                elif hasattr(result.data, "model_dump"):
                    # Pydantic v2
                    answer_data = result.data.model_dump()
                elif hasattr(result.data, "dict"):
                    # Pydantic v1
                    answer_data = result.data.dict()
                else:
                    answer_data = None
            else:
                answer_data = None

            # Формируем ответ: чистый текст + спойлер с деталями
            if answer_data and isinstance(answer_data, dict):
                final_answer = answer_data.get("final_answer", "")
                sources = answer_data.get("sources", [])
                confidence = answer_data.get("confidence_score")
                remaining = answer_data.get("remaining_questions", [])
                summary = answer_data.get("summary_of_steps", "")
                metadata = answer_data.get("metadata", {})

                # Основной ответ — чистый текст с выделением
                answer = final_answer if final_answer else str(result.data)
                
                # Выделяем ответ визуально
                answer = f"<div style='font-size: 16px; font-weight: 600; color: #1a1a1a; padding: 10px; background: #f5f5f5; border-radius: 8px; border-left: 4px solid #007AFF;'>{answer}</div>"

                # Получаем историю шагов агента
                agent_steps = get_agent_steps()

                # Формируем спойлер с деталями
                details_parts = []

                # Источники
                if sources:
                    if isinstance(sources, list):
                        sources_text = "\n".join(f"• {s}" for s in sources if s)
                    else:
                        sources_text = str(sources)
                    details_parts.append(f"### 📚 Источники\n{sources_text}")

                # Уверенность
                if confidence is not None:
                    conf_percent = int(confidence * 100)
                    conf_emoji = "✅" if confidence >= 0.8 else "⚠️" if confidence >= 0.5 else "❌"
                    details_parts.append(f"### {conf_emoji} Уверенность\n{conf_percent}%")

                # Оставшиеся вопросы
                if remaining:
                    remaining_text = "\n".join(f"• {q}" for q in remaining if q)
                    details_parts.append(f"### ❓ Требует уточнения\n{remaining_text}")

                # Как агент думал — пошагово
                if agent_steps:
                    steps_parts = []
                    for i, step in enumerate(agent_steps, 1):
                        step_type = step.get("type", "")
                        if step_type == "capability_selected":
                            capability = step.get("capability", "unknown")
                            reasoning = step.get("reasoning", "")
                            step_num = step.get("step", i)
                            steps_parts.append(f"**Шаг {step_num}** — Выбор действия\n- **Capability:** `{capability}`\n- **Обоснование:** {reasoning}")
                        elif step_type == "action_performed":
                            action = step.get("action", "unknown")
                            params = step.get("parameters", {})
                            status = step.get("status", "unknown")
                            error = step.get("error")
                            step_num = step.get("step", i)

                            params_text = ""
                            if params:
                                import json
                                params_text = f"\n- **Параметры:**\n```json\n{json.dumps(params, ensure_ascii=False, indent=2)}\n```"

                            error_text = f"\n- **Ошибка:** {error}" if error else ""
                            steps_parts.append(f"**Шаг {step_num}** — Выполнение\n- **Действие:** `{action}`\n- **Статус:** {status}{params_text}{error_text}")

                    if steps_parts:
                        steps_text = "\n\n".join(steps_parts)
                        details_parts.append(f"### 🧠 Ход мышления агента\n{steps_text}")

                # Собираем весь спойлер
                if details_parts:
                    details_content = "\n\n---\n\n".join(details_parts)
                    # Streamlit expандер — скрытый по умолчанию
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"<details>\n<summary><b>📊 Подробности ответа</b> (нажмите, чтобы развернуть)</summary>\n\n{details_content}\n\n</details>",
                        "duration_ms": 0,
                        "is_html": True
                    })
            else:
                # Fallback для нестандартных ответов
                answer = str(result.data) if result.data else str(result)

            # Добавляем ответ агента
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "duration_ms": duration_ms,
                "is_html": True
            })

            if result.error:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"**Ошибка:** {result.error}",
                    "duration_ms": 0
                })

            # Очищаем флаг обработки и контейнер мыслей
            st.session_state.processing = False
            thinking_placeholder.empty()

            # Технические логи больше не показываем пользователю

            st.rerun()

# === TAB 2: УПРАВЛЕНИЕ ===
with tab2:
    from web_ui.agent_holder import init_contexts, shutdown_contexts, get_system_info

    status = get_status()

    # Статус системы
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Infra", "✅" if status["infra_ready"] else "❌")
    with col2:
        st.metric("App", "✅" if status["app_ready"] else "❌")
    with col3:
        st.metric("Готов", "Да" if status["is_ready"] else "Нет")

    st.divider()

    # Кнопки управления
    col_start, col_stop = st.columns(2)

    with col_start:
        if st.button("🚀 Запустить систему", use_container_width=True, type="primary"):
            import asyncio
            with st.spinner("Инициализация..."):
                asyncio.run(init_contexts(profile="prod", data_dir="data"))
            st.success("Система запущена")
            # Переключаемся на вкладку Агент
            st.session_state.active_tab = 0
            st.rerun()

    with col_stop:
        if is_ready():
            if st.button("🛑 Остановить систему", use_container_width=True, type="secondary"):
                import asyncio
                with st.spinner("Остановка..."):
                    asyncio.run(shutdown_contexts())
                st.success("Система остановлена")
                st.rerun()
        else:
            st.write("Система не запущена")

    # Информация о системе (чек-ап)
    if is_ready():
        sys_info = get_system_info()

        # Унифицированная функция для отображения карточки компонента
        def render_component_card(comp, bg_color):
            """Отображение карточки компонента единым блоком."""
            name = comp.get("name", "unknown")
            desc = comp.get("description", "")
            status = comp.get("status", "unknown")
            caps = comp.get("capabilities", [])
            prompts = comp.get("prompts", [])
            contracts = comp.get("contracts", [])

            status_icon = "✅" if status == "initialized" else "⏳"
            
            html_parts = [f'<div style="padding: 15px; background: {bg_color}; border-radius: 12px; margin-bottom: 12px;">']
            html_parts.append(f'<div style="font-size: 16px; font-weight: bold; margin-bottom: 5px;">{status_icon} {name}</div>')
            
            if desc:
                html_parts.append(f'<div style="color: #555; font-size: 13px; margin-bottom: 10px;">{desc}</div>')
            
            # Capabilities - каждая на своей плитке
            if caps:
                html_parts.append('<div style="margin-top: 8px;"><strong>Capabilities:</strong></div>')
                for c in caps:
                    cap_name = c.get("name", "")
                    cap_desc = c.get("description", "")
                    
                    # Находим промпты и контракты для этой capability
                    cap_prompts = [p for p in prompts if p.get("capability", "").startswith(cap_name)]
                    cap_contracts = [c for c in contracts if c.get("capability", "").startswith(cap_name)]
                    
                    # Плитка capability
                    html_parts.append(f'<div style="margin: 5px 0; padding: 10px; background: rgba(255,255,255,0.7); border-radius: 8px; border-left: 3px solid #2196F3;">')
                    html_parts.append(f'<div style="font-weight: bold; font-size: 13px;">{cap_name}</div>')
                    if cap_desc:
                        html_parts.append(f'<div style="font-size: 12px; color: #666; margin-bottom: 5px;">{cap_desc}</div>')
                    
                    # Промпты и контракты под capability (в одну строку, справа налево)
                    if cap_prompts or cap_contracts:
                        html_parts.append('<div style="margin-top: 6px; display: flex; gap: 8px; flex-wrap: wrap;">')
                        
                        # Контракты (справа) - INPUT/OUTPUT
                        if cap_contracts:
                            input_contracts = [c for c in cap_contracts if c.get("direction") == "input"]
                            output_contracts = [c for c in cap_contracts if c.get("direction") == "output"]
                            
                            if output_contracts:
                                html_parts.append('<div style="padding: 4px 8px; background: #fff3e0; border-radius: 4px;">')
                                html_parts.append('<span style="font-size: 10px; font-weight: bold; color: #e65100; margin-right: 6px;">OUTPUT →</span>')
                                for c in output_contracts:
                                    stat = c.get("status", "unknown")
                                    status_icon = "🟢" if stat == "active" else "🔴" if stat == "inactive" else "🟡"
                                    html_parts.append(f'<span style="font-size: 11px; color: #333; margin-left: 6px;">{status_icon} {c["capability"].split(".")[-1]} <span style="color: #e65100; font-weight: bold;">{c["version"]}</span></span>')
                                html_parts.append('</div>')
                            
                            if input_contracts:
                                html_parts.append('<div style="padding: 4px 8px; background: #fff3e0; border-radius: 4px;">')
                                html_parts.append('<span style="font-size: 10px; font-weight: bold; color: #e65100; margin-right: 6px;">INPUT ←</span>')
                                for c in input_contracts:
                                    stat = c.get("status", "unknown")
                                    status_icon = "🟢" if stat == "active" else "🔴" if stat == "inactive" else "🟡"
                                    html_parts.append(f'<span style="font-size: 11px; color: #333; margin-left: 6px;">{status_icon} {c["capability"].split(".")[-1]} <span style="color: #e65100; font-weight: bold;">{c["version"]}</span></span>')
                                html_parts.append('</div>')
                        
                        # Промпты (слева от контрактов)
                        if cap_prompts:
                            html_parts.append('<div style="padding: 4px 8px; background: #e3f2fd; border-radius: 4px;">')
                            html_parts.append('<span style="font-size: 10px; font-weight: bold; color: #1565c0; margin-right: 6px;">PROMPTS</span>')
                            for p in cap_prompts:
                                stat = p.get("status", "unknown")
                                status_icon = "🟢" if stat == "active" else "🔴" if stat == "inactive" else "🟡"
                                html_parts.append(f'<span style="font-size: 11px; color: #333; margin-left: 6px;">{status_icon} {p["capability"].split(".")[-1]} <span style="color: #1565c0; font-weight: bold;">{p["version"]}</span></span>')
                            html_parts.append('</div>')
                        
                        html_parts.append('</div>')
                    
                    html_parts.append('</div>')
            
            # Если нет capabilities - показываем промпты и контракты в одну строку справа
            if not caps:
                html_parts.append('<div style="margin-top: 8px; display: flex; gap: 12px; flex-wrap: wrap;">')
                
                # Промпты (синий стиль)
                if prompts:
                    html_parts.append('<div style="padding: 4px 8px; background: #e3f2fd; border-radius: 4px;">')
                    html_parts.append('<span style="font-size: 10px; font-weight: bold; color: #1565c0;">PROMPTS</span>')
                    for p in prompts:
                        stat = p.get("status", "unknown")
                        status_icon = "🟢" if stat == "active" else "🔴" if stat == "inactive" else "🟡"
                        html_parts.append(f'<span style="font-size: 11px; color: #333; margin-left: 8px;">{status_icon} {p["capability"].split(".")[-1]} <span style="color: #1565c0; font-weight: bold;">{p["version"]}</span></span>')
                    html_parts.append('</div>')
                
                # Контракты (оранжевый стиль)
                if contracts:
                    input_contracts = [c for c in contracts if c.get("direction") == "input"]
                    output_contracts = [c for c in contracts if c.get("direction") == "output"]
                    
                    if input_contracts:
                        html_parts.append('<div style="padding: 4px 8px; background: #fff3e0; border-radius: 4px;">')
                        html_parts.append('<span style="font-size: 10px; font-weight: bold; color: #e65100;">INPUT ←</span>')
                        for c in input_contracts:
                            stat = c.get("status", "unknown")
                            status_icon = "🟢" if stat == "active" else "🔴" if stat == "inactive" else "🟡"
                            html_parts.append(f'<span style="font-size: 11px; color: #333; margin-left: 6px;">{status_icon} {c["capability"].split(".")[-1]} <span style="color: #e65100; font-weight: bold;">{c["version"]}</span></span>')
                        html_parts.append('</div>')
                    
                    if output_contracts:
                        html_parts.append('<div style="padding: 4px 8px; background: #fff3e0; border-radius: 4px;">')
                        html_parts.append('<span style="font-size: 10px; font-weight: bold; color: #e65100;">OUTPUT →</span>')
                        for c in output_contracts:
                            stat = c.get("status", "unknown")
                            status_icon = "🟢" if stat == "active" else "🔴" if stat == "inactive" else "🟡"
                            html_parts.append(f'<span style="font-size: 11px; color: #333; margin-left: 6px;">{status_icon} {c["capability"].split(".")[-1]} <span style="color: #e65100; font-weight: bold;">{c["version"]}</span></span>')
                        html_parts.append('</div>')
                
                html_parts.append('</div>')
            
            html_parts.append('</div>')
            
            st.markdown("\n".join(html_parts), unsafe_allow_html=True)

        # LLM провайдеры - отдельно
        with st.expander("🤖 **LLM Провайдеры**", expanded=False):
            if sys_info.get("llm_providers"):
                for p in sys_info["llm_providers"]:
                    desc = p.get("description", "")
                    name = p.get("name", "unknown")
                    status = p.get("status", "unknown")
                    status_icon = "✅" if status == "initialized" else "⏳"
                    
                    html = f'<div style="padding: 15px; background: #e8eaf6; border-radius: 12px; margin-bottom: 10px;">'
                    html += f'<div style="font-size: 16px; font-weight: bold;">{status_icon} {name}</div>'
                    if desc:
                        html += f'<div style="color: #555; font-size: 13px;">{desc}</div>'
                    html += '</div>'
                    st.markdown(html, unsafe_allow_html=True)
            else:
                st.write("Не найдены")

        # Базы данных - отдельно
        with st.expander("💾 **Базы данных**", expanded=False):
            if sys_info.get("db_providers"):
                for p in sys_info["db_providers"]:
                    desc = p.get("description", "")
                    name = p.get("name", "unknown")
                    status = p.get("status", "unknown")
                    status_icon = "✅" if status == "initialized" else "⏳"
                    
                    html = f'<div style="padding: 15px; background: #fce4ec; border-radius: 12px; margin-bottom: 10px;">'
                    html += f'<div style="font-size: 16px; font-weight: bold;">{status_icon} {name}</div>'
                    if desc:
                        html += f'<div style="color: #555; font-size: 13px;">{desc}</div>'
                    html += '</div>'
                    st.markdown(html, unsafe_allow_html=True)
            else:
                st.write("Не найдены")

        # Сервисы
        with st.expander("🔧 **Сервисы**", expanded=False):
            if sys_info.get("services"):
                for s in sys_info["services"]:
                    render_component_card(s, "#e3f2fd")
            else:
                st.write("Не определены")

        # Навыки
        with st.expander("🧠 **Навыки (Skills)**", expanded=False):
            if sys_info.get("skills"):
                # Скрываем meta_component_creator
                filtered_skills = [s for s in sys_info["skills"] if s.get("name") != "meta_component_creator"]
                for s in filtered_skills:
                    render_component_card(s, "#fce4ec")
            else:
                st.write("Не определены")

        # Инструменты
        with st.expander("🔨 **Инструменты (Tools)**", expanded=False):
            if sys_info.get("tools"):
                for t in sys_info["tools"]:
                    render_component_card(t, "#e8f5e9")
            else:
                st.write("Не определены")

        # Паттерны
        with st.expander("🎯 **Паттерны поведения**", expanded=False):
            if sys_info.get("patterns"):
                for p in sys_info["patterns"]:
                    render_component_card(p, "#f3e5f5")
            else:
                st.write("Не определены")

        if "error" in sys_info:
            st.error(f"Ошибка: {sys_info['error']}")