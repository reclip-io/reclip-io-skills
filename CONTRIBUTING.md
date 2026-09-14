# Contributing

Keep `skills/reclip` independently installable and the runtime compatible with Python 3.9+ without third-party packages. Add behavioral tests for request, billing, retry, or credential-handling changes.

Run `python3 scripts/validate_skill.py` and `python3 -m unittest discover -s skills/reclip/tests -v` before opening a pull request. Do not run paid jobs as part of CI.

The JSON references are snapshots generated from the backend public API contract at the commit recorded in each `source` object. When updating them, regenerate both from the same backend revision, compare every method/path and tool input schema, update the client and documentation, and record the new API version. Never add an unsupported route as if it were deployed. The repository validator checks snapshot/client coverage; live deployment parity requires the optional read-only check and provider acceptance belongs to the backend release process.

Do not commit keys, signed URLs, local media, or run state. Do not broaden API scopes or budget authorization as a side effect of a documentation change.
