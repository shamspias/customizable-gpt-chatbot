"""Golden (NL request → expected-spec properties) cases.

Assertions are property-level (not exact-match) because the compiler is a
generative task: we check the load-bearing decisions (did it attach the KB when
the task needs documents? did it avoid tools when it doesn't?), not exact wording.
This corpus doubles as the seed for the v1 self-mod dry-run replay gate.
"""

from __future__ import annotations

CASES: list[dict] = [
    {
        "name": "docs_qa_with_citations",
        "request": "Answer questions strictly from my uploaded documents and always cite the page.",
        "expect": {"needs_kb": True},
    },
    {
        "name": "summarize_docs",
        "request": "Summarize the key findings from the documents I uploaded.",
        "expect": {"needs_kb": True},
    },
    {
        "name": "support_triage_from_docs",
        "request": "Triage support emails: classify urgency and draft a reply grounded in our docs.",
        "expect": {"needs_kb": True},
    },
    {
        "name": "python_tutor_no_docs",
        "request": "A friendly assistant that explains Python programming concepts simply.",
        "expect": {"no_tools": True},
    },
    {
        "name": "slogan_brainstormer_no_docs",
        "request": "A creative brainstorming partner that generates marketing slogans.",
        "expect": {"no_tools": True},
    },
]

# Compiler is generative; require a high but not perfect pass rate.
TARGET_ACCURACY = 0.8
