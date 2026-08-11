"""Local, model-free evaluation for retrieval comparisons."""

from olympus_copilot_sdk.evaluation.comparison import (
    EvaluationRecord,
    attach_baseline_result,
    record_vector_result,
)
from olympus_copilot_sdk.evaluation.metrics import ResponseMetrics, evaluate_response

__all__ = [
    "EvaluationRecord",
    "ResponseMetrics",
    "attach_baseline_result",
    "evaluate_response",
    "record_vector_result",
]
