# YouTube, TikTok, Instagram, and Twitch video APIs

Use these templates when the source is a supported platform URL. They describe ten direct source/tool combinations across six existing tools; the complete catalog still contains 30 tools. Each template has a sample source URL and an illustrative `maximum_credits: 100`. Replace the source and set the credit cap to the user's authorized budget before quoting or submitting.

| Task | Request template | Existing tool | Documentation |
|---|---|---|---|
| [YouTube Video Downloader](https://www.reclip.io/api/tools/youtube-video-downloader) | [JSON](platform-requests/youtube-video-downloader.json) | `video_downloader` | [Guide](https://www.reclip.io/docs/platforms/youtube-video-downloader) |
| [TikTok Video Downloader](https://www.reclip.io/api/tools/tiktok-video-downloader) | [JSON](platform-requests/tiktok-video-downloader.json) | `video_downloader` | [Guide](https://www.reclip.io/docs/platforms/tiktok-video-downloader) |
| [Instagram Video Downloader](https://www.reclip.io/api/tools/instagram-video-downloader) | [JSON](platform-requests/instagram-video-downloader.json) | `video_downloader` | [Guide](https://www.reclip.io/docs/platforms/instagram-video-downloader) |
| [YouTube Video Clipping](https://www.reclip.io/api/tools/youtube-ai-clipper) | [JSON](platform-requests/youtube-ai-clipper.json) | `ai_clipper` | [Guide](https://www.reclip.io/docs/platforms/youtube-ai-clipper) |
| [Twitch VOD Clipping](https://www.reclip.io/api/tools/twitch-vod-clipper) | [JSON](platform-requests/twitch-vod-clipper.json) | `ai_clipper` | [Guide](https://www.reclip.io/docs/platforms/twitch-vod-clipper) |
| [YouTube AI B-Roll](https://www.reclip.io/api/tools/youtube-ai-broll) | [JSON](platform-requests/youtube-ai-broll.json) | `ai_broll` | [Guide](https://www.reclip.io/docs/platforms/youtube-ai-broll) |
| [Twitch VOD AI B-Roll](https://www.reclip.io/api/tools/twitch-vod-ai-broll) | [JSON](platform-requests/twitch-vod-ai-broll.json) | `ai_broll` | [Guide](https://www.reclip.io/docs/platforms/twitch-vod-ai-broll) |
| [YouTube Video Captions](https://www.reclip.io/api/tools/youtube-ai-captions) | [JSON](platform-requests/youtube-ai-captions.json) | `ai_captions` | [Guide](https://www.reclip.io/docs/platforms/youtube-ai-captions) |
| [YouTube Transcript](https://www.reclip.io/api/tools/youtube-transcript) | [JSON](platform-requests/youtube-transcript.json) | `youtube_transcript` | [Guide](https://www.reclip.io/docs/tools/youtube-transcript) |
| [TikTok Transcript](https://www.reclip.io/api/tools/tiktok-transcript) | [JSON](platform-requests/tiktok-transcript.json) | `tiktok_transcript` | [Guide](https://www.reclip.io/docs/tools/tiktok-transcript) |

The task names link to the matching public API landing pages. The [platform directory](https://www.reclip.io/platforms) links all four platform overviews.

## Choose the accepted source

- **Downloader:** YouTube, TikTok, and Instagram use `video_downloader` with a matching `platform` and HTTPS `source_url`. A source must remain accessible. Formats, resolution, audio, and download availability depend on the source; set `maximum_download_bytes` and inspect the live catalog before choosing formats. Downloading does not guarantee watermark-free files or access to private media.
- **Clipping and B-roll:** YouTube video URLs and recorded Twitch VOD URLs use `ai_clipper` or `ai_broll`. Twitch inputs require the form `https://www.twitch.tv/videos/<numeric ID>`; channel pages, live stream capture, and Twitch clip URLs are outside this contract. Select the analysis or editing range in `options`.
- **Caption rendering:** `ai_captions` accepts a YouTube URL with source duration and caption options. It returns a captioned video asset. It does not edit captions on an existing YouTube upload.
- **Transcript extraction:** `youtube_transcript` and `tiktok_transcript` retrieve an existing accessible caption track, optionally with timestamps. They do not fall back to speech recognition when captions are missing. Use `transcription` with a compatible video asset for speech-to-text.

Clipping, B-roll, captions, and transcript requests have no downloader `platform` field. URL-based editing requests supply one video source: omit `asset_id` when sending `source_url`. Other editing tools accept compatible uploaded or downloaded assets in separate jobs. For example, download an Instagram video first, then pass its asset ID to a separately quoted transcription or editing request. Shorts, Reels, and TikTok-shaped outputs do not imply extra source integrations or automatic publishing.

## Use a request with the Python client

Resolve the installed skill directory first. In the commands below, `SKILL_DIR` is that absolute directory and `CLIENT` is `$SKILL_DIR/scripts/reclip_api.py`. Copy the selected template into a private run directory, replace its sample URL, and set the authorized cap. The filename selects documentation only; the request's `tool` remains the existing API tool code.

```bash
python3 "$CLIENT" tool video_downloader --offline
python3 "$CLIENT" catalog video_downloader
python3 "$CLIENT" quote "$RUN_DIR/request.json"
python3 "$CLIENT" run "$RUN_DIR/request.json" \
  --state "$RUN_DIR/youtube-download.state.json" \
  --maximum-credits "$APPROVED_CREDIT_CAP"
```

`RECLIP_API_KEY` belongs in the client's environment, outside chat prompts and request files. `tool --offline` reads the pinned contract without credentials; live discovery and quotes use the configured Reclip deployment. A quote estimates cost and does not lock a price. The `run` command quotes before a new submission, persists its idempotency key, enforces the lower of the file cap and CLI cap, and polls with a bounded timeout. Resume with the same state, request, base URL, and key after an uncertain result. If the job is still running when polling times out, check that job again rather than creating a replacement.

On success inspect `result` and `outputs`, then download a retained output asset with `download ASSET_ID --output PATH`. For another operation, use a separate state file and account for the remaining authorized credits. See [the client task examples](workflows.md) for uploads, downloads, and chaining.

## Use the same request through MCP

Discover the current schema with `tools/list`. Quote by calling `reclip_quote_job` with the full request under `body`. Submit with `reclip_TOOL`, passing the template's `input`, the approved `maximum_credits`, and a stable `idempotency_key`. Poll `reclip_get_job` with the returned job `id` and inspect both `result` and `outputs`. See [MCP transport and tool names](mcp.md).

Example agent requests:

> Use Reclip to quote downloading this YouTube video: [YouTube URL]. Use `video_downloader` with `platform: youtube` and a download size cap. Show the estimate, then use my approved credit budget to submit and retrieve the video asset.

> Create highlights from this recorded Twitch VOD: [numeric VOD URL]. Inspect `ai_clipper`, quote the requested analysis range, then submit within my approved budget and return the completed clips. Reuse the same job if a request times out.

> Retrieve the available transcript for this TikTok video: [TikTok URL]. Use `tiktok_transcript` with timestamps and quote first. If it has no existing captions, report that result before considering a separately budgeted download and speech transcription job.
