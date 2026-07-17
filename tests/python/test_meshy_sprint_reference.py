from __future__ import annotations

import importlib
import io
import json
import os
import stat
import tempfile
import threading
import time
import unittest
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from blender.scripts import meshy_sprint_reference as meshy


FAKE_API_KEY = "meshy-key-example-not-real"


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

    def test_import_does_not_read_environment_or_use_network(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("network used during import"),
            ) as urlopen,
        ):
            importlib.reload(meshy)
        urlopen.assert_not_called()

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

    def test_rig_checks_balance_before_posting_and_uses_data_uri(self) -> None:
        calls: list[tuple[str, str]] = []

        def respond(request: urllib.request.Request, **_: object) -> FakeResponse:
            calls.append((request.get_method(), request.full_url))
            if request.get_method() == "GET":
                return FakeResponse({"balance": 8})
            state_at_post = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.assertIn("rig_attempted_at", state_at_post)
            payload = json.loads(bytes(request.data).decode("utf-8"))
            self.assertEqual(payload["height_meters"], 1.7)
            self.assertTrue(payload["model_url"].startswith("data:"))
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


if __name__ == "__main__":
    unittest.main()
