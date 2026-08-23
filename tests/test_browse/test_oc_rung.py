"""Rung 1.5 — the `oc` provider and its seat in the ladder. No subprocess, no network."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from bad_research.browse import oc
from bad_research.browse.ladder import fetch_tiered
from tests.test_browse.conftest import FakeRunner, make_result


def _payload(blocks, url="https://x.test/page", title="Real"):
    return json.dumps({"url": url, "title": title, "blocks": blocks})


def _article_blocks(n=12):
    return [{"type": "heading", "level": 1, "text": "The Headline"}] + [
        {"type": "text", "text": f"Paragraph {i} carrying real prose about the subject."}
        for i in range(n)
    ]


# ---------------------------------------------------------------- the provider ----

def test_fetch_renders_headings_and_text_and_drops_chrome() -> None:
    blocks = [
        {"type": "button", "text": "Back", "n": 1},
        {"type": "link", "text": "Log in", "href": "/login", "n": 2},
        {"type": "heading", "level": 1, "text": "The Headline", "n": 3},
        {"type": "text", "text": "The first real paragraph of the article body."},
        # Enough prose to clear MIN_USEFUL_CHARS. Below it a render is a miss, not a
        # thin page, and the provider returns None on purpose — see the #14 test.
        *[
            {"type": "text", "text": f"Body paragraph {i} with enough prose to count."}
            for i in range(6)
        ],
    ]
    runner = FakeRunner(replies=[_payload(blocks)])
    result = oc.fetch("https://x.test/page", runner=runner)

    assert result is not None
    assert "# The Headline" in result.content
    assert "The first real paragraph" in result.content
    # A button is scaffolding and goes. A link stays: on an aggregator the link text
    # IS the headline, and dropping it empties the page.
    assert "Back" not in result.content
    assert "Log in" in result.content
    assert result.metadata["provider"] == "oc"


def test_fetch_asks_for_raw_json_and_pins_its_own_session_dir() -> None:
    captured: dict = {}

    def runner(argv, *, timeout=None, env=None, stdin=None):
        captured["argv"] = list(argv)
        captured["env"] = dict(env or {})
        return (0, _payload(_article_blocks()), "")

    assert oc.fetch("https://x.test/page", runner=runner) is not None
    assert captured["argv"][-3:] == ["raw", "https://x.test/page", "--json"]
    # Never the user's own ~/.only-cli.
    assert "bad-research" in captured["env"]["OC_HOME"]


def test_a_render_that_distilled_almost_nothing_is_not_a_result() -> None:
    """only-cli/oc#14: a JS-only page exits 0 with no content blocks and claims success."""
    runner = FakeRunner(replies=[_payload([{"type": "link", "text": "Skip to main content"}])])
    assert oc.fetch("https://x.test/page", runner=runner) is None


def test_nonzero_exit_empty_stdout_and_malformed_json_are_all_none() -> None:
    assert oc.fetch("https://x.test/p", runner=FakeRunner(replies=["{}"], returncode=1)) is None
    assert oc.fetch("https://x.test/p", runner=FakeRunner(replies=[""])) is None
    assert oc.fetch("https://x.test/p", runner=FakeRunner(replies=["not json"])) is None


def test_a_blocked_entry_url_never_reaches_the_cli() -> None:
    runner = FakeRunner(replies=[_payload(_article_blocks())])
    assert oc.fetch("http://127.0.0.1/admin", runner=runner) is None
    assert runner.calls == []


def test_a_blocked_final_url_is_discarded_even_though_oc_returned_content() -> None:
    """oc re-validates every hop itself; a rung must not rest on that staying correct."""
    runner = FakeRunner(replies=[_payload(_article_blocks(), url="http://169.254.169.254/latest")])
    assert oc.fetch("https://x.test/page", runner=runner) is None


# -------------------------------------------------------------------- the rung ----

def test_rung1_empty_escalates_to_oc_before_crawl4ai() -> None:
    t0 = MagicMock()
    t0.fetch.return_value = make_result("tiny", title="Stub")
    t1 = MagicMock()
    provider = MagicMock()
    provider.fetch.return_value = make_result(
        "Substantial real article content. " * 30, title="Real"
    )

    r = fetch_tiered(
        "https://x.test", tier_max=3, _tier0=t0, _oc=provider, _tier1_factory=lambda: t1
    )

    assert r.content.startswith("Substantial real")
    provider.fetch.assert_called_once()
    t1.fetch.assert_not_called()


def test_a_good_rung1_result_never_reaches_oc() -> None:
    t0 = MagicMock()
    t0.fetch.return_value = make_result("Substantial real article content. " * 30, title="Real")
    provider = MagicMock()

    fetch_tiered("https://x.test", tier_max=3, _tier0=t0, _oc=provider, _tier1_factory=lambda: None)

    provider.fetch.assert_not_called()


def test_an_oc_miss_keeps_the_incumbent_and_the_ladder_escalates() -> None:
    """The silent-miss guard: `oc` returning nothing must not stop crawl4ai running."""
    t0 = MagicMock()
    t0.fetch.return_value = make_result("tiny", title="Stub")
    t1 = MagicMock()
    t1.fetch.return_value = make_result("Substantial real article content. " * 30, title="Real")
    provider = MagicMock()
    provider.fetch.return_value = None

    r = fetch_tiered(
        "https://x.test", tier_max=3, _tier0=t0, _oc=provider, _tier1_factory=lambda: t1
    )

    assert r.content.startswith("Substantial real")
    t1.fetch.assert_called_once()


def test_oc_wins_only_by_returning_more_text_than_the_incumbent() -> None:
    t0 = MagicMock()
    t0.fetch.return_value = make_result("tiny but distinctive rung one body", title="Stub")
    provider = MagicMock()
    provider.fetch.return_value = make_result("shorter", title="Thin")

    r = fetch_tiered(
        "https://x.test", tier_max=1, _tier0=t0, _oc=provider, _tier1_factory=lambda: None
    )

    assert r.content == "tiny but distinctive rung one body"


def test_a_broken_provider_is_a_skipped_rung_not_an_error() -> None:
    t0 = MagicMock()
    t0.fetch.return_value = make_result("tiny", title="Stub")
    provider = MagicMock()
    provider.fetch.side_effect = RuntimeError("cli exploded")

    r = fetch_tiered(
        "https://x.test", tier_max=1, _tier0=t0, _oc=None, _tier1_factory=lambda: None
    )

    assert r.content == "tiny"
