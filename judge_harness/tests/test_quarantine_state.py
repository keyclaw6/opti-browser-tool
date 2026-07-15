"""Strict-state and atomic-write regression tests for the T3 quarantine queue."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from opti_judge.quarantine import QuarantineQueue, QuarantineStateError


def _seed(path: Path) -> tuple[QuarantineQueue, dict[str, object]]:
    queue = QuarantineQueue(path)
    entry = queue.enqueue(
        task_id="task-a",
        run_ref="run-1/task-a/trace.jsonl",
        verifier_status="passed",
        reason="possible false positive",
        flags=[{"check": "expected_state", "severity": "suspicion"}],
    )
    return queue, entry.to_dict()


def _render(row: dict[str, object]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


class QuarantineStateContractTest(unittest.TestCase):
    def test_positive_framing_controls_and_round_trip(self) -> None:
        for label, ending in (
            ("no-final-lf", ""),
            ("one-final-lf", "\n"),
            ("crlf", "\r\n"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "queue.jsonl"
                queue, row = _seed(path)
                path.write_bytes((_render(row) + ending).encode("utf-8"))
                loaded = queue.pending()
                self.assertEqual([entry.to_dict() for entry in loaded], [row])

    def test_malformed_and_alternate_record_framing_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.jsonl"
            queue, row = _seed(path)
            line = _render(row)
            cases = {
                "zero-bytes": "",
                "whitespace-only": " \t ",
                "truncated-record": line + '\n{"entry_id":',
                "final-lone-cr": line + "\r",
                "interior-blank": line + "\n\n" + line + "\n",
                "double-trailing-lf": line + "\n\n",
            }
            for name, separator in (
                ("lone-cr", "\r"),
                ("vertical-tab", "\v"),
                ("form-feed", "\f"),
                ("file-separator", "\x1c"),
                ("nel", "\u0085"),
                ("line-separator", "\u2028"),
                ("paragraph-separator", "\u2029"),
            ):
                cases[name] = line + separator + line + "\n"
            for label, text in cases.items():
                with self.subTest(label=label):
                    path.write_bytes(text.encode("utf-8"))
                    with self.assertRaises(QuarantineStateError):
                        queue.pending()

    def test_invalid_entry_contract_and_unrelated_bad_rows_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.jsonl"
            queue, row = _seed(path)
            mutations: dict[str, tuple[str, object]] = {
                "bogus-verifier": ("verifier_status", "unknown"),
                "bogus-status": ("status", "open"),
                "pending-resolution": ("resolution", "true_success"),
                "flags-null": ("flags", None),
                "blank-entry-id": ("entry_id", ""),
                "blank-task-id": ("task_id", ""),
                "blank-run-ref": ("run_ref", ""),
                "blank-reason": ("reason", ""),
                "invalid-created-at": ("created_at", "yesterday"),
            }
            invalid_rows: dict[str, dict[str, object]] = {}
            for label, (field, replacement) in mutations.items():
                changed = copy.deepcopy(row)
                changed[field] = replacement
                invalid_rows[label] = changed
            extra = copy.deepcopy(row)
            extra["unexpected"] = True
            invalid_rows["extra-field"] = extra
            wrong_fingerprint = copy.deepcopy(row)
            wrong_fingerprint["flags"][0]["fingerprint"] = "0" * 64  # type: ignore[index]
            invalid_rows["wrong-fingerprint"] = wrong_fingerprint
            invalid_recorded_at = copy.deepcopy(row)
            invalid_recorded_at["flags"][0]["recorded_at"] = "yesterday"  # type: ignore[index]
            invalid_rows["invalid-flag-recorded-at"] = invalid_recorded_at

            duplicate_flag = copy.deepcopy(row)
            duplicate_flag["flags"].append(  # type: ignore[union-attr]
                copy.deepcopy(duplicate_flag["flags"][0])  # type: ignore[index]
            )
            invalid_rows["duplicate-flag-fingerprint"] = duplicate_flag

            backwards_resolution = copy.deepcopy(row)
            backwards_resolution.update(
                status="resolved",
                resolution="true_success",
                resolution_note="confirmed",
                resolved_at="2000-01-01T00:00:00Z",
            )
            invalid_rows["resolution-before-creation"] = backwards_resolution

            for label, changed in invalid_rows.items():
                with self.subTest(label=label):
                    path.write_text(_render(changed) + "\n", encoding="utf-8")
                    with self.assertRaises(QuarantineStateError):
                        queue.pending()

            malformed_unrelated = copy.deepcopy(row)
            malformed_unrelated["entry_id"] = "unrelated"
            malformed_unrelated["verifier_status"] = "bogus"
            path.write_text(
                _render(row) + "\n" + _render(malformed_unrelated) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(QuarantineStateError):
                queue.pending()

            duplicate = copy.deepcopy(row)
            path.write_text(
                _render(row) + "\n" + _render(duplicate) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(QuarantineStateError, "duplicate"):
                queue.pending()

    def test_non_finite_flags_and_caller_fingerprints_are_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                queue = QuarantineQueue(Path(tmp) / "queue.jsonl")
                with self.assertRaises(ValueError):
                    queue.enqueue(
                        task_id="task-a",
                        run_ref="run-1/task-a/trace.jsonl",
                        verifier_status="passed",
                        reason="possible false positive",
                        flags=[{"check": "expected_state", "score": value}],
                    )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.jsonl"
            queue, _ = _seed(path)
            row = json.loads(path.read_text(encoding="utf-8"))
            raw = _render(row).replace('"severity":"suspicion"', '"severity":NaN')
            path.write_text(raw + "\n", encoding="utf-8")
            with self.assertRaises(QuarantineStateError):
                queue.pending()

        with tempfile.TemporaryDirectory() as tmp:
            queue = QuarantineQueue(Path(tmp) / "queue.jsonl")
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                queue.enqueue(
                    task_id="task-a",
                    run_ref="run-1/task-a/trace.jsonl",
                    verifier_status="passed",
                    reason="possible false positive",
                    flags=[
                        {
                            "check": "expected_state",
                            "fingerprint": "0" * 64,
                        }
                    ],
                )

    def test_atomic_replace_failure_preserves_original_and_removes_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.jsonl"
            queue, _ = _seed(path)
            original = path.read_bytes()
            with mock.patch(
                "opti_judge.quarantine.os.replace",
                side_effect=OSError("synthetic replace failure"),
            ):
                with self.assertRaisesRegex(QuarantineStateError, "atomically"):
                    queue.enqueue(
                        task_id="task-b",
                        run_ref="run-1/task-b/trace.jsonl",
                        verifier_status="failed",
                        reason="possible false negative",
                    )
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])
            self.assertEqual(len(queue.pending()), 1)


if __name__ == "__main__":
    unittest.main()
