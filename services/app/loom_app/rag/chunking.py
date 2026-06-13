"""Structure-aware chunking with page/char metadata for precise citations.

~512-token target chunks, split on paragraph boundaries (never mid-paragraph
unless a single paragraph exceeds the budget). Each chunk carries its page number
and char span — that citation metadata is the load-bearing part of the page index.
Token sizing uses tiktoken's cl100k_base purely as a length heuristic (not for
Claude billing — that would use count_tokens).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")
_PARA = re.compile(r"\n\s*\n")


@dataclass
class Chunk:
    content: str
    page_number: int | None
    char_start: int
    char_end: int
    token_count: int


def _ntokens(text: str) -> int:
    return len(_ENC.encode(text))


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Char spans of paragraphs (blank-line separated), preserving offsets."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in _PARA.finditer(text):
        if m.start() > pos:
            spans.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return [(s, e) for (s, e) in spans if text[s:e].strip()]


def chunk_page(
    text: str,
    page_number: int | None,
    base_offset: int,
    target_tokens: int = 512,
) -> list[Chunk]:
    """Chunk a single page's text into ~target_tokens chunks. char offsets are
    absolute within the document (base_offset = this page's start in the doc)."""
    chunks: list[Chunk] = []
    cur_start: int | None = None
    cur_end = 0
    cur_tokens = 0

    def flush() -> None:
        nonlocal cur_start, cur_end, cur_tokens
        if cur_start is None:
            return
        content = text[cur_start:cur_end].strip()
        if content:
            chunks.append(
                Chunk(content, page_number, base_offset + cur_start, base_offset + cur_end,
                      _ntokens(content))
            )
        cur_start, cur_end, cur_tokens = None, 0, 0

    for start, end in _paragraph_spans(text):
        para = text[start:end]
        ptok = _ntokens(para)
        if ptok > target_tokens:
            # Oversized paragraph (e.g. a table): emit current, then split by sentences.
            flush()
            for s2, e2 in _sentence_subspans(text, start, end, target_tokens):
                seg = text[s2:e2].strip()
                if seg:
                    chunks.append(
                        Chunk(seg, page_number, base_offset + s2, base_offset + e2, _ntokens(seg))
                    )
            continue
        if cur_start is not None and cur_tokens + ptok > target_tokens:
            flush()
        if cur_start is None:
            cur_start = start
        cur_end = end
        cur_tokens += ptok
    flush()
    return chunks


def _sentence_subspans(text: str, start: int, end: int, target: int) -> list[tuple[int, int]]:
    """Greedy sentence packing for an oversized paragraph; falls back to words."""
    segment = text[start:end]
    pieces = re.split(r"(?<=[.!?])\s+", segment)
    spans: list[tuple[int, int]] = []
    pos = start
    cur_s = start
    cur_tok = 0
    for piece in pieces:
        plen = len(piece)
        # advance pos to the piece location (handles the consumed whitespace)
        idx = text.find(piece, pos, end) if piece else pos
        if idx < 0:
            idx = pos
        ptok = _ntokens(piece)
        if cur_tok + ptok > target and cur_s < idx:
            spans.append((cur_s, idx))
            cur_s = idx
            cur_tok = 0
        cur_tok += ptok
        pos = idx + plen
    if cur_s < end:
        spans.append((cur_s, end))
    return spans
