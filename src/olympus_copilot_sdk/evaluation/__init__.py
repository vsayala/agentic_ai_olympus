"""Local, model-free evaluation for retrieval comparisons."""

from olympus_copilot_sdk.evaluation.comparison import (
    EvaluationRecord,
    record_vector_result,
    run_knowledge_baseline,
)
from olympus_copilot_sdk.evaluation.metrics import ResponseMetrics, evaluate_response

__all__ = [
    "EvaluationRecord",
    "ResponseMetrics",
    "evaluate_response",
    "record_vector_result",
    "run_knowledge_baseline",
]
