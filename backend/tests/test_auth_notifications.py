from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.entities import DataPermission, GuardianLink, Notification, User


def test_invitation_validation_and_email_normalization(client, register_user, auth_headers, db_session):
    guardian = register_user()
    dependent = register_user(role="DEPENDENT")
    other_guardian = register_user()
    guardian_headers = auth_headers(guardian["access_token"])

    missing = client.post("/api/v1/guardian/links", headers=guardian_headers,
                          json={"dependent_email": "unknown.person@example.com"})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "No registered dependent account was found with this email."

    guardian_email = client.post("/api/v1/guardian/links", headers=guardian_headers,
                                 json={"dependent_email": other_guardian["user"]["email"]})
    assert guardian_email.status_code == 400
    assert guardian_email.json()["detail"] == "This email belongs to a guardian account."

    own_email = client.post("/api/v1/guardian/links", headers=guardian_headers,
                            json={"dependent_email": guardian["user"]["email"]})
    assert own_email.status_code == 400

    inactive = db_session.get(User, UUID(dependent["user"]["id"]))
    inactive.is_active = False
    db_session.commit()
    inactive_result = client.post("/api/v1/guardian/links", headers=guardian_headers,
                                  json={"dependent_email": dependent["user"]["email"]})
    assert inactive_result.status_code == 400
    inactive.is_active = True
    db_session.commit()

    normalized = client.post("/api/v1/guardian/links", headers=guardian_headers,
                             json={"dependent_email": f"  {dependent['user']['email'].upper()}  "})
    assert normalized.status_code == 201, normalized.text
    link_id = normalized.json()["id"]
    duplicate = client.post("/api/v1/guardian/links", headers=guardian_headers,
                            json={"dependent_email": dependent["user"]["email"]})
    assert duplicate.status_code == 409
    assert "already pending" in duplicate.json()["detail"]

    dependent_notifications = client.get("/api/v1/notifications", headers=auth_headers(dependent["access_token"]))
    assert dependent_notifications.status_code == 200
    invite = dependent_notifications.json()[0]
    assert invite["notification_type"] == "guardian_link.invited"
    assert invite["guardian_link_id"] == link_id
    assert guardian["user"]["display_name"] in invite["message"]

    accepted = client.post(f"/api/v1/dependent/links/{link_id}/accept",
                           headers=auth_headers(dependent["access_token"]), json={"granted_categories": []})
    assert accepted.status_code == 200
    active_duplicate = client.post("/api/v1/guardian/links", headers=guardian_headers,
                                   json={"dependent_email": dependent["user"]["email"]})
    assert active_duplicate.status_code == 409
    assert "already linked" in active_duplicate.json()["detail"]


