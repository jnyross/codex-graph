import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from root_workflow import evaluate_root_workflow  # noqa: E402


def worker(role="writer"):
    return {
        "role": role,
        "environment": "isolated_worktree",
        "read_scope": ["repository"],
        "write_scope": ["isolated draft"],
        "capabilities": {
            "durable_mutation": False,
            "real_checkout_integration": False,
        },
        "isolation_proof": "worktree:writer",
    }


def metadata():
    return {
        "revision": 7,
        "authority_preflight": {
            "revision": 7,
            "reachable_decision_loops": [],
            "reachable_mutations": [
                {"identity": "integrate-draft", "owner": "root"}
            ],
            "workers": [worker()],
            "generic_trigger_state": {"T1-WORKER-NEED": "fired"},
            "generic_topology": "L1",
            "evidence": ["evidence:preflight"],
        },
        "observed_effects": ["effect:read-complete"],
    }


class RootWorkflowTests(unittest.TestCase):
    def test_safety_precedes_complexity_without_forbidding_isolated_drafts(self):
        delegated = evaluate_root_workflow(metadata())
        self.assertEqual(delegated["selected_topology"], "L1")
        self.assertEqual(delegated["authority_preflight"]["status"], "allow_generation")
        self.assertTrue(delegated["execution_permission"]["delegated_work"])
        self.assertTrue(delegated["execution_permission"]["root_mutation"])
        self.assertFalse(delegated["execution_permission"]["delegated_mutation"])

        interactive_metadata = metadata()
        interactive_metadata["authority_preflight"]["reachable_decision_loops"] = [
            "review > human choice"
        ]
        interactive = evaluate_root_workflow(interactive_metadata)
        self.assertEqual(interactive["selected_topology"], "L0")
        self.assertEqual(
            interactive["authority_preflight"]["interactivity"]["verdict"],
            "interactive",
        )
        self.assertFalse(interactive["execution_permission"]["delegated_work"])
        self.assertEqual(interactive["workflow_state"], {"state": "continue", "final": False})

    def test_invalid_preflight_matrix_fails_closed(self):
        fixtures = {}

        fixtures["missing"] = metadata()
        del fixtures["missing"]["authority_preflight"]

        fixtures["malformed"] = metadata()
        fixtures["malformed"]["authority_preflight"] = "invalid"

        fixtures["stale"] = metadata()
        fixtures["stale"]["authority_preflight"]["revision"] = 6

        fixtures["ambiguous"] = metadata()
        fixtures["ambiguous"]["authority_preflight"]["reachable_mutations"].append(
            {"identity": "integrate-draft", "owner": "worker"}
        )

        fixtures["contradicted"] = metadata()
        fixtures["contradicted"]["authority_preflight"]["reachable_mutations"][0][
            "owner"
        ] = "worker"

        fixtures["unproved confinement"] = metadata()
        fixtures["unproved confinement"]["authority_preflight"]["workers"][0][
            "isolation_proof"
        ] = ""

        fixtures["missing worker confinement"] = metadata()
        fixtures["missing worker confinement"]["authority_preflight"]["workers"] = []

        fixtures["read-only L4 without confinement"] = metadata()
        read_only_l4 = fixtures["read-only L4 without confinement"][
            "authority_preflight"
        ]
        read_only_l4["reachable_mutations"] = []
        read_only_l4["workers"] = []
        read_only_l4["generic_trigger_state"] = {"T4-SHARDED-RECOVERY": "fired"}
        read_only_l4["generic_topology"] = "L4"

        fixtures["malformed trigger value"] = metadata()
        fixtures["malformed trigger value"]["authority_preflight"][
            "generic_trigger_state"
        ] = {"T1-WORKER-NEED": []}

        fixtures["malformed topology"] = metadata()
        fixtures["malformed topology"]["authority_preflight"]["generic_topology"] = []

        for name, fixture in fixtures.items():
            with self.subTest(name=name):
                result = evaluate_root_workflow(fixture)
                self.assertEqual(result["selected_topology"], "L0")
                self.assertEqual(result["authority_preflight"]["status"], "block")
                self.assertEqual(
                    result["execution_permission"],
                    {
                        "root_mutation": False,
                        "delegated_work": False,
                        "delegated_mutation": False,
                        "stopped_workers": [],
                    },
                )
                self.assertEqual(result["workflow_state"], {"state": "blocked", "final": True})
                self.assertTrue(result["authority_preflight"]["reasons"])

    def test_runtime_decision_discovery_requires_a_root_l0_plan_and_retains_facts(self):
        result = evaluate_root_workflow(
            metadata(),
            [
                {
                    "type": "decision_loop_discovered",
                    "path": "draft > human approval",
                    "evidence": ["evidence:runtime-decision"],
                    "observed_effects": ["effect:draft-created"],
                }
            ],
        )

        self.assertEqual(result["selected_topology"], "L0")
        self.assertEqual(result["authority_preflight"]["status"], "runtime_replan")
        self.assertEqual(result["authority_preflight"]["required_action"], "root_l0_plan")
        self.assertFalse(result["execution_permission"]["delegated_work"])
        self.assertEqual(result["workflow_state"], {"state": "continue", "final": False})
        self.assertEqual(
            result["retained_evidence"],
            ["evidence:preflight", "evidence:runtime-decision"],
        )
        self.assertEqual(
            result["observed_effects"],
            ["effect:read-complete", "effect:draft-created"],
        )

        malformed = evaluate_root_workflow(
            metadata(),
            [
                {
                    "type": "decision_loop_discovered",
                    "path": "",
                    "evidence": ["evidence:valid-before-invalidation"],
                    "observed_effects": ["effect:already-observed-at-runtime"],
                }
            ],
        )
        self.assertEqual(malformed["workflow_state"], {"state": "blocked", "final": True})
        self.assertIn(
            "evidence:valid-before-invalidation", malformed["retained_evidence"]
        )
        self.assertIn(
            "effect:already-observed-at-runtime", malformed["observed_effects"]
        )

    def test_mixed_validity_evidence_and_effect_lists_retain_valid_facts(self):
        mixed = metadata()
        mixed["authority_preflight"]["evidence"] = [
            "evidence:preflight",
            None,
            "evidence:second",
        ]
        mixed["observed_effects"] = [
            "effect:read-complete",
            3,
            "effect:second",
        ]
        result = evaluate_root_workflow(
            mixed,
            [
                {
                    "type": "decision_loop_discovered",
                    "path": "runtime choice",
                    "evidence": [
                        "evidence:runtime",
                        {},
                        "evidence:runtime-second",
                    ],
                    "observed_effects": [
                        "effect:runtime",
                        "",
                        "effect:runtime-second",
                    ],
                }
            ],
        )

        self.assertEqual(result["workflow_state"], {"state": "blocked", "final": True})
        self.assertEqual(
            result["retained_evidence"],
            [
                "evidence:preflight",
                "evidence:second",
                "evidence:runtime",
                "evidence:runtime-second",
            ],
        )
        self.assertEqual(
            result["observed_effects"],
            [
                "effect:read-complete",
                "effect:second",
                "effect:runtime",
                "effect:runtime-second",
            ],
        )
        self.assertTrue(
            {
                "malformed_authority_evidence",
                "malformed_observed_effects",
                "malformed_runtime_evidence",
                "malformed_runtime_effects",
            }.issubset(result["authority_preflight"]["reasons"])
        )

    def test_worker_discovered_mutation_stops_before_action_and_requires_reproof(self):
        discovery = {
            "type": "worker_mutation_discovered",
            "worker_role": "writer",
            "mutation": {"identity": "publish-draft", "owner": "root"},
            "evidence": ["evidence:mutation-discovery"],
        }

        blocked = evaluate_root_workflow(metadata(), [discovery])
        self.assertEqual(blocked["selected_topology"], "L0")
        self.assertEqual(blocked["authority_preflight"]["status"], "block")
        self.assertEqual(blocked["execution_permission"]["stopped_workers"], ["writer"])
        self.assertFalse(blocked["execution_permission"]["root_mutation"])

        wrong_worker = copy.deepcopy(discovery)
        wrong_worker["revision"] = 8
        wrong_worker["worker_confinement"] = worker("reviewer")
        wrong_worker_result = evaluate_root_workflow(metadata(), [wrong_worker])
        self.assertEqual(
            wrong_worker_result["workflow_state"], {"state": "blocked", "final": True}
        )

        reproved_discovery = copy.deepcopy(discovery)
        reproved_discovery["revision"] = 8
        reproved_discovery["worker_confinement"] = worker()
        reproved = evaluate_root_workflow(metadata(), [reproved_discovery])
        self.assertEqual(reproved["selected_topology"], "L1")
        self.assertEqual(reproved["authority_preflight"]["status"], "allow_generation")
        self.assertEqual(reproved["authority_preflight"]["revision"], 8)
        self.assertEqual(reproved["execution_permission"]["stopped_workers"], ["writer"])
        self.assertTrue(reproved["execution_permission"]["root_mutation"])
        self.assertTrue(reproved["execution_permission"]["delegated_work"])
        self.assertFalse(reproved["execution_permission"]["delegated_mutation"])
        self.assertIn("evidence:preflight", reproved["retained_evidence"])

        parallel_metadata = metadata()
        parallel_metadata["authority_preflight"]["workers"].append(worker("reviewer"))
        writer_reproof = copy.deepcopy(reproved_discovery)
        reviewer_reproof = {
            "type": "worker_mutation_discovered",
            "worker_role": "reviewer",
            "mutation": {"identity": "publish-review", "owner": "root"},
            "revision": 8,
            "worker_confinement": worker("reviewer"),
        }
        parallel = evaluate_root_workflow(
            parallel_metadata, [writer_reproof, reviewer_reproof]
        )
        self.assertEqual(parallel["authority_preflight"]["status"], "allow_generation")
        self.assertEqual(parallel["authority_preflight"]["revision"], 8)
        self.assertEqual(
            parallel["execution_permission"]["stopped_workers"], ["writer", "reviewer"]
        )
        self.assertTrue(parallel["execution_permission"]["delegated_work"])

    def test_process_facts_and_attempt_verdicts_never_become_workflow_success(self):
        process_facts = [
            {"type": "process_exit", "code": 0},
            {"type": "generated_output", "artifact": "candidate.json"},
            {"type": "attempt_pass", "attempt": "validator-1"},
        ]
        result = evaluate_root_workflow(metadata(), process_facts)
        self.assertEqual(result["workflow_state"], {"state": "continue", "final": False})
        self.assertNotEqual(result["workflow_state"]["state"], "accepted")

        waiting = evaluate_root_workflow(
            metadata(),
            [
                {"type": "human_decision_required", "path": "approval"},
                {"type": "decision_loop_discovered", "path": "later choice"},
            ],
        )
        self.assertEqual(
            waiting["workflow_state"],
            {"state": "human_decision_required", "final": False},
        )
        self.assertEqual(waiting["selected_topology"], "L0")


if __name__ == "__main__":
    unittest.main()
