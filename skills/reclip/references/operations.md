# API operations

All paths use `/api/v1`. The Python client and MCP expose every operation. See the bundled JSON snapshots for provenance and schemas.

| Operation                        | Endpoint                               | Access                                                                                              |
| -------------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `get_b-roll_composition`         | `GET /broll/{id}`                      | Required scopes: jobs:read. Beta API. Availability depends on deployment enablement.                |
| `edit_b-roll_composition`        | `PATCH /broll/{id}`                    | Required scopes: assets:write. Beta API. Availability depends on deployment enablement.             |
| `export_b-roll_composition`      | `POST /broll/{id}/exports`             | Required scopes: jobs:write. Beta API. Availability depends on deployment enablement.               |
| `quote_b-roll_shot_regeneration` | `POST /broll/{id}/regenerate-quote`    | Required scopes: jobs:write. Beta API. Availability depends on deployment enablement.               |
| `regenerate_b-roll_shot`         | `POST /broll/{id}/regenerate`          | Required scopes: jobs:write. Beta API. Availability depends on deployment enablement.               |
| `create_roblox_composition`      | `POST /tools/roblox_rant/projects`     | Required scopes: projects:write. Beta API. Availability depends on deployment enablement.           |
| `get_roblox_composition`         | `GET /tools/roblox_rant/projects/{id}` | Required scopes: projects:read. Beta API. Availability depends on deployment enablement.            |
| `get_api_identity`               | `GET /me`                              | Beta API. Availability depends on deployment enablement.                                            |
| `list_tools`                     | `GET /tools`                           | Beta API. Availability depends on deployment enablement.                                            |
| `get_tool_schema`                | `GET /tools/{tool}`                    | Beta API. Availability depends on deployment enablement.                                            |
| `get_tool_catalog`               | `GET /tools/{tool}/catalog`            | Beta API. Availability depends on deployment enablement.                                            |
| `create_upload`                  | `POST /assets/uploads`                 | Required scopes: assets:write. Beta API. Availability depends on deployment enablement.             |
| `confirm_upload`                 | `POST /assets/{id}/confirm`            | Required scopes: assets:write. Beta API. Availability depends on deployment enablement.             |
| `get_asset`                      | `GET /assets/{id}`                     | Required scopes: assets:read. Beta API. Availability depends on deployment enablement.              |
| `get_download_url`               | `GET /assets/{id}/download`            | Required scopes: assets:read. Beta API. Availability depends on deployment enablement.              |
| `quote_job`                      | `POST /jobs/quote`                     | Required scopes: jobs:write. Beta API. Availability depends on deployment enablement.               |
| `create_job`                     | `POST /jobs`                           | Required scopes: jobs:write. Beta API. Availability depends on deployment enablement.               |
| `list_jobs`                      | `GET /jobs`                            | Required scopes: jobs:read. Beta API. Availability depends on deployment enablement.                |
| `get_job`                        | `GET /jobs/{id}`                       | Required scopes: jobs:read. Beta API. Availability depends on deployment enablement.                |
| `cancel_job`                     | `POST /jobs/{id}/cancel`               | Required scopes: jobs:write. Beta API. Availability depends on deployment enablement.               |
| `list_job_clips`                 | `GET /jobs/{id}/clips`                 | Required scopes: jobs:read + assets:read. Beta API. Availability depends on deployment enablement.  |
| `get_clip`                       | `GET /clips/{id}`                      | Required scopes: assets:read. Beta API. Availability depends on deployment enablement.              |
| `save_clip_captions`             | `PATCH /clips/{id}`                    | Required scopes: assets:write. Beta API. Availability depends on deployment enablement.             |
| `export_clip_revision`           | `POST /clips/{id}/exports`             | Required scopes: jobs:write + assets:read. Beta API. Availability depends on deployment enablement. |
| `create_project`                 | `POST /projects`                       | Required scopes: projects:write. Beta API. Availability depends on deployment enablement.           |
| `list_projects`                  | `GET /projects`                        | Required scopes: projects:read. Beta API. Availability depends on deployment enablement.            |
| `get_project`                    | `GET /projects/{id}`                   | Required scopes: projects:read. Beta API. Availability depends on deployment enablement.            |
| `get_usage_and_limits`           | `GET /usage`                           | Required scopes: usage:read. Beta API. Availability depends on deployment enablement.               |
