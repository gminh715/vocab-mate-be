import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.enums import CefrLevel, UserRole, UserStatus
from app.models.users import User


@pytest.mark.asyncio
async def test_vocabularies_lifecycle(client):
    rand = str(uuid.uuid4())[:8]
    admin_email = f"voc_admin_{rand}@example.com"
    learner_email = f"voc_learner_{rand}@example.com"
    pwd = "VocPassword123!"

    # 1. Setup users
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

    # Admin logins and creates/publishes article
    admin_login = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['accessToken']}"}

    cat_resp = await client.post(
        "/api/v1/admin/categories",
        headers=admin_headers,
        json={"name": f"Voc Category {rand}", "slug": f"voc-cat-{rand}", "isActive": True},
    )
    cat_id = cat_resp.json()["data"]["category"]["id"]

    art_slug = f"renewable-energy-{rand}"
    art_resp = await client.post(
        "/api/v1/admin/articles",
        headers=admin_headers,
        json={
            "categoryId": cat_id,
            "title": f"Renewable Energy Advances {rand}",
            "slug": art_slug,
            "summary": "Recent breakthroughs in sustainable power and energy storage.",
            "contentHtml": (
                "<p>Renewable power represents a fundamental shift in energy production. "
                "Engineers investigate the mysterious efficiency of advanced solar cells. "
                "This discovery could revolutionize secure electrical grids globally.</p>"
            ),
            "cefrLevel": "B2",
        },
    )
    art_id = art_resp.json()["data"]["article"]["id"]

    await client.post(f"/api/v1/admin/articles/{art_id}/parse-content", headers=admin_headers, json={"force": True})
    await client.post(f"/api/v1/admin/articles/{art_id}/analyze", headers=admin_headers)
    await client.post(f"/api/v1/admin/articles/{art_id}/publish", headers=admin_headers)

    # 2. Learner logins
    learner_login = await client.post("/api/v1/auth/login", json={"email": learner_email, "password": pwd})
    learner_headers = {"Authorization": f"Bearer {learner_login.json()['data']['accessToken']}"}

    # 3. Learner creates a Collection
    col_resp = await client.post(
        "/api/v1/collections",
        headers=learner_headers,
        json={"name": f"Key Terms {rand}"},
    )
    assert col_resp.status_code == 201
    col_id = col_resp.json()["data"]["collection"]["id"]

    # 4. Learner reads article to get candidate term
    reader_resp = await client.get(f"/api/v1/reading/articles/{art_slug}", headers=learner_headers)
    assert reader_resp.status_code == 200
    highlighted_ids = reader_resp.json()["data"]["highlightedTermIds"]
    assert len(highlighted_ids) >= 1
    term_id = highlighted_ids[0]

    # 5. Learner saves the term to the collection
    save_resp = await client.post(
        "/api/v1/vocabularies",
        headers=learner_headers,
        json={
            "articleSentenceTermId": term_id,
            "collectionIds": [col_id],
        },
    )
    assert save_resp.status_code == 201
    save_data = save_resp.json()["data"]
    uv_id = save_data["vocabulary"]["id"]
    assert len(save_data["collections"]) == 1
    assert save_data["collections"][0]["id"] == col_id

    # 6. Duplicate save returns 409
    dup_resp = await client.post(
        "/api/v1/vocabularies",
        headers=learner_headers,
        json={
            "articleSentenceTermId": term_id,
            "collectionIds": [col_id],
        },
    )
    assert dup_resp.status_code == 409

    # 7. Learner lists vocabularies
    list_resp = await client.get("/api/v1/vocabularies", headers=learner_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert any(item["id"] == uv_id for item in items)

    # 8. Collection items includes this vocabulary
    col_items_resp = await client.get(f"/api/v1/collections/{col_id}/items", headers=learner_headers)
    assert col_items_resp.status_code == 200
    assert any(item["id"] == uv_id for item in col_items_resp.json()["data"]["items"])

    # 9. Get vocabulary detail
    detail_resp = await client.get(f"/api/v1/vocabularies/{uv_id}", headers=learner_headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    assert detail_data["vocabulary"]["id"] == uv_id
    assert detail_data["sourceArticle"]["slug"] == art_slug

    # 10. Delete vocabulary
    del_resp = await client.delete(f"/api/v1/vocabularies/{uv_id}", headers=learner_headers)
    assert del_resp.status_code == 204

    # 11. Detail after delete -> 404
    after_del = await client.get(f"/api/v1/vocabularies/{uv_id}", headers=learner_headers)
    assert after_del.status_code == 404
