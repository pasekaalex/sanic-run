"""Guard a single Meshy rig task and a single sprint-animation task.

This client intentionally prefers a permanent local stop over an accidental
duplicate paid request. It never retries task creation and never clears an
attempt marker.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


API_BASE = "https://api.meshy.ai/openapi/v1"
REFERENCE_ROOT = Path(
    "/home/alex/Downloads/SANIC-Meshy-v3/meshy-reference"
).resolve()
RIG_REQUIRED_BALANCE = 8
ANIMATION_REQUIRED_BALANCE = 3
TERMINAL_FAILURE_STATUSES = {"FAILED", "CANCELED"}
TASK_STATUSES = {"PENDING", "IN_PROGRESS", "SUCCEEDED", *TERMINAL_FAILURE_STATUSES}
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
RIG_DOWNLOADS = {
    "rigged_character_fbx_url": "rigged-character.fbx",
    "rigged_character_glb_url": "rigged-character.glb",
}
BASIC_ANIMATION_DOWNLOADS = {
    "walking_glb_url": "basic-walking.glb",
    "walking_fbx_url": "basic-walking.fbx",
    "walking_armature_glb_url": "basic-walking-armature.glb",
    "running_glb_url": "basic-running.glb",
    "running_fbx_url": "basic-running.fbx",
    "running_armature_glb_url": "basic-running-armature.glb",
}
ANIMATION_DOWNLOADS = {
    "animation_glb_url": "animation.glb",
    "animation_fbx_url": "animation.fbx",
    "processed_usdz_url": "processed.usdz",
    "processed_armature_fbx_url": "processed-armature.fbx",
    "processed_animation_fps_fbx_url": "processed-24fps.fbx",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("balance")

    rig_parser = subparsers.add_parser("rig")
    rig_parser.add_argument("input_glb", type=Path)
    rig_parser.add_argument("state_json", type=Path)

    poll_rig_parser = subparsers.add_parser("poll-rig")
    poll_rig_parser.add_argument("state_json", type=Path)
    poll_rig_parser.add_argument("output_dir", type=Path)

    approve_rig_parser = subparsers.add_parser("approve-rig")
    approve_rig_parser.add_argument("state_json", type=Path)

    animate_parser = subparsers.add_parser("animate")
    animate_parser.add_argument("state_json", type=Path)

    poll_animation_parser = subparsers.add_parser("poll-animation")
    poll_animation_parser.add_argument("state_json", type=Path)
    poll_animation_parser.add_argument("output_dir", type=Path)
    return parser


def read_api_key(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    try:
        value = source["MESHY_API_KEY"]
    except KeyError:
        raise RuntimeError("MESHY_API_KEY is required") from None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("MESHY_API_KEY is required")
    return value.strip()


def _reference_path(path: Path, description: str) -> Path:
    reference_root = REFERENCE_ROOT.expanduser().resolve()
    expanded = path.expanduser()
    absolute = Path(os.path.abspath(expanded))
    resolved = absolute.resolve()
    if not (
        absolute.is_relative_to(reference_root)
        and resolved.is_relative_to(reference_root)
    ):
        raise RuntimeError(f"{description} must stay under the reference root")
    return resolved


def _state_path(path: Path) -> Path:
    return _reference_path(path, "Meshy state JSON")


@contextmanager
def _state_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError:
        raise RuntimeError("Could not open the Meshy state lock") from None
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except OSError:
        os.close(descriptor)
        raise RuntimeError("Could not lock the Meshy state JSON") from None
    try:
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _load_state(path: Path, *, allow_missing: bool = False) -> dict[str, object]:
    if not path.exists():
        if allow_missing:
            return {}
        raise RuntimeError("Meshy state JSON does not exist")
    if path.is_symlink():
        raise RuntimeError("Meshy state JSON must be a regular file")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("Meshy state JSON must be a regular file")
    if metadata.st_nlink != 1:
        raise RuntimeError("Meshy state JSON must not have hard-link aliases")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise RuntimeError("Meshy state JSON permissions must be 0600")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Meshy state JSON is unreadable") from None
    if not isinstance(value, dict):
        raise RuntimeError("Meshy state JSON must contain an object")
    return value


def _assert_safe_state(value: object, *, key: str = "") -> None:
    normalized_key = key.lower()
    forbidden_keys = {
        "api_key",
        "authorization",
        "data_uri",
        "model_url",
        "request_body",
    }
    if normalized_key in forbidden_keys:
        raise RuntimeError("Refusing to persist sensitive Meshy state")
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if not isinstance(child_key, str):
                raise RuntimeError("Meshy state keys must be strings")
            _assert_safe_state(child_value, key=child_key)
    elif isinstance(value, list):
        for child_value in value:
            _assert_safe_state(child_value, key=key)
    elif isinstance(value, str):
        lowered = value.lower()
        if (
            lowered.startswith("data:")
            or lowered.startswith("http://")
            or lowered.startswith("https://")
            or lowered.startswith("bearer ")
        ):
            raise RuntimeError("Refusing to persist sensitive Meshy state")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_state(path: Path, state: dict[str, object]) -> None:
    _assert_safe_state(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            descriptor = -1
            json.dump(state, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        path.chmod(0o600)
        _fsync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _safe_error_message(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    message = re.sub(r"(?i)\bbearer\s+\S+", "[redacted]", value)
    message = re.sub(r"(?i)\bdata:\S+", "[redacted]", message)
    message = re.sub(r"https?://\S+", "[redacted-url]", message)
    return message[:500]


def _api_request_json(
    method: str,
    path: str,
    api_key: str,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    if not path.startswith("/") or "://" in path:
        raise RuntimeError("Invalid Meshy API path")
    body = (
        None
        if payload is None
        else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Meshy {method} request failed with HTTP {error.code}"
        ) from None
    except (urllib.error.URLError, OSError):
        raise RuntimeError(f"Meshy {method} request failed") from None
    try:
        value = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Meshy API returned invalid JSON") from None
    if not isinstance(value, dict):
        raise RuntimeError("Meshy API returned an invalid object")
    return value


def _credit_balance(api_key: str) -> int | float:
    response = _api_request_json("GET", "/balance", api_key)
    value = response.get("balance")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value < 0
    ):
        raise RuntimeError("Meshy balance response is invalid")
    return value


def _task_id(value: object, description: str) -> str:
    if not isinstance(value, str) or TASK_ID_PATTERN.fullmatch(value) is None:
        raise RuntimeError(f"Meshy {description} task ID is invalid")
    return value


def _task_id_from_creation(
    response: dict[str, object],
    description: str,
) -> str:
    return _task_id(response.get("result"), description)


def _id_suffix(task_id: str) -> str:
    return task_id[-6:]


def _task_status(response: dict[str, object]) -> str:
    status = response.get("status")
    if not isinstance(status, str) or status not in TASK_STATUSES:
        raise RuntimeError("Meshy task status is invalid")
    return status


def _progress(response: dict[str, object]) -> int | float | None:
    value = response.get("progress")
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0 <= value <= 100
    ):
        raise RuntimeError("Meshy task progress is invalid")
    return value


def _consumed_credits(response: dict[str, object]) -> int | float | None:
    value = response.get("consumed_credits")
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value < 0
    ):
        raise RuntimeError("Meshy consumed credits value is invalid")
    return value


def _task_error(response: dict[str, object]) -> str:
    value = response.get("task_error")
    if not isinstance(value, dict):
        return ""
    return _safe_error_message(value.get("message"))


def _task_summary(
    task: str,
    task_id: str,
    status: str,
    *,
    progress: int | float | None = None,
    consumed_credits: int | float | None = None,
    files: list[str] | None = None,
    error: str = "",
) -> dict[str, object]:
    summary: dict[str, object] = {
        "task": task,
        "id_suffix": _id_suffix(task_id),
        "status": status,
    }
    if progress is not None:
        summary["progress"] = progress
    if consumed_credits is not None:
        summary["consumed_credits"] = consumed_credits
    if files:
        summary["files"] = files
    if error:
        summary["error"] = error
    return summary


def balance(
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    credits = _credit_balance(read_api_key(environ))
    return {"task": "balance", "credits": credits}


def rig(
    input_glb: Path,
    state_json: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    input_path = _reference_path(input_glb, "Rig input GLB")
    if not input_path.is_file() or input_path.suffix.lower() != ".glb":
        raise RuntimeError("Rig input must be an existing GLB")
    state_path = _state_path(state_json)
    with _state_lock(state_path):
        state = _load_state(state_path, allow_missing=True)
        if "rig_attempted_at" in state:
            raise RuntimeError(
                "Rig task was already attempted; retry is forbidden"
            )

        api_key = read_api_key(environ)
        credits = _credit_balance(api_key)
        if credits < RIG_REQUIRED_BALANCE:
            raise RuntimeError(
                f"Rig task requires at least {RIG_REQUIRED_BALANCE} credits"
            )

        encoded_glb = base64.b64encode(input_path.read_bytes()).decode("ascii")
        payload: dict[str, object] = {
            "model_url": f"data:model/gltf-binary;base64,{encoded_glb}",
            "height_meters": 1.7,
        }
        state["rig_attempted_at"] = _utc_timestamp()
        _atomic_write_state(state_path, state)

    response = _api_request_json("POST", "/rigging", api_key, payload)
    task_id = _task_id_from_creation(response, "rig")
    with _state_lock(state_path):
        state = _load_state(state_path)
        state["rig_task_id"] = task_id
        state["rig_status"] = "PENDING"
        _atomic_write_state(state_path, state)
    return _task_summary("rig", task_id, "PENDING")


def _require_stored_task_id(
    state: dict[str, object],
    field: str,
    description: str,
) -> str:
    return _task_id(state.get(field), description)


def _download_file(url: object, destination: Path) -> None:
    if not isinstance(url, str):
        raise RuntimeError("Meshy result URL is invalid")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("Meshy result URL must use HTTPS")
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        raise RuntimeError("Meshy result download failed") from None
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, destination)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)


def _download_fields(
    result: dict[str, object],
    field_names: Mapping[str, str],
    output_dir: Path,
) -> list[str]:
    filenames: list[str] = []
    for field, filename in field_names.items():
        url = result.get(field)
        if url is None:
            continue
        destination = output_dir / filename
        _download_file(url, destination)
        filenames.append(filename)
    return filenames


def _poll_task(
    *,
    task: str,
    endpoint: str,
    state_path: Path,
    output_dir: Path,
    task_id_field: str,
    status_field: str,
    progress_field: str,
    credits_field: str,
    error_field: str,
    files_field: str,
    download_fields: Mapping[str, str],
    nested_download_fields: Mapping[str, str] | None,
    environ: Mapping[str, str] | None,
) -> dict[str, object]:
    with _state_lock(state_path):
        state = _load_state(state_path)
        stored_status = state.get(status_field)
        if stored_status in TERMINAL_FAILURE_STATUSES:
            raise RuntimeError(f"{task.capitalize()} branch has already ended")
        task_id = _require_stored_task_id(state, task_id_field, task)
        response = _api_request_json(
            "GET",
            f"/{endpoint}/{urllib.parse.quote(task_id, safe='')}",
            read_api_key(environ),
        )
        response_id = _task_id(response.get("id"), task)
        if response_id != task_id:
            raise RuntimeError("Meshy task response ID does not match stored ID")
        status = _task_status(response)
        progress = _progress(response)
        consumed_credits = _consumed_credits(response)
        error = _task_error(response)

        files: list[str] = []
        if status == "SUCCEEDED":
            result = response.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("Successful Meshy task has no result object")
            output_dir.mkdir(parents=True, exist_ok=True)
            files.extend(_download_fields(result, download_fields, output_dir))
            if nested_download_fields is not None:
                nested = result.get("basic_animations")
                if nested is not None and not isinstance(nested, dict):
                    raise RuntimeError(
                        "Meshy basic animation result is invalid"
                    )
                if isinstance(nested, dict):
                    files.extend(
                        _download_fields(
                            nested,
                            nested_download_fields,
                            output_dir,
                        )
                    )
            if not files:
                raise RuntimeError(
                    "Successful Meshy task has no allow-listed files"
                )

        state[status_field] = status
        if progress is not None:
            state[progress_field] = progress
        if consumed_credits is not None:
            state[credits_field] = consumed_credits
        if error:
            state[error_field] = error
        if files:
            state[files_field] = files
        _atomic_write_state(state_path, state)
        return _task_summary(
            task,
            task_id,
            status,
            progress=progress,
            consumed_credits=consumed_credits,
            files=files,
            error=error,
        )


def poll_rig(
    state_json: Path,
    output_dir: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    return _poll_task(
        task="rig",
        endpoint="rigging",
        state_path=_state_path(state_json),
        output_dir=_reference_path(output_dir, "Meshy output directory"),
        task_id_field="rig_task_id",
        status_field="rig_status",
        progress_field="rig_progress",
        credits_field="rig_consumed_credits",
        error_field="rig_error",
        files_field="rig_files",
        download_fields=RIG_DOWNLOADS,
        nested_download_fields=BASIC_ANIMATION_DOWNLOADS,
        environ=environ,
    )


def approve_rig(state_json: Path) -> dict[str, object]:
    state_path = _state_path(state_json)
    with _state_lock(state_path):
        state = _load_state(state_path)
        task_id = _require_stored_task_id(state, "rig_task_id", "rig")
        if state.get("rig_status") != "SUCCEEDED":
            raise RuntimeError("Only a successful rig task can be approved")
        state["rig_approved"] = True
        _atomic_write_state(state_path, state)
        return _task_summary("rig", task_id, "APPROVED")


def animate(
    state_json: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    state_path = _state_path(state_json)
    with _state_lock(state_path):
        state = _load_state(state_path)
        if "animation_attempted_at" in state:
            raise RuntimeError(
                "Animation task was already attempted; retry is forbidden"
            )
        rig_task_id = _require_stored_task_id(state, "rig_task_id", "rig")
        if state.get("rig_status") != "SUCCEEDED":
            raise RuntimeError("Animation requires a successful rig task")
        if state.get("rig_approved") is not True:
            raise RuntimeError("Animation requires explicit rig approval")

        api_key = read_api_key(environ)
        credits = _credit_balance(api_key)
        if credits < ANIMATION_REQUIRED_BALANCE:
            raise RuntimeError(
                "Animation task requires at least "
                f"{ANIMATION_REQUIRED_BALANCE} credits"
            )
        payload: dict[str, object] = {
            "rig_task_id": rig_task_id,
            "action_id": 644,
            "post_process": {
                "operation_type": "change_fps",
                "fps": 24,
            },
        }
        state["animation_attempted_at"] = _utc_timestamp()
        _atomic_write_state(state_path, state)

    response = _api_request_json("POST", "/animations", api_key, payload)
    task_id = _task_id_from_creation(response, "animation")
    with _state_lock(state_path):
        state = _load_state(state_path)
        state["animation_task_id"] = task_id
        state["animation_status"] = "PENDING"
        _atomic_write_state(state_path, state)
    return _task_summary("animation", task_id, "PENDING")


def poll_animation(
    state_json: Path,
    output_dir: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    return _poll_task(
        task="animation",
        endpoint="animations",
        state_path=_state_path(state_json),
        output_dir=_reference_path(output_dir, "Meshy output directory"),
        task_id_field="animation_task_id",
        status_field="animation_status",
        progress_field="animation_progress",
        credits_field="animation_consumed_credits",
        error_field="animation_error",
        files_field="animation_files",
        download_fields=ANIMATION_DOWNLOADS,
        nested_download_fields=None,
        environ=environ,
    )


def _print_summary(summary: dict[str, object]) -> None:
    fields = [f"task={summary['task']}"]
    if "id_suffix" in summary:
        fields.append(f"id_suffix={summary['id_suffix']}")
    for key in ("status", "progress", "credits", "consumed_credits"):
        if key in summary:
            fields.append(f"{key}={summary[key]}")
    files = summary.get("files")
    if isinstance(files, list):
        fields.append(f"files={','.join(str(value) for value in files)}")
    error = summary.get("error")
    if isinstance(error, str) and error:
        fields.append(f"error={_safe_error_message(error)}")
    print(" ".join(fields))


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "balance":
            summary = balance()
        elif arguments.command == "rig":
            summary = rig(arguments.input_glb, arguments.state_json)
        elif arguments.command == "poll-rig":
            summary = poll_rig(arguments.state_json, arguments.output_dir)
        elif arguments.command == "approve-rig":
            summary = approve_rig(arguments.state_json)
        elif arguments.command == "animate":
            summary = animate(arguments.state_json)
        elif arguments.command == "poll-animation":
            summary = poll_animation(
                arguments.state_json,
                arguments.output_dir,
            )
        else:
            raise RuntimeError("Unknown Meshy guard command")
    except OSError:
        print(
            f"task={arguments.command} error=local filesystem operation failed",
            file=sys.stderr,
        )
        return 1
    except RuntimeError as error:
        message = _safe_error_message(str(error)) or "Meshy command failed"
        print(f"task={arguments.command} error={message}", file=sys.stderr)
        return 1
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
