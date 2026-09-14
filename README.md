# Reclip Agent Skills

An installable Reclip skill with a zero-dependency Python client for video, image, and audio workflows. Modeled after [glade-agent-skills](https://github.com/ricciflow-api/glade-agent-skills): one focused skill, executable client, operation references, and offline tests.

**Status:** client release 1.0.0 targets Reclip API **1.0.0-beta.1**, backend `api-dev` commit `2059685938ec59f5277269b2ca73b723253be45d`. The API must be deployed and enabled by its operator. Publishing this repository does not enable production endpoints or certify live provider execution.

## Install

With the Skills CLI:

```bash
npx skills add ricciflow-api/reclip-io-skills
```

Select `reclip` and your agent in the installer. Alternatively, clone the repository and copy **the entire** `skills/reclip` directory to your agent's skill directory, such as `.agents/skills/reclip` for a project. The installed directory is self-contained; it does not depend on repository-root files.

For Codex, ask the skill installer to install `skills/reclip` from `https://github.com/ricciflow-api/reclip-io-skills`, then reload skills if your agent requires it. Invoke `$reclip`, or ask for a Reclip media workflow.

## Configure and use

Requires Python 3.9+ and an API-enabled paid Reclip workspace. Create a scoped workspace key in Settings → API Keys. Supply `RECLIP_API_KEY` via your environment or secret manager; do not put it in chat or a command argument. `.env.example` documents the variables. The client does **not** automatically load `.env` files.

`RECLIP_API_BASE_URL` defaults to `https://www.reclip.io/api/v1`. Override it only for the Reclip deployment you intend to trust with the key. HTTPS is required except for loopback development.

From a checkout:

```bash
python3 skills/reclip/scripts/reclip_api.py --help
python3 skills/reclip/scripts/reclip_api.py tool ai_clipper --offline
python3 skills/reclip/scripts/reclip_api.py identity
python3 skills/reclip/scripts/reclip_api.py tools
```

Example agent request:

> Use $reclip to extract audio from my source.mp4. Spend at most 20 credits, save the MP3 locally, and reuse the same job if a request times out.

Budget numbers are user choices, not advertised prices. See the [workflow guide](skills/reclip/references/workflows.md) for complete upload, submit, wait, download, clip export, and chaining examples.

## Coverage

The bundled catalog describes all 24 server tools across clipping/captions, video/image generation, watermark removal, voiceover/dubbing, transcription, downloading, and media conversion. Individual tools retain their source, plan, input, and model restrictions. Browser-only Gemini watermark tools are excluded.

The client covers all 23 resource operations in the pinned API contract. It adds durable idempotency state, bounded polling, upload recovery, signed downloads, and explicit per-job credit caps. Exports use editor revisions and saved state; this beta contract provides **no export quote or hard credit cap**. There is no MCP server or natural-language agent endpoint.

- [Skill instructions](skills/reclip/SKILL.md)
- [Operations and scopes](skills/reclip/references/operations.md)
- [API documentation repository](https://github.com/ricciflow-api/reclip-io-api-docs)
- [Backend API branch](https://github.com/asterism-software/reclip-io/tree/api-dev)

## Development

```bash
python3 scripts/validate_skill.py
python3 -m unittest discover -s skills/reclip/tests -v
```

`npm test` runs the same checks for maintainers who use Node. Runtime installation needs neither Node nor pip packages. CI runs offline tests across supported Python versions. Tests use fake transports; they do not incur credits or prove deployment/provider availability. Optional `python3 scripts/verify_live.py` makes authenticated read-only checks against the configured deployment and never submits jobs.

MIT licensed. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
