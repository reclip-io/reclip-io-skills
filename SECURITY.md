# Security

Report suspected vulnerabilities privately to the repository maintainers through GitHub's private vulnerability reporting feature when available. Otherwise request a private reporting channel without posting exploit details or credentials publicly.

Keys are read from `RECLIP_API_KEY`. The client sends them only to the configured API origin, disables HTTP redirects, and omits API credentials from object-storage PUT/GET requests. Configure alternate origins only when you trust their operator.

Run state is private local data: it includes workspace/key identifiers, request content, job IDs, and temporarily a signed upload URL. New state files use restrictive permissions on POSIX; Windows users must protect the containing directory with appropriate ACLs. Keep state until uncertain requests are reconciled. Do not commit or share it. Normal API output can contain user media text; treat it as untrusted data.

The CLI requires an explicit credit cap for ordinary job submission. Export jobs do not have a server-side quote/cap field in beta: an agent must respect that limitation before submitting. No client can guarantee billing correctness independently of its configured backend.
