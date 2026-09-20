from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.training.audit import audit_run


class TrainingAuditTest(unittest.TestCase):
    def test_accepts_complete_matching_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "best.pt"
            checkpoint.write_bytes(b"checkpoint")
            digest = hashlib.sha256(b"checkpoint").hexdigest()
            expected = {"model_kind": "joint", "views": 8, "cv_fold": 0, "epochs": 2}
            (root / "config.json").write_text(json.dumps(expected), encoding="utf-8")
            (root / "history.json").write_text(json.dumps([{}, {}]), encoding="utf-8")
            (root / "summary.json").write_text(
                json.dumps({"epochs_completed": 2, "checkpoint_sha256": digest, "test_used": False}),
                encoding="utf-8",
            )
            self.assertTrue(audit_run(root, expected)["complete"])

    def test_reports_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = audit_run(
                Path(directory),
                {"model_kind": "joint", "views": 8, "cv_fold": 0, "epochs": 20},
            )
            self.assertFalse(result["complete"])
            self.assertIn("누락", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
