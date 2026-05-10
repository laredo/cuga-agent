"""Unit tests for _parse_slack_notifications() in swarm.py.

Pure string logic — no LLM, no async, no external dependencies.

Covers:
- Plain text with no directives → returned as leftover, no notifications
- Single NOTIFY_SLACK: block (inline and multi-line)
- Multiple NOTIFY_SLACK: blocks
- Mixed: plain text + NOTIFY_SLACK blocks in various orders
- Inline text on the NOTIFY_SLACK: line is captured
- Empty NOTIFY_SLACK: block (no text follows) → skipped
- Case insensitivity of the NOTIFY_SLACK: prefix
- Edge cases: only whitespace, Windows line endings, colons in content
"""

from __future__ import annotations

import pytest

from cuga.backend.multi_agent.patterns.swarm import _parse_slack_notifications


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse(text: str):
    """Thin wrapper so tests read naturally."""
    return _parse_slack_notifications(text)


# ---------------------------------------------------------------------------
# Plain text — no directives
# ---------------------------------------------------------------------------

class TestPlainText:

    def test_empty_string(self):
        leftover, notifs = parse("")
        assert leftover == ""
        assert notifs == []

    def test_whitespace_only(self):
        leftover, notifs = parse("   \n  \n  ")
        assert leftover == ""
        assert notifs == []

    def test_plain_text_returned_as_leftover(self):
        leftover, notifs = parse("Hello from the chief of staff.")
        assert leftover == "Hello from the chief of staff."
        assert notifs == []

    def test_multiline_plain_text_preserved(self):
        text = "Line one.\nLine two.\nLine three."
        leftover, notifs = parse(text)
        assert leftover == text
        assert notifs == []

    def test_text_with_colon_not_treated_as_directive(self):
        text = "Status: all good\nResult: done"
        leftover, notifs = parse(text)
        assert leftover == text
        assert notifs == []


# ---------------------------------------------------------------------------
# Single NOTIFY_SLACK: block
# ---------------------------------------------------------------------------

class TestSingleNotify:

    def test_inline_text_only(self):
        leftover, notifs = parse("NOTIFY_SLACK:Hello Slack!")
        assert leftover == ""
        assert notifs == ["Hello Slack!"]

    def test_inline_text_with_leading_space(self):
        leftover, notifs = parse("NOTIFY_SLACK: Hello Slack!")
        assert notifs == ["Hello Slack!"]

    def test_multiline_block(self):
        text = "NOTIFY_SLACK:\nLine one\nLine two"
        leftover, notifs = parse(text)
        assert leftover == ""
        assert len(notifs) == 1
        assert "Line one" in notifs[0]
        assert "Line two" in notifs[0]

    def test_inline_plus_continuation_lines(self):
        text = "NOTIFY_SLACK: First line\nSecond line\nThird line"
        leftover, notifs = parse(text)
        assert leftover == ""
        assert len(notifs) == 1
        assert "First line" in notifs[0]
        assert "Second line" in notifs[0]
        assert "Third line" in notifs[0]

    def test_empty_notify_block_produces_no_entry(self):
        """A NOTIFY_SLACK: with only whitespace/blank lines → nothing appended."""
        leftover, notifs = parse("NOTIFY_SLACK:\n   \n")
        assert notifs == []

    def test_emoji_in_content_preserved(self):
        leftover, notifs = parse("NOTIFY_SLACK: ✅ *Vetted:* Source — Score: 4/5.")
        assert notifs[0] == "✅ *Vetted:* Source — Score: 4/5."

    def test_url_in_content_preserved(self):
        text = "NOTIFY_SLACK:\nhttps://example.com/article?q=1&page=2"
        leftover, notifs = parse(text)
        assert "https://example.com/article?q=1&page=2" in notifs[0]

    def test_colon_inside_notify_content_not_split(self):
        """A colon inside the notification body must not split the block."""
        text = "NOTIFY_SLACK: Score: 5/5\nURL: https://example.com"
        leftover, notifs = parse(text)
        assert len(notifs) == 1
        assert "Score: 5/5" in notifs[0]
        assert "URL: https://example.com" in notifs[0]


# ---------------------------------------------------------------------------
# Multiple NOTIFY_SLACK: blocks
# ---------------------------------------------------------------------------

class TestMultipleNotify:

    def test_two_inline_blocks(self):
        text = "NOTIFY_SLACK: First\nNOTIFY_SLACK: Second"
        leftover, notifs = parse(text)
        assert leftover == ""
        assert len(notifs) == 2
        assert notifs[0] == "First"
        assert notifs[1] == "Second"

    def test_five_blocks_all_captured(self):
        lines = "\n".join(f"NOTIFY_SLACK: Doc {i}" for i in range(5))
        leftover, notifs = parse(lines)
        assert len(notifs) == 5
        for i, n in enumerate(notifs):
            assert f"Doc {i}" in n

    def test_multiline_blocks_each_independent(self):
        text = (
            "NOTIFY_SLACK: Block A header\n"
            "Block A body\n"
            "NOTIFY_SLACK: Block B header\n"
            "Block B body"
        )
        leftover, notifs = parse(text)
        assert len(notifs) == 2
        assert "Block A header" in notifs[0]
        assert "Block A body" in notifs[0]
        assert "Block B header" in notifs[1]
        assert "Block B body" in notifs[1]
        # A body must not leak into B and vice versa
        assert "Block B" not in notifs[0]
        assert "Block A" not in notifs[1]


