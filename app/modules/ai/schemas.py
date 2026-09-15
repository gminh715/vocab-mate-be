"""Strict JSON Schemas enforced on external LLM generation."""

from typing import Any

from app.modules.ai.contracts import (
    CEFR_LEVELS,
    OPTION_IDS,
    RETEST_TYPES,
    TUTOR_QUESTION_TYPES,
)


def _required_string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _nullable_string(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


def _strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
    }


def _bounded_string_array(description: str, max_items: int = 8) -> dict[str, Any]:
    return {
        "type": "array",
        "maxItems": max_items,
        "description": description,
        "items": {"type": "string"},
    }


term_enrichment_schema: dict[str, Any] = _strict_object(
    {
        "partOfSpeech": _required_string("Part of speech in this sentence context."),
        "cefrLevel": {
            "type": "string",
            "enum": list(CEFR_LEVELS),
            "description": "CEFR difficulty of this contextual term.",
        },
        "contextualMeaningVi": _required_string(
            "One concise Vietnamese meaning in this exact sentence context (strictly 1 to 6 words, without commas)."
        ),
        "definitionEn": _required_string("A concise English definition."),
        "contextualExplanation": _required_string("A concise explanation of how the term works in this context."),
        "ipa": {"type": ["string", "null"], "description": "IPA pronunciation."},
        "synonyms": _bounded_string_array("Contextually relevant synonyms."),
        "antonyms": _bounded_string_array("Contextually relevant antonyms."),
        "collocations": _bounded_string_array("Useful collocations."),
        "relatedTerms": _bounded_string_array("Closely related vocabulary."),
        "examples": {
            "type": "array",
            "maxItems": 2,
            "items": _strict_object(
                {
                    "sentence": _required_string("A natural English example sentence."),
                    "translationVi": _required_string("Vietnamese translation of the example."),
                }
            ),
        },
        "sentenceTranslationVi": _required_string("Vietnamese translation of the supplied parent sentence."),
    }
)

tutor_question_schema: dict[str, Any] = _strict_object(
    {
        "selectedCandidateId": _required_string(
            "The ID of the chosen vocabulary candidate from the provided candidates list."
        ),
        "questionType": {
            "type": "string",
            "enum": list(TUTOR_QUESTION_TYPES),
            "description": "Question type for this tutor activity.",
        },
        "questionPromptVi": _required_string("Instruction or question prompt displayed to the learner in Vietnamese."),
        "explanationVi": _required_string(
            "Detailed explanation in Vietnamese of the vocabulary item and correct answer."
        ),
        "feedbackCorrectVi": _required_string(
            "Short encouraging feedback in Vietnamese when learner answers correctly."
        ),
        "feedbackIncorrectVi": _required_string(
            "Short constructive feedback in Vietnamese when learner answers incorrectly."
        ),
        "options": {
            "type": "array",
            "maxItems": 4,
            "items": _strict_object(
                {
                    "id": {
                        "type": "string",
                        "enum": list(OPTION_IDS),
                        "description": "Option identifier (A, B, C, D).",
                    },
                    "text": _required_string("Option text."),
                }
            ),
            "description": "Exactly 4 options for MULTIPLE_CHOICE, or empty array if not applicable.",
        },
        "correctOptionId": {
            "type": ["string", "null"],
            "enum": list(OPTION_IDS) + [None],
            "description": "The correct option ID (A, B, C, D) for MULTIPLE_CHOICE, or null if not applicable.",
        },
        "sentenceWithBlank": _nullable_string(
            'The English sentence containing "___" for CONTEXTUAL_CLOZE or cloze retest, or null.'
        ),
        "recallPromptVi": _nullable_string(
            "Prompt in Vietnamese asking for recall of the English word for TYPED_RECALL or recall retest, or null."
        ),
        "microLessonTitle": _nullable_string(
            "A short catchy title in English or Vietnamese for the interesting fact in MICRO_LESSON_RETEST, or null."
        ),
        "microLessonFactEn": _nullable_string(
            "A 2-4 sentence interesting fact reading passage in English (<80 words) naturally embedding the target vocabulary word for MICRO_LESSON_RETEST, or null."
        ),
        "microLessonFactVi": _nullable_string(
            "Natural Vietnamese translation of the fact reading passage for MICRO_LESSON_RETEST, or null."
        ),
        "microLessonVi": _nullable_string(
            "A concise lesson/summary (<150 words) in Vietnamese for MICRO_LESSON_RETEST, or null."
        ),
        "retestType": {
            "type": ["string", "null"],
            "enum": list(RETEST_TYPES) + [None],
            "description": "Question type for the retest in MICRO_LESSON_RETEST, or null.",
        },
        "canonicalAnswer": _nullable_string(
            "The exact canonical answer string for cloze, typed recall, or retest, or null."
        ),
    }
)

session_warmup_schema: dict[str, Any] = _strict_object(
    {
        "facts": {
            "type": "array",
            "description": "List of 1 to 3 intriguing real-world fact stories in natural Vietnamese embedding the target vocabulary words.",
            "items": _strict_object(
                {
                    "title": {
                        "type": "string",
                        "description": "An intriguing 3 to 7 word title in Vietnamese.",
                    },
                    "factContentVi": {
                        "type": "string",
                        "description": 'A fascinating real-world fact/trivia passage (40-100 words) in natural Vietnamese, embedding the English words in bold markdown followed by parentheses: "**word** (nghĩa tiếng Việt)".',
                    },
                    "targetWords": {
                        "type": "array",
                        "description": "The English vocabulary words woven into this fact story.",
                        "items": {"type": "string"},
                    },
                }
            ),
        },
    }
)
