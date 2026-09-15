"""Tests for article NLP and HTML helpers."""

import uuid

from app.models.enums import CefrLevel
from app.modules.articles.helpers.cefr_analyzer import CefrAnalyzerHelper
from app.modules.articles.helpers.html_sanitizer import HtmlSanitizerHelper
from app.modules.articles.helpers.sentence_parser import SentenceParserHelper
from app.modules.articles.helpers.term_marker import TermMarkerHelper


def test_html_sanitizer():
    dirty_html = '<p>Hello world!<script>alert("xss")</script><a href="javascript:steal()">bad</a><a href="https://example.com">good</a></p>'
    clean = HtmlSanitizerHelper.sanitize(dirty_html)
    assert "<script>" not in clean
    assert "javascript:" not in clean
    assert "https://example.com" in clean
    assert 'rel="noopener noreferrer"' in clean


def test_sentence_parser():
    raw_html = "<p>Dr. Smith arrived yesterday. He announced a new discovery! Will it change the world?</p>"
    parsed = SentenceParserHelper.parse(raw_html)
    assert len(parsed.sentences) == 3
    assert "data-sentence-id" in parsed.content_html
    assert parsed.sentences[0].sentence_text == "Dr. Smith arrived yesterday."
    assert parsed.sentences[1].sentence_text == "He announced a new discovery!"
    assert parsed.sentences[2].sentence_text == "Will it change the world?"


def test_term_marker():
    s_id = uuid.uuid4()
    t_id = uuid.uuid4()
    html = f'<p><span data-sentence-id="{s_id}">He made an important discovery yesterday.</span></p>'
    marked = TermMarkerHelper.insert(html, s_id, t_id, "discovery")
    assert f'data-term-id="{t_id}"' in marked
    assert f'<span data-term-id="{t_id}">discovery</span>' in marked

    # Whole word boundary check: "discover" should not match "discovery"
    t_id2 = uuid.uuid4()
    not_marked = TermMarkerHelper.insert(html, s_id, t_id2, "discover")
    assert f'data-term-id="{t_id2}"' not in not_marked

    # Unwrap test
    unwrapped = TermMarkerHelper.unwrap(marked, t_id)
    assert f'data-term-id="{t_id}"' not in unwrapped
    assert "discovery" in unwrapped


def test_cefr_analyzer():
    easy_text = "This is a book. I like to read books every day with my friend."
    level, term_levels, score = CefrAnalyzerHelper.evaluate_text(easy_text)
    assert isinstance(level, CefrLevel)
    assert "book" in term_levels or "read" in term_levels
    assert score > 0
