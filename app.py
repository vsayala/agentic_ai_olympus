from __future__ import annotations

import streamlit as st

from olympus_copilot_sdk.ui.chat_page import render_chat_page
from olympus_copilot_sdk.ui.evaluation_page import render_evaluation_page

st.set_page_config(page_title="Olympus", page_icon="⚡", layout="wide")

chatbot_page = st.Page(
    render_chat_page,
    title="Chatbot",
    icon=":material/chat:",
    default=True,
)


def render_evaluation_route() -> None:
    render_evaluation_page(lambda: st.switch_page(chatbot_page))


evaluation_page = st.Page(
    render_evaluation_route,
    title="Evaluation",
    icon=":material/analytics:",
)

navigation = st.navigation([chatbot_page, evaluation_page], position="sidebar")
navigation.run()
