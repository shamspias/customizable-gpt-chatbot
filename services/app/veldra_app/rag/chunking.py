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
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(\S.*?)\s*#*$")


@dataclass
class Chunk:
    content: str
    page_number: int | None
    char_start: int
    char_end: int
    token_count: int
    section_path: str | None = None


def _ntokens(text: str) -> int:
    return len(_ENC.encode(text))


def _update_sections(stack: dict[int, str], paragraph: str) -> None:
    """If the paragraph opens with a Markdown heading, update the section stack."""
    first = paragraph.lstrip().split("\n", 1)[0]
    m = _HEADING.match(first)
    if not m:
        return
    level = len(m.group(1))
    stack[level] = m.group(2).strip()
    for deeper in [lvl for lvl in stack if lvl > level]:
        del stack[deeper]


def _section_path(stack: dict[int, str]) -> str | None:
    return " › ".join(stack[lvl] for lvl in sorted(stack)) or None


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
    stack: dict[int, str] = {}      # active Markdown heading stack → section_path
    cur_start: int | None = None
    cur_end = 0
    cur_tokens = 0
    cur_section: str | None = None

    def flush() -> None:
        nonlocal cur_start, cur_end, cur_tokens, cur_section
        if cur_start is None:
            return
        content = text[cur_start:cur_end].strip()
        if content:
            chunks.append(
                Chunk(content, page_number, base_offset + cur_start, base_offset + cur_end,
                      _ntokens(content), cur_section)
            )
        cur_start, cur_end, cur_tokens, cur_section = None, 0, 0, None

    for start, end in _paragraph_spans(text):
        para = text[start:end]
        _update_sections(stack, para)  # headings refine the section before this content
        ptok = _ntokens(para)
        if ptok > target_tokens:
            # Oversized paragraph (e.g. a table): emit current, then split by sentences.
            flush()
            path = _section_path(stack)
            for s2, e2 in _sentence_subspans(text, start, end, target_tokens):
                seg = text[s2:e2].strip()
                if seg:
                    chunks.append(
                        Chunk(seg, page_number, base_offset + s2, base_offset + e2,
                              _ntokens(seg), path)
                    )
            continue
        if cur_start is not None and cur_tokens + ptok > target_tokens:
            flush()
        if cur_start is None:
            cur_start = start
            cur_section = _section_path(stack)
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
