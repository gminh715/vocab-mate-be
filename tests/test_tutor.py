"""Integration tests for FSRS Tutor Sessions, server-side grading, and activity lifecycle."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.enums import CefrLevel, FsrsCardState, TutorQuestionType, TutorSessionStatus, UserRole, UserStatus
from app.models.users import User
from app.models.vocabularies import UserVocabulary
from app.modules.ai.contracts import (
    McOption,
    MultipleChoiceResult,
    SessionWarmupResult,
    WarmupFactStory,
)
from app.modules.ai.service import AiService


@pytest.mark.asyncio
async def test_tutor_full_lifecycle(client):
    """Verifies end-to-end tutor session flow: today status, start, server grading, FSRS update, abandon, and history."""
    rand = str(uuid.uuid4())[:8]
    admin_email = f"tutor_admin_{rand}@example.com"
    learner_email = f"tutor_learner_{rand}@example.com"
    pwd = "TutorPassword123!"

    # 1. Setup users
    admin_id = uuid.uuid4()
    learner_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        admin = User(
            id=admin_id,
            email=admin_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Admin {rand}",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        learner = User(
            id=learner_id,
            email=learner_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Learner {rand}",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            current_cefr_level=CefrLevel.B1,
            daily_study_minutes=15,
            learning_goal="B2",
        )
        session.add_all([admin, learner])
        await session.commit()

    # 2. Admin creates and publishes an article with terms
    admin_login = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['accessToken']}"}

    cat_resp = await client.post(
        "/api/v1/admin/categories",
        headers=admin_headers,
        json={"name": f"Tutor Tech {rand}", "slug": f"tutor-tech-{rand}", "isActive": True},
    )
    cat_id = cat_resp.json()["data"]["category"]["id"]

    art_slug = f"quantum-breakthrough-{rand}"
    art_resp = await client.post(
        "/api/v1/admin/articles",
        headers=admin_headers,
        json={
            "categoryId": cat_id,
            "title": f"Quantum Breakthrough {rand}",
            "slug": art_slug,
            "summary": "Exploring supercomputing architectures and memory encryption.",
            "contentHtml": (
                "<p>Scientists have revealed an extraordinary phenomenon in quantum computers. "
                "The innovative mechanism demonstrates supreme efficiency in cryptographic security.</p>"
            ),
            "cefrLevel": "B2",
        },
    )
    art_id = art_resp.json()["data"]["article"]["id"]

    await client.post(f"/api/v1/admin/articles/{art_id}/parse-content", headers=admin_headers, json={"force": True})
    await client.post(f"/api/v1/admin/articles/{art_id}/analyze", headers=admin_headers)
    await client.post(f"/api/v1/admin/articles/{art_id}/publish", headers=admin_headers)

    # 3. Learner logs in, creates a collection, and saves 2 terms
    learner_login = await client.post("/api/v1/auth/login", json={"email": learner_email, "password": pwd})
    learner_headers = {"Authorization": f"Bearer {learner_login.json()['data']['accessToken']}"}

    col_resp = await client.post(
        "/api/v1/collections",
        headers=learner_headers,
        json={"name": f"Tutor Collection {rand}"},
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["data"]["collection"]["id"]

    reader_resp = await client.get(f"/api/v1/reading/articles/{art_slug}", headers=learner_headers)
    highlighted_ids = reader_resp.json()["data"]["highlightedTermIds"]
    assert len(highlighted_ids) >= 2

    term_id_1 = highlighted_ids[0]
    term_id_2 = highlighted_ids[1]

    save_resp_1 = await client.post(
        "/api/v1/vocabularies",
        headers=learner_headers,
        json={"articleSentenceTermId": term_id_1, "collectionIds": [col_id]},
    )
    assert save_resp_1.status_code == 201

    save_resp_2 = await client.post(
        "/api/v1/vocabularies",
        headers=learner_headers,
        json={"articleSentenceTermId": term_id_2, "collectionIds": [col_id]},
    )
    assert save_resp_2.status_code == 201

    # 4. Check today status before starting any session
    today_resp = await client.get("/api/v1/tutor-sessions/today", headers=learner_headers)
    assert today_resp.status_code == 200
    today_data = today_resp.json()["data"]
    assert today_data["canStart"] is True
    assert today_data["canResume"] is False
    assert today_data["isCompletedToday"] is False
    assert today_data["isAbandoned"] is False

    # 5. Mock AI generation for deterministic test output
    mock_warmup = SessionWarmupResult(
        facts=[
            WarmupFactStory(
                title="Lượng tử và mật mã",
                factContentVi="Máy tính lượng tử sử dụng cơ chế bảo mật **cryptographic** (mật mã) đột phá.",
                targetWords=["cryptographic"],
            )
        ]
    )

    def make_mock_mc_result(cand_id: str):
        return MultipleChoiceResult(
            selected_candidate_id=cand_id,
            question_prompt_vi="Chọn đáp án đúng biểu thị ý nghĩa của từ:",
            explanation_vi="Đây là thuật ngữ khoa học chính xác.",
            feedback_correct_vi="Chính xác!",
            feedback_incorrect_vi="Chưa chính xác rồi!",
            options=[
                McOption(id="A", text="ý nghĩa chính xác"),
                McOption(id="B", text="ý nghĩa sai lệch"),
                McOption(id="C", text="không liên quan"),
                McOption(id="D", text="ngược nghĩa"),
            ],
            correct_option_id="A",
        )

    with (
        patch.object(AiService, "generate_session_warmup_facts", new_callable=AsyncMock) as mock_warmup_fn,
        patch.object(AiService, "generate_tutor_activity", new_callable=AsyncMock) as mock_act_fn,
    ):
        mock_warmup_fn.return_value = mock_warmup
        mock_act_fn.side_effect = lambda input_data: make_mock_mc_result(input_data.candidates[0].id)

        # 6. Start new session
        start_resp = await client.post("/api/v1/tutor-sessions", headers=learner_headers)
        assert start_resp.status_code == 200
        start_data = start_resp.json()["data"]

        session_dto = start_data["session"]
        session_id = session_dto["id"]
        assert session_dto["status"] == TutorSessionStatus.ACTIVE
        assert start_data["currentItem"] is not None

        # Critical Security Invariant Check: Pending item MUST NOT leak correct answer or explanations
        pending_item = start_data["currentItem"]
        item_id_1 = pending_item["id"]
        assert pending_item["questionType"] == TutorQuestionType.MULTIPLE_CHOICE
        assert "correctAnswer" not in pending_item
        assert "explanationVi" not in pending_item
        assert "feedbackCorrectVi" not in pending_item
        assert "options" in pending_item["questionPayload"]
        assert len(pending_item["questionPayload"]["options"]) == 4

        # Calling start again resumes the existing active session
        resume_resp = await client.post("/api/v1/tutor-sessions", headers=learner_headers)
        assert resume_resp.status_code == 200
        assert resume_resp.json()["data"]["session"]["id"] == session_id

        # Query session via GET /api/v1/tutor-sessions/{sessionId}
        get_sess_resp = await client.get(f"/api/v1/tutor-sessions/{session_id}", headers=learner_headers)
        assert get_sess_resp.status_code == 200
        assert get_sess_resp.json()["data"]["session"]["id"] == session_id

        # 7. Submit correct answer for Item 1
        ans_resp_1 = await client.post(
            f"/api/v1/tutor-sessions/{session_id}/items/{item_id_1}/answers",
            headers=learner_headers,
            json={"answer": "A", "responseTimeMs": 8000},
        )
        assert ans_resp_1.status_code == 200
        ans_data_1 = ans_resp_1.json()["data"]
        assert ans_data_1["item"]["isCorrect"] is True
        assert ans_data_1["item"]["fsrsRating"] == 2  # Hard (2) ceiling for MULTIPLE_CHOICE recognition
        assert ans_data_1["item"]["explanationVi"] == "Đây là thuật ngữ khoa học chính xác."
        assert ans_data_1["item"]["feedbackVi"] == "Chính xác!"

        # Verify FSRS database persistence for word 1
        async with AsyncSessionLocal() as db_check:
            uv1 = (
                (
                    await db_check.execute(
                        UserVocabulary.__table__.select().where(
                            UserVocabulary.user_id == learner_id,
                            UserVocabulary.article_sentence_term_id == term_id_1,
                        )
                    )
                )
                .mappings()
                .first()
            )
            assert uv1["review_count"] == 1
            assert uv1["fsrs_stability"] > 0
            assert uv1["fsrs_state"] == FsrsCardState.LEARNING
            assert uv1["next_review_at"] is not None

        # Fetch next item if session is still in progress using POST /api/v1/tutor-sessions (matching frontend flow)
        sess_state_resp = await client.post("/api/v1/tutor-sessions", headers=learner_headers)
        assert sess_state_resp.status_code == 200
        next_item = sess_state_resp.json()["data"].get("currentItem")
        if next_item:
            item_id_2 = next_item["id"]
            # 8. Submit incorrect answer for Item 2
            ans_resp_2 = await client.post(
                f"/api/v1/tutor-sessions/{session_id}/items/{item_id_2}/answers",
                headers=learner_headers,
                json={"answer": "B", "responseTimeMs": 4000},
            )
            assert ans_resp_2.status_code == 200
            ans_data_2 = ans_resp_2.json()["data"]
            assert ans_data_2["item"]["isCorrect"] is False
            assert ans_data_2["item"]["fsrsRating"] == 1
            assert ans_data_2["item"]["feedbackVi"] == "Chưa chính xác rồi!"

        # 9. Query completed/updated session detail
        detail_resp = await client.get(
            f"/api/v1/tutor-sessions/{session_id}/detail",
            headers=learner_headers,
        )
        assert detail_resp.status_code == 200
        detail_payload = detail_resp.json()["data"]
        detail_session = detail_payload["session"]
        detail_items = detail_payload["items"]
        assert detail_session["id"] == session_id
        assert len(detail_items) >= 1
        # In detail view, explanations and grading specs are visible for review
        assert detail_items[0]["answeredAt"] is not None
        assert detail_items[0]["explanationVi"] is not None

        # 10. Test abandon flow
        # Start a new session (if previous completed) or abandon current
        if detail_session["status"] == TutorSessionStatus.COMPLETED:
            new_sess_resp = await client.post("/api/v1/tutor-sessions", headers=learner_headers)
            abandon_target_id = new_sess_resp.json()["data"]["session"]["id"]
        else:
            abandon_target_id = session_id

        abandon_resp = await client.post(
            f"/api/v1/tutor-sessions/{abandon_target_id}/abandon",
            headers=learner_headers,
        )
        assert abandon_resp.status_code == 200
        assert abandon_resp.json()["data"]["session"]["status"] == TutorSessionStatus.ABANDONED

        # 11. Test history pagination
        history_resp = await client.get("/api/v1/tutor-sessions/history?limit=10", headers=learner_headers)
        assert history_resp.status_code == 200
        history_data = history_resp.json()["data"]
        assert len(history_data["items"]) >= 1
        assert any(s["id"] == session_id for s in history_data["items"])
