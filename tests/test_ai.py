"""Tests for the AI Service, validation logic, and lazy term enrichment."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.articles import Article, ArticleSentence, ArticleSentenceTerm
from app.models.categories import Category
from app.models.enums import (
    AiGenerationStatus,
    ArticleStatus,
    CefrLevel,
    TermOrigin,
    TermReviewStatus,
    UserRole,
    UserStatus,
)
from app.models.users import User
from app.modules.ai.contracts import (
    ContextualClozeResult,
    MultipleChoiceResult,
    TermEnrichmentInput,
    TermEnrichmentResult,
    TermExample,
    TutorQuestionCandidate,
    TutorQuestionInput,
)
from app.modules.ai.errors import AiError, ProviderCallError
from app.modules.ai.providers.base import (
    BaseAiProvider,
    StructuredAiResponse,
    TokenUsage,
)
from app.modules.ai.service import AiService
from app.modules.ai.validation.term_enrichment import (
    parse_term_enrichment_result,
    validate_term_enrichment_input,
)
from app.modules.ai.validation.tutor_question import (
    parse_tutor_question_result,
    validate_tutor_question_input,
)
from app.modules.reading.service import ReadingService


def test_term_enrichment_input_validation():
    """Verifies that term enrichment rejects invalid input bounds and absent surface words."""
    valid_input = TermEnrichmentInput(
        articleId="art-1",
        articleTitle="Quantum Leap",
        termId="term-1",
        value="quantum",
        lemma="quantum",
        parentSentenceText="This is a quantum leap in physics.",
        surroundingSentenceContext="This is a quantum leap in physics.",
    )
    # Valid should not raise
    validate_term_enrichment_input(valid_input)

    # Word not in sentence
    invalid_input = TermEnrichmentInput(
        articleId="art-1",
        articleTitle="Quantum Leap",
        termId="term-1",
        value="missingword",
        lemma="missingword",
        parentSentenceText="This is a quantum leap in physics.",
        surroundingSentenceContext="This is a quantum leap in physics.",
    )
    with pytest.raises(AiError) as exc_info:
        validate_term_enrichment_input(invalid_input)
    assert exc_info.value.code == "INVALID_INPUT"


def test_term_enrichment_output_validation():
    """Verifies that term enrichment output rejects commas and words > 6 in contextualMeaningVi."""
    valid_raw = {
        "partOfSpeech": "noun",
        "cefrLevel": "B2",
        "contextualMeaningVi": "bước nhảy vọt",
        "definitionEn": "A sudden large increase or advance.",
        "contextualExplanation": "Used here to denote a major scientific breakthrough.",
        "ipa": "/ˈkwɑːn.təm/",
        "synonyms": ["breakthrough", "advance"],
        "antonyms": ["regression"],
        "collocations": ["quantum leap"],
        "relatedTerms": ["physics"],
        "examples": [
            {
                "sentence": "The new chip represents a quantum leap.",
                "translationVi": "Con chip mới đại diện cho một bước nhảy vọt.",
            }
        ],
        "sentenceTranslationVi": "Đây là một bước nhảy vọt trong vật lý học.",
    }
    result = parse_term_enrichment_result(valid_raw)
    assert isinstance(result, TermEnrichmentResult)
    assert result.contextual_meaning_vi == "bước nhảy vọt"
    assert result.cefr_level == "B2"

    # Reject commas in contextualMeaningVi
    with_comma = dict(valid_raw, contextualMeaningVi="bước nhảy, vọt")
    with pytest.raises(ProviderCallError):
        parse_term_enrichment_result(with_comma)

    # Reject > 6 words
    too_long = dict(valid_raw, contextualMeaningVi="đây là một bước nhảy quá dài và nhiều từ")
    with pytest.raises(ProviderCallError):
        parse_term_enrichment_result(too_long)


def test_tutor_question_validation():
    """Verifies that tutor question validation checks candidates, allowlist, and question types."""
    candidate = TutorQuestionCandidate(
        id="c-1",
        wordDisplay="quantum",
        lemma="quantum",
        partOfSpeech="noun",
        meaningVi="lượng tử",
        examples=None,
    )
    # Valid input
    valid_input = TutorQuestionInput(
        allowlistIds=["c-1"],
        candidates=[candidate],
        questionType="MULTIPLE_CHOICE",
    )
    validate_tutor_question_input(valid_input)

    # Candidate not in allowlist
    invalid_input = TutorQuestionInput(
        allowlistIds=["c-2"],
        candidates=[candidate],
        questionType="MULTIPLE_CHOICE",
    )
    with pytest.raises(AiError) as exc_info:
        validate_tutor_question_input(invalid_input)
    assert exc_info.value.code == "INVALID_INPUT"

    # Parse Multiple Choice result
    raw_mc = {
        "selectedCandidateId": "c-1",
        "questionType": "MULTIPLE_CHOICE",
        "questionPromptVi": "Chọn từ đúng",
        "explanationVi": "Quantum nghĩa là lượng tử",
        "feedbackCorrectVi": "Chính xác!",
        "feedbackIncorrectVi": "Chưa đúng.",
        "options": [
            {"id": "A", "text": "quantum"},
            {"id": "B", "text": "atom"},
            {"id": "C", "text": "molecule"},
            {"id": "D", "text": "particle"},
        ],
        "correctOptionId": "A",
        "sentenceWithBlank": None,
        "recallPromptVi": None,
        "microLessonTitle": None,
        "microLessonFactEn": None,
        "microLessonFactVi": None,
        "microLessonVi": None,
        "retestType": None,
        "canonicalAnswer": None,
    }
    parsed_mc = parse_tutor_question_result(raw_mc, ["c-1"], "MULTIPLE_CHOICE")
    assert isinstance(parsed_mc, MultipleChoiceResult)
    assert parsed_mc.correct_option_id == "A"
    assert len(parsed_mc.options) == 4

    # Parse Contextual Cloze result
    raw_cloze = dict(
        raw_mc,
        questionType="CONTEXTUAL_CLOZE",
        sentenceWithBlank="This is a ___ leap.",
        canonicalAnswer="quantum",
        options=[],
        correctOptionId=None,
    )
    parsed_cloze = parse_tutor_question_result(raw_cloze, ["c-1"], "CONTEXTUAL_CLOZE")
    assert isinstance(parsed_cloze, ContextualClozeResult)
    assert parsed_cloze.canonical_answer == "quantum"


@pytest.mark.asyncio
async def test_ai_service_fallback():
    """Verifies that AiService gracefully falls back from Gemini to Groq on transient errors."""
    mock_gemini = AsyncMock(spec=BaseAiProvider)
    mock_gemini.generate_structured.side_effect = ProviderCallError("timeout")

    valid_json = (
        '{"partOfSpeech":"noun","cefrLevel":"B2","contextualMeaningVi":"bước nhảy vọt",'
        '"definitionEn":"A sudden advance.","contextualExplanation":"Significant step.",'
        '"ipa":null,"synonyms":[],"antonyms":[],"collocations":[],"relatedTerms":[],'
        '"examples":[{"sentence":"A quantum leap.","translationVi":"Một bước nhảy vọt."}],'
        '"sentenceTranslationVi":"Một bước nhảy vọt trong khoa học."}'
    )
    mock_groq = AsyncMock(spec=BaseAiProvider)
    mock_groq.generate_structured.return_value = StructuredAiResponse(
        content=valid_json,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    )

    ai_service = AiService(gemini_provider=mock_gemini, groq_provider=mock_groq)

    input_data = TermEnrichmentInput(
        articleId="art-1",
        articleTitle="Quantum",
        termId="term-1",
        value="quantum",
        lemma="quantum",
        parentSentenceText="This is a quantum leap.",
        surroundingSentenceContext="This is a quantum leap.",
    )

    result = await ai_service.enrich_contextual_term(input_data)
    assert result.contextual_meaning_vi == "bước nhảy vọt"
    assert mock_gemini.generate_structured.call_count == 1
    assert mock_groq.generate_structured.call_count == 1


@pytest.mark.asyncio
async def test_lazy_enrichment_in_reading():
    """Verifies that ReadingService.get_contextual_term triggers lazy enrichment when term is PENDING."""
    rand = str(uuid.uuid4())[:8]
    pwd = "SecurePassword123!"

    async with AsyncSessionLocal() as session:
        # Seed admin and learner
        admin = User(
            id=uuid.uuid4(),
            email=f"admin_{rand}@example.com",
            password_hash=get_password_hash(pwd),
            display_name="Admin",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        learner = User(
            id=uuid.uuid4(),
            email=f"learner_{rand}@example.com",
            password_hash=get_password_hash(pwd),
            display_name="Learner",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            current_cefr_level=CefrLevel.B1,
            learning_goal="B2",
        )
        category = Category(
            id=uuid.uuid4(),
            name=f"Tech {rand}",
            slug=f"tech-{rand}",
            is_active=True,
            display_order=0,
            created_by_user_id=admin.id,
            updated_by_user_id=admin.id,
        )
        article = Article(
            id=uuid.uuid4(),
            category_id=category.id,
            title=f"Quantum Computing {rand}",
            slug=f"quantum-comp-{rand}",
            summary="Quantum summary",
            content_html="<p>Quantum computing is revolutionary.</p>",
            status=ArticleStatus.PUBLISHED,
            cefr_level=CefrLevel.B2,
            published_at=datetime.now(UTC),
            content_version=1,
        )
        sentence = ArticleSentence(
            id=uuid.uuid4(),
            article_id=article.id,
            sentence_order=1,
            sentence_text="Quantum computing is revolutionary.",
            translation_vi=None,
            content_version=1,
            is_active=True,
        )
        term = ArticleSentenceTerm(
            id=uuid.uuid4(),
            sentence_id=sentence.id,
            value="revolutionary",
            lemma="revolutionary",
            part_of_speech=None,
            cefr_level=None,
            contextual_meaning_vi=None,
            definition_en=None,
            contextual_explanation=None,
            explanation_status=AiGenerationStatus.PENDING,
            review_status=TermReviewStatus.APPROVED,
            is_lookup_enabled=True,
            is_active=True,
            origin=TermOrigin.NLP,
        )
        session.add_all([admin, learner])
        await session.flush()
        session.add_all([category, article, sentence, term])
        await session.commit()

        # Create mock AI Service
        mock_ai = AsyncMock(spec=AiService)
        mock_ai.enrich_contextual_term.return_value = TermEnrichmentResult(
            partOfSpeech="adjective",
            cefrLevel="B2",
            contextualMeaningVi="mang tính cách mạng",
            definitionEn="Involving or causing a complete or dramatic change.",
            contextualExplanation="Describes the groundbreaking nature of quantum computing.",
            ipa="/ˌrev.əˈluː.ʃən.er.i/",
            synonyms=["groundbreaking"],
            antonyms=["conservative"],
            collocations=["revolutionary technology"],
            relatedTerms=["revolution"],
            examples=[
                TermExample(
                    sentence="A revolutionary new technology.",
                    translationVi="Một công nghệ mang tính cách mạng mới.",
                )
            ],
            sentenceTranslationVi="Điện toán lượng tử mang tính cách mạng.",
        )

        # Call get_contextual_term
        res = await ReadingService.get_contextual_term(
            session,
            learner.id,
            article.id,
            term.id,
            ai_service=mock_ai,
        )

        assert res.term.contextualMeaningVi == "mang tính cách mạng"
        assert res.term.explanationStatus == AiGenerationStatus.READY
        assert res.parentSentence.translationVi == "Điện toán lượng tử mang tính cách mạng."
        assert mock_ai.enrich_contextual_term.call_count == 1

        # Second call should not invoke AI service again
        res_cached = await ReadingService.get_contextual_term(
            session,
            learner.id,
            article.id,
            term.id,
            ai_service=mock_ai,
        )
        assert res_cached.term.explanationStatus == AiGenerationStatus.READY
        assert mock_ai.enrich_contextual_term.call_count == 1
