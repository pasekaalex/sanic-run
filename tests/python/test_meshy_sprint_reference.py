from __future__ import annotations

import base64
import importlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock


with (
    mock.patch.dict(os.environ, {}, clear=True),
    mock.patch(
        "urllib.request.urlopen",
        side_effect=AssertionError("network used during first import"),
    ) as import_urlopen,
):
    meshy = importlib.import_module("blender.scripts.meshy_sprint_reference")
IMPORT_NETWORK_CALL_COUNT = import_urlopen.call_count


FAKE_API_KEY = "meshy-key-example-not-real"


def load_blender_script(name: str) -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2] / "blender" / "scripts" / f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(f"test_{name}", script_path)
    assert spec is not None and spec.loader is not None
    bpy = ModuleType("bpy")
    mathutils = ModuleType("mathutils")
    mathutils.Vector = object  # type: ignore[attr-defined]
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"bpy": bpy, "mathutils": mathutils}):
        spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, value: object, *, json_response: bool = True) -> None:
        self.body = (
            json.dumps(value).encode("utf-8")
            if json_response
            else bytes(value)
        )

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class TrackingEnvironment(Mapping[str, str]):
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.accessed: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.accessed.append(key)
        return self.values[key]

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("environment must not be enumerated")

    def __len__(self) -> int:
        return len(self.values)


class MeshySprintReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.input_glb = self.root / "input.glb"
        self.input_glb.write_bytes(b"glTF-example")
        self.state_path = self.root / "state.json"
        self.output_dir = self.root / "output"
        self.environment = {"MESHY_API_KEY": FAKE_API_KEY}
        reference_root = mock.patch.object(
            meshy,
            "REFERENCE_ROOT",
            self.root.resolve(),
            create=True,
        )
        reference_root.start()
        self.addCleanup(reference_root.stop)

    def write_state(self, value: dict[str, object]) -> None:
        self.state_path.write_text(json.dumps(value), encoding="utf-8")
        self.state_path.chmod(0o600)

    def run_concurrent_paid_attempts(
        self,
        operation: Callable[[], dict[str, object]],
        *,
        balance: int,
        task: str,
    ) -> tuple[list[Future[dict[str, object]]], list[str]]:
        first_balance_started = threading.Event()
        second_attempt_started = threading.Event()
        call_lock = threading.Lock()
        balance_calls = 0
        calls: list[str] = []

        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            nonlocal balance_calls
            method = request.get_method()
            with call_lock:
                calls.append(method)
                if method == "GET":
                    balance_calls += 1
                    call_number = balance_calls
                else:
                    call_number = calls.count("POST")
            if method == "GET":
                if call_number == 1:
                    first_balance_started.set()
                    self.assertTrue(second_attempt_started.wait(timeout=2))
                    time.sleep(0.1)
                return FakeResponse({"balance": balance})
            return FakeResponse({"result": f"{task}-task-example-{call_number}"})

        patcher = mock.patch("urllib.request.urlopen", side_effect=respond)
        patcher.start()
        self.addCleanup(patcher.stop)
        executor = ThreadPoolExecutor(max_workers=2)
        self.addCleanup(executor.shutdown)
        first = executor.submit(operation)
        self.assertTrue(first_balance_started.wait(timeout=2))

        def second_operation() -> dict[str, object]:
            second_attempt_started.set()
            return operation()

        second = executor.submit(second_operation)
        return [first, second], calls

    def test_first_import_does_not_read_environment_or_use_network(self) -> None:
        self.assertEqual(IMPORT_NETWORK_CALL_COUNT, 0)

    def test_api_key_reads_only_meshy_api_key_and_requires_it(self) -> None:
        environment = TrackingEnvironment({"MESHY_API_KEY": FAKE_API_KEY})
        self.assertEqual(meshy.read_api_key(environment), FAKE_API_KEY)
        self.assertEqual(environment.accessed, ["MESHY_API_KEY"])

        missing = TrackingEnvironment({})
        with self.assertRaises(RuntimeError):
            meshy.read_api_key(missing)
        self.assertEqual(missing.accessed, ["MESHY_API_KEY"])

    def test_parser_exposes_only_the_guarded_commands(self) -> None:
        parser = meshy.build_parser()
        commands = {
            parser.parse_args(arguments).command
            for arguments in (
                ["balance"],
                ["rig", "input.glb", "state.json"],
                ["poll-rig", "state.json", "output"],
                ["approve-rig", "state.json"],
                ["animate", "state.json"],
                ["poll-animation", "state.json", "output"],
            )
        }
        self.assertEqual(
            commands,
            {
                "balance",
                "rig",
                "poll-rig",
                "approve-rig",
                "animate",
                "poll-animation",
            },
        )

    def test_balance_does_not_return_or_print_authorization(self) -> None:
        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, f"{meshy.API_BASE}/balance")
            self.assertEqual(
                dict(request.header_items())["Authorization"],
                f"Bearer {FAKE_API_KEY}",
            )
            return FakeResponse({"balance": 12})

        output = io.StringIO()
        with (
            mock.patch("urllib.request.urlopen", side_effect=respond),
            mock.patch.dict(os.environ, self.environment, clear=True),
            redirect_stdout(output),
        ):
            result = meshy.balance(self.environment)
            exit_code = meshy.main(["balance"])

        self.assertEqual(result, {"task": "balance", "credits": 12})
        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertNotIn(FAKE_API_KEY, rendered)
        self.assertNotIn("Authorization", rendered)
        self.assertNotIn("authorization", json.dumps(result).lower())

    def test_filesystem_errors_have_restricted_cli_output(self) -> None:
        standard_output = io.StringIO()
        standard_error = io.StringIO()
        sensitive_path = "/private/example/credential-bearing-state.json"
        with (
            mock.patch.object(
                Path,
                "mkdir",
                side_effect=OSError(f"cannot create {sensitive_path}"),
            ),
            mock.patch("urllib.request.urlopen") as urlopen,
            redirect_stdout(standard_output),
            redirect_stderr(standard_error),
        ):
            try:
                exit_code = meshy.main(
                    ["rig", str(self.input_glb), str(self.state_path)]
                )
            except OSError as error:
                self.fail(f"filesystem error escaped main: {type(error).__name__}")

        self.assertEqual(exit_code, 1)
        self.assertEqual(standard_output.getvalue(), "")
        self.assertEqual(
            standard_error.getvalue(),
            "task=rig error=local filesystem operation failed\n",
        )
        self.assertNotIn(sensitive_path, standard_error.getvalue())
        urlopen.assert_not_called()

    def test_rig_checks_balance_before_posting_and_uses_data_uri(self) -> None:
        calls: list[tuple[str, str]] = []

        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            calls.append((request.get_method(), request.full_url))
            if request.get_method() == "GET":
                return FakeResponse({"balance": 8})
            state_at_post = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.assertIn("rig_attempted_at", state_at_post)
            payload = json.loads(bytes(request.data).decode("utf-8"))
            self.assertEqual(set(payload), {"model_url", "height_meters"})
            self.assertEqual(payload["height_meters"], 1.7)
            prefix = "data:model/gltf-binary;base64,"
            self.assertTrue(payload["model_url"].startswith(prefix))
            encoded = payload["model_url"][len(prefix) :]
            self.assertEqual(
                base64.b64decode(encoded, validate=True),
                self.input_glb.read_bytes(),
            )
            self.assertNotIn("model_url", state_at_post)
            return FakeResponse({"result": "rig-task-example"})

        with (
            mock.patch("urllib.request.urlopen", side_effect=respond),
            mock.patch("os.replace", wraps=os.replace) as replace,
        ):
            result = meshy.rig(
                self.input_glb,
                self.state_path,
                self.environment,
            )

        self.assertEqual(
            calls,
            [
                ("GET", f"{meshy.API_BASE}/balance"),
                ("POST", f"{meshy.API_BASE}/rigging"),
            ],
        )
        self.assertGreaterEqual(replace.call_count, 2)
        self.assertEqual(result["task"], "rig")
        self.assertNotIn("rig-task-example", json.dumps(result))
        self.assertEqual(
            stat.S_IMODE(self.state_path.stat().st_mode),
            0o600,
        )

    def test_state_directory_is_fsynced_before_rig_post(self) -> None:
        events: list[str] = []
        real_fsync = os.fsync
        real_replace = os.replace
        real_chmod = Path.chmod

        def observed_fsync(descriptor: int) -> None:
            try:
                target = Path(
                    os.readlink(f"/proc/self/fd/{descriptor}")
                ).resolve()
            except OSError:
                target = None
            events.append(
                "directory_fsync"
                if target == self.state_path.parent.resolve()
                else "file_fsync"
            )
            real_fsync(descriptor)

        def observed_replace(source: object, destination: object) -> None:
            events.append("replace")
            real_replace(source, destination)

        def observed_chmod(
            path: Path,
            mode: int,
            *,
            follow_symlinks: bool = True,
        ) -> None:
            if path == self.state_path:
                events.append("chmod")
            real_chmod(path, mode, follow_symlinks=follow_symlinks)

        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            if request.get_method() == "GET":
                return FakeResponse({"balance": 8})
            events.append("post")
            return FakeResponse({"result": "rig-task-example"})

        with (
            mock.patch("os.fsync", side_effect=observed_fsync),
            mock.patch("os.replace", side_effect=observed_replace),
            mock.patch.object(
                Path,
                "chmod",
                autospec=True,
                side_effect=observed_chmod,
            ),
            mock.patch("urllib.request.urlopen", side_effect=respond),
        ):
            meshy.rig(self.input_glb, self.state_path, self.environment)

        before_post = events[: events.index("post")]
        self.assertIn("directory_fsync", before_post)
        self.assertLess(
            max(index for index, event in enumerate(before_post) if event == "replace"),
            before_post.index("directory_fsync"),
        )
        self.assertLess(
            max(index for index, event in enumerate(before_post) if event == "chmod"),
            before_post.index("directory_fsync"),
        )

    def test_rig_refuses_when_balance_is_below_eight(self) -> None:
        with mock.patch(
            "urllib.request.urlopen",
            return_value=FakeResponse({"balance": 7}),
        ) as urlopen:
            with self.assertRaises(RuntimeError):
                meshy.rig(
                    self.input_glb,
                    self.state_path,
                    self.environment,
                )

        self.assertEqual(urlopen.call_count, 1)
        self.assertFalse(self.state_path.exists())

    def test_failed_rig_post_permanently_blocks_a_second_post(self) -> None:
        def fail_after_balance(
            request: urllib.request.Request,
            **_: object,
        ) -> FakeResponse:
            if request.get_method() == "GET":
                return FakeResponse({"balance": 8})
            raise OSError("mocked rig failure")

        with mock.patch(
            "urllib.request.urlopen",
            side_effect=fail_after_balance,
        ):
            with self.assertRaises(RuntimeError):
                meshy.rig(
                    self.input_glb,
                    self.state_path,
                    self.environment,
                )

        self.assertTrue(
            self.state_path.is_file(),
            "rig attempt marker was not persisted before the failed POST",
        )
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertIn("rig_attempted_at", state)
        with mock.patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(RuntimeError):
                meshy.rig(
                    self.input_glb,
                    self.state_path,
                    self.environment,
                )
        urlopen.assert_not_called()

    def test_concurrent_rig_invocations_allow_only_one_paid_post(self) -> None:
        futures, calls = self.run_concurrent_paid_attempts(
            lambda: meshy.rig(
                self.input_glb,
                self.state_path,
                self.environment,
            ),
            balance=8,
            task="rig",
        )
        outcomes: list[str] = []
        for future in futures:
            try:
                future.result(timeout=3)
            except RuntimeError:
                outcomes.append("blocked")
            else:
                outcomes.append("submitted")

        self.assertEqual(calls.count("POST"), 1)
        self.assertCountEqual(outcomes, ["submitted", "blocked"])

    def test_hard_link_state_aliases_cannot_submit_concurrently(self) -> None:
        self.write_state({})
        alias_path = self.root / "state-alias.json"
        os.link(self.state_path, alias_path)
        self.assertEqual(self.state_path.stat().st_nlink, 2)

        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            if request.get_method() == "GET":
                return FakeResponse({"balance": 8})
            return FakeResponse({"result": "rig-task-example"})

        with (
            mock.patch("urllib.request.urlopen", side_effect=respond) as urlopen,
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            futures = [
                executor.submit(
                    meshy.rig,
                    self.input_glb,
                    state_path,
                    self.environment,
                )
                for state_path in (self.state_path, alias_path)
            ]
            outcomes: list[str] = []
            for future in futures:
                try:
                    future.result(timeout=3)
                except RuntimeError:
                    outcomes.append("blocked")
                else:
                    outcomes.append("submitted")

        self.assertEqual(outcomes, ["blocked", "blocked"])
        urlopen.assert_not_called()

    def test_rig_input_must_stay_under_reference_root(self) -> None:
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        outside_input = Path(outside.name) / "outside.glb"
        outside_input.write_bytes(b"glTF-outside")
        with mock.patch(
            "urllib.request.urlopen",
            return_value=FakeResponse({"balance": 0}),
        ) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "reference root"):
                meshy.rig(outside_input, self.state_path, self.environment)
        urlopen.assert_not_called()

    def test_state_path_must_stay_under_reference_root(self) -> None:
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        outside_state = Path(outside.name) / "state.json"
        with mock.patch(
            "urllib.request.urlopen",
            return_value=FakeResponse({"balance": 0}),
        ) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "reference root"):
                meshy.rig(self.input_glb, outside_state, self.environment)
        urlopen.assert_not_called()

    def test_download_output_must_stay_under_reference_root(self) -> None:
        self.write_state({"rig_task_id": "rig-task-example"})
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        outside_output = Path(outside.name) / "output"
        with mock.patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(
                {
                    "id": "rig-task-example",
                    "status": "FAILED",
                    "progress": 0,
                    "consumed_credits": 0,
                }
            ),
        ) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "reference root"):
                meshy.poll_rig(
                    self.state_path,
                    outside_output,
                    self.environment,
                )
        urlopen.assert_not_called()

    def test_prepare_output_must_stay_under_reference_root(self) -> None:
        prepare = load_blender_script("prepare_meshy_reference")
        prepare.REFERENCE_ROOT = self.root.resolve()
        prepare.assert_outside_repository(self.root / "input.glb")
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        with self.assertRaisesRegex(AssertionError, "reference root"):
            prepare.assert_outside_repository(Path(outside.name) / "input.glb")

    def test_animation_requires_successful_approved_rig(self) -> None:
        invalid_states = (
            {},
            {"rig_task_id": "rig-task-example", "rig_status": "FAILED"},
            {"rig_task_id": "rig-task-example", "rig_status": "SUCCEEDED"},
        )
        for state in invalid_states:
            with self.subTest(state=state):
                self.write_state(state)
                with mock.patch("urllib.request.urlopen") as urlopen:
                    with self.assertRaises(RuntimeError):
                        meshy.animate(self.state_path, self.environment)
                urlopen.assert_not_called()

    def test_approve_rig_is_local_only_and_atomic(self) -> None:
        self.write_state(
            {
                "rig_task_id": "rig-task-example",
                "rig_status": "SUCCEEDED",
            }
        )
        with (
            mock.patch("urllib.request.urlopen") as urlopen,
            mock.patch("os.replace", wraps=os.replace) as replace,
        ):
            result = meshy.approve_rig(self.state_path)

        urlopen.assert_not_called()
        replace.assert_called()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertIs(state["rig_approved"], True)
        self.assertEqual(result["task"], "rig")

    def test_state_file_mode_must_be_exactly_0600(self) -> None:
        self.write_state(
            {
                "rig_task_id": "rig-task-example",
                "rig_status": "SUCCEEDED",
            }
        )
        self.state_path.chmod(0o700)

        with mock.patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(RuntimeError):
                meshy.approve_rig(self.state_path)

        urlopen.assert_not_called()
        self.assertEqual(
            stat.S_IMODE(self.state_path.stat().st_mode),
            0o700,
        )

    def test_animation_marker_precedes_exact_one_shot_payload(self) -> None:
        self.write_state(
            {
                "rig_task_id": "rig-task-example",
                "rig_status": "SUCCEEDED",
                "rig_approved": True,
            }
        )
        calls: list[tuple[str, str]] = []

        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            calls.append((request.get_method(), request.full_url))
            if request.get_method() == "GET":
                return FakeResponse({"balance": 3})
            state_at_post = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.assertIn("animation_attempted_at", state_at_post)
            self.assertEqual(
                json.loads(bytes(request.data).decode("utf-8")),
                {
                    "rig_task_id": "rig-task-example",
                    "action_id": 644,
                    "post_process": {
                        "operation_type": "change_fps",
                        "fps": 24,
                    },
                },
            )
            return FakeResponse({"result": "animation-task-example"})

        with mock.patch("urllib.request.urlopen", side_effect=respond):
            result = meshy.animate(self.state_path, self.environment)

        self.assertEqual(
            calls,
            [
                ("GET", f"{meshy.API_BASE}/balance"),
                ("POST", f"{meshy.API_BASE}/animations"),
            ],
        )
        self.assertEqual(result["task"], "animation")
        self.assertNotIn("animation-task-example", json.dumps(result))
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        forbidden = {
            "action_id",
            "post_process",
            "request_body",
            "authorization",
        }
        self.assertTrue(forbidden.isdisjoint(state))

        with mock.patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(RuntimeError):
                meshy.animate(self.state_path, self.environment)
        urlopen.assert_not_called()

    def test_failed_animation_post_permanently_blocks_a_second_post(self) -> None:
        self.write_state(
            {
                "rig_task_id": "rig-task-example",
                "rig_status": "SUCCEEDED",
                "rig_approved": True,
            }
        )

        def fail_after_balance(
            request: urllib.request.Request,
            **_: object,
        ) -> FakeResponse:
            if request.get_method() == "GET":
                return FakeResponse({"balance": 3})
            raise OSError("mocked animation failure")

        with mock.patch(
            "urllib.request.urlopen",
            side_effect=fail_after_balance,
        ):
            with self.assertRaises(RuntimeError):
                meshy.animate(self.state_path, self.environment)

        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertIn("animation_attempted_at", state)
        with mock.patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(RuntimeError):
                meshy.animate(self.state_path, self.environment)
        urlopen.assert_not_called()

    def test_concurrent_animation_invocations_allow_only_one_paid_post(self) -> None:
        self.write_state(
            {
                "rig_task_id": "rig-task-example",
                "rig_status": "SUCCEEDED",
                "rig_approved": True,
            }
        )
        futures, calls = self.run_concurrent_paid_attempts(
            lambda: meshy.animate(self.state_path, self.environment),
            balance=3,
            task="animation",
        )
        outcomes: list[str] = []
        for future in futures:
            try:
                future.result(timeout=3)
            except RuntimeError:
                outcomes.append("blocked")
            else:
                outcomes.append("submitted")

        self.assertEqual(calls.count("POST"), 1)
        self.assertCountEqual(outcomes, ["submitted", "blocked"])

    def test_poll_rig_uses_stored_id_and_downloads_only_allow_list(self) -> None:
        self.write_state({"rig_task_id": "rig-task-example"})
        requested: list[str] = []

        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            requested.append(request.full_url)
            if request.full_url.startswith(meshy.API_BASE):
                return FakeResponse(
                    {
                        "id": "rig-task-example",
                        "status": "SUCCEEDED",
                        "progress": 100,
                        "consumed_credits": 5,
                        "result": {
                            "rigged_character_glb_url": "https://files.example/rig.glb",
                            "basic_animations": {
                                "running_fbx_url": "https://files.example/run.fbx",
                                "unexpected_url": "https://files.example/nope.bin",
                            },
                            "unexpected_url": "https://files.example/nope.bin",
                        },
                    }
                )
            self.assertNotIn("Authorization", dict(request.header_items()))
            return FakeResponse(b"asset", json_response=False)

        with mock.patch("urllib.request.urlopen", side_effect=respond):
            result = meshy.poll_rig(
                self.state_path,
                self.output_dir,
                self.environment,
            )

        self.assertEqual(
            requested[0],
            f"{meshy.API_BASE}/rigging/rig-task-example",
        )
        self.assertEqual(
            set(requested[1:]),
            {
                "https://files.example/rig.glb",
                "https://files.example/run.fbx",
            },
        )
        self.assertEqual(
            set(result["files"]),
            {"rigged-character.glb", "basic-running.fbx"},
        )
        self.assertNotIn("https://", self.state_path.read_text(encoding="utf-8"))

    def test_poll_animation_stops_failed_branch_without_downloading(self) -> None:
        self.write_state(
            {
                "animation_task_id": "animation-task-example",
                "animation_attempted_at": "2030-01-01T00:00:00Z",
            }
        )
        with mock.patch(
            "urllib.request.urlopen",
            return_value=FakeResponse(
                {
                    "id": "animation-task-example",
                    "status": "CANCELED",
                    "progress": 25,
                    "consumed_credits": 0,
                    "task_error": {"message": "mocked canceled task"},
                    "result": {
                        "animation_fbx_url": "https://files.example/nope.fbx",
                    },
                }
            ),
        ) as urlopen:
            result = meshy.poll_animation(
                self.state_path,
                self.output_dir,
                self.environment,
            )

        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(result["status"], "CANCELED")
        self.assertFalse(self.output_dir.exists())
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertIn("animation_attempted_at", state)
        self.assertEqual(state["animation_status"], "CANCELED")

    def test_poll_animation_skips_empty_optional_result_urls(self) -> None:
        self.write_state(
            {
                "animation_task_id": "animation-task-example",
                "animation_attempted_at": "2030-01-01T00:00:00Z",
            }
        )
        requested: list[str] = []

        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            requested.append(request.full_url)
            if request.full_url.startswith(meshy.API_BASE):
                return FakeResponse(
                    {
                        "id": "animation-task-example",
                        "status": "SUCCEEDED",
                        "progress": 100,
                        "consumed_credits": 3,
                        "result": {
                            "animation_glb_url": "https://files.example/run.glb",
                            "animation_fbx_url": "https://files.example/run.fbx",
                            "processed_usdz_url": "",
                            "processed_armature_fbx_url": "",
                            "processed_animation_fps_fbx_url": (
                                "https://files.example/run-24fps.fbx"
                            ),
                        },
                    }
                )
            return FakeResponse(b"asset", json_response=False)

        with mock.patch("urllib.request.urlopen", side_effect=respond):
            result = meshy.poll_animation(
                self.state_path,
                self.output_dir,
                self.environment,
            )

        self.assertEqual(
            requested[1:],
            [
                "https://files.example/run.glb",
                "https://files.example/run.fbx",
                "https://files.example/run-24fps.fbx",
            ],
        )
        self.assertEqual(
            result["files"],
            ["animation.glb", "animation.fbx", "processed-24fps.fbx"],
        )

    def test_validator_ignores_images_not_referenced_by_visible_meshes(self) -> None:
        validator = load_blender_script("validate_meshy_reference")
        referenced = SimpleNamespace(
            name="referenced",
            size=(1_024, 512),
            packed_file=object(),
        )
        unreferenced = SimpleNamespace(
            name="unreferenced",
            size=(4_096, 4_096),
            packed_file=object(),
        )
        node = SimpleNamespace(type="TEX_IMAGE", image=referenced)
        material = SimpleNamespace(
            node_tree=SimpleNamespace(nodes=[node]),
        )
        mesh = SimpleNamespace(
            type="MESH",
            hide_render=False,
            hide_viewport=False,
            material_slots=[SimpleNamespace(material=material)],
        )
        validator.bpy.context = SimpleNamespace(
            scene=SimpleNamespace(objects=[mesh])
        )
        validator.bpy.data = SimpleNamespace(images=[referenced, unreferenced])

        self.assertEqual(
            validator.image_dimensions(),
            {"referenced": (1_024, 512)},
        )

    def test_validator_rejects_referenced_images_that_are_not_embedded(self) -> None:
        validator = load_blender_script("validate_meshy_reference")
        referenced = SimpleNamespace(
            name="referenced",
            size=(1_024, 512),
            packed_file=None,
        )
        node = SimpleNamespace(type="TEX_IMAGE", image=referenced)
        material = SimpleNamespace(
            node_tree=SimpleNamespace(nodes=[node]),
        )
        mesh = SimpleNamespace(
            type="MESH",
            hide_render=False,
            hide_viewport=False,
            material_slots=[SimpleNamespace(material=material)],
        )
        validator.bpy.context = SimpleNamespace(
            scene=SimpleNamespace(objects=[mesh])
        )
        validator.bpy.data = SimpleNamespace(images=[referenced])

        with self.assertRaisesRegex(AssertionError, "embedded/packed"):
            validator.image_dimensions()


if __name__ == "__main__":
    unittest.main()
