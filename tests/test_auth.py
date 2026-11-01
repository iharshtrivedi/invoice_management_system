from fastapi.testclient import TestClient


def test_register_login_and_reject_invalid_password(client: TestClient, registered_user: dict[str, str]):
    assert registered_user["Authorization"].startswith("Bearer ")

    response = client.post(
        "/api/auth/token",
        data={"username": "admin@acme.com", "password": "incorrect"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_is_rate_limited(client: TestClient, registered_user: dict[str, str]):
    for _ in range(4):
        response = client.post(
            "/api/auth/token",
            data={"username": "admin@acme.com", "password": "incorrect"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/auth/token",
        data={"username": "admin@acme.com", "password": "incorrect"},
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_forgot_password_does_not_disclose_user_existence(client: TestClient):
    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "missing@example.com"},
    )
    assert response.status_code == 202
    assert "If an account exists" in response.json()["message"]


def test_authenticated_user_can_change_password(client: TestClient, registered_user: dict[str, str]):
    response = client.get("/api/users/me", headers=registered_user)
    assert response.status_code == 200
    assert response.json()["email"] == "admin@acme.com"

    response = client.post(
        "/api/users/me/change-password",
        headers=registered_user,
        json={
            "current_password": "correct-horse-battery-staple",
            "new_password": "a-new-correct-horse-battery-staple",
        },
    )
    assert response.status_code == 200, response.text

    response = client.post(
        "/api/auth/token",
        data={"username": "admin@acme.com", "password": "a-new-correct-horse-battery-staple"},
    )
    assert response.status_code == 200
