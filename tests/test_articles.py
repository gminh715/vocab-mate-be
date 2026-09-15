import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.enums import UserRole, UserStatus
from app.models.users import User


@pytest.mark.asyncio
async def test_articles_full_lifecycle(client):
    rand = str(uuid.uuid4())[:8]
    admin_email = f"art_admin_{rand}@example.com"
    pwd = "AdminPassword123!"

    # 1. Setup admin user
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

    # Login admin
    login_resp = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["accessToken"]
    admin_headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Category
    cat_slug = f"tech-{rand}"
    cat_resp = await client.post(
        "/api/v1/admin/categories",
        headers=admin_headers,
        json={"name": f"Technology {rand}", "slug": cat_slug, "isActive": True},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["data"]["category"]["id"]

    # 3. Create Draft Article
    art_slug = f"quantum-computing-{rand}"
    art_content = (
        "<p>Quantum computing represents a fundamental shift in computation. "
        "Scientists investigate the mysterious behavior of quantum particles. "
        "This breakthrough could revolutionize secure communication globally.</p>"
    )
    create_resp = await client.post(
        "/api/v1/admin/articles",
        headers=admin_headers,
        json={
            "categoryId": cat_id,
            "title": f"Quantum Computing Breakthrough {rand}",
            "slug": art_slug,
            "summary": "An introduction to quantum computation and particles.",
            "contentHtml": art_content,
            "cefrLevel": "B2",
            "sourceName": "Science Daily",
            "authorName": "Dr. Quantum",
        },
    )
    assert create_resp.status_code == 201
    art_data = create_resp.json()["data"]["article"]
    art_id = art_data["id"]
    assert art_data["status"] == "DRAFT"

    # 4. Parse content into sentences
    parse_resp = await client.post(
        f"/api/v1/admin/articles/{art_id}/parse-content",
        headers=admin_headers,
        json={"force": True},
    )
    assert parse_resp.status_code == 200
    parse_data = parse_resp.json()["data"]
    assert parse_data["sentenceCount"] >= 2
    assert "data-sentence-id" in parse_data["contentHtml"]

    # 5. Analyze CEFR and candidate vocabulary
    analyze_resp = await client.post(
        f"/api/v1/admin/articles/{art_id}/analyze",
        headers=admin_headers,
    )
    assert analyze_resp.status_code == 200
    analyze_data = analyze_resp.json()["data"]
    assert analyze_data["aiAnalysisStatus"] == "READY"
    assert "cefrLevel" in analyze_data
    assert analyze_data["candidateCount"] >= 1

    # 6. Publish Article
    pub_resp = await client.post(
        f"/api/v1/admin/articles/{art_id}/publish",
        headers=admin_headers,
    )
    assert pub_resp.status_code == 200
    assert pub_resp.json()["data"]["status"] == "PUBLISHED"
    assert pub_resp.json()["data"]["publishedAt"] is not None

    # 7. Public user lists articles -> published article is present
    catalog_resp = await client.get(f"/api/v1/articles?q={rand}")
    assert catalog_resp.status_code == 200
    items = catalog_resp.json()["data"]["items"]
    assert any(a["slug"] == art_slug for a in items)

    # 8. Public user gets article by slug
    detail_resp = await client.get(f"/api/v1/articles/{art_slug}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    assert detail_data["article"]["slug"] == art_slug
    assert detail_data["category"]["id"] == cat_id

    # 9. Admin archives article
    archive_resp = await client.post(
        f"/api/v1/admin/articles/{art_id}/archive",
        headers=admin_headers,
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["data"]["status"] == "ARCHIVED"

    # Public user can no longer find archived article by slug -> 404
    pub_archived = await client.get(f"/api/v1/articles/{art_slug}")
    assert pub_archived.status_code == 404

    # 10. Admin restores article to draft
    restore_resp = await client.post(
        f"/api/v1/admin/articles/{art_id}/restore-draft",
        headers=admin_headers,
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["data"]["status"] == "DRAFT"