# ---------------------------------------------------------------------------
# Mixed plain text + NOTIFY_SLACK blocks
# ---------------------------------------------------------------------------

class TestMixedContent:

    def test_plain_text_before_notify(self):
        text = "Ack: I'm on it.\nNOTIFY_SLACK: Update from the team."
        leftover, notifs = parse(text)
        assert "Ack: I'm on it." in leftover
        assert notifs == ["Update from the team."]

    def test_plain_text_after_notify(self):
        """Text after a NOTIFY_SLACK block is consumed into the block, not leftover."""
        text = "NOTIFY_SLACK: The update\nSome trailing text"
        leftover, notifs = parse(text)
        assert leftover == ""
        assert "Some trailing text" in notifs[0]

    def test_plain_text_between_notify_blocks(self):
        """Lines between two NOTIFY_SLACK: markers fall inside the first block."""
        text = (
            "NOTIFY_SLACK: First update\n"
            "Still inside first block\n"
            "NOTIFY_SLACK: Second update"
        )
        leftover, notifs = parse(text)
        assert len(notifs) == 2
        assert "Still inside first block" in notifs[0]

    def test_chief_of_staff_realistic_output(self):
        """Simulates a real chief_of_staff response: ack text + no NOTIFY block."""
        text = (
            "🔍 Starting research on *quantum computing*. "
            "My team is on it — I'll post updates here."
        )
        leftover, notifs = parse(text)
        assert "Starting research" in leftover
        assert notifs == []

    def test_web_searcher_realistic_output(self):
        """Simulates web_searcher output: multiple NOTIFY blocks, no leftover."""
        text = (
            "NOTIFY_SLACK:📄 *Found:* Quantum Supremacy Paper — Nature (2023)\n"
            "https://nature.com/articles/123\n"
            "NOTIFY_SLACK:📄 *Found:* IBM Quantum Report — IBM (2024)\n"
            "https://ibm.com/quantum/report\n"
            "NOTIFY_SLACK:✅ *Web search complete* — dispatched 2 sources."
        )
        leftover, notifs = parse(text)
        assert leftover == ""
        assert len(notifs) == 3
        assert "Quantum Supremacy" in notifs[0]
        assert "IBM Quantum" in notifs[1]
        assert "Web search complete" in notifs[2]

    def test_fact_checker_realistic_output(self):
        """Simulates fact_checker output: single NOTIFY block, no leftover."""
        text = "NOTIFY_SLACK:✅ *Vetted:* Quantum Supremacy Paper — Score: 5/5. Stored in KB."
        leftover, notifs = parse(text)
        assert leftover == ""
        assert len(notifs) == 1
        assert "Vetted" in notifs[0]
        assert "5/5" in notifs[0]


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------

class TestCaseInsensitivity:

    def test_uppercase_prefix_recognised(self):
        leftover, notifs = parse("NOTIFY_SLACK: message")
        assert notifs == ["message"]

    def test_lowercase_prefix_recognised(self):
        leftover, notifs = parse("notify_slack: message")
        assert notifs == ["message"]

    def test_mixed_case_prefix_recognised(self):
        leftover, notifs = parse("Notify_Slack: message")
        assert notifs == ["message"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_windows_line_endings(self):
        text = "NOTIFY_SLACK: line one\r\nline two\r\nNOTIFY_SLACK: second"
        leftover, notifs = parse(text)
        # Should not crash; blocks should be detected
        assert len(notifs) >= 1

    def test_notify_slack_in_middle_of_word_not_triggered(self):
        """Only a line that STARTS with NOTIFY_SLACK: should be treated as directive."""
        text = "See NOTIFY_SLACK: this is not a directive"
        leftover, notifs = parse(text)
        # Line doesn't start with NOTIFY_SLACK: so it's leftover
        assert "See NOTIFY_SLACK:" in leftover
        assert notifs == []

    def test_very_long_content_preserved(self):
        long_body = "word " * 500
        text = f"NOTIFY_SLACK: {long_body.strip()}"
        leftover, notifs = parse(text)
        assert len(notifs) == 1
        assert len(notifs[0]) > 100

    def test_return_types_are_correct(self):
        leftover, notifs = parse("anything")
        assert isinstance(leftover, str)
        assert isinstance(notifs, list)

    def test_notify_only_whitespace_after_colon_skipped(self):
        text = "NOTIFY_SLACK:   \n\n"
        leftover, notifs = parse(text)
        assert notifs == []
