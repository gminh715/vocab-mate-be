"""Sentence segmentation and HTML wrapping helper for article reader texts."""

import re
import uuid
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

READING_ELEMENTS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "figcaption"}
CONDITIONAL_READING_ELEMENTS = {"blockquote", "li", "th", "td"}
NON_READER_ELEMENTS = {"script", "style", "noscript"}

ABBREVIATIONS = (
    "Mr.",
    "Mrs.",
    "Ms.",
    "Dr.",
    "Prof.",
    "Sr.",
    "Jr.",
    "St.",
    "Mt.",
    "Gen.",
    "Rep.",
    "Sen.",
    "Gov.",
    "Capt.",
    "Lt.",
    "Col.",
    "Sgt.",
    "U.S.",
    "e.g.",
    "i.e.",
)


@dataclass
class ParsedSentence:
    """Dataclass holding segmented sentence attributes.

    Attributes:
        id (uuid.UUID): Unique sentence identifier matching data-sentence-id.
        sentence_order (int): 1-indexed order within the article.
        sentence_text (str): Plain text content of the sentence.

    Example:
        >>> s = ParsedSentence(id=uuid.uuid4(), sentence_order=1, sentence_text="Hello world.")
        >>> s.sentence_order
        1
    """

    id: uuid.UUID
    sentence_order: int
    sentence_text: str


@dataclass
class ParsedArticleContent:
    """Dataclass representing parsed HTML and extracted sentence records.

    Attributes:
        content_html (str): Sanitized HTML containing data-sentence-id spans.
        sentences (list[ParsedSentence]): Ordered list of parsed sentences.

    Example:
        >>> parsed = ParsedArticleContent(content_html="<p>Test</p>", sentences=[])
        >>> len(parsed.sentences)
        0
    """

    content_html: str
    sentences: list[ParsedSentence]


def _segment_text(text: str) -> list[str]:
    """Segments raw text into individual sentences while respecting known abbreviations.

    Args:
        text (str): Raw string of paragraph or block text.

    Returns:
        list[str]: Sequence of segmented, clean sentences.

    Example:
        >>> _segment_text("Dr. Smith left. He walked away.")
        ['Dr. Smith left.', 'He walked away.']
    """
    # Temporarily mask abbreviation periods
    masked = text
    mask_map: dict[str, str] = {}
    for i, abbr in enumerate(ABBREVIATIONS):
        placeholder = f"__ABBR_{i}__"
        if abbr in masked:
            masked = masked.replace(abbr, placeholder)
            mask_map[placeholder] = abbr

    # Split by standard sentence terminators (. ! ?) followed by whitespace or quote
    raw_sentences = re.split(r"(?<=[.!?])\s+", masked)
    results = []
    for s in raw_sentences:
        clean = s.strip()
        if not clean:
            continue
        # Unmask abbreviations
        for placeholder, original in mask_map.items():
            clean = clean.replace(placeholder, original)
        if any(c.isalnum() for c in clean):
            results.append(clean)
    return results


class SentenceParserHelper:
    """Segments article HTML text into distinct sentence records wrapped with span[data-sentence-id].

    Example:
        >>> parsed = SentenceParserHelper.parse("<p>First sentence. Second sentence.</p>")
        >>> len(parsed.sentences)
        2
    """

    @classmethod
    def parse(cls, content_html: str) -> ParsedArticleContent:
        """Parses HTML content, wraps text in sentence spans, and produces sentence records.

        Args:
            content_html (str): Input sanitized article HTML.

        Returns:
            ParsedArticleContent: Container with wrapped HTML and extracted sentence records.

        Example:
            >>> res = SentenceParserHelper.parse("<p>Hello world.</p>")
            >>> "data-sentence-id" in res.content_html
            True
        """
        soup = BeautifulSoup(content_html, "html.parser")

        # 1. Strip preexisting markers
        for tag in soup.find_all(True):
            if not isinstance(tag, Tag):
                continue
            if tag.has_attr("data-sentence-id"):
                del tag.attrs["data-sentence-id"]
            if tag.has_attr("data-term-id"):
                del tag.attrs["data-term-id"]
            if tag.name == "span" and not tag.attrs:
                tag.unwrap()

        # 2. Find target reading blocks
        target_elements: list[Tag] = []
        for tag in soup.find_all(True):
            if not isinstance(tag, Tag):
                continue
            if tag.name in READING_ELEMENTS:
                target_elements.append(tag)
            elif tag.name in CONDITIONAL_READING_ELEMENTS:
                # Only if it does not contain a nested reading element
                if not tag.find_all(READING_ELEMENTS):
                    target_elements.append(tag)

        sentences: list[ParsedSentence] = []
        order = 1

        for elem in target_elements:
            # Extract plain text of element
            text = elem.get_text()
            if not text.strip():
                continue

            elem_sentences = _segment_text(text)
            if not elem_sentences:
                continue

            # Clear elem contents and reconstruct with sentence spans
            elem.clear()
            for s_text in elem_sentences:
                s_id = uuid.uuid4()
                span = soup.new_tag("span", attrs={"data-sentence-id": str(s_id)})
                span.string = s_text
                elem.append(span)
                elem.append(NavigableString(" "))
                sentences.append(ParsedSentence(id=s_id, sentence_order=order, sentence_text=s_text))
                order += 1

        return ParsedArticleContent(content_html=str(soup).strip(), sentences=sentences)
