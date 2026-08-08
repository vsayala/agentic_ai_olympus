from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import cast

import streamlit as st

from olympus_copilot_sdk.evaluation.comparison import EvaluationRecord
from olympus_copilot_sdk.vector_db_02.agents import Usage, list_available_models
from olympus_copilot_sdk.vector_db_02.milvus import VectorKnowledgeBase
from olympus_copilot_sdk.vector_db_02.retrieval import IndexSummary

ROOT = Path(__file__).parents[3]
DATA_DIRECTORY = ROOT / "data"
DEFAULT_MODEL = os.getenv("COPILOT_MODEL", "gpt-5-mini")
RECORDS_KEY = "evaluation_records"


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f6f3ea; color: #1c2526; }
        [data-testid="stSidebar"] { background: #162c2a; color: #f7f1df; }
        [data-testid="stSidebar"] * { color: #f7f1df; }
        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"],
        [data-testid="stSidebar"] [data-testid="stNumberInputContainer"],
        [data-testid="stSidebar"] .stButton > button,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary {
            background-color: #2f6f5e !important; border-color: #7fc6a4 !important;
            color: #f7f1df !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover,
        [data-testid="stSidebar"] .stButton > button:active,
        [data-testid="stSidebar"] .stButton > button:focus-visible,
        [data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"]:focus-within,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover,
        [data-testid="stSidebar"] [data-testid="stExpander"] summary:focus-visible {
            background-color: #245648 !important; border-color: #a6dfbe !important;
        }
        .olympus-title { color: #bd4b31; font-family: Georgia, serif; font-size: 2.2rem;
            font-weight: 700; }
        .olympus-subtitle { color: #52605e; margin-bottom: 1.25rem; }
        .stChatMessage { border-left: 3px solid #d1a54b; background: rgba(255,255,255,.5); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def evaluation_records() -> list[EvaluationRecord]:
    if RECORDS_KEY not in st.session_state:
        st.session_state[RECORDS_KEY] = []
    return cast(list[EvaluationRecord], st.session_state[RECORDS_KEY])


@st.cache_resource(show_spinner=False)
def vector_index() -> VectorKnowledgeBase:
    return VectorKnowledgeBase(DATA_DIRECTORY)


@st.cache_data(ttl=300, show_spinner=False)
def available_model_options() -> tuple[tuple[str, str], ...]:
    return tuple(asyncio.run(list_available_models(ROOT)))


def vector_usage(records: list[EvaluationRecord]) -> Usage:
    usage = Usage(model=DEFAULT_MODEL)
    for record in records:
        current = record.vector.result.usage
        usage.input_tokens += current.input_tokens
        usage.output_tokens += current.output_tokens
        usage.cost += current.cost
        usage.calls += current.calls
        usage.model = current.model or usage.model
        usage.has_sdk_cost = usage.has_sdk_cost or current.has_sdk_cost
    return usage


def data_folder_inventory(summary: IndexSummary) -> tuple[str, ...]:
    readable = ((source, "Read") for source in summary.indexed_files)
    unsupported = ((source, "Unsupported") for source in summary.skipped_files)
    return tuple(f"{status}: {source}" for source, status in sorted((*readable, *unsupported)))
