"""HTML term marker helper for inserting, updating, and removing span[data-term-id] elements."""

import re
import uuid

from bs4 import BeautifulSoup, NavigableString, Tag


class TermMarkerHelper:
    """Utility for inserting, replacing, and unwrapping span[data-term-id] elements."""

    @staticmethod
    def matches_text(sentence_text: str, value: str) -> bool:
        """Checks whether a vocabulary term value occurs with whole-word boundary in sentence text.

        Args:
            sentence_text (str): Plain text of the sentence.
            value (str): Vocabulary word or expression to match.

        Returns:
            bool: True if matched with whole word boundary, False otherwise.

        Example:
            >>> TermMarkerHelper.matches_text("He made a great discovery.", "discovery")
            True
            >>> TermMarkerHelper.matches_text("He made a great discovery.", "discover")
            False
        """
        pattern = rf"\b{re.escape(value)}\b"
        return bool(re.search(pattern, sentence_text, re.IGNORECASE))

    @classmethod
    def insert(
        cls,
        content_html: str,
        sentence_id: uuid.UUID | str,
        term_id: uuid.UUID | str,
        value: str,
        first_only: bool = False,
    ) -> str:
        """Wraps occurrences of value inside span[data-sentence-id] with span[data-term-id].

        Args:
            content_html (str): Raw or sanitized article HTML.
            sentence_id (uuid.UUID | str): UUID identifier of the enclosing sentence span.
            term_id (uuid.UUID | str): UUID identifier of the vocabulary term.
            value (str): Word or expression to mark.
            first_only (bool, optional): If True, only wraps the first occurrence. Defaults to False.

        Returns:
            str: Annotated HTML string with data-term-id span elements.

        Example:
            >>> s_id = "11111111-1111-1111-1111-111111111111"
            >>> t_id = "22222222-2222-2222-2222-222222222222"
            >>> html = f'<p><span data-sentence-id="{s_id}">A discovery is made.</span></p>'
            >>> res = TermMarkerHelper.insert(html, s_id, t_id, "discovery")
            >>> f'data-term-id="{t_id}"' in res
            True
        """
        soup = BeautifulSoup(content_html, "html.parser")
        s_str = str(sentence_id)
        t_str = str(term_id)

        sentence_tag = soup.find(attrs={"data-sentence-id": s_str})
        if not sentence_tag or not isinstance(sentence_tag, Tag):
            return content_html

        # Check if already has this term
        if sentence_tag.find(attrs={"data-term-id": t_str}):
            return content_html

        pattern = re.compile(rf"\b({re.escape(value)})\b", re.IGNORECASE)

        marked_any = False
        # Iterate over text nodes inside sentence
        for text_node in list(sentence_tag.find_all(string=True)):
            if first_only and marked_any:
                break

            # Don't annotate if already inside a term marker
            if text_node.parent and text_node.parent.has_attr("data-term-id"):
                continue

            node_text = str(text_node)
            matches = list(pattern.finditer(node_text))
            if not matches:
                continue

            # Split node_text by matches and insert tags
            last_idx = 0
            replacement_nodes = []
            for m in matches:
                if first_only and marked_any:
                    break
                start, end = m.span()
                if start > last_idx:
                    replacement_nodes.append(NavigableString(node_text[last_idx:start]))
                matched_text = m.group(1)
                term_span = soup.new_tag("span", attrs={"data-term-id": t_str})
                term_span.string = matched_text
                replacement_nodes.append(term_span)
                last_idx = end
                marked_any = True

            if last_idx < len(node_text):
                replacement_nodes.append(NavigableString(node_text[last_idx:]))

            # Replace node with replacement nodes
            for r_node in replacement_nodes:
                text_node.insert_before(r_node)
            text_node.extract()

        return str(soup).strip()

    @classmethod
    def insert_first(
        cls,
        content_html: str,
        sentence_id: uuid.UUID | str,
        term_id: uuid.UUID | str,
        value: str,
    ) -> str:
        """Inserts a data-term-id marker for only the first valid occurrence of a term.

        Args:
            content_html (str): Raw or sanitized article HTML.
            sentence_id (uuid.UUID | str): UUID identifier of the enclosing sentence span.
            term_id (uuid.UUID | str): UUID identifier of the vocabulary term.
            value (str): Word or expression to mark.

        Returns:
            str: Annotated HTML string.

        Example:
            >>> s_id = "11111111-1111-1111-1111-111111111111"
            >>> t_id = "22222222-2222-2222-2222-222222222222"
            >>> html = f'<p><span data-sentence-id="{s_id}">Test test test.</span></p>'
            >>> res = TermMarkerHelper.insert_first(html, s_id, t_id, "Test")
            >>> res.count(f'data-term-id="{t_id}"')
            1
        """
        return cls.insert(content_html, sentence_id, term_id, value, first_only=True)

    @classmethod
    def replace(
        cls,
        content_html: str,
        term_id: uuid.UUID | str,
        new_value: str,
    ) -> str:
        """Updates the inner text of all span[data-term-id] elements for the given term ID.

        Args:
            content_html (str): HTML content containing markers.
            term_id (uuid.UUID | str): Term identifier to update.
            new_value (str): Replacement text value.

        Returns:
            str: Updated HTML content.

        Example:
            >>> t_id = "22222222-2222-2222-2222-222222222222"
            >>> html = f'<p><span data-term-id="{t_id}">old</span></p>'
            >>> TermMarkerHelper.replace(html, t_id, "new")
            '<p><span data-term-id="22222222-2222-2222-2222-222222222222">new</span></p>'
        """
        soup = BeautifulSoup(content_html, "html.parser")
        t_str = str(term_id)
        for tag in soup.find_all(attrs={"data-term-id": t_str}):
            tag.string = new_value
        return str(soup).strip()

    @classmethod
    def unwrap(
        cls,
        content_html: str,
        term_id: uuid.UUID | str,
    ) -> str:
        """Unwraps span[data-term-id] without removing inner text.

        Args:
            content_html (str): HTML content containing markers.
            term_id (uuid.UUID | str): Term identifier whose marker spans should be unwrapped.

        Returns:
            str: Cleaned HTML string without the target term markers.

        Example:
            >>> t_id = "22222222-2222-2222-2222-222222222222"
            >>> html = f'<p><span data-term-id="{t_id}">discovery</span></p>'
            >>> TermMarkerHelper.unwrap(html, t_id)
            '<p>discovery</p>'
        """
        soup = BeautifulSoup(content_html, "html.parser")
        t_str = str(term_id)
        for tag in soup.find_all(attrs={"data-term-id": t_str}):
            tag.unwrap()
        return str(soup).strip()
