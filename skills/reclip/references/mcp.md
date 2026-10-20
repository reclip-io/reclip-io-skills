# Reclip MCP

Connect a Streamable HTTP client to `https://www.reclip.io/api/mcp`, with its workspace key configured privately in the `Authorization: Bearer` header. Protocol `2025-11-25` and `2025-06-18` are supported. POST accepts JSON-RPC with `Content-Type: application/json` and `Accept: application/json, text/event-stream`. This server is stateless; GET/DELETE return 405. Clients must support private API-key headers. This endpoint does not provide OAuth sign-in; use the installable skill when the assistant requires OAuth.

`tools/list` returns all 30 product tools and all 28 resource operations. The [snapshot](mcp-tools.json) includes their input schemas. Product calls use `reclip_TOOL` with `input`, optional schema-specific `options`, `maximum_credits`, and `idempotency_key`. Quotes and resource calls wrap request JSON under `body` and pass path arguments such as `id` separately.

Call `reclip_quote_job` with `body: {tool, input, options}` as appropriate, then use the corresponding product tool with the authorized credit cap. Poll using `reclip_get_job` with `id`; read `result` and `outputs`. Reuse exact payloads and idempotency keys for uncertain submits. Errors in tool execution return `isError: true`, with the REST error in `structuredContent` and the text content. JSON-RPC errors identify invalid methods or arguments.

Scopes and workspace credits are shared with REST. A connected client does not authorize additional paid operations, exports, or tool chains.
