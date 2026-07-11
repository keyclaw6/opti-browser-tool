from __future__ import annotations

import os
import unittest
from pathlib import Path

from opti_eval.validation import validate_repository


class RepositoryValidationTest(unittest.TestCase):
    def test_complete_repository(self) -> None:
        root = Path(os.environ["OPTI_BROWSER_REPO_ROOT"])
        report = validate_repository(root)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["candidate_count"], 140)
        self.assertEqual(report["catalog_count"], 140)
        self.assertEqual(report["primary_count"], 140)
        self.assertEqual(report["smoke_count"], 20)


if __name__ == "__main__":
    unittest.main()
