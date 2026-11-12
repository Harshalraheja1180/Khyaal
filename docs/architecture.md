# MemoryCare architecture

## Phase 1 boundary

This is a design contract, not a running application. It establishes components and trust boundaries for the full product while keeping implementation limited to the architecture phase. No future feature is represented as working.

## Product and safety principles

- Support daily routines, engagement, and coordination. Do not diagnose dementia, Alzheimer's disease, depression, or other conditions.
- Use fictional data in development. Minimize sensitive data and make sharing purpose-specific and revocable.
- Treat a dependent as potentially a child. Require an explicit, recorded guardian relationship and authorization appropriate to the deployment.
- Give administrators technical/support access only. No default access to personal media, location, or care information.
- Make monitoring visible and permission-based. Location sharing is off by default.
- A guardian's access is scoped to linked dependents and granted data categories; a frontend check alone is never authorization.

## Component responsibilities

| Component | Responsibility | Trust boundary |
| --- | --- | --- |
| Next.js web client | Accessible role-specific flows, form validation for usability, API calls, loading/error/offline states | Untrusted client; never decides access rights |
| FastAPI | REST interface, input/output validation, authentication, authorization, domain services, audit events, storage mediation | Enforces identity, relationship, and data-scope checks on every protected request |
| PostgreSQL | Durable relational records, foreign keys, uniqueness/check constraints, indexes, transactions | Reachable only by backend credentials; no browser connection |
| Private media storage | Original uploaded files, outside the public web root | Access mediated by backend; database stores a non-public storage key and metadata |
| Alembic | Versioned schema changes | Migration history is reviewed and applied deliberately |

## Technology decisions

- Frontend: Next.js, React, TypeScript, semantic accessible components.
- Backend: Python, FastAPI, Pydantic schemas, SQLAlchemy 2.x.
- Database: PostgreSQL. Alembic is the sole schema migration path.
- API: versioned REST JSON under `/api/v1`.
- File handling: a storage interface. Local development uses a private filesystem directory outside `frontend/public`; a production object-storage adapter can be selected later. The browser never receives a public object URL.
- Authentication: short-lived signed JWT bearer tokens; password hashes use Argon2. Logout increments a server-side token version, revoking existing access tokens. A browser frontend must keep tokens out of localStorage and choose an appropriate secure token-storage strategy before deployment.

## Data and request flows

### Normal API request

1. The browser calls the FastAPI origin over HTTPS with JSON.
2. FastAPI validates the request and resolves the authenticated account.
3. The authorization layer checks role, guardian-dependent link status, and the requested data scope.
4. Domain services use a SQLAlchemy transaction to read/write PostgreSQL.
5. The API returns a validated response. Protected reads/writes generate audit events where specified.

### Guardian media upload (future)

1. The browser sends a multipart upload to FastAPI.
2. FastAPI checks relationship and media permission, enforces size/type limits, inspects content, and generates a random storage key.
3. The backend writes the file to private storage and inserts metadata/reference rows in PostgreSQL in a controlled operation.
4. Later reads go through an authorized backend endpoint. No guessable path or public URL is returned.

The failure/cleanup strategy for a storage write and database transaction must be implemented with compensating deletion or staged upload records; it must not leave an orphaned file silently.

## Authorization model

Roles are `ADMIN`, `GUARDIAN`, and `DEPENDENT`. Dependent interaction modes (`OLDER_ADULT`, `MEMORY_SUPPORT`) are profile preferences, not security roles. A user may have more than one role only if explicitly granted by a trusted administrative process.

Guardians connect to dependents through a relationship record with invitation/approval state and timestamps. Authorization requires an active link plus the required per-category permission. Sensitive resources are always scoped by dependent ID in the backend query, avoiding object-ID-only access and IDOR vulnerabilities. Admin support actions are audited and do not implicitly unlock private data.

## Reliability, observability, and security requirements for implementation

- Keep secrets in environment/configuration management; do not commit them.
- Use TLS in deployed environments, password hashing with a modern adaptive password hash, authentication rate limits, secure session rotation/expiry, and CSRF protection for cookie-authenticated mutations.
- Validate all input on the server, use parameterized ORM queries, and return generic authentication errors.
- Use database constraints in addition to application validation. Back up PostgreSQL and document restore procedures before real use.
- Keep sensitive details out of logs, analytics, and notification previews. Audit access to reports, media, location, role/link changes, and permission changes.
- Define retention/export/deletion policies before real personal data is used.
- Treat alert delivery as fallible. Record delivery state and avoid implying that the application guarantees emergency response.

## Planned implementation sequence

The pasted master prompt defined the original Phase 1 documentation scope. The current milestone implements the backend/database foundation described in the follow-on request. Frontend screens, reminder/alert engines, full report aggregation, and optional AI remain future work.
