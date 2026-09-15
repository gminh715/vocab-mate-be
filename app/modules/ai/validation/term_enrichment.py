"""Validation and parsing logic for contextual term enrichment."""

from typing import Any

from app.modules.ai.contracts import (
    CEFR_LEVELS,
    TermEnrichmentInput,
    TermEnrichmentResult,
    TermExample,
)
from app.modules.ai.errors import AiError, ProviderCallError

TERM_ENRICHMENT_OUTPUT_LIMITS = {
    "termText": 200,
    "partOfSpeech": 100,
    "enrichmentText": 2000,
    "contextualMeaningWords": 6,
    "ipa": 100,
    "listItems": 8,
    "listItemText": 200,
    "examples": 2,
    "exampleSentence": 500,
    "exampleTranslation": 1000,
    "sentenceTranslation": 5000,
}


def _fail_input(field: str) -> None:
    raise AiError("INVALID_INPUT", f"Invalid AI input: {field}")


def _fail_output(field: str) -> None:
    raise ProviderCallError("unusable-output")


def _record_value(value: Any, expected_keys: list[str], boundary: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        if boundary == "input":
            _fail_input("record")
        _fail_output("record")
    actual_keys = sorted(value.keys())
    exp_keys = sorted(expected_keys)
    if actual_keys != exp_keys:
        if boundary == "input":
            _fail_input("keys")
        _fail_output("keys")
    return value


def _string_value(value: Any, maximum: int, boundary: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        if boundary == "input":
            _fail_input(field)
        _fail_output(field)
    return value


def _nullable_string_value(value: Any, maximum: int, boundary: str, field: str) -> str | None:
    if value is None:
        return None
    return _string_value(value, maximum, boundary, field)


def _string_array_value(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or len(value) > TERM_ENRICHMENT_OUTPUT_LIMITS["listItems"]:
        _fail_output(field)
    strings: list[str] = []
    for idx, item in enumerate(value):
        s = _string_value(item, TERM_ENRICHMENT_OUTPUT_LIMITS["listItemText"], "output", f"{field}[{idx}]")
        strings.append(s)
    unique = {s.strip().lower() for s in strings}
    if len(unique) != len(strings):
        _fail_output(field)
    return strings


def validate_term_enrichment_input(input_data: TermEnrichmentInput | dict[str, Any]) -> None:
    """Validates caller-supplied input parameters before dispatching term enrichment."""
    data = input_data.model_dump(by_alias=True) if isinstance(input_data, TermEnrichmentInput) else input_data
    val = _record_value(
        data,
        [
            "articleId",
            "articleTitle",
            "termId",
            "value",
            "lemma",
            "parentSentenceText",
            "surroundingSentenceContext",
        ],
        "input",
    )
    _string_value(val.get("articleId"), 128, "input", "articleId")
    _string_value(val.get("articleTitle"), 500, "input", "articleTitle")
    _string_value(val.get("termId"), 128, "input", "termId")
    surface_val = _string_value(val.get("value"), 200, "input", "value")
    _string_value(val.get("lemma"), 200, "input", "lemma")
    sentence = _string_value(val.get("parentSentenceText"), 10000, "input", "parentSentenceText")
    _string_value(val.get("surroundingSentenceContext"), 4000, "input", "surroundingSentenceContext")

    if surface_val not in sentence:
        _fail_input("value")


def parse_term_enrichment_result(raw: Any) -> TermEnrichmentResult:
    """Parses and validates raw JSON output from the AI provider into a TermEnrichmentResult."""
    result = _record_value(
        raw,
        [
            "partOfSpeech",
            "cefrLevel",
            "contextualMeaningVi",
            "definitionEn",
            "contextualExplanation",
            "ipa",
            "synonyms",
            "antonyms",
            "collocations",
            "relatedTerms",
            "examples",
            "sentenceTranslationVi",
        ],
        "output",
    )

    raw_examples = result.get("examples")
    if not isinstance(raw_examples, list) or len(raw_examples) > TERM_ENRICHMENT_OUTPUT_LIMITS["examples"]:
        _fail_output("examples")

    parsed_examples: list[TermExample] = []
    for idx, eg in enumerate(raw_examples):
        eg_dict = _record_value(eg, ["sentence", "translationVi"], "output")
        sentence = _string_value(
            eg_dict.get("sentence"),
            TERM_ENRICHMENT_OUTPUT_LIMITS["exampleSentence"],
            "output",
            f"examples[{idx}].sentence",
        )
        trans = _string_value(
            eg_dict.get("translationVi"),
            TERM_ENRICHMENT_OUTPUT_LIMITS["exampleTranslation"],
            "output",
            f"examples[{idx}].translationVi",
        )
        parsed_examples.append(TermExample(sentence=sentence, translationVi=trans))

    unique_egs = {eg.sentence.strip().lower() for eg in parsed_examples}
    if len(unique_egs) != len(parsed_examples):
        _fail_output("examples")

    contextual_meaning_vi = _string_value(
        result.get("contextualMeaningVi"),
        TERM_ENRICHMENT_OUTPUT_LIMITS["enrichmentText"],
        "output",
        "contextualMeaningVi",
    )
    if (
        "," in contextual_meaning_vi
        or len(contextual_meaning_vi.strip().split()) > TERM_ENRICHMENT_OUTPUT_LIMITS["contextualMeaningWords"]
    ):
        _fail_output("contextualMeaningVi")

    cefr = result.get("cefrLevel")
    if cefr not in CEFR_LEVELS:
        _fail_output("cefrLevel")

    part_of_speech = (
        _string_value(
            result.get("partOfSpeech"),
            TERM_ENRICHMENT_OUTPUT_LIMITS["partOfSpeech"],
            "output",
            "partOfSpeech",
        )
        .strip()
        .lower()
    )

    definition_en = _string_value(
        result.get("definitionEn"),
        TERM_ENRICHMENT_OUTPUT_LIMITS["enrichmentText"],
        "output",
        "definitionEn",
    )
    contextual_explanation = _string_value(
        result.get("contextualExplanation"),
        TERM_ENRICHMENT_OUTPUT_LIMITS["enrichmentText"],
        "output",
        "contextualExplanation",
    )
    ipa = _nullable_string_value(
        result.get("ipa"),
        TERM_ENRICHMENT_OUTPUT_LIMITS["ipa"],
        "output",
        "ipa",
    )
    synonyms = _string_array_value(result.get("synonyms"), "synonyms")
    antonyms = _string_array_value(result.get("antonyms"), "antonyms")
    collocations = _string_array_value(result.get("collocations"), "collocations")
    related_terms = _string_array_value(result.get("relatedTerms"), "relatedTerms")
    sentence_trans = _string_value(
        result.get("sentenceTranslationVi"),
        TERM_ENRICHMENT_OUTPUT_LIMITS["sentenceTranslation"],
        "output",
        "sentenceTranslationVi",
    )

    return TermEnrichmentResult(
        partOfSpeech=part_of_speech,
        cefrLevel=cefr,
        contextualMeaningVi=contextual_meaning_vi,
        definitionEn=definition_en,
        contextualExplanation=contextual_explanation,
        ipa=ipa,
        synonyms=synonyms,
        antonyms=antonyms,
        collocations=collocations,
        relatedTerms=related_terms,
        examples=parsed_examples,
        sentenceTranslationVi=sentence_trans,
    )
