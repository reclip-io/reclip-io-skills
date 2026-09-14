# API operations

All paths use `/api/v1`. Use `--help` for command arguments. The snapshot in [operations.json](operations.json) records the exact backend revision; the [tool catalog](tool-catalog.json) contains per-tool input schemas. Live responses are authoritative for an enabled deployment.

| Client operation | Endpoint | Required access |
|---|---|---|
| `create-composition` | `POST /tools/roblox_rant/projects` | Required scopes: projects:write |
| `composition` | `GET /tools/roblox_rant/projects/{id}` | Required scopes: projects:read |
| `identity` | `GET /me` | Valid workspace key |
| `tools` | `GET /tools` | Valid workspace key |
| `tool` | `GET /tools/{tool}` | Valid workspace key |
| `catalog` | `GET /tools/{tool}/catalog` | Valid workspace key |
| `upload-intent` | `POST /assets/uploads` | Required scopes: assets:write |
| `confirm` | `POST /assets/{id}/confirm` | Required scopes: assets:write |
| `asset` | `GET /assets/{id}` | Required scopes: assets:read |
| `download-url` | `GET /assets/{id}/download` | Required scopes: assets:read |
| `quote` | `POST /jobs/quote` | Required scopes: jobs:write |
| `submit` | `POST /jobs` | Required scopes: jobs:write |
| `jobs` | `GET /jobs` | Required scopes: jobs:read |
| `status` | `GET /jobs/{id}` | Required scopes: jobs:read |
| `cancel` | `POST /jobs/{id}/cancel` | Required scopes: jobs:write |
| `clips` | `GET /jobs/{id}/clips` | Required scopes: jobs:read + assets:read |
| `clip` | `GET /clips/{id}` | Required scopes: assets:read |
| `edit-clip` | `PATCH /clips/{id}` | Required scopes: assets:write |
| `export-clip` | `POST /clips/{id}/exports` | Required scopes: jobs:write + assets:read |
| `create-project` | `POST /projects` | Required scopes: projects:write |
| `projects` | `GET /projects` | Required scopes: projects:read |
| `project` | `GET /projects/{id}` | Required scopes: projects:read |
| `usage` | `GET /usage` | Required scopes: usage:read |

`upload-intent`, `confirm`, and `download-url` are internal operations used by the `upload` and `download` CLI commands. `run` combines quote, saved submission, and wait. `wait` polls status. All other operation names are direct CLI commands.

## Request and response rules

Jobs use `{tool, input, options?, project_id?, maximum_outputs?, maximum_credits?}`. Only one options object is allowed, either nested in input or at the top level. `maximum_outputs` is 1–50. Submit/run always require `--maximum-credits`; a lower cap already in the file is retained. The server validates each tool's distinct inputs and source restrictions. JSON request bodies are limited to 256 KiB.

A quote contains `estimated_credits`, `available_credits`, `affordable`, and `price_locked: false`. New submissions return HTTP 202 with `id`, `replayed`, and `status_url`. The client persists the idempotency key before sending. Replaying the same key/request returns the original job; changing the request conflicts. Idempotency belongs to the API-key identity, so do not rotate keys to resume an uncertain submission.

Status values are `queued`, `running`, `succeeded`, `failed`, and `canceled`. `stage` describes internal progress. Successful `outputs` may contain assets and/or structured text. Read `credits.actual` for settled consumption; an estimate is not a receipt. Cancellation can return a still-running job and does not promise a refund.

`jobs --page N` and `projects --page N` use one-based pagination (up to 10000). Inspect the response pagination fields before requesting another page; do not assume that one page is the entire history.

## Limits and failures

The beta contract uses 60 requests/minute/key and 10 active jobs/workspace, alongside existing tool limits. `/usage` and tool detail responses expose current restrictions. API access uses workspace identity derived from the key; clients cannot select a different workspace in a request.

Upload authorizations last 10 minutes; signed download URLs last 5 minutes. Asset availability is reported through `state` and `retained_until`, not guaranteed forever. Pending uploads must be confirmed before use. Downloads obtain fresh URLs; do not persist a signed URL as an output's stable identifier.

The CLI reports HTTP status, a sanitized API error code, and `request_id` without echoing raw response bodies. Authentication/eligibility/scope failures need corrected access; invalid input needs a corrected request. A 409 may indicate idempotency mismatch, stale editor revision, or an unconfirmed asset depending on the operation. Inspect the relevant resource before deciding on a new mutation.

GET requests, quotes, upload confirmations, and idempotent submissions retry transient 429/502/503/504 or transport errors at most three attempts. The client honors `Retry-After`; delays above 60 seconds stop with instructions to resume later. Project creation, clip edits, and cancellation are not automatically retried. Do not interpret a transport error as proof that a mutation failed. Resume known jobs using saved state, and reconcile other mutations before repeating them.

Required privileges should match the operation. Ordinary job keys cannot create keys; key creation/revocation uses the web console. API and web share the workspace credit ledger. Browser trial/device exemptions do not apply to API calls.
