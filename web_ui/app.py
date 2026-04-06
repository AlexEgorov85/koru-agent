"""
Веб-интерфейс агента в стиле Qwen/DeepSeek — тёмная минималистичная тема.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from core.agent.factory import AgentFactory
from web_ui.agent_holder import get_status, is_ready, get_app_context, get_logs, clear_logs, get_shared_dialogue_history, reset_dialogue_history

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
/* Light theme -统一的字体 */
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

        with st.chat_message(role):
            st.markdown(content)
            if duration > 0:
                st.caption(f"{duration} мс")

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

    # Поле ввода как в классических LLM-чатах
    if is_ready():
        if prompt := st.chat_input("Введите ваш вопрос...", max_chars=2000):
            # Сохраняем вопрос в session_state для обработки
            st.session_state.pending_question = prompt
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

            with st.spinner("Думаю..."):
                start = time.time()
                app_ctx = get_app_context()
                factory = AgentFactory(app_ctx)
                
                # Получаем общую историю диалога (сохраняется между запросами)
                shared_dialogue_history = get_shared_dialogue_history()

                async def run():
                    # Новый SessionContext, но с копией истории диалога
                    agent = await factory.create_agent(goal=pending, dialogue_history=shared_dialogue_history)
                    return await agent.run(pending)

                result = asyncio.run(run())
                duration_ms = int((time.time() - start) * 1000)

            st.session_state.last_request_time = time.time()

            # Извлечение ответа
            if hasattr(result, "data") and result.data:
                if isinstance(result.data, dict):
                    answer = result.data.get("final_answer", str(result.data))
                else:
                    answer = str(result.data)
            else:
                answer = str(result)

            # Добавляем ответ агента
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "duration_ms": duration_ms
            })

            if result.error:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"**Ошибка:** {result.error}",
                    "duration_ms": 0
                })

            # Логи (кратко)
            logs = get_logs()
            if logs:
                log_text = "\n".join([log.get("message", "") for log in logs[-10:] if log.get("message")])
                if log_text:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"```\n{log_text}\n```",
                        "duration_ms": 0
                    })

            st.rerun()
    else:
        st.info("Система не инициализирована — перейдите в Управление")

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
        with st.expander("🤖 **LLM Провайдеры**", expanded=True):
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
        with st.expander("💾 **Базы данных**", expanded=True):
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
        with st.expander("🔧 **Сервисы**", expanded=True):
            if sys_info.get("services"):
                for s in sys_info["services"]:
                    render_component_card(s, "#e3f2fd")
            else:
                st.write("Не определены")

        # Навыки
        with st.expander("🧠 **Навыки (Skills)**", expanded=True):
            if sys_info.get("skills"):
                # Скрываем meta_component_creator
                filtered_skills = [s for s in sys_info["skills"] if s.get("name") != "meta_component_creator"]
                for s in filtered_skills:
                    render_component_card(s, "#fce4ec")
            else:
                st.write("Не определены")

        # Инструменты
        with st.expander("🔨 **Инструменты (Tools)**", expanded=True):
            if sys_info.get("tools"):
                for t in sys_info["tools"]:
                    render_component_card(t, "#e8f5e9")
            else:
                st.write("Не определены")

        # Паттерны
        with st.expander("🎯 **Паттерны поведения**", expanded=True):
            if sys_info.get("patterns"):
                for p in sys_info["patterns"]:
                    render_component_card(p, "#f3e5f5")
            else:
                st.write("Не определены")

        if "error" in sys_info:
            st.error(f"Ошибка: {sys_info['error']}")