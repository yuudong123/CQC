from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.training.evaluate import claim_final_test


class FinalEvaluationTest(unittest.TestCase):
    def test_checkpoint_can_claim_final_test_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "final.pt"
            checkpoint.write_bytes(b"checkpoint")
            output = Path(directory) / "test-result.json"
            marker = claim_final_test(checkpoint, output)
            self.assertEqual(
                json.loads(marker.read_text(encoding="utf-8")),
                {"output": str(output)},
            )
            with self.assertRaisesRegex(RuntimeError, "이미 실행 또는 시도"):
                claim_final_test(checkpoint, output)


if __name__ == "__main__":
    unittest.main()
