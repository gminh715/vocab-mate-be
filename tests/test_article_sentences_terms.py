"""Integration tests for Admin Article Sentences and Terms management."""

import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.articles import ArticleSentenceTerm
from app.models.enums import AiGenerationStatus, CefrLevel, TermOrigin, TermReviewStatus, UserRole, UserStatus
from app.models.users import User
from app.models.vocabularies import UserVocabulary


@pytest.mark.asyncio
async def test_admin_article_sentences_and_terms_flow(client):
    rand = str(uuid.uuid4())[:8]
    admin_email = f"admin_st_{rand}@example.com"
    pwd = "AdminSecurePassword123!"

    # 1. Seed admin in DB
    async with AsyncSessionLocal() as session:
        admin = User(
            id=uuid.uuid4(),
            email=admin_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Admin {rand}",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        session.add(admin)
        await session.commit()

    # 2. Login admin
    login_resp = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create category
    cat_resp = await client.post(
        "/api/v1/admin/categories",
        headers=headers,
        json={"name": f"Technology {rand}", "slug": f"technology-{rand}", "isActive": True},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["data"]["category"]["id"]

    # 4. Create draft article
    art_slug = f"ai-robotics-{rand}"
    art_resp = await client.post(
        "/api/v1/admin/articles",
        headers=headers,
        json={
            "categoryId": cat_id,
            "title": f"Robotics Revolution {rand}",
            "slug": art_slug,
            "summary": "The rapid advancement of intelligent robots in industry.",
            "contentHtml": (
                "<p>Modern robotics utilizes intelligent algorithms. "
                "Autonomous machines can perform complex operations efficiently.</p>"
            ),
            "cefrLevel": "B2",
        },
    )
    assert art_resp.status_code == 201
    art_id = art_resp.json()["data"]["article"]["id"]

    # 5. Parse content into sentences
    parse_resp = await client.post(
        f"/api/v1/admin/articles/{art_id}/parse-content", headers=headers, json={"force": True}
    )
    assert parse_resp.status_code == 200
    assert parse_resp.json()["data"]["sentenceCount"] == 2

    # 6. List sentences (Admin)
    sentences_resp = await client.get(f"/api/v1/admin/articles/{art_id}/sentences", headers=headers)
    assert sentences_resp.status_code == 200
    s_json = sentences_resp.json()
    assert len(s_json["data"]["items"]) == 2
    assert s_json["meta"]["total"] == 2
    s1_id = s_json["data"]["items"][0]["id"]
    s2_id = s_json["data"]["items"][1]["id"]
    assert s_json["data"]["items"][0]["termCount"] == 0

    # 7. Get sentence detail (Admin)
    s_detail_resp = await client.get(f"/api/v1/admin/articles/{art_id}/sentences/{s1_id}", headers=headers)
    assert s_detail_resp.status_code == 200
    assert s_detail_resp.json()["data"]["sentenceText"] == "Modern robotics utilizes intelligent algorithms."
    assert s_detail_resp.json()["data"]["terms"] == []

    # 8. Update sentence metadata (Admin)
    s_update_resp = await client.patch(
        f"/api/v1/admin/articles/{art_id}/sentences/{s1_id}",
        headers=headers,
        json={"translationVi": "Ngành robot hiện đại ứng dụng các thuật toán thông minh."},
    )
    assert s_update_resp.status_code == 200
    assert s_update_resp.json()["data"]["translationVi"] == "Ngành robot hiện đại ứng dụng các thuật toán thông minh."

    # 9. Create manual term on sentence 1 (Admin)
    term_create_resp = await client.post(
        f"/api/v1/admin/articles/{art_id}/sentences/{s1_id}/terms",
        headers=headers,
        json={
            "value": "algorithms",
            "lemma": "algorithm",
            "partOfSpeech": "noun",
            "ipa": "/ˈæl.ɡə.rɪ.ðəm/",
            "cefrLevel": "B2",
            "contextualMeaningVi": "thuật toán",
            "definitionEn": "A process or set of rules to be followed in calculations.",
            "synonyms": ["procedures", "methods"],
        },
    )
    assert term_create_resp.status_code == 201
    term_data = term_create_resp.json()["data"]["term"]
    t_id = term_data["id"]
    assert term_data["value"] == "algorithms"
    assert term_data["origin"] == "MANUAL"
    assert term_data["reviewStatus"] == "APPROVED"
    assert term_create_resp.json()["data"]["contentHtmlChanged"] is True

    # Verify marker is present in article HTML
    art_detail = await client.get(f"/api/v1/admin/articles/{art_id}", headers=headers)
    assert f'data-term-id="{t_id}"' in art_detail.json()["data"]["article"]["contentHtml"]

    # 10. List terms (Admin)
    terms_list_resp = await client.get(f"/api/v1/admin/articles/{art_id}/terms", headers=headers)
    assert terms_list_resp.status_code == 200
    t_items = terms_list_resp.json()["data"]["items"]
    assert len(t_items) >= 1
    assert any(t["id"] == t_id for t in t_items)

    # 11. Get single term detail with parent sentence (Admin)
    term_detail_resp = await client.get(f"/api/v1/admin/articles/{art_id}/terms/{t_id}", headers=headers)
    assert term_detail_resp.status_code == 200
    assert term_detail_resp.json()["data"]["parentSentence"]["id"] == s1_id

    # 12. Update term lexical metadata (Admin)
    term_update_resp = await client.patch(
        f"/api/v1/admin/articles/{art_id}/terms/{t_id}",
        headers=headers,
        json={"contextualMeaningVi": "các thuật toán tính toán"},
    )
    assert term_update_resp.status_code == 200
    assert term_update_resp.json()["data"]["term"]["contextualMeaningVi"] == "các thuật toán tính toán"

    # 13. Moderation tests: Add an AI candidate term in DB
    ai_term_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        ai_term = ArticleSentenceTerm(
            id=ai_term_id,
            sentence_id=uuid.UUID(s2_id),
            value="efficiently",
            lemma="efficient",
            part_of_speech="adverb",
            cefr_level=CefrLevel.B2,
            origin=TermOrigin.AI,
            review_status=TermReviewStatus.PENDING,
            explanation_status=AiGenerationStatus.READY,
            is_lookup_enabled=False,
            is_active=False,
        )
        session.add(ai_term)
        await session.commit()

    # Approve AI term candidate
    approve_resp = await client.post(f"/api/v1/admin/articles/{art_id}/terms/{ai_term_id}/approve", headers=headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["term"]["reviewStatus"] == "APPROVED"
    assert approve_resp.json()["data"]["term"]["isActive"] is True
    assert approve_resp.json()["data"]["contentHtmlChanged"] is True

    # Add another AI candidate and reject it
    ai_reject_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        reject_term = ArticleSentenceTerm(
            id=ai_reject_id,
            sentence_id=uuid.UUID(s2_id),
            value="complex",
            lemma="complex",
            part_of_speech="adjective",
            cefr_level=CefrLevel.B1,
            origin=TermOrigin.AI,
            review_status=TermReviewStatus.PENDING,
            explanation_status=AiGenerationStatus.READY,
            is_lookup_enabled=False,
            is_active=False,
        )
        session.add(reject_term)
        await session.commit()

    reject_resp = await client.post(f"/api/v1/admin/articles/{art_id}/terms/{ai_reject_id}/reject", headers=headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["data"]["term"]["reviewStatus"] == "REJECTED"
    assert reject_resp.json()["data"]["term"]["isActive"] is False

    # 14. Delete manual term and verify marker unwrapping
    del_resp = await client.delete(f"/api/v1/admin/articles/{art_id}/terms/{t_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify marker is unwrapped
    art_after_del = await client.get(f"/api/v1/admin/articles/{art_id}", headers=headers)
    assert f'data-term-id="{t_id}"' not in art_after_del.json()["data"]["article"]["contentHtml"]
    assert "algorithms" in art_after_del.json()["data"]["article"]["contentHtml"]

    # 15. Referential integrity test: Saved vocabulary cannot be deleted
    # Recreate term and simulate learner saving it
    re_term_resp = await client.post(
        f"/api/v1/admin/articles/{art_id}/sentences/{s1_id}/terms",
        headers=headers,
        json={"value": "robotics", "lemma": "robotics", "cefrLevel": "B2"},
    )
    assert re_term_resp.status_code == 201
    rob_term_id = re_term_resp.json()["data"]["term"]["id"]

    # Seed UserVocabulary referencing rob_term_id
    async with AsyncSessionLocal() as session:
        user_vocab = UserVocabulary(
            id=uuid.uuid4(),
            user_id=admin.id,
            article_sentence_term_id=uuid.UUID(rob_term_id),
            saved_word_display="robotics",
            saved_lemma="robotics",
            saved_part_of_speech="noun",
            saved_cefr_level=CefrLevel.B2,
            saved_meaning_vi="ngành robot",
            saved_examples=[],
        )
        session.add(user_vocab)
        await session.commit()

    # Attempt delete -> 409 Conflict
    del_conflict = await client.delete(f"/api/v1/admin/articles/{art_id}/terms/{rob_term_id}", headers=headers)
    assert del_conflict.status_code == 409
    assert "referenced in saved vocabulary" in del_conflict.json()["error"]["message"]
