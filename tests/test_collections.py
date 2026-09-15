import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.enums import UserRole, UserStatus
from app.models.users import User


@pytest.mark.asyncio
async def test_collections_crud(client):
    rand = str(uuid.uuid4())[:8]
    email = f"col_user_{rand}@example.com"
    pwd = "ColPassword123!"

    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=get_password_hash(pwd),
            display_name=f"Col User {rand}",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        await session.commit()

    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create collection
    create_res = await client.post(
        "/api/v1/collections",
        headers=headers,
        json={"name": f"Technology Lexicon {rand}"},
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["data"]["collection"]["id"]

    # 2. Duplicate name conflict
    dup_res = await client.post(
        "/api/v1/collections",
        headers=headers,
        json={"name": f"Technology Lexicon {rand}"},
    )
    assert dup_res.status_code == 409

    # 3. List collections
    list_res = await client.get("/api/v1/collections", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()["data"]["items"]
    assert any(c["id"] == col_id for c in items)

    # 4. Get by ID
    get_res = await client.get(f"/api/v1/collections/{col_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["collection"]["name"] == f"Technology Lexicon {rand}"
    assert get_res.json()["data"]["vocabularyCount"] == 0

    # 5. Patch name
    new_name = f"Advanced Tech {rand}"
    patch_res = await client.patch(
        f"/api/v1/collections/{col_id}",
        headers=headers,
        json={"name": new_name},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["collection"]["name"] == new_name

    # 6. List items empty
    items_res = await client.get(f"/api/v1/collections/{col_id}/items", headers=headers)
    assert items_res.status_code == 200
    assert items_res.json()["data"]["items"] == []

    # 7. Delete collection
    del_res = await client.delete(f"/api/v1/collections/{col_id}", headers=headers)
    assert del_res.status_code == 204

    # 8. Verify deleted -> 404
    after_del = await client.get(f"/api/v1/collections/{col_id}", headers=headers)
    assert after_del.status_code == 404
