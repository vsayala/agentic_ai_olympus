from __future__ import annotations

import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from time import perf_counter


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s", force=True)


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, default=str, sort_keys=True))


@contextmanager
def job_run(logger: logging.Logger, job: str, source: str) -> Generator[None]:
    started = perf_counter()
    log_event(logger, "job_started", job=job, source=source)
    try:
        yield
    except Exception:
        logger.exception(
            json.dumps({"event": "job_failed", "job": job, "source": source}, sort_keys=True)
        )
        raise
    else:
        log_event(
            logger,
            "job_completed",
            job=job,
            source=source,
            duration_seconds=round(perf_counter() - started, 3),
        )
