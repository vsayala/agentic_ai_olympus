from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import streamlit as st

from olympus_copilot_sdk.evaluation.comparison import EvaluationRecord, record_vector_result
from olympus_copilot_sdk.ui.common import (
    DATA_DIRECTORY,
    DEFAULT_MODEL,
    SECONDARY_DATA_DIRECTORY,
    apply_theme,
    available_model_options,
    data_folder_inventory,
    evaluation_records,
    secondary_vector_index,
    vector_index,
    vector_usage,
)
from olympus_copilot_sdk.vector_db_02.agents import Stage, VectorOrchestrator

logger = logging.getLogger(__name__)
CHAT_RUNNING_KEY = "olympus_vector_request_running"

_STAGE_LABELS: dict[Stage, str] = {
    "zeus_thinking": "Zeus is thinking",
    "delegating": "Zeus is delegating",
    "hercules_working": "Hercules is searching the hybrid index",
    "hercules_done": "Hercules returned evidence",
    "hades_working": "Hades is searching the secondary corpus",
    "hades_done": "Hades returned evidence",
    "zeus_final": "Zeus is synthesizing",
}


@dataclass(frozen=True)
class PromptSuggestion:
    label: str
    prompt: str


PROMPT_SUGGESTIONS = (
    PromptSuggestion(
        "Summarize key policies",
        "Summarize the main policies in the data folder and cite the relevant sources.",
    ),
    PromptSuggestion(
        "Reporting concerns",
        "What does the Code of Conduct say about reporting concerns and speaking up?",
    ),
    PromptSuggestion(
        "Compare conduct policies",
        "Compare the conflicts of interest and anti-bribery policies, citing each source.",
    ),
)


def render_chat_page() -> None:
    apply_theme()
    records = evaluation_records()
    model, input_price, output_price = _sidebar(records)
    st.markdown('<div class="olympus-title">Olympus</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="olympus-subtitle">Zeus routes across the Hercules and Hades Milvus indexes. '
        "Run the legacy baseline only from Evaluation.</div>",
        unsafe_allow_html=True,
    )
    for record in records:
        with st.chat_message("user"):
            st.markdown(record.query)
        with st.chat_message("assistant"):
            st.markdown(record.vector.result.response)
            if record.vector.result.sources:
                st.caption("Sources: " + ", ".join(record.vector.result.sources))

    request_running = bool(st.session_state.get(CHAT_RUNNING_KEY, False))
    suggested_prompt = render_prompt_suggestions(disabled=request_running)
    typed_prompt = st.chat_input("Ask Zeus about the indexed files", disabled=request_running)
    if prompt := suggested_prompt or typed_prompt:
        if request_running:
            return
        st.session_state[CHAT_RUNNING_KEY] = True
        orchestrator = VectorOrchestrator(
            DATA_DIRECTORY,
            model,
            input_price,
            output_price,
            index=vector_index(),
            secondary_data_directory=SECONDARY_DATA_DIRECTORY,
            secondary_index=secondary_vector_index(),
        )
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            status = st.status("Running 02_Vector_DB", expanded=True)

            def show_stage(stage: Stage, detail: str) -> None:
                status.update(label=_STAGE_LABELS[stage])
                status.write(detail)

            start = time.perf_counter()
            try:
                result = asyncio.run(orchestrator.answer(prompt, show_stage))
            except Exception:
                logger.exception("Vector request failed")
                status.update(label="Vector request failed", state="error", expanded=True)
                st.error(
                    "The vector agent could not complete the request. Check the launcher logs "
                    "and retry."
                )
            else:
                records.append(
                    record_vector_result(
                        prompt,
                        result,
                        time.perf_counter() - start,
                        model,
                        input_price,
                        output_price,
                    )
                )
                status.update(label="Vector answer complete", state="complete", expanded=False)
                st.rerun()
            finally:
                st.session_state[CHAT_RUNNING_KEY] = False


def render_prompt_suggestions(*, disabled: bool = False) -> str | None:
    st.caption("Suggested questions")
    selected: str | None = None
    for column, suggestion in zip(st.columns(3), PROMPT_SUGGESTIONS, strict=True):
        if column.button(
            suggestion.label,
            key=f"prompt_suggestion_{suggestion.label}",
            help=suggestion.prompt,
            use_container_width=True,
            disabled=disabled,
        ):
            selected = suggestion.prompt
    return selected


def _sidebar(records: list[EvaluationRecord]) -> tuple[str, float, float]:
    usage = vector_usage(records)
    summary = vector_index().summary
    secondary_index = secondary_vector_index()
    secondary_summary = secondary_index.summary if secondary_index is not None else None
    with st.sidebar:
        st.subheader("Vector chatbot")
        try:
            options = available_model_options()
        except Exception:
            logger.exception("Could not load the Copilot model catalog")
            st.warning("Could not load the model catalog. Using the configured default model.")
            options = ((DEFAULT_MODEL, DEFAULT_MODEL),)
        labels = dict(options or ((DEFAULT_MODEL, DEFAULT_MODEL),))
        labels.setdefault(DEFAULT_MODEL, DEFAULT_MODEL)
        model_ids = list(labels)
        model = st.selectbox(
            "Copilot model",
            model_ids,
            index=model_ids.index(DEFAULT_MODEL),
            format_func=lambda model_id: labels[model_id],
        )
        with st.expander("Fallback pricing"):
            input_price = st.number_input("Input $ / 1M tokens", min_value=0.0, value=0.0)
            output_price = st.number_input("Output $ / 1M tokens", min_value=0.0, value=0.0)
        st.metric("Vector input tokens", f"{usage.input_tokens:,}")
        st.metric("Vector output tokens", f"{usage.output_tokens:,}")
        st.metric("Vector model calls", f"{usage.calls:,}")
        if st.button("Clear chat", use_container_width=True):
            records.clear()
            st.rerun()
        st.caption(f"Hercules index: {summary.chunk_count:,} semantic chunks")
        if secondary_summary is not None:
            st.caption(f"Hades index: {secondary_summary.chunk_count:,} semantic chunks")
        with st.expander(
            f"Data Folder ({len(summary.indexed_files)} read, "
            f"{len(summary.skipped_files)} unsupported)"
        ):
            inventory = data_folder_inventory(summary)
            if inventory:
                for item in inventory:
                    st.text(item)
            else:
                st.caption("No files found.")
    return model, input_price, output_price
