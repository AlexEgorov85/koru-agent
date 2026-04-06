"""
Страница запуска агента — использует глобальный app_ctx из agent_holder.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from core.agent.factory import AgentFactory
from web_ui.agent_holder import get_status, is_ready, get_app_context

st.set_page_config(page_title="Агент", page_icon="🤖")

st.sidebar.title("Навигация")
page = st.sidebar.radio("Страница:", ["🤖 Агент", "⚙️ Админка"], index=0)

if page == "⚙️ Админка":
    import pages.Админка
    st.stop()

st.title("🤖 Агент")

status = get_status()

if status["app_ready"]:
    st.success("✅ Контекст поднят")
else:
    st.warning("⚠️ Контекст не поднят — перейдите в Админку")

if is_ready():
    with st.form("run_form"):
        goal = st.text_area(
            "Ваш вопрос:",
            height=150,
            placeholder="Какие есть книги в библиотеке?"
        )

        col1, col2 = st.columns(2)
        with col1:
            max_steps = st.slider("Шагов", 1, 50, 10)
        with col2:
            temperature = st.slider("Температура", 0.0, 1.0, 0.3)

        submit = st.form_submit_button("🚀 Отправить", type="primary")

    if submit and goal:
        import asyncio

        with st.spinner("Агент работает..."):
            start = time.time()

            app_ctx = get_app_context()
            factory = AgentFactory(app_ctx)

            async def run():
                agent = await factory.create_agent(goal=goal)
                return await agent.run(goal)

            result = asyncio.run(run())

            duration_ms = int((time.time() - start) * 1000)

        st.success(f"Готово за {duration_ms} мс")

        if hasattr(result, "data") and result.data:
            if isinstance(result.data, dict):
                answer = result.data.get("final_answer", str(result.data))
            else:
                answer = str(result.data)
        else:
            answer = str(result)

        st.write("### Ответ")
        st.write(answer)

        with st.expander("Детали"):
            steps = result.metadata.get("total_steps", 0) if result.metadata else 0
            st.write(f"Шагов: {steps}")
            if result.error:
                st.error(f"Ошибка: {result.error}")
else:
    st.info("Поднимите контекст в разделе Админка")