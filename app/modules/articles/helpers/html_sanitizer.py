"""HTML sanitization helper module enforcing clean and safe reader HTML content."""

import re

from bs4 import BeautifulSoup, Comment, Tag

ALLOWED_TAGS = {
    "p",
    "div",
    "span",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "mark",
    "br",
    "hr",
    "a",
    "img",
    "figure",
    "figcaption",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "pre",
    "code",
}

ALLOWED_GLOBAL_ATTRS = {"data-sentence-id", "data-term-id"}

ALLOWED_ATTRS: dict[str, set[str]] = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "p": {"style"},
    "h1": {"style"},
    "h2": {"style"},
    "h3": {"style"},
    "h4": {"style"},
    "h5": {"style"},
    "h6": {"style"},
    "th": {"colspan", "rowspan", "scope"},
    "td": {"colspan", "rowspan"},
}

ALLOWED_SCHEMES = ("http://", "https://", "mailto:")
TEXT_ALIGN_REGEX = re.compile(r"^text-align:\s*(left|center|right|justify);?$", re.IGNORECASE)


class HtmlSanitizerHelper:
    """Strict HTML sanitization policy permitting safe reader tags while stripping scripts.

    Example:
        >>> HtmlSanitizerHelper.sanitize("<p>Hello <script>alert(1)</script>World</p>")
        '<p>Hello World</p>'
    """

    @classmethod
    def sanitize(cls, html_content: str) -> str:
        """Strips unallowed HTML tags, attributes, and styles according to the article policy.

        Args:
            html_content (str): Raw HTML content from draft editor or news provider.

        Returns:
            str: Cleaned HTML containing only allowed tags and safe attributes.

        Example:
            >>> HtmlSanitizerHelper.sanitize("<b>Test</b>")
            '<b>Test</b>'
        """
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, "html.parser")

        # Strip comments and unwanted nodes
        for node in soup.find_all(string=lambda t: isinstance(t, Comment)):
            node.extract()

        for tag in soup.find_all(["script", "style", "noscript", "iframe", "object", "embed", "form", "input"]):
            tag.decompose()

        # Sanitize all tags
        for tag in list(soup.find_all(True)):
            if not isinstance(tag, Tag):
                continue

            tag_name = tag.name.lower()
            if tag_name not in ALLOWED_TAGS:
                tag.unwrap()
                continue

            # Check attributes
            tag_allowed_attrs = ALLOWED_ATTRS.get(tag_name, set()) | ALLOWED_GLOBAL_ATTRS
            for attr_name in list(tag.attrs.keys()):
                attr_lower = attr_name.lower()
                if attr_lower not in tag_allowed_attrs:
                    del tag.attrs[attr_name]
                    continue

                attr_val = tag.attrs[attr_name]
                if isinstance(attr_val, list):
                    attr_val = " ".join(attr_val)

                # Protocol validation for urls
                if attr_lower in ("href", "src"):
                    val_lower = str(attr_val).strip().lower()
                    if not any(val_lower.startswith(scheme) for scheme in ALLOWED_SCHEMES):
                        del tag.attrs[attr_name]
                        continue

                # Style validation
                if attr_lower == "style":
                    val_str = str(attr_val).strip()
                    if not TEXT_ALIGN_REGEX.match(val_str):
                        del tag.attrs[attr_name]
                        continue

            # Enforce rel="noopener noreferrer" on <a> tags
            if tag_name == "a":
                tag.attrs["rel"] = "noopener noreferrer"

        return str(soup).strip()
