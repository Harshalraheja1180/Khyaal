# MemoryCare database design

## Scope and conventions

This is the PostgreSQL schema reference implemented with SQLAlchemy 2.x and Alembic. Migrations are the executable source of truth. Tables use UUID primary keys for domain records, UTC `TIMESTAMPTZ` timestamps, explicit foreign keys, indexes for relationship/date queries, and database constraints for invariants. Avoid storing derived aggregates when they can be calculated safely.

Use `created_at` and `updated_at` where appropriate. Keep timestamps in UTC and store an IANA timezone on the dependent profile for schedules and display. Store date-of-birth only if a feature requires it; age bands are preferable for demo and analytics.

## Identity, role, and authorization tables

| Table | Important fields and constraints | Purpose |
| --- | --- | --- |
| `users` | `id`, normalized unique `email` (nullable only for a supported invitation flow), `password_hash`, `status`, timestamps | Login identity; never store plaintext passwords |
| `user_roles` | `user_id`, `role`, granted/revoked timestamps; unique active `(user_id, role)` | `ADMIN`, `GUARDIAN`, `DEPENDENT` role assignments |
| `guardian_dependent_links` | `id`, guardian/dependent user FKs, `status`, invitation/approval/revocation timestamps, `created_by`; unique active pair | Explicit, auditable care relationship; no inferred access from email or family name |
| `data_permissions` | `id`, link FK, `category`, `allowed`, grantor, version, granted/revoked timestamps; unique current category per link | Field/category scope such as routines, reports, wellbeing, media, location, emergency events |
| `consent_records` | `id`, subject user FK, guardian/link FK nullable, purpose, policy version, authorization basis, recorded/revoked timestamps, actor | Versioned consent/authorization history; append/revoke rather than erase history |
| `audit_logs` | `id`, actor FK nullable, action, resource type/id, dependent scope, timestamp, outcome, minimal request metadata | Security-relevant access and changes; do not copy sensitive payloads into logs |

Role and link checks belong in server authorization code as well as database integrity rules. Revoking a link or permission takes effect for the next request.

## Profiles and accessible preferences

| Table | Important fields | Purpose |
| --- | --- | --- |
| `dependent_profiles` | unique `user_id`, preferred display name, mode, timezone, locale, optional age band, timestamps | Minimal dependent-specific configuration |
| `accessibility_preferences` | unique profile FK, text scale, contrast, audio/read-aloud, reduced motion, interaction options | User experience preferences, separate from security authorization |

Do not put a home address or detailed medical history in a general profile. Add narrowly scoped fields only when a real feature and retention policy require them.

## Care plan and activity data planned for later phases

| Table family | Tables and key relationships | Notes |
| --- | --- | --- |
| Routine configuration | `reminders`, `reminder_occurrences`, `reminder_actions` | Recurrence/timezone rule, scheduled instance, and append-only complete/snooze/skip action history are separate. Unique occurrence key prevents duplicate generation. |
| Contacts | `emergency_contacts` | Belongs to a dependent; configurable relationship and contact method; not a hard-coded emergency number. |
| Personal memory | `familiar_people`, `familiar_places`, `familiar_objects` | Scoped to dependent; references to approved media are optional and permission-controlled. |
| Media | `media_assets` | Owner/dependent FK, private storage key, detected media type, size, checksum, upload status, retention/deletion timestamps. Never store public URL as the access mechanism. |
| Activities | `activities`, `activity_questions`, `activity_attempts` | Guardian-configured recognition/orientation content and engagement history; explicitly non-diagnostic. |
| Games | `games`, `game_sessions` | Game definition and participation/session metadata. Do not label results as a medical score. |
| Wellbeing | `wellbeing_checkins` | Optional response, refusal/skip status, timestamp, and sharing scope; treat as sensitive. |
| Alerts | `alerts`, `alert_events`, `notification_deliveries` | Alert lifecycle, deduplication key, acknowledgement/resolution history, channel delivery/retry status. |
| Location (optional) | `location_permissions`, `location_events` | Off by default, short retention, purpose/viewer scopes, permission checks and access audit. Omit location capture unless explicitly enabled. |

## Relationships and deletion

- Every dependent-owned record must have a foreign key to the dependent profile or user and an index beginning with that scope key.
- A guardian can read a dependent-owned row only through an active relationship and allowed category. The query must apply that scope in the backend.
- Use restrictive deletion for users with legal/audit obligations. Use explicit anonymization/purge workflows for personal content after revocation or retention expiry. Media deletion must remove the object and mark/remove its reference consistently.
- `audit_logs` and revoked consent/link history have a documented retention policy; they should not cascade away with ordinary profile edits.
- Migration tests in future phases must validate constraints and downgrade/upgrade behavior. No migration exists in Phase 1.

## Indexes and constraints

Plan indexes for normalized user email, `(guardian_user_id, status)`, `(dependent_user_id, status)`, `(dependent_id, scheduled_at)` on occurrences, `(dependent_id, created_at)` on event/history tables, active alert status/date, and media owner/status. Add checks for valid enum values, positive media size, nonnegative durations, and consistent lifecycle timestamps. Add unique constraints for one reminder occurrence per reminder/scheduled instant and one active permission per link/category.

## Phase boundary

The current backend migration covers the identity, roles/permissions, links, profiles, care-plan, memory/media, activity, wellbeing, alert, location-permission/event, consent, notification, and audit tables listed above. Operational behavior for alerts/location/notifications and full CRUD for every table is still future work.
