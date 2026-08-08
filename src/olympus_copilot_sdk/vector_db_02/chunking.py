from __future__ import annotations

import re
from dataclasses import dataclass

VECTOR_CHUNK_CHARACTERS = 800
VECTOR_CHUNK_OVERLAP = 120


@dataclass(frozen=True)
class VectorChunk:
    chunk_id: int
    source: str
    text: str


def make_vector_chunks(source: str, text: str, start_id: int = 0) -> list[VectorChunk]:
    normalized = re.sub(r"\s+", " ", text).strip()
    chunks: list[VectorChunk] = []
    start = 0
    while start < len(normalized):
        end = min(start + VECTOR_CHUNK_CHARACTERS, len(normalized))
        chunks.append(VectorChunk(start_id + len(chunks), source, normalized[start:end]))
        if end == len(normalized):
            break
        start = end - VECTOR_CHUNK_OVERLAP
    return chunks
