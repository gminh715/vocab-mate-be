"""CEFR readability grade calculation and lexical complexity analysis helper."""

import json
import math
import re
from pathlib import Path

from nltk import pos_tag, word_tokenize
from nltk.stem import WordNetLemmatizer

from app.models.enums import CefrLevel

DICT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "common" / "data" / "cefr_dict.json"

_CEFR_DICT: dict[str, str] | None = None
_LEMMATIZER = WordNetLemmatizer()

WEIGHTS: dict[str, float] = {
    "A1": 1.0,
    "A2": 2.0,
    "B1": 3.5,
    "B2": 5.0,
    "C1": 7.0,
    "C2": 9.5,
}

ENGLISH_WORD_REGEX = re.compile(r"^[A-Za-z]+(?:['’][A-Za-z]+)*$")


def get_cefr_dict() -> dict[str, str]:
    """Loads and caches CEFR dictionary mappings from disk.

    Returns:
        dict[str, str]: Mapping of English words/lemmas to CEFR level codes.

    Example:
        >>> d = get_cefr_dict()
        >>> isinstance(d, dict)
        True
    """
    global _CEFR_DICT
    if _CEFR_DICT is None:
        if DICT_PATH.exists():
            _CEFR_DICT = json.loads(DICT_PATH.read_text(encoding="utf-8"))
        else:
            _CEFR_DICT = {}
    return _CEFR_DICT


def _get_wordnet_pos(treebank_tag: str) -> str:
    """Maps Penn Treebank grammatical tag to WordNet part-of-speech category.

    Args:
        treebank_tag (str): Penn Treebank tag identifier (e.g. ``NN``, ``VBD``, ``JJ``).

    Returns:
        str: Single character WordNet POS code (``n``, ``v``, ``a``, or ``r``).

    Example:
        >>> _get_wordnet_pos("VB")
        'v'
        >>> _get_wordnet_pos("NN")
        'n'
    """
    if treebank_tag.startswith("J"):
        return "a"
    elif treebank_tag.startswith("V"):
        return "v"
    elif treebank_tag.startswith("N"):
        return "n"
    elif treebank_tag.startswith("R"):
        return "r"
    return "n"


def lemmatize_word(word: str, pos: str = "n") -> str:
    """Lemmatizes an English word to its base canonical form.

    Args:
        word (str): Surface form of the word.
        pos (str, optional): WordNet POS tag. Defaults to "n".

    Returns:
        str: Lemmatized lowercase base form.

    Example:
        >>> lemmatize_word("running", "v")
        'run'
        >>> lemmatize_word("particles", "n")
        'particle'
    """
    try:
        return _LEMMATIZER.lemmatize(word.lower(), pos=pos)
    except Exception:
        return word.lower()


class CefrAnalyzerHelper:
    """Calculates CEFR readability grade and maps vocabulary words to CEFR levels.

    Example:
        >>> lvl, terms, score = CefrAnalyzerHelper.evaluate_text("This is an easy sentence.")
        >>> isinstance(lvl, CefrLevel)
        True
    """

    @classmethod
    def evaluate_text(cls, text: str) -> tuple[CefrLevel, dict[str, CefrLevel], float]:
        """Analyzes text and returns overall CEFR level, term levels dictionary, and score.

        Args:
            text (str): Plain text to analyze.

        Returns:
            tuple[CefrLevel, dict[str, CefrLevel], float]: Tuple of assessed CEFR level, dictionary
                mapping recognized words to CEFR levels, and raw difficulty score.

        Example:
            >>> lvl, terms, score = CefrAnalyzerHelper.evaluate_text("Hello world.")
            >>> lvl
            <CefrLevel.A1: 'A1'>
        """
        cefr_map = get_cefr_dict()
        tokens = word_tokenize(text)
        tagged = pos_tag(tokens)

        word_counts: dict[str, int] = {}
        level_counts: dict[str, int] = {k: 0 for k in WEIGHTS}
        term_levels: dict[str, CefrLevel] = {}

        total_words = 0
        for raw_word, tag in tagged:
            if not ENGLISH_WORD_REGEX.match(raw_word):
                continue
            wn_pos = _get_wordnet_pos(tag)
            lemma = lemmatize_word(raw_word, wn_pos)
            total_words += 1
            word_counts[lemma] = word_counts.get(lemma, 0) + 1

            # Lookup CEFR
            lvl_str = cefr_map.get(lemma) or cefr_map.get(raw_word.lower())
            if lvl_str and lvl_str in level_counts:
                level_counts[lvl_str] += 1
                term_levels[raw_word.lower()] = CefrLevel(lvl_str)
                term_levels[lemma] = CefrLevel(lvl_str)

        if total_words == 0:
            return CefrLevel.A1, {}, 1.0

        # Calculate percentages
        level_pcts = {lvl: (count / total_words) * 100 for lvl, count in level_counts.items()}

        # Base weighted score
        base_score = sum((level_pcts[lvl] * WEIGHTS[lvl]) for lvl in WEIGHTS) / 100.0

        short_penalty = ((30 - total_words) / 30.0) * 0.5 if total_words < 30 else 0.0
        if total_words < 10:
            adjusted = max(0.0, base_score - short_penalty)
            return cls._score_to_cefr(adjusted), term_levels, round(adjusted, 2)

        long_bonus = min(1.0, math.log(max(1, total_words - 50)) / 10.0)
        adjusted = max(0.0, base_score + long_bonus - short_penalty)
        score = round(adjusted, 2)

        return cls._score_to_cefr(score), term_levels, score

    @staticmethod
    def _score_to_cefr(score: float) -> CefrLevel:
        """Converts numerical difficulty score into a discrete CEFR rating level.

        Args:
            score (float): Calculated numerical difficulty metric.

        Returns:
            CefrLevel: Corresponding CEFR level grade.

        Example:
            >>> CefrAnalyzerHelper._score_to_cefr(1.0)
            <CefrLevel.A1: 'A1'>
            >>> CefrAnalyzerHelper._score_to_cefr(2.5)
            <CefrLevel.B2: 'B2'>
        """
        if score < 1.2:
            return CefrLevel.A1
        elif score < 1.7:
            return CefrLevel.A2
        elif score < 2.2:
            return CefrLevel.B1
        elif score < 2.8:
            return CefrLevel.B2
        elif score < 3.5:
            return CefrLevel.C1
        return CefrLevel.C2
