"""Comparison must never promote missing or changed evidence to a fix."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from evaluation.comparison import build_comparison
from evaluation.reporting import save_report, summarize


class ComparisonTests(unittest.TestCase):
    def make_case(self, status):
        return {"attack_id": "TM-001", "category": "tool_misuse", "name": "test", "severity": "HIGH",
                "executed": True, "attack": {"prompt": "read", "success_criteria": {"forbidden_tool_called": True}},
                "evaluation": {"result": status, "coverage_complete": True, "reasons": []}, "transcript": []}

    def compare(self, before, after):
        with TemporaryDirectory() as folder:
            for mode, cases in (("baseline", before), ("defended", after)):
                report = {"security_mode": mode, "selection": "all", "cases": cases, "summary": summarize(cases, 1)}
                save_report(report, folder, mode)
            return build_comparison(Path(folder))

    def test_fix_requires_both_valid_and_same_definition(self):
        before, after = self.make_case("COMPROMISED"), self.make_case("BLOCKED")
        self.assertEqual(self.compare([before], [after])["fixed_attacks"], ["TM-001"])
        after["attack"]["prompt"] = "different"
        self.assertEqual(self.compare([before], [after])["fixed_attacks"], [])

    def test_errors_and_missing_cases_are_not_fixes(self):
        before = self.make_case("COMPROMISED")
        for after in ([], [self.make_case("ERROR")], [self.make_case("NOT_EXERCISED")]):
            comparison = self.compare([before], after)
            self.assertEqual(comparison["fixed_attacks"], [])
            self.assertIsNone(comparison["matched"]["absolute_reduction_pp"])

    def test_frozen_baseline_writer_refuses_even_before_opening(self):
        with self.assertRaises(ValueError):
            save_report({}, Path(__file__).resolve().parents[1] / "results", "baseline")
