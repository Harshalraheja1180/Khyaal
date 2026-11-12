# MemoryCare API design

## Contract conventions

- Base path: `/api/v1`; JSON request/response except authorized multipart media uploads in a later phase.
- Authentication uses short-lived signed JWT bearer tokens. Protected endpoints require a valid token and active account. Logout increments a database token version, revoking existing access tokens.
- All dependent-scoped routes enforce role, active guardian link, and category permission on the server. A caller-supplied UUID does not grant access.
- Use request/response schemas with allow-listed fields. Do not accept role, owner, guardian, status, or audit fields as unrestricted mass-assignment input.
- Use `201 Created`, `204 No Content`, `400` invalid operation, `401` unauthenticated, `403` authenticated but disallowed, `404` absent/out-of-scope resource (consistent policy to avoid enumeration), `409` state conflict, `422` validation failure, and `429` rate limit.
- Current errors use FastAPI's `{"detail": ...}` response for expected client errors and a generic `{"detail":"An internal server error occurred"}` for unexpected failures. Do not expose stack traces or sensitive values.
- Use cursor pagination for growing event/history lists. Use idempotency keys for operations that could be retried (for example, creating occurrences or recording a user action).
- The authentication, link, profile, care, activity foundation, and media routes in this document have initial implementations. Some planned module route families remain future work.

## Phase 2 — identity and guardian relationships

| Method and path | Access | Purpose |
| --- | --- | --- |
| `POST /auth/login` | Public, rate-limited | Authenticate and create a session; generic failure message |
| `POST /auth/logout` | Authenticated + CSRF | Revoke current session |
| `GET /users/me` | Authenticated | Return minimal user identity and effective roles |
| `POST /guardian/links/invitations` | Guardian | Invite a dependent/guardian using a one-time, expiring token |
| `POST /guardian/links/{link_id}/accept` | Invited party / authorized guardian flow | Accept relationship and record authorization |
| `GET /guardian/dependents` | Guardian | List only active linked dependents and permitted summaries |
| `GET /guardian/dependents/{dependent_id}` | Guardian with active link | Return profile fields allowed by permissions |
| `GET /dependent/home` | Dependent | Return a minimal role/mode-specific shell payload |
| `GET /guardian/home` | Guardian | Return linked-user shell and permitted counts |

Relationship setup and dependent consent must be designed to match the deployment's legal requirements before production use. Admin APIs are support-only and separately audited.

## Later module route families

These are route families to design/implement when approved phases reach them; they are not Phase 1 APIs.

| Family | Example endpoints | Authorization/data scope |
| --- | --- | --- |
| Reminders and care plan | `GET/POST /dependents/{id}/reminders`, `GET /dependents/{id}/reminder-occurrences/today`, `POST /reminder-occurrences/{id}/actions` | Dependent self-access or linked guardian with routines permission |
| Contacts | `GET/POST /dependents/{id}/emergency-contacts` | Linked guardian with emergency permission; dependent read limited to configured view |
| Media and memory | `POST /dependents/{id}/media`, `GET /media/{id}/content`, `/familiar-people`, `/familiar-places`, `/familiar-objects` | Backend authorizes every upload and read; private storage key never exposed |
| Activities and games | `/activities`, `/activity-attempts`, `/games`, `/game-sessions` | Dependent can submit own participation; guardian config/read needs activity permission |
| Wellbeing | `POST /dependents/{id}/wellbeing-checkins`, `GET /dependents/{id}/wellbeing-checkins` | Dependent submission and explicitly permitted guardian view; refusal is valid |
| Alerts | `GET /guardian/alerts`, `POST /alerts/{id}/acknowledgements` | Only recipients and guardians with alert permission; state changes audited |
| Reports | `GET /guardian/dependents/{id}/reports?from=...&to=...` | Explicit reports permission; aggregate, non-diagnostic wording |
| Permissions and consent | `GET/POST /guardian/dependents/{id}/permissions`, `/consents` | Authorized grantor only; revocation is recorded and enforced immediately |
| Location (optional) | `GET /dependents/{id}/location/permission`, `POST /.../permission`, `GET /.../events` | Off by default; purpose, permitted viewers, retention and access audit required |

## Audit events

Record successful and denied access where warranted for authentication, role/link changes, profile changes, report reads, media reads, location reads, permission/consent changes, alert acknowledgement, and privileged support actions. Store actor, action, resource scope, timestamp, outcome, and request ID; exclude passwords, session tokens, image content, wellbeing answer text, and other unnecessary payloads.

## Frontend connection

The Next.js API client will use one configured API base URL, typed request/response contracts, credentials for the session cookie, CSRF token handling for mutations, and consistent loading/error states. The UI may hide unavailable actions for clarity, but the FastAPI authorization check remains authoritative.
