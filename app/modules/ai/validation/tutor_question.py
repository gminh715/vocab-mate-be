"""Validation and parsing logic for adaptive AI tutor questions."""

from typing import Any

from app.modules.ai.contracts import (
    OPTION_IDS,
    RETEST_TYPES,
    TUTOR_QUESTION_TYPES,
    ContextualClozeResult,
    McOption,
    MicroLessonRetestResult,
    MultipleChoiceResult,
    TutorQuestionInput,
    TutorQuestionResult,
    TutorQuestionType,
    TypedRecallResult,
)
from app.modules.ai.errors import AiError, ProviderCallError

TUTOR_QUESTION_LIMITS = {
    "candidateList": 50,
    "allowlist": 50,
    "id": 128,
    "wordDisplay": 200,
    "lemma": 200,
    "partOfSpeech": 100,
    "meaningVi": 500,
    "questionPromptVi": 500,
    "explanationVi": 1000,
    "feedbackVi": 500,
    "optionText": 300,
    "sentenceWithBlank": 1000,
    "recallPromptVi": 500,
    "microLessonTitle": 300,
    "microLessonFactEn": 1500,
    "microLessonFactVi": 1500,
    "microLessonVi": 2000,
    "canonicalAnswer": 200,
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


def _optional_string_value(value: Any, maximum: int, field: str) -> str | None:
    if value is None:
        return None
    return _string_value(value, maximum, "output", field)


def validate_tutor_question_input(input_data: TutorQuestionInput | dict[str, Any]) -> None:
    """Validates caller-supplied input parameters before dispatching tutor question generation."""
    data = input_data.model_dump(by_alias=True) if isinstance(input_data, TutorQuestionInput) else input_data
    val = _record_value(data, ["allowlistIds", "candidates", "questionType"], "input")

    raw_allowlist = val.get("allowlistIds")
    if (
        not isinstance(raw_allowlist, list)
        or len(raw_allowlist) == 0
        or len(raw_allowlist) > TUTOR_QUESTION_LIMITS["allowlist"]
    ):
        _fail_input("allowlistIds")

    allowlist_set: set[str] = set()
    for idx, a_id in enumerate(raw_allowlist):
        s_id = _string_value(a_id, TUTOR_QUESTION_LIMITS["id"], "input", f"allowlistIds[{idx}]")
        allowlist_set.add(s_id)

    q_type = val.get("questionType")
    if q_type not in TUTOR_QUESTION_TYPES:
        _fail_input("questionType")

    raw_candidates = val.get("candidates")
    if (
        not isinstance(raw_candidates, list)
        or len(raw_candidates) == 0
        or len(raw_candidates) > TUTOR_QUESTION_LIMITS["candidateList"]
    ):
        _fail_input("candidates")

    for idx, cand in enumerate(raw_candidates):
        cand_dict = _record_value(
            cand,
            ["id", "wordDisplay", "lemma", "partOfSpeech", "meaningVi", "examples"],
            "input",
        )
        c_id = _string_value(cand_dict.get("id"), TUTOR_QUESTION_LIMITS["id"], "input", f"candidates[{idx}].id")
        if c_id not in allowlist_set:
            _fail_input(f"candidates[{idx}].id")
        _string_value(
            cand_dict.get("wordDisplay"),
            TUTOR_QUESTION_LIMITS["wordDisplay"],
            "input",
            f"candidates[{idx}].wordDisplay",
        )
        _string_value(cand_dict.get("lemma"), TUTOR_QUESTION_LIMITS["lemma"], "input", f"candidates[{idx}].lemma")
        _string_value(
            cand_dict.get("partOfSpeech"),
            TUTOR_QUESTION_LIMITS["partOfSpeech"],
            "input",
            f"candidates[{idx}].partOfSpeech",
        )
        _string_value(
            cand_dict.get("meaningVi"), TUTOR_QUESTION_LIMITS["meaningVi"], "input", f"candidates[{idx}].meaningVi"
        )


def parse_tutor_question_result(
    raw: Any,
    allowlist_ids: list[str],
    expected_type: TutorQuestionType,
) -> TutorQuestionResult:
    """Parses and validates raw JSON output from the AI provider into a TutorQuestionResult."""
    result = _record_value(
        raw,
        [
            "selectedCandidateId",
            "questionType",
            "questionPromptVi",
            "explanationVi",
            "feedbackCorrectVi",
            "feedbackIncorrectVi",
            "options",
            "correctOptionId",
            "sentenceWithBlank",
            "recallPromptVi",
            "microLessonTitle",
            "microLessonFactEn",
            "microLessonFactVi",
            "microLessonVi",
            "retestType",
            "canonicalAnswer",
        ],
        "output",
    )

    selected_candidate_id = _string_value(
        result.get("selectedCandidateId"),
        TUTOR_QUESTION_LIMITS["id"],
        "output",
        "selectedCandidateId",
    )
    if selected_candidate_id not in allowlist_ids:
        _fail_output("selectedCandidateId")

    q_type = result.get("questionType")
    if q_type != expected_type:
        _fail_output("questionType")

    question_prompt_vi = _string_value(
        result.get("questionPromptVi"),
        TUTOR_QUESTION_LIMITS["questionPromptVi"],
        "output",
        "questionPromptVi",
    )
    explanation_vi = _string_value(
        result.get("explanationVi"),
        TUTOR_QUESTION_LIMITS["explanationVi"],
        "output",
        "explanationVi",
    )
    feedback_correct_vi = _string_value(
        result.get("feedbackCorrectVi"),
        TUTOR_QUESTION_LIMITS["feedbackVi"],
        "output",
        "feedbackCorrectVi",
    )
    feedback_incorrect_vi = _string_value(
        result.get("feedbackIncorrectVi"),
        TUTOR_QUESTION_LIMITS["feedbackVi"],
        "output",
        "feedbackIncorrectVi",
    )

    base_kwargs = {
        "selectedCandidateId": selected_candidate_id,
        "questionPromptVi": question_prompt_vi,
        "explanationVi": explanation_vi,
        "feedbackCorrectVi": feedback_correct_vi,
        "feedbackIncorrectVi": feedback_incorrect_vi,
    }

    if q_type == "MULTIPLE_CHOICE":
        raw_options = result.get("options")
        if not isinstance(raw_options, list) or len(raw_options) != 4:
            _fail_output("options")

        options: list[McOption] = []
        for idx, opt in enumerate(raw_options):
            opt_dict = _record_value(opt, ["id", "text"], "output")
            o_id = opt_dict.get("id")
            if o_id not in OPTION_IDS:
                _fail_output(f"options[{idx}].id")
            text = _string_value(
                opt_dict.get("text"), TUTOR_QUESTION_LIMITS["optionText"], "output", f"options[{idx}].text"
            )
            options.append(McOption(id=o_id, text=text))

        option_ids = {o.id for o in options}
        if len(option_ids) != 4 or not all(expected in option_ids for expected in OPTION_IDS):
            _fail_output("options.ids")

        correct_id = result.get("correctOptionId")
        if correct_id not in OPTION_IDS:
            _fail_output("correctOptionId")

        return MultipleChoiceResult(
            **base_kwargs,
            questionType="MULTIPLE_CHOICE",
            options=options,
            correctOptionId=correct_id,
        )

    if q_type == "CONTEXTUAL_CLOZE":
        sentence_with_blank = _string_value(
            result.get("sentenceWithBlank"),
            TUTOR_QUESTION_LIMITS["sentenceWithBlank"],
            "output",
            "sentenceWithBlank",
        )
        if "___" not in sentence_with_blank:
            _fail_output("sentenceWithBlank")

        canonical_ans = _string_value(
            result.get("canonicalAnswer"),
            TUTOR_QUESTION_LIMITS["canonicalAnswer"],
            "output",
            "canonicalAnswer",
        )

        return ContextualClozeResult(
            **base_kwargs,
            questionType="CONTEXTUAL_CLOZE",
            sentenceWithBlank=sentence_with_blank,
            canonicalAnswer=canonical_ans,
        )

    if q_type == "TYPED_RECALL":
        recall_prompt_vi = _string_value(
            result.get("recallPromptVi"),
            TUTOR_QUESTION_LIMITS["recallPromptVi"],
            "output",
            "recallPromptVi",
        )
        canonical_ans = _string_value(
            result.get("canonicalAnswer"),
            TUTOR_QUESTION_LIMITS["canonicalAnswer"],
            "output",
            "canonicalAnswer",
        )

        return TypedRecallResult(
            **base_kwargs,
            questionType="TYPED_RECALL",
            recallPromptVi=recall_prompt_vi,
            canonicalAnswer=canonical_ans,
        )

    if q_type == "MICRO_LESSON_RETEST":
        micro_title = _optional_string_value(
            result.get("microLessonTitle"), TUTOR_QUESTION_LIMITS["microLessonTitle"], "microLessonTitle"
        )
        micro_fact_en = _optional_string_value(
            result.get("microLessonFactEn"), TUTOR_QUESTION_LIMITS["microLessonFactEn"], "microLessonFactEn"
        )
        micro_fact_vi = _optional_string_value(
            result.get("microLessonFactVi"), TUTOR_QUESTION_LIMITS["microLessonFactVi"], "microLessonFactVi"
        )

        raw_micro_lesson_vi = result.get("microLessonVi")
        if isinstance(raw_micro_lesson_vi, str) and raw_micro_lesson_vi.strip():
            micro_lesson_vi = _string_value(
                raw_micro_lesson_vi, TUTOR_QUESTION_LIMITS["microLessonVi"], "output", "microLessonVi"
            )
        elif micro_fact_vi:
            micro_lesson_vi = micro_fact_vi
        else:
            micro_lesson_vi = _string_value(
                raw_micro_lesson_vi, TUTOR_QUESTION_LIMITS["microLessonVi"], "output", "microLessonVi"
            )

        retest_type = result.get("retestType")
        if retest_type not in RETEST_TYPES:
            _fail_output("retestType")

        canonical_ans = _string_value(
            result.get("canonicalAnswer"),
            TUTOR_QUESTION_LIMITS["canonicalAnswer"],
            "output",
            "canonicalAnswer",
        )

        if retest_type == "CONTEXTUAL_CLOZE":
            sentence_with_blank = _string_value(
                result.get("sentenceWithBlank"),
                TUTOR_QUESTION_LIMITS["sentenceWithBlank"],
                "output",
                "sentenceWithBlank",
            )
            if "___" not in sentence_with_blank:
                _fail_output("sentenceWithBlank")

            return MicroLessonRetestResult(
                **base_kwargs,
                questionType="MICRO_LESSON_RETEST",
                microLessonTitle=micro_title,
                microLessonFactEn=micro_fact_en,
                microLessonFactVi=micro_fact_vi,
                microLessonVi=micro_lesson_vi,
                retestType="CONTEXTUAL_CLOZE",
                sentenceWithBlank=sentence_with_blank,
                canonicalAnswer=canonical_ans,
            )

        recall_prompt_vi = _string_value(
            result.get("recallPromptVi"),
            TUTOR_QUESTION_LIMITS["recallPromptVi"],
            "output",
            "recallPromptVi",
        )
        return MicroLessonRetestResult(
            **base_kwargs,
            questionType="MICRO_LESSON_RETEST",
            microLessonTitle=micro_title,
            microLessonFactEn=micro_fact_en,
            microLessonFactVi=micro_fact_vi,
            microLessonVi=micro_lesson_vi,
            retestType="TYPED_RECALL",
            recallPromptVi=recall_prompt_vi,
            canonicalAnswer=canonical_ans,
        )

    _fail_output("questionType")
