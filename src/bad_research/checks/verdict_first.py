"""`bad verdict-gate` — the answer opens on its verdict and says what would overturn it.

The owner reads a research answer's top line and, more often than not, stops there. An
answer that opens on the journey, the tier, or a paragraph of context has spent its one
guaranteed line on something other than the answer. So two form rules, both mechanical:

1. The first line of prose — after any YAML front matter, headings and blank lines — has
   at most 15 whitespace-separated words. That line is the verdict.
2. Some line names what would overturn the conclusion ("Что перевернёт вывод: …",
   "What would overturn this: …"). A verdict with no stated way to be wrong reads as
   certainty the run did not earn.

This checks form, never fact: a 15-word verdict can still be wrong, and an overturn line
can name something nobody will ever check. It refuses only the shapes that hide the
answer or hide its fragility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_VERDICT_WORDS = 15

_OVERTURN = re.compile(
    r"что перевернёт|перевернет|would overturn|what would change"
    r"|would change (?:this|the) (?:answer|verdict|conclusion)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VerdictFinding:
    kind: str  # verdict_too_long | no_verdict | no_overturn_line
    line: int  # 1-based; 0 when the finding is about the whole answer
    message: str


@dataclass(frozen=True)
class VerdictReport:
    verdict: str
    verdict_line: int
    findings: tuple[VerdictFinding, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "verdict_line": self.verdict_line,
            "verdict_words": len(self.verdict.split()),
            "max_words": MAX_VERDICT_WORDS,
            "findings": [
                {"kind": f.kind, "line": f.line, "message": f.message} for f in self.findings
            ],
        }


def _body_start(lines: list[str]) -> int:
    """Index of the first line after a leading YAML front-matter block (0 if none)."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                return i + 1
    return 0


def check_verdict_first(answer: str) -> VerdictReport:
    lines = answer.splitlines()
    verdict, verdict_line = "", 0
    for i in range(_body_start(lines), len(lines)):
        s = lines[i].strip()
        if not s or s.startswith("#"):
            continue
        verdict, verdict_line = s, i + 1
        break

    findings: list[VerdictFinding] = []
    if not verdict:
        findings.append(VerdictFinding("no_verdict", 0, "no prose line found; the answer has no verdict"))
    else:
        n = len(verdict.split())
        if n > MAX_VERDICT_WORDS:
            findings.append(VerdictFinding(
                "verdict_too_long", verdict_line,
                f"first prose line has {n} words (max {MAX_VERDICT_WORDS}): {verdict[:80]}",
            ))
    if not any(_OVERTURN.search(ln) for ln in lines):
        findings.append(VerdictFinding(
            "no_overturn_line", 0,
            'no line names what would overturn the conclusion ("Что перевернёт вывод: …" / '
            '"What would overturn this: …")',
        ))
    return VerdictReport(verdict, verdict_line, tuple(findings))


__all__ = ["MAX_VERDICT_WORDS", "VerdictFinding", "VerdictReport", "check_verdict_first"]
