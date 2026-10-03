# ruff: noqa: RUF001 -- the Russian fixtures are Cyrillic on purpose
"""`bad verdict-gate` — the answer opens on a verdict a reader can take in at a glance.

The owner skims a long report for its top line and stops there, so the first line of prose
must BE the answer (at most 15 words), and somewhere the answer must say what would
overturn it. Both are form checks: they cannot tell a good verdict from a bad one.
"""
from __future__ import annotations

import json
import subprocess
import sys

from bad_research.checks.verdict_first import MAX_VERDICT_WORDS, check_verdict_first

RU_PASS = """Бери uv: он ставит зависимости в 10 раз быстрее pip на нашем репо.
Tier: standard — версии и цифры меняются, поэтому нужен свежий источник.

Подробности и цифры ниже.

Что перевернёт вывод: прогон на CI, где pip с кешем окажется не медленнее.
"""

EN_PASS = """Use uv: it installs this repo's dependencies ten times faster than pip.
Tier: standard — versions and timings move, so a fresh source was needed.

Details follow.

What would overturn this: a CI run where cached pip is no slower.
"""


def test_a_russian_answer_that_leads_with_the_verdict_passes():
    r = check_verdict_first(RU_PASS)
    assert r.ok, r.findings
    assert r.verdict.startswith("Бери uv")


def test_an_english_answer_that_leads_with_the_verdict_passes():
    r = check_verdict_first(EN_PASS)
    assert r.ok, r.findings


def test_a_sixteen_word_first_line_is_refused():
    line = " ".join(f"w{i}" for i in range(16))
    r = check_verdict_first(line + "\n\nWhat would overturn this: nothing yet.\n")
    assert not r.ok
    assert [f.kind for f in r.findings] == ["verdict_too_long"]
    assert r.findings[0].line == 1
    assert "16" in r.findings[0].message


def test_exactly_fifteen_words_is_the_limit_not_past_it():
    line = " ".join(f"w{i}" for i in range(MAX_VERDICT_WORDS))
    r = check_verdict_first(line + "\nWould change the answer: a rerun.\n")
    assert r.ok, r.findings


def test_a_heading_then_the_verdict_passes():
    answer = "# Which installer\n\n## Verdict\n\nUse uv, it is faster here.\n\nWhat would change this: a CI rerun.\n"
    r = check_verdict_first(answer)
    assert r.ok, r.findings
    assert r.verdict == "Use uv, it is faster here."
    assert r.verdict_line == 5


def test_front_matter_is_skipped():
    words = " ".join(f"meta{i}" for i in range(30))
    answer = f"---\ntitle: {words}\ntags: [a, b]\n---\n\nUse uv.\n\nЧто перевернет вывод: прогон на CI.\n"
    r = check_verdict_first(answer)
    assert r.ok, r.findings
    assert r.verdict == "Use uv."


def test_a_missing_overturn_line_is_refused():
    r = check_verdict_first("Use uv: it is faster.\n\nDetails follow.\n")
    assert not r.ok
    assert [f.kind for f in r.findings] == ["no_overturn_line"]


def test_an_answer_with_no_prose_is_refused_not_passed():
    """A gate that passes on an empty file is a gate that can only pass."""
    r = check_verdict_first("---\na: b\n---\n\n# Title\n\n")
    assert not r.ok
    assert "no_verdict" in [f.kind for f in r.findings]


def _cli(tmp_path, text, *extra):
    p = tmp_path / "answer.md"
    p.write_text(text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "bad_research", "verdict-gate", str(p), *extra],
        capture_output=True, text=True,
    )


def test_cli_exits_zero_on_a_clean_answer(tmp_path):
    r = _cli(tmp_path, EN_PASS)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cli_exits_one_with_one_line_per_finding(tmp_path):
    line = " ".join(f"w{i}" for i in range(20))
    r = _cli(tmp_path, line + "\n")
    assert r.returncode == 1, r.stdout + r.stderr
    finding_lines = [ln for ln in r.stdout.splitlines() if ln.startswith("verdict-gate: ")]
    assert len(finding_lines) == 2, r.stdout


def test_cli_json(tmp_path):
    r = _cli(tmp_path, "Use uv.\n", "--json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["ok"] is False
    assert [f["kind"] for f in data["findings"]] == ["no_overturn_line"]
