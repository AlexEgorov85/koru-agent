"""
Веб-интерфейс агента в стиле Qwen/DeepSeek — тёмная минималистичная тема.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from core.agent.factory import AgentFactory
from web_ui.agent_holder import get_status, is_ready, get_app_context, get_logs, clear_logs

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

            async def run():
                agent = await factory.create_agent(goal=pending)
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
        steps = result.metadata.get("total_steps", 0) if result.metadata else 0
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"**Ответ:** {answer}\n\n---\nШагов: {steps} | Время: {duration_ms} мс",
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
        st.info("Инициализируйте систему в разделе Управление")

# === TAB 2: УПРАВЛЕНИЕ ===
with tab2:
    from web_ui.agent_holder import init_contexts, shutdown_contexts

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

    if is_ready():
        st.divider()
        st.write("**Система готова к работе**")