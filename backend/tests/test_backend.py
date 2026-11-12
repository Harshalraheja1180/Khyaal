import io

from sqlalchemy import text
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import engine
from app.models.entities import Role, User, UserRole


def test_health_and_database_connectivity(client):
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/health/ready")
    assert ready.status_code == 200, ready.text
    assert ready.json()["database"] == "connected"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_registration_login_and_protected_route(client, register_user):
    created = register_user()
    token = created["access_token"]
    assert created["user"]["roles"] == ["GUARDIAN"]
    assert client.get("/api/v1/users/me").status_code == 401
    current = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["display_name"] == "Demo User"
    login = client.post("/api/v1/auth/login", json={"email": created["user"]["email"], "password": "StrongDemoPassword!234"})
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_dependent_role_and_profile(client, register_user, auth_headers):
    dependent = register_user(role="DEPENDENT", mode="MEMORY_SUPPORT")
    token = dependent["access_token"]
    assert dependent["user"]["roles"] == ["DEPENDENT"]
    profile = client.get(f"/api/v1/dependents/{dependent['user']['id']}/profile", headers=auth_headers(token))
    assert profile.status_code == 200
    assert profile.json()["mode"] == "MEMORY_SUPPORT"


def test_guardian_link_requires_dependent_acceptance_and_scoped_permission(client, register_user, auth_headers):
    guardian = register_user()
    dependent = register_user(role="DEPENDENT")
    other_dependent = register_user(role="DEPENDENT")
    g_headers = auth_headers(guardian["access_token"])
    d_headers = auth_headers(dependent["access_token"])
    link_response = client.post("/api/v1/guardian/links", headers=g_headers,
                                json={"dependent_email": dependent["user"]["email"]})
    assert link_response.status_code == 201
    link_id = link_response.json()["id"]
    target_id = dependent["user"]["id"]
    assert client.post(f"/api/v1/dependents/{target_id}/medications", headers=g_headers,
                       json={"name": "Demo medication"}).status_code == 404
    accepted = client.post(f"/api/v1/dependent/links/{link_id}/accept", headers=d_headers,
                           json={"granted_categories": ["routines"]})
    assert accepted.status_code == 200
    summary = client.get("/api/v1/guardian/dependents", headers=g_headers)
    assert summary.status_code == 200
    assert summary.json()[0]["display_name"] == "Linked dependent"
    assert summary.json()[0]["preferred_name"] is None
    created = client.post(f"/api/v1/dependents/{target_id}/medications", headers=g_headers,
                          json={"name": "Demo medication", "schedule": {"time": "09:00"}})
    assert created.status_code == 201, created.text
    unrelated = client.get(f"/api/v1/dependents/{other_dependent['user']['id']}/medications", headers=g_headers)
    assert unrelated.status_code == 404
    no_scope = client.get(f"/api/v1/dependents/{target_id}/emergency-contacts", headers=g_headers)
    assert no_scope.status_code == 403
    revoked = client.post(f"/api/v1/dependent/links/{link_id}/revoke", headers=d_headers)
    assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"
    assert client.get(f"/api/v1/dependents/{target_id}/medications", headers=g_headers).status_code == 404
    relink = client.post("/api/v1/guardian/links", headers=g_headers,
                         json={"dependent_email": dependent["user"]["email"]})
    assert relink.status_code == 201
    assert client.post(f"/api/v1/dependent/links/{relink.json()['id']}/accept", headers=d_headers,
                       json={"granted_categories": []}).status_code == 200
    assert client.get(f"/api/v1/dependents/{target_id}/medications", headers=g_headers).status_code == 403


def test_admin_does_not_get_guardian_access(client, db_session, register_user):
    dependent = register_user(role="DEPENDENT")
    admin_role = db_session.scalar(select(Role).where(Role.name == "ADMIN"))
    admin = User(email="admin-test@example.com", display_name="Support Admin", password_hash=hash_password("StrongDemoPassword!234"))
    db_session.add(admin)
    db_session.flush()
    db_session.add(UserRole(user_id=admin.id, role_id=admin_role.id))
    db_session.commit()
    token = create_access_token(str(admin.id), admin.token_version)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(f"/api/v1/dependents/{dependent['user']['id']}/profile", headers=headers)
    assert response.status_code == 403
    invite = client.get("/api/v1/guardian/links", headers=headers)
    assert invite.status_code == 403


def test_basic_crud_foundation(client, register_user, auth_headers):
    dependent = register_user(role="DEPENDENT")
    headers = auth_headers(dependent["access_token"])
    target_id = dependent["user"]["id"]
    medication = client.post(f"/api/v1/dependents/{target_id}/medications", headers=headers,
                             json={"name": "Demo item", "schedule": {"daily": True}})
    assert medication.status_code == 201
    listed = client.get(f"/api/v1/dependents/{target_id}/medications", headers=headers)
    assert listed.status_code == 200 and listed.json()[0]["name"] == "Demo item"
    reminder = client.post(f"/api/v1/dependents/{target_id}/reminders", headers=headers,
                           json={"title": "Walk", "kind": "exercise"})
    assert reminder.status_code == 201
    patched = client.patch(f"/api/v1/reminders/{reminder.json()['id']}", headers=headers, json={"title": "Gentle walk"})
    assert patched.status_code == 200 and patched.json()["title"] == "Gentle walk"
    contact = client.post(f"/api/v1/dependents/{target_id}/emergency-contacts", headers=headers,
                          json={"name": "Fictional contact", "phone": "+1-202-555-0181"})
    assert contact.status_code == 201


def test_media_upload_is_private_and_authorized(client, register_user, auth_headers, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_root", tmp_path)
    guardian = register_user()
    dependent = register_user(role="DEPENDENT")
    g_headers = auth_headers(guardian["access_token"])
    d_headers = auth_headers(dependent["access_token"])
    dep_id = dependent["user"]["id"]
    rejected = client.post(f"/api/v1/dependents/{dep_id}/media", headers=g_headers,
                           files={"file": ("photo.png", io.BytesIO(b"\x89PNG\r\n\x1a\nFAKE"), "image/png")})
    assert rejected.status_code == 404
    link = client.post("/api/v1/guardian/links", headers=g_headers,
                       json={"dependent_email": dependent["user"]["email"]}).json()
    client.post(f"/api/v1/dependent/links/{link['id']}/accept", headers=d_headers,
                json={"granted_categories": ["media"]})
    uploaded = client.post(f"/api/v1/dependents/{dep_id}/media", headers=g_headers,
                           files={"file": ("../../family photo.png", io.BytesIO(b"\x89PNG\r\n\x1a\nFAKE"), "image/png")})
    assert uploaded.status_code == 201, uploaded.text
    assert "storage_key" not in uploaded.json()
    media_id = uploaded.json()["id"]
    content = client.get(f"/api/v1/media/{media_id}/content", headers=g_headers)
    assert content.status_code == 200
    assert "family%20photo.png" in content.headers.get("content-disposition", "")
    assert len(list(tmp_path.iterdir())) == 1


def test_logout_revokes_token(client, register_user, auth_headers):
    result = register_user()
    headers = auth_headers(result["access_token"])
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
