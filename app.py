from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

import streamlit as st

from olympus_copilot_sdk.agents import (
    OlympusOrchestrator,
    Stage,
    Usage,
    list_available_models,
)

ROOT = Path(__file__).parent
DATA_DIRECTORY = ROOT / "data"
DEFAULT_MODEL = os.getenv("COPILOT_MODEL", "gpt-5-mini")

st.set_page_config(page_title="Olympus", page_icon="⚡", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #f6f3ea; color: #1c2526; }
    [data-testid="stSidebar"] { background: #162c2a; color: #f7f1df; }
    [data-testid="stSidebar"] * { color: #f7f1df; }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"],
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"] {
        background-color: #2f6f5e !important;
        border-color: #7fc6a4 !important;
    }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] input[role="combobox"],
    [data-testid="stSidebar"] [data-baseweb="select"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    [data-testid="stSidebar"] [data-testid="stSelectbox"] svg,
    [data-testid="stSidebar"] [data-baseweb="select"] svg {
        fill: #ffffff !important;
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInputContainer"] {
        background-color: #2f6f5e !important;
        border-color: #7fc6a4 !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInputField"] {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInputContainer"] button,
    [data-testid="stSidebar"] [data-testid="stNumberInputContainer"] svg {
        color: #ffffff !important;
        fill: #ffffff !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background-color: #2f6f5e !important;
        border-color: #7fc6a4 !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover,
    [data-testid="stSidebar"] .stButton > button:focus {
        background-color: #3f806e !important;
        border-color: #a4dbc1 !important;
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stButton > button * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    .agent-mark { color: #bd4b31; font-family: Georgia, serif; font-size: 2.2rem;
        font-weight: 700; }
    .agent-subtitle { color: #52605e; margin-bottom: 1.5rem; }
    .stChatMessage { border-left: 3px solid #d1a54b; background: rgba(255,255,255,.5); }
    </style>
    """,
    unsafe_allow_html=True,
)


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str
    sources: NotRequired[list[str]]
    process: NotRequired[list[str]]


def _new_usage() -> Usage:
    return Usage(model=DEFAULT_MODEL)


@st.cache_data(ttl=300, show_spinner=False)
def _available_model_options() -> tuple[tuple[str, str], ...]:
    return tuple(asyncio.run(list_available_models(ROOT)))


if "messages" not in st.session_state:
    st.session_state["messages"] = cast(list[ChatMessage], [])
if "usage" not in st.session_state:
    st.session_state.usage = _new_usage()

messages = cast(list[ChatMessage], st.session_state.messages)
usage = cast(Usage, st.session_state.usage)

with st.sidebar:
    st.header("Session usage")
    try:
        model_options = _available_model_options()
    except Exception as error:
        st.warning(f"Could not load the Copilot model catalog: {error}")
        model_options = ((DEFAULT_MODEL, DEFAULT_MODEL),)
    if not model_options:
        model_options = ((DEFAULT_MODEL, DEFAULT_MODEL),)
    model_labels = dict(model_options)
    model_ids = list(model_labels)
    if DEFAULT_MODEL not in model_labels:
        model_ids.insert(0, DEFAULT_MODEL)
        model_labels[DEFAULT_MODEL] = DEFAULT_MODEL
    model = st.selectbox(
        "Copilot model",
        model_ids,
        index=model_ids.index(DEFAULT_MODEL),
        format_func=lambda model_id: model_labels[model_id],
    )
    st.caption(f"Usage model: {usage.model}")
    st.metric("Input tokens", f"{usage.input_tokens:,}")
    st.metric("Output tokens", f"{usage.output_tokens:,}")
    st.metric("Model calls", f"{usage.calls:,}")
    st.metric("Session cost", f"${usage.cost:.6f}")
    if usage.has_sdk_cost:
        st.caption("Cost reported by the Copilot SDK.")
    else:
        st.caption("Estimated from the fallback rates below.")
    with st.expander("Fallback pricing"):
        input_price = st.number_input("Input $ / 1M tokens", min_value=0.0, value=0.0, step=0.1)
        output_price = st.number_input("Output $ / 1M tokens", min_value=0.0, value=0.0, step=0.1)
    if st.button("Clear session", use_container_width=True):
        st.session_state.messages = []
        st.session_state.usage = _new_usage()
        st.rerun()

st.markdown('<div class="agent-mark">Olympus</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="agent-subtitle">Zeus orchestrates. Hercules grounds every answer in '
    "your data.</div>",
    unsafe_allow_html=True,
)

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        sources = message.get("sources")
        if sources:
            st.caption("Sources: " + ", ".join(sources))
        stored_process_trace = message.get("process")
        if stored_process_trace:
            with st.expander("Agent process"):
                for step in stored_process_trace:
                    st.markdown(step)

if prompt := st.chat_input("Ask Zeus about the files in data/"):
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    orchestrator = OlympusOrchestrator(DATA_DIRECTORY, model, input_price, output_price)
    with st.chat_message("assistant"):
        process = st.status("Talking to Zeus", expanded=True)
        process_trace: list[str] = []

        def show_stage(stage: Stage, detail: str) -> None:
            labels = {
                "zeus_thinking": "Zeus is thinking",
                "delegating": "Zeus is talking to Hercules",
                "hercules_working": "Hercules is searching the data",
                "hercules_done": "Hercules is responding to Zeus",
                "zeus_final": "Zeus is preparing the final response",
            }
            process_trace.append(f"**{labels[stage]}**\n\n{detail}")
            process.write(f"**{labels[stage]}**")
            process.write(detail)

        try:
            result = asyncio.run(orchestrator.answer(prompt, show_stage))
        except Exception as error:
            process.update(label="Request failed", state="error", expanded=True)
            st.error(f"Copilot could not complete the request: {error}")
        else:
            process.update(label="Zeus has answered", state="complete", expanded=False)
            st.markdown(result.response)
            if result.sources:
                st.caption("Sources: " + ", ".join(result.sources))
            messages.append(
                {
                    "role": "assistant",
                    "content": result.response,
                    "sources": result.sources,
                    "process": process_trace,
                }
            )
            usage.input_tokens += result.usage.input_tokens
            usage.output_tokens += result.usage.output_tokens
            usage.cost += result.usage.cost
            usage.calls += result.usage.calls
            usage.model = result.usage.model
            usage.has_sdk_cost = usage.has_sdk_cost or result.usage.has_sdk_cost
            st.rerun()

with st.sidebar:
    st.divider()
    preview = OlympusOrchestrator(DATA_DIRECTORY, model).knowledge.summary
    st.caption(f"{len(preview.indexed_files)} files · {preview.chunk_count} searchable chunks")
    with st.expander("Data inventory"):
        for source in preview.indexed_files:
            st.write(f"✓ {source}")
        for source in preview.skipped_files:
            st.write(f"– {source} (unsupported or empty)")