def test_link_creation_and_notification_recipient_authorization(client, register_user, auth_headers):
    guardian_a = register_user()
    guardian_b = register_user()
    dependent = register_user(role="DEPENDENT")
    invite = client.post("/api/v1/guardian/links", headers=auth_headers(guardian_a["access_token"]),
                         json={"dependent_email": dependent["user"]["email"]})
    assert invite.status_code == 201
    link_id = invite.json()["id"]

    # A dependent cannot invite; a guardian sees only their own links and notifications.
    assert client.post("/api/v1/guardian/links", headers=auth_headers(dependent["access_token"]),
                       json={"dependent_email": dependent["user"]["email"]}).status_code == 403
    assert client.get("/api/v1/guardian/links", headers=auth_headers(guardian_b["access_token"])).json() == []
    assert client.get("/api/v1/notifications", headers=auth_headers(guardian_a["access_token"])).json() == []
    assert client.get("/api/v1/notifications", headers=auth_headers(guardian_b["access_token"])).json() == []

    dependent_headers = auth_headers(dependent["access_token"])
    guardian_headers = auth_headers(guardian_a["access_token"])
    assert client.get("/api/v1/notifications/unread-count", headers=dependent_headers).json() == {"unread_count": 1}
    dep_notification = client.get("/api/v1/notifications", headers=dependent_headers).json()[0]
    foreign_read = client.patch(f"/api/v1/notifications/{dep_notification['id']}/read", headers=guardian_headers)
    assert foreign_read.status_code == 404

    marked = client.patch(f"/api/v1/notifications/{dep_notification['id']}/read", headers=dependent_headers)
    assert marked.status_code == 200 and marked.json()["is_read"] is True
    assert client.get("/api/v1/notifications/unread-count", headers=dependent_headers).json() == {"unread_count": 0}

    # Mark-all is limited to the authenticated recipient.
    client.post(f"/api/v1/dependent/links/{link_id}/decline", headers=dependent_headers)
    second = client.post("/api/v1/guardian/links", headers=auth_headers(guardian_b["access_token"]),
                         json={"dependent_email": dependent["user"]["email"]})
    assert second.status_code == 201
    assert client.get("/api/v1/notifications/unread-count", headers=dependent_headers).json() == {"unread_count": 1}
    assert client.post("/api/v1/notifications/read-all", headers=dependent_headers).json() == {"updated_count": 1}
    assert client.get("/api/v1/notifications/unread-count", headers=dependent_headers).json() == {"unread_count": 0}
    assert client.get("/api/v1/notifications", headers=auth_headers(guardian_b["access_token"])).json() == []
    accepted = client.post(f"/api/v1/dependent/links/{second.json()['id']}/accept", headers=dependent_headers,
                           json={"granted_categories": []})
    assert accepted.status_code == 200
    guardian_b_event = client.get("/api/v1/notifications", headers=auth_headers(guardian_b["access_token"])).json()[0]
    assert guardian_b_event["notification_type"] == "guardian_link.accepted"
    assert client.patch(f"/api/v1/notifications/{guardian_b_event['id']}/read", headers=guardian_headers).status_code == 404
    guardian_a_events = client.get("/api/v1/notifications", headers=guardian_headers).json()
    assert all(event["id"] != guardian_b_event["id"] for event in guardian_a_events)


def test_dependent_data_isolation_between_guardians_and_dependents(client, register_user, auth_headers):
    guardian_a = register_user()
    guardian_b = register_user()
    dependent_a = register_user(role="DEPENDENT")
    dependent_b = register_user(role="DEPENDENT")
    guardian_b_headers = auth_headers(guardian_b["access_token"])
    dependent_b_headers = auth_headers(dependent_b["access_token"])

    invitation = client.post("/api/v1/guardian/links", headers=guardian_b_headers,
                             json={"dependent_email": dependent_b["user"]["email"]})
    link_id = invitation.json()["id"]
    approved = client.post(f"/api/v1/dependent/links/{link_id}/accept", headers=dependent_b_headers,
                           json={"granted_categories": ["profile", "routines"]})
    assert approved.status_code == 200

    dependent_b_profile = f"/api/v1/dependents/{dependent_b['user']['id']}/profile"
    assert client.get(dependent_b_profile, headers=guardian_b_headers).status_code == 200
    assert client.get(dependent_b_profile, headers=auth_headers(guardian_a["access_token"])).status_code == 404
    assert client.get(dependent_b_profile, headers=auth_headers(dependent_a["access_token"])).status_code == 403
    assert client.get(f"/api/v1/dependents/{dependent_a['user']['id']}/profile",
                      headers=auth_headers(dependent_a["access_token"])).status_code == 200
    invitation_notifications = client.get("/api/v1/notifications", headers=dependent_b_headers).json()
    assert len(invitation_notifications) == 1
    dependent_a_headers = auth_headers(dependent_a["access_token"])
    assert client.get("/api/v1/notifications", headers=dependent_a_headers).json() == []
    assert client.patch(f"/api/v1/notifications/{invitation_notifications[0]['id']}/read",
                        headers=dependent_a_headers).status_code == 404

    # Changing a dependent_id in a guardian's URL does not grant the relationship or its scopes.
    foreign_write = client.post(f"/api/v1/dependents/{dependent_b['user']['id']}/medications",
                                headers=auth_headers(guardian_a["access_token"]),
                                json={"name": "Unauthorized medicine"})
    assert foreign_write.status_code == 404


