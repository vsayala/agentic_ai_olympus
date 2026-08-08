from __future__ import annotations

import asyncio
import time

import streamlit as st

from olympus_copilot_sdk.evaluation.comparison import EvaluationRecord, record_vector_result
from olympus_copilot_sdk.ui.common import (
    DATA_DIRECTORY,
    DEFAULT_MODEL,
    apply_theme,
    available_model_options,
    evaluation_records,
    vector_index,
    vector_usage,
)
from olympus_copilot_sdk.vector_db_02.agents import Stage, VectorOrchestrator

_STAGE_LABELS: dict[Stage, str] = {
    "zeus_thinking": "Zeus is thinking",
    "delegating": "Zeus is delegating",
    "hercules_working": "Hercules is searching the hybrid index",
    "hercules_done": "Hercules returned evidence",
    "zeus_final": "Zeus is synthesizing",
}


def render_chat_page() -> None:
    apply_theme()
    records = evaluation_records()
    model, input_price, output_price = _sidebar(records)
    st.markdown('<div class="olympus-title">Olympus</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="olympus-subtitle">Milvus Lite semantic retrieval with Zeus and Hercules. '
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

    if prompt := st.chat_input("Ask Zeus about the files in data/"):
        orchestrator = VectorOrchestrator(
            DATA_DIRECTORY,
            model,
            input_price,
            output_price,
            index=vector_index(),
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
            except Exception as error:
                status.update(label="Vector request failed", state="error", expanded=True)
                st.error(f"The vector agent could not complete the request: {error}")
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


def _sidebar(records: list[EvaluationRecord]) -> tuple[str, float, float]:
    usage = vector_usage(records)
    with st.sidebar:
        st.subheader("Vector chatbot")
        try:
            options = available_model_options()
        except Exception as error:
            st.warning(f"Could not load model catalog: {error}")
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
        st.caption(f"02_Vector_DB: {vector_index().summary.chunk_count} semantic chunks")
    return model, input_price, output_price
