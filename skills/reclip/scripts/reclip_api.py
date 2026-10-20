#!/usr/bin/env python3
"""Zero-dependency Reclip API CLI. Python 3.9+. See --help for commands."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

VERSION = "1.1.0"
DEFAULT_BASE = "https://www.reclip.io/api/v1"
MAX_JSON = 1536 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
TERMINAL = {"succeeded", "failed", "canceled"}
REFERENCES = Path(__file__).resolve().parents[1] / "references"
CATALOG = json.loads((REFERENCES / "tool-catalog.json").read_text(encoding="utf-8"))
TOOLS = tuple(t["id"] for t in CATALOG["tools"])
OPERATIONS = {
    "broll": ("GET", "/broll/{id}"),
    "edit-broll": ("PATCH", "/broll/{id}"),
    "export-broll": ("POST", "/broll/{id}/exports"),
    "quote-broll-shot": ("POST", "/broll/{id}/regenerate-quote"),
    "regenerate-broll-shot": ("POST", "/broll/{id}/regenerate"),
    "identity": ("GET", "/me"), "tools": ("GET", "/tools"),
    "tool": ("GET", "/tools/{tool}"), "catalog": ("GET", "/tools/{tool}/catalog"),
    "usage": ("GET", "/usage"), "asset": ("GET", "/assets/{id}"),
    "upload-intent": ("POST", "/assets/uploads"), "confirm": ("POST", "/assets/{id}/confirm"),
    "download-url": ("GET", "/assets/{id}/download"),
    "quote": ("POST", "/jobs/quote"), "submit": ("POST", "/jobs"),
    "jobs": ("GET", "/jobs"), "status": ("GET", "/jobs/{id}"),
    "cancel": ("POST", "/jobs/{id}/cancel"), "clips": ("GET", "/jobs/{id}/clips"),
    "clip": ("GET", "/clips/{id}"), "edit-clip": ("PATCH", "/clips/{id}"),
    "export-clip": ("POST", "/clips/{id}/exports"),
    "projects": ("GET", "/projects"), "project": ("GET", "/projects/{id}"),
    "create-project": ("POST", "/projects"),
    "create-composition": ("POST", "/tools/roblox_rant/projects"),
    "composition": ("GET", "/tools/roblox_rant/projects/{id}"),
}


class ClientError(RuntimeError):
    """Safe error without credentials, signed URLs or provider response bodies."""


class ApiError(ClientError):
    def __init__(self, status, code="request_failed", request_id="unknown"):
        self.status, self.code = status, code
        super().__init__("API HTTP {}: {}; request_id={}".format(status, code, request_id))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def integer(value, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or (maximum is not None and value > maximum):
        raise ClientError("Integer is outside the documented range.")
    return value


def identifier(value):
    if not isinstance(value, str):
        raise ClientError("A resource ID must be a UUID.")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ClientError("A resource ID must be a UUID.") from None
    if str(parsed) != value.lower():
        raise ClientError("Use the hyphenated UUID resource ID.")
    return str(parsed)


def encode_json(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        raise ClientError("Expected finite, serializable JSON values.") from None
    if len(encoded) > MAX_JSON:
        raise ClientError("API JSON bodies must not exceed 1.5 MiB.")
    return encoded


def read_json(path, state=False):
    try:
        data = Path(path).read_bytes()
        if len(data) > (MAX_RESPONSE if state else MAX_JSON):
            raise ClientError("JSON file exceeds the client size limit.")
        value = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (OSError, ValueError, UnicodeError):
        raise ClientError("Cannot read a valid JSON request file.") from None
    if not isinstance(value, dict):
        raise ClientError("The request must be a JSON object.")
    if not state:
        encode_json(value)
    return value


def job_payload(value, budget=None):
    if not isinstance(value, dict) or set(value) - {"tool", "input", "options", "project_id", "maximum_outputs", "maximum_credits"}:
        raise ClientError("Unsupported job envelope field.")
    if value.get("tool") not in TOOLS:
        raise ClientError("Choose a tool from the current Reclip catalog.")
    if not isinstance(value.get("input"), dict):
        raise ClientError("A job requires an input object.")
    if "options" in value and (not isinstance(value["options"], dict) or "options" in value["input"]):
        raise ClientError("Provide options once, as an object.")
    if "project_id" in value:
        identifier(value["project_id"])
    if "maximum_outputs" in value:
        integer(value["maximum_outputs"], 1, 50)
    result = dict(value)
    if budget is not None:
        integer(budget)
        # An explicit lower budget already in the file is never widened.
        result["maximum_credits"] = min(budget, integer(value.get("maximum_credits", budget)))
    elif "maximum_credits" in result:
        integer(result["maximum_credits"])
    encode_json(result)
    return result


def base_url(value):
    value = value.strip().rstrip("/")
    try:
        p = urllib.parse.urlsplit(value)
        port = p.port
    except ValueError:
        raise ClientError("Invalid RECLIP_API_BASE_URL.") from None
    if not p.hostname or p.username or p.password or p.query or p.fragment or p.path != "/api/v1":
        raise ClientError("API base must be an origin followed by /api/v1, without credentials, query or fragment.")
    if p.scheme != "https" and not (p.scheme == "http" and p.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise ClientError("Use HTTPS; HTTP is allowed only on loopback for local tests.")
    if port is not None and not 1 <= port <= 65535:
        raise ClientError("Invalid API port.")
    return value


def safe_code(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", value) else "unknown"


def read_response(response):
    raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ClientError("API response exceeds the client size limit.")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ClientError("The API returned non-JSON content.") from None
    if not isinstance(result, dict):
        raise ClientError("Expected a JSON object from the API.")
    return result


def retry_seconds(value, attempt):
    if value:
        try:
            seconds = float(value)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                seconds = 2 ** attempt
        if math.isfinite(seconds):
            # Do not retry earlier than a long server-requested delay.
            if seconds > 60:
                raise ClientError("Retry-After exceeds 60 seconds. Resume the saved request later.")
            return max(0, seconds)
    return 2 ** attempt


class Client:
    def __init__(self, base=None, key=None, opener=None, sleep=time.sleep, clock=time.monotonic):
        self.base = base_url(base or os.environ.get("RECLIP_API_BASE_URL", DEFAULT_BASE))
        self.key = key or os.environ.get("RECLIP_API_KEY", "")
        if not self.key or re.search(r"\s", self.key):
            raise ClientError("Configure RECLIP_API_KEY in your environment or secret manager; do not paste it into chat.")
        self.opener = opener or urllib.request.build_opener(NoRedirect)
        self.sleep, self.clock = sleep, clock

    def call(self, operation, resource=None, data=None, page=None, idempotency=None, deadline=None):
        if operation not in OPERATIONS:
            raise ClientError("Unsupported API operation.")
        method, path = OPERATIONS[operation]
        if "{tool}" in path:
            if resource not in TOOLS:
                raise ClientError("Unknown server tool.")
            path = path.replace("{tool}", resource)
        if "{id}" in path:
            path = path.replace("{id}", identifier(resource))
        if page is not None:
            if operation not in {"jobs", "projects"}:
                raise ClientError("This operation does not accept pagination.")
            path += "?page=" + str(integer(page, 1, 10000))
        body = encode_json(data) if data is not None else None
        if operation in {"submit", "export-clip", "export-broll", "regenerate-broll-shot"} and not idempotency:
            raise ClientError("Use a durable state file for job submission.")
        if idempotency and not re.fullmatch(r"[A-Za-z0-9:_-]{8,160}", idempotency):
            raise ClientError("Invalid idempotency key.")
        headers = {"Authorization": "Bearer " + self.key, "Accept": "application/json", "User-Agent": "reclip-io-skills/" + VERSION}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if idempotency:
            headers["Idempotency-Key"] = idempotency
        retryable = method == "GET" or idempotency is not None or operation in {"quote", "confirm"}
        for attempt in range(3):
            remaining = deadline - self.clock() if deadline is not None else 30
            if remaining <= 0:
                raise ClientError("Polling timeout reached. Resume using the saved job ID or state file.")
            try:
                req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
                with self.opener.open(req, timeout=min(30, remaining)) as response:
                    return read_response(response)
            except urllib.error.HTTPError as error:
                if retryable and attempt < 2 and error.code in {429, 502, 503, 504}:
                    delay = retry_seconds(error.headers.get("Retry-After"), attempt)
                else:
                    try:
                        failure = read_response(error)
                    except ClientError:
                        failure = {}
                    detail = failure.get("error", {})
                    code = detail.get("code") if isinstance(detail, dict) else None
                    raise ApiError(error.code, safe_code(code), safe_code(failure.get("request_id"))) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if not retryable or attempt >= 2:
                    raise ClientError("Transport outcome is uncertain. Preserve state; do not submit a replacement job.") from None
                delay = 2 ** attempt
            if deadline is not None and self.clock() + delay >= deadline:
                raise ClientError("Polling timeout reached. Resume using the saved job ID or state file.")
            self.sleep(delay)
        raise ClientError("Request retry limit reached.")


@contextmanager
def locked_state(path):
    """OS-released lock: process death does not leave a stale locked run."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    stream = os.fdopen(fd, "r+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield path
    except (BlockingIOError, PermissionError):
        raise ClientError("This run state is already in use, or is not writable.") from None
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()
        # Keep the empty lock file: unlinking could create two separately locked inodes.


