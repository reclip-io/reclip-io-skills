# Workflows

In these examples, `CLIENT` is the absolute path to the installed `scripts/reclip_api.py`. Set it once for your installation. State and request files belong in a private working directory, not inside the installed skill. UUIDs below are placeholders; replace them with actual API IDs. Credit limits are examples, not current prices or implied user authorization.

## Upload, convert, download

```bash
python3 "$CLIENT" identity
python3 "$CLIENT" tool mp4_to_mp3
python3 "$CLIENT" upload source.mp4 --tool mp4_to_mp3 --state upload.state.json
```

Create `request.json`, replacing the asset ID with the confirmed upload result:

```json
{
  "tool": "mp4_to_mp3",
  "input": {
    "asset_id": "00000000-0000-4000-8000-000000000001",
    "file_name": "source.mp4",
    "operation": "extract_mp3"
  }
}
```

```bash
python3 "$CLIENT" quote request.json
python3 "$CLIENT" run request.json --state convert.state.json --maximum-credits 20 --timeout 1800
python3 "$CLIENT" download OUTPUT_ASSET_ID --output result.mp3
```

Use the asset ID from `outputs` in the successful job, not the upload ID. `run` stops on failure/cancellation or timeout. Resume it with the identical command and state: it retrieves the saved job rather than making another one. `submit` returns the accepted ID immediately; `wait ID --timeout 1800 --interval 5` resumes polling. `status ID` reads once. A timeout does not cancel a job.

Upload recovery first attempts to confirm the saved asset: the previous PUT may already have finished. If it has not, the same signed upload authorization is reused. An expired upload URL requires a new upload state; preserve the old state for reconciliation. Upload intents themselves are not idempotent: a lost intent response can leave an unused asset, but does not create a paid media job. State temporarily holds a signed URL until confirmation, then removes it. Protect the run directory; never commit or share state files. Downloads fetch a fresh signed URL and never forward the API key to storage. Existing output files are not overwritten.

## Clipping and editing

Query `tool ai_clipper` for the full schema. A range-limited uploaded-video request can be:

```json
{
  "tool": "ai_clipper",
  "input": {"asset_id": "00000000-0000-4000-8000-000000000001"},
  "options": {
    "analysis_start_seconds": 0,
    "analysis_end_seconds": 60,
    "captions_enabled": true,
    "language": "en"
  },
  "maximum_outputs": 2
}
```

Set the analysis range to the actual media and user's scope. After the job succeeds:

```bash
python3 "$CLIENT" clips JOB_ID
python3 "$CLIENT" clip CLIP_ID
```

Build an edit object from that clip's current values, containing exactly `captions_enabled`, `caption_group_size`, `caption_style`, and `caption_words`. Do not pass the entire GET response to PATCH. Retain unchanged values. Each word has `id`, `start_seconds`, `end_seconds`, `text`, and optional `color`. Enabled captions require words; at most 900 words. Group size is 1–6.

The style fields are `font_family`, `font_size` (24–240), `position_y_percent` (6–94), `base_color`, `highlight_color`, `outline_color`, `background_color`, `outline_width` (0–16), `background_opacity` (0–100), `word_spacing` (0–12), and optional `layout_version` (2). Use uppercase hex colors and valid font/preset values from the catalog. Server validation is authoritative.

```bash
python3 "$CLIENT" edit-clip CLIP_ID edit.json
python3 "$CLIENT" export-clip CLIP_ID --revision REVISION_FROM_EDIT --state export.state.json
python3 "$CLIENT" wait EXPORT_JOB_ID
```

An export uses the exact editor revision returned by the edit. A stale revision returns a conflict; inspect the clip and user-intended edit before creating another request. Export is potentially billable and has no estimate/cap endpoint in this contract. Proceed only within explicit export authorization that does not require an enforceable hard cap. Do not invent `maximum_credits` on this endpoint.

## Chaining tools within a total budget

Select an output from job A by its media type and intended role. Wait for success before passing its asset ID to job B; do not pass an expiring download URL as an asset identifier. Inspect B's live schema: single-asset tools generally use `asset_id`, while generation/composition tools may need `input_asset_ids`, `motion_asset_id`, `character_asset_id`, `product_asset_id`, or `avatar_asset_id`.

Keep a separate stable state file per intentional job. Set each cap to at most the unspent authorized total. After A settles, subtract its actual credits before quoting B. If actual credits are unavailable, conservatively reserve A's full submitted cap; do not count estimated credits as settled spend. Include other in-flight jobs' full caps. Do not automatically launch parallel paid steps without accounting for their combined caps. Failed/canceled jobs may consume credits: reconcile before retrying. Skip exports if a strict total cap cannot be guaranteed.

## Two project resources

`create-project --title TITLE` creates an organizational container. Its ID is the **outer** job envelope's `project_id`.

`create-composition --title TITLE` creates the Roblox Rant composition required by that tool's **input** `project_id`; `composition ID` reads its state. These are different resources even though both use UUIDs. Read `tool roblox_rant` and `catalog roblox_rant` before composing the request. Creating a composition does not create a media job.