def test_decline_accept_permission_and_revoke_notifications(client, register_user, auth_headers, db_session):
    guardian = register_user()
    dependent = register_user(role="DEPENDENT")
    another_dependent = register_user(role="DEPENDENT")
    g_headers = auth_headers(guardian["access_token"])
    d_headers = auth_headers(dependent["access_token"])
    other_headers = auth_headers(another_dependent["access_token"])

    link = client.post("/api/v1/guardian/links", headers=g_headers,
                       json={"dependent_email": dependent["user"]["email"]}).json()
    link_id = link["id"]
    assert client.post(f"/api/v1/dependent/links/{link_id}/accept", headers=other_headers,
                       json={"granted_categories": []}).status_code == 404
    declined = client.post(f"/api/v1/dependent/links/{link_id}/decline", headers=d_headers)
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"
    assert declined.json()["declined_at"]
    assert client.get("/api/v1/notifications/unread-count", headers=d_headers).json() == {"unread_count": 0}
    guardian_events = client.get("/api/v1/notifications", headers=g_headers).json()
    assert [event["notification_type"] for event in guardian_events] == ["guardian_link.declined"]

    reinvite = client.post("/api/v1/guardian/links", headers=g_headers,
                           json={"dependent_email": dependent["user"]["email"]})
    assert reinvite.status_code == 201
    link_id = reinvite.json()["id"]
    accepted = client.post(f"/api/v1/dependent/links/{link_id}/accept", headers=d_headers,
                           json={"granted_categories": ["profile"]})
    assert accepted.status_code == 200
    events = client.get("/api/v1/notifications", headers=g_headers).json()
    assert sum(event["notification_type"] == "guardian_link.accepted" for event in events) == 1

    change = {"permissions": {"profile": False}}
    assert client.put(f"/api/v1/dependent/links/{link_id}/permissions", headers=d_headers, json=change).status_code == 200
    assert client.put(f"/api/v1/dependent/links/{link_id}/permissions", headers=d_headers, json=change).status_code == 200
    events = client.get("/api/v1/notifications", headers=g_headers).json()
    assert sum(event["notification_type"] == "guardian_link.permissions_changed" for event in events) == 1

    revoked = client.post(f"/api/v1/dependent/links/{link_id}/revoke", headers=d_headers)
    assert revoked.status_code == 200
    events = client.get("/api/v1/notifications", headers=g_headers).json()
    assert sum(event["notification_type"] == "guardian_link.revoked" for event in events) == 1
    assert db_session.scalar(select(func.count(Notification.id)).where(Notification.user_id == UUID(guardian["user"]["id"]))) == len(events)


def test_password_change_role_login_and_token_revocation(client, register_user, auth_headers):
    created = register_user(role="GUARDIAN")
    token = created["access_token"]
    mismatch = client.post("/api/v1/auth/login", json={
        "email": created["user"]["email"], "password": "StrongDemoPassword!234", "role": "DEPENDENT",
    })
    assert mismatch.status_code == 403

    changed = client.post("/api/v1/auth/change-password", headers=auth_headers(token), json={
        "current_password": "StrongDemoPassword!234",
        "new_password": "AnotherSecurePassword!789",
        "confirm_password": "AnotherSecurePassword!789",
    })
    assert changed.status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth_headers(token)).status_code == 401
    old_login = client.post("/api/v1/auth/login", json={"email": created["user"]["email"], "password": "StrongDemoPassword!234"})
    assert old_login.status_code == 401
    new_login = client.post("/api/v1/auth/login", json={"email": created["user"]["email"], "password": "AnotherSecurePassword!789", "role": "GUARDIAN"})
    assert new_login.status_code == 200
    user = client.get("/api/v1/auth/me", headers=auth_headers(new_login.json()["access_token"]))
    assert user.status_code == 200


