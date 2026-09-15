import uuid

import pytest


@pytest.mark.asyncio
async def test_auth_full_flow(client):
    random_str = str(uuid.uuid4())[:8]
    test_email = f"test_{random_str}@example.com"
    test_password = "SecurePassword123!"

    # 1. Register
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": test_email,
            "password": test_password,
            "displayName": f"User {random_str}",
            "preferredLanguage": "vi",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert reg_data["success"] is True
    assert "accessToken" in reg_data["data"]
    assert reg_data["data"]["user"]["email"] == test_email
    assert "refreshToken" in reg_resp.cookies

    access_token = reg_data["data"]["accessToken"]
    refresh_cookie = reg_resp.cookies["refreshToken"]

    # 2. Duplicate registration fails (409)
    dup_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": test_email,
            "password": test_password,
            "displayName": "Duplicate",
            "preferredLanguage": "vi",
        },
    )
    assert dup_resp.status_code == 409

    # 3. Login with wrong password (401)
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    # 4. Login with correct password (200)
    good_login = await client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": test_password},
    )
    assert good_login.status_code == 200
    login_data = good_login.json()
    assert login_data["success"] is True
    assert "accessToken" in login_data["data"]
    access_token = login_data["data"]["accessToken"]

    # 5. Access /api/v1/users/me with Bearer token
    headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = await client.get("/api/v1/users/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["success"] is True
    assert me_data["data"]["email"] == test_email
    assert me_data["data"]["dailyStudyMinutes"] == 10

    # 6. Update user profile / learning settings with valid dailyStudyMinutes (20)
    update_resp = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"dailyStudyMinutes": 20, "preferredLanguage": "en"},
    )
    assert update_resp.status_code == 200
    update_data = update_resp.json()
    assert update_data["data"]["dailyStudyMinutes"] == 20
    assert update_data["data"]["preferredLanguage"] == "en"

    # 7. Refresh token
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refreshToken": refresh_cookie},
    )
    assert refresh_resp.status_code == 200
    ref_data = refresh_resp.json()
    assert "accessToken" in ref_data["data"]
    new_access_token = ref_data["data"]["accessToken"]
    assert new_access_token != ""

    # 8. Logout
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_access_token}"},
        cookies={"refreshToken": refresh_resp.cookies.get("refreshToken", refresh_cookie)},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["success"] is True
