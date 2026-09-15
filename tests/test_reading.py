import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.enums import CefrLevel, UserRole, UserStatus
from app.models.users import User


@pytest.mark.asyncio
async def test_reading_full_flow(client):
    rand = str(uuid.uuid4())[:8]
    admin_email = f"admin_{rand}@example.com"
    learner_email = f"learner_{rand}@example.com"
    pwd = "SecurePassword123!"

    # 1. Seed admin and learner users
    async with AsyncSessionLocal() as session:
        admin = User(
            id=uuid.uuid4(),
            email=admin_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Admin {rand}",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        learner = User(
            id=uuid.uuid4(),
            email=learner_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Learner {rand}",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            current_cefr_level=CefrLevel.B1,
            learning_goal="B2",
        )
        session.add_all([admin, learner])
        await session.commit()

    # 2. Login admin and create + publish article
    admin_login = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    admin_token = admin_login.json()["data"]["accessToken"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Category
    cat_resp = await client.post(
        "/api/v1/admin/categories",
        headers=admin_headers,
        json={"name": f"Science {rand}", "slug": f"science-{rand}", "isActive": True},
    )
    cat_id = cat_resp.json()["data"]["category"]["id"]

    # Article
    art_slug = f"quantum-physics-{rand}"
    art_resp = await client.post(
        "/api/v1/admin/articles",
        headers=admin_headers,
        json={
            "categoryId": cat_id,
            "title": f"Quantum Physics Revolution {rand}",
            "slug": art_slug,
            "summary": "Exploring quantum states and mysterious communications.",
            "contentHtml": (
                "<p>Quantum mechanics represents a fundamental shift in physics. "
                "Researchers investigate the mysterious behavior of entangled particles. "
                "This discovery could revolutionize secure global networks.</p>"
            ),
            "cefrLevel": "B2",
        },
    )
    art_id = art_resp.json()["data"]["article"]["id"]

    # Parse content
    await client.post(f"/api/v1/admin/articles/{art_id}/parse-content", headers=admin_headers, json={"force": True})

    # Analyze terms
    analyze_resp = await client.post(f"/api/v1/admin/articles/{art_id}/analyze", headers=admin_headers)
    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["data"]["candidateCount"] >= 1

    # Publish
    pub_resp = await client.post(f"/api/v1/admin/articles/{art_id}/publish", headers=admin_headers)
    assert pub_resp.status_code == 200

    # 3. Login learner
    learner_login = await client.post("/api/v1/auth/login", json={"email": learner_email, "password": pwd})
    learner_token = learner_login.json()["data"]["accessToken"]
    learner_headers = {"Authorization": f"Bearer {learner_token}"}

    # 4. Reader article payload
    reader_resp = await client.get(f"/api/v1/reading/articles/{art_slug}", headers=learner_headers)
    assert reader_resp.status_code == 200
    reader_data = reader_resp.json()["data"]
    assert reader_data["article"]["slug"] == art_slug
    assert len(reader_data["highlightedTermIds"]) >= 1
    term_id = reader_data["highlightedTermIds"][0]
    assert reader_data["progress"]["status"] == "READING"
    assert reader_data["progress"]["progressPercent"] == 0.0

    # 5. Get default reading progress
    prog_resp = await client.get(f"/api/v1/reading/progress/{art_id}", headers=learner_headers)
    assert prog_resp.status_code == 200
    assert prog_resp.json()["data"]["progress"]["progressPercent"] == 0.0

    # 6. Update reading progress
    update_resp = await client.put(
        f"/api/v1/reading/progress/{art_id}",
        headers=learner_headers,
        json={"progressPercent": 65},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["progress"]["progressPercent"] == 65.0
    assert update_resp.json()["data"]["progress"]["status"] == "READING"

    # 7. Check reading history
    hist_resp = await client.get("/api/v1/reading/history", headers=learner_headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()["data"]
    assert hist_data["meta"]["total"] >= 1
    assert any(item["article"]["id"] == art_id for item in hist_data["items"])

    # 8. Complete reading progress
    comp_resp = await client.post(f"/api/v1/reading/progress/{art_id}/complete", headers=learner_headers)
    assert comp_resp.status_code == 200
    assert comp_resp.json()["data"]["progress"]["status"] == "COMPLETED"
    assert comp_resp.json()["data"]["progress"]["progressPercent"] == 100.0
    assert comp_resp.json()["data"]["progress"]["completedAt"] is not None

    # 9. Contextual term lookup
    term_resp = await client.get(f"/api/v1/reading/articles/{art_id}/terms/{term_id}", headers=learner_headers)
    assert term_resp.status_code == 200
    term_data = term_resp.json()["data"]
    assert term_data["term"]["id"] == term_id
    assert term_data["parentSentence"]["sentenceText"] is not None
    assert term_data["saveState"]["isSaved"] is False

    # 10. Delete reading progress
    del_resp = await client.delete(f"/api/v1/reading/progress/{art_id}", headers=learner_headers)
    assert del_resp.status_code == 204

    # Verification: reading progress is back to non-persisted default
    after_del = await client.get(f"/api/v1/reading/progress/{art_id}", headers=learner_headers)
    assert after_del.status_code == 200
    assert after_del.json()["data"]["progress"]["progressPercent"] == 0.0
