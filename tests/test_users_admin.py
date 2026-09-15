import uuid

import pytest

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.enums import UserRole, UserStatus
from app.models.users import User


@pytest.mark.asyncio
async def test_admin_users_flow(client):
    # 1. Create a regular user and an admin user in DB
    rand = str(uuid.uuid4())[:8]
    user_email = f"user_{rand}@example.com"
    admin_email = f"admin_{rand}@example.com"
    pwd = "AdminUserPassword123!"

    async with AsyncSessionLocal() as session:
        reg_user = User(
            id=uuid.uuid4(),
            email=user_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Normal {rand}",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
        )
        admin_user = User(
            id=uuid.uuid4(),
            email=admin_email,
            password_hash=get_password_hash(pwd),
            display_name=f"Admin {rand}",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        session.add_all([reg_user, admin_user])
        await session.commit()
        user_id = reg_user.id

    # 2. Login as regular user
    user_login = await client.post("/api/v1/auth/login", json={"email": user_email, "password": pwd})
    assert user_login.status_code == 200
    user_token = user_login.json()["data"]["accessToken"]

    # 3. Regular user attempts admin endpoint -> 403 Forbidden
    forbidden_resp = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert forbidden_resp.status_code == 403

    # 4. Login as admin user
    admin_login = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": pwd})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["data"]["accessToken"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 5. Admin lists users
    list_resp = await client.get("/api/v1/admin/users?page=1&limit=10", headers=admin_headers)
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["success"] is True
    assert "data" in list_data
    assert "meta" in list_data
    assert list_data["meta"]["total"] >= 2

    # 6. Admin updates user status to SUSPENDED
    status_resp = await client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        headers=admin_headers,
        json={"status": "SUSPENDED"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["status"] == "SUSPENDED"

    # Suspended user tries to login -> 403
    suspended_login = await client.post("/api/v1/auth/login", json={"email": user_email, "password": pwd})
    assert suspended_login.status_code == 403

    # 7. Admin updates user role to ADMIN and status back to ACTIVE
    role_resp = await client.patch(
        f"/api/v1/admin/users/{user_id}/role",
        headers=admin_headers,
        json={"role": "ADMIN"},
    )
    assert role_resp.status_code == 200
    assert role_resp.json()["data"]["role"] == "ADMIN"

    reactivate_resp = await client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        headers=admin_headers,
        json={"status": "ACTIVE"},
    )
    assert reactivate_resp.status_code == 200
    assert reactivate_resp.json()["data"]["status"] == "ACTIVE"
