from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from typing import cast

import streamlit as st

from olympus_copilot_sdk.evaluation.comparison import (
    ApproachEvaluation,
    EvaluationRecord,
    Preference,
    run_knowledge_baseline,
)
from olympus_copilot_sdk.evaluation.metrics import ResponseMetrics
from olympus_copilot_sdk.knowledge_01.agents import KnowledgeOrchestrator, Stage
from olympus_copilot_sdk.ui.common import DATA_DIRECTORY, apply_theme, evaluation_records

logger = logging.getLogger(__name__)
BASELINE_RUNNING_PREFIX = "olympus_baseline_running_"


def render_baseline_action(index: int) -> bool:
    running_key = f"{BASELINE_RUNNING_PREFIX}{index}"
    baseline_running = bool(st.session_state.get(running_key, False))
    return (
        st.button(
            "Run 01_Knowledge baseline",
            key=f"baseline_{index}",
            disabled=baseline_running,
        )
        and not baseline_running
    )


def render_evaluation_page(go_back: Callable[[], None]) -> None:
    apply_theme()
    if st.button("Back to chatbot", icon=":material/arrow_back:"):
        go_back()
    st.markdown('<div class="olympus-title">Evaluation</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="olympus-subtitle">Run the isolated 01_Knowledge baseline only when needed, '
        "using the exact prompt and model from a vector chat turn.</div>",
        unsafe_allow_html=True,
    )
    records = evaluation_records()
    if not records:
        st.info("Ask a question in Chatbot to create a vector result for evaluation.")
        return
    completed = [record for record in records if record.lexical is not None]
    _render_summary(completed)
    for index, record in reversed(list(enumerate(records))):
        with st.expander(record.query, expanded=index == len(records) - 1):
            _render_record(records, index, record)


def _render_record(records: list[EvaluationRecord], index: int, record: EvaluationRecord) -> None:
    if record.lexical is None:
        _metric_panel("02_Vector_DB", record.vector.metrics)
        st.markdown(record.vector.result.response)
        st.info("01_Knowledge has not been run. No baseline tokens have been spent.")
        running_key = f"{BASELINE_RUNNING_PREFIX}{index}"
        if render_baseline_action(index):
            st.session_state[running_key] = True
            orchestrator = KnowledgeOrchestrator(
                DATA_DIRECTORY,
                record.model,
                record.input_price,
                record.output_price,
            )
            status = st.status("Running isolated lexical baseline", expanded=True)

            def show_stage(stage: Stage, detail: str) -> None:
                status.update(label=f"01_Knowledge: {stage}")
                status.write(detail)

            try:
                records[index] = asyncio.run(
                    run_knowledge_baseline(record, orchestrator, show_stage)
                )
            except Exception:
                logger.exception("Knowledge baseline failed")
                status.update(label="Baseline failed", state="error", expanded=True)
                st.error("The baseline could not complete. Check the launcher logs and retry.")
            else:
                status.update(label="Baseline complete", state="complete", expanded=False)
                st.rerun()
            finally:
                st.session_state[running_key] = False
        return

    lexical_column, vector_column = st.columns(2)
    with lexical_column:
        _approach_panel("01_Knowledge", record.lexical)
    with vector_column:
        _approach_panel("02_Vector_DB", record.vector)
    overlap = record.source_overlap_ratio
    st.caption(
        f"Fewer tokens: {record.lower_usage_approach} · "
        f"Higher quality proxy: {record.higher_quality_approach} · "
        f"Source overlap: {overlap:.0%}"
    )
    selected = st.segmented_control(
        "Which response is more useful?",
        ["01_Knowledge", "02_Vector_DB", "Tie"],
        default=record.preference,
        key=f"preference_{index}",
    )
    if selected is not None and selected != record.preference:
        records[index] = replace(record, preference=cast(Preference, selected))
        st.rerun()


def _render_summary(records: list[EvaluationRecord]) -> None:
    st.subheader("Completed baseline comparisons")
    st.metric("Compared prompts", len(records))
    if not records:
        st.caption("No baseline has been run yet.")
        return
    lexical_tokens = sum(
        cast(ApproachEvaluation, item.lexical).metrics.total_tokens for item in records
    )
    vector_tokens = sum(item.vector.metrics.total_tokens for item in records)
    first, second = st.columns(2)
    first.metric("01_Knowledge tokens", f"{lexical_tokens:,}")
    second.metric("02_Vector_DB tokens", f"{vector_tokens:,}")


def _approach_panel(name: str, approach: ApproachEvaluation) -> None:
    _metric_panel(name, approach.metrics)
    st.markdown(approach.result.response)
    if approach.result.sources:
        st.caption("Sources: " + ", ".join(approach.result.sources))


def _metric_panel(name: str, values: ResponseMetrics) -> None:
    st.subheader(name)
    st.metric("Quality proxy", f"{values.quality_score:.1f}/100")
    first, second, third = st.columns(3)
    first.metric("Tokens", f"{values.total_tokens:,}")
    second.metric("Latency", f"{values.latency_seconds:.2f}s")
    third.metric("Cost", f"${values.cost:.6f}")
    st.caption(
        f"Citation validity {values.valid_citation_ratio:.0%} · "
        f"source coverage {values.source_coverage_ratio:.0%} · "
        f"grounded sentences {values.grounded_sentence_ratio:.0%}"
    )
    if values.evidence_topic_completeness is not None:
        st.caption(
            "Broad evidence-topic citation completeness "
            f"{values.evidence_topic_completeness:.0%} (reported separately from quality)"
        )