def save_state(path, state):
    fd, temp = tempfile.mkstemp(prefix="." + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def identity_context(client):
    identity = client.call("identity")
    return {"base_url": client.base, "workspace_id": identity["workspace_id"], "key_id": identity["key_id"]}


def check_context(state, context):
    if state.get("context") != context:
        raise ClientError("State belongs to another API base, workspace or key. Resolve the previous run before submitting under a replacement key.")


def submit_saved(client, operation, payload, state_path, resource=None):
    if operation not in {"submit", "export-clip", "export-broll", "regenerate-broll-shot"}:
        raise ClientError("Only job creation and exports use saved submission state.")
    with locked_state(state_path) as path:
        context = identity_context(client)
        request = {"operation": operation, "resource": resource, "body": payload}
        if path.exists():
            state = read_json(path, state=True)
            check_context(state, context)
            if state.get("kind") != "submission" or state.get("request") != request:
                raise ClientError("State does not match this request; use a new file only for an intentional new job.")
        else:
            if operation == "submit":
                budget = integer(payload.get("maximum_credits"))
                quote = client.call("quote", data=payload)
                estimate = quote.get("estimated_credits")
                if isinstance(estimate, bool) or not isinstance(estimate, (int, float)) or not math.isfinite(estimate) or estimate < 0:
                    raise ClientError("The API did not return a usable quote.")
                if estimate > budget or not quote.get("affordable"):
                    raise ClientError("Quote exceeds the authorized budget or available balance; no job was submitted.")
            if operation == "regenerate-broll-shot":
                quote = client.call("quote-broll-shot", resource, payload)
                if quote.get("credits", float("inf")) > integer(payload.get("maximum_credits")):
                    raise ClientError("Regeneration quote exceeds the authorized budget.")
            state = {"version": 1, "kind": "submission", "context": context, "request": request, "idempotency_key": str(uuid.uuid4())}
            save_state(path, state)
        if state.get("job_id"):
            return {"id": identifier(state["job_id"]), "replayed": True}
        accepted = client.call(operation, resource, payload, idempotency=state["idempotency_key"])
        state["job_id"] = identifier(accepted["id"])
        save_state(path, state)
        return accepted


def wait_job(client, job_id, timeout=1800, interval=5):
    integer(timeout, 1, 86400)
    integer(interval, 1, 60)
    deadline = client.clock() + timeout
    while True:
        result = client.call("status", job_id, deadline=deadline)
        status = result.get("status")
        if status == "succeeded":
            return result
        if status in {"failed", "canceled"}:
            raise ClientError("Job {} is {}; no replacement was submitted.".format(job_id, status))
        if status not in {"queued", "running"}:
            raise ClientError("Unexpected job status; inspect the job before continuing.")
        remaining = deadline - client.clock()
        if remaining <= 0:
            raise ClientError("Job {} is still processing. Resume with the same ID.".format(job_id))
        client.sleep(min(interval, remaining))


def storage_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError()
    except (ValueError, TypeError):
        raise ClientError("Storage authorization must use HTTPS without embedded credentials.") from None
    return url


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size_bytes": path.stat().st_size}


def upload(client, file, tool, state_path, mime=None, opener=None):
    if tool not in TOOLS:
        raise ClientError("Unknown server tool.")
    file = Path(file)
    info = fingerprint(file)
    if info["size_bytes"] < 1:
        raise ClientError("Cannot upload an empty file.")
    mime = mime or mimetypes.guess_type(file.name)[0]
    if not mime:
        raise ClientError("Specify --mime with this tool's supported content type.")
    declaration = {"tool": tool, "file_name": file.name, "mime_type": mime, "size_bytes": info["size_bytes"]}
    transport = opener or urllib.request.build_opener(NoRedirect)
    with locked_state(state_path) as path:
        context = identity_context(client)
        if path.exists():
            state = read_json(path, state=True)
            check_context(state, context)
            if state.get("kind") != "upload" or state.get("source") != info or state.get("declaration") != declaration:
                raise ClientError("Upload state does not match this file, tool or MIME type.")
        else:
            state = {"version": 1, "kind": "upload", "context": context, "source": info, "declaration": declaration}
            save_state(path, state)
        if state.get("confirmed"):
            asset = client.call("asset", state["authorization"]["asset_id"])
            if asset.get("state") != "ready":
                raise ClientError("Previously uploaded asset is no longer ready.")
            return {"asset_id": asset["id"], "state": "ready"}
        if "authorization" not in state:
            state["authorization"] = client.call("upload-intent", data=declaration)
            save_state(path, state)
        auth = state["authorization"]
        # A prior PUT may have succeeded before the process stopped. Confirm it first.
        try:
            confirmed = client.call("confirm", auth["asset_id"])
        except ApiError as error:
            if error.status not in {404, 409, 503}:
                raise
        else:
            state["confirmed"] = True
            state["authorization"] = {"asset_id": auth["asset_id"]}
            save_state(path, state)
            return confirmed
        try:
            expiry = datetime.fromisoformat(auth["expires_at"].replace("Z", "+00:00"))
            if expiry <= datetime.now(timezone.utc):
                raise ClientError("Upload URL expired; preserve this state and start a new upload with another state file.")
        except (ValueError, KeyError, TypeError):
            raise ClientError("Invalid upload authorization expiry.") from None
        if auth.get("method") != "PUT":
            raise ClientError("Unsupported upload method.")
        # Only the declared content type is forwarded; never any API credentials.
        headers = {"Content-Type": mime, "Content-Length": str(info["size_bytes"])}
        if auth.get("headers", {}).get("Content-Type") != mime:
            raise ClientError("Upload authorization content type mismatch.")
        try:
            with file.open("rb") as stream:
                req = urllib.request.Request(storage_url(auth["upload_url"]), data=stream, headers=headers, method="PUT")
                with transport.open(req, timeout=300) as response:
                    response.read(1024)
        except (urllib.error.URLError, OSError):
            raise ClientError("Upload interrupted. Resume with the same upload state; no new job was submitted.") from None
        result = client.call("confirm", auth["asset_id"])
        state["confirmed"] = True
        state["authorization"] = {"asset_id": auth["asset_id"]}
        save_state(path, state)
        return result


def download(client, asset_id, destination, max_bytes=5 * 1024 ** 3, opener=None):
    integer(max_bytes, 1)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked_state(path):
        if path.exists():
            raise ClientError("Destination already exists; choose another output path.")
        metadata = client.call("asset", asset_id)
        if metadata.get("state") != "ready":
            raise ClientError("Asset is not ready for download.")
        expected = metadata.get("size_bytes")
        if expected is not None:
            integer(expected, 0, max_bytes)
        authorization = client.call("download-url", asset_id)
        transport = opener or urllib.request.build_opener(NoRedirect)
        fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=str(path.parent))
        total = 0
        try:
            with os.fdopen(fd, "wb") as output:
                # API Bearer authentication is never forwarded to object storage.
                with transport.open(urllib.request.Request(storage_url(authorization["url"])), timeout=300) as response:
                    while True:
                        chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise ClientError("Download exceeded --max-bytes; incomplete file discarded.")
                        output.write(chunk)
            if expected is not None and total != expected:
                raise ClientError("Download size mismatch; incomplete file discarded.")
            # Hard-link publication is atomic and fails if any process created destination.
            os.link(temporary, path)
        except (urllib.error.URLError, OSError):
            raise ClientError("Download failed; no partial output was published. Retry with a fresh signed URL.") from None
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"asset_id": asset_id, "path": str(path), "size_bytes": total}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("identity", "tools", "usage"):
        sub.add_parser(name)
    for name in ("tool", "catalog"):
        q = sub.add_parser(name)
        q.add_argument("tool", choices=TOOLS)
        if name == "tool":
            q.add_argument("--offline", action="store_true", help="Read the bundled contract snapshot, without credentials.")
    for name in ("asset", "status", "cancel", "clips", "clip", "project", "composition", "broll"):
        sub.add_parser(name).add_argument("id")
    for name in ("jobs", "projects"):
        sub.add_parser(name).add_argument("--page", type=int, default=1)
    for name in ("create-project", "create-composition"):
        sub.add_parser(name).add_argument("--title", required=True)
    q = sub.add_parser("upload")
    q.add_argument("file", type=Path)
    q.add_argument("--tool", choices=TOOLS, required=True)
    q.add_argument("--state", type=Path, required=True)
    q.add_argument("--mime")
    q = sub.add_parser("download")
    q.add_argument("id")
    q.add_argument("--output", type=Path, required=True)
    q.add_argument("--max-bytes", type=int, default=5 * 1024 ** 3)
    sub.add_parser("quote").add_argument("request", type=Path)
    for name in ("submit", "run"):
        q = sub.add_parser(name)
        q.add_argument("request", type=Path)
        q.add_argument("--state", type=Path, required=True)
        q.add_argument("--maximum-credits", type=int, required=True)
        if name == "run":
            q.add_argument("--timeout", type=int, default=1800)
            q.add_argument("--interval", type=int, default=5)
    q = sub.add_parser("wait")
    q.add_argument("id")
    q.add_argument("--timeout", type=int, default=1800)
    q.add_argument("--interval", type=int, default=5)
    q = sub.add_parser("edit-clip")
    q.add_argument("id")
    q.add_argument("request", type=Path)
    q = sub.add_parser("export-clip", help="Export an explicitly selected revision. API v1 has no export quote or budget-cap field.")
    q.add_argument("id")
    q.add_argument("--revision", type=int, required=True)
    q.add_argument("--state", type=Path, required=True)
    for name in ("edit-broll", "quote-broll-shot", "regenerate-broll-shot"):
        q = sub.add_parser(name)
        q.add_argument("id")
        q.add_argument("request", type=Path)
        if name == "regenerate-broll-shot":
            q.add_argument("--state", type=Path, required=True)
            q.add_argument("--maximum-credits", type=int, required=True)
    q = sub.add_parser("export-broll")
    q.add_argument("id")
    q.add_argument("--revision", type=int, required=True)
    q.add_argument("--state", type=Path, required=True)
    return p


