"""Integration tests for Learner and Administrative Analytics reporting endpoints."""

import uuid
from datetime import UTC, datetime

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.articles import Article, ArticleSentence, ArticleSentenceTerm
from app.models.categories import Category
from app.models.enums import (
    AiGenerationStatus,
    ArticleStatus,
    CefrLevel,
    FsrsCardState,
    TermOrigin,
    TermReviewStatus,
    TutorSessionStatus,
    UserRole,
    UserStatus,
)
from app.models.reading import UserArticleProgress
from app.models.tutor import TutorSession
from app.models.users import User
from app.models.vocabularies import UserVocabulary


@pytest.mark.asyncio
async def test_analytics_full_flow(client):
    """Verifies all learner metrics (overview, vocabulary, reading, review) and admin platform metrics."""
    rand = str(uuid.uuid4())[:8]
    admin_email = f"analytics_admin_{rand}@example.com"
    learner_email = f"analytics_learner_{rand}@example.com"
    pwd = "AnalyticsPassword123!"

    admin_id = uuid.uuid4()
    learner_id = uuid.uuid4()
    now = datetime.now(UTC)

    # 1. Setup Admin and Learner
    async with AsyncSessionLocal() as session:
        admin = User(
            id=admin_id,
            email=admin_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Admin Analytics {rand}",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        learner = User(
            id=learner_id,
            email=learner_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Learner Analytics {rand}",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            current_cefr_level=CefrLevel.B1,
            learning_goal="B2",
            daily_study_minutes=20,
        )
        session.add_all([admin, learner])
        await session.flush()

        # 2. Setup Category and Article
        cat = Category(
            id=uuid.uuid4(),
            name=f"Science {rand}",
            slug=f"science-{rand}",
            is_active=True,
            created_by_user_id=admin_id,
            updated_by_user_id=admin_id,
        )
        session.add(cat)
        await session.flush()

        article = Article(
            id=uuid.uuid4(),
            category_id=cat.id,
            title=f"Astrophysics Insights {rand}",
            slug=f"astrophysics-insights-{rand}",
            summary="Understanding cosmic radiation.",
            content_html="<p>Deep space radiation permeates galaxies.</p>",
            cefr_level=CefrLevel.B2,
            status=ArticleStatus.PUBLISHED,
            published_at=now,
        )
        session.add(article)
        await session.flush()

        sentence = ArticleSentence(
            id=uuid.uuid4(),
            article_id=article.id,
            content_version=1,
            sentence_order=1,
            sentence_text="Deep space radiation permeates galaxies.",
            is_active=True,
        )
        session.add(sentence)
        await session.flush()

        term = ArticleSentenceTerm(
            id=uuid.uuid4(),
            sentence_id=sentence.id,
            value="permeates",
            lemma="permeate",
            part_of_speech="verb",
            cefr_level=CefrLevel.B2,
            contextual_meaning_vi="thấm qua",
            definition_en="To spread throughout.",
            origin=TermOrigin.AI,
            review_status=TermReviewStatus.APPROVED,
            explanation_status=AiGenerationStatus.READY,
            is_lookup_enabled=True,
            is_active=True,
        )
        session.add(term)
        await session.flush()

        # 3. Setup Saved Vocabulary for Learner
        uv = UserVocabulary(
            id=uuid.uuid4(),
            user_id=learner_id,
            article_sentence_term_id=term.id,
            saved_word_display="permeates",
            saved_lemma="permeate",
            saved_part_of_speech="verb",
            saved_cefr_level=CefrLevel.B2,
            saved_meaning_vi="thấm qua",
            saved_examples=[],
            saved_at=now,
            fsrs_state=FsrsCardState.LEARNING,
            fsrs_stability=2.5,
            fsrs_difficulty=5.0,
            fsrs_scheduled_days=3,
            review_count=2,
            next_review_at=now,
        )
        session.add(uv)

        # 4. Setup Reading Progress
        progress = UserArticleProgress(
            id=uuid.uuid4(),
            user_id=learner_id,
            article_id=article.id,
            first_opened_at=now,
            last_read_at=now,
            completed_at=now,
            progress_percent=100,
        )
        session.add(progress)

        # 5. Setup Completed Tutor Session
        tutor_sess = TutorSession(
            id=uuid.uuid4(),
            user_id=learner_id,
            study_date=now.date(),
            status=TutorSessionStatus.COMPLETED,
            target_duration_minutes=20,
            target_activity_count=5,
            new_word_target=2,
            started_at=now,
            completed_at=now,
        )
        session.add(tutor_sess)

        await session.commit()

    # 6. Login tokens
    learner_login = await client.post("/api/v1/auth/login", json={"email": learner_email, "password": pwd})
    learner_headers = {"Authorization": f"Bearer {learner_login.json()['data']['accessToken']}"}

    admin_login = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['accessToken']}"}

    # ---------------------------------------------------------------------------
    # Learner Endpoints
    # ---------------------------------------------------------------------------

    # GET /api/v1/analytics/me/overview
    ov_resp = await client.get("/api/v1/analytics/me/overview", headers=learner_headers)
    assert ov_resp.status_code == 200
    ov_data = ov_resp.json()["data"]
    assert ov_data["savedVocabulary"] >= 1
    assert ov_data["articlesCompleted"] >= 1

    # Also test alias /api/v1/analytics/overview
    ov_alias_resp = await client.get("/api/v1/analytics/overview", headers=learner_headers)
    assert ov_alias_resp.status_code == 200
    assert ov_alias_resp.json()["data"]["savedVocabulary"] == ov_data["savedVocabulary"]

    # GET /api/v1/analytics/me/vocabulary
    voc_resp = await client.get("/api/v1/analytics/me/vocabulary?groupBy=DAY", headers=learner_headers)
    assert voc_resp.status_code == 200
    voc_data = voc_resp.json()["data"]
    assert voc_data["totals"]["total"] >= 1
    assert any(c["cefrLevel"] == "B2" and c["count"] >= 1 for c in voc_data["byCefr"])
    assert isinstance(voc_data["savedTrend"], list)

    # GET /api/v1/analytics/me/reading
    read_resp = await client.get("/api/v1/analytics/me/reading?groupBy=DAY", headers=learner_headers)
    assert read_resp.status_code == 200
    read_data = read_resp.json()["data"]
    assert read_data["opened"] >= 1
    assert read_data["completed"] >= 1
    assert read_data["completionRate"] > 0
    assert len(read_data["byCategory"]) >= 1
    assert isinstance(read_data["trend"], list)

    # GET /api/v1/analytics/me/review
    rev_resp = await client.get("/api/v1/analytics/me/review", headers=learner_headers)
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()["data"]
    assert rev_data["streak"]["currentStreak"] >= 1
    assert rev_data["streak"]["isTodayCompleted"] is True
    assert len(rev_data["streak"]["recentDays"]) == 7
    assert rev_data["mastery"]["total"] >= 1
    assert rev_data["mastery"]["learningCount"] >= 1

    # ---------------------------------------------------------------------------
    # Admin Endpoints
    # ---------------------------------------------------------------------------

    # GET /api/v1/admin/analytics/overview
    admin_ov_resp = await client.get("/api/v1/admin/analytics/overview", headers=admin_headers)
    assert admin_ov_resp.status_code == 200
    admin_ov_data = admin_ov_resp.json()["data"]
    assert admin_ov_data["users"] >= 2
    assert admin_ov_data["activeUsers"] >= 1
    assert admin_ov_data["publishedArticles"] >= 1
    assert admin_ov_data["savedVocabulary"] >= 1

    # GET /api/v1/admin/analytics/content
    admin_cnt_resp = await client.get("/api/v1/admin/analytics/content", headers=admin_headers)
    assert admin_cnt_resp.status_code == 200
    admin_cnt_data = admin_cnt_resp.json()["data"]
    assert isinstance(admin_cnt_data["topArticles"], list)
    assert isinstance(admin_cnt_data["completionRates"], list)
    assert isinstance(admin_cnt_data["termSaveCounts"], list)

    # GET /api/v1/admin/analytics/users
    admin_usr_resp = await client.get("/api/v1/admin/analytics/users", headers=admin_headers)
    assert admin_usr_resp.status_code == 200
    admin_usr_data = admin_usr_resp.json()["data"]
    assert admin_usr_data["activeLearners"] >= 1
    assert isinstance(admin_usr_data["registrationsTrend"], list)
    assert "rate" in admin_usr_data["retentionProxy"]
    assert "multiActivity" in admin_usr_data["learningDistribution"]

    # ---------------------------------------------------------------------------
    # RBAC and Security Invariants
    # ---------------------------------------------------------------------------

    # Learner forbidden from accessing administrative analytics
    learner_forbidden = await client.get("/api/v1/admin/analytics/overview", headers=learner_headers)
    assert learner_forbidden.status_code == 403

    # Unauthenticated rejected from learner metrics
    unauth_resp = await client.get("/api/v1/analytics/me/overview")
    assert unauth_resp.status_code == 401
