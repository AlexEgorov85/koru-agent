"""
Админка — управление контекстами: поднятие, остановка, статус.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from web_ui.agent_holder import (
    get_status, init_contexts, shutdown_contexts, is_ready
)

st.set_page_config(page_title="Админка", page_icon="⚙️")

st.title("⚙️ Админка")

st.write("### Статус")
status = get_status()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Infra", "✅" if status["infra_ready"] else "❌")
with col2:
    st.metric("App", "✅" if status["app_ready"] else "❌")
with col3:
    st.metric("Готов", "Да" if status["is_ready"] else "Нет")

st.write("### Управление")

col_up, col_down = st.columns(2)

with col_up:
    with st.form("init_form"):
        st.write("Поднять контекст")
        data_dir = st.text_input("Путь к данным", value="data")
        submit_init = st.form_submit_button("🚀 Поднять", type="primary")

        if submit_init:
            with st.spinner("Поднимаю контекст..."):
                asyncio.run(init_contexts(profile="prod", data_dir=data_dir))
            st.success("Контекст поднят!")
            st.rerun()

with col_down:
    if is_ready():
        if st.button("🛑 Остановить", type="primary"):
            with st.spinner("Останавливаю..."):
                asyncio.run(shutdown_contexts())
            st.success("Контекст остановлен")
            st.rerun()
    else:
        st.write("Контекст не поднят")

if is_ready():
    st.write("### Информация")
    st.write("Контекст готов к работе")