from __future__ import annotations

import re
from dataclasses import dataclass, replace

VECTOR_CHUNK_CHARACTERS = 800
VECTOR_CHUNK_OVERLAP = 120
VECTOR_PARENT_TARGET_CHARACTERS = 2000
VECTOR_PARENT_MAX_CHARACTERS = 2400
VECTOR_CHUNKING_VERSION = "hierarchical-location-v2"

_PAGE_MARKER = re.compile(r"(?m)^Page\s+(\d+)\s*$")


@dataclass(frozen=True)
class VectorChunk:
    chunk_id: int
    source: str
    text: str
    page_label: str = ""
    section: str = ""
    parent_id: int = -1
    parent_text: str = ""

    @property
    def location(self) -> str:
        return self.section or self.page_label or f"chunk {self.chunk_id + 1}"

    @property
    def child_location(self) -> str:
        prefix = f"{self.page_label}, " if self.page_label else ""
        return f"{prefix}chunk {self.chunk_id + 1}"


def make_vector_chunks(source: str, text: str, start_id: int = 0) -> list[VectorChunk]:
    chunks: list[VectorChunk] = []
    for page_label, page_text in _located_pages(text):
        units = _semantic_units(page_text)
        current: list[str] = []
        for unit in units:
            if current and _joined_length((*current, unit)) > VECTOR_CHUNK_CHARACTERS:
                chunks.append(
                    VectorChunk(start_id + len(chunks), source, " ".join(current), page_label)
                )
                current = _overlap_units(current)
            if current and _joined_length((*current, unit)) > VECTOR_CHUNK_CHARACTERS:
                current = []
            current.append(unit)
        if current:
            chunks.append(
                VectorChunk(start_id + len(chunks), source, " ".join(current), page_label)
            )
    return _assign_parents(chunks)


def _located_pages(text: str) -> list[tuple[str, str]]:
    markers = list(_PAGE_MARKER.finditer(text))
    if not markers:
        return [("", text)]
    pages: list[tuple[str, str]] = []
    prefix = text[: markers[0].start()].strip()
    if prefix:
        pages.append(("", prefix))
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        pages.append((f"page {marker.group(1)}", text[marker.end() : end].strip()))
    return pages


def _assign_parents(chunks: list[VectorChunk]) -> list[VectorChunk]:
    assigned: list[VectorChunk] = []
    parent_id = 0
    start = 0
    while start < len(chunks):
        page_label = chunks[start].page_label
        end = start
        texts: list[str] = []
        while end < len(chunks) and chunks[end].page_label == page_label:
            candidate = (*texts, chunks[end].text)
            if texts and _joined_length(candidate) > VECTOR_PARENT_MAX_CHARACTERS:
                break
            texts.append(chunks[end].text)
            end += 1
            if _joined_length(texts) >= VECTOR_PARENT_TARGET_CHARACTERS:
                break
        parent_text = " ".join(texts)
        section = page_label
        page_chunk_count = sum(chunk.page_label == page_label for chunk in chunks)
        if page_chunk_count > len(texts):
            section = f"{page_label + ', ' if page_label else ''}section {parent_id + 1}"
        assigned.extend(
            replace(
                chunk,
                section=section,
                parent_id=parent_id,
                parent_text=parent_text,
            )
            for chunk in chunks[start:end]
        )
        parent_id += 1
        start = end
    return assigned


def _semantic_units(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n+", text)
    units: list[str] = []
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", " ", paragraph).strip()
        if not normalized:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", normalized):
            units.extend(_split_oversized_unit(sentence))
    return units


def _split_oversized_unit(text: str) -> list[str]:
    if len(text) <= VECTOR_CHUNK_CHARACTERS:
        return [text]
    pieces: list[str] = []
    current = ""
    for word in text.split():
        if len(word) > VECTOR_CHUNK_CHARACTERS:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(
                word[start : start + VECTOR_CHUNK_CHARACTERS]
                for start in range(0, len(word), VECTOR_CHUNK_CHARACTERS)
            )
        elif not current:
            current = word
        elif len(current) + len(word) + 1 <= VECTOR_CHUNK_CHARACTERS:
            current = f"{current} {word}"
        else:
            pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _overlap_units(units: list[str]) -> list[str]:
    overlap: list[str] = []
    for unit in reversed(units):
        if _joined_length((unit, *overlap)) > VECTOR_CHUNK_OVERLAP:
            break
        overlap.insert(0, unit)
    return overlap


def _joined_length(units: tuple[str, ...] | list[str]) -> int:
    return sum(map(len, units)) + max(0, len(units) - 1)
