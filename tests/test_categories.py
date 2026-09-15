"""Test suite for Categories module."""

import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.enums import UserRole, UserStatus
from app.models.users import User


@pytest.mark.asyncio
async def test_categories_lifecycle(client):
    # 1. Prepare Admin User
    rand = str(uuid.uuid4())[:8]
    admin_email = f"cat_admin_{rand}@example.com"
    pwd = "AdminPassword123!"

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
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Admin creates category
    cat_slug = f"science-tech-{rand}"
    cat_name = f"Science & Technology {rand}"
    create_resp = await client.post(
        "/api/v1/admin/categories",
        headers=headers,
        json={
            "name": cat_name,
            "slug": cat_slug,
            "description": "Scientific discoveries and modern technology",
            "displayOrder": 1,
            "isActive": True,
        },
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["success"] is True
    cat_id = created_data["data"]["category"]["id"]
    assert created_data["data"]["category"]["slug"] == cat_slug

    # 3. Public lists categories -> contains newly created category
    pub_list = await client.get(f"/api/v1/categories?q={rand}")
    assert pub_list.status_code == 200
    items = pub_list.json()["data"]["items"]
    assert any(c["slug"] == cat_slug for c in items)

    # 4. Public gets category by slug
    pub_detail = await client.get(f"/api/v1/categories/{cat_slug}")
    assert pub_detail.status_code == 200
    assert pub_detail.json()["data"]["category"]["name"] == cat_name

    # 5. Admin updates category
    update_resp = await client.patch(
        f"/api/v1/admin/categories/{cat_id}",
        headers=headers,
        json={"name": f"{cat_name} (Updated)", "displayOrder": 5},
    )
    assert update_resp.status_code == 200
    assert "(Updated)" in update_resp.json()["data"]["category"]["name"]

    # 6. Admin updates status to inactive
    status_resp = await client.patch(
        f"/api/v1/admin/categories/{cat_id}/status",
        headers=headers,
        json={"isActive": False},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["isActive"] is False

    # Inactive category is no longer accessible on public slug route -> 404
    pub_404 = await client.get(f"/api/v1/categories/{cat_slug}")
    assert pub_404.status_code == 404

    # 7. Admin gets category detail with articleCount
    admin_detail = await client.get(f"/api/v1/admin/categories/{cat_id}", headers=headers)
    assert admin_detail.status_code == 200
    detail_data = admin_detail.json()["data"]
    assert detail_data["articleCount"] == 0
    assert detail_data["category"]["isActive"] is False

    # 8. Admin deletes unused category -> 204 No Content
    del_resp = await client.delete(f"/api/v1/admin/categories/{cat_id}", headers=headers)
    assert del_resp.status_code == 204

    # Verify deleted
    admin_404 = await client.get(f"/api/v1/admin/categories/{cat_id}", headers=headers)
    assert admin_404.status_code == 404
