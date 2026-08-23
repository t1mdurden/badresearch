import hashlib

from bad_research.models.note import Note, NoteMeta
from bad_research.retrieval.chunker import chunk_note, make_chunk_id
from bad_research.retrieval.constants import CHUNK_BYTE_TARGET


def _note(body: str, source="https://ex.com/a", content_type=None, status="draft") -> Note:
    meta = NoteMeta(title="T", id="n1", source=source, content_type=content_type, status=status)
    return Note(meta=meta, body=body, path="research/n1.md")


def test_chunk_id_is_stable_sha1_of_url_hash_heading():
    cid = make_chunk_id("https://ex.com/a", "Setup")
    assert cid == hashlib.sha1(b"https://ex.com/a#Setup").hexdigest()
    # Deterministic: same inputs -> same id across calls.
    assert make_chunk_id("https://ex.com/a", "Setup") == cid


def test_short_note_is_single_whole_note_chunk():
    body = "# Title\n\nA short prose note under the min byte threshold.\n"
    chunks = chunk_note(_note(body))
    assert len(chunks) == 1
    c = chunks[0]
    # Offsets cover the whole body and slice back to it.
    assert c.char_start == 0
    assert c.char_end == len(body)


def test_prose_splits_at_h2_headings_with_correct_offsets():
    body = (
        "# Title\n\nIntro paragraph.\n\n"
        "## Section One\n\n" + ("alpha " * 600) + "\n\n"
        "## Section Two\n\n" + ("beta " * 600) + "\n"
    )
    chunks = chunk_note(_note(body))
    assert len(chunks) >= 2
    # PROVENANCE: every chunk slices back to its declared offsets exactly.
    for c in chunks:
        assert body[c.char_start:c.char_end] == _slice_for(body, c)
    # Headings became distinct chunk_ids (sha1 of url#heading).
    ids = {c.chunk_id for c in chunks}
    assert len(ids) == len(chunks)


def _slice_for(body, chunk):
    # The chunk text (minus any prepended embed header) must be a verbatim
    # substring of body at [char_start:char_end].
    return body[chunk.char_start:chunk.char_end]


def test_chunk_text_is_verbatim_body_slice():
    body = "# T\n\n## A\n\n" + ("word " * 700) + "\n\n## B\n\n" + ("term " * 700) + "\n"
    for c in chunk_note(_note(body)):
        assert c.text == body[c.char_start:c.char_end]
        assert 0 <= c.char_start < c.char_end <= len(body)


def test_blank_lineless_page_still_splits_below_the_hard_cap():
    # A fetched page: one line per paragraph, no blank lines, no headings.
    body = "\n".join(f"Sentence {i} about smart money indicators." for i in range(900))
    chunks = chunk_note(_note(body))
    assert len(chunks) > 1
    assert max(len(c.text.encode()) for c in chunks) <= CHUNK_BYTE_TARGET * 2
    for c in chunks:
        assert c.text == body[c.char_start:c.char_end]