def test_password_change_rejects_bad_current_and_mismatch(client, register_user, auth_headers):
    created = register_user()
    headers = auth_headers(created["access_token"])
    wrong_current = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "not-the-current-password",
        "new_password": "AnotherSecurePassword!789",
        "confirm_password": "AnotherSecurePassword!789",
    })
    assert wrong_current.status_code == 400
    mismatch = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "StrongDemoPassword!234",
        "new_password": "AnotherSecurePassword!789",
        "confirm_password": "DifferentSecurePassword!123",
    })
    assert mismatch.status_code == 422


def test_single_guardian_rule_rejects_invite_and_accept_until_revoked(
    client, register_user, auth_headers, db_session,
):
    guardian_a = register_user()
    guardian_b = register_user()
    dependent = register_user(role="DEPENDENT")
    guardian_a_headers = auth_headers(guardian_a["access_token"])
    guardian_b_headers = auth_headers(guardian_b["access_token"])
    dependent_headers = auth_headers(dependent["access_token"])
    dependent_id = dependent["user"]["id"]

    first_invite = client.post("/api/v1/guardian/links", headers=guardian_a_headers,
                               json={"dependent_email": dependent["user"]["email"]})
    assert first_invite.status_code == 201
    first_link_id = first_invite.json()["id"]
    accepted = client.post(f"/api/v1/dependent/links/{first_link_id}/accept", headers=dependent_headers,
                           json={"granted_categories": ["profile", "routines", "emergency", "media", "reports", "wellbeing", "location"]})
    assert accepted.status_code == 200

    blocked_invite = client.post("/api/v1/guardian/links", headers=guardian_b_headers,
                                 json={"dependent_email": dependent["user"]["email"]})
    assert blocked_invite.status_code == 409
    assert "already has an active guardian" in blocked_invite.json()["detail"]
    assert client.get("/api/v1/guardian/links", headers=guardian_b_headers).json() == []

    # Model an older pending invitation that was created before the active-link
    # rule existed (or while an invite and acceptance were racing).
    stale_pending = GuardianLink(
        guardian_id=UUID(guardian_b["user"]["id"]),
        dependent_id=UUID(dependent_id),
        status="pending",
    )
    db_session.add(stale_pending)
    db_session.commit()
    stale_link_id = str(stale_pending.id)
    rejected_accept = client.post(f"/api/v1/dependent/links/{stale_link_id}/accept", headers=dependent_headers,
                                  json={"granted_categories": ["profile", "routines"]})
    assert rejected_accept.status_code == 409
    db_session.refresh(stale_pending)
    assert stale_pending.status == "pending"
    assert db_session.scalar(select(func.count(DataPermission.id)).where(
        DataPermission.link_id == stale_pending.id, DataPermission.allowed.is_(True),
    )) == 0

    # Unrelated guardians cannot use the dependent id in any of the main data URLs.
    unrelated = [
        f"/api/v1/dependents/{dependent_id}/profile",
        f"/api/v1/dependents/{dependent_id}/orientation",
        f"/api/v1/dependents/{dependent_id}/medications",
        f"/api/v1/dependents/{dependent_id}/appointments",
        f"/api/v1/dependents/{dependent_id}/reminders",
        f"/api/v1/dependents/{dependent_id}/emergency-contacts",
        f"/api/v1/dependents/{dependent_id}/memory/people",
        f"/api/v1/dependents/{dependent_id}/quizzes",
        f"/api/v1/dependents/{dependent_id}/games",
        f"/api/v1/dependents/{dependent_id}/orientation-activities",
        f"/api/v1/dependents/{dependent_id}/alerts",
        f"/api/v1/dependents/{dependent_id}/media",
        f"/api/v1/dependents/{dependent_id}/reports",
        f"/api/v1/dependents/{dependent_id}/wellbeing-checkins",
        f"/api/v1/dependents/{dependent_id}/wellbeing/report",
        f"/api/v1/dependents/{dependent_id}/location",
    ]
    for path in unrelated:
        response = client.get(path, headers=guardian_b_headers)
        assert response.status_code == 404, f"{path}: {response.status_code} {response.text}"

    # The guardian has profile permission but still cannot change identity/orientation.
    guardian_edit = client.put(f"/api/v1/dependents/{dependent_id}/profile", headers=guardian_a_headers,
                               json={"preferred_name": "Changed by guardian", "mode": "MEMORY_SUPPORT", "timezone": "UTC"})
    assert guardian_edit.status_code == 403
    original_email = dependent["user"]["email"]
    original_display_name = dependent["user"]["display_name"]
    own_edit = client.put(f"/api/v1/dependents/{dependent_id}/profile", headers=dependent_headers,
                          json={"preferred_name": "My chosen name", "mode": "MEMORY_SUPPORT", "timezone": "Asia/Kolkata"})
    assert own_edit.status_code == 200
    assert own_edit.json()["preferred_name"] == "My chosen name"
    assert own_edit.json()["mode"] == "MEMORY_SUPPORT"
    invalid_identity_edit = client.put(f"/api/v1/dependents/{dependent_id}/profile", headers=dependent_headers,
                                       json={"preferred_name": "Another name", "email": "changed@example.com"})
    assert invalid_identity_edit.status_code == 422
    current_user = client.get("/api/v1/auth/me", headers=dependent_headers).json()
    assert current_user["email"] == original_email
    assert current_user["display_name"] == original_display_name

    declined_stale = client.post(f"/api/v1/dependent/links/{stale_link_id}/decline", headers=dependent_headers)
    assert declined_stale.status_code == 200
    revoked = client.post(f"/api/v1/dependent/links/{first_link_id}/revoke", headers=dependent_headers)
    assert revoked.status_code == 200
    relink_invite = client.post("/api/v1/guardian/links", headers=guardian_b_headers,
                                json={"dependent_email": dependent["user"]["email"]})
    assert relink_invite.status_code == 201
    relinked = client.post(f"/api/v1/dependent/links/{relink_invite.json()['id']}/accept", headers=dependent_headers,
                           json={"granted_categories": ["profile", "routines"]})
    assert relinked.status_code == 200
    assert client.get(f"/api/v1/dependents/{dependent_id}/profile", headers=guardian_b_headers).status_code == 200
    assert client.get(f"/api/v1/dependents/{dependent_id}/profile", headers=guardian_a_headers).status_code == 404


