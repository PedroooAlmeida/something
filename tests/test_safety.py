"""M5 acceptance tests: banned-term filter + anti-fabrication scrubber."""

from __future__ import annotations

from gordon.safety import detect_fabrications, enforce_roast_budget, filter_text

CONTEXT = 'Their prompt: """Make this work on line 12 of app.py"""'


def test_fabricated_percentage_stripped() -> None:
    # the spec's M5 gate, verbatim
    text = "Flash v2 is 40% faster. Your prompt is mush."
    safe, dropped = filter_text(text, CONTEXT)
    assert safe == "Your prompt is mush."
    assert len(dropped) == 1 and "40%" in dropped[0]


def test_number_present_in_context_kept() -> None:
    safe, dropped = filter_text("Line 12 deserves better than this.", CONTEXT)
    assert safe == "Line 12 deserves better than this."
    assert dropped == []


def test_version_and_date_from_knowledge_context_kept() -> None:
    context = CONTEXT + " React 19 released 2024-12-05 source react.dev"
    text = "React 19 shipped on 2024-12-05 and you missed it."
    safe, dropped = filter_text(text, context)
    assert safe == text
    assert dropped == []


def test_fabricated_year_stripped() -> None:
    safe, dropped = filter_text("This prompt belongs in 2019. Bland work.", CONTEXT)
    assert safe == "Bland work."
    assert "2019" in dropped[0]


def test_banned_term_strips_whole_sentence() -> None:
    safe, dropped = filter_text("You absolute moron. The prompt has no goal.", CONTEXT)
    assert safe == "The prompt has no goal."
    assert "moron" in dropped[0]


def test_person_directed_insult_stripped_artifact_kept() -> None:
    safe, dropped = filter_text("You're stupid for this. This stupid prompt has no goal.", CONTEXT)
    assert safe == "This stupid prompt has no goal."
    assert len(dropped) == 1


def test_identity_terms_never_pass() -> None:
    safe, dropped = filter_text("Spoken like a jewish grandmother. No goal stated.", CONTEXT)
    assert safe == "No goal stated."
    assert len(dropped) == 1


def test_everything_stripped_returns_empty() -> None:
    safe, dropped = filter_text("This is 40% slower than v9.9.", CONTEXT)
    assert safe == ""
    assert len(dropped) == 1


def test_detect_fabrications_logs_but_never_edits() -> None:
    text = "Use Python 3.99 and cut latency by 80%."
    notes = detect_fabrications(text, CONTEXT)
    assert len(notes) == 1
    assert "3.99" in notes[0] and "80%" in notes[0]


def test_roast_budget_sentence_cap() -> None:
    assert enforce_roast_budget("One. Two. Three. Four.") == "One. Two."


def test_roast_budget_word_cap() -> None:
    long_sentence = " ".join(["word"] * 50) + "."
    trimmed = enforce_roast_budget(long_sentence)
    assert len(trimmed.split()) <= 36  # 35 words + trailing period merge
    assert trimmed.endswith(".")


def test_roast_budget_leaves_compliant_text_alone() -> None:
    text = "Raw in the middle. Send it back."
    assert enforce_roast_budget(text) == text