def execute(args, client=None):
    cmd = args.command
    if cmd == "tool" and args.offline:
        return {"source": CATALOG["source"], "snapshot": next(t for t in CATALOG["tools"] if t["id"] == args.tool)}
    client = client or Client()
    if cmd in {"submit", "run"}:
        if cmd == "run":
            integer(args.timeout, 1, 86400)
            integer(args.interval, 1, 60)
        payload = job_payload(read_json(args.request), args.maximum_credits)
        accepted = submit_saved(client, "submit", payload, args.state)
        return wait_job(client, accepted["id"], args.timeout, args.interval) if cmd == "run" else accepted
    if cmd == "quote":
        return client.call("quote", data=job_payload(read_json(args.request)))
    if cmd == "upload":
        return upload(client, args.file, args.tool, args.state, args.mime)
    if cmd == "download":
        return download(client, identifier(args.id), args.output, args.max_bytes)
    if cmd == "wait":
        return wait_job(client, identifier(args.id), args.timeout, args.interval)
    if cmd == "edit-clip":
        data = read_json(args.request)
        required = {"captions_enabled", "caption_group_size", "caption_style", "caption_words"}
        if set(data) != required:
            raise ClientError("Clip edits require captions_enabled, caption_group_size, caption_style and caption_words.")
        return client.call(cmd, args.id, data)
    if cmd in {"edit-broll", "quote-broll-shot", "regenerate-broll-shot"}:
        payload = read_json(args.request)
        if cmd == "regenerate-broll-shot":
            payload = dict(payload, maximum_credits=min(integer(args.maximum_credits), integer(payload["maximum_credits"])) if "maximum_credits" in payload else integer(args.maximum_credits))
            return submit_saved(client, cmd, payload, args.state, identifier(args.id))
        return client.call(cmd, identifier(args.id), payload)
    if cmd == "export-broll":
        return submit_saved(client, cmd, {"revision": integer(args.revision, 1)}, args.state, identifier(args.id))
    if cmd == "export-clip":
        return submit_saved(client, cmd, {"editor_revision": integer(args.revision)}, args.state, identifier(args.id))
    if cmd in {"create-project", "create-composition"}:
        title = args.title.strip()
        if not 1 <= len(title) <= (160 if cmd == "create-composition" else 200):
            raise ClientError("Project title exceeds the documented length.")
        return client.call(cmd, data={"title": title})
    return client.call(cmd, getattr(args, "id", getattr(args, "tool", None)), page=getattr(args, "page", None))


def main():
    args = parser().parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    except (ClientError, OSError, KeyError, TypeError, ValueError) as error:
        # Untrusted content, transport errors and local path strings are not echoed.
        print(str(error) if isinstance(error, ClientError) else "Invalid local input or unexpected API response. Preserve run state before retrying.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
