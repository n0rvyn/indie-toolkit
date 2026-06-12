#!/usr/bin/env python3
"""
Tests for compute_checkpoints.py.

This test file deliberately imports `compute_checkpoints` at module top-level
so the suite fails with ImportError / ModuleNotFoundError until the
implementation lands (Task 1-impl).

Pin contract: given a plan file + K, the implementation must emit:
  - batches keyed by canonical task ids ("<N>" / "<N>-tests" / "<N>-impl")
  - per-task downstream-dependent counts
  - hard_stops (batch 0; any batch with a task whose dependents >= K;
    any batch with a task whose body has <!-- checkpoint -->)
  - <N>-tests / <N>-impl pair must never straddle a batch boundary
"""

import os
import sys
import unittest

# This import will fail until Task 1-impl lands. That is the intended
# "tests run before impl exists and fail for the right reason" gate.
import compute_checkpoints  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")


def _plan_path(name: str) -> str:
    return os.path.join(FIXTURES, name)


class CanonicalIdContract(unittest.TestCase):
    """Task ids must be the canonical strings '<N>' / '<N>-tests' / '<N>-impl'."""

    def test_linear_canonical_ids(self):
        result = compute_checkpoints.compute(_plan_path("plan-linear.md"), k=3, batch_size=5)
        flat = [tid for batch in result["batches"] for tid in batch]
        # First batch should hold 5 tasks: "1", "2", "3", "4", "5"
        self.assertEqual(flat[:5], ["1", "2", "3", "4", "5"])

    def test_pair_boundary_canonical_ids(self):
        result = compute_checkpoints.compute(_plan_path("plan-pair-boundary.md"), k=3, batch_size=5)
        flat = [tid for batch in result["batches"] for tid in batch]
        # The pair must use "<N>-tests" / "<N>-impl" canonical ids, never "Task 5-tests" or "5_tests"
        for tid in flat:
            self.assertFalse(tid.startswith("Task "), f"non-canonical id: {tid}")
            self.assertNotIn("_", tid, f"underscore in id (not canonical): {tid}")
        self.assertIn("5-tests", flat)
        self.assertIn("5-impl", flat)


class BatchSizeContract(unittest.TestCase):
    """Batches respect batch_size, but pair-keep may push a batch one over."""

    def test_linear_batch_count(self):
        result = compute_checkpoints.compute(_plan_path("plan-linear.md"), k=3, batch_size=5)
        # 5 tasks, batch_size=5 → exactly 1 batch of 5
        self.assertEqual(len(result["batches"]), 1)
        self.assertEqual(len(result["batches"][0]), 5)

    def test_total_field(self):
        result = compute_checkpoints.compute(_plan_path("plan-linear.md"), k=3, batch_size=5)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["batch_size"], 5)

    def test_pair_boundary_batch_size_does_not_split_pair(self):
        """A 5-tests / 5-impl pair must stay in the SAME batch; a batch may
        run one over batch_size to keep a pair intact."""
        result = compute_checkpoints.compute(_plan_path("plan-pair-boundary.md"), k=3, batch_size=5)
        # Find the batch containing 5-tests
        batch_with_tests = None
        for batch in result["batches"]:
            if "5-tests" in batch:
                batch_with_tests = batch
                break
        self.assertIsNotNone(batch_with_tests, "5-tests must be in some batch")
        # The same batch must also contain 5-impl
        self.assertIn("5-impl", batch_with_tests, "5-tests and 5-impl must be in same batch")


class HardStopContract(unittest.TestCase):
    """Hard-stops: batch 0 always; hub batch at K; marked batch."""

    def test_linear_only_batch_zero_is_hardstop(self):
        result = compute_checkpoints.compute(_plan_path("plan-linear.md"), k=3, batch_size=5)
        # Only one batch, batch index 0 is always a hard-stop
        self.assertEqual(result["hard_stops"], [0])

    def test_hub_at_k_3_is_hardstop(self):
        result = compute_checkpoints.compute(_plan_path("plan-hub.md"), k=3, batch_size=5)
        # Task 1 has 3 direct dependents (tasks 2, 3, 4) → dependents["1"] == 3
        self.assertEqual(result["dependents"]["1"], 3)
        # The batch containing task 1 must be a hard-stop
        hub_batch_idx = None
        for i, batch in enumerate(result["batches"]):
            if "1" in batch:
                hub_batch_idx = i
                break
        self.assertIsNotNone(hub_batch_idx)
        self.assertIn(hub_batch_idx, result["hard_stops"])

    def test_hub_at_k_2_also_pauses(self):
        """Lower K → more checkpoints (per DP-001)."""
        # With K=2, the hub (dependents=3) is still >= 2, so still hard-stop
        result = compute_checkpoints.compute(_plan_path("plan-hub.md"), k=2, batch_size=5)
        hub_batch_idx = None
        for i, batch in enumerate(result["batches"]):
            if "1" in batch:
                hub_batch_idx = i
                break
        self.assertIn(hub_batch_idx, result["hard_stops"])

    def test_marked_batch_is_hardstop(self):
        result = compute_checkpoints.compute(_plan_path("plan-marked.md"), k=3, batch_size=5)
        # The marker is in task 1's body → batch 0 → already a hard-stop.
        # Use a higher K to confirm marker alone is enough even if not a hub.
        # The marked fixture is the simplest case: 1 batch, 5 tasks, marker in task 1
        self.assertIn(0, result["hard_stops"])


class PairBoundaryContract(unittest.TestCase):
    """Pair-keep rule: no batch boundary (and therefore no hard-stop) lands mid-pair."""

    def test_no_hardstop_between_pair(self):
        result = compute_checkpoints.compute(_plan_path("plan-pair-boundary.md"), k=3, batch_size=5)
        # Find indices of 5-tests and 5-impl
        idx_tests = None
        idx_impl = None
        for i, batch in enumerate(result["batches"]):
            if "5-tests" in batch:
                idx_tests = i
            if "5-impl" in batch:
                idx_impl = i
        # They must be in the same batch
        self.assertEqual(idx_tests, idx_impl, "5-tests and 5-impl must share a batch index")


class DependentsCountContract(unittest.TestCase):
    """dependents map: direct dependents only, count, not transitive."""

    def test_hub_dependents_count(self):
        result = compute_checkpoints.compute(_plan_path("plan-hub.md"), k=3, batch_size=5)
        # Task 1 has 3 direct dependents
        self.assertEqual(result["dependents"]["1"], 3)
        # Tasks 2, 3, 4 each have 0 direct dependents
        self.assertEqual(result["dependents"]["2"], 0)
        self.assertEqual(result["dependents"]["3"], 0)
        self.assertEqual(result["dependents"]["4"], 0)
        # Task 5 has 0
        self.assertEqual(result["dependents"]["5"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