def test_concurrent_accepts_leave_exactly_one_active_guardian(client, register_user, auth_headers, db_session):
    guardian_a = register_user()
    guardian_b = register_user()
    dependent = register_user(role="DEPENDENT")
    dependent_headers = auth_headers(dependent["access_token"])
    guardian_headers = [auth_headers(guardian_a["access_token"]), auth_headers(guardian_b["access_token"])]
    links = []
    for guardian in guardian_headers:
        invitation = client.post("/api/v1/guardian/links", headers=guardian,
                                 json={"dependent_email": dependent["user"]["email"]})
        assert invitation.status_code == 201
        links.append(invitation.json()["id"])

    start = Barrier(2)

    def accept(link_id: str):
        start.wait(timeout=10)
        return client.post(f"/api/v1/dependent/links/{link_id}/accept", headers=dependent_headers,
                           json={"granted_categories": ["profile"]})

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(accept, links))
    assert sorted(response.status_code for response in results) == [200, 409]
    active = db_session.scalars(select(GuardianLink).where(
        GuardianLink.dependent_id == UUID(dependent["user"]["id"]), GuardianLink.status == "active",
    )).all()
    assert len(active) == 1


def test_database_rejects_second_active_guardian(client, register_user, auth_headers, db_session):
    guardian_a = register_user()
    guardian_b = register_user()
    dependent = register_user(role="DEPENDENT")
    invite = client.post("/api/v1/guardian/links", headers=auth_headers(guardian_a["access_token"]),
                         json={"dependent_email": dependent["user"]["email"]}).json()
    accepted = client.post(f"/api/v1/dependent/links/{invite['id']}/accept",
                           headers=auth_headers(dependent["access_token"]), json={"granted_categories": []})
    assert accepted.status_code == 200

    db_session.add(GuardianLink(
        guardian_id=UUID(guardian_b["user"]["id"]),
        dependent_id=UUID(dependent["user"]["id"]),
        status="active",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